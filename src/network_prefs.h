#ifndef E64_NETWORK_PREFS_H
#define E64_NETWORK_PREFS_H
#ifdef __cplusplus
extern "C" {
#endif
/* Global service preferences. IP/NTP and credentials keep their existing
 * /system/network.cfg and /system/wifi-settings.conf storage. */
#define NETWORK_PREFS_FILE "/system/network-prefs.txt"
typedef struct FtdiSettings {
  int adapter;
  int baud; /* Zero means no global FTDI settings have been saved. */
  int parity;
  int data_bits;
  int stop_bits;
  int enabled;
} FtdiSettings;

typedef struct {
  int device; /* 0 Off, 1 Ethernet, 2 Wi-Fi */
  int webui_enabled;
  char webui_pin[16];
  int modem_base;
  int modem_baud;
  FtdiSettings ftdi;
} NetworkPrefs;
/* A missing global file can migrate the running legacy settings, read only.
 * NULL uses the preserved root settings as the legacy fallback. */
int network_prefs_load(NetworkPrefs *prefs, const char *legacy);
int network_prefs_save(const NetworkPrefs *prefs);
#ifdef __cplusplus
}
#endif
#endif
