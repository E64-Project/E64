// Immutable firmware configs. No SD files are created for their settings.
#include "configs_internal.h"
#include <string.h>
// Index 1 is a hidden, protected compatibility identity for old PAL selections.
// Normal enumeration exposes only index 0: Default. Neither has SD files.
static const ConfigInfo factory[] = {
 {CONFIGS_FACTORY_NTSC, "Default", "", "C64/NTSC/HDMI/VICE 768x525@59.827Hz", CONFIG_START_SWITCH},
 {CONFIGS_FACTORY_PAL, "Default", "", "C64/PAL/HDMI/VICE 720p@50Hz", CONFIG_START_SWITCH}
};
int configs_is_factory(const char *id) {
 return id && (!strcmp(id, CONFIGS_FACTORY_NTSC) || !strcmp(id, CONFIGS_FACTORY_PAL));
}
int configs_running_is_factory(void) { return configs_is_factory(configs_running()->id); }
const ConfigInfo *configs_factory_info(int i) { return i >= 0 && i < 2 ? &factory[i] : 0; }
// Shared E64 settings, parsed through the ordinary settings loader.
const char *configs_factory_settings(void) {
 return "keyboard_layout=1\nkeyboard_layout_mapping=1\ngpio_config=1\n"
        "port_1=3\nport_2=4\nport_3=0\nport_4=0\n"
        "auto_drive_type_8=1\nauto_drive_type_9=1\nauto_drive_type_10=1\nauto_drive_type_11=1\n"
        "palette=11\n" // Godot, shared by both protected factory Configs.
        "h_center_0=0\nv_center_0=0\nh_border_0=32\nv_border_0=20\n"
        "h_stretch_0=1600\nv_stretch_0=1000\n"
        "scaling_interp=0\nuse_int_scaling_0=0\nvolume=100\n";
}
// VICE defaults supply empty media slots; skip all saved vice.ini files first.
int configs_factory_resources(int (*si)(const char *, int),
                              int (*ss)(const char *, const char *)) {
 static const struct { const char *key; int value; } ints[] = {
  // Final E64 audio baseline; drive volume uses the existing UI maximum.
  {"SoundVolume",100}, {"DriveSoundEmulation",1}, {"DriveSoundEmulationVolume",1000},
  {"VICIIFilter",0}, {"IEEE488",0}, {"CartridgeType",-1}, {"Drive8AutoType",1},
  {"Drive9AutoType",1}, {"Drive10AutoType",1}, {"Drive11AutoType",1}
 };
 static const struct { const char *key, *value; } strings[] = {
  {"BasicName","basic"}, {"KernalName","kernal"}, {"ChargenName","chargen"},
  {"CartridgeFile",""}
 };
 for (unsigned i=0;i<sizeof(ints)/sizeof(ints[0]);i++) if(si(ints[i].key,ints[i].value)<0)return -1;
 for (unsigned i=0;i<sizeof(strings)/sizeof(strings[0]);i++) if(ss(strings[i].key,strings[i].value)<0)return -1;
 return 0;
}
