E64 V1 paths: /system/network.cfg, /system/wifi-settings.conf and
/system/wpa_supplicant.conf. Keep Wi-Fi firmware in /firmware.

E64 - Network and Time Setup
============================

Files in /system on the E64 SD card:
  network.cfg                DHCP/static network and clock settings
  wifi-settings.conf         Wi-Fi credentials (create from .example)
  network-readme.txt         This guide

1. Edit network.cfg in a plain-text editor. Save as ordinary text (no rich
   formatting). Restart E64 for changes to take effect.
2. MODE=DHCP asks the router for an IP address, subnet mask, gateway and DNS.
   MODE=STATIC uses IP, NETMASK, GATEWAY and DNS from the file.
   Use dotted IPv4 values. NETMASK must be a contiguous mask. Avoid an IP
   already assigned to another device. Gateway/DNS may be 0.0.0.0 for an
   intentionally isolated network such as a dedicated test LAN.
3. NTP_ENABLED=YES obtains UTC time from NTP_SERVER. Use a local IPv4 address
   (default 192.168.1.5), or a hostname such as pool.ntp.org when DNS works.
   On failure E64 retries in five minutes, and resyncs every 15 minutes.
4. TIMEZONE specifies STANDARD UTC offset in whole hours. For US Eastern use
   -5, including summer. DST_ENABLED=YES follows current US DST rules after
   NTP synchronization. It does not model historical rule changes or non-US
   DST rules. Use DST_ENABLED=NO for fixed standard time. Daylight correction
   is applied after NTP succeeds; until then the standard offset is used.
5. For Wi-Fi, copy /system/wifi-settings.conf.example to
   /system/wifi-settings.conf and replace YOUR_WIFI_NAME and YOUR_WIFI_PASSWORD. The old
   wpa_supplicant.conf filename still works as a fallback, but the new name
   takes precedence. Do not keep conflicting credentials in both files.
   Wi-Fi firmware under /firmware remains required. Network device (Off,
   Ethernet, Wi-Fi) is still selected in E64's existing settings/menu.

Syntax:
  - Comments must occupy their own lines and begin with #.
  - Each setting must be KEY=VALUE. Spaces around = are allowed.
  - Keys, MODE values, YES and NO are case-sensitive.
  - An unknown key or invalid value rejects the file: E64 logs the error
    and defaults to DHCP and clock defaults rather than partially applying it.
  - Missing network.cfg defaults to DHCP and NTP=192.168.1.5.

Troubleshooting:
  - DHCP requires a responding DHCP server/router.
  - For STATIC, verify IP, subnet and gateway match your LAN.
  - Hostname-based NTP requires a valid DNS server.
  - If Wi-Fi fails, confirm the credentials and firmware. The legacy file
    is used only if wifi-settings.conf is absent. Saving Wi-Fi through the
    E64 menu writes wifi-settings.conf; it does not delete the old file.
  - Look at the E64 system log for network and NTP initialization messages.

Historical R3 source notes (not the current complete E64 checkout):
  This archive was supplied without third_party and build artifacts. Reuse
  the existing complete source checkout and toolchain for cross-compilation.
  The supplied menu.c was patched separately and is included under
  third_party/common/menu.c. The rest of third_party is still absent.
