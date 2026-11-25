#include "../../src/fan_control.h"
/*
 * menu_configs.c
 *
 * This file is part of VICE, the Versatile Commodore Emulator.
 * See README for copyright notice.
 */

#include "menu_configs.h"
#include "menu_theme.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>

// RASPI includes
#include "circle.h"
#include "demo.h"
#include "menu.h"
#include "menu_switch.h"
#include "ui.h"
#include "../../src/configs/configs.h"
#include "../../src/configs/configs_internal.h"

extern void reboot(void);
extern int circle_cycles_per_sec(void);

// Folder whose name shows the running config's autostart.
static struct menu_item *autostart_folder;
// Items that show the running config's name.
static struct menu_item *status_item;
static struct menu_item *save_item;
static struct menu_item *protection_item;

static void show_result(int result) {
  if (result == CONFIGS_NOT_IMPLEMENTED) {
    ui_info("Not implemented yet");
  } else if (result != CONFIGS_OK) {
    ui_error("Config action failed");
  }
}

// For actions that save straight away: confirm what was saved.
static void show_saved(int result, const char *message) {
  if (result == CONFIGS_OK) {
    ui_info("%s", message);
  } else {
    show_result(result);
  }
}

static const char *base_name(const char *path) {
  const char *slash = strrchr(path, '/');
  return slash ? slash + 1 : path;
}

static void update_autostart_label(void) {
  if (autostart_folder == NULL) {
    return;
  }
  const char *autostart = configs_autostart();
  snprintf(autostart_folder->displayed_value,
           sizeof(autostart_folder->displayed_value),
           "%s", autostart[0] ? base_name(autostart) : "None");
}

// Config name for the config lists.
static void config_label(const ConfigInfo *info, char *out, int out_size) {
  // Only the saved machine's second component specifies its video standard.
  // Legacy machine-only values have no standard; don't infer one from the
  // running machine or from a description containing PAL/NTSC.
  const char *standard = strchr(info->machine, '/');
  const char *prefix = "";
  if (standard) {
    standard++;
    while (*standard == ' ') standard++;
    const char *end = strchr(standard, '/');
    if (!end) end = standard + strlen(standard);
    while (end > standard && end[-1] == ' ') end--;
    if (end - standard == 4 && !strncasecmp(standard, "NTSC", 4))
      prefix = "NTSC - ";
    else if (end - standard == 3 && !strncasecmp(standard, "PAL", 3))
      prefix = "PAL  - ";
  }
  // Existing display-style prefixes are normalized only in this label.
  // Never rename the Config or use its displayed text as its identity.
  const char *name = info->name;
  while (!strncmp(name, "NTSC - ", 7) || !strncmp(name, "PAL  - ", 7)) {
    if (!prefix[0]) break;
    name += 7;
  }
  snprintf(out, out_size, "%s%s", prefix, name);
}

// Pushes a menu with a heading. Call ready() once its items are added.
static struct menu_item *push_menu(int w_chars, int h_chars,
                                   const char *title) {
  struct menu_item *root = ui_push_menu(w_chars, h_chars);
  ui_menu_add_read_only_heading(root, title);
  ui_menu_add_divider(root);
  return root;
}

// The cursor must start on a selectable item, not on the heading.
static void ready(void) {
  ui_select_first_interactive_item();
}

static void list_popped(struct menu_item *old_root,
                        struct menu_item *new_root) {
  configs_list_close();
}

// Calculate a compact popup height from the actual visible menu rows.
// Two rows are reserved for the title and divider.
static int config_popup_height(int skip_main_and_running) {
  const char *running = configs_running()->id;
  int rows = 2;

  // Factory and uncategorized Configs appear directly in the list.
  for (int i = 0; configs_list_at(i) != NULL; i++) {
    const ConfigInfo *info = configs_list_at(i);
    if (skip_main_and_running &&
        (strcmp(info->id, running) == 0 ||
         configs_is_factory(info->id)))
      continue;

    if (!info->category[0])
      rows++;
  }

  // Each distinct category adds one collapsed folder row.
  for (int i = 1; configs_list_at(i) != NULL; i++) {
    const ConfigInfo *info = configs_list_at(i);
    if (!info->category[0])
      continue;

    int seen = 0;
    for (int j = 1; j < i; j++) {
      const ConfigInfo *previous = configs_list_at(j);
      if (strcmp(previous->category, info->category) == 0) {
        seen = 1;
        break;
      }
    }
    if (!seen)
      rows++;
  }

  // Twelve pixels per row, with padding above and below.
  // Keep the popup within the normal 25-row menu area.
  int pixels = rows * 12 + 20;
  int height = (pixels + 7) / 8;

  if (height < 9) height = 9;
  if (height > 20) height = 20;

  return height;
}

