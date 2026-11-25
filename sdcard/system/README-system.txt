========================================================================
 E64 - Enhanced 64
 SYSTEM SUPPORT AND MANAGEMENT FILES
========================================================================

NETWORK AND MACHINE FILES - /system
------------------------------------------------------------------------
  network.cfg                DHCP/static addressing and network time
  wifi-settings.conf         Preferred Wi-Fi credentials
  wpa_supplicant.conf         Fallback if wifi-settings.conf is absent
  *.conf.example             Templates; copy/edit to the active filename
  network-readme.txt          Network setup and troubleshooting
  machines.txt               Available machine and video modes
  demo.txt                   Demo playback definition, when enabled
  LICENSE                    Software license and upstream attribution

Keep network configuration and credentials private. Preserve existing
credentials when preparing a revised layout. Saving Wi-Fi settings uses
wifi-settings.conf; do not keep conflicting fallback credentials.
Device firmware belongs in /firmware. Machine/video defaults should not
be changed during a documentation or layout review.

CONFIG MANAGEMENT JOURNALS
------------------------------------------------------------------------
  protect/ and protect.id    Protection journal and anchor
  deleted/ and deleted.id    Logical-deletion/restore journal and anchor

These binary records are created when needed. Keep each journal with its
anchor. Do not edit, delete or partially restore them. Invalid/incomplete
records cause management to fail closed until recovery is reviewed.
Named Configs belong in /configs; Main's displayed name is Default
Configuration. Its identity remains main and it is permanently protected.

ROOT SETTINGS AND SAVE RECOVERY
------------------------------------------------------------------------
/settings.txt and /vice.ini hold Main settings. /E64SET.NEW and
/E64SET.OLD are reserved root transaction/recovery paths. Do not move them
into /system or remove them during a save/recovery. They are normally
absent in a clean layout. Use native Save Settings for Main.
Keep mandatory Raspberry Pi boot files at root, as described in /README.txt.
