#include "rs232_usb_bridge.h"
#include "../third_party/vice-3.3/src/rs232drv/rs232usb.h"
#include <circle/devicenameservice.h>
#include <circle/usb/usbserial.h>
#include <circle/usb/usbserialhost.h>
#include <circle/usb/usbdevice.h>
#include <circle/usb/usbhostcontroller.h>
#include <circle/timer.h>
#include <circle/logger.h>

namespace {
Rs232UsbBridge bridge;
// A previously selected, still-connected adapter can retain custom framing
// and UART FIFO data while Auto uses another device. Rebindings after custom
// use conservatively purge; initial/unchanged 8N1 keeps its original controls.
bool customDeviceMayRemain = false;
class CircleSerialPort : public Rs232UsbPort {
public:
  CUSBSerialDevice *device = nullptr;
  CDevice::TRegistrationHandle removal = nullptr;
  unsigned index = 0;
  bool firstPacket = true;
  unsigned appliedParity = 0, appliedDataBits = 8, appliedStopBits = 1;
  bool framingUncertain = false;
  bool Configure(unsigned baud) override {
    return ConfigureLine(baud, 0, 8, 1);
  }
  bool ConfigureLine(unsigned baud, unsigned parity, unsigned dataBits, unsigned stopBits) override {
    if (parity > 2 || (dataBits != 7 && dataBits != 8) || (stopBits != 1 && stopBits != 2)) return false;
    if (parity || dataBits != 8 || stopBits != 1) customDeviceMayRemain = true;
    TUSBSerialParity mappedParity;
    switch (parity) {
      case 0: mappedParity = USBSerialParityNone; break;
      case 1: mappedParity = USBSerialParityEven; break;
      case 2: mappedParity = USBSerialParityOdd; break;
      default: return false;
    }
    CLogger::Get()->Write("rs232", LogNotice, "FTDI activation begin (%u baud)", baud);
    auto *host = device->GetHostDevice();
    // Service waits for the old URB before calling here. Purge adapter FIFOs
    // only across framing changes; unchanged 8N1 uses its original controls.
    bool reframe = framingUncertain || parity != appliedParity || dataBits != appliedDataBits || stopBits != appliedStopBits;
    if (reframe) framingUncertain = true;
    auto purge = [host](unsigned value) {
      return host->GetHost()->ControlMessage(host->GetEndpoint0(),
          REQUEST_OUT | REQUEST_VENDOR | REQUEST_TO_DEVICE,
          0 /* FTDI_SIO_RESET */, value, 0, nullptr, 0) >= 0;
    };
    device->SetOptions(0); // Raw binary, no CR/LF translation.
    bool ok = host->EnableAsyncIO();
    if (ok && reframe) ok = purge(1 /* purge RX */) && purge(2 /* purge TX */);
    if (ok) {
      CLogger::Get()->Write("rs232", LogNotice, "FTDI activation: baud control begin");
      ok = device->SetBaudRate(baud);
    }
    if (ok) {
      CLogger::Get()->Write("rs232", LogNotice, "FTDI activation: baud end, framing control begin");
      ok = device->SetLineProperties(dataBits == 7 ? USBSerialDataBits7 : USBSerialDataBits8,
                                    mappedParity, stopBits == 1 ? USBSerialStopBits1 : USBSerialStopBits2);
    }
    if (ok && reframe) ok = purge(1 /* discard RX collected during control changes */);
    if (ok) {
      appliedParity = parity;
      appliedDataBits = dataBits;
      appliedStopBits = stopBits;
      framingUncertain = false;
    }
    firstPacket = true;
    CLogger::Get()->Write("rs232", LogNotice, "FTDI activation end (%u)", (unsigned) ok);
    return ok;
  }
  bool Idle() const override { return device->GetHostDevice()->SerialPacketIdle(); }
  int Submit(bool in, const uint8_t *p, unsigned n) override {
    if (firstPacket) CLogger::Get()->Write("rs232", LogNotice, "FTDI first bulk submit begin");
    int result = device->GetHostDevice()->SubmitSerialPacket(in, p, n);
    if (firstPacket) CLogger::Get()->Write("rs232", LogNotice, "FTDI first bulk submit end (%d)", result);
    firstPacket = false;
    return result;
  }
  int Poll(uint8_t *p, unsigned n) override {
    return device->GetHostDevice()->PollSerialPacket(p, n);
  }
  int PollWithStatus(uint8_t *p, unsigned n, Rs232UsbReceiveStatus *status) override {
    if (status) *status = {};
    TUSBSerialPacketStatus raw = {};
    int result = device->GetHostDevice()->PollSerialPacketWithStatus(p, n, &raw);
    if (status && result >= 0 && raw.HeaderValid) {
      status->headerValid = true;
      status->modemStatus = raw.ModemStatus;
      status->lineStatus = raw.LineStatus;
      // FTDI line-status flags describe observations, not damaged byte indices.
      status->overrun = (raw.LineStatus & 0x02) != 0;
      status->parityError = (raw.LineStatus & 0x04) != 0;
      status->framingError = (raw.LineStatus & 0x08) != 0;
      status->breakDetected = (raw.LineStatus & 0x10) != 0;
    }
    return result;
  }
} port;

void Removed(CDevice *, void *) {
  bridge.Removed(&port);
  auto discovery = bridge.Discovery();
  if (port.index) bridge.PublishDiscovery(discovery.compatibleMask & ~(1u << (port.index - 1)));
  port.device = nullptr;
  port.removal = nullptr;
  port.index = 0;
}
}
extern "C" int e64_rs232_usb_select(unsigned selection) { return bridge.Select(selection); }
extern "C" void e64_rs232_usb_discovery(e64_rs232_usb_discovery_t *discovery) {
  if (discovery) *discovery = bridge.Discovery();
}
extern "C" void e64_rs232_usb_status(e64_rs232_usb_status_t *status) {
  if (status) *status = bridge.Status();
}
extern "C" int e64_rs232_usb_open(unsigned adapter, unsigned baud) { return bridge.Open(adapter, baud); }
extern "C" int e64_rs232_usb_open_configured(unsigned adapter, unsigned baud,
    unsigned parity, unsigned dataBits, unsigned stopBits) {
  return bridge.OpenConfigured(adapter, baud, parity, dataBits, stopBits);
}
extern "C" int e64_rs232_usb_set_framing(unsigned parity, unsigned dataBits, unsigned stopBits) {
  return bridge.SetFraming(parity, dataBits, stopBits);
}
extern "C" void e64_rs232_usb_close(void) { bridge.Close(); }
extern "C" int e64_rs232_usb_set_baud(unsigned baud) { return bridge.SetBaud(baud); }
extern "C" int e64_rs232_usb_put(uint8_t b) { return bridge.Put(b); }
extern "C" int e64_rs232_usb_get(uint8_t *b) { return bridge.Get(b); }

