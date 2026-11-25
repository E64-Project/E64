#
# Makefile for a machine kernel image
#

CIRCLEHOME = third_party/circle-stdlib/libs/circle
NEWLIBDIR = third_party/circle-stdlib/install/arm-none-circle
VPATH = src

APP_INCLUDES = -I"$(NEWLIBDIR)/include" -I$(STDDEF_INCPATH) \
	      -Ithird_party/circle-stdlib/include \
	      -I$(CIRCLEHOME)/include \
	      -I$(CIRCLEHOME)/addon \
	      -Ithird_party/vice-3.3/src \
	      -Ithird_party/common \
	      -I$(CIRCLEHOME)/addon/fatfs \
	      -Ithird_party/zlib

ifeq ($(MACHINE_CLASS),RASPI_PLUS4EMU)
	APP_INCLUDES += -I "third_party/plus4emu/src"
endif

EXTRAINCLUDE += $(APP_INCLUDES)

OBJS	= src/main.o src/kernel.o src/new_io.o src/io_stats_bench.o src/perf_stats_env.o src/vicesound.o src/vicesoundbasedevice.o src/bmcmodem.o src/rs232_usb.o src/rs232_usb_bridge.o \
		  src/viceoptions.o src/viceapp.o src/vice_network.o src/network_config.o src/network_prefs.o src/fan_control.o src/fan_gpio.o src/network_time_sync.o src/fbl.o src/crt_pi_idx.o src/crt_pi_rgb.o \
				  src/webui/webui.o src/webui/webui_http.o src/webui/webui_fs.o src/webui/webui_machine.o src/webui/webui_assets.o src/keyboard/keyboard_router.o \
				  src/keyboard/gpio_recovery.o src/keyboard/keyboard_layout.o src/keyboard/layout_us.o src/keyboard/layout_uk.o src/keyboard/layout_no.o \
				  src/keyboard/layout_fr.o src/keyboard/layout_de.o src/keyboard/layout_latam.o src/keyboard/layout_c64.o src/keyboard/layout_positional.o src/keyboard/layout_maxi.o \
				  src/configs/config_store.o src/configs/config_transaction.o src/configs/config_factory.o src/configs/config_boot.o src/configs/config_machine.o \
				  src/configs/config_kv.o src/configs/config_deleted.o src/configs/config_protection.o src/sdcard/sd_fs_fatfs.o src/sdcard/sd_fs_file.o \
				  src/power/power.o

ifeq ($(MACHINE_CLASS),RASPI_PLUS4EMU)
OBJS	+= src/plus4emulatorcore.o
else
OBJS	+= src/viceemulatorcore.o
endif

include $(CIRCLEHOME)/Rules.mk

CFLAGS += $(APP_INCLUDES) -D $(MACHINE_CLASS)
# zlib (third_party/zlib, decompression for the updater) without its gz* file
# functions; the updater supplies zalloc/zfree.
CFLAGS += -DZ_SOLO
CPPFLAGS += $(APP_INCLUDES) -D $(MACHINE_CLASS) -fno-exceptions -fno-rtti

# Opt-in storage I/O instrumentation.
ifeq ($(BMC64_IO_STATS),1)
CFLAGS += -DBMC64_IO_STATS
CPPFLAGS += -DBMC64_IO_STATS
endif

# Opt-in frame/audio performance instrumentation.
ifeq ($(BMC64_PERF_STATS),1)
CFLAGS += -DBMC64_PERF_STATS
CPPFLAGS += -DBMC64_PERF_STATS
endif

# The web UI's static assets are embedded in the image via a generated C
# source. Regenerate it from src/webui/assets/ whenever an asset or the
# generator changes. The generated file is committed, so builds without a
# Python interpreter fall back to that copy.
PYTHON ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
WEBUI_ASSET_SRCS = $(shell find src/webui/assets -type f)

