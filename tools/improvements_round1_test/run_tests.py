#!/usr/bin/env python3
"""Execute Round 1 native production helpers with host-only fixtures."""
from pathlib import Path
import re,subprocess,tempfile
R=Path(__file__).resolve().parents[2]
def fn(p,n):
 s=(R/p).read_text();m=re.search(r'^(?:static )?[\w *]+\b'+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 return s[m.start():s.index('\n}',m.end())+2]
menu='third_party/common/menu.c';api='third_party/vice-3.3/src/arch/raspi/vice_api.c';switch='third_party/common/menu_switch.c'
active=fn(api,'emux_active_drive_rom');ids=sorted(set(re.findall(r'\bMENU_[A-Z0-9_]+',active)))
code=r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <strings.h>
#include <cctype>
#include <string>
#include <vector>
#include <map>
#include "ui.h"
#include "menu_theme.h"
enum { @IDS@ };
static const char *live_name;
static std::string saved_ini,seen_resource;
static FILE *ini_file;
static int resources_get_string(const char *resource,const char **name){seen_resource=resource;*name=live_name;return live_name?0:-1;}
static const char *configs_vice_config(){return "/fixture/vice.ini";}
static FILE *test_open(const char *name,const char *mode){assert(!strcmp(name,"/fixture/vice.ini")&&!strcmp(mode,"r"));ini_file=tmpfile();assert(ini_file);fputs(saved_ini.c_str(),ini_file);rewind(ini_file);return ini_file;}
static int sysfile_locate(const char *name,char **out){if(!strcmp(name,"missing"))return -1;std::string p=strchr(name,':')?name:std::string("SD:/drives/")+name;*out=strdup(p.c_str());return 0;}
static void lib_free(void *p){free(p);}
#define fopen test_open
'''.replace('@IDS@',','.join(ids))+active+r'''
#undef fopen
'''+fn(menu,'rom_browser_path')+r'''
static char boot_video_config[16384],boot_video_cmdline[4096];
static int boot_video_captured;
struct machine_option{char key[32],value[96];machine_option *next;};
struct machine_entry{machine_option *options;};
'''+fn(switch,'boot_video_value')+'\n'+fn(switch,'switch_video_mode_active')+r'''
int main(){
 char path[1024];live_name="USB:/drives/live.rom";saved_ini="[C64]\nDosName1541=\"saved.rom\"\n";
 assert(emux_active_drive_rom(MENU_DRIVE_ROM_FILE_1541,path,sizeof(path))&&!strcmp(path,live_name));
 assert(seen_resource=="DosName1541");
 // Drive ROM resources are shared by model, not per-drive-unit resources.
 assert(emux_active_drive_rom(MENU_DRIVE_ROM_FILE_1541II,path,sizeof(path))&&seen_resource=="DosName1541ii");
 live_name=nullptr;assert(emux_active_drive_rom(MENU_DRIVE_ROM_FILE_1541,path,sizeof(path))&&!strcmp(path,"SD:/drives/saved.rom"));
 live_name="missing";assert(!emux_active_drive_rom(MENU_DRIVE_ROM_FILE_1541,path,sizeof(path)));
 live_name="long.rom";assert(!emux_active_drive_rom(MENU_DRIVE_ROM_FILE_1541,path,2));
 assert(!emux_active_drive_rom(-1,path,sizeof(path)));
 assert(!strcasecmp(rom_browser_path("SD:/drives/Same.rom"),rom_browser_path("./drives/same.rom")));
 assert(strcasecmp(rom_browser_path("USB:/drives/same.rom"),rom_browser_path("SD:/drives/same.rom")));
 assert(strcasecmp(rom_browser_path("SD:/other/same.rom"),rom_browser_path("SD:/drives/same.rom")));
 machine_option a={"hdmi_group","2",nullptr},b={"hdmi_mode","87",nullptr},c={"machine_timing","ntsc-hdmi",nullptr};a.next=&b;b.next=&c;machine_entry entry={&a};
 boot_video_captured=1;strcpy(boot_video_config,"# ignored\nhdmi_group=1\nhdmi_group=2\nhdmi_mode=87\n");strcpy(boot_video_cmdline,"machine_timing=ntsc-hdmi root=test");
 assert(switch_video_mode_active(&entry));strcpy(b.value,"82");assert(!switch_video_mode_active(&entry));strcpy(b.value,"87");
 strcpy(boot_video_cmdline,"machine_timing=ntsc-custom-hdmi e64_timing_base=ntsc-hdmi");assert(switch_video_mode_active(&entry));
 boot_video_captured=0;assert(!switch_video_mode_active(&entry));
 puts("PASS: live ROM precedence, saved fallback, model resource, full path/volume distinction, missing/overlong safety; actual video options, comments, last value, calibrated base");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-round1-') as d:
 p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(R/'third_party/common'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
# Existing raw attachment/CRT validation, menu stack Back and full filename
# checks are executed by their retained suites, not duplicated here.
# Execute GPIO builder and callback: visible sort must never renumber storage.
gpio=(R/'third_party/common/menu_gpio.c').read_text();a=gpio.index('int custom_gpio_pins[');b=gpio.index('static void menu_value_changed',a);data=gpio[a:b]
constants=sorted(set(re.findall(r'\bBTN_ASSIGN_[A-Z0-9_]+',data)))
code=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>
#include <algorithm>
#include "ui.h"
#define NUM_GPIO_PINS 23
enum { @CONSTANTS@ };
static unsigned int gpio_bindings[NUM_GPIO_PINS];
static std::vector<menu_item*> rows;
menu_item *ui_menu_add_multiple_choice(int id,menu_item *,const char *){auto *p=new menu_item{};p->id=id;rows.push_back(p);return p;}
static const char *function_to_string(unsigned){return "Binding";}
'''.replace('@CONSTANTS@',','.join(constants))+data+fn('third_party/common/menu_gpio.c','menu_value_changed')+'\n'+fn('third_party/common/menu_gpio.c','build_gpio_menu')+r'''
int main(){
 for(int i=0;i<NUM_GPIO_PINS;i++)gpio_bindings[i]=menu_items_list[i][0]|(menu_items_list[i][1]<<8);
 auto original=std::vector<unsigned int>(gpio_bindings,gpio_bindings+NUM_GPIO_PINS);menu_item root={};build_gpio_menu(&root);assert(rows.size()==NUM_GPIO_PINS);
 int last=-1;for(auto row:rows){int pin;assert(sscanf(row->name,"GPIO%d Binding",&pin)==1);assert(pin>last&&pin==custom_gpio_pins[row->id]);last=pin;assert((unsigned)row->choice_ints[row->value]==original[row->id]);
 for(int choice=0;choice<row->num_choices;choice++){row->value=choice;row->on_value_changed(row);assert(gpio_bindings[row->id]==(unsigned)(menu_items_list[choice][0]|(menu_items_list[choice][1]<<8)));}
 }
 for(auto row:rows)delete row;
 puts("PASS: actual GPIO numerical order, exact existing 23 pins, original storage IDs/current choices, every callback and bank mapping");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-round1-gpio-') as d:
 p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(R/'third_party/common'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
# Execute the backend's path policy, including protected folders and case.
fs='src/webui/webui_fs.cpp';source=(R/fs).read_text();a=source.index('const char *const kConfigFiles[]');b=source.index('\n};',a)+3
code=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
using boolean=bool;
#define TRUE true
#define FALSE false
#define SD_MAX_NAME_LEN 255
static bool configs_protection_external_allowed(const char *p,int){return !strstr(p,"/protected/");}
static bool configs_path_allowed(const char *p){return !strstr(p,"_factory-");}
static bool configs_path_is_managed(const char *p){return !strncmp(p,"/configs",8);}
'''+source[a:b]+'\n'+fn(fs,'RelPath')+'\n'+fn(fs,'CiEqual')+'\n'+fn(fs,'IsConfigFile')+'\n'+fn(fs,'IsEditableName')+'\n'+fn(fs,'IsKeymapName')+'\n'+fn(fs,'InConfigsFolder')+'\n'+fn(fs,'IsConfigFilePath')+'\n'+fn(fs,'IsProtectedPath')+'\n'+fn(fs,'IsEditablePath')+r'''
int main(){
 for(const char *p:{"/notes.txt","/dir/Mixed.TxT","USB:/deep/notes.TXT","/config.txt","/cmdline.txt","/c64/rpi_pos.vkm","/configs/user/settings-C64.txt"})assert(IsEditablePath(p));
 for(const char *p:{"/data.dat","/data.img","/c64/config.txt","/firmware/notes.txt","/configs/_factory-ntsc/notes.txt","/protected/notes.txt"})assert(!IsEditablePath(p));
 assert(IsProtectedPath("/config.txt")&&IsProtectedPath("/cmdline.txt"));
 puts("PASS: backend case-insensitive .txt edit policy, SD/USB paths, existing config/keymap policy, protected/system/factory restrictions, unrelated .dat/.img excluded");
}
'''
code='#include <initializer_list>\n'+code
with tempfile.TemporaryDirectory(prefix='e64-round1-text-policy-') as d:
 p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
