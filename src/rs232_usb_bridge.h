#ifndef E64_RS232_USB_BRIDGE_H
#define E64_RS232_USB_BRIDGE_H
#include <stdint.h>
#include "../third_party/vice-3.3/src/rs232drv/rs232usb.h"
#include <circle/spinlock.h>

// All Port calls run on the USB PnP owner. No emulator callback uses a Port.
// One completion's observations, never per-byte error attribution.
struct Rs232UsbReceiveStatus {
  bool headerValid;
  uint8_t modemStatus, lineStatus;
  bool overrun, parityError, framingError, breakDetected;
};

class Rs232UsbPort {
public:
  virtual ~Rs232UsbPort() {}
  virtual bool Configure(unsigned baud) = 0;
  virtual bool ConfigureLine(unsigned baud, unsigned parity, unsigned dataBits, unsigned stopBits) {
    return parity == 0 && dataBits == 8 && stopBits == 1 && Configure(baud);
  }
  virtual bool Idle() const = 0;
  virtual int Submit(bool input, const uint8_t *bytes, unsigned count) = 0;
  virtual int Poll(uint8_t *bytes, unsigned count) = 0;
  // Additive fallback keeps existing ports working without status support.
  virtual int PollWithStatus(uint8_t *bytes, unsigned count,
                            Rs232UsbReceiveStatus *status) {
    if (status) *status = {};
    return Poll(bytes, count);
  }
};

typedef e64_rs232_usb_status_t Rs232UsbStatus;

class Rs232UsbBridge {
public:
  enum { Capacity = 4096, MaxAdapters = 16, Packet = 32 };
  Rs232UsbBridge();
  int Open(unsigned adapter, unsigned baud);
  int OpenConfigured(unsigned adapter, unsigned baud, unsigned parity, unsigned dataBits, unsigned stopBits);
  void Close();
  int SetBaud(unsigned baud);
  int SetFraming(unsigned parity, unsigned dataBits, unsigned stopBits);
  int Put(uint8_t byte);
  int Get(uint8_t *byte);
  Rs232UsbStatus Status();
  int Select(unsigned selection);
  e64_rs232_usb_discovery_t Discovery();
  void PublishDiscovery(unsigned mask);
  void Service(Rs232UsbPort *candidate, unsigned adapter);
  void ServiceAtEpoch(Rs232UsbPort *candidate, unsigned adapter, unsigned epoch);
  void Removed(Rs232UsbPort *port);
private:
  class Guard {
    CSpinLock &lock;
  public:
    explicit Guard(CSpinLock &l) : lock(l) { lock.Acquire(); }
    ~Guard() { lock.Release(); }
  };
  void Clear(); // lock held
  CSpinLock lock_;
  Rs232UsbStatus status_;
  e64_rs232_usb_discovery_t discovery_;
  bool open_;
  uint8_t tx_[Capacity], rx_[Capacity];
  unsigned txRead_, txWrite_, rxRead_, rxWrite_;
  // USB owner only, except status_/queues protected above.
  Rs232UsbPort *port_;
  unsigned configured_, fault_, pendingEpoch_, pendingCount_;
  bool pending_, input_, nextInput_;
};
#endif
