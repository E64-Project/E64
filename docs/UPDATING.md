# Updating E64

E64 V1 does not include the inherited BMC64 automatic updater.

Do not install upstream BMC64 update packages on E64.

## Manual Installation

1. Back up the complete existing SD card.
2. Obtain the intended E64 release package.
3. Verify the supplied SHA256 checksums.
4. Review the release-specific installation instructions.
5. Preserve personal ROMs, Configs and network settings.
6. Install the appropriate E64 release files.

Future community-maintained versions may provide their own
update procedures.

E64 V1 is provided as-is, without a commitment to future
releases, maintenance or technical support.

## Upgrading from V1.0.0 to V1.0.1

For an existing E64 V1.0.0 installation on the Raspberry Pi 3B+:

1. Back up the existing SD card.
2. Download kernel8-32.img and its SHA-256 checksum.
3. Verify the downloaded firmware checksum.
4. Replace only kernel8-32.img at the root of the SD card.
5. Safely remove the SD card and boot E64.
6. Confirm version 1.0.1 in the About menu.

Preserve all existing ROMs, Configs, network settings and boot files.
New installations should use the complete V1.0.1 installation ZIP.
