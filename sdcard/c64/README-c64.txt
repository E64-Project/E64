========================================================================
 E64 - Enhanced 64
 C64 SYSTEM ROMS AND SUPPORT FILES
========================================================================

DEFAULT SYSTEM ROMS - /c64
------------------------------------------------------------------------
Default Configuration (internal Main) starts with stock ROM filenames:

  basic       8192 bytes   Commodore 64 BASIC interpreter
  chargen     4096 bytes   C64 character generator (CHARGEN)
  kernal      8192 bytes   Standard Commodore 64 KERNAL

Use ROMs from a source you may use. The loader also accepts a two-byte
load-address header for these system ROMs. Extensionless names are valid.
The production search order is /c64, /drives, /carts.
Do not leave conflicting drive-ROM copies in /c64: it is searched first.

OPTIONAL KERNAL VARIANTS - 8192 BYTES EACH
------------------------------------------------------------------------
  kernal-Green-on-Black
  kernal-LightBlue-on-Blue
  kernal-LightGray-on-Blue
  kernal-LightGreen-on-Black
  JD-kernal                       JiffyDOS, standard colors
  JD-kernal-Green-on-Black
  JD-kernal-LightBlue-on-Blue
  JD-kernal-LightGray-on-Blue
  JD-kernal-LightGreen-on-Black

Color suffixes describe each KERNAL's screen colors. Merely storing a ROM
here does not select it. Keep stock and JD-* filenames separate. Create
a Config, choose its alternate KERNAL in the native ROM menu, then save.
For JiffyDOS, choose a matching drive ROM from /drives as well; see
/drives/README-drives.txt. Main does not automatically select JiffyDOS.

KEYBOARD, PALETTES AND BOOT LOOKUPS
------------------------------------------------------------------------
  rpi_pos.vkm   Positional keyboard mapping; other *.vkm maps also live here
  *.vpl         Color palettes, when used
  bootstat.txt  Boot-time file lookup shortcuts; not a ROM

Keep keyboard mapping filenames and bytes unchanged. Keymaps remain
available in keyboard configuration, but *.vkm, README and other known
support files are hidden from Load ROM. Valid extensionless ROMs remain
selectable. Files selected from another directory keep their chosen path.

bootstat.txt scopes missing drive-ROM shortcuts to /c64 so real ROMs in
/drives are not hidden. Do not replace these with unqualified dos* failure
entries. Drive firmware belongs in /drives; cartridges belong in /carts.
ROM-Notes.txt has been distributed into these directory READMEs.
