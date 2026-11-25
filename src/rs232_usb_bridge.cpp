#include "rs232_usb_bridge.h"

namespace {
bool ValidFraming(unsigned parity, unsigned dataBits, unsigned stopBits) {
  return parity <= 2 && (dataBits == 7 || dataBits == 8) && (stopBits == 1 || stopBits == 2);
}
unsigned Resolve(unsigned requested, unsigned mask) {
  if (requested == E64_RS232_USB_AUTO) {
    for (unsigned i = 1; i <= Rs232UsbBridge::MaxAdapters; ++i)
      if (mask & (1u << (i - 1))) return i;
    return 0;
  }
  return requested && requested <= Rs232UsbBridge::MaxAdapters &&
      (mask & (1u << (requested - 1))) ? requested : 0;
}
}

Rs232UsbBridge::Rs232UsbBridge()
    : status_{}, discovery_{}, open_(false), txRead_(0), txWrite_(0), rxRead_(0), rxWrite_(0),
      port_(0), configured_(0), fault_(0), pendingEpoch_(0), pendingCount_(0),
      pending_(false), input_(false), nextInput_(true) {}

void Rs232UsbBridge::Clear() {
  status_.txDropped += status_.txQueued;
  status_.rxDropped += status_.rxQueued;
  status_.txQueued = status_.rxQueued = 0;
  txRead_ = txWrite_ = rxRead_ = rxWrite_ = 0;
  status_.ready = 0;
}

