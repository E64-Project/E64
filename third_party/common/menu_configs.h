/*
 * menu_configs.h
 *
 * This file is part of VICE, the Versatile Commodore Emulator.
 * See README for copyright notice.
 */

#ifndef RASPI_MENU_CONFIGS_H
#define RASPI_MENU_CONFIGS_H

#include "ui.h"

// The on-screen menu for configs (docs/CONFIGS.md). The config logic is
// in src/configs; this file only builds and handles the menu items.

// Adds the current config folder to the top of the main menu.
void menu_configs_add_status_line(struct menu_item *root);
struct menu_item *menu_configs_get_status_item(void);

// Adds config actions inside the current config folder.
struct menu_item *build_configs_menu(struct menu_item *root);
// Add the current Autostart status and direct pick/clear actions to System.
void build_configs_autostart_items(struct menu_item *root);

// Adds the startup disk entries to the Drives menu.
void build_configs_drive_items(struct menu_item *drives);

// Labels "Save settings" with the running config.
void menu_configs_label_save_item(struct menu_item *item);

// A file was picked for the config's autostart (path includes the volume).
void menu_configs_autostart_chosen(const char *path);

struct machine_entry;

// Switch machine applied entry; the configs follow it.
void menu_configs_machine_switched(struct machine_entry *entry);

// Call before BMC64 restarts itself (not for a config or machine choice).
void menu_configs_before_reboot(void);

#ifdef __cplusplus
extern "C" {

#endif

// Called once, before the emulator reads its settings, with the machine
// that booted ("C64", "VIC20", "Plus4Emu", ...). Decides which config runs.
void menu_configs_boot(const char *machine);
void menu_configs_save_timing(unsigned long cycles, int ntsc);

// Switch to, or Start once (once != 0), Config id, as
// from Select config: switches machine first if needed, then restarts.
// Only returns if the config can't be started; the reason is shown on
// screen and kept for menu_configs_start_error(). Call on the emulator's
// main loop (emu_config_start_interrupt() queues it from elsewhere).
void menu_configs_start(const char *id, int once);

// Why the last menu_configs_start() failed, or "" (for the Web UI).
const char *menu_configs_start_error(void);
void menu_configs_clear_start_error(void);

// Called once the emulator is running: finishes start-up and shows any
// message about it.
void menu_configs_boot_complete(void);
void menu_configs_logical_action(const char *id, int legacy);
unsigned menu_configs_delete_begin(const char *id);
void menu_configs_delete_status(unsigned *serial, int *state, char *id, int id_size, char *error, int error_size);
void menu_configs_protection_action(const char *id, int on, int confirmed_off);

#ifdef __cplusplus
}

#endif


#endif