// Adds one button per config to a list, grouped into folders by category.
// Factory and user Configs without a category come first. The button's str_value
// holds the config id. Returns the number of buttons added.
static int add_config_buttons(struct menu_item *root, int id,
                               int skip_main_and_running,
                               void (*on_chosen)(struct menu_item *)) {
  const char *running = configs_running()->id;
  int count = 0;
  while (configs_list_at(count) != NULL) count++;
  int added = 0;
  for (int pass = 0; pass < count; pass++) {
    // Pass 0 adds configs without a category; each later pass adds the
    // category of config 'pass' if that config is the first one in it.
    struct menu_item *parent = root;
    const char *category = "";
    if (pass > 0) {
      category = configs_list_at(pass)->category;
      if (!category[0]) {
        continue;
      }
      int seen = 0;
      for (int i = 1; i < pass && !seen; i++) {
        seen = strcmp(configs_list_at(i)->category, category) == 0;
      }
      if (seen) {
        continue;
      }
      parent = ui_menu_add_folder(root, (char *)category);
    }
    for (int i = 0; i < count; i++) {
      const ConfigInfo *info = configs_list_at(i);
      if (strcmp(info->category, category) != 0) {
        continue;
      }
      int is_running = strcmp(info->id, running) == 0 ||
          (configs_is_factory(info->id) && configs_is_factory(running));
      if (skip_main_and_running &&
          (is_running || configs_is_factory(info->id))) {
        continue;
      }
      struct menu_item *item = ui_menu_add_button(id, parent, "");
      config_label(info, item->name, sizeof(item->name));
      snprintf(item->str_value, sizeof(item->str_value), "%s", info->id);
      ui_menu_mark_option(item, is_running);
      item->on_value_changed = on_chosen;
      added++;
    }
  }
  return added;
}

// ---- Machines ----

static int booted_ntsc;
static BMC64VideoOut booted_out;

// What booted, in machines.txt terms, e.g. "C64/PAL/HDMI".
static void describe_booted(const char *machine, char *out, int out_size) {
  int timing = circle_get_machine_timing();
  booted_ntsc = timing == MACHINE_TIMING_NTSC_HDMI ||
                timing == MACHINE_TIMING_NTSC_COMPOSITE ||
                timing == MACHINE_TIMING_NTSC_CUSTOM_HDMI ||
                timing == MACHINE_TIMING_NTSC_DPI ||
                timing == MACHINE_TIMING_NTSC_CUSTOM_DPI;
  if (timing == MACHINE_TIMING_NTSC_COMPOSITE ||
      timing == MACHINE_TIMING_PAL_COMPOSITE) {
    booted_out = BMC64_VIDEO_OUT_COMPOSITE;
  } else if (timing >= MACHINE_TIMING_NTSC_DPI &&
             timing <= MACHINE_TIMING_NTSC_CUSTOM_DPI) {
    booted_out = BMC64_VIDEO_OUT_DPI;
  } else {
    booted_out = BMC64_VIDEO_OUT_HDMI;
  }
  snprintf(out, out_size, "%s/%s/%s", machine, booted_ntsc ? "NTSC" : "PAL",
           booted_out == BMC64_VIDEO_OUT_COMPOSITE ? "Composite"
           : booted_out == BMC64_VIDEO_OUT_DPI     ? "DPI"
                                                   : "HDMI");
}

// Applies the first machines.txt entry with every part of machine,
// preferring the video standard and output that booted. Returns 0, or -1 if
// there's no such entry or it can't be applied.
static int apply_machine(const char *machine) {
  struct machine_entry *head;
  load_machines(&head);
  struct machine_entry *best = NULL;
  int best_score = -1;
  for (struct machine_entry *ptr = head; ptr; ptr = ptr->next) {
    // Filter before restoring calibrated timing or changing either boot file.
    if (ptr->video_out == BMC64_VIDEO_OUT_DPI && !fan_dpi_allowed()) continue;
    if (ptr->class == BMC64_MACHINE_CLASS_PLUS4EMU && circle_get_model() < 3) {
      continue;  // not offered on this Pi
    }
    if (!configs_machine_covers(machine, ptr->header)) {
      continue;
    }
    int ntsc = ptr->video_standard == BMC64_VIDEO_STANDARD_NTSC;
    int score = (ntsc == booted_ntsc ? 2 : 0) + (ptr->video_out == booted_out);
    if (score > best_score) {
      best = ptr;
      best_score = score;
    }
  }
  int result = -1;
  if (best != NULL && switch_calibrated_timing(0, 0, NULL) == 0 &&
      switch_apply_files(best) == 0) {
    result = 0;
  }
  free_machines(head);
  return result;
}

static int config_assets_in_use(const char *id) {
  if (emux_config_in_use(id) || configs_path_belongs(configs_autostart(), id)) return 1;
  for (int i = 0; i < CONFIGS_NUM_DRIVES; i++) {
    if (configs_path_belongs(attached_disk_name[i], id) ||
        configs_path_belongs(configs_startup_disk(i), id)) return 1;
  }
  return 0;
}

