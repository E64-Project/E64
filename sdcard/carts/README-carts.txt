========================================================================
 E64 - Enhanced 64
 CARTRIDGE IMAGES AND IEEE-488 INTERFACE
========================================================================

CARTRIDGE FILES - /carts
------------------------------------------------------------------------
Put cartridge ROM images and supported CRT cartridge containers here.
Use the Cartridge menu to attach the appropriate cartridge type/image.
A file's presence does not enable it or guarantee format compatibility.
Drive DOS ROMs belong in /drives, not here. Cartridge images are not disk
images. Preserve original filenames and obtain ROMs from a permitted source.

IEEE-488 INTERFACE
------------------------------------------------------------------------
  eprom.bin   4096 bytes   IEEE-488 interface EEPROM image

Keep the exact filename /carts/eprom.bin. The native Cartridge menu loads
this absolute path explicitly when enabling the interface and restarts
the emulator. This replaces the historical relative-path description.
The interface is not enabled by default. Select a suitable IEEE drive
model and ensure its DOS ROM is in /drives, then attach the disk image.
The interface ROM cannot substitute for a drive DOS ROM.

Dual-mechanism IEEE drives use drive 8 or 10 as the first device of a pair.
See /drives/README-drives.txt for dos2031, dos2040, dos3040, dos4040 and
dos1001. Historical D82 image tests do not prove full 8250 emulation;
separate interface/drive hardware validation remains necessary.
