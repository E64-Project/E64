#include "configs_internal.h"
#include "../sdcard/sd_fs.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// Config files on the SD card: /configs/active.txt, config.txt, the
// config list, and creating, renaming and deleting configs
// (docs/CONFIGS.md, Config files).

// Most configs listed; more are ignored.
#define CONFIGS_MAX_LISTED 256

void configs_path(const char *id, const char *file, char *out, int out_size) {
   snprintf(out, (size_t)out_size, "%s/%s/%s", CONFIGS_DIR, id, file);
}

// A machine name as used in file names: "plus4emu" for "Plus4Emu".
static void machine_file_part(const char *machine, char *out, int out_size) {
   int i = 0;
   for (; machine[i] && machine[i] != '/' && i < out_size - 1; i++) {
      char c = machine[i];
      out[i] = (c >= 'A' && c <= 'Z') ? c - 'A' + 'a' : c;
   }
   out[i] = '\0';
}

void configs_settings_path(const char *id, const char *machine, char *out,
                            int out_size) {
   char name[16];
   machine_file_part(machine, name, sizeof(name));
   snprintf(out, (size_t)out_size, "%s/%s/settings-%s.txt", CONFIGS_DIR, id,
            name);
}

// ---- Ids ----

// Reserve the retired directory so preserved settings can never be reused.
int configs_id_valid(const char *id) {
   if (configs_is_factory(id)) return 1;
   if (id == NULL || !strcmp(id, "main") || id[0] == '\0' || strlen(id) > CONFIGS_MAX_ID_LEN) {
      return 0;
   }
   for (const char *c = id; *c; c++) {
      if (!((*c >= 'a' && *c <= 'z') || (*c >= '0' && *c <= '9') ||
            *c == '-')) {
         return 0;
      }
   }
   return 1;
}

static int id_used(const char *id) {
   if (!configs_is_active(id) || configs_is_protected(id)) return 1;
   char path[CONFIGS_MAX_PATH_LEN];
   snprintf(path, sizeof(path), "%s/%s", CONFIGS_DIR, id);
   return sd_stat(path, NULL, NULL) != SD_NOT_FOUND;
}