void menu_configs_boot(const char *machine) {
  switch_capture_video_mode();
  configs_protection_init(circle_get_disk_volume());
  configs_set_system_volume(circle_get_disk_volume());
  configs_set_runtime_guard(config_assets_in_use);
  char booted[64];
  describe_booted(machine, booted, sizeof(booted));
  configs_boot_init(booted);
  unsigned long cycles = configs_running_timing(booted_ntsc);
  // A Start Once calibration must not leak into an uncalibrated power-on
  // Config on the next boot. Restore only the original timing arguments.
  if (!cycles) {
    int restored = 0;
    if (switch_calibrated_timing(0, 0, &restored) != 0) configs_timing_apply_failed();
    else if (restored) {
      configs_before_reboot();
      fan_prepare_shutdown(); reboot();
      return;
    }
  }
  if (cycles && booted_out == BMC64_VIDEO_OUT_HDMI) {
    int wanted = booted_ntsc ? MACHINE_TIMING_NTSC_CUSTOM_HDMI : MACHINE_TIMING_PAL_CUSTOM_HDMI;
    if (circle_get_machine_timing() != wanted || (unsigned long)circle_cycles_per_sec() != cycles) {
      if (switch_calibrated_timing(booted_ntsc, cycles, NULL) == 0) {
        configs_before_reboot();
        fan_prepare_shutdown(); reboot();
        return;
      }
      configs_timing_apply_failed();
    }
  }
  if (configs_running_is_factory() &&
      !configs_machine_matches(configs_running()->machine, booted)) {
    if (apply_machine(configs_running()->machine) == 0) { fan_prepare_shutdown(); reboot(); }
    // Keep a missing definition from making the persisted recovery choice
    // fatal on every subsequent boot. Continue on the machine that booted.
    configs_factory_machine_failed();
    // Try NTSC after a failed PAL lookup. If both entries are unavailable,
    // keep factory defaults on the video mode that already booted.
    if (!configs_machine_matches(configs_running()->machine, booted) &&
        apply_machine(configs_running()->machine) == 0) { fan_prepare_shutdown(); reboot(); }
  }
}

void menu_configs_before_reboot(void) {
  configs_before_reboot();
  // A Start-once config on another machine: the power-on config's machine
  // was put back after boot, so this restart needs the config's again.
  if (configs_return_machine()[0] != '\0') {
    apply_machine(configs_running()->machine);
  }
}

void menu_configs_machine_switched(struct machine_entry *entry) {
  configs_machine_switched(entry->header);
}

// ---- Select config ----

// Why the last menu_configs_start() couldn't start a config, or "".
static char start_error[64];

void menu_configs_start(const char *id, int once) {
  start_error[0] = '\0';
  if (!configs_is_active(id)) {
    snprintf(start_error, sizeof(start_error), "Config deleted or records unavailable");
  } else if (strcmp(id, configs_running()->id) == 0) {
    snprintf(start_error, sizeof(start_error), "Already running");
  } else {
    const char *needed = configs_machine_for(id);
    // Restore only timing when the target uses the current video mode.
    // A different machine uses the existing full machine-switch path.
    if (!needed[0] && switch_calibrated_timing(0, 0, NULL) != 0) {
      ui_error("Can't restore video timing");
      return;
    }
    if (needed[0] != '\0' && apply_machine(needed) != 0) {
      snprintf(start_error, sizeof(start_error),
               "No machine for this config in machines.txt");
    } else if ((once ? configs_start_once(id) : configs_switch_to(id)) !=
               CONFIGS_OK) {
      snprintf(start_error, sizeof(start_error), "Can't start this config");
    } else {
      fan_prepare_shutdown(); reboot();
    }
  }
  ui_error("%s", start_error);
}

const char *menu_configs_start_error(void) {
  return start_error;
}

void menu_configs_clear_start_error(void) {
  start_error[0] = '\0';
}

static void start_chosen(struct menu_item *item) {
  menu_configs_start(item->str_value, item->id == MENU_CONFIGS_START_ONCE);
}

static void config_selected(struct menu_item *item) {
  if (strcmp(item->str_value, configs_running()->id) == 0) {
    ui_config_already_running();
    return;
  }
  ConfigStart start = CONFIG_START_SWITCH;
  for (int i = 0; configs_list_at(i) != NULL; i++) {
    if (strcmp(configs_list_at(i)->id, item->str_value) == 0) {
      start = configs_list_at(i)->start;
      break;
    }
  }

  // The config's "start" choice is offered first.
  static const int switch_first[] = {MENU_CONFIGS_SWITCH_TO,
                                     MENU_CONFIGS_START_ONCE};
  static const int once_first[] = {MENU_CONFIGS_START_ONCE,
                                   MENU_CONFIGS_SWITCH_TO};
  const int *order = start == CONFIG_START_ONCE ? once_first : switch_first;
  int choices = 2;

  struct menu_item *root = push_menu(E64_MENU_CONFIG_NAME_COLS, 8, item->name);
  root->is_submenu = 1;
  for (int i = 0; i < choices; i++) {
    struct menu_item *button = ui_menu_add_button(
        order[i], root,
        order[i] == MENU_CONFIGS_SWITCH_TO ? "Switch To" : "Start Once");
    strcpy(button->str_value, item->str_value);
    button->on_value_changed = start_chosen;
  }
  ready();
}

