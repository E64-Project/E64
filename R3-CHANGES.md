# BMC64 customized R3 source update

This update builds on Harry's customized BMC64 5.2.6 C64 source snapshot.
The original C64-only storage, Web UI and other project changes remain in
place; this is a source package, not a tested Raspberry Pi boot image.

## Changes

- `network.cfg` selects DHCP or static addressing on Ethernet or Wi-Fi.
- IPv4, contiguous netmask, mode, clock settings and unknown keys are checked.
  Invalid configuration falls back to DHCP defaults with a log warning.
- NTP server hostname/IP and enabled flag come from `network.cfg`.
- Configured standard timezone and US daylight-saving rules are applied;
  daylight-saving correction is refreshed after successful NTP sync.
- `wifi-settings.conf` is the preferred WPA Supplicant filename; the original
  `wpa_supplicant.conf` remains a fallback for compatibility.
- Wi-Fi settings in the menu now load the preferred file, fall back to the
  original, and save only to `wifi-settings.conf`.
- The C64 menu's version string is now `5.2.6-R3`.
- The Web UI configuration file allowlist recognizes the new filenames.
- `network-readme.txt` and `wifi-settings.conf.example` explain setup.

## Integration into the complete Devuan checkout

This uploaded snapshot deliberately excluded `third_party` and `build`, so it
cannot be cross-compiled on its own. Copy these modified files into the full
checkout while preserving its `third_party` directory. Before compiling,
inspect any local changes made after this snapshot and merge them carefully.

`third_party/common/menu.c` was supplied separately and is included in this
R3 archive. It has the renamed Wi-Fi paths and the R3 version string. All
other files under `third_party` remain excluded: do not replace the entire
third-party tree with this partial directory.

Once the complete third-party sources and cross-compiler are available, run
the established build process (`source get_gnu_toolchain.sh`, then
`BOARD=pi3 make -f Makefile-C64`). Test both network modes, Wi-Fi filename
preference, NTP resolution, and March/November DST transitions on hardware.