int configs_make_id(const char *name, char *out, int out_size) {
   char base[CONFIGS_MAX_ID_LEN + 1];
   int length = 0;
   for (const char *c = name; *c && length < CONFIGS_MAX_ID_LEN; c++) {
      char ch = *c;
      if (ch >= 'A' && ch <= 'Z') ch = ch - 'A' + 'a';
      if ((ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9')) {
         base[length++] = ch;
      } else if (length > 0 && base[length - 1] != '-') {
         base[length++] = '-';
      }
   }
   while (length > 0 && base[length - 1] == '-') length--;
   base[length] = '\0';
   if (length == 0) {
      strcpy(base, "config");
   }

   for (int number = 1; number < 1000; number++) {
      char candidate[CONFIGS_MAX_ID_LEN + 1];
      if (number == 1) {
         snprintf(candidate, sizeof(candidate), "%s", base);
      } else {
         char suffix[8];
         int suffix_length = snprintf(suffix, sizeof(suffix), "-%d", number);
         int keep = (int)strlen(base);
         if (keep > CONFIGS_MAX_ID_LEN - suffix_length) {
            keep = CONFIGS_MAX_ID_LEN - suffix_length;
         }
         while (keep > 0 && base[keep - 1] == '-') keep--;
         snprintf(candidate, sizeof(candidate), "%.*s%s", keep, base, suffix);
      }
      if (!id_used(candidate)) {
         if ((int)strlen(candidate) >= out_size) return CONFIGS_ERROR;
         strcpy(out, candidate);
         return CONFIGS_OK;
      }
   }
   return CONFIGS_ERROR;
}

// ---- config.txt ----

static void config_key(void *ctx, const char *key, const char *value) {
   ConfigFile *pf = (ConfigFile *)ctx;
   if (strcmp(key, "name") == 0) {
      // Invalid metadata must never silently turn into a different name.
      if (strlen(value) > CONFIGS_MAX_NAME_LEN) pf->info.name[0] = '\0';
      else pkv_copy(pf->info.name, sizeof(pf->info.name), value);
   } else if (strcmp(key, "machine") == 0) {
      pkv_copy(pf->info.machine, sizeof(pf->info.machine), value);
   } else if (strcmp(key, "legacy_machine") == 0) {
      pkv_copy(pf->legacy_machine, sizeof(pf->legacy_machine), value);
   } else if (!strcmp(key, "timing_ntsc") || !strcmp(key, "timing_pal")) {
      unsigned long cycles = 0;
      int valid = *value != 0;
      for (const char *p = value; *p; p++) {
         if (*p < '0' || *p > '9' || cycles > 3000000) { valid = 0; break; }
         cycles = cycles * 10 + (*p - '0');
      }
      if (valid && configs_timing_valid(cycles)) {
         if (!strcmp(key, "timing_ntsc")) pf->timing_ntsc = cycles;
         else pf->timing_pal = cycles;
      }
   } else if (strcmp(key, "category") == 0) {
      pkv_copy(pf->info.category, sizeof(pf->info.category), value);
   } else if (strcmp(key, "description") == 0) {
      pkv_copy(pf->description, sizeof(pf->description), value);
   } else if (strcmp(key, "start") == 0) {
      pf->info.start =
          strcmp(value, "once") == 0 ? CONFIG_START_ONCE : CONFIG_START_SWITCH;
   } else if (strcmp(key, "autostart") == 0) {
      pkv_copy(pf->autostart, sizeof(pf->autostart), value);
   } else if (strncmp(key, "disk_", 5) == 0) {
      int drive = atoi(key + 5);
      char expected[16];
      snprintf(expected, sizeof(expected), "disk_%d", drive);
      if (strcmp(key, expected) == 0 && drive >= CONFIGS_FIRST_DRIVE &&
          drive < CONFIGS_FIRST_DRIVE + CONFIGS_NUM_DRIVES) {
         pkv_copy(pf->disks[drive - CONFIGS_FIRST_DRIVE],
                  sizeof(pf->disks[0]), value);
      }
   }
   // Other keys are ignored.
}

int config_file_parse(char *text, ConfigFile *pf) {
   memset(pf, 0, sizeof(*pf));
   pf->info.start = CONFIG_START_SWITCH;
   pkv_parse(text, config_key, pf);
   return (pf->info.name[0] && pf->info.machine[0]) ? CONFIGS_OK
                                                    : CONFIGS_ERROR;
}

int config_file_format(const ConfigFile *pf, char *buf, int size) {
   if (!memchr(pf->info.name, 0, sizeof(pf->info.name))) return CONFIGS_ERROR;
   int len = 0;
   buf[0] = '\0';
   int rc = pkv_append(buf, size, &len, "name", pf->info.name);
   rc |= pkv_append(buf, size, &len, "description", pf->description);
   rc |= pkv_append(buf, size, &len, "category", pf->info.category);
   rc |= pkv_append(buf, size, &len, "machine", pf->info.machine);
   rc |= pkv_append(buf, size, &len, "legacy_machine", pf->legacy_machine);
   if (pf->info.start == CONFIG_START_ONCE) {
      rc |= pkv_append(buf, size, &len, "start", "once");
   }
   for (int i = 0; i < CONFIGS_NUM_DRIVES; i++) {
      char key[16];
      snprintf(key, sizeof(key), "disk_%d", CONFIGS_FIRST_DRIVE + i);
      rc |= pkv_append(buf, size, &len, key, pf->disks[i]);
   }
   rc |= pkv_append(buf, size, &len, "autostart", pf->autostart);
   char timing[24];
   if (configs_timing_valid(pf->timing_ntsc)) {
      snprintf(timing, sizeof(timing), "%lu", pf->timing_ntsc);
      rc |= pkv_append(buf, size, &len, "timing_ntsc", timing);
   }
   if (configs_timing_valid(pf->timing_pal)) {
      snprintf(timing, sizeof(timing), "%lu", pf->timing_pal);
      rc |= pkv_append(buf, size, &len, "timing_pal", timing);
   }
   return rc == 0 ? len : CONFIGS_ERROR;
}

int config_file_read_raw(const char *id, ConfigFile *pf) {
   if (configs_is_factory(id)) {
      memset(pf, 0, sizeof(*pf));
      pf->info = *configs_factory_info(!strcmp(id, CONFIGS_FACTORY_PAL));
      return CONFIGS_OK;
   }
   char path[CONFIGS_MAX_PATH_LEN];
   char text[CONFIGS_MAX_FILE_LEN];
   if (!configs_id_valid(id)) {
      return CONFIGS_ERROR;
   }
   configs_path(id, "config.txt", path, sizeof(path));
   if (configs_storage_recover(id) != CONFIGS_OK ||
       sd_read_file(path, text, sizeof(text)) < 0 ||
       config_file_parse(text, pf) != CONFIGS_OK) {
      return CONFIGS_ERROR;
   }
   snprintf(pf->info.id, sizeof(pf->info.id), "%s", id);
   return CONFIGS_OK;
}

int config_file_read(const char *id, ConfigFile *pf) {
   return configs_is_active(id) ? config_file_read_raw(id, pf) : CONFIGS_ERROR;
}

int config_file_write(const char *id, const ConfigFile *pf) {
   if (configs_is_factory(id)) return CONFIGS_ERROR;
   if (!configs_is_active(id)) return CONFIGS_ERROR;
   char path[CONFIGS_MAX_PATH_LEN];
   char text[CONFIGS_MAX_FILE_LEN];
   int len = config_file_format(pf, text, sizeof(text));
   if (len < 0) {
      return CONFIGS_ERROR;
   }
   configs_path(id, "config.txt", path, sizeof(path));
   return configs_storage_write(id, path, text, len);
}

// ---- active.txt ----

static void active_key(void *ctx, const char *key, const char *value) {
   ActiveFile *af = (ActiveFile *)ctx;
   int is_config = strcmp(key, "config") == 0;
   if (!is_config && strcmp(key, "once") != 0) {
      return;
   }
   if (configs_id_valid(value)) {
      strcpy(is_config ? af->config : af->once, value);
   } else if (value[0] != '\0') {
      // A typo, a name instead of an id, upper case...
      pkv_copy(is_config ? af->bad_config : af->bad_once,
               sizeof(af->bad_config), value);
   }
}

void active_file_clear(ActiveFile *af) {
   memset(af, 0, sizeof(*af));
   strcpy(af->config, CONFIGS_FACTORY_NTSC);
}

void active_file_parse(char *text, ActiveFile *af) {
   active_file_clear(af);
   pkv_parse(text, active_key, af);
}

static unsigned selection_crc(const char *text, unsigned n) {
   unsigned crc=~0U;
   for(unsigned i=0;i<n;i++) {
      crc ^= (unsigned char)text[i];
      for(int b=0;b<8;b++) crc=(crc>>1)^(0xedb88320U & (0U-(crc&1)));
   }
   return ~crc;
}
static int selection_valid(char *text, int require_crc) {
   char *tag=strstr(text,"selection_crc=");
   if(!tag)return !require_crc;
   if(tag!=text && tag[-1]!='\n')return 0;
   unsigned stored=0;int consumed=0;
   if(sscanf(tag,"selection_crc=%8x\n%n",&stored,&consumed)!=1 ||
      consumed!=23 || tag[consumed])return 0;
   return selection_crc(text,(unsigned)(tag-text))==stored;
}
int active_file_read(ActiveFile *af) {
   char text[CONFIGS_MAX_FILE_LEN];
   if (sd_read_file(CONFIGS_ACTIVE_FILE, text, sizeof(text)) < 0) {
      // Only a complete, checksummed pending selection can recover a missing
      // final file. Never replace an existing unreadable/corrupt final file.
      if (sd_stat(CONFIGS_ACTIVE_FILE, NULL, NULL) != SD_NOT_FOUND ||
          sd_read_file(CONFIGS_DIR "/active.new", text, sizeof(text)) < 0 ||
          !selection_valid(text, 1)) {
         active_file_clear(af);
         return CONFIGS_ERROR;
      }
      if (sd_rename(CONFIGS_DIR "/active.new", CONFIGS_ACTIVE_FILE) != SD_OK) {
         active_file_clear(af);
         return CONFIGS_ERROR;
      }
   }
   if (!selection_valid(text, 0)) { active_file_clear(af); return CONFIGS_ERROR; }
   active_file_parse(text, af);
   return CONFIGS_OK;
}

int active_file_write(const ActiveFile *af) {
   char text[512];
   int len = 0;
   text[0] = '\0';
   if (pkv_append(text, sizeof(text), &len, "config", af->config) != 0 ||
       pkv_append(text, sizeof(text), &len, "once", af->once) != 0 ||
       sd_mkdir(CONFIGS_DIR) != 0) {
      return CONFIGS_ERROR;
   }
   unsigned checksum = selection_crc(text, (unsigned)len);
   len += snprintf(text + len, sizeof(text) - (size_t)len,
                   "selection_crc=%08x\n", checksum);
   // Write a new file, then swap it in, so a power cut never leaves a
   // half-written active.txt. A verified active.new recovers the rename gap.
   const char *temp = CONFIGS_DIR "/active.new";
   sd_file *pending = sd_open(temp, SD_WRITE);
   if (!pending) return CONFIGS_ERROR;
   int complete = sd_write(pending, text, (unsigned)len) == SD_OK;
   if (sd_sync(pending) != SD_OK) complete = 0;
   if (sd_close(pending) != SD_OK) complete = 0;
   if (!complete) return CONFIGS_ERROR;
   char check[512];
   if (sd_read_file(temp, check, sizeof(check)) != len || strcmp(check, text))
      return CONFIGS_ERROR;
   int remove_rc = sd_unlink(CONFIGS_ACTIVE_FILE);
   if (remove_rc != SD_OK && remove_rc != SD_NOT_FOUND) return CONFIGS_ERROR;
   return sd_rename(temp, CONFIGS_ACTIVE_FILE) == 0 ? CONFIGS_OK
                                                     : CONFIGS_ERROR;
}

// ---- The config list ----

static ConfigInfo *list;
static int list_count;

static int compare_names(const void *a, const void *b) {
   const char *x = ((const ConfigInfo *)a)->name;
   const char *y = ((const ConfigInfo *)b)->name;
   for (;; x++, y++) {
      int cx = (*x >= 'A' && *x <= 'Z') ? *x - 'A' + 'a' : *x;
      int cy = (*y >= 'A' && *y <= 'Z') ? *y - 'A' + 'a' : *y;
      if (cx != cy || cx == 0) return cx - cy;
   }
}

static int add_listed(void *ctx, const char *name, int is_dir) {
   int *capacity = (int *)ctx;
   ConfigFile pf;
   if (!is_dir || configs_is_factory(name) ||
       config_file_read(name, &pf) != CONFIGS_OK) {
      return 0;
   }
   if (list_count == *capacity) {
      if (*capacity >= CONFIGS_MAX_LISTED) return 1;
      int bigger = *capacity * 2;
      ConfigInfo *grown = realloc(list, sizeof(ConfigInfo) * (size_t)bigger);
      if (grown == NULL) return 1;
      list = grown;
      *capacity = bigger;
   }
   list[list_count++] = pf.info;
   return 0;
}

int configs_list_open(void) {
   configs_list_close();
   int capacity = 16;
   list = malloc(sizeof(ConfigInfo) * (size_t)capacity);
   if (list == NULL) {
      // Default remains available through list_at(), but report the failure.
      return CONFIGS_ERROR;
   }
   list[0] = *configs_factory_info(0);
   list_count = 1;
   int rc = sd_list(CONFIGS_DIR, add_listed, &capacity);
   if (rc != SD_OK && rc != SD_NOT_FOUND) {
      configs_list_close();
      return CONFIGS_ERROR;
   }
   // A missing /configs directory is a valid factory-only installation.
   qsort(list + 1, (size_t)(list_count - 1), sizeof(ConfigInfo),
         compare_names);
   return list_count;
}

const ConfigInfo *configs_list_at(int index) {
   if (list == NULL) {
      return index==0?configs_factory_info(0):NULL;
   }
   return index >= 0 && index < list_count ? &list[index] : NULL;
}

void configs_list_close(void) {
   free(list);
   list = NULL;
   list_count = 0;
}

// ---- Actions ----

// A valid Config that can be started. Whether it needs
// another machine is configs_machine_for()'s job.
static int check_startable(const char *id) {
   ConfigFile pf;
   return config_file_read(id, &pf);
}

int configs_switch_to(const char *id) {
   int rc = check_startable(id);
   if (rc != CONFIGS_OK) {
      return rc;
   }
   ActiveFile af;
   active_file_read(&af);
   strcpy(af.config, id);
   af.once[0] = '\0';
   return active_file_write(&af);
}

int configs_start_once(const char *id) {
   int rc = check_startable(id);
   if (rc != CONFIGS_OK) {
      return rc;
   }
   ActiveFile af;
   active_file_read(&af);
   strcpy(af.once, id);
   return active_file_write(&af);
}

static int clean_name(const char *name, char *out, int out_size) {
   if (!name) return CONFIGS_ERROR;
   while (*name == ' ') name++;
   size_t length = strlen(name);
   while (length && (name[length - 1] == ' ' || name[length - 1] == '\r' || name[length - 1] == '\n')) length--;
   if (!length || length > CONFIGS_MAX_NAME_LEN || length >= (size_t)out_size)
      return CONFIGS_ERROR;
   memcpy(out, name, length);
   out[length] = '\0';
   for (char *p = out; *p; ++p) if (*p == '\n' || *p == '\r') *p = ' ';
   while (length && out[length - 1] == ' ') out[--length] = '\0';
   return length ? CONFIGS_OK : CONFIGS_ERROR;
}

int configs_create(const char *name, char *id_out, int id_size) {
   if (!configs_management_ready() || !configs_protection_ready()) return CONFIGS_ERROR;
   ConfigFile pf;
   memset(&pf, 0, sizeof(pf));
   if (clean_name(name, pf.info.name, sizeof(pf.info.name)) != CONFIGS_OK) {
      return CONFIGS_ERROR;
   }
   // Same machine as the running Config.
   const ConfigInfo *running = configs_running();
   pkv_copy(pf.info.machine, sizeof(pf.info.machine),
            configs_running_is_factory() ? configs_booted() :
            running->machine[0] ? running->machine : configs_booted());
   if (pf.info.machine[0] == '\0') {
      return CONFIGS_ERROR;
   }

   char id[CONFIGS_MAX_ID_LEN + 1];
   char folder[CONFIGS_MAX_PATH_LEN];
   if (configs_make_id(pf.info.name, id, sizeof(id)) != CONFIGS_OK ||
       (int)strlen(id) >= id_size || sd_mkdir(CONFIGS_DIR) != 0) {
      return CONFIGS_ERROR;
   }
   snprintf(folder, sizeof(folder), "%s/%s", CONFIGS_DIR, id);
   if (sd_mkdir(folder) != 0) {
      return CONFIGS_ERROR;
   }
   if (config_file_write(id, &pf) != CONFIGS_OK) {
      sd_unlink(folder);
      return CONFIGS_ERROR;
   }
   strcpy(id_out, id);
   return CONFIGS_OK;
}

// Check display-name collisions without disturbing the native list snapshot.
// Directory iteration owns/closes its own filesystem handle through sd_list().
typedef struct {
   const char *id;
   ConfigInfo proposed;
   int conflict;
} RenameCheck;
static int rename_name_used(void *ctx, const char *id, int is_dir) {
   RenameCheck *check = ctx;
   if (!is_dir || !strcmp(id, check->id) || !configs_id_valid(id) ||
       configs_is_factory(id) || !configs_is_active(id)) return 0;
   char path[CONFIGS_MAX_PATH_LEN];sd_info info;
   configs_path(id, "config.txt", path, sizeof(path));
   int rc = sd_stat_info(path, &info);
   if (rc == SD_NOT_FOUND) return 0; // Unrelated/orphan folders aren't Configs.
   ConfigFile other;
   if (rc != SD_OK || info.is_dir || config_file_read(id, &other) != CONFIGS_OK ||
       compare_names(&check->proposed, &other.info) == 0) {
      check->conflict = 1; // Fail closed if another Config cannot be checked.
      return 1;
   }
   return 0;
}

int configs_rename(const char *id, const char *name) {
   ConfigFile pf;
   char clean[CONFIGS_MAX_NAME_LEN + 1];
   if (!configs_id_valid(id) || configs_is_factory(id) ||
       clean_name(name, clean, sizeof(clean)) != CONFIGS_OK ||
       config_file_read(id, &pf) != CONFIGS_OK) {
      return CONFIGS_ERROR;
   }
   if (!strcmp(pf.info.name, clean)) {
      if (!strcmp(id, configs_running()->id)) configs_running_renamed(clean);
      return CONFIGS_OK;
   }
   RenameCheck check;
   memset(&check, 0, sizeof(check));check.id = id;
   snprintf(check.proposed.name, sizeof(check.proposed.name), "%s", clean);
   if (compare_names(&check.proposed, configs_factory_info(0)) == 0 ||
       sd_list(CONFIGS_DIR, rename_name_used, &check) != SD_OK || check.conflict)
      return CONFIGS_ERROR;
   strcpy(pf.info.name, clean);
   if (config_file_write(id, &pf) != CONFIGS_OK) {
      return CONFIGS_ERROR;
   }
   if (!strcmp(id, configs_running()->id)) configs_running_renamed(clean);
   return CONFIGS_OK;
}


int configs_rename_running(const char *name) {
   return configs_rename(configs_running()->id, name);
}