static void show_select_list(void) {
  configs_list_open();
  int height = config_popup_height(0);
  struct menu_item *root = push_menu(E64_MENU_CONFIG_LIST_COLS, height, "Select Config");
  root->is_submenu = 1;
  strcpy(root->name, E64_MENU_CONFIG_LIST_TAG);
  ui_refresh_menu_window();
  root->on_popped_off = list_popped;
  add_config_buttons(root, MENU_CONFIGS_SELECT_ITEM, 0, config_selected);
  ready();
}

// ---- New config / Rename ----

static void update_name_labels(void) {
  if (status_item != NULL) {
    const char *name = configs_running()->name;
    // The fixed 40-column root cannot hold its prefix plus a full 32-byte
    // name. Keep the full name and the existing expandable-folder marker.
    snprintf(status_item->name, sizeof(status_item->name), "%s%s",
             strlen(name) + strlen("Active Config: ") < sizeof(status_item->name)
                 ? "Active Config: "
                 : strlen(name) + strlen("Config: ") < sizeof(status_item->name)
                       ? "Config: " : "", name);
  }
  if (save_item != NULL) {
    snprintf(save_item->name, sizeof(save_item->name),
             "Save Changes To The Current Config");
  }
}

static char rename_config_id[CONFIGS_MAX_ID_LEN + 1];
static unsigned long new_config_timing;
static int new_config_ntsc;

// Saves the current settings as a new config and restarts into it.
static void create_config(const char *name) {
  char id[CONFIGS_MAX_ID_LEN + 1];
  if (configs_create(name, id, sizeof(id)) != CONFIGS_OK) {
    ui_error("Can't create the config");
    return;
  }
  if (menu_save_settings_to_config(id) != 0) {
    // Preserve an incomplete new config for recovery; do not implicitly
    // initialize or alter logical-deletion records on a failed Save.
    ui_error("Can't save new config\nFiles retained for recovery");
    return;
  }
  if (new_config_timing &&
      configs_save_timing(id, new_config_ntsc, new_config_timing) != CONFIGS_OK) {
    ui_error("Can't save calibration");
    return;
  }
  if (configs_switch_to(id) != CONFIGS_OK) {
    ui_error("Config saved, but can't\nswitch to it");
    return;
  }
  fan_prepare_shutdown(); reboot();
}

static void name_entered(struct menu_item *item) {
  if (item->str_value[0] == '\0') {
    return;
  }
  if (item->id == MENU_CONFIGS_NEW_NAME) {
    create_config(item->str_value);
  } else if (configs_rename(rename_config_id, item->str_value) == CONFIGS_OK) {
    update_name_labels();
    ui_pop_menu();
    ui_info("Config renamed");
  } else {
    ui_error("Can't rename the config");
  }
}

static void show_name_dialog(int id, const char *title, const char *name) {
  int has_cancel = id == MENU_CONFIGS_NEW_NAME && new_config_timing;
  struct menu_item *root = ui_push_menu(E64_MENU_CONFIG_NAME_COLS, has_cancel ? 6 : 5);
  strcpy(root->name, E64_MENU_CONFIG_NAME_TAG);
  ui_menu_add_read_only_heading(root, title);
  ui_menu_add_divider(root);
  struct menu_item *field = ui_menu_add_text_field_limit(
      id, root, "", (char *)name, CONFIGS_MAX_NAME_LEN);
  field->on_value_changed = name_entered;
  if (has_cancel)
    ui_menu_add_button(MENU_CONFIRM_CANCEL, root, "Cancel");
  ready();
}

void menu_configs_save_timing(unsigned long cycles, int ntsc) {
  if (!configs_timing_valid(cycles)) { ui_error("Invalid calibration"); return; }
  if (configs_running_is_factory()) {
    new_config_timing = cycles;
    new_config_ntsc = ntsc;
    show_name_dialog(MENU_CONFIGS_NEW_NAME, "Create Custom Config To Save", "");
    return;
  }
  if (configs_save_timing(configs_running()->id, ntsc, cycles) != CONFIGS_OK) {
    ui_error("Can't save timing\nConfig may be protected");
    return;
  }
  menu_configs_before_reboot();
  fan_prepare_shutdown(); reboot();
}

void menu_configs_protection_action(const char *id, int on, int confirmed_off) {
  int result = configs_set_protected(id, on, confirmed_off);
  snprintf(start_error, sizeof(start_error), "%s", result == CONFIGS_OK ? "" : configs_protection_error());
}

