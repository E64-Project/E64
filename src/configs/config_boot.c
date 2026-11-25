#include "configs_internal.h"

#include "../sdcard/sd_fs.h"

#include <stdio.h>
#include <string.h>

// Start-up: which config runs, the machine to go back to, and the startup
// disks and autostart (docs/CONFIGS.md, Switch to, or Start once; Configs
// and machines; Auto-attach disks; Autostart).

// What booted ("C64/PAL/HDMI") and its machine name ("C64").
static char booted_desc[64];
static char booted_machine[16];
static ConfigFile running;
// active.txt was there at start-up.
static int in_use;
// Started with Start once.
static int running_once;
// The Start-once entry still has to be removed from active.txt.
static int once_to_remove;
// The power-on config's machine, after a Start-once config on another one.
static char return_machine[CONFIGS_MAX_MACHINE_LEN + 1];
// The running config's settings are still in an older config's
// settings.txt; startup reads it without changing its name or bytes.
static int settings_legacy;
static char boot_message[128];
// Kept for as long as the emulator runs: VICE holds on to the vice.ini path.
static char vice_config_path[CONFIGS_MAX_PATH_LEN];
static char settings_path[CONFIGS_MAX_PATH_LEN];
static int recovery_choice;
void configs_recovery_choice(int choice) { recovery_choice = choice == 1 ? 1 : 0; }

static void start_default(void) {
   memset(&running, 0, sizeof(running));
   running.info = *configs_factory_info(0);
}

static void machine_of(const char *id, char *out, int out_size) {
   ConfigFile pf;
   out[0] = '\0';
   if (config_file_read(id, &pf) == CONFIGS_OK)
      pkv_copy(out, out_size, pf.info.machine);
}

// Picks the config active.txt asks for, or Default NTSC with a message.
static void start_from_active(const ActiveFile *a) {
   const char *id = a->config;
   if (a->bad_config[0] || a->bad_once[0]) configs_startup_failed();
   if (a->once[0]) {
      id = a->once;
      running_once = 1;
      once_to_remove = 1;
   } else if (a->bad_once[0]) {
      // A typo in once=: ignored, the usual config starts.
      snprintf(boot_message, sizeof(boot_message),
               "once=%s in active.txt\nisn't a config id.\nIgnored it.",
               a->bad_once);
   }
   if (!a->once[0] && a->bad_config[0]) {
      // A typo in config=: Default NTSC starts.
      snprintf(boot_message, sizeof(boot_message),
               "config=%s in active.txt\nisn't a config id.\n"
               "Started Default NTSC instead.", a->bad_config);
   }

   ConfigFile pf;
   if (config_file_read(id, &pf) != CONFIGS_OK) {
      configs_startup_failed();
      snprintf(boot_message, sizeof(boot_message),
               "Can't read config\n%s\nStarted " "Default NTSC" " instead.", id);
      return;
   }
   if (!configs_is_factory(id) && !configs_machine_matches(pf.info.machine, booted_desc)) {
      configs_startup_failed();
      snprintf(boot_message, sizeof(boot_message),
               "Config %s\nis for another machine.\nStarted " "Default NTSC" " instead.",
               pf.info.name);
      return;
   }
   running = pf;
}

void configs_boot_init(const char *booted) {
   configs_logical_init();
   snprintf(booted_desc, sizeof(booted_desc), "%s", booted ? booted : "");
   configs_machine_name(booted_desc, booted_machine, sizeof(booted_machine));
   start_default();
   return_machine[0] = '\0';
   running_once = 0;
   once_to_remove = 0;
   settings_legacy = 0;
   in_use = 0;
   boot_message[0] = '\0';
   /* Recover even unselected Configs before either UI can enumerate them. */
   if (configs_storage_recover_all() != CONFIGS_OK) {
      configs_startup_failed();
      snprintf(boot_message, sizeof(boot_message), "Config storage needs recovery.\nDeletion countdown paused.");
   }
   if (!configs_management_ready()) {
      configs_startup_failed();
      snprintf(boot_message, sizeof(boot_message), "Deletion records need recovery.\nUser Config changes are suspended.");
   }

   // Read the independent boot-selection journal after user-file recovery.
   ActiveFile af;
   if (recovery_choice) {
      active_file_clear(&af);
      strcpy(af.config, configs_factory_info(0)->id);
      recovery_choice = 0;
      if (active_file_write(&af) != CONFIGS_OK) {
         configs_startup_failed();
         snprintf(boot_message, sizeof(boot_message), "Factory recovery selected.\nCannot persist selection: storage error.");
      }
   } else if (active_file_read(&af) != CONFIGS_OK) {
      configs_startup_failed();
      if (configs_deleted_count()) snprintf(boot_message, sizeof(boot_message), "Cannot read boot selection.\nDeletion countdown paused.");
      return;
   }
   in_use = 1;
   start_from_active(&af);
   if (!configs_running_is_factory()) {
      // An older config keeps its settings in settings.txt, which is always
      // for the machine it originally ran on (tagged on explicit switches).
      char own[CONFIGS_MAX_PATH_LEN];
      char legacy[CONFIGS_MAX_PATH_LEN];
      configs_settings_path(running.info.id, booted_machine, own, sizeof(own));
      configs_path(running.info.id, "settings.txt", legacy, sizeof(legacy));
      settings_legacy = sd_stat(own, NULL, NULL) == SD_NOT_FOUND &&
                        sd_stat(legacy, NULL, NULL) == SD_OK &&
                        (!running.legacy_machine[0] ||
                         configs_machine_matches(running.legacy_machine, booted_desc));
   }
   // Start once on another machine: the next power-on goes back to the
   // power-on config's machine.
   if (running_once) {
      machine_of(af.config, return_machine,
                 sizeof(return_machine));
      if (return_machine[0] == '\0' ||
          configs_machine_matches(return_machine, booted_desc)) {
         return_machine[0] = '\0';
      }
   }
}

