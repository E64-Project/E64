/*
 * rsuser.c - Daniel Dallmann's 9600 baud RS232 userport interface.
 *
 * Written by
 *  Andre Fachat <a.fachat@physik.tu-chemnitz.de>
 *  Andreas Boose <viceteam@t-online.de>
 *
 * This file is part of VICE, the Versatile Commodore Emulator.
 * See README for copyright notice.
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
 *  02111-1307  USA.
 *
 */
/*
 * This is a very crude emulation. It does not check for a lot of things.
 * It simply tries to work with existing programs that work on the real
 * machine and does not try to catch rogue attempts...
 */

/* FIXME: Should keep its own log.  */

#include "vice.h"

#include <stdio.h>

#include "alarm.h"
#include "clkguard.h"
#include "cmdline.h"
#include "log.h"
#include "maincpu.h"
#include "resources.h"
#include "rs232drv.h"
#include "rsuser.h"
#include "machine.h"
#ifdef HAVE_RS232BMC
#include "rs232usb.h"
#endif
#include "types.h"

static int fd = -1;

static alarm_t *rsuser_alarm = NULL;

static int dtr;
static int rts;

static int rxstate;
static uint8_t rxdata;
static uint8_t txdata;
static uint8_t txbit;

static long cycles_per_sec = 1000000;

static CLOCK clk_start_rx = 0;
static CLOCK clk_start_tx = 0;
static CLOCK clk_start_bit = 0;
static CLOCK clk_end_tx = 0;

static void (*start_bit_trigger)(void);
static void (*byte_rx_func)(uint8_t);

static void clk_overflow_callback(CLOCK sub, void *data);

static void int_rsuser(CLOCK offset, void *data);
static void rsuser_setup(void);

#undef DEBUG

#define RSUSER_TICKS    21111

#undef DEBUG_TIMING_SEND
#undef DEBUG_TIMING_RECV


#ifdef DEBUG
# define LOG_DEBUG(_xxx) log_debug _xxx
#else
# define LOG_DEBUG(_xxx)
#endif

#ifdef DEBUG_TIMING_SEND
# define LOG_DEBUG_TIMING_TX(_xxx) log_debug _xxx
#else
# define LOG_DEBUG_TIMING_TX(_xxx)
#endif

#ifdef DEBUG_TIMING_RECV
# define LOG_DEBUG_TIMING_RX(_xxx) log_debug _xxx
#else
# define LOG_DEBUG_TIMING_RX(_xxx)
#endif

/***********************************************************************
 * resource handling
 */

int rsuser_enabled = 0;                 /* enable flag */
static int rsuser_baudrate = 300;       /* saves the baud rate given */
/* Physical FTDI framing only; the inherited modem always retains 8N1. */
static int rsuser_parity = 0;          /* 0: None, 1: Even, 2: Odd */
static int rsuser_data_bits = 8;
static int rsuser_stop_bits = 1;
static int char_clk_ticks = 0;          /* clk ticks per character */
static int bit_clk_ticks = 0;           /* clk ticks per character */

static int rsuser_device;
static unsigned int buf;
static unsigned int valid;
static int rsuser_ftdi; /* 0 legacy, 1..16 manual uttyN, E64_RS232_USB_AUTO Auto. */
#define RSUSER_FTDI_FD 0x10000

static int physical_framing(void)
{
#ifdef HAVE_RS232BMC
    return rsuser_ftdi != 0;
#else
    return 0;
#endif
}

static int frame_bits(void)
{
    return physical_framing()
        ? 1 + rsuser_data_bits + (rsuser_parity != 0) + rsuser_stop_bits : 10;
}

static int custom_framing(void)
{
    return physical_framing() &&
        (rsuser_parity != 0 || rsuser_data_bits != 8 || rsuser_stop_bits != 1);
}

static int parity_bit(unsigned byte)
{
    int i, parity = 0;
    for (i = 0; i < rsuser_data_bits; ++i) parity ^= (byte >> i) & 1;
    return parity ^ (rsuser_parity == 2);
}

