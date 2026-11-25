/*
 * menu_power.c
 *
 * This file is part of VICE, the Versatile Commodore Emulator.
 * See README for copyright notice.
 */

#include "menu_power.h"
#include <string.h>

// RASPI includes
#include "circle.h"
#include "emux_api.h"
#include "menu.h"
#include "menu_configs.h"
#include "ui.h"

// How long the shutdown message stays up before the display goes off.

// Detaching makes the emulator close each image file, which writes out
// anything it still has buffered; a plain restart can lose the last writes
// to a disk image.
static void write_out_images(void) {
  for (int unit = 8; unit <= 11; unit++) {
    emux_detach_disk(unit);
  }
  emux_detach_tape();
}

void menu_power_reboot(void) {
  write_out_images();
  menu_configs_before_reboot();
  circle_reboot();
}

void menu_power_off(void) {
  write_out_images();
  // No menu_configs_before_reboot(): the next start is a power-on, so a
  // Start-once config should not start again.
  circle_power_off();
}

static void reboot_chosen(struct menu_item *item) {
  (void)item;
  menu_power_reboot();
}

static void power_off_chosen(struct menu_item *item) {
  (void)item;
  menu_power_off();
}

// Cancel uses the menu's usual MENU_CONFIRM_CANCEL handling (pop).
static void confirm(const char *title, int id, const char *action,
                    void (*chosen)(struct menu_item *)) {
  // Use the longest option across both dialogs, with two cells on each side.
  int width = (int)strlen("Shutdown Now") + 4;
  struct menu_item *root = ui_push_menu(width, 6);
  strcpy(root->name, "E64 Power Confirm");
  ui_menu_add_read_only_heading(root, title);
  ui_menu_add_divider(root);
  ui_menu_add_button(id, root, action)->on_value_changed = chosen;
  ui_menu_add_button(MENU_CONFIRM_CANCEL, root, "Cancel");
  ui_select_first_interactive_item();
}

static void reboot_selected(struct menu_item *item) {
  (void)item;
  confirm("REBOOT", MENU_POWER_REBOOT, "Reboot Now", reboot_chosen);
}

static void power_off_selected(struct menu_item *item) {
  (void)item;
  confirm("SHUTDOWN", MENU_POWER_OFF, "Shutdown Now",
          power_off_chosen);
}

void build_power_menu(struct menu_item *root) {
  struct menu_item *parent = ui_menu_add_folder(root, "Power");
  ui_menu_add_button(MENU_POWER_REBOOT, parent, "Reboot")
      ->on_value_changed = reboot_selected;
  ui_menu_add_button(MENU_POWER_OFF, parent, "Shutdown")
      ->on_value_changed = power_off_selected;
  ui_menu_add_button(MENU_SOFT_RESET, parent, "Immediate Soft Reset");
  ui_menu_add_button(MENU_HARD_RESET, parent, "Immediate Hard Reset");
}