const char *configs_return_machine(void) {
   return return_machine;
}

void configs_after_boot(void) {
   // Legacy settings remain in place; startup never renames user files.
   if (!configs_management_ready() || !once_to_remove) return;
   once_to_remove = 0;
   ActiveFile af;
   if (active_file_read(&af) == CONFIGS_OK) {
      af.once[0] = '\0';
      active_file_write(&af);
   }
}

const char *configs_boot_message(void) {
   return boot_message;
}

void configs_before_reboot(void) {
   if (!running_once) {
      return;
   }
   ActiveFile af;
   active_file_read(&af);
   strcpy(af.once, running.info.id);
   active_file_write(&af);
}

void configs_factory_machine_failed(void) {
   if (!configs_running_is_factory()) return;
   ActiveFile af;
   active_file_clear(&af);
   // Persistence failure must never prevent this boot from continuing.
   int saved = active_file_write(&af) == CONFIGS_OK;
   start_default();
   running_once = once_to_remove = 0;
   return_machine[0] = '\0';
   settings_legacy = 0;
   configs_startup_failed();
   snprintf(boot_message, sizeof(boot_message),
            "Factory timing unavailable.\nDefault NTSC on current video.\n%s",
            saved ? "Check system/machines.txt." : "Cannot persist selection; check storage.");
}

const char *configs_booted(void) {
   return booted_desc;
}

const char *configs_booted_machine(void) {
   return booted_machine;
}

const char *configs_machine_for(const char *id) {
   static char machine[CONFIGS_MAX_MACHINE_LEN + 1];
   if (id == NULL) {
      return "";
   }
   machine_of(id, machine, sizeof(machine));
   if (machine[0] == '\0' || configs_machine_matches(machine, booted_desc)) {
      return "";
   }
   return machine;
}

void configs_machine_switched(const char *entry) {
   if (configs_running_is_factory()) {
      ActiveFile factory_selection;
      if(active_file_read(&factory_selection)!=CONFIGS_OK)return;
      if(configs_is_factory(factory_selection.config)) {
         char desc[CONFIGS_MAX_MACHINE_LEN+1];configs_machine_desc(entry,desc,sizeof(desc));
         const char *standard=strchr(desc,'/');
         if(standard && (!strncmp(standard+1,"PAL/",4)||!strcmp(standard+1,"PAL")))
            strcpy(factory_selection.config,CONFIGS_FACTORY_PAL);
         else strcpy(factory_selection.config,CONFIGS_FACTORY_NTSC);
         factory_selection.once[0]=0;active_file_write(&factory_selection);
      }
      return;
   }
   ActiveFile af;
   if (active_file_read(&af) != CONFIGS_OK) {
      return;
   }
   if (!configs_is_factory(af.config)) {
      ConfigFile pf;
      if (config_file_read(af.config, &pf) == CONFIGS_OK) {
         // The config follows, also to another machine: each machine has
         // its own settings file in it, so the old machine's are kept. An
         // older config's settings.txt is for its old machine.
         char legacy[CONFIGS_MAX_PATH_LEN];
         configs_path(af.config, "settings.txt", legacy, sizeof(legacy));
         if (!pf.legacy_machine[0] && sd_stat(legacy, NULL, NULL) == SD_OK) {
            pkv_copy(pf.legacy_machine, sizeof(pf.legacy_machine), pf.info.machine);
         }
         configs_machine_desc(entry, pf.info.machine,
                               sizeof(pf.info.machine));
         config_file_write(af.config, &pf);
      } else {
         strcpy(af.config, CONFIGS_FACTORY_NTSC);
      }
   }
   af.once[0] = '\0';
   active_file_write(&af);
}