static int userport_open(void)
{
#ifdef HAVE_RS232BMC
    if (rsuser_ftdi) {
        return e64_rs232_usb_open_configured(rsuser_ftdi, rsuser_baudrate,
            rsuser_parity, rsuser_data_bits, rsuser_stop_bits) == 0 ? RSUSER_FTDI_FD : -1;
    }
#endif
    return rs232drv_open(rsuser_device);
}
static void userport_close(int handle)
{
#ifdef HAVE_RS232BMC
    if (handle == RSUSER_FTDI_FD) { e64_rs232_usb_close(); return; }
#endif
    rs232drv_close(handle);
}
static int userport_putc(int handle, uint8_t byte)
{
#ifdef HAVE_RS232BMC
    if (handle == RSUSER_FTDI_FD) return e64_rs232_usb_put(byte);
#endif
    return rs232drv_putc(handle, byte);
}
static int userport_getc(int handle, uint8_t *byte)
{
#ifdef HAVE_RS232BMC
    if (handle == RSUSER_FTDI_FD) return e64_rs232_usb_get(byte);
#endif
    return rs232drv_getc(handle, byte);
}


static void calculate_baudrate(void)
{
    if (rsuser_enabled) {
        char_clk_ticks = (int)(10.0 * cycles_per_sec / ((double)rsuser_baudrate));
    } else {
        char_clk_ticks = RSUSER_TICKS;
    }
    bit_clk_ticks = (int)((double)(char_clk_ticks) / 10.0);
    if (rsuser_enabled && custom_framing()) {
        /* Keep bit rounding identical to 8N1; vary only character length. */
        char_clk_ticks = bit_clk_ticks * frame_bits();
    }

    LOG_DEBUG(("RS232: %d cycles per char (cycles_per_sec=%ld).",
               char_clk_ticks, cycles_per_sec));
}

static int set_enable(int value, void *param)
{
    int newval = value ? 1 : 0;

    if (newval && !rsuser_enabled) {
        dtr = DTR_OUT;  /* inactive */
        rts = RTS_OUT;  /* inactive */
        fd = -1;
    }
    if (rsuser_enabled && !newval) {
        if (fd != -1) {
            /* if (clk_start_tx) userport_putc(fd, rxdata); */
            userport_close(fd);
        }
        if (rsuser_alarm) {
            alarm_unset(rsuser_alarm);
        }
        fd = -1;
    }

    rsuser_enabled = newval;

    calculate_baudrate();

#ifdef HAVE_RS232BMC
    /* The BMC modem is always attached; open it without waiting for DTR. */
    if (rsuser_enabled && fd == -1 && rsuser_alarm != NULL) {
        rsuser_setup();
    }
#endif

    return 0;
}

static int set_baudrate(int val, void *param)
{
    if (val < 1 || (rsuser_ftdi && val != 300 && val != 600 && val != 1200 && val != 2400 && val != 9600)) {
        return -1;
    }
#ifdef HAVE_RS232BMC
    if (fd == RSUSER_FTDI_FD && e64_rs232_usb_set_baud(val) != 0) return -1;
#endif
    if (rsuser_baudrate == val) return 0;
    rsuser_baudrate = val;

    calculate_baudrate();
#ifdef HAVE_RS232BMC
    if (fd == RSUSER_FTDI_FD) {
        /* A baud epoch must not inherit an old partial guest frame. */
        buf = (unsigned int)(~0);
        valid = 0;
        txbit = 1;
        clk_end_tx = 0;
        rsuser_setup();
    }
#endif

    return 0;
}

static int set_up_device(int val, void *param)
{
    if (val < 0 || val > 3) {
        return -1;
    }

    rsuser_device = val;

    if (fd != -1) {
        userport_close(fd);
        fd = userport_open();
    }
    return 0;
}

