#include "network_config.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace {
char *Trim(char *s) {
  while (isspace(static_cast<unsigned char>(*s))) ++s;
  char *end = s + strlen(s);
  while (end > s && isspace(static_cast<unsigned char>(end[-1]))) --end;
  *end = '\0';
  return s;
}

bool IPv4(const char *text, uint8_t ip[4]) {
  for (unsigned i = 0; i < 4; ++i) {
    if (!isdigit(static_cast<unsigned char>(*text))) return false;
    unsigned value = 0, digits = 0;
    while (isdigit(static_cast<unsigned char>(*text))) {
      value = value * 10 + (*text++ - '0');
      if (++digits > 3 || value > 255) return false;
    }
    ip[i] = static_cast<uint8_t>(value);
    if (i < 3 && *text++ != '.') return false;
  }
  return *text == '\0';
}

bool YesNo(const char *value, bool *out) {
  if (!strcmp(value, "YES")) { *out = true; return true; }
  if (!strcmp(value, "NO")) { *out = false; return true; }
  return false;
}

bool NetmaskValid(const uint8_t mask[4]) {
  uint32_t bits = (uint32_t(mask[0]) << 24) | (uint32_t(mask[1]) << 16) |
                  (uint32_t(mask[2]) << 8) | mask[3];
  if (bits == 0) return false;
  const uint32_t inverse = ~bits;
  return (inverse & (inverse + 1)) == 0;
}
}

bool LoadBmcNetworkConfig(BmcNetworkConfig *config) {
  if (!config) return false;
  BmcNetworkConfig candidate = {};
  candidate.dhcp = true;
  candidate.ntp_enabled = true;
  strcpy(candidate.ntp_server, "192.168.1.5");
  candidate.timezone_minutes = -300;
  candidate.dst_enabled = true;
  candidate.netmask[0] = candidate.netmask[1] = candidate.netmask[2] = 255;
  *config = candidate;

  FILE *file = fopen("/system/network.cfg", "r");
  if (!file) return true;
  char line[256];
  bool valid = true;
  unsigned line_no = 0;
  while (fgets(line, sizeof(line), file)) {
    ++line_no;
    // A final line need not end in a newline. Reject overlong input.
    if (!strchr(line, '\n') && strlen(line) == sizeof(line) - 1) {
      valid = false;
      break;
    }
    char *key = Trim(line);
    if (*key == '#' || !*key) continue;
    char *equals = strchr(key, '=');
    if (!equals) { valid = false; break; }
    *equals++ = '\0';
    key = Trim(key);
    char *value = Trim(equals);
    if (!strcmp(key, "MODE")) {
      if (!strcmp(value, "DHCP")) candidate.dhcp = true;
      else if (!strcmp(value, "STATIC")) candidate.dhcp = false;
      else valid = false;
    } else if (!strcmp(key, "IP")) valid = IPv4(value, candidate.ip);
    else if (!strcmp(key, "NETMASK")) valid = IPv4(value, candidate.netmask);
    else if (!strcmp(key, "GATEWAY")) valid = IPv4(value, candidate.gateway);
    else if (!strcmp(key, "DNS")) valid = IPv4(value, candidate.dns);
    else if (!strcmp(key, "NTP_ENABLED")) valid = YesNo(value, &candidate.ntp_enabled);
    else if (!strcmp(key, "DST_ENABLED")) valid = YesNo(value, &candidate.dst_enabled);
    else if (!strcmp(key, "NTP_SERVER")) {
      if (!*value || strlen(value) >= sizeof(candidate.ntp_server)) valid = false;
      else strcpy(candidate.ntp_server, value);
    } else if (!strcmp(key, "TIMEZONE")) {
      char *end = nullptr;
      long hours = strtol(value, &end, 10);
      if (!*value || *end || hours < -12 || hours > 14) valid = false;
      else candidate.timezone_minutes = static_cast<int>(hours * 60);
    } else if (!strcmp(key, "TIMEZONE_MINUTES")) {
      char *end = nullptr;
      long minutes = strtol(value, &end, 10);
      if (!*value || *end || minutes < -720 || minutes > 840) valid = false;
      else candidate.timezone_minutes = static_cast<int>(minutes);
    } else valid = false;
    if (!valid) break;
  }
  if (ferror(file)) valid = false;
  fclose(file);
  if (!candidate.dhcp && (candidate.ip[0] == 0 ||
      candidate.ip[0] >= 224 || !NetmaskValid(candidate.netmask))) valid = false;
  if (valid) *config = candidate;
  else fprintf(stderr, "network.cfg: invalid setting near line %u; using DHCP defaults\n", line_no);
  return valid;
}
