include ../circle-stdlib/Config.mk
CIRCLE_STDLIB_HOME = ../circle-stdlib
include Config.mk

ifeq ($(BOARD),pi0)
CFLAGS_FOR_TARGET += "-DRASPI_LITE"
endif

# Opt-in storage I/O instrumentation (build with: ./make_all.sh <board> --io-stats).
ifeq ($(BMC64_IO_STATS),1)
CFLAGS_FOR_TARGET += -DBMC64_IO_STATS
CPPFLAGS_FOR_TARGET += -DBMC64_IO_STATS
endif

# Opt-in frame/audio performance instrumentation (build with: ./make_all.sh <board> --perf-stats).
ifeq ($(BMC64_PERF_STATS),1)
CFLAGS_FOR_TARGET += -DBMC64_PERF_STATS
CPPFLAGS_FOR_TARGET += -DBMC64_PERF_STATS
endif

OBJ = demo.o emux_api.o font.o io_stats.o joy.o kbd.o keycodes.o menu.o menu_text_layout.o menu_wifi.o menu_confirm_osd.o menu_reset_osd.o menu_key_binding.o menu_gpio.o menu_image_contents.o menu_keyset.o menu_switch.o menu_logging.o menu_logging_device.o menu_power.o menu_configs.o menu_tape_osd.o menu_timing.o menu_usb.o overlay.o perf_stats.o raspi_util.o text.o ui.o semaphore.o usb_gamepad_defaults.o

INCLUDES = -I $(CIRCLE_STDLIB_HOME)/install/arm-none-circle/include \
	-I $(CIRCLE_STDLIB_HOME)/include \
	-I $(CIRCLE_STDLIB_HOME)/libs/circle/include \
	-I $(CIRCLE_STDLIB_HOME)/libs/circle/addon \
	-I $(CIRCLE_STDLIB_HOME)/libs/circle/addon/fatfs

all: libbmc64common.a

%.o : %.cpp
	$(CXX_FOR_TARGET) $(INCLUDES) -c -O2 -o $@ $< $(CFLAGS_FOR_TARGET) $(CPPFLAGS_FOR_TARGET)

%.o : %.c
	$(CC_FOR_TARGET) $(INCLUDES) -c -O2 -o $@ $< $(CFLAGS_FOR_TARGET)

libbmc64common.a: $(OBJ)
	$(AR_FOR_TARGET) cr libbmc64common.a $(OBJ)
	$(RANLIB_FOR_TARGET) libbmc64common.a

clean:
	rm -rf *.o *.a

# Native theme edits must rebuild every renderer consuming its roles.
ui.o: menu_theme.h ui.h web_datasette.h
menu.o menu_configs.o: ui.h

# Config display aliases and native name dialogs use the shared byte limit.
ui.o menu_configs.o: ../../src/configs/configs.h menu_theme.h

menu.o: menu_theme.h
menu_configs.o: ../../src/configs/configs_internal.h

menu_timing.o: menu.h menu_configs.h ../../src/configs/configs.h
menu_configs.o: menu.h menu_switch.h menu_configs.h
menu_switch.o: menu_switch.h

menu.o: ../../src/network_prefs.h

menu.o menu_configs.o menu_switch.o: ../../src/fan_control.h