static unsigned delete_serial;
static int delete_state;
static char delete_id[CONFIGS_MAX_ID_LEN+1], delete_error[256];
// Called by the Web queue while circle_lock is held.
unsigned menu_configs_delete_begin(const char *id) {
  if(delete_state==1)return 0;
  delete_serial=(delete_serial%0x7ffffffeU)+1;
  snprintf(delete_id,sizeof(delete_id),"%s",id);delete_error[0]=0;delete_state=1;
  return delete_serial;
}
void menu_configs_delete_status(unsigned *serial,int *state,char *id,int id_size,char *error,int error_size) {
  circle_lock_acquire();*serial=delete_serial;*state=delete_state;
  snprintf(id,id_size,"%s",delete_id);snprintf(error,error_size,"%s",delete_error);
  circle_lock_release();
}
void menu_configs_logical_action(const char *id,int legacy) {
  int result=legacy?configs_purge_legacy(id):configs_delete(id);
  circle_lock_acquire();
  snprintf(delete_error,sizeof(delete_error),"%s",result==CONFIGS_OK?"":configs_management_error());
  delete_state=result==CONFIGS_OK?2:-1;
  circle_lock_release();
}

// Native deletion has two independent, cancel-first questions. Stage one is
// popped before stage two, so Back/Escape from either cancels the operation.
static struct menu_item *cleanup_parent,*cleanup_item;
static void delete_question(const char *id,const char *name,int second,int legacy);
static void remove_empty_cleanup_control(void) {
  if(!cleanup_parent || !cleanup_item || configs_deleted_count())return;
  struct menu_item **link=&cleanup_parent->first_child;
  while(*link && *link!=cleanup_item)link=&(*link)->next;
  if(*link){*link=cleanup_item->next;free(cleanup_item);}
  cleanup_item=NULL;ui_select_first_interactive_item();
}
static void delete_confirmed(struct menu_item *item) {
  char id[CONFIGS_MAX_ID_LEN+1];snprintf(id,sizeof(id),"%s",item->str_value);
  int legacy=item->sub_id;
  int result=legacy?configs_purge_legacy(id):configs_delete(id);
  if(result!=CONFIGS_OK){ui_error("%s",configs_management_error());return;}
  ui_pop_menu();ui_pop_menu();
  remove_empty_cleanup_control();
  ui_info("Config permanently deleted");
}
static void delete_first_yes(struct menu_item *item) {
  char id[CONFIGS_MAX_ID_LEN+1],name[CONFIGS_MAX_NAME_LEN+1];int legacy=item->sub_id;
  snprintf(id,sizeof(id),"%s",item->str_value);
  ConfigFile pf;
  if(legacy){snprintf(name,sizeof(name),"%s",id);for(int i=0;i<configs_deleted_count();i++)if(!strcmp(configs_deleted_id((unsigned)i),id))snprintf(name,sizeof(name),"%s",configs_deleted_name((unsigned)i));}
  else if(config_file_read(id,&pf)==CONFIGS_OK)snprintf(name,sizeof(name),"%s",pf.info.name);
  else {ui_error("Config changed. Refresh first.");return;}
  ui_pop_menu();delete_question(id,name,1,legacy);
}
static void delete_question(const char *id,const char *name,int second,int legacy) {
  char text[128];snprintf(text,sizeof(text),second?"Confirm permanent deletion of \"%s\"?":"Delete Config \"%s\"?",name);
  struct menu_item *root=push_menu(38,10,"Delete Config");
  strcpy(root->name, "E64 Delete Confirm");
  const char *cursor=text;
  while(*cursor){unsigned n=(unsigned)strlen(cursor);if(n>36){n=36;while(n && cursor[n]!=' ')n--;if(!n)n=36;}
    char line[37];memcpy(line,cursor,n);line[n]=0;ui_menu_add_read_only_heading(root,line)->type=READ_ONLY_DESCRIPTION;cursor+=n;while(*cursor==' ')cursor++;
  }
  ui_menu_add_button(MENU_CONFIRM_CANCEL,root,"No");
  struct menu_item *yes=ui_menu_add_button(MENU_CONFIGS_DELETE_CONFIRM,root,second?"Yes, Delete":"Yes");
  snprintf(yes->str_value,sizeof(yes->str_value),"%s",id);yes->sub_id=legacy;
  yes->on_value_changed=second?delete_confirmed:delete_first_yes;
  // One full cell of clearance above and below the complete wrapped content.
  int rows = 0;
  for (struct menu_item *p = root->first_child; p; p = p->next) ++rows;
  int height = (rows + 2) * E64_MENU_CELL;
  root->menu_top += (root->menu_height - height) / 2;
  root->menu_height = height;
  for (struct menu_item *p = root->first_child; p; p = p->next) {
    p->menu_top = root->menu_top;
    p->menu_height = height;
  }
  ready();
}
static void delete_selected(struct menu_item *item) {
  ConfigFile pf;
  if(config_file_read(item->str_value,&pf)!=CONFIGS_OK){ui_error("Cannot read Config");return;}
  delete_question(item->str_value,pf.info.name,0,0);
}
static void show_delete_list(void) {
  configs_list_open();
  struct menu_item *root=push_menu(E64_MENU_CONFIG_LIST_COLS,config_popup_height(1),"Delete Config");
  root->is_submenu = 1;
  strcpy(root->name, E64_MENU_CONFIG_LIST_TAG);
  ui_refresh_menu_window();root->on_popped_off=list_popped;
  if(add_config_buttons(root,MENU_CONFIGS_DELETE_ITEM,1,delete_selected)==0)ui_menu_add_button(MENU_TEXT,root,"No Configs to delete");
  ready();
}
static void legacy_delete_selected(struct menu_item *item) {
  const char *name=item->str_value;
  for(int i=0;i<configs_deleted_count();i++)if(!strcmp(configs_deleted_id((unsigned)i),item->str_value))name=configs_deleted_name((unsigned)i);
  delete_question(item->str_value,name,0,1);
}
static void show_restore_list(void) {
  int count=configs_deleted_count(),height=count+4;if(height>20)height=20;
  struct menu_item *root=push_menu(E64_MENU_CONFIG_LIST_COLS,height,"Legacy Config Cleanup");
  root->is_submenu = 1;
  strcpy(root->name, E64_MENU_CONFIG_LIST_TAG);
  for(int i=0;i<count;i++){
    struct menu_item *item=ui_menu_add_button(MENU_CONFIGS_RESTORE_ITEM,root,(char*)configs_deleted_name((unsigned)i));
    snprintf(item->str_value,sizeof(item->str_value),"%s",configs_deleted_id((unsigned)i));item->on_value_changed=legacy_delete_selected;
  }
  if(!count)ui_menu_add_read_only_heading(root,"No legacy entries");
  ready();
}