static int set_ftdi(int val, void *param)
{
    int enabled = rsuser_enabled;
    if (val < 0) return -1;
#ifndef HAVE_RS232BMC
    if (val) return -1;
#else
    if (val > 16 && val != E64_RS232_USB_AUTO) return -1;
    /* This transport is intentionally user-port/C64 only, never ACIA. */
    if (val && (machine_class != VICE_MACHINE_C64 ||
                (rsuser_baudrate != 300 && rsuser_baudrate != 600 && rsuser_baudrate != 1200 && rsuser_baudrate != 2400 && rsuser_baudrate != 9600))) return -1;
#endif
    if (val == rsuser_ftdi) return 0;
    set_enable(0, NULL);
#ifdef HAVE_RS232BMC
    e64_rs232_usb_select(val); /* Publish preference even while session closed. */
#endif
    rsuser_ftdi = val;
    /* Deselecting hardware means Off, not an implicit network modem open. */
    if (enabled && val) set_enable(1, NULL);
    return 0;
}

static int set_framing(int parity, int data_bits, int stop_bits)
{
    if (parity < 0 || parity > 2 || (data_bits != 7 && data_bits != 8) ||
        (stop_bits != 1 && stop_bits != 2)) return -1;
    if (parity == rsuser_parity && data_bits == rsuser_data_bits &&
        stop_bits == rsuser_stop_bits) return 0;
#ifdef HAVE_RS232BMC
    if (fd == RSUSER_FTDI_FD &&
        e64_rs232_usb_set_framing(parity, data_bits, stop_bits) != 0) return -1;
#endif
    rsuser_parity = parity;
    rsuser_data_bits = data_bits;
    rsuser_stop_bits = stop_bits;
    if (physical_framing()) {
        calculate_baudrate();
        /* Discard guest TX samples and RX state from the previous format. */
        buf = (unsigned int)(~0);
        valid = 0;
        txbit = 1;
        txdata = rxdata = 0;
        rxstate = 0;
        clk_start_rx = clk_start_tx = clk_start_bit = clk_end_tx = 0;
        if (rsuser_enabled && rsuser_alarm != NULL) rsuser_setup();
    }
    return 0;
}

static int set_parity(int val, void *param)
{
    return set_framing(val, rsuser_data_bits, rsuser_stop_bits);
}

static int set_data_bits(int val, void *param)
{
    return set_framing(rsuser_parity, val, rsuser_stop_bits);
}

static int set_stop_bits(int val, void *param)
{
    return set_framing(rsuser_parity, rsuser_data_bits, val);
}

static const resource_int_t resources_int[] = {
    { "RsUserFTDI", 0, RES_EVENT_NO, NULL,
      &rsuser_ftdi, set_ftdi, NULL },
    { "RsUserEnable", 0, RES_EVENT_STRICT, (resource_value_t)0,
      &rsuser_enabled, set_enable, NULL },
    { "RsUserBaud", 300, RES_EVENT_NO, NULL,
      &rsuser_baudrate, set_baudrate, NULL },
    { "RsUserDev", 0, RES_EVENT_NO, NULL,
      &rsuser_device, set_up_device, NULL },
    { "RsUserParity", 0, RES_EVENT_NO, NULL,
      &rsuser_parity, set_parity, NULL },
    { "RsUserDataBits", 8, RES_EVENT_NO, NULL,
      &rsuser_data_bits, set_data_bits, NULL },
    { "RsUserStopBits", 1, RES_EVENT_NO, NULL,
      &rsuser_stop_bits, set_stop_bits, NULL },
    RESOURCE_INT_LIST_END
};

int rsuser_resources_init(void)
{
    if (resources_register_int(resources_int) < 0) {
        return -1;
    }

#ifdef HAVE_RS232BMC
    /* E64 C64 defaults: automatically enable the FTDI user port. */
    if (machine_class == VICE_MACHINE_C64) {
        if (resources_set_default_int("RsUserFTDI", E64_RS232_USB_AUTO) < 0 ||
            resources_set_default_int("RsUserEnable", 1) < 0 ||
            resources_set_default_int("RsUserBaud", 2400) < 0) {
            return -1;
        }
    }
#endif

    return 0;
}

