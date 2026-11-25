#ifndef E64_RS232_USB_H
#define E64_RS232_USB_H
#include <stdint.h>
#define E64_RS232_USB_AUTO 17
#ifdef __cplusplus
extern "C" {
#endif
typedef struct e64_rs232_usb_status_s {
    unsigned adapter, baud, epoch, ready, txQueued, rxQueued;
    unsigned txDropped, rxDropped, errors, disconnects;
    /* Lifetime totals of IN status observations accepted in their active epoch,
     * not damaged byte counts. Not reset on close, reconfigure or disconnect.
     * Multiple error flags may be observed in one packet, even without data. */
    unsigned rxStatusObservations, rxOverrunObservations, rxParityObservations;
    unsigned rxFramingObservations, rxBreakObservations;
    unsigned parity, dataBits, stopBits;
} e64_rs232_usb_status_t;
void e64_rs232_usb_status(e64_rs232_usb_status_t *status);
typedef struct e64_rs232_usb_discovery_s {
    unsigned requested;       /* 0 legacy, 1..16 manual, 17 Auto; survives close */
    unsigned resolved;        /* compatible physical index, or 0; not readiness */
    unsigned compatibleMask;  /* bit 0 = utty1, bit 15 = utty16 */
    unsigned ready;           /* active guest session configured */
} e64_rs232_usb_discovery_t;
/* Selection publication and cached snapshots do no USB work. */
int e64_rs232_usb_select(unsigned selection);
void e64_rs232_usb_discovery(e64_rs232_usb_discovery_t *discovery);
/* Only rsuser calls these. ACIA/network routing is deliberately independent. */
int e64_rs232_usb_open(unsigned adapter, unsigned baud);
/* Parity: 0 None, 1 Even, 2 Odd. Legacy open continues to select 8N1. */
int e64_rs232_usb_open_configured(unsigned adapter, unsigned baud,
                                unsigned parity, unsigned data_bits, unsigned stop_bits);
int e64_rs232_usb_set_framing(unsigned parity, unsigned data_bits, unsigned stop_bits);
void e64_rs232_usb_close(void);
int e64_rs232_usb_set_baud(unsigned baud);
int e64_rs232_usb_put(uint8_t byte);
int e64_rs232_usb_get(uint8_t *byte);
/* Called exclusively by the USB plug-and-play owner (never by VICE). */
void e64_rs232_usb_service(void);
#ifdef __cplusplus
}
#endif
#endif