// Independent protection setting; unprotect requires an explicit confirmation.
static void protection_label(void) {
  int status = configs_protection_status(configs_running()->id);
  if (protection_item) snprintf(protection_item->name, sizeof(protection_item->name),
                               status < 0 ? "Protect Current Config: %s" : "Protect The Current Config: %s",
                               status < 0 ? "Unavailable" : status ? "On" : "Off");
}
static void unprotect_confirmed(struct menu_item *item) {
  if (configs_set_protected(item->str_value, 0, 1) != CONFIGS_OK) {
    ui_error("%s", configs_protection_error());return;
  }
  protection_label();ui_pop_menu();ui_info("Protection Off");
}
static void change_protection(void) {
  const char *id = configs_running()->id;
  if (configs_running_is_factory()) { ui_info("This config is permanently protected");return; }
  int status = configs_protection_status(id);
  if (status < 0) { ui_error("Protection unavailable.\nRetry or recover records.");return; }
  if (status) {
    struct menu_item *root = push_menu(29, 7, "Turn Protection Off?");
    struct menu_item *confirm = ui_menu_add_button(MENU_CONFIGS_UNPROTECT_CONFIRM, root, "Confirm Protection Off");
    snprintf(confirm->str_value, sizeof(confirm->str_value), "%s", id);
    confirm->on_value_changed = unprotect_confirmed;
    ui_menu_add_button(MENU_CONFIRM_CANCEL, root, "Cancel");ready();
  } else if (configs_set_protected(id, 1, 0) != CONFIGS_OK) {
    ui_error("%s", configs_protection_error());
  } else { protection_label();ui_info("Protection On"); }
}

static void rename_chosen(struct menu_item *item) {
  if (configs_is_factory(item->str_value)) return;
  ConfigFile pf;
  if (config_file_read(item->str_value, &pf) != CONFIGS_OK) {
    ui_error("Config unavailable.\nReopen Rename Config.");
    return;
  }
  // Read current metadata and copy the ID before popping frees the list/button.
  snprintf(rename_config_id, sizeof(rename_config_id), "%s", item->str_value);
  ui_pop_menu();
  show_name_dialog(MENU_CONFIGS_RENAME_NAME, "Rename Config", pf.info.name);
}

static void show_rename_list(void) {
  // This API returns a count (including Default), not CONFIGS_OK.
  int listed = configs_list_open();
  if (listed < 0) {
    configs_list_close();
    ui_error("Can't read Config list.\nCheck Config storage.");
    return;
  }
  struct menu_item *root = push_menu(38, 20, "Select Config To Rename");
  root->is_submenu = 1;
  strcpy(root->name, E64_MENU_CONFIG_LIST_TAG);
  ui_refresh_menu_window();
  root->on_popped_off = list_popped;
  int count = 0;
  for (int i = 0; i < listed; i++) {
    const ConfigInfo *info = configs_list_at(i);
    if (!info || configs_is_factory(info->id)) continue;
    // Custom protection guards deletion, not display-name edits. Running,
    // Power-on and Start Once identities are stable across a rename.
    struct menu_item *button = ui_menu_add_button(MENU_CONFIGS_RENAME_NAME, root, "");
    config_label(info, button->name, sizeof(button->name));
    snprintf(button->str_value, sizeof(button->str_value), "%s", info->id);
    button->on_value_changed = rename_chosen;
    count++;
  }
  if (!count) {
    ui_menu_add_read_only_heading(root, "No custom Configs to rename");
    ui_menu_add_button(MENU_CONFIRM_CANCEL, root, "Back");
  }
  ready();
}