static const cmdline_option_t cmdline_options[] =
{
    { "-rsuserftdi", SET_RESOURCE, CMDLINE_ATTRIB_NEED_ARGS,
      NULL, NULL, "RsUserFTDI", NULL,
      "<0-17>", "Select FTDI uttyN (1-16), Auto (17), or existing backend (0)" },
    { "-rsuser", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "RsUserEnable", (void *)1,
      NULL, "Enable RS232 userport emulation" },
    { "+rsuser", SET_RESOURCE, CMDLINE_ATTRIB_NONE,
      NULL, NULL, "RsUserEnable", (void *)0,
      NULL, "Disable RS232 userport emulation" },
    { "-rsuserbaud", SET_RESOURCE, CMDLINE_ATTRIB_NEED_ARGS,
      NULL, NULL, "RsUserBaud", NULL,
      "<baud>", "Set the baud rate of the RS232 userport emulation." },
    { "-rsuserdev", SET_RESOURCE, CMDLINE_ATTRIB_NEED_ARGS,
      NULL, NULL, "RsUserDev", NULL,
      "<0-3>", "Specify VICE RS232 device for userport" },
    CMDLINE_LIST_END
};

int rsuser_cmdline_options_init(void)
{
    return cmdline_register_options(cmdline_options);
}

/*********************************************************************/

static unsigned char code[256];
static const unsigned int masks[] =
{
    1, 2, 4, 8, 0x10, 0x20, 0x40, 0x80, 0x100, 0x200, 0x400, 0x800,
    0x1000, 0x2000, 0x4000, 0x8000
};

void rsuser_init(long cycles, void (*startfunc)(void), void (*bytefunc)(uint8_t))
{
    int i, j;
    unsigned char c, d;

    rsuser_alarm = alarm_new(maincpu_alarm_context, "RSUser", int_rsuser, NULL);

    clk_guard_add_callback(maincpu_clk_guard, clk_overflow_callback, NULL);

    cycles_per_sec = cycles;
    calculate_baudrate();

    start_bit_trigger = startfunc;
    byte_rx_func = bytefunc;

    for (i = 0; i < 256; i++) {
        c = i; d = 0;
        for (j = 0; j < 8; j++) {
            d <<= 1;
            if (c & 1) {
                d |= 1;
            }
            c >>= 1;
        }
        code[i] = d;
    }

    dtr = DTR_OUT;      /* inactive */
    rts = RTS_OUT;      /* inactive */
    fd = -1;

    buf = (unsigned int)(~0); /* all 1s */
    valid = 0;
}

void rsuser_reset(void)
{
    rxstate = 0;
    clk_start_rx = 0;
    clk_start_tx = 0;
    clk_start_bit = 0;
    clk_end_tx = 0;
    if (fd != -1) {
        userport_close(fd);
    }

    alarm_unset(rsuser_alarm);
    fd = -1;

#ifdef HAVE_RS232BMC
    if (rsuser_enabled) {
        rsuser_setup();
    }
#endif
}

static void rsuser_setup(void)
{
    rxstate = 0;
    clk_start_rx = 0;
    clk_start_tx = 0;
    clk_start_bit = 0;
    if (fd < 0) {
#ifdef HAVE_RS232BMC
        if (rsuser_ftdi) {
            /* A new physical session cannot inherit a partial old TX frame. */
            buf = (unsigned int)(~0);
            valid = 0;
            txbit = 1;
        }
#endif
        fd = userport_open();
    }
    alarm_set(rsuser_alarm, maincpu_clk + char_clk_ticks / 8);
}

void rsuser_write_ctrl(uint8_t b)
{
    int new_dtr = b & DTR_OUT;  /* = 0 is active, != 0 is inactive */
    int new_rts = b & RTS_OUT;  /* = 0 is active, != 0 is inactive */

    if (rsuser_enabled) {
        if (dtr && !new_dtr) {
            rsuser_setup();
        }
        if (new_dtr && !dtr && fd != -1) {
#if 0   /* This is a bug in the X-line handshake of the C64... */
            LOG_DEBUG(("switch rs232 off."));
            alarm_unset(rsuser_alarm);
            userport_close(fd);
            fd = -1;
#endif
        }
    }

    dtr = new_dtr;
    rts = new_rts;
}

