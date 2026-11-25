/*
 * menu_switch.c
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

#include "menu_switch.h"
#include "../../src/fan_control.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <unistd.h>

#include "circle.h"
#include "../../src/configs/configs.h"

#define OPTION_SCRATCH_LEN (KEY_LEN+1+VALUE_LEN+1)

#define ERROR_1 1
#define ERROR_2 2
#define ERROR_3 4
#define ERROR_4 8
#define ERROR_5 16
#define ERROR_6 32
#define ERROR_7 64
#define ERROR_8 128
#define ERROR_9 256
#define ERROR_10 512

// BMC64's default GPU memory split (MB). Most machine configs are happy
// with this. A config that needs more (currently only the PET 1080p HDMI
// modes, where the CRT shader's triple-buffered full screen EGL surface
// does not fit a 64MB split) asks for a higher floor with a gpu_mem= line
// in machines.txt; switching to any config that doesn't ask resets the
// split back to this default.
#define DEFAULT_GPU_MEM 64

struct s_cfg_flags {
  // Have flags for cmdline.txt
  int have_cycles_per_second;
  int have_machine_timing;
  int have_serial;
  int have_demo;
  int have_audio_out;
  int have_disk_partition;
  int have_enable_dpi;
  int have_scaling_params;
  int have_scaling_params2;
  int have_raster_skip;
  int have_raster_skip2;

  // Have flags for config.txt
  int have_kernel;
  int have_gpu_mem;
  int have_hdmi_timings;
  int have_cvt;
  int have_dpi_timings;
  int have_enable_dpi_lcd;
  int have_display_default_lcd;
  int have_dpi_group;
  int have_dpi_mode;
  int have_dpi_output_format;

  // Since kernel comes and goes, need this flag
  // to know whether it should be added if not
  // already present to config.txt
  int need_kernel;
};

static int entry_id;

static int next_id() {
   return entry_id++;
}

static void rtrim(char *txt) {
  if (!txt) return;
  int p=strlen(txt)-1;
  while (isspace(txt[p])) { txt[p] = '\0'; p--; }
}

static char* ltrim(char *txt) {
  if (!txt) return NULL;
  int p=0;
  while (isspace(txt[p])) { p++; }
  return txt+p;
}

static char* trim(char *txt) {
  if (!txt) return NULL;
  rtrim(txt);
  return ltrim(txt);
}

static int copy_file(char* from, char* to) {
  FILE *fp = fopen(from,"r");
  if (fp == NULL) {
     return 1;
  }
  FILE *fp2 = fopen(to,"w");
  if (fp2 == NULL) {
     fclose(fp);
     return 1;
  }
  int c = fgetc(fp);
  while (c != EOF) {
    if (fputc(c, fp2) == EOF) { fclose(fp); fclose(fp2); return 1; }
    c = fgetc(fp);
  }
  int error = ferror(fp);
  if (fclose(fp) != 0) error = 1;
  if (fclose(fp2) != 0) error = 1;
  return error;
}

// The audio destination belongs to the entire BMC64, not a machine/config.
// The startup parser already accepts audio_out=hdmi|auto|analog.
int switch_global_audio_get(void) {
  FILE *fp = fopen("/cmdline.txt", "r");
  if (fp == NULL) return 0; // HDMI is the global default.
  char line[CONFIG_TXT_LINE_LEN];
  int result = 0;
  while (fgets(line, sizeof(line), fp)) {
    if (line[0] == '#') continue;
    char *token = strtok(line, " \t\r\n");
    while (token != NULL) {
      if (strncmp(token, "audio_out=", 10) == 0) {
        const char *value = token + 10;
        result = strcmp(value, "auto") == 0 ? 1 :
                 strcmp(value, "analog") == 0 ? 2 : 0;
        fclose(fp);
        return result;
      }
      token = strtok(NULL, " \t\r\n");
    }
  }
  fclose(fp);
  return result;
}

int switch_global_audio_set(int choice) {
  const char *value = choice == 0 ? "hdmi" :
                      choice == 1 ? "auto" :
                      choice == 2 ? "analog" : NULL;
  if (value == NULL) return 1;
  FILE *src = fopen("/cmdline.txt", "r");
  if (src == NULL) return 1;
  FILE *dst = fopen("/cmdline.audio.new", "w");
  if (dst == NULL) { fclose(src); return 1; }
  char line[CONFIG_TXT_LINE_LEN];
  char rebuilt[CONFIG_TXT_LINE_LEN];
  int changed = 0, error = 0, backed_up = 0;
  while (fgets(line, sizeof(line), src)) {
    // Refuse oversized lines rather than risk truncating boot arguments.
    if (strchr(line, '\n') == NULL && !feof(src)) {
      error = 1;
      break;
    }
    if (!changed && line[0] != '#' && line[0] != '\n' && line[0] != '\r') {
      rebuilt[0] = '\0';
      char *token = strtok(line, " \t\r\n");
      while (token != NULL) {
        if (strncmp(token, "audio_out=", 10) != 0) {
          size_t used = strlen(rebuilt), length = strlen(token);
          if (used + length + 32 >= sizeof(rebuilt)) { error = 1; break; }
          if (used) strcat(rebuilt, " ");
          strcat(rebuilt, token);
        }
        token = strtok(NULL, " \t\r\n");
      }
      if (error) break;
      if (rebuilt[0]) strcat(rebuilt, " ");
      strcat(rebuilt, "audio_out=");
      strcat(rebuilt, value);
      if (fprintf(dst, "%s\n", rebuilt) < 0) { error = 1; break; }
      changed = 1;
    } else if (fputs(line, dst) == EOF) {
      error = 1;
      break;
    }
  }
  if (ferror(src)) error = 1;
  if (!error && !changed && fprintf(dst, "audio_out=%s\n", value) < 0)
    error = 1;
  if (fclose(dst) != 0) error = 1;
  fclose(src);
  if (!error) {
    // Retain a recoverable copy of the previous boot command line.
    if (copy_file("/cmdline.txt", "/cmdline.audio.bak") != 0)
      error = 1;
    else {
      backed_up = 1;
      if (copy_file("/cmdline.audio.new", "/cmdline.txt") != 0)
        error = 1;
    }
  }
  if (error && backed_up) {
    // Restore when an update fails after the backup was created.
    FILE *backup = fopen("/cmdline.audio.bak", "r");
    if (backup != NULL) {
      fclose(backup);
      copy_file("/cmdline.audio.bak", "/cmdline.txt");
    }
  }
  unlink("/cmdline.audio.new");
  return error;
}

int switch_calibrated_timing(int ntsc, unsigned long cycles, int *changed_out) {
  if (changed_out) *changed_out = 0;
  if ((ntsc != 0 && ntsc != 1) || (cycles && (cycles < 500000 || cycles > 2500000))) return 1;
  FILE *src = fopen("/cmdline.txt", "r");
  if (src == NULL) return 1;
  // Keep the original timing with the boot arguments, so a same-standard
  // Config switch restores it without reapplying a different HDMI mode.
  char base_timing[40] = "", base_cycles[40] = "";
  char saved_timing[40] = "", saved_cycles[40] = "";
  char scan[CONFIG_TXT_LINE_LEN];
  while (fgets(scan, sizeof(scan), src)) {
    if (scan[0] == '#') continue;
    char *t = strtok(scan, " \t\r\n");
    while (t) {
      if (!strncmp(t, "machine_timing=", 15)) snprintf(base_timing, sizeof(base_timing), "%s", t+15);
      if (!strncmp(t, "cycles_per_refresh=", 19) && !base_cycles[0]) snprintf(base_cycles, sizeof(base_cycles), "%s", t+19);
      if (!strncmp(t, "cycles_per_second=", 18)) snprintf(base_cycles, sizeof(base_cycles), "%s", t+18);
      if (!strncmp(t, "e64_timing_base=", 16)) snprintf(saved_timing, sizeof(saved_timing), "%s", t+16);
      if (!strncmp(t, "e64_cycles_base=", 16)) snprintf(saved_cycles, sizeof(saved_cycles), "%s", t+16);
      t = strtok(NULL, " \t\r\n");
    }
  }
  if (ferror(src)) { fclose(src); return 1; }
  if (!cycles && !saved_timing[0]) { fclose(src); return 0; }
  if (saved_timing[0]) {
    strcpy(base_timing, saved_timing);
    strcpy(base_cycles, saved_cycles);
  }
  if (!base_timing[0]) { fclose(src); return 1; }
  rewind(src);
  char value[224];
  if (cycles) {
    snprintf(value, sizeof(value), "machine_timing=%s-custom cycles_per_second=%lu e64_timing_base=%s e64_cycles_base=%s",
             ntsc ? "ntsc" : "pal", cycles, base_timing, base_cycles[0] ? base_cycles : "none");
  } else {
    snprintf(value, sizeof(value), "machine_timing=%s%s%s", base_timing,
             base_cycles[0] && strcmp(base_cycles, "none") ? " cycles_per_second=" : "",
             base_cycles[0] && strcmp(base_cycles, "none") ? base_cycles : "");
  }
  FILE *dst = fopen("/cmdline.timing.new", "w");
  if (dst == NULL) { fclose(src); return 1; }
  char line[CONFIG_TXT_LINE_LEN];
  char rebuilt[CONFIG_TXT_LINE_LEN];
  int changed = 0, error = 0, backed_up = 0;
  while (fgets(line, sizeof(line), src)) {
    // Refuse oversized lines rather than risk truncating boot arguments.
    if (strchr(line, '\n') == NULL && !feof(src)) {
      error = 1;
      break;
    }
    if (!changed && line[0] != '#' && line[0] != '\n' && line[0] != '\r') {
      rebuilt[0] = '\0';
      char *token = strtok(line, " \t\r\n");
      while (token != NULL) {
        if (strncmp(token, "machine_timing=", 15) != 0 &&
            strncmp(token, "cycles_per_second=", 18) != 0 &&
            strncmp(token, "cycles_per_refresh=", 19) != 0 &&
            strncmp(token, "e64_timing_base=", 16) != 0 &&
            strncmp(token, "e64_cycles_base=", 16) != 0) {
          size_t used = strlen(rebuilt), length = strlen(token);
          if (used + length + strlen(value) + 2 >= sizeof(rebuilt)) { error = 1; break; }
          if (used) strcat(rebuilt, " ");
          strcat(rebuilt, token);
        }
        token = strtok(NULL, " \t\r\n");
      }
      if (error) break;
      if (rebuilt[0]) strcat(rebuilt, " ");
      strcat(rebuilt, value);
      if (fprintf(dst, "%s\n", rebuilt) < 0) { error = 1; break; }
      changed = 1;
    } else if (fputs(line, dst) == EOF) {
      error = 1;
      break;
    }
  }
  if (ferror(src)) error = 1;
  if (!error && !changed && fprintf(dst, "%s\n", value) < 0)
    error = 1;
  if (fclose(dst) != 0) error = 1;
  fclose(src);
  if (!error) {
    // Retain a recoverable copy of the previous boot command line.
    if (copy_file("/cmdline.txt", "/cmdline.timing.bak") != 0)
      error = 1;
    else {
      backed_up = 1;
      if (copy_file("/cmdline.timing.new", "/cmdline.txt") != 0)
        error = 1;
    }
  }
  if (error && backed_up) {
    // Restore when an update fails after the backup was created.
    FILE *backup = fopen("/cmdline.timing.bak", "r");
    if (backup != NULL) {
      fclose(backup);
      copy_file("/cmdline.timing.bak", "/cmdline.txt");
    }
  }
  unlink("/cmdline.timing.new");
  if (!error && changed_out) *changed_out = 1;
  return error;
}

static int new_section(struct machine_entry** new_section, char* line) {
  char* header = &line[1];
  for (int i=0;i<strlen(header);i++) {
    if (header[i]==']') { header[i] = '\0'; break; }
  }
  header = trim(header);
  char full_header[HEADER_LEN];
  snprintf(full_header, sizeof(full_header), "%s", header);

  char *video_nam = trim(strtok(header, "/"));
  if (video_nam == NULL) return 1;
  char *video_std = trim(strtok(NULL, "/"));
  if (video_std == NULL) return 1;
  char *video_out = trim(strtok(NULL, "/"));
  if (video_out == NULL) return 1;
  char *video_res = trim(strtok(NULL, "/"));
  if (video_res == NULL) return 1;

  struct machine_entry* entry =
     (struct machine_entry*) malloc(sizeof(struct machine_entry));

  char desc[DESC_LEN];
  entry->id = next_id();
  entry->class = BMC64_MACHINE_CLASS_UNKNOWN;
  entry->video_standard = BMC64_VIDEO_STANDARD_UNKNOWN;
  entry->video_out = BMC64_VIDEO_OUT_UNKNOWN;

  strcpy(entry->desc,video_std);
  strcat(entry->desc," ");
  strcat(entry->desc,video_out);
  strcat(entry->desc," ");
  strcat(entry->desc,video_res);
  char mode_display[DESC_LEN];
  unsigned out = 0;
  for (const char *p = entry->desc; *p && out + 4 < sizeof(mode_display); p++) {
    if (*p == '@') {
      while (out && mode_display[out - 1] == ' ') out--;
      mode_display[out++] = ' ';
      mode_display[out++] = '@';
      mode_display[out++] = ' ';
      while (p[1] == ' ') p++;
    } else {
      if (*p == 'H' && p[1] == 'z' && out && mode_display[out - 1] != ' ')
        mode_display[out++] = ' ';
      mode_display[out++] = *p;
    }
  }
  mode_display[out] = 0;
  snprintf(entry->desc, sizeof(entry->desc), "%s", mode_display);
  strcpy(entry->header, full_header);

  entry->options = NULL;
  entry->next = NULL;
   if (strcasecmp(video_nam,"c64") == 0)
      entry->class = BMC64_MACHINE_CLASS_C64;
  if (strcasecmp(video_std,"ntsc") == 0)
     entry->video_standard = BMC64_VIDEO_STANDARD_NTSC;
  else if (strcasecmp(video_std,"pal") == 0)
     entry->video_standard = BMC64_VIDEO_STANDARD_PAL;

  if (strcasecmp(video_out,"hdmi") == 0)
     entry->video_out = BMC64_VIDEO_OUT_HDMI;
  else if (strcasecmp(video_out,"composite") == 0)
     entry->video_out = BMC64_VIDEO_OUT_COMPOSITE;
  else if (strcasecmp(video_out,"dpi") == 0)
     entry->video_out = BMC64_VIDEO_OUT_DPI;

  *new_section = entry;
  return 0;
}

static int append_to_section(struct machine_entry* section, char* line) {
  if (!section) return 0;

  line = trim(line);
  if (strlen(line) == 0) return 0;

  char *key = trim(strtok(line, "="));
  char *value = trim(strtok(NULL, "="));

  if (key == NULL || value == NULL) {
    return 1;
  }

  struct machine_option* option =
     (struct machine_option*) malloc(sizeof(struct machine_option));

  strncpy (option->key, key, KEY_LEN-1);
  strncpy (option->value, value, VALUE_LEN-1);
  option->next = NULL;

  struct machine_option* prev = NULL;
  struct machine_option* ptr = section->options;
  while (ptr) {
     prev = ptr;
     ptr = ptr->next;
  }
  if (prev)
    prev->next = option;
  else
    section->options = option;

  return 0;
}

// Load and parse the machine config from machines.txt
// Returns non-zero on error.
int load_machines(struct machine_entry** head) {
  FILE* fp = fopen("/system/machines.txt","r");
  if (fp == NULL) {
     *head = NULL;
     return 1;
  }

  char line[CONFIG_TXT_LINE_LEN];

  struct machine_entry* current_section = NULL;
  struct machine_entry* first_section = NULL;
  entry_id = 0;
  while (fgets(line, CONFIG_TXT_LINE_LEN - 1, fp)) {
    if (feof(fp))
      break;
    if (strlen(line) == 0)
      continue;
    if (line[0] == '#')
      continue;

    if (line[0] == '[') {
      struct machine_entry* section;
      if (new_section(&section, line) == 0) {
        if (current_section != NULL) {
           current_section->next = section;
        }
        current_section = section;
        if (!first_section) {
           first_section = current_section;
        }
      }
    } else {
      append_to_section(current_section, line);
    }
  }

  *head = first_section;
  fclose(fp);
  return 0;
}

void free_machines(struct machine_entry* head) {
  struct machine_entry* ptr = head;
  struct machine_entry* next_ptr;
  while (ptr) {
     struct machine_option* opt = ptr->options;
     struct machine_option* next_opt;
     while (opt) {
        next_opt = opt->next;
        free(opt);
        opt = next_opt;
     }
     next_ptr = ptr->next;
     free(ptr);
     ptr = next_ptr;
  }
}

static struct machine_option* find_option(const char *key,
                                          struct machine_option *head) {
  struct machine_option* opt = head;
  while (opt) {
    if(strcmp(opt->key, key) == 0) {
      return opt;
    }
    opt=opt->next;
  }
  return NULL;
}

// Single line version of apply_override where each param
// is one per line.  This is a non-destructive update in
// that existing parameters will not be altered other
// than those found in the options list for the machine
// entry.  However, the following options will be removed
// unless machine_timing=hdmi-custom or pal-custom is set:
// hdmi_cvt, hdmi_timings, dpi_timings
static void apply_override_s(char *line,
                             struct machine_entry *head, char* kernel_name,
                             struct s_cfg_flags* cfg_flags, int is_custom) {
  if (strlen(line) > 0 && line[0] != '#') {
    char *key = strtok(line, "=");
    char *value = strtok(NULL, "=");
    if (key == NULL || value == NULL) {
       return;
    }

    // If we find a kernal name, overwrite it now.
    if(strcmp(key, "kernel") == 0) {
       if (cfg_flags->need_kernel) {
          snprintf(line, CONFIG_TXT_LINE_LEN, "kernel=%s\n",kernel_name);
          cfg_flags->have_kernel = 1;
       } else {
          line[0] = '\0';
       }
       return;
    }

    // gpu_mem: a config can raise the floor (machines.txt gpu_mem=N) but
    // never lowers a bigger value the user chose themselves. Any config
    // that doesn't ask resets the split back to the BMC64 default.
    if(strcmp(key, "gpu_mem") == 0) {
       cfg_flags->have_gpu_mem = 1;
       struct machine_option* gm = find_option("gpu_mem", head->options);
       int want = DEFAULT_GPU_MEM;
       if (gm) {
          int floor = atoi(gm->value);
          int current = atoi(value);
          want = current > floor ? current : floor;
       }
       snprintf(line, CONFIG_TXT_LINE_LEN, "gpu_mem=%d\n", want);
       return;
    }

    // Make sure we remove custom hdmi stuff unless we are using a custom mode
    if(strcmp(key, "hdmi_timings") == 0) {
       cfg_flags->have_hdmi_timings = 1;
       if (!is_custom || head->video_out != BMC64_VIDEO_OUT_HDMI) {
          cfg_flags->have_hdmi_timings = 0;
          line[0] = '\0';
          return;
       }
    }
    if(strcmp(key, "hdmi_cvt") == 0) {
       cfg_flags->have_cvt = 1;
       if (!is_custom || head->video_out != BMC64_VIDEO_OUT_HDMI) {
          cfg_flags->have_cvt = 0;
          line[0] = '\0';
          return;
       }
    }
    if(strcmp(key, "dpi_timings") == 0) {
       cfg_flags->have_dpi_timings = 1;
       if (!is_custom || head->video_out != BMC64_VIDEO_OUT_DPI) {
          cfg_flags->have_dpi_timings = 0;
          line[0] = '\0';
          return;
       }
    }
    if(strcmp(key, "enable_dpi_lcd") == 0) {
       cfg_flags->have_enable_dpi_lcd = 1;
       if (head->video_out != BMC64_VIDEO_OUT_DPI) {
          cfg_flags->have_enable_dpi_lcd = 0;
          line[0] = '\0';
          return;
       }
    }
    if(strcmp(key, "display_default_lcd") == 0) {
       cfg_flags->have_display_default_lcd = 1;
       if (head->video_out != BMC64_VIDEO_OUT_DPI) {
          cfg_flags->have_display_default_lcd = 0;
          line[0] = '\0';
          return;
       }
    }
    if(strcmp(key, "dpi_group") == 0) {
       cfg_flags->have_dpi_group = 1;
       if (head->video_out != BMC64_VIDEO_OUT_DPI) {
          cfg_flags->have_dpi_group = 0;
          line[0] = '\0';
          return;
       }
    }
    if(strcmp(key, "dpi_mode") == 0) {
       cfg_flags->have_dpi_mode = 1;
       if (head->video_out != BMC64_VIDEO_OUT_DPI) {
          cfg_flags->have_dpi_mode = 0;
          line[0] = '\0';
          return;
       }
    }
    if(strcmp(key, "dpi_output_format") == 0) {
       cfg_flags->have_dpi_output_format = 1;
       if (head->video_out != BMC64_VIDEO_OUT_DPI) {
          cfg_flags->have_dpi_output_format = 0;
          line[0] = '\0';
          return;
       }
    }

    struct machine_option* found = find_option(key, head->options);
    char new_option[OPTION_SCRATCH_LEN];
    if (found) {
       snprintf(new_option, OPTION_SCRATCH_LEN, "%s=%s\n", key, found->value);
    } else {
       // Value already has newline since it came from original input.
       snprintf(new_option, OPTION_SCRATCH_LEN, "%s=%s", key, value);
    }
    strcpy(line, new_option);
  }
}


// Multi param version of apply_override where there are
// multiple parameters on a single line of text. This is
// a non-destructive update in that existing parameters
// will not be altered other than those found in the
// options list for the machine entry.  The following
// options are removed first:
// cycles_per_second, cycles_per_refresh, machine_timing
// serial, demo, audio_out, disk_partition
// Machine definitions must not own global network/service preferences.
static int global_network_option(const char *key) {
  static const char *prefixes[] = {"network", "wifi", "wlan", "ethernet", "webui", "ntp", "dhcp"};
  for (unsigned i = 0; i < sizeof(prefixes) / sizeof(prefixes[0]); ++i)
    if (!strncmp(key, prefixes[i], strlen(prefixes[i]))) return 1;
  return !strcmp(key, "hostname") || !strcmp(key, "ip_address") ||
         !strcmp(key, "netmask") || !strcmp(key, "gateway") || !strcmp(key, "dns") ||
         !strcmp(key, "timezone_offset_minutes");
}

static int apply_override_m(char *line, struct machine_entry *head,
                            struct s_cfg_flags* cfg_flags) {
  if (strlen(line) > 0 && line[0] != '#') {
    char replacement[CONFIG_TXT_LINE_LEN];
    char new_option[CONFIG_TXT_LINE_LEN];

    replacement[0] = '\0';

    line = trim(line);
    int need_space = 0;
    char *context;
    for (char *next_option = strtok_r(line, " \t", &context); next_option;
         next_option = strtok_r(NULL, " \t", &context)) {
      char *key = next_option;
      char *value = strchr(key, '=');
      if (value) *value++ = '\0';

      if (strcmp(key,"cycles_per_second") == 0) { cfg_flags->have_cycles_per_second = 1; }
      if (strcmp(key,"machine_timing") == 0) { cfg_flags->have_machine_timing = 1; }
      if (strcmp(key,"serial") == 0) { cfg_flags->have_serial = 1; }
      if (strcmp(key,"demo") == 0) { cfg_flags->have_demo = 1; }
      if (strcmp(key,"audio_out") == 0) { cfg_flags->have_audio_out = 1; }
      if (strcmp(key,"disk_partition") == 0) { cfg_flags->have_disk_partition = 1; }
      if (strcmp(key,"enable_dpi") == 0) { cfg_flags->have_enable_dpi = 1; }
      if (strcmp(key,"scaling_params") == 0) { cfg_flags->have_scaling_params = 1; }
      if (strcmp(key,"scaling_params2") == 0) { cfg_flags->have_scaling_params2 = 1; }
      if (strcmp(key,"raster_skip") == 0) { cfg_flags->have_raster_skip = 1; }
      if (strcmp(key,"raster_skip2") == 0) { cfg_flags->have_raster_skip2 = 1; }

      struct machine_option* found = find_option(key, head->options);
      if (found && strcmp(key, "audio_out") != 0 && !global_network_option(key)) {
         if (need_space) { strcat(replacement," ");}
         snprintf(new_option, sizeof(new_option), "%s=%s", key, found->value);
         if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
         need_space=1;
      } else {
         // Leave params we don't know about unchanged.
         if (strcmp(key,"cycles_per_refresh")!=0 &&
             strcmp(key,"cycles_per_second")!=0 &&
             strcmp(key,"machine_timing")!=0 &&
             strcmp(key,"serial")!=0 &&
             strcmp(key,"demo")!=0 &&
             strcmp(key,"disk_partition")!=0 &&
             strcmp(key,"enable_dpi")!=0 &&
             strcmp(key,"raster_skip")!=0 &&
             strcmp(key,"raster_skip2")!=0 &&
             strcmp(key,"scaling_params")!=0 &&
             strcmp(key,"scaling_params2")!=0) {
            if (need_space) { strcat(replacement," "); }
            snprintf(new_option, sizeof(new_option), "%s=%s", key, value);
            if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
            need_space=1;
         }
      }

    }

    // Now add params that should be present according to the entry.
    if (!cfg_flags->have_cycles_per_second) {
       struct machine_option* found = find_option("cycles_per_second", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_machine_timing) {
       struct machine_option* found = find_option("machine_timing", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_serial) {
       struct machine_option* found = find_option("serial", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_demo) {
       struct machine_option* found = find_option("demo", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_disk_partition) {
       struct machine_option* found = find_option("disk_partition", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_enable_dpi) {
       struct machine_option* found = find_option("enable_dpi", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_scaling_params) {
       struct machine_option* found = find_option("scaling_params", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_scaling_params2) {
       struct machine_option* found = find_option("scaling_params2", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_raster_skip) {
       struct machine_option* found = find_option("raster_skip", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }
    if (!cfg_flags->have_raster_skip2) {
       struct machine_option* found = find_option("raster_skip2", head->options);
       if (found) {
          if (need_space) { strcat(replacement," "); }
          snprintf(new_option, sizeof(new_option), "%s=%s", found->key, found->value);
          if (strlen(replacement) + strlen(new_option) >= sizeof(replacement) - 1) return 1;
          strcat(replacement, new_option);
          need_space=1;
       }
    }

    strcat(replacement, "\n");
    strcpy(line, replacement);
  }
  return 0;
}

static int apply_cmdline(struct machine_entry* head, struct s_cfg_flags *cfg_flags) {
  FILE* fp = fopen("/cmdline.txt","r");
  if (fp == NULL) {
     return ERROR_1;
  }

  FILE* fp2 = fopen("/cmdline.new","w");
  if (fp2 == NULL) {
     fclose(fp);
     return ERROR_2;
  }

  char line[CONFIG_TXT_LINE_LEN];

  int error = 0;
  while (fgets(line, sizeof(line), fp)) {
    if ((!strchr(line, '\n') && !feof(fp)) ||
        apply_override_m(line, head, cfg_flags) != 0 || fprintf(fp2, "%s", line) < 0) {
      error = 1;
      break;
    }
  }
  if (ferror(fp)) error = 1;
  if (fclose(fp) != 0) error = 1;
  if (fclose(fp2) != 0) error = 1;
  if (error) { unlink("/cmdline.new"); return ERROR_3; }

  if (copy_file("/cmdline.new","/cmdline.txt")) {
     return ERROR_3;
  }
  if (unlink("/cmdline.new")) {
     return ERROR_4;
  }
  return 0;
}

// Reads config.txt and creates config.txt.new, overwriting
// any config.txt related items from the machine_entry. If
// kernel param is absent, it will be added.
static int apply_config(struct machine_entry* head, int pi_model, struct s_cfg_flags *cfg_flags) {
  char kernel_name[VALUE_LEN];
  switch (pi_model) {
    case 0:
    case 1:
       strcpy(kernel_name,"kernel.img");
       break;
    case 2:
       strcpy(kernel_name,"kernel7.img");
       break;
    case 3:
       strcpy(kernel_name,"kernel8-32.img");
       break;
    case 4:
       strcpy(kernel_name,"kernel7l.img");
       break;
    default:
       return ERROR_5;
  }
   if (head->class != BMC64_MACHINE_CLASS_C64) {
      return ERROR_6;
   }
  FILE* fp = fopen("/config.txt","r");
  if (fp == NULL) {
     return ERROR_7;
  }

  FILE* fp2 = fopen("/config.new","w");
  if (fp2 == NULL) {
     fclose(fp);
     return ERROR_8;
  }

  int is_custom = 0;
  struct machine_option* found = find_option("machine_timing", head->options);
  if (found && (strcmp(found->value, "ntsc-custom") == 0 || strcmp(found->value,"pal-custom") == 0)) {
    is_custom = 1;
  }

  char line[CONFIG_TXT_LINE_LEN];
  cfg_flags->need_kernel = 0;
  while (fgets(line, CONFIG_TXT_LINE_LEN - 1, fp)) {
    if (feof(fp))
      break;

    apply_override_s(line, head, kernel_name, cfg_flags, is_custom);
    fprintf(fp2,"%s",line);
  }

  // This may have been overwritten by the pass above. If not present, add
  // now.
  if (!cfg_flags->have_kernel && cfg_flags->need_kernel) {
    fprintf(fp2,"kernel=%s\n", kernel_name);
  }

  // If config.txt had no gpu_mem line at all, add the floor this config
  // asks for (e.g. PET 1080p). Configs that don't ask inherit the
  // firmware default and need no line.
  if (!cfg_flags->have_gpu_mem) {
    found = find_option("gpu_mem", head->options);
    if (found) {
       int floor = atoi(found->value);
       fprintf(fp2,"gpu_mem=%d\n", floor > DEFAULT_GPU_MEM ? floor : DEFAULT_GPU_MEM);
    }
  }

  // Ensure we add custom timings if present.
  if (is_custom) {
    if (!cfg_flags->have_hdmi_timings) {
       found = find_option("hdmi_timings", head->options);
       if (found) {
          fprintf(fp2,"hdmi_timings=%s\n", found->value);
       }
    }
    if (!cfg_flags->have_dpi_timings) {
       found = find_option("dpi_timings", head->options);
       if (found) {
          fprintf(fp2,"dpi_timings=%s\n", found->value);
       }
    }
    if (!cfg_flags->have_cvt) {
       found = find_option("hdmi_cvt", head->options);
       if (found) {
          fprintf(fp2,"hdmi_cvt=%s\n", found->value);
       }
    }
  }

  // Ensure we add dpi if necessary
  if (head->video_out == BMC64_VIDEO_OUT_DPI) {
     found = find_option("enable_dpi_lcd", head->options);
     if (found) {
        fprintf(fp2,"enable_dpi_lcd=%s\n", found->value);
     }

     found = find_option("display_default_lcd", head->options);
     if (found) {
        fprintf(fp2,"display_default_lcd=%s\n", found->value);
     }

     found = find_option("dpi_group", head->options);
     if (found) {
        fprintf(fp2,"dpi_group=%s\n", found->value);
     }

     found = find_option("dpi_mode", head->options);
     if (found) {
        fprintf(fp2,"dpi_mode=%s\n", found->value);
     }

     found = find_option("dpi_output_format", head->options);
     if (found) {
        fprintf(fp2,"dpi_output_format=%s\n", found->value);
     }
  }

  fclose(fp);
  fclose(fp2);

  if (copy_file("/config.new","/config.txt")) {
    return ERROR_9;
  }
  if (unlink("/config.new")) {
    return ERROR_10;
  }
  return 0;
}

int switch_apply_files(struct machine_entry* head) {
  // Common is shared across targets: ask the kernel bridge, not a build macro.
  // Reject before touching either boot file, even with automatic control disabled.
  if (head->video_out == BMC64_VIDEO_OUT_DPI && !fan_dpi_allowed()) return -1;
  struct s_cfg_flags cfg_flags;
  memset(&cfg_flags, 0, sizeof(struct s_cfg_flags));

  int status = apply_config(head, circle_get_model(), &cfg_flags);
  status |= apply_cmdline(head, &cfg_flags);
  return status;
}


// Capture boot inputs before Start Once restores next-boot machine files.
// This is read-only and has no effect on mode switching.
static char boot_video_config[16384], boot_video_cmdline[4096];
static int boot_video_captured;
void switch_capture_video_mode(void) {
  if (boot_video_captured) return;
  boot_video_captured = 1;
  const char *files[] = {"/config.txt", "/cmdline.txt"};
  char *buffers[] = {boot_video_config, boot_video_cmdline};
  size_t sizes[] = {sizeof(boot_video_config), sizeof(boot_video_cmdline)};
  for (int i = 0; i < 2; ++i) {
    FILE *fp = fopen(files[i], "r");
    if (!fp) continue;
    size_t n = fread(buffers[i], 1, sizes[i] - 1, fp);
    buffers[i][n] = 0;
    if (ferror(fp) || !feof(fp)) buffers[i][0] = 0;
    fclose(fp);
  }
}
static int boot_video_value(const char *key, char *out, size_t capacity) {
  int found = 0;
  out[0] = 0;
  const char *buffers[] = {boot_video_config, boot_video_cmdline};
  for (int i = 0; i < 2; ++i) {
    const char *p = buffers[i];
    while (*p) {
      while (isspace((unsigned char)*p)) ++p;
      if (*p == '#') { while (*p && *p != '\n') ++p; continue; }
      const char *end = p;
      if (i) { while (*end && !isspace((unsigned char)*end)) ++end; }
      else { while (*end && *end != '\n' && *end != '\r') ++end; }
      size_t k = strlen(key);
      if ((size_t)(end-p) > k && !strncmp(p, key, k) && p[k] == '=') {
        size_t n = (size_t)(end - p - k - 1);
        while (n && isspace((unsigned char)p[k+1+n-1])) --n;
        if (n < capacity) { memcpy(out, p+k+1, n); out[n] = 0; found = 1; }
      }
      if (end == p && *p) ++p; else p = end;
    }
  }
  return found;
}
int switch_video_mode_active(const struct machine_entry *entry) {
  int matched = 0;
  if (!boot_video_captured || !boot_video_config[0] || !boot_video_cmdline[0]) return 0;
  for (const struct machine_option *opt = entry->options; opt; opt = opt->next) {
    if (strncmp(opt->key, "hdmi_", 5) && strncmp(opt->key, "dpi_", 4) &&
        strncmp(opt->key, "sdtv_", 5) && strcmp(opt->key, "enable_dpi") &&
        strcmp(opt->key, "enable_dpi_lcd") && strcmp(opt->key, "display_default_lcd") &&
        strcmp(opt->key, "machine_timing")) continue;
    char value[512];
    if (!boot_video_value(opt->key, value, sizeof(value))) return 0;
    if (!strcmp(opt->key, "machine_timing") && strstr(value, "-custom"))
      boot_video_value("e64_timing_base", value, sizeof(value));
    if (strcmp(value, opt->value)) return 0;
    ++matched;
  }
  return matched > 0;
}
