========================================================================
 E64 - Enhanced 64
 SD CARD GUIDE - RASPBERRY PI 3B+
========================================================================

DIRECTORY LAYOUT
------------------------------------------------------------------------
Use FAT32. Directory names are lowercase; preserve ROM/vendor filenames.

  /c64       BASIC, CHARGEN, KERNAL variants, keymaps and palettes
  /drives    Drive DOS ROMs, including IEEE and JiffyDOS drive ROMs
  /carts     Cartridge images and the IEEE-488 interface eprom.bin
  /configs   Named Configs and power-on/Start once choices
  /firmware  Wi-Fi device firmware with original vendor filenames
  /system    Network settings, machine definitions and management journals

Each directory has its own README. Disk images and programs may remain
on USB in folders of your choice. Drive firmware is not a disk image.

FILES THAT STAY AT ROOT
------------------------------------------------------------------------
  config.txt       Raspberry Pi boot/video configuration
  cmdline.txt      Kernel command line
  bootcode.bin     Raspberry Pi boot program
  start.elf        Raspberry Pi boot firmware
  fixup.dat        Matching Raspberry Pi firmware data
  kernel8-32.img   E64 Pi 3B+ 32-bit kernel
  settings.txt     Retired native settings, preserved and protected
  vice.ini         Retired emulator settings, preserved and protected
  E64SET.NEW       Retired transaction staging, left untouched
  E64SET.OLD       Retired transaction rollback, left untouched

Keep any additional boot-required DTB/overlay files where config.txt
expects them. Do not rename mandatory boot files or change video defaults.
Retired settings and transaction files are no longer loaded or recovered.
Leave retired files intact until separate hardware-validated cleanup.

CONFIGS AND MEDIA
------------------------------------------------------------------------
Default NTSC and Default PAL are immutable firmware Configs. Missing or
corrupt selection starts Default NTSC. Hold C= at boot for protected Default
NTSC. Shift+C= has no special recovery function; select protected Default
PAL normally from Configs. Save Settings saves writable user Configs. Old
Main files remain protected on disk; no migration or cleanup runs. See the
Configs README.

The Web UI mounts disk images on drives 8-11; Load & Run uses drive 8.
Image-format choices and ROM inventory do not guarantee complete drive
emulation. D67, P64 and X64 menu entries alone are not compatibility tests.
README files are hidden from normal media pickers. ROM pickers also hide
keymaps and other known support files; keyboard menus retain keymaps.

REVIEW STATUS AND ATTRIBUTION
------------------------------------------------------------------------
E64 is Enhanced 64, derived from upstream BMC64 5.2.6, VICE and Circle.
See /system/LICENSE for the software license; preserve upstream notices.
This is the E64 V1 public-release layout. Host checks do not replace Pi boot,
visual, SD/USB, Config/protection and interrupted-save testing on hardware.
Back up ROMs and Config files separately unless a source/firmware archive
explicitly includes them. Historical source archives are not ROM backups.

RELEASE VERSION: 1.0.1
------------------------------------------------------------------------
Maintenance release correcting Web UI Config deletion and automatic refresh.

Official downloads:
https://github.com/E64-Project/E64/releases

Official community:
https://www.reddit.com/r/E64Project/
