/* Recoverable per-file user Config replacement. No change to file payloads.
 * An OLD copy always wins recovery, even if a final exists: only successful
 * readback of the replacement permits deleting OLD. NEW is never booted.
 * Filesystem durability contract (FatFs sync/rename/unlink).
 */
#include "configs_internal.h"
#include "../sdcard/sd_fs.h"
#include <stdio.h>
#include <string.h>

static volatile int storage_busy;
static int storage_lease;
static int take(void) { return __sync_bool_compare_and_swap(&storage_busy, 0, 1); }
static void give(void) { __sync_lock_release(&storage_busy); }
static int names(const char *path, char *next, char *old) {
   int a = snprintf(next, CONFIGS_MAX_PATH_LEN, "%s.e64-new", path);
   int b = snprintf(old, CONFIGS_MAX_PATH_LEN, "%s.e64-old", path);
   return a > 0 && a < CONFIGS_MAX_PATH_LEN && b > 0 && b < CONFIGS_MAX_PATH_LEN;
}
static int remove_optional(const char *path) {
   sd_info info;
   int rc = sd_stat_info(path, &info);
   if (rc == SD_NOT_FOUND) return 1;
   return rc == SD_OK && !info.is_dir && sd_unlink(path) == SD_OK;
}
static int recover_file(const char *path) {
   char next[CONFIGS_MAX_PATH_LEN], old[CONFIGS_MAX_PATH_LEN];
   if (!names(path, next, old)) return CONFIGS_ERROR;
   sd_info info;
   int previous = sd_stat_info(old, &info);
   if ((previous != SD_OK && previous != SD_NOT_FOUND) ||
       (previous == SD_OK && info.is_dir)) return CONFIGS_ERROR;
   if (previous == SD_OK) {
      /* If interrupted here, OLD is still available on the next attempt. */
      if (!remove_optional(path) || sd_rename(old, path) != SD_OK) return CONFIGS_ERROR;
   }
   if (!remove_optional(next)) return CONFIGS_ERROR;
   /* VICE's private backup of the staged resource file, never the original. */
   next[strlen(next)-1] = '~';
   return remove_optional(next) ? CONFIGS_OK : CONFIGS_ERROR;
}

static int payload_name(const char *name) {
   char lower[SD_MAX_NAME_LEN + 1];
   unsigned n = (unsigned)strlen(name);
   if (n > SD_MAX_NAME_LEN) return 0;
   for (unsigned i = 0; i <= n; i++) {
      char c = name[i]; lower[i] = c >= 'A' && c <= 'Z' ? c + 32 : c;
   }
   return !strcmp(lower, "config.txt") || !strcmp(lower, "vice.ini") ||
          !strcmp(lower, "settings.txt") ||
          (n >= 13 && !strncmp(lower, "settings-", 9) && !strcmp(lower + n - 4, ".txt"));
}
typedef struct { char base[SD_MAX_NAME_LEN + 1]; int found; } PendingFile;
static int find_pending(void *ctx, const sd_info *info) {
   PendingFile *pending = ctx;
   if (info->is_dir) return 0;
   unsigned n = (unsigned)strlen(info->name);
   if (n <= 8) return 0;
   char suffix[9];
   for (unsigned i = 0; i <= 8; i++) {
      char c = info->name[n - 8 + i]; suffix[i] = c >= 'A' && c <= 'Z' ? c + 32 : c;
   }
   if (strcmp(suffix, ".e64-new") && strcmp(suffix, ".e64-old") && strcmp(suffix, ".e64-ne~")) return 0;
   memcpy(pending->base, info->name, n - 8); pending->base[n - 8] = 0;
   pending->found = payload_name(pending->base);
   return pending->found;
}
int configs_storage_recover(const char *id) {
   if (!configs_id_valid(id) || configs_is_factory(id)) return CONFIGS_ERROR;
   if (!take()) return CONFIGS_ERROR;
   char dir[CONFIGS_MAX_PATH_LEN];
   snprintf(dir, sizeof(dir), "%s/%s", CONFIGS_DIR, id);
   int result = CONFIGS_ERROR;
   /* Close enumeration before mutating the directory. Repeat to cover all
    * native machine names, including existing custom settings-*.txt files. */
   for (unsigned i = 0; i < 256; i++) {
      PendingFile pending = {{0}, 0};
      int rc = sd_list_info(dir, find_pending, &pending);
      if (rc != SD_OK && rc != SD_NOT_FOUND) break;
      if (!pending.found) { result = CONFIGS_OK; break; }
      char path[CONFIGS_MAX_PATH_LEN];
      int n = snprintf(path, sizeof(path), "%s/%s", dir, pending.base);
      if (n <= 0 || n >= (int)sizeof(path) || recover_file(path) != CONFIGS_OK) break;
   }
   give();
   return result;
}