extern "C" void e64_rs232_usb_service(void) {
  // This function shares an owner with UpdatePlugAndPlay. No device reference
  // escapes to the emulator core and teardown cannot run during configuration.
  static unsigned lastService;
  unsigned now = CTimer::GetClockTicks();
  if ((unsigned) (now - lastService) < 20000) return; // At most 50 Hz on core 0.
  lastService = now;
  CUSBSerialDevice *compatible[Rs232UsbBridge::MaxAdapters] = {};
  unsigned mask = 0;
#if RASPPI == 3
  for (unsigned index = 1; index <= Rs232UsbBridge::MaxAdapters; ++index) {
    CDevice *found = CDeviceNameService::Get()->GetDevice("utty", index, FALSE);
    // utty names are exclusively registered by CUSBSerialDevice.
    if (found) {
      auto *serial = static_cast<CUSBSerialDevice *>(found);
      auto *host = serial->GetHostDevice();
      if (host) {
        const auto *id = host->GetDevice()->GetDeviceDescriptor();
        if (id->idVendor == 0x0403 && id->idProduct == 0x6001) {
          compatible[index - 1] = serial;
          mask |= 1u << (index - 1);
        }
      }
    }
  }
#endif
  bridge.PublishDiscovery(mask);
  Rs232UsbStatus status = bridge.Status();
  unsigned resolved = 0;
  if (status.adapter == E64_RS232_USB_AUTO) {
    for (unsigned i = 1; i <= Rs232UsbBridge::MaxAdapters; ++i)
      if (compatible[i - 1]) { resolved = i; break; }
  } else if (status.adapter && status.adapter <= Rs232UsbBridge::MaxAdapters &&
             compatible[status.adapter - 1]) resolved = status.adapter;
  CUSBSerialDevice *candidate = resolved ? compatible[resolved - 1] : nullptr;
  if (candidate != port.device || resolved != port.index) {
    if (port.device) {
      // Retire the old logical attachment immediately, but keep its device
      // and removal handler until its outstanding URB is consumed. Never
      // poll that completion through a wrapper rebound to a different device.
      bridge.Removed(&port);
      if (!port.Idle()) {
        uint8_t discarded[64];
        port.Poll(discarded, sizeof discarded);
        return; // Bounded progress; no waiting on the emulator or USB owner.
      }
      port.device->UnregisterRemovedHandler(port.removal);
      port.device = nullptr;
      port.removal = nullptr;
      port.index = 0;
      return; // Recompute selection/epoch before attaching on the next pass.
    }
    port.device = candidate;
    port.index = resolved;
    // A fresh enumeration starts at 8N1, but an Auto/manual handover may
    // revisit an adapter previously configured by this same USB owner.
    port.appliedParity = 0;
    port.appliedDataBits = 8;
    port.appliedStopBits = 1;
    port.framingUncertain = customDeviceMayRemain;
    if (candidate) port.removal = candidate->RegisterRemovedHandler(Removed);
  }
  bridge.ServiceAtEpoch(port.device ? &port : nullptr, status.adapter, status.epoch);
}
