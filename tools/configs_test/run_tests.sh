#!/bin/bash
# Builds the configs tests with the PC's C compiler and runs them.
# Used by make_all.sh (before the long build) and by the Makefile.
# The Pi's SD card layer (src/sdcard/sd_fs_fatfs.c) is swapped for one that
# uses a temporary folder on the PC (tools/sdcard/sd_fs_posix.c).

cd "$(dirname "$0")/../.." || exit 1

CC="${CONFIGS_TEST_CC:-cc}"
BIN=build/.configs_test

if ! command -v "$CC" >/dev/null 2>&1
then
       echo "A host C compiler is required for the configs tests" >&2
       exit 1
fi

mkdir -p build
"$CC" -std=gnu11 -Wall -Wextra -Werror -Isrc/configs \
       tools/configs_test/configs_test.c tools/sdcard/sd_fs_posix.c \
       src/sdcard/sd_fs_file.c src/configs/*.c -o "$BIN" || exit 1
"./$BIN" || exit 1
python3 tools/configs_test/logical_delete_test.py || exit 1

python3 tools/configs_test/protection_test.py || exit 1
"$CC" -std=gnu11 -Wall -Wextra -Werror -Isrc/configs -Isrc/sdcard \
       tools/configs_test/phase1_test.c tools/sdcard/sd_fs_posix.c \
       src/sdcard/sd_fs_file.c src/configs/*.c src/keyboard/gpio_recovery.c \
       -o build/.phase1_test || exit 1
./build/.phase1_test || exit 1
python3 tools/configs_test/phase1_integration_test.py || exit 1
python3 tools/configs_test/pal_machine_test.py || exit 1
python3 tools/configs_test/timing_ui_test.py || exit 1
"$CC" -std=gnu11 -Wall -Wextra -Werror -Isrc/configs -Isrc/sdcard \
       tools/configs_test/selection_fault_test.c tools/sdcard/sd_fs_posix.c \
       src/sdcard/sd_fs_file.c src/configs/*.c \
       -Wl,--wrap=sd_open,--wrap=sd_write,--wrap=sd_sync,--wrap=sd_close,--wrap=sd_unlink,--wrap=sd_rename \
       -o build/.selection_fault_test || exit 1
./build/.selection_fault_test || exit 1
python3 tools/configs_test/storage_fault_test.py || exit 1
python3 tools/configs_test/web_storage_test.py || exit 1
python3 tools/configs_test/stage2_audit_test.py || exit 1

python3 tools/configs_test/native_delete_test.py || exit 1

python3 tools/configs_test/native_rename_test.py || exit 1
