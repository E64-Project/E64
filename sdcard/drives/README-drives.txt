========================================================================
 E64 - Enhanced 64
 DRIVE DOS ROM FILENAMES AND COMPATIBILITY
========================================================================

STANDARD DRIVE ROMS - /drives
------------------------------------------------------------------------
Keep these exact filenames; their capitalization is intentional.

  dos1541      16384 bytes   Commodore 1541
  d1541II      16384 bytes   Commodore 1541-II (not dos1541II)
  dos1570      32768 bytes   Commodore 1570
  dos1571      32768 bytes   Commodore 1571
  dos1581      32768 bytes   Commodore 1581
  dos2000      32768 bytes   CMD FD-2000
  dos4000      32768 bytes   CMD FD-4000
  dosCMDHD     16384 bytes   CMD HD; supplied ROM is v2.80

The installed 1570 ROM does not add a separate 1570 native menu choice.
A drive model needs its matching ROM; image format and model are distinct.
VICE's default DOS filenames above match the production resource defaults.
Its search order is /c64, /drives, /carts. Keep DOS ROMs
here, without duplicate copies in /c64 that could override them.
bootstat.txt in /c64 scopes absent-ROM shortcuts to /c64, not /drives.

IEEE-488 DRIVE ROMS - /drives
------------------------------------------------------------------------
  dos2031      16384 bytes   Commodore 2031
  dos2040       8192 bytes   Commodore 2040
  dos3040      12288 bytes   Commodore 3040
  dos4040      12288 bytes   Commodore 4040
  dos1001      16384 bytes   Commodore 1001 / 8250 family

These are drive DOS ROMs, separate from /carts/eprom.bin. Enable the IEEE
interface and select a matching drive model, then attach its disk image.
The 8250 is dual mechanism: select drive 8 or 10 as the first device of a
pair, not 9 or 11. See /carts/README-carts.txt for the interface ROM.
One copy of dos1001 in /drives is sufficient.

OPTIONAL JIFFYDOS DRIVE ROMS
------------------------------------------------------------------------
  JD-d1541II   16384 bytes   JiffyDOS 1541-II
  JD-dos1571   32768 bytes   JiffyDOS 1571
  JD-dos1581   32768 bytes   JiffyDOS 1581

JiffyDOS C64 KERNALs (JD-kernal and color variants) belong in /c64.
Create a Config, select the matching KERNAL/drive-ROM pair and save it.
Default Configuration does not select these merely because they exist.
Preserve stock ROMs separately. Disk images such as .d64, .d81 and .dhd
are media, not drive firmware. Preserve ROM filenames, sizes and bytes.

HISTORICAL TEST RESULTS - NOT VALIDATION OF THIS BUILD
------------------------------------------------------------------------
The approved backup notes record R3/R4 Pi 3B+ tests of 1541, 1541-II,
1571, 1581, FD-2000, FD-4000 and CMD HD, and JiffyDOS switching/drive ROMs.
FD-2000 D2M directory/file writes, FD-4000 D4M directory/file writes and
CMD HD DHD operation were verified in those historical tests.
R4 tested D64, D71, D81, D82 and G64 images. D82 operation alone does not
establish full 8250 IEEE emulation. The installed 1570 ROM was not a 1570
menu/model test. Verify IEEE models separately on hardware. Host checks
and these prior results do not validate this new kernel or directory layout.
