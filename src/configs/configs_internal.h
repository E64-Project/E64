#ifndef BMC64_CONFIGS_INTERNAL_H
#define BMC64_CONFIGS_INTERNAL_H

// Shared between the files in src/configs and their tests only.

#include "configs.h"

#define CONFIGS_ACTIVE_FILE CONFIGS_DIR "/active.txt"

// Config files are small; this is the most that is read of one.
#define CONFIGS_MAX_FILE_LEN 2048

// ---- key=value files (config_kv.c) ----

typedef void (*pkv_cb)(void *ctx, const char *key, const char *value);

// Calls cb for each key=value line. Changes text.
void pkv_parse(char *text, pkv_cb cb, void *ctx);

// Appends "key=value\n" to buf (holding *len bytes). Nothing is written for
// an empty value. Returns -1 if it doesn't fit.
int pkv_append(char *buf, int size, int *len, const char *key,
               const char *value);

// Copies a value, cut to fit and kept on one line.
void pkv_copy(char *out, int out_size, const char *value);

// ---- config.txt (config_store.c) ----

typedef struct {
   ConfigInfo info;
   unsigned long timing_ntsc;
   unsigned long timing_pal;
   // Explicit machine switches tag legacy settings without renaming the file.
   char legacy_machine[CONFIGS_MAX_MACHINE_LEN + 1];
   char description[CONFIGS_MAX_DESCRIPTION_LEN + 1];
   char disks[CONFIGS_NUM_DRIVES][CONFIGS_MAX_PATH_LEN + 1];
   char autostart[CONFIGS_MAX_PATH_LEN + 1];
} ConfigFile;

// Fills pf from config.txt text (changes text). Returns 0 if the config is
// valid: it has a name and a machine.
int config_file_parse(char *text, ConfigFile *pf);

// Writes pf as config.txt text. Returns the length, or -1 if it won't fit.
int config_file_format(const ConfigFile *pf, char *buf, int size);

int config_file_read(const char *id, ConfigFile *pf);
int config_file_read_raw(const char *id, ConfigFile *pf);
int config_file_write(const char *id, const ConfigFile *pf);

// ---- active.txt (config_store.c) ----

typedef struct {
   char config[CONFIGS_MAX_ID_LEN + 1];
   char once[CONFIGS_MAX_ID_LEN + 1];
   // Values that aren't config ids (e.g. a typo), cut to fit; "" if none.
   char bad_config[CONFIGS_MAX_ID_LEN + 1];
   char bad_once[CONFIGS_MAX_ID_LEN + 1];
} ActiveFile;

// Empties af: Default NTSC, nothing else set.
void active_file_clear(ActiveFile *af);

// Fills af from active.txt text (changes text). Missing or invalid ids
// become "_factory-ntsc" (config) and "" (once); invalid ones are also kept in
// bad_config / bad_once so start-up can say so.
void active_file_parse(char *text, ActiveFile *af);

// Returns -1, with af set to Default NTSC, if there is no active.txt.
int active_file_read(ActiveFile *af);
int active_file_write(const ActiveFile *af);

// ---- Settings files (config_store.c) ----

// A config's BMC64 settings for a machine:
// /configs/<id>/settings-<machine>.txt, e.g. settings-plus4.txt.
void configs_settings_path(const char *id, const char *machine, char *out,
                            int out_size);

// ---- Ids (config_store.c) ----

// 1 for a valid config id: 1 to 32 lowercase letters, digits and '-'.
int configs_id_valid(const char *id);

// Makes an unused id from a name (docs/CONFIGS.md, Config files).
int configs_make_id(const char *name, char *out, int out_size);

// ---- Machines (config_machine.c) ----

// The machine, standard and output of a machine value, e.g. "C64/PAL/HDMI"
// from "C64/PAL/HDMI/VICE 720p@50Hz".
void configs_machine_desc(const char *machine, char *out, int out_size);

// The machine part, e.g. "C64" from "C64/PAL/HDMI".
void configs_machine_name(const char *machine, char *out, int out_size);

// ---- State (config_store.c / config_boot.c) ----


// The booted machine's name, e.g. "C64" from "C64/PAL/HDMI".
const char *configs_booted_machine(void);

// Updates the running config's name after a rename.
void configs_running_renamed(const char *name);

#endif