static void check_tx_buffer(void)
{
    uint8_t c;

    if (custom_framing()) {
        unsigned length = frame_bits();
        while (valid >= length) {
            unsigned i;
            int good = 1;
            /* Oldest sample is the start bit; skip preceding idle marks. */
            if ((buf >> (valid - 1)) & 1) { --valid; continue; }
            c = 0;
            for (i = 0; i < (unsigned)rsuser_data_bits; ++i)
                c |= ((buf >> (valid - 2 - i)) & 1) << i;
            if (rsuser_parity &&
                (int)((buf >> (valid - 2 - rsuser_data_bits)) & 1) != parity_bit(c)) {
                log_error(LOG_DEFAULT, "FTDI guest parity error!");
                good = 0;
            }
            for (i = 0; i < (unsigned)rsuser_stop_bits; ++i)
                if (!((buf >> (valid - length + i)) & 1)) good = 0;
            if (!good) log_error(LOG_DEFAULT, "FTDI guest frame rejected!");
            else if (fd != -1) userport_putc(fd, c);
            valid -= length;
        }
        return;
    }

    while (valid >= 10 && ((buf >> (valid - 1)) & 1U)) {
        valid--;
    }

    if (valid >= 10) {     /* (valid-1)-th bit is not set = start bit! */
        if (!(buf & masks[valid - 10])) {
            log_error(LOG_DEFAULT, "Frame error!");
        } else {
            c = (buf >> (valid - 9)) & 0xff;
            if (fd != -1) {
                LOG_DEBUG(("\"%c\" (%02x).", code[c], code[c]));
                userport_putc(fd, ((uint8_t)(code[c])));
            }
        }
        valid -= 10;
    }
}

static void keepup_tx_buffer(void)
{
    if ((!clk_start_bit) || maincpu_clk < clk_start_bit) {
        return;
    }

    while (clk_start_bit < clk_end_tx) {
        LOG_DEBUG(("keepup: clk=%d, _bit=%d (%d), _tx=%d.",
                   maincpu_clk, clk_start_bit - clk_start_tx, clk_start_bit,
                   clk_start_tx));
        buf = buf << 1;
        if (txbit) {
            buf |= 1;
        }
        valid++;
        if (valid >= (unsigned)frame_bits()) {
            check_tx_buffer();
        }

        clk_start_bit += bit_clk_ticks;

        if (clk_start_bit >= maincpu_clk) {
            break;
        }
    }
    if (clk_start_bit >= clk_end_tx) {
        clk_start_tx = 0;
        clk_start_bit = 0;
        clk_end_tx = 0;
    }
}

void rsuser_set_tx_bit(int b)
{
    LOG_DEBUG(("rsuser_set_tx(clk=%d, clk_start_tx=%d, b=%d).",
               maincpu_clk, clk_start_tx, b));

    LOG_DEBUG_TIMING_TX(("rsuser_set_tx(clk=%d, clk_start_tx=%d, b=%d).",
                         maincpu_clk, clk_start_tx, b));

    if (fd == -1 || rsuser_baudrate > 2400) {
        clk_start_tx = 0;
        return;
    }

    /* feeds the output buffer with enough bits till clk */
    keepup_tx_buffer();
    txbit = b;

    if (!clk_start_tx && !b) {
        /* the clock where we start sampling - in the middle of the bit */
        clk_start_tx = maincpu_clk + (bit_clk_ticks / 2);
        clk_start_bit = clk_start_tx;
        /* Character duration can differ from the sum of rounded bit periods.
         * Always end TX sampling after the selected number of whole bits.
         */
        clk_end_tx = clk_start_tx + (bit_clk_ticks * frame_bits());
        txdata = 0;
    }
}