int Rs232UsbBridge::Open(unsigned adapter, unsigned baud) {
  return OpenConfigured(adapter, baud, 0, 8, 1);
}
int Rs232UsbBridge::OpenConfigured(unsigned adapter, unsigned baud, unsigned parity,
                                  unsigned dataBits, unsigned stopBits) {
  if (!ValidFraming(parity, dataBits, stopBits)) return -1;
  if (!adapter || (adapter > MaxAdapters && adapter != E64_RS232_USB_AUTO) || (baud != 300 && baud != 600 && baud != 1200 && baud != 2400 && baud != 9600)) return -1;
  Guard guard(lock_);
  Clear();
  open_ = true;
  status_.adapter = adapter;
  discovery_.requested = adapter;
  discovery_.resolved = Resolve(adapter, discovery_.compatibleMask);
  status_.baud = baud;
  status_.parity = parity;
  status_.dataBits = dataBits;
  status_.stopBits = stopBits;
  ++status_.epoch;
  return 0; // Logical session survives physical absence; never modem fallback.
}
void Rs232UsbBridge::Close() {
  Guard guard(lock_);
  Clear();
  open_ = false;
  status_.adapter = 0;
  ++status_.epoch;
}
int Rs232UsbBridge::SetBaud(unsigned baud) {
  if (baud != 300 && baud != 600 && baud != 1200 && baud != 2400 && baud != 9600) return -1;
  Guard guard(lock_);
  if (baud != status_.baud) {
    Clear();
    status_.baud = baud;
    ++status_.epoch;
  }
  return 0;
}
int Rs232UsbBridge::SetFraming(unsigned parity, unsigned dataBits, unsigned stopBits) {
  if (!ValidFraming(parity, dataBits, stopBits)) return -1;
  Guard guard(lock_);
  if (status_.parity != parity || status_.dataBits != dataBits || status_.stopBits != stopBits) {
    Clear();
    status_.parity = parity;
    status_.dataBits = dataBits;
    status_.stopBits = stopBits;
    ++status_.epoch;
  }
  return 0;
}
int Rs232UsbBridge::Put(uint8_t byte) {
  Guard guard(lock_);
  if (!open_ || !status_.ready || status_.txQueued == Capacity) {
    ++status_.txDropped;
    return -1; // Drop newest; never block the emulated CPU.
  }
  tx_[txWrite_] = byte;
  txWrite_ = (txWrite_ + 1) % Capacity;
  ++status_.txQueued;
  return 0;
}
int Rs232UsbBridge::Get(uint8_t *byte) {
  Guard guard(lock_);
  if (!byte || !open_ || !status_.ready || !status_.rxQueued) return 0;
  *byte = rx_[rxRead_];
  rxRead_ = (rxRead_ + 1) % Capacity;
  --status_.rxQueued;
  return 1;
}
Rs232UsbStatus Rs232UsbBridge::Status() {
  Guard guard(lock_);
  return status_;
}
int Rs232UsbBridge::Select(unsigned selection) {
  if (selection > MaxAdapters && selection != E64_RS232_USB_AUTO) return -1;
  Guard guard(lock_);
  if (discovery_.requested != selection) {
    Clear();
    open_ = false;
    status_.adapter = 0;
    ++status_.epoch;
    discovery_.requested = selection;
    discovery_.resolved = Resolve(selection, discovery_.compatibleMask);
  }
  return 0;
}
e64_rs232_usb_discovery_t Rs232UsbBridge::Discovery() {
  Guard guard(lock_);
  auto result = discovery_;
  result.ready = open_ && status_.adapter == result.requested && status_.ready;
  return result;
}
void Rs232UsbBridge::PublishDiscovery(unsigned mask) {
  Guard guard(lock_);
  discovery_.compatibleMask = mask & 0xffffu;
  // Resolve against the current preference, never a stale discovery selection.
  unsigned resolved = Resolve(discovery_.requested, discovery_.compatibleMask);
  if (resolved != discovery_.resolved && open_ && status_.ready) {
    Clear();
    ++status_.epoch;
  }
  discovery_.resolved = resolved;
}
void Rs232UsbBridge::Removed(Rs232UsbPort *port) {
  if (!port || port != port_) return;
  port_ = 0;
  configured_ = fault_ = 0;
  Guard guard(lock_);
  if (pending_ && !input_) status_.txDropped += pendingCount_;
  pending_ = false;
  ++status_.disconnects;
  Clear();
  ++status_.epoch;
}
void Rs232UsbBridge::Service(Rs232UsbPort *candidate, unsigned adapter) {
  ServiceAtEpoch(candidate, adapter, Status().epoch);
}
void Rs232UsbBridge::ServiceAtEpoch(Rs232UsbPort *candidate, unsigned adapter, unsigned epoch) {
  // Discovery used a snapshot. Never configure/send to a different selection
  // if the emulator changed it while the USB owner was looking up uttyN.
  {
    Guard guard(lock_);
    if (status_.adapter != adapter || status_.epoch != epoch) return;
  }
  if (candidate != port_) {
    bool replacing = port_ != nullptr;
    Removed(port_);
    // Removed advances the epoch for our own attachment transition. Account
    // for exactly that increment, never adopt a concurrent caller's epoch.
    if (replacing) ++epoch;
    port_ = candidate;
    configured_ = fault_ = 0;
    nextInput_ = true;
  }
  if (!port_) return;
  // Evaluate only while lock_ is held. Keep the discovered candidate and
  // selection fixed for this entire pass, including after re-entrant calls.
  auto current = [&]() {
    return port_ == candidate && status_.adapter == adapter && status_.epoch == epoch;
  };
  uint8_t bytes[64];
  Rs232UsbStatus wanted;
  if (pending_) {
    Rs232UsbReceiveStatus received = {};
    int result = candidate->PollWithStatus(bytes, sizeof bytes, &received);
    if (port_ != candidate) return; // Removal already retired this request.
    if (result == -2) return;
    Guard guard(lock_);
    if (result < 0 || result > (int) sizeof bytes || (!input_ && (unsigned) result != pendingCount_)) {
      ++status_.errors;
      if (!input_) status_.txDropped += pendingCount_;
      // Do not retry an ambiguous failed OUT: the peer may have seen a prefix.
      if (current() && pendingEpoch_ == status_.epoch) {
        Clear();
        fault_ = status_.epoch;
      }
    } else if (input_ && current() && pendingEpoch_ == status_.epoch && status_.ready) {
      // Diagnostic only: preserve payload delivery, including flagged packets.
      // Header-only packets also count. Old-epoch observations are ignored.
      if (received.headerValid) {
        ++status_.rxStatusObservations;
        if (received.overrun) ++status_.rxOverrunObservations;
        if (received.parityError) ++status_.rxParityObservations;
        if (received.framingError) ++status_.rxFramingObservations;
        if (received.breakDetected) ++status_.rxBreakObservations;
      }
      for (int i = 0; i < result; ++i) {
        if (status_.rxQueued == Capacity) { ++status_.rxDropped; continue; }
        rx_[rxWrite_] = bytes[i];
        rxWrite_ = (rxWrite_ + 1) % Capacity;
        ++status_.rxQueued;
      }
    } else if (input_) status_.rxDropped += (unsigned) result;
    pending_ = false;
    // Completion accounting above belongs to the consumed request. Do not
    // continue this pass using a newly selected session's configuration.
    if (!current()) return;
  }
  // Consume a completion left by an earlier logical session before controls.
  bool idle = candidate->Idle();
  {
    Guard guard(lock_);
    if (!current()) return;
    wanted = status_;
  }
  if (!idle) {
    candidate->Poll(bytes, sizeof bytes);
    return;
  }
  if (!wanted.adapter || fault_ == wanted.epoch) return;
  if (configured_ != wanted.epoch) {
    bool ok = candidate->ConfigureLine(wanted.baud, wanted.parity, wanted.dataBits, wanted.stopBits);
    // USB owner only; never under lock.
    Guard guard(lock_);
    if (!current()) return;
    status_.ready = ok ? 1 : 0;
    if (!ok) { ++status_.errors; fault_ = wanted.epoch; return; }
    configured_ = wanted.epoch;
  }
  unsigned count = 64;
  bool input = true;
  {
    Guard guard(lock_);
    if (!current() || !status_.ready || status_.epoch != configured_) return;
    if (!nextInput_ && status_.txQueued) {
      input = false;
      count = status_.txQueued < Packet ? status_.txQueued : (unsigned) Packet;
      for (unsigned i = 0; i < count; ++i) {
        bytes[i] = tx_[txRead_];
        txRead_ = (txRead_ + 1) % Capacity;
      }
      status_.txQueued -= count;
    }
    pendingEpoch_ = status_.epoch;
  }
  int result = candidate->Submit(input, bytes, count);
  if (port_ != candidate) return; // A re-entrant removal owns cleanup/accounting.
  if (result != 1) {
    Guard guard(lock_);
    ++status_.errors;
    if (!input) status_.txDropped += count;
    if (current() && pendingEpoch_ == status_.epoch) {
      Clear();
      fault_ = status_.epoch;
    }
    return;
  }
  // A successful submission still needs draining if Submit changed selection.
  // Keep its original pendingEpoch_; it cannot deliver into the new session.
  pending_ = true;
  input_ = input;
  pendingCount_ = input ? 0 : count;
  nextInput_ = !input;
}
