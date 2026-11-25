# E64 V1 Installation

## Hardware

The E64 V1 release targets the Raspberry Pi 3B+ with HDMI video.

## Prepare the SD Card

1. Prepare a FAT32-formatted SD card.
2. Extract the E64 V1 SD card release archive.
3. Copy its contents to the root of the SD card.
4. Obtain and install the required Commodore ROM files.
5. Insert the SD card into the Raspberry Pi and power it on.

No separate Linux operating system is required.

## Required ROM Files

Commodore ROMs are not distributed with E64 V1.

| Directory | Filename | Size |
|---|---|---:|
| /c64 | basic | 8192 bytes |
| /c64 | kernal | 8192 bytes |
| /c64 | chargen | 4096 bytes |
| /drives | d1541II | 16384 bytes |

Additional drive ROMs, JiffyDOS ROMs, replacement KERNALs and
cartridge ROMs may be installed separately.

See the directory-specific instructions:

- [C64 ROMs](../sdcard/c64/README-c64.txt)
- [Drive ROMs](../sdcard/drives/README-drives.txt)
- [Cartridge ROMs](../sdcard/carts/README-carts.txt)
- [Complete SD card layout](../sdcard/README.txt)

## Raspberry Pi Firmware

The required Raspberry Pi boot files and Wi-Fi device firmware
are supplied with the distribution under their respective
vendor licenses.

Preserve the accompanying copyright and license documents.

## Existing Installations

Back up existing ROMs, Configs and personal settings before
installing E64 V1.

Do not apply upstream BMC64 update packages to E64.

See [Updating E64](UPDATING.md).

## Release Validation

The published kernel has passed compilation and host regression checks.
Full hardware verification of the published firmware remains outstanding.