static int recover_directory(void *ctx, const sd_info *info) {
   int *ok = ctx;
   if (info->is_dir && configs_id_valid(info->name) &&
       !configs_is_factory(info->name) &&
       configs_storage_recover(info->name) != CONFIGS_OK) *ok = 0;
   return 0;
}
int configs_storage_recover_all(void) {
   int ok = 1;
   int rc = sd_list_info(CONFIGS_DIR, recover_directory, &ok);
   return ok && (rc == SD_OK || rc == SD_NOT_FOUND) ? CONFIGS_OK : CONFIGS_ERROR;
}

int configs_storage_begin(const char *id) {
   if (!configs_id_valid(id) || configs_is_factory(id) ||
       !configs_is_active(id) || !take()) return CONFIGS_ERROR;
   char path[CONFIGS_MAX_PATH_LEN];
   configs_path(id, "config.txt", path, sizeof(path));
   storage_lease = configs_path_acquire(path);
   if (storage_lease < 0) { give(); return CONFIGS_ERROR; }
   return CONFIGS_OK;
}
void configs_storage_end(void) {
   configs_path_release(storage_lease);
   storage_lease = 0;
   give();
}

/* Copy an existing VICE file so resources_save retains other machine sections.
 * A failed copy cannot touch the original. */
static int copy_file(const char *from, const char *to) {
   int exists = sd_stat(from, NULL, NULL);
   if (exists == SD_NOT_FOUND) return CONFIGS_OK;
   if (exists != SD_OK) return CONFIGS_ERROR;
   sd_file *in = sd_open(from, SD_READ);
   if (!in) return CONFIGS_ERROR;
   sd_file *out = sd_open(to, SD_WRITE);
   int ok = out != NULL;
   uint32_t remaining = sd_size(in);
   char buf[512];
   while (ok && remaining) {
      unsigned n = remaining < sizeof(buf) ? remaining : sizeof(buf), got = 0;
      ok = sd_read(in, buf, n, &got) == SD_OK && got == n && sd_write(out, buf, n) == SD_OK;
      remaining -= n;
   }
   if (sd_close(in) != SD_OK) ok = 0;
   if (out) {
      if (sd_sync(out) != SD_OK) ok = 0;
      if (sd_close(out) != SD_OK) ok = 0;
   }
   return ok ? CONFIGS_OK : CONFIGS_ERROR;
}
int configs_storage_prepare(const char *path, char *next, int size, int copy) {
   char old[CONFIGS_MAX_PATH_LEN], temp[CONFIGS_MAX_PATH_LEN];
   if (!names(path, temp, old) || (int)strlen(temp) >= size || recover_file(path) != CONFIGS_OK) return CONFIGS_ERROR;
   strcpy(next, temp);
   return copy ? copy_file(path, next) : CONFIGS_OK;
}

