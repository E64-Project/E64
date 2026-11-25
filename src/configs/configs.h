#ifndef BMC64_CONFIGS_H
#define BMC64_CONFIGS_H

// Configs: complete, saved setups of BMC64 that can be switched to from the
// menu. How they work for users, and the file formats, are in
// docs/CONFIGS.md.
//
// This is the core logic only (config files, start-up, machines). It
// doesn't depend on Circle or VICE, so it can be tested on the PC
// (tools/configs_test). File access goes through src/sdcard/sd_fs.h. The
// on-screen menu is in third_party/common/menu_configs.c.
//
// Logical-deletion metadata is checked at startup. Only pending countdowns
// write at a qualifying startup; config configuration files are untouched.

#ifdef __cplusplus
extern "C" {
#endif

#define CONFIGS_DIR "/configs"
#define CONFIGS_FACTORY_NTSC "_factory-ntsc"
#define CONFIGS_FACTORY_PAL "_factory-pal"

#define CONFIGS_MAX_ID_LEN 32
#define CONFIGS_MAX_NAME_LEN 32
#define CONFIGS_MAX_CATEGORY_LEN 32
#define CONFIGS_MAX_DESCRIPTION_LEN 64
#define CONFIGS_MAX_MACHINE_LEN 128
#define CONFIGS_MAX_PATH_LEN 256

// Startup disks are for drives 8 to 11.
#define CONFIGS_FIRST_DRIVE 8
#define CONFIGS_NUM_DRIVES 4

typedef enum {
   CONFIGS_OK = 0,
   CONFIGS_ERROR = -1,
   CONFIGS_NOT_IMPLEMENTED = -2,
} ConfigsResult;

// Which choice the config list offers first ("start" in config.txt).
typedef enum {
   CONFIG_START_SWITCH = 0,
   CONFIG_START_ONCE,
} ConfigStart;

typedef struct {
   char id[CONFIGS_MAX_ID_LEN + 1];
   char name[CONFIGS_MAX_NAME_LEN + 1];
   char category[CONFIGS_MAX_CATEGORY_LEN + 1];
   // A machines.txt section header, e.g. "C64/PAL/HDMI/VICE 720p@50Hz", or
   // the start of one, e.g. "C64/PAL/HDMI" or "C64"; missing parts match
   // anything.
   char machine[CONFIGS_MAX_MACHINE_LEN + 1];
   ConfigStart start;
} ConfigInfo;

// Firmware IDs use an underscore, outside the historical user-ID alphabet.
int configs_is_factory(const char *id);
int configs_running_is_factory(void);
const ConfigInfo *configs_factory_info(int index);
const char *configs_factory_settings(void);
int configs_factory_resources(int (*set_int)(const char *, int),
                              int (*set_string)(const char *, const char *));
/* Early GPIO recovery: only 1 requests NTSC; all other values mean normal boot. */
void configs_recovery_choice(int choice);
// Failed factory lookup: select NTSC, retaining usable current video.
void configs_factory_machine_failed(void);

// ---- Start-up (config_boot.c) ----

// Called once, before the emulator reads its settings. booted describes what
// booted in machines.txt terms: the machine ("C64", "C128", "VIC20",
// "Plus4", "Plus4Emu", "Pet"), then the video standard and output, e.g.
// "C64/PAL/HDMI". Decides which config runs; any problem (including a
// config for another machine) falls back to Default NTSC with a message
// (configs_boot_message).
void configs_boot_init(const char *booted);

// Called once the emulator is running ("boot complete"). Does the work that
// mustn't slow boot down: removes a used Start-once entry.
void configs_after_boot(void);

// After a Start-once config on another machine: the power-on config's
// machine, which the caller applies so the next power-on is back on it.
// Otherwise "".
const char *configs_return_machine(void);

// A message for the user about how start-up went, or "".
const char *configs_boot_message(void);

// Call before BMC64 restarts itself (e.g. a settings change that needs a
// restart), so a Start-once config starts again.
void configs_before_reboot(void);

// ---- The running config (config_boot.c) ----

const ConfigInfo *configs_running(void);

// 1 if configs are in use: /configs/active.txt was there at start-up.
// Known from start-up, so it costs nothing to ask.
int configs_in_use(void);

// The user Config VICE settings path, or NULL for firmware factory defaults.
const char *configs_vice_config(void);

// User Config native settings path; factory settings come from firmware.
const char *configs_settings_file(void);

// Where a new config's BMC64 settings go, for the machine running now.
void configs_new_settings_file(const char *id, char *out, int out_size);

// The path of a file in a config's folder, e.g. ("geos", "vice.ini").
void configs_path(const char *id, const char *file, char *out, int out_size);

// ---- The config list (config_store.c) ----
// Only read when the menu asks for it, and freed again afterwards, so it
// costs nothing at boot. Default comes first; users are sorted by name.
// Configs for every machine are listed. list_open returns the Config count,
// or CONFIGS_ERROR for allocation/filesystem failure. A missing /configs
// directory is a normal factory-only list. Always close when finished;
// Default remains readable via list_at(0) even after a listing failure.

int configs_list_open(void);
const ConfigInfo *configs_list_at(int index);
void configs_list_close(void);

// Independent video calibrations, in machine cycles per second.
int configs_timing_valid(unsigned long cycles);
void configs_timing_apply_failed(void);
int configs_save_timing(const char *id, int ntsc, unsigned long cycles);
unsigned long configs_running_timing(int ntsc);

// ---- Config actions (config_store.c) ----

// The machine a config needs if it isn't what booted, or "".
// The caller applies a matching machines.txt
// entry before Switch to / Start once.
const char *configs_machine_for(const char *id);

// Switch to and Start once only update /configs/active.txt; the caller then
// restarts BMC64.
int configs_switch_to(const char *id);
int configs_start_once(const char *id);

// Creates a config for the running machine with only its config.txt and
// returns its id. The caller then saves the settings into it.
int configs_create(const char *name, char *id_out, int id_size);

int configs_rename(const char *id, const char *name);
int configs_rename_running(const char *name);
void configs_protection_init(const char *system_volume);
int configs_protection_ready(void);
int configs_is_protected(const char *id);
int configs_protection_status(const char *id);
int configs_set_protected(const char *id, int on, int confirmed_off);
const char *configs_protection_error(void);
int configs_protection_read_begin(void);
void configs_protection_read_end(void);
unsigned configs_protected_count(void);
const char *configs_protected_id(unsigned index);
int configs_protection_can_write(const char *path);
int configs_protection_can_remove(const char *path);
int configs_protection_external_allowed(const char *path, int writing);
int configs_delete(const char *id); // Permanent; caller supplies two confirmations.
int configs_purge_legacy(const char *id);
const char *configs_deleted_name(unsigned index);
int configs_restore(const char *id);
int configs_is_active(const char *id);
int configs_deleted_count(void);
const char *configs_deleted_id(unsigned index);
int configs_deleted_remaining(const char *id);
const char *configs_management_error(void);
int configs_management_ready(void);
void configs_logical_init(void);
void configs_set_system_volume(const char *volume);
void configs_startup_failed(void);
void configs_successful_startup(void);
int configs_path_allowed(const char *path);
int configs_path_belongs(const char *path, const char *id);
int configs_path_is_managed(const char *path);
void configs_set_runtime_guard(int (*guard)(const char *id));
int configs_path_acquire(const char *path);
void configs_path_release(int lease);
int configs_web_begin(void);
void configs_web_end(void);

// ---- Startup disks and autostart of the running config (config_boot.c) ----
// Saved to the config straight away; nothing else is saved with them.

// The autostart file or snapshot, or "" when there is none.
const char *configs_autostart(void);
int configs_set_autostart(const char *path);
int configs_clear_autostart(void);

// The disk image for drive CONFIGS_FIRST_DRIVE + drive at start-up, with
// its volume (e.g. "SD:/disks/geos.d64"), or "".
const char *configs_startup_disk(int drive);

// paths[0] is drive 8; empty or NULL entries mean no disk.
int configs_set_startup_disks(const char *const paths[CONFIGS_NUM_DRIVES]);
int configs_clear_startup_disks(void);

// ---- Machines (config_machine.c, config_boot.c) ----

// What booted, as passed to configs_boot_init(), e.g. "C64/PAL/HDMI".
const char *configs_booted(void);

// "Switch machine" applied entry (its machines.txt header). The power-on
// config follows it, also to another machine (its settings for each
// machine are kept apart). Factories never change.
void configs_machine_switched(const char *entry);

// Short machine name for menus from a machine value,
// e.g. "VIC20/PAL/HDMI/..." gives "VIC-20". Empty for an empty value.
void configs_machine_label(const char *machine, char *out, int out_size);

// 1 if two machine values don't contradict each other: every part that both
// have is the same ("C64" and "C64/PAL/HDMI" match; "C64/NTSC" and
// "C64/PAL/HDMI" don't). Case and spaces around parts don't matter.
int configs_machine_matches(const char *machine, const char *other);

// 1 if a machines.txt header has every part of a machine value
// ("C64/PAL" covers "C64/PAL/HDMI/VICE 720p@50Hz").
int configs_machine_covers(const char *machine, const char *header);

/* Internal native-save storage protocol. Hold begin/end across prepare,
 * the checked stdio writer, and commit. Only writable user Config files are accepted. */
int configs_storage_begin(const char *id);
void configs_storage_end(void);
int configs_storage_prepare(const char *path, char *next, int size, int copy);
int configs_storage_commit(const char *path);
int configs_storage_commit_backup(const char *path);
int configs_storage_recover(const char *id);
int configs_storage_recover_all(void);
int configs_storage_write(const char *id, const char *path, const char *data, int len);

#ifdef __cplusplus
}
#endif

#endif