// At depth two in the 40-column root, text starts at column four and
// ends before column 39. Keep 35 cells, including the ten-cell label.
#define CONFIG_ROM_VALUE_COLS 25
static void config_rom_row_render(struct menu_item *item) {
  static const char *const labels[] = {"KERNAL  : ", "BASIC   : ", "CHARGEN : "};
  const char *name = "Unavailable";
  emux_get_string_1(Setting_ConfigROM, &name, item->sub_id);
  unsigned long now = circle_get_ticks();
  if (strcmp(item->str_value, name)) {
    snprintf(item->str_value, sizeof(item->str_value), "%s", name);
    item->value = (int)(unsigned)now;
  }
  // One second per cell, with a three-second pause at either end. No
  // ellipsis replaces filename bytes: every byte enters the visible window.
  unsigned length = strlen(item->str_value);
  unsigned offset = 0;
  if (length > CONFIG_ROM_VALUE_COLS) {
    unsigned travel = length - CONFIG_ROM_VALUE_COLS;
    unsigned phase = (((unsigned)now - (unsigned)item->value) / 1000000U) % (travel + 6);
    offset = phase < 3 ? 0 : phase - 3;
    if (offset > travel) offset = travel;
  }
  snprintf(item->name, sizeof(item->name), "%s%.*s", labels[item->sub_id],
           CONFIG_ROM_VALUE_COLS, item->str_value + offset);
}

static void config_rom_summary_render(struct menu_item *folder) {
  snprintf(folder->name, sizeof(folder->name), "%s",
           folder->is_expanded ? "ROMs in this Config" : "ROMs in this Config >");
}

static void config_rom_summary_changed(struct menu_item *folder) {
  for (struct menu_item *row = folder->first_child; row; row = row->next)
    row->str_value[0] = 0; // Restart long names at their beginning on RETURN.
  config_rom_summary_render(folder);
}

static void add_config_rom_summary(struct menu_item *parent) {
  struct menu_item *folder = ui_menu_add_folder(parent, "ROMs in this Config >");
  folder->is_expanded = 0;
  folder->on_value_changed = config_rom_summary_changed;
  folder->on_render = config_rom_summary_render;
  for (int i = 0; i < 3; i++) {
    struct menu_item *row = ui_menu_add_read_only_heading(folder, "");
    row->type = READ_ONLY_DESCRIPTION;
    row->sub_id = i;
    row->on_render = config_rom_row_render;
    config_rom_row_render(row);
  }
}

// ---- Menu items ----

static void configs_item_chosen(struct menu_item *item) {
  switch (item->id) {
  case MENU_CONFIGS_PROTECTION:
    change_protection();
    break;
  case MENU_CONFIGS_SELECT:
    show_select_list();
    break;
  case MENU_CONFIGS_NEW:
    new_config_timing = 0;
    show_name_dialog(MENU_CONFIGS_NEW_NAME, "New Config Name", "");
    break;
  case MENU_CONFIGS_RENAME:
    show_rename_list();
    break;
  case MENU_CONFIGS_RESTORE:
    show_restore_list();
    break;
  case MENU_CONFIGS_DELETE:
    show_delete_list();
    break;
  case MENU_CONFIGS_AUTOSTART_FILE:
    menu_show_autostart_files(MENU_CONFIGS_AUTOSTART_PICK);
    break;
  case MENU_CONFIGS_CLEAR_AUTOSTART:
    show_saved(configs_clear_autostart(), "Nothing will autostart");
    update_autostart_label();
    break;
  case MENU_CONFIGS_AUTO_ATTACH_DISKS: {
    const char *paths[CONFIGS_NUM_DRIVES];
    char message[64] = "No disks set for boot";
    int length = 0;
    for (int i = 0; i < CONFIGS_NUM_DRIVES; i++) {
      paths[i] = attached_disk_name[i];
      if (paths[i][0]) {
        length += snprintf(message + length, sizeof(message) - length,
                           length ? ",%d" : "Boot disks: %d", CONFIGS_FIRST_DRIVE + i);
      }
    }
    show_saved(configs_set_startup_disks(paths), message);
    break;
  }
  case MENU_CONFIGS_CLEAR_AUTO_ATTACH:
    show_saved(configs_clear_startup_disks(),
               "Boot disk list cleared");
    break;
  default:
    break;
  }
}