uint8_t rsuser_get_rx_bit(void)
{
    int bit = 0, byte = 1;
    LOG_DEBUG_TIMING_RX(("rsuser_get_rx_bit(clk=%d, clk_start_rx=%d).",
                         maincpu_clk, clk_start_rx));

    if (clk_start_rx) {
        byte = 0;
        bit = (maincpu_clk - clk_start_rx) / (bit_clk_ticks);
        if (custom_framing()) {
            if (bit == 0) return 0;
            if (bit > 0 && bit <= rsuser_data_bits)
                return (rxdata >> (bit - 1)) & 1;
            /* Reconstructed parity describes the delivered payload, not the
             * original wire parity. Packet-associated errors remain diagnostic. */
            if (rsuser_parity && bit == rsuser_data_bits + 1) return parity_bit(rxdata);
            return 1; /* All configured stop bits, followed by idle mark. */
        }
        LOG_DEBUG(("read ctrl(_rx=%d, clk-start_rx=%d -> bit=%d)",
                   clk_start_rx, maincpu_clk - clk_start_rx, bit));
        if (!bit) {
            byte = 0;   /* start bit */
        } else
        if (bit < 9) {    /* 8 data bits */
            byte = rxdata & (1 << (bit - 1));
            if (byte) {
                byte = 1;
            }
        } else {        /* stop bits */
            byte = 1;
        }
    }
    return byte;
}

uint8_t rsuser_read_ctrl(uint8_t b)
{
    return b & (rsuser_get_rx_bit() | CTS_IN | (rsuser_baudrate > 2400 ? 0 : DCD_IN));
}

void rsuser_tx_byte(uint8_t b)
{
    buf = (buf << 8) | b;
    valid += 8;

    check_tx_buffer();
}

static void int_rsuser(CLOCK offset, void *data)
{
    CLOCK rclk = maincpu_clk - offset;

    keepup_tx_buffer();

    switch (rxstate) {
        case 0:
receive_next:
            if (fd != -1 && userport_getc(fd, &rxdata) > 0) {
                if (physical_framing() && rsuser_data_bits == 7) rxdata &= 0x7f;
                /* byte received, signal startbit on flag */
                rxstate++;
                if (start_bit_trigger) {
                    start_bit_trigger();
                }
                clk_start_rx = rclk;
#ifdef HAVE_RS232BMC
                /* High-speed physical userport: deliver SDR before
                 * the stop-bit interval ends. */
                if (fd == RSUSER_FTDI_FD && rsuser_baudrate > 2400) {
                    alarm_set(rsuser_alarm,
                              maincpu_clk + 9 * bit_clk_ticks);
                    break;
                }
#endif
            }
            alarm_set(rsuser_alarm, maincpu_clk + char_clk_ticks);
            break;
        case 1:
            /* now byte should be in shift register */
            if (byte_rx_func) {
                byte_rx_func((uint8_t)(code[rxdata]));
            }
#ifdef HAVE_RS232BMC
            if (fd == RSUSER_FTDI_FD && rsuser_baudrate > 2400) {
                /* Allow the guest to acknowledge SDR before FLAG.
                 * Preserve the original ten-bit start interval. */
                rxstate = 2;
                clk_start_rx = 0;
                alarm_set(rsuser_alarm,
                          maincpu_clk + char_clk_ticks
                          - 9 * bit_clk_ticks);
                break;
            }
#endif
            rxstate = 0;
            clk_start_rx = 0;
#ifdef HAVE_RS232BMC
            /* Preserve established low-speed FTDI scheduling. */
            if (fd == RSUSER_FTDI_FD) goto receive_next;
#endif
            alarm_set(rsuser_alarm, maincpu_clk + char_clk_ticks / 8);
            break;

        case 2:
            rxstate = 0;
            clk_start_rx = 0;
#ifdef HAVE_RS232BMC
            if (fd == RSUSER_FTDI_FD
                && rsuser_baudrate > 2400) goto receive_next;
#endif
            alarm_set(rsuser_alarm, maincpu_clk + char_clk_ticks / 8);
            break;
    }
}

static void clk_overflow_callback(CLOCK sub, void *data)
{
    if (clk_start_tx) {
        clk_start_tx -= sub;
    }
    if (clk_start_rx) {
        clk_start_rx -= sub;
    }
    if (clk_start_bit) {
        clk_start_bit -= sub;
    }
}
