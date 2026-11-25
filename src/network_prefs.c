#include "network_prefs.h"
#include "sdcard/sd_fs.h"
#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PREFS_NEXT NETWORK_PREFS_FILE ".new"
#define PREFS_OLD NETWORK_PREFS_FILE ".old"

static int valid_ftdi(const FtdiSettings *s) {
  return s->adapter >= 0 && s->adapter <= 17 &&
         s->baud > 0 && (!s->adapter || s->baud == 300 || s->baud == 600 ||
                        s->baud == 1200 || s->baud == 2400 || s->baud == 9600) &&
         s->parity >= 0 && s->parity <= 2 &&
         (s->data_bits == 7 || s->data_bits == 8) &&
         (s->stop_bits == 1 || s->stop_bits == 2) &&
         (s->enabled == 0 || s->enabled == 1);
}

static void parse_ftdi(const char *value, FtdiSettings *settings) {
  FtdiSettings parsed;
  int *fields[] = {&parsed.adapter, &parsed.baud, &parsed.parity,
                   &parsed.data_bits, &parsed.stop_bits, &parsed.enabled};
  *settings = (FtdiSettings){0};
  for (unsigned i = 0; i < sizeof(fields) / sizeof(fields[0]); ++i) {
    char *end;
    if (*value < '0' || *value > '9') return;
    errno = 0;
    long number = strtol(value, &end, 10);
    char separator = i + 1 == sizeof(fields) / sizeof(fields[0]) ? '\0' : ',';
    if (*end != separator || errno == ERANGE || number > INT_MAX) return;
    *fields[i] = (int)number;
    value = end + 1;
  }
  if (valid_ftdi(&parsed)) *settings = parsed;
}

static int valid(const NetworkPrefs *p) {
  if (p->device < 0 || p->device > 2 || p->webui_enabled < 0 || p->webui_enabled > 1 ||
      !memchr(p->webui_pin, 0, sizeof(p->webui_pin)) ||
      (p->modem_base != 0 && p->modem_base != 0xd700 && p->modem_base != 0xde00 &&
       p->modem_base != 0xdf00 && p->modem_base != 0xdf80) ||
      (p->modem_baud != 300 && p->modem_baud != 1200 && p->modem_baud != 2400)) return 0;
  for (const char *c = p->webui_pin; *c; ++c)
    if ((unsigned char)*c < 32 || (unsigned char)*c == 127) return 0;
  return 1;
}
static int recover(void) {
  int live = sd_stat(NETWORK_PREFS_FILE, NULL, NULL);
  if (live != SD_OK && live != SD_NOT_FOUND) return 1;
  if (live == SD_NOT_FOUND && sd_stat(PREFS_OLD, NULL, NULL) == SD_OK)
    return sd_rename(PREFS_OLD, NETWORK_PREFS_FILE) != SD_OK;
  return 0;
}
int network_prefs_save(const NetworkPrefs *prefs) {
  const FtdiSettings *ftdi = &prefs->ftdi;
  if (!valid(prefs) || (ftdi->baud && !valid_ftdi(ftdi)) || recover()) return 1;
  char text[256];
  int n = snprintf(text, sizeof(text),
      "network_device=%d\nwebui_enabled=%d\nwebui_pin=%s\nnetwork_modem_base=%d\nnetwork_modem_baud=%d\n",
      prefs->device, prefs->webui_enabled, prefs->webui_pin, prefs->modem_base, prefs->modem_baud);
  if (ftdi->baud)
    n += snprintf(text + n, sizeof(text) - n, "ftdi=%d,%d,%d,%d,%d,%d\n",
                  ftdi->adapter, ftdi->baud, ftdi->parity, ftdi->data_bits,
                  ftdi->stop_bits, ftdi->enabled);
  if (sd_write_file(PREFS_NEXT, text, n) != SD_OK) return 1;
  int have_live = sd_stat(NETWORK_PREFS_FILE, NULL, NULL) == SD_OK;
  if (sd_stat(PREFS_OLD, NULL, NULL) == SD_OK && sd_unlink(PREFS_OLD) != SD_OK) return 1;
  if (have_live && sd_rename(NETWORK_PREFS_FILE, PREFS_OLD) != SD_OK) return 1;
  if (sd_rename(PREFS_NEXT, NETWORK_PREFS_FILE) != SD_OK) {
    if (have_live) sd_rename(PREFS_OLD, NETWORK_PREFS_FILE);
    return 1;
  }
  return 0;
}
static char *trim(char *s) {
  while (*s == ' ' || *s == '\t' || *s == '\r') ++s;
  char *e = s + strlen(s);
  while (e > s && (e[-1] == ' ' || e[-1] == '\t' || e[-1] == '\r')) --e;
  *e = 0;
  return s;
}
static int parse(char *text, NetworkPrefs *p) {
  int found = 0;
  for (char *line = text; line && *line;) {
    char *next = strchr(line, '\n');
    if (next) *next++ = 0;
    line = trim(line);
    char *eq = strchr(line, '=');
    if (*line != '#' && eq) {
      *eq++ = 0;
      char *key = trim(line), *value = trim(eq);
      int *number = NULL;
      if (!strcmp(key, "network_device")) number = &p->device;
      else if (!strcmp(key, "webui_enabled")) number = &p->webui_enabled;
      else if (!strcmp(key, "network_modem_base")) number = &p->modem_base;
      else if (!strcmp(key, "network_modem_baud")) number = &p->modem_baud;
      else if (!strcmp(key, "ftdi")) parse_ftdi(value, &p->ftdi);
      else if (!strcmp(key, "webui_pin")) {
        if (strlen(value) >= sizeof(p->webui_pin)) return -1;
        strcpy(p->webui_pin, value);
        found = 1;
      }
      if (number) {
        char *end;
        long n = strtol(value, &end, 10);
        if (!*value || *end || n < 0 || n > 100000) return -1;
        *number = (int)n;
        found = 1;
      }
    }
    line = next;
  }
  return valid(p) ? found : -1;
}
int network_prefs_load(NetworkPrefs *prefs, const char *legacy) {
  NetworkPrefs candidate = {.modem_baud = 300};
  *prefs = candidate;
  if (recover()) return 1;
  int exists = sd_stat(NETWORK_PREFS_FILE, NULL, NULL);
  if (exists != SD_OK && exists != SD_NOT_FOUND) return 1;
  /* Legacy native settings can be larger than the global preferences. */
  char *text = (char *)malloc(16384);
  if (!text) return 1;
  const char *path = exists == SD_OK ? NETWORK_PREFS_FILE : legacy ? legacy : "/settings.txt";
  int n = sd_read_file(path, text, 16384);
  if (n < 0 && exists != SD_OK && legacy &&
      sd_stat(path, NULL, NULL) == SD_NOT_FOUND) {
    path = "/settings.txt";
    n = sd_read_file(path, text, 16384);
  }
  if (n < 0 && exists != SD_OK && sd_stat(path, NULL, NULL) == SD_NOT_FOUND) {
    free(text);
    return 0;
  }
  int parsed = n < 0 ? -1 : parse(text, &candidate);
  free(text);
  if (parsed < 0 || (exists == SD_OK && !parsed)) return 1;
  *prefs = candidate;
  // Migrate once, without writing any old Config or root settings file.
  return exists != SD_OK && parsed ? network_prefs_save(prefs) : 0;
}