static struct menu_item *add_item(int id, struct menu_item *parent,
                                  const char *name) {
  struct menu_item *item = ui_menu_add_button(id, parent, (char *)name);
  item->on_value_changed = configs_item_chosen;
  return item;
}

void menu_configs_add_status_line(struct menu_item *root) {
  // The first line opens all config operations in one place.
  status_item = ui_menu_add_folder(root, "Config");
  status_item->id = MENU_CONFIGS_SELECT;
  update_name_labels();
}

struct menu_item *menu_configs_get_status_item(void) {
  return status_item;
}

struct menu_item *build_configs_menu(struct menu_item *root) {
  struct menu_item *parent = root;
  add_item(MENU_CONFIGS_SELECT, parent, "Select An Existing Config >");
  if (emux_machine_class == BMC64_MACHINE_CLASS_C64)
    add_config_rom_summary(parent);
  add_item(MENU_CONFIGS_NEW, parent, "Create Config From Current Settings");
  // Keep the original menu_value_changed save handler assigned by build_menu.
  menu_configs_label_save_item(ui_menu_add_button(MENU_SAVE_SETTINGS, parent,
                              "Save Changes To The Current Config"));
  add_item(MENU_CONFIGS_RENAME, parent, "Rename A Config >");
  protection_item = add_item(MENU_CONFIGS_PROTECTION, parent, "");
  protection_label();
  add_item(MENU_CONFIGS_DELETE, parent, "Delete An Existing Config >");
  cleanup_parent=parent;cleanup_item=NULL;
  if(configs_deleted_count())cleanup_item=add_item(MENU_CONFIGS_RESTORE,parent,"Legacy Config Cleanup >");

  return parent;
}

void build_configs_autostart_items(struct menu_item *root) {
  autostart_folder = ui_menu_add_button(MENU_ID_DO_NOTHING, root,
                                       "Current Autostart");
  autostart_folder->disabled = 1;
  autostart_folder->prefer_str = 1;
  add_item(MENU_CONFIGS_AUTOSTART_FILE, root,
           "Autostart PRG/Disk >");
  update_autostart_label();
  add_item(MENU_CONFIGS_CLEAR_AUTOSTART, root,
           "Clear Autostart PRG/Disk");
}

void build_configs_drive_items(struct menu_item *drives) {
  struct menu_item *parent = ui_menu_add_folder(drives, "Auto-Attach Options");
  add_item(MENU_CONFIGS_AUTO_ATTACH_DISKS, parent,
           "Auto-Attach Current Disks At Boot");
  add_item(MENU_CONFIGS_CLEAR_AUTO_ATTACH, parent,
           "Remove Auto-Attached Disks");
}

void menu_configs_label_save_item(struct menu_item *item) {
  save_item = item;
  update_name_labels();
}

void menu_configs_autostart_chosen(const char *path) {
  ui_pop_menu();  // the file list
  int result = configs_set_autostart(path);
  update_autostart_label();
  if (result == CONFIGS_OK) {
    ui_info("Autostart set: %s", base_name(path));
  } else {
    ui_error("Can't set the autostart");
  }
}

void menu_configs_boot_complete(void) {
  // A Start-once config on another machine: the next power-on is back on
  // the power-on config's machine.
  const char *back = configs_return_machine();
  if (back[0] != '\0' && apply_machine(back) != 0) {
    ui_error("No machine for %s\nin machines.txt", back);
  }
  configs_after_boot();
  const char *message = configs_boot_message();
  if (message[0] != '\0') {
    ui_error("%s", message);
  }

  // The config's startup disks, as if attached from the Drives menu.
  for (int i = 0; i < CONFIGS_NUM_DRIVES && !raspi_demo_mode; i++) {
    const char *disk = configs_startup_disk(i);
    if (disk[0] == '\0') {
      continue;
    }
    int unit = CONFIGS_FIRST_DRIVE + i;
    struct stat st;
    if (stat(disk, &st) != 0) {
      configs_startup_failed();
      ui_error("Can't find the disk for\ndrive %d: %s", unit, base_name(disk));
    } else if (emux_attach_disk_image(unit, (char *)disk) != 0) {
      configs_startup_failed();
      ui_error("Can't attach the disk for\ndrive %d: %s", unit, base_name(disk));
    } else {
      snprintf(attached_disk_name[i], MAX_STR_VAL_LEN, "%s", disk);
    }
  }

  // The config's autostart, as if picked from Autostart Prg/Disk. It's
  // queued for the main loop rather than started here: this runs while boot
  // warp is still on, and VICE's autostart puts back the warp state it
  // started with when it finishes, which would leave warp (and no sound) on.
  const char *autostart = configs_autostart();
  if (autostart[0] != '\0' && !raspi_demo_mode) {
    struct stat st;
    if (stat(autostart, &st) != 0) {
      configs_startup_failed();
      ui_error("Can't find the autostart\n%s", base_name(autostart));
    } else {
      emu_autostart_interrupt(autostart);
    }
  }
}
