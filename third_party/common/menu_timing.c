/*
 * menu_timing.c
 *
 * Written by
 *  Randy Rossi <randy.rossi@gmail.com>
 *
 * This file is part of VICE, the Versatile Commodore Emulator.
 * See README for copyright notice.
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
 *  02111-1307  USA.
 *
 */

#include "menu_timing.h"

#include <dirent.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// RASPI includes
#include "circle.h"
#include "emux_api.h"
#include "menu.h"
#include "menu_configs.h"
#include "../../src/configs/configs.h"
#include "ui.h"

static struct menu_item *g_countdown_item;
static struct menu_item *timing_page;
static struct menu_item *start_item;

static int hdmi_timing_active;
static unsigned long measured_cycles;
static int measured_ntsc;
static void save_timing(struct menu_item *item) {
  (void)item;
  menu_configs_save_timing(measured_cycles, measured_ntsc);
}

// How many ticks we counted for hdmi timing
static unsigned int hdmi_timing_count;

// When we started counting for hdmi timing
static unsigned long hdmi_timing_start;

// Start time for updating the countdown every second
static unsigned long hdmi_timing_countdown_start;

#define TEST_DURATION 600000000

#define NUM_TIMING_LINES 17
static char instructions[NUM_TIMING_LINES][40] = {
    "If you are using a custom HDMI mode,",
    "the refresh rate may not be exactly",
    "the 50/60 hz the emulator expects.",
    "This can cause audio to get out of",
    "sync or cause popping noises.",
    "",
    "This tool will calculate the number",
    "of machine cycles that should be",
    "emulated within one refresh cycle",
    "using the current HDMI mode. For",
    "an accurate number, the test will",
    "take 10 minutes. When complete,",
    "choose Save Timing To Config.",
    "Factory Configs offer to create a",
    "custom Config. Back cancels.",
    "NTSC and PAL values stay separate.",
    "Saving restarts the emulator.",

};

// When countdown dialog is popped, turn off the test
static void calc_popped(struct menu_item *new_root,
                        struct menu_item *old_root) {

  strcpy(start_item->name, "Start Calculation");
  start_item->disabled = 0;
  if (hdmi_timing_active) {
    // User bailed. Don't try to calculate anything.
    hdmi_timing_count = 0;
    hdmi_timing_active = 0;
    return;
  }

  double fps = (double)hdmi_timing_count / (double)(TEST_DURATION / 1000000);
  unsigned long cycles = emux_calculate_timing(fps);

  char timing_str[64];
  if (fps >= 49 && fps <= 51) {
    sprintf(timing_str, "machine_timing=pal-custom");
  } else if (fps >= 59 && fps <= 61) {
    sprintf(timing_str, "machine_timing=ntsc-custom");
  } else {
    sprintf(timing_str, "machine_timing=ERROR: FPS OUT OF RANGE, %f", fps);
  }

  int timing = circle_get_machine_timing();
  int ntsc = timing == MACHINE_TIMING_NTSC_HDMI || timing == MACHINE_TIMING_NTSC_CUSTOM_HDMI;
  int pal = timing == MACHINE_TIMING_PAL_HDMI || timing == MACHINE_TIMING_PAL_CUSTOM_HDMI;
  if (configs_timing_valid(cycles) &&
      ((ntsc && fps >= 59 && fps <= 61) || (pal && fps >= 49 && fps <= 51))) {
    measured_cycles = cycles;
    measured_ntsc = ntsc;
    struct menu_item *root = ui_push_menu(36, 11);
    struct menu_item *tmp_item;
    ui_menu_add_button(MENU_TEXT, root, "Calculation complete!");
    ui_menu_add_divider(root);
    ui_menu_add_button(MENU_TEXT, root, timing_str);
    tmp_item = ui_menu_add_button(MENU_TEXT, root, "");
    sprintf(tmp_item->name, "cycles_per_second=%lu", cycles);
    ui_menu_add_divider(root);
    tmp_item = ui_menu_add_button(MENU_TEXT, root, "");
    sprintf(tmp_item->name, "Actual fps = %f", fps);
    tmp_item = ui_menu_add_button(MENU_SAVE_CALC_TIMING, root, "Save Timing To Config");
    tmp_item->on_value_changed = save_timing;
    ui_menu_add_button(MENU_CONFIRM_CANCEL, root, "Cancel");
  } else {
    ui_error("Invalid FPS or HDMI standard");
  }

  hdmi_timing_count = 0;
}

// Begin running the test
static void run_calc() {
  struct menu_item *root = ui_push_menu(30, 1);
  // Replace the Start row. The native CHARGEN panel fits between the
  // lower separator and the page bottom, keeping every instruction visible.
  start_item->name[0] = '\0';
  start_item->disabled = 1;
  root->menu_left = timing_page->menu_left + (timing_page->menu_width - root->menu_width) / 2;
  root->menu_top = timing_page->menu_top + (NUM_TIMING_LINES + 5) * 8;
  root->on_popped_off = calc_popped;
  g_countdown_item = ui_menu_add_read_only_heading(root, "600 Seconds Remaining");
  hdmi_timing_active = 1;
  hdmi_timing_start = circle_get_ticks();
  hdmi_timing_countdown_start = hdmi_timing_start;
}

// Capture menu item click to begin test
static void menu_timing_value_changed(struct menu_item *item) {
  switch (item->id) {
  case MENU_START_CALC_TIMING:
    run_calc();
    break;
  }
}

void build_timing_menu(struct menu_item *root) {
  timing_page = root;
  ui_menu_add_read_only_heading(root, "TIMING CALIBRATION CORRECTION");
  ui_menu_add_divider(root);
  int i;
  for (i = 0; i < NUM_TIMING_LINES; i++) {
    ui_menu_add_button(MENU_TEXT, root, instructions[i]);
  }
  ui_menu_add_divider(root);
  ui_menu_add_button(MENU_TEXT, root, ""); // room for the countdown frame
  struct menu_item *item =
      ui_menu_add_button(MENU_START_CALC_TIMING, root, "Start Calculation");
  item->on_value_changed = menu_timing_value_changed;
  start_item = item;
  ui_menu_add_button(MENU_TEXT, root, "");
  hdmi_timing_count = 0;
}

// Called from the ui frame draw trap in ui
void hdmi_timing_hook(void) {
  if (hdmi_timing_active) {
    if (circle_get_ticks() - hdmi_timing_start >= TEST_DURATION) {
      hdmi_timing_active = 0;
      ui_pop_menu();
    } else if (circle_get_ticks() - hdmi_timing_countdown_start >= 1000000) {
      // Update the countdown item
      unsigned int num_seconds_remain =
          (TEST_DURATION - (circle_get_ticks() - hdmi_timing_start)) / 1000000;
      sprintf(g_countdown_item->name, "%u Seconds Remaining",
              num_seconds_remain);
      hdmi_timing_countdown_start = circle_get_ticks();
    }
    hdmi_timing_count++;
  }
}
