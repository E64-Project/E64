#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "$(realpath -- "$0")")"

if [[ ! -f Makefile-C64 || ! -f sdcard/config.txt ]]; then
    echo "ERROR: E64 source root not found." >&2
    exit 1
fi

echo "Cleaning generated E64 build artifacts..."

find src third_party -type f \( \
    -name '*.o' -o \
    -name '*.lo' -o \
    -name '*.Po' -o \
    -name '*.Plo' -o \
    -name '*.pyc' \
\) -delete

rm -f -- kernel8-32.elf kernel8-32.lst kernel8-32.map

echo "Cleanup complete."
echo "Source code and firmware images preserved."
