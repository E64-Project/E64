#ifndef BMC64_NETWORK_CONFIG_H
#define BMC64_NETWORK_CONFIG_H

#include <stdint.h>

struct BmcNetworkConfig {
  bool dhcp;
  uint8_t ip[4];
  uint8_t netmask[4];
  uint8_t gateway[4];
  uint8_t dns[4];
  bool ntp_enabled;
  char ntp_server[128];
  int timezone_minutes; // Standard-time UTC offset, e.g. -300 for Eastern.
  bool dst_enabled;      // US daylight-saving rules.
};

// Defaults to DHCP; missing file is permitted. Invalid settings reject the
// entire file and leave these safe defaults in effect.
bool LoadBmcNetworkConfig(BmcNetworkConfig *config);

#endif
