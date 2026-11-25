#include "fan_control.h"
#include "sdcard/sd_fs.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <errno.h>

int fan_settings_valid(const FanSettings *p) {
  return p && (p->enabled == FAN_OFF || p->enabled == FAN_AUTO || p->enabled == FAN_ON) &&
    p->off_c >= FAN_MIN_C && p->on_c <= FAN_MAX_C && p->off_c < p->on_c;
}
int fan_decide(const FanSettings *p, int available, int was_on, int millic) {
  if (!available || p->enabled == FAN_OFF) return 0;
  if (p->enabled == FAN_ON) return 1;
  if (millic <= 0 || millic > 125000) return 1;
  if (millic >= p->on_c * 1000) return 1;
  if (millic <= p->off_c * 1000) return 0;
  return !!was_on;
}
static int recover(void) {
  int live = sd_stat(FAN_PREFS_FILE, NULL, NULL);
  if (live != SD_OK && live != SD_NOT_FOUND) return 1;
  if (live == SD_NOT_FOUND && sd_stat(FAN_PREFS_FILE ".old", NULL, NULL) == SD_OK)
    return sd_rename(FAN_PREFS_FILE ".old", FAN_PREFS_FILE) != SD_OK;
  return 0;
}
int fan_prefs_load(FanSettings *p) {
  *p = (FanSettings){0, 55, 50};
  if (recover()) return 1;
  int exists = sd_stat(FAN_PREFS_FILE, NULL, NULL);
  if (exists == SD_NOT_FOUND) return 0;
  if (exists != SD_OK) return 1;
  char text[160];
  FanSettings candidate;
  int n = sd_read_file(FAN_PREFS_FILE, text, sizeof(text));
  if (n < 0 || n >= (int)sizeof(text)-1 || strlen(text) != (size_t)n) return 1;
  const char *keys[] = {"fan_enabled=", "fan_on_c=", "fan_off_c="};
  int *fields[] = {&candidate.enabled, &candidate.on_c, &candidate.off_c};
  char *cursor = text;
  for (int i = 0; i < 3; ++i) {
    size_t len = strlen(keys[i]);
    if (strncmp(cursor, keys[i], len)) return 1;
    cursor += len;
    if (*cursor < '0' || *cursor > '9') return 1;
    char *end;
    errno = 0;
    long value = strtol(cursor, &end, 10);
    if (errno || value > 100 || (*end != '\n' && *end != '\r' && *end)) return 1;
    *fields[i] = (int)value;
    cursor = end;
    if (*cursor == '\r') ++cursor;
    if (*cursor == '\n') ++cursor;
  }
  if (*cursor || !fan_settings_valid(&candidate)) return 1;
  *p = candidate;
  return 0;
}
int fan_prefs_save(const FanSettings *p) {
  if (!fan_settings_valid(p) || recover() || sd_mkdir("/system") != SD_OK) return 1;
  char text[160];
  int n = snprintf(text, sizeof(text), "fan_enabled=%d\nfan_on_c=%d\nfan_off_c=%d\n",
                   p->enabled, p->on_c, p->off_c);
  if (sd_write_file(FAN_PREFS_FILE ".new", text, n) != SD_OK) return 1;
  int live = sd_stat(FAN_PREFS_FILE, NULL, NULL) == SD_OK;
  if (sd_stat(FAN_PREFS_FILE ".old", NULL, NULL) == SD_OK &&
      sd_unlink(FAN_PREFS_FILE ".old") != SD_OK) return 1;
  if (live && sd_rename(FAN_PREFS_FILE, FAN_PREFS_FILE ".old") != SD_OK) return 1;
  if (sd_rename(FAN_PREFS_FILE ".new", FAN_PREFS_FILE) != SD_OK) {
    if (live) sd_rename(FAN_PREFS_FILE ".old", FAN_PREFS_FILE);
    return 1;
  }
  return 0;
}