static int signature(const char *path, unsigned *checksum, uint32_t *length, int sync) {
   sd_file *f = sd_open(path, sync ? SD_UPDATE : SD_READ);
   if (!f) return CONFIGS_ERROR;
   int ok = !sync || sd_sync(f) == SD_OK;
   /* SD_UPDATE is write-only on FatFs: close and reopen before readback. */
   if (sync) {
      if (sd_close(f) != SD_OK) ok = 0;
      if (!ok) return CONFIGS_ERROR;
      f = sd_open(path, SD_READ);
      if (!f) return CONFIGS_ERROR;
   }
   *length = sd_size(f);
   uint32_t remaining = *length;
   unsigned crc = ~0U;
   unsigned char buf[512];
   while (ok && remaining) {
      unsigned n = remaining < sizeof(buf) ? remaining : sizeof(buf), got = 0;
      ok = sd_read(f, buf, n, &got) == SD_OK && got == n;
      if (ok) for (unsigned i = 0; i < n; i++) {
         crc ^= buf[i];
         for (int b = 0; b < 8; b++) crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1)));
      }
      remaining -= n;
   }
   if (sd_close(f) != SD_OK) ok = 0;
   *checksum = ~crc;
   return ok ? CONFIGS_OK : CONFIGS_ERROR;
}
static int commit_file(const char *path, int backup) {
   char next[CONFIGS_MAX_PATH_LEN], old[CONFIGS_MAX_PATH_LEN];
   unsigned crc, check; uint32_t len, check_len;
   if (!names(path, next, old) || sd_stat(old, NULL, NULL) != SD_NOT_FOUND ||
       signature(next, &crc, &len, 1) != CONFIGS_OK) return CONFIGS_ERROR;
   sd_info info;
   int current = sd_stat_info(path, &info);
   if ((current != SD_OK && current != SD_NOT_FOUND) ||
       (current == SD_OK && info.is_dir)) return CONFIGS_ERROR;
   if (current == SD_OK && sd_rename(path, old) != SD_OK) return CONFIGS_ERROR;
   if (sd_rename(next, path) != SD_OK) return CONFIGS_ERROR;
   if (signature(path, &check, &check_len, 0) != CONFIGS_OK || check != crc || check_len != len) return CONFIGS_ERROR;
   /* Browser edits historically retain .bak. Move OLD only after verifying
    * final; interruption before this last rename still rolls back safely. */
   if (backup && current == SD_OK) {
      char bak[CONFIGS_MAX_PATH_LEN];
      int n = snprintf(bak, sizeof(bak), "%s.bak", path);
      if (n <= 0 || n >= (int)sizeof(bak) || !remove_optional(bak) ||
          sd_rename(old, bak) != SD_OK) return CONFIGS_ERROR;
      return CONFIGS_OK;
   }
   /* Report cleanup failure: a remaining OLD will intentionally roll back. */
   return remove_optional(old) ? CONFIGS_OK : CONFIGS_ERROR;
}
int configs_storage_commit(const char *path) { return commit_file(path, 0); }
int configs_storage_commit_backup(const char *path) { return commit_file(path, 1); }
int configs_storage_write(const char *id, const char *path, const char *data, int len) {
   if (len < 0 || configs_storage_begin(id) != CONFIGS_OK) return CONFIGS_ERROR;
   char next[CONFIGS_MAX_PATH_LEN];
   int rc = configs_storage_prepare(path, next, sizeof(next), 0);
   if (rc == CONFIGS_OK) {
      sd_file *f = sd_open(next, SD_WRITE);
      rc = CONFIGS_ERROR;
      if (f) {
         int ok = sd_write(f, data, (unsigned)len) == SD_OK;
         if (sd_sync(f) != SD_OK) ok = 0;
         if (sd_close(f) != SD_OK) ok = 0;
         /* Exact byte verification, without changing config.txt's format. */
         char check[CONFIGS_MAX_FILE_LEN];
         if (ok && len < (int)sizeof(check) && sd_read_file(next, check, sizeof(check)) == len && !memcmp(data, check, (size_t)len))
            rc = configs_storage_commit(path);
      }
   }
   configs_storage_end();
   return rc;
}
