========================================================================
 E64 - Enhanced 64
 Configs
========================================================================

Default NTSC and Default PAL are protected firmware Configs. The menu shows
NTSC - Default (Read Only) and PAL  - Default (Read Only). The * marker
identifies the running Config independently of the cursor.

Missing or corrupt active selection starts Default NTSC. Hold C= at boot
for protected Default NTSC, even if held continuously from power-on.
Shift+C= has no special recovery function; C= still selects NTSC. Shift
alone leaves selection unchanged. Select protected Default PAL normally.
Normal boot loads the last selected Config, subject to Start once.
The former C=+F7 recovery is removed. A failed
PAL timing lookup tries NTSC, then retains usable current video if needed.

Factory Configs cannot be saved, renamed, deleted, unprotected or replaced.
Use New Config From Current Settings for a writable copy. Save Settings
saves user Configs through recoverable per-file transactions. Names accept
32 UTF-8 bytes. Existing custom ROMs, palettes and settings remain intact.
Start once returns to the power-on Config on the next power-on.

Files:
  active.txt         Persistent and optional one-time Config selection
  active.new         Verified pending selection for rename-gap recovery
  <id>/config.txt    Name, machine, category, startup media and autostart
  <id>/settings.txt  Legacy user settings, retained without conversion
  <id>/settings-c64.txt   Machine-specific native settings
  <id>/vice.ini      Emulator settings including ROM and drive choices

User writes use .e64-new staging and .e64-old rollback siblings. Interrupted
saves recover before settings are loaded. Browser edits retain .bak copies.
Protection and recoverable deletion use independent checked journals.
Deleted Configs can be restored before the existing countdown expires.

Retired root settings.txt, vice.ini, /E64SET.NEW, /E64SET.OLD and configs/main
are preserved and protected. They are no longer loaded or recovered by
startup. No old settings are migrated and no replacement Config is created.
Do not remove these files before separate hardware-validated cleanup.

------------------------------------------------------------------------