const ConfigInfo *configs_running(void) {
   return &running.info;
}

int configs_in_use(void) {
   return in_use;
}

void configs_running_renamed(const char *name) {
   pkv_copy(running.info.name, sizeof(running.info.name), name);
}

const char *configs_vice_config(void) {
   if (configs_running_is_factory()) return NULL;
   configs_path(running.info.id, "vice.ini", vice_config_path,
                 sizeof(vice_config_path));
   return vice_config_path;
}

const char *configs_settings_file(void) {
   if (settings_legacy) {
      configs_path(running.info.id, "settings.txt", settings_path,
                    sizeof(settings_path));
   } else {
      configs_settings_path(running.info.id, booted_machine, settings_path,
                             sizeof(settings_path));
   }
   return settings_path;
}

void configs_new_settings_file(const char *id, char *out, int out_size) {
   configs_settings_path(id, booted_machine, out, out_size);
}

const char *configs_autostart(void) {
   return running.autostart;
}

// The running config's startup actions as they'll be saved.
typedef struct {
   const char *autostart;  // NULL: unchanged
   const char *disks[CONFIGS_NUM_DRIVES];
   int set_disks;
} StartupChange;

static int change_fits(const StartupChange *c) {
   if (c->autostart && strlen(c->autostart) >= sizeof(running.autostart)) {
      return 0;
   }
   for (int i = 0; c->set_disks && i < CONFIGS_NUM_DRIVES; i++) {
      if (c->disks[i] && strlen(c->disks[i]) >= sizeof(running.disks[i])) {
         return 0;
      }
   }
   return 1;
}

static void apply_change(ConfigFile *pf, const StartupChange *c) {
   if (c->autostart) {
      pkv_copy(pf->autostart, sizeof(pf->autostart), c->autostart);
   }
   for (int i = 0; c->set_disks && i < CONFIGS_NUM_DRIVES; i++) {
      pkv_copy(pf->disks[i], sizeof(pf->disks[i]),
               c->disks[i] ? c->disks[i] : "");
   }
}

// Saves the running config's autostart and/or startup disks straight away.
static int save_startup(const StartupChange *c) {
   if (configs_running_is_factory()) return CONFIGS_ERROR;
   if (!change_fits(c)) {
      return CONFIGS_ERROR;
   }
   // Re-read the file so changes made since start-up (a rename) are kept.
   ConfigFile pf;
   if (config_file_read(running.info.id, &pf) != CONFIGS_OK) {
      return CONFIGS_ERROR;
   }
   apply_change(&pf, c);
   if (config_file_write(running.info.id, &pf) != CONFIGS_OK) {
      return CONFIGS_ERROR;
   }
   apply_change(&running, c);
   return CONFIGS_OK;
}

int configs_set_autostart(const char *path) {
   if (path == NULL || path[0] == '\0') {
      return CONFIGS_ERROR;
   }
   StartupChange c = {path, {NULL}, 0};
   return save_startup(&c);
}

int configs_clear_autostart(void) {
   StartupChange c = {"", {NULL}, 0};
   return save_startup(&c);
}

const char *configs_startup_disk(int drive) {
   if (drive < 0 || drive >= CONFIGS_NUM_DRIVES) {
      return "";
   }
   return running.disks[drive];
}

int configs_set_startup_disks(const char *const paths[CONFIGS_NUM_DRIVES]) {
   StartupChange c = {NULL, {NULL}, 1};
   for (int i = 0; paths && i < CONFIGS_NUM_DRIVES; i++) {
      c.disks[i] = paths[i];
   }
   return save_startup(&c);
}

int configs_clear_startup_disks(void) {
   StartupChange c = {NULL, {NULL}, 1};
   return save_startup(&c);
}

// Covers the cycle rates of every supported machine; FPS and the running
// video standard are additionally validated by the calibration UI.
int configs_timing_valid(unsigned long cycles) {
   return cycles >= 500000 && cycles <= 2500000;
}
unsigned long configs_running_timing(int ntsc) {
   if (configs_running_is_factory()) return 0;
   return ntsc ? running.timing_ntsc : running.timing_pal;
}
int configs_save_timing(const char *id, int ntsc, unsigned long cycles) {
   ConfigFile pf;
   if ((ntsc != 0 && ntsc != 1) || !configs_timing_valid(cycles) ||
       configs_is_factory(id) || configs_is_protected(id) ||
       config_file_read(id, &pf) != CONFIGS_OK) return CONFIGS_ERROR;
   if (ntsc) pf.timing_ntsc = cycles;
   else pf.timing_pal = cycles;
   return config_file_write(id, &pf);
}

void configs_timing_apply_failed(void) {
   configs_startup_failed();
   snprintf(boot_message, sizeof(boot_message),
            "Saved video timing not applied.\nCannot update cmdline.txt.");
}