# The web UI's JavaScript tests must pass before the assets are embedded. They
# need Node.js, which get_gnu_toolchain.sh puts on PATH. The stamp file means
# they only run again when the code they test or the tests themselves change.
WEBUI_TEST_SRCS = tools/webui_test/icon_artwork_manifest.json $(wildcard src/webui/assets/js/*.js) $(wildcard tools/webui_test/*.js tools/webui_test/*.mjs tools/webui_test/*.py) \
		 src/webui/webui_fs.cpp src/webui/webui_fs.h src/sdcard/sd_fs_fatfs.c src/sdcard/sd_fs.h
WEBUI_TEST_STAMP = build/.webui_tests.stamp

src/webui/assets/js/config_limits.js: src/configs/configs.h tools/gen_config_limits.py
	@python3 tools/gen_config_limits.py
$(WEBUI_TEST_STAMP): src/webui/assets/js/config_limits.js

$(WEBUI_TEST_STAMP): $(WEBUI_TEST_SRCS)
	@command -v node >/dev/null 2>&1 || { echo "Node.js is required to run the web UI tests: source get_gnu_toolchain.sh" >&2; exit 1; }
	@echo "  TEST  web UI"
	@node tools/webui_test/run_tests.mjs
	@node tools/webui_test/logical_configs_test.mjs
	@node tools/webui_test/config_protection_test.mjs
	@node tools/webui_test/factory_configs_test.mjs
	@$(PYTHON) tools/webui_test/fs_endpoints_test.py
	@$(PYTHON) tools/webui_test/asset_generator_test.py
	@$(PYTHON) tools/webui_test/commodore_icons_test.py
	@$(PYTHON) tools/webui_test/config_protection_test.py
	@mkdir -p $(dir $@) && touch $@

src/webui/webui_assets.c: $(WEBUI_ASSET_SRCS) tools/gen_webui_assets.py | $(WEBUI_TEST_STAMP)
ifeq ($(PYTHON),)
	@echo "  WARN  no python interpreter found; using committed $@"
	@touch $@
else
	@echo "  GEN   $@"
	@$(PYTHON) tools/gen_webui_assets.py
endif

# Exercise the production ROM lookup and media documentation policy, and
# verify that review staging starts with Main and only lowercase directories.
LAYOUT_TEST_STAMP = build/.layout_tests.stamp
$(LAYOUT_TEST_STAMP): src/bootstat_c64.h sdcard/c64/bootstat.txt tools/layout_test/run_tests.py tools/stage_e64.py third_party/vice-3.3/src/arch/raspi/archdep.c third_party/common/menu.c $(shell find sdcard -name 'README*.txt')
	@python3 tools/layout_test/run_tests.py
	@mkdir -p $(dir $@) && touch $@
src/configs/config_store.o: $(LAYOUT_TEST_STAMP)
src/viceapp.o: src/bootstat_c64.h

# Check live header indicators and independent header/footer alignment on the host.
MENU_TITLE_TEST_STAMP = build/.menu_title_tests.stamp
$(MENU_TITLE_TEST_STAMP): tools/menu_final_polish_test/run_tests.py tools/menu_navigation_test/run_tests.py tools/menu_reorganization_test/run_tests.py tools/config_dialog_test/run_tests.py tools/e64_ui_test/run_tests.py tools/menu_cleanup_test/run_tests.py src/configs/configs.h third_party/common/text.c third_party/common/menu_theme.h third_party/common/ui.h tools/menu_theme_test/run_tests.py tools/menu_footer_test/run_tests.py third_party/vice-3.3/src/arch/raspi/vice_api.c tools/menu_title_test/run_tests.py src/vice_network.cpp third_party/common/circle.h third_party/common/ui.c third_party/common/menu.c third_party/common/menu_configs.c
	@python3 tools/menu_title_test/run_tests.py
	@python3 tools/menu_footer_test/run_tests.py
	@python3 tools/menu_theme_test/run_tests.py
	@python3 tools/config_dialog_test/run_tests.py
	@python3 tools/menu_cleanup_test/run_tests.py
	@python3 tools/e64_ui_test/run_tests.py
	@python3 tools/menu_reorganization_test/run_tests.py
	@python3 tools/menu_navigation_test/run_tests.py
	@python3 tools/menu_final_polish_test/run_tests.py
	@mkdir -p $(dir $@) && touch $@
src/vice_network.o: $(MENU_TITLE_TEST_STAMP)

# Stage 1 checks only adapter error semantics; no device or card access.
FILESYSTEM_TEST_STAMP = build/.filesystem_stage1_tests.stamp
$(FILESYSTEM_TEST_STAMP): tools/fs_stage1_test/run_tests.py src/new_io.cpp src/sdcard/sd_fs_file.c src/sdcard/sd_fs_fatfs.c third_party/common/menu.c third_party/vice-3.3/src/resources.c third_party/vice-3.3/src/ioutil.c src/configs/config_store.c src/configs/config_boot.c
	@echo "  TEST  filesystem Stage 1"
	@python3 tools/fs_stage1_test/run_tests.py
	@mkdir -p $(dir $@) && touch $@
src/new_io.o src/sdcard/sd_fs_file.o src/sdcard/sd_fs_fatfs.o: $(FILESYSTEM_TEST_STAMP)

# Stage 2A host tests compile the production transfer adapter and USB methods.
BLOCK_TRANSFER_TEST_STAMP = build/.filesystem_stage2a_tests.stamp
BLOCK_TRANSFER_TEST_BASELINE = tools/fs_stage2a_test/fixtures/third_party/circle-stdlib/libs/circle/lib/usb/usbmassdevice.cpp
$(BLOCK_TRANSFER_TEST_STAMP): $(BLOCK_TRANSFER_TEST_BASELINE) tools/fs_stage2a_test/run_tests.py third_party/circle-stdlib/libs/circle/addon/fatfs/diskio.cpp third_party/circle-stdlib/libs/circle/lib/usb/usbmassdevice.cpp src/io_stats_bench.cpp
	@echo "  TEST  filesystem Stage 2A"
	@python3 tools/fs_stage2a_test/run_tests.py
	@mkdir -p $(dir $@) && touch $@
src/io_stats_bench.o: $(BLOCK_TRANSFER_TEST_STAMP)

KEYBOARD_TEST_CC ?= cc
KEYBOARD_TEST_STAMP = build/.keyboard_tests.stamp
KEYBOARD_TEST_BIN = build/.keyboard_router_test
KEYBOARD_TEST_SRCS = tools/keyboard_test/keyboard_router_test.c tools/keyboard_test/run_tests.sh src/keyboard/keyboard_router.c \
					 src/keyboard/keyboard_router.h src/keyboard/keyboard_feature.h third_party/common/kbd.c \
					 src/keyboard/keyboard_layout.h src/keyboard/keyboard_layout.c $(wildcard src/keyboard/layout_*.c)

$(KEYBOARD_TEST_STAMP): $(KEYBOARD_TEST_SRCS)
	@echo "  TEST  keyboard"
	@KEYBOARD_TEST_CC=$(KEYBOARD_TEST_CC) tools/keyboard_test/run_tests.sh
	@mkdir -p $(dir $@) && touch $@

src/keyboard/keyboard_router.o: $(KEYBOARD_TEST_STAMP)

CONFIGS_TEST_CC ?= cc
CONFIGS_TEST_STAMP = build/.configs_tests.stamp
CONFIGS_TEST_BIN = build/.configs_test
CONFIGS_TEST_SRCS = tools/configs_test/native_rename_test.py tools/configs_test/timing_ui_test.py third_party/common/menu_timing.c tools/configs_test/stage2_audit_test.py tools/configs_test/storage_fault_test.py tools/configs_test/web_storage_test.py src/webui/webui_fs.cpp tools/configs_test/pal_machine_test.py templates/e64-v1/system/machines.txt third_party/common/menu_switch.c third_party/common/menu_configs.c tools/configs_test/selection_fault_test.c  tools/configs_test/phase1_integration_test.py tools/configs_test/phase1_test.c src/keyboard/gpio_recovery.c src/keyboard/gpio_recovery.h  tools/configs_test/protection_test.py third_party/vice-3.3/src/arch/raspi/videoarch.c tools/configs_test/logical_delete_test.py tools/configs_test/configs_test.c tools/configs_test/run_tests.sh tools/sdcard/sd_fs_posix.c \
					 $(wildcard src/configs/*.c) $(wildcard src/configs/*.h) $(wildcard src/sdcard/*.c) $(wildcard src/sdcard/*.h)

$(CONFIGS_TEST_STAMP): $(CONFIGS_TEST_SRCS)
	@echo "  TEST  configs"
	@CONFIGS_TEST_CC=$(CONFIGS_TEST_CC) tools/configs_test/run_tests.sh
	@mkdir -p $(dir $@) && touch $@

src/configs/config_store.o src/configs/config_transaction.o: $(CONFIGS_TEST_STAMP)

FILTERED_CIRCLE_NEWLIB = libcirclenewlib-bmc64.a

$(FILTERED_CIRCLE_NEWLIB): $(NEWLIBDIR)/lib/libcirclenewlib.a
	@cp $< $@
	@$(AR) d $@ io.o

EXTRACLEAN += $(FILTERED_CIRCLE_NEWLIB)
EXTRACLEAN += $(OBJS) $(DEPS)
# make_machines.sh invokes an unqualified "make clean", for which
# MACHINE_CLASS is unset. Remove both mutually exclusive core objects so a
# previous machine build cannot link against a differently configured Circle.
EXTRACLEAN += src/plus4emulatorcore.o src/viceemulatorcore.o
EXTRACLEAN += $(KEYBOARD_TEST_STAMP) $(KEYBOARD_TEST_BIN)
EXTRACLEAN += $(CONFIGS_TEST_STAMP) $(CONFIGS_TEST_BIN)

$(TARGET).img: $(FILTERED_CIRCLE_NEWLIB)

LIBS := $(VICELIBS) \
        third_party/common/libbmc64common.a \
        $(NEWLIBDIR)/lib/libm.a \
	$(NEWLIBDIR)/lib/libc.a \
	$(FILTERED_CIRCLE_NEWLIB) \
 	$(CIRCLEHOME)/addon/SDCard/libsdcard.a \
  	$(CIRCLEHOME)/lib/usb/libusb.a \
 	$(CIRCLEHOME)/lib/input/libinput.a \
 	$(CIRCLEHOME)/lib/fs/libfs.a \
  	$(CIRCLEHOME)/lib/net/libnet.a \
  	$(CIRCLEHOME)/addon/vc4/vchiq/libvchiq.a \
	$(CIRCLEHOME)/addon/vc4/interface/bcm_host/libbcm_host.a \
	$(CIRCLEHOME)/addon/vc4/interface/khronos/libkhrn_client.a \
	$(CIRCLEHOME)/addon/vc4/interface/vcos/libvcos.a \
	$(CIRCLEHOME)/addon/vc4/interface/vmcs_host/libvmcs_host.a \
  	$(CIRCLEHOME)/addon/linux/liblinuxemu.a \
	$(CIRCLEHOME)/addon/fatfs/libfatfs.a \
	$(CIRCLEHOME)/addon/wlan/hostap/wpa_supplicant/libwpa_supplicant.a \
	$(CIRCLEHOME)/addon/wlan/libwlan.a \
	$(CIRCLEHOME)/lib/sound/libsound.a \
  	$(CIRCLEHOME)/lib/sched/libsched.a \
  	$(CIRCLEHOME)/lib/libcircle.a

# R6: Track linked libraries when deciding whether to rebuild firmware.
$(TARGET).img: $(LIBS)

# These archives have their own object dependency graphs. Always consult them
# before linking; an existing archive alone does not mean its sources are current.
.PHONY: check-native-archives
check-native-archives:

third_party/common/libbmc64common.a: check-native-archives
	+$(MAKE) -C third_party/common

ifneq ($(strip $(VICE)),)
# Use the configured VICE rules without regenerating its legacy autotools
# files. Supply workspace-local includes (the configured paths may be stale).
$(VICE)/arch/raspi/libarch.a: check-native-archives
	+$(MAKE) -C $(VICE)/arch/raspi -o Makefile libarch.a \
		CFLAGS='-O3 $(ARCH) -ffreestanding -nostdlib $(foreach p,third_party/common $(NEWLIBDIR)/include third_party/circle-stdlib/include $(CIRCLEHOME)/include $(CIRCLEHOME)/addon $(CIRCLEHOME)/addon/fatfs,-I$(abspath $(p)))'
endif

.PHONY: check-datasette-link
ifneq ($(strip $(VICE)),)
.DEFAULT_GOAL := all
all: check-datasette-link
check-datasette-link: $(TARGET).img
	@$(PYTHON) tools/webui_test/datasette_link_test.py --nm $(PREFIX)nm --elf $(TARGET).elf
endif

# Retain the dormant lifetime API in the ELF without invoking it at startup.
LDFLAGS += --undefined=circle_device_lifetime_api_version

# Retain the dormant submission API without invoking it.
LDFLAGS += --undefined=circle_usb_submission_api_version

# ConfigFile is shared by storage, protection, deletion, boot and firmware defaults.
$(wildcard src/configs/*.o): src/configs/configs.h src/configs/configs_internal.h
# Boot options and the GPIO sampler are used before VICE starts.
src/main.o src/kernel.o src/viceapp.o src/viceoptions.o src/viceemulatorcore.o src/vice_network.o: src/viceoptions.h src/viceapp.h
src/viceapp.o: src/keyboard/gpio_recovery.h

# Config metadata layout is shared by all native Config modules.
$(filter src/configs/%.o,$(OBJS)): src/configs/configs_internal.h src/configs/configs.h

src/network_prefs.o src/viceapp.o: src/network_prefs.h

# Global networking is independent of Config and video timing storage.
NETWORK_TEST_STAMP = build/.network_tests.stamp
$(NETWORK_TEST_STAMP): tools/network_test/run_tests.py sdcard/config.txt sdcard/cmdline.txt templates/e64-v1/system/machines.txt src/network_prefs.c src/network_prefs.h src/viceapp.cpp third_party/common/menu.c third_party/common/menu_switch.c $(wildcard src/configs/*.c src/configs/*.h)
	@echo "  TEST  global network"
	@$(PYTHON) tools/network_test/run_tests.py
	@mkdir -p $(dir $@) && touch $@

src/network_prefs.o src/viceapp.o: $(NETWORK_TEST_STAMP)

# Hardware-wide fan policy/GPIO bridge (no changes to emulator frame timing).
src/fan_control.o src/fan_gpio.o src/kernel.o src/viceapp.o src/main.o src/power/power.o src/webui/webui.o: src/fan_control.h
