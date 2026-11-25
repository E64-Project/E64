#!/usr/bin/env python3
"""Exercise production presentation/audio functions and check boot integration."""
from pathlib import Path
import re, subprocess, tempfile
root = Path(__file__).resolve().parents[2]
def function(path, name):
    s = (root/path).read_text()
    m = re.search(r'^(?:static )?[\w:* ]+\b'+name+r'\([^;]*?\)\s*(?:const\s*)?\{',s,re.M)
    assert m, name
    return s[m.start():s.index('\n}',m.end())+2]
app=(root/'src/viceapp.cpp').read_text()
start=app.index('bool ViceScreenApp::Initialize')
assert app.index('SetupGPIO();',start) < app.index('gpio_recovery_sample',start) < app.index('FrameBufferLayer::Initialize();',start)
assert app.index('gpio_recovery_sample',start) < app.index('menu_configs_boot("C64")') < app.index('mEmulatorCore->LaunchEmulator')
assert '!mViceOptions.DPIEnabled() && !mViceOptions.GPIOOutputsEnabled()' in app
assert 'mViceOptions.GPIORecoveryEnabled()' in app
assert 'boot_safe_recovery' not in app
assert 'switch_safe' not in app
sampler=(root/'src/keyboard/gpio_recovery.c').read_text()
assert 'emu_key_' not in sampler and 'kbdMatrixStates' not in sampler
ui=(root/'third_party/common/ui.c').read_text()
assert 'text_x - E64_MENU_CELL' in ui
assert 'text_x - (node->id == MENU_CONFIGS_SELECT_ITEM ? 2 : 1)' not in ui
# Factory palette must pass through the ordinary parser and final palette apply.
menu=(root/'third_party/common/menu.c').read_text()
assert 'FILE *fp = configs_running_is_factory()' in menu
assert '? fmemopen((void *)factory_text, strlen(factory_text), "r")' in menu
assert ': fopen(configs_settings_file(), "r")' in menu
assert 'strcmp(name, "palette") == 0' in menu
assert 'palette_item[0]->value = emux_machine_class == BMC64_MACHINE_CLASS_C64 ? 11 : value;' in menu
assert 'emux_change_palette(0, palette_item[0]->value);' in menu
# Factory scaling follows the same parser and final application as custom Configs.
for key,item in [('h_center_0','h_center_item'),('v_center_0','v_center_item'),
                 ('h_border_0','h_border_item'),('v_border_0','v_border_item'),
                 ('h_stretch_0','h_stretch_item'),('v_stretch_0','v_stretch_item')]:
    assert re.search(r'strcmp\(name, "'+key+r'"\) == 0\) \{\s*'+item+r'\[0\]->value = value;', menu),key
build=menu[menu.index('  load_settings();',menu.index('void build_menu')):]
assert build.index('load_settings();') < build.index('do_video_settings(FB_LAYER_VIC);')
assert 'circle_set_interpolation(scaling_interp_item->value);' in build
assert 'circle_set_volume(volume_item->value);' in build
assert '"Drive Volume", 0, 1000, 100, 1000' in menu
assert 'crt_filter != MENU_VIDEO_FILTER_NONE' in menu
assert 'allow_shader() ? s_enable_shader_item->value : 0' in build
main=(root/'third_party/vice-3.3/src/main.c').read_text()
assert 'if (!ishelp && !configs_running_is_factory())' in main
assert 'configs_factory_resources(resources_set_int, resources_set_string)' in main
# Both native and Web creation persist the running settings/resources into the new ID.
creation=(root/'third_party/common/menu_configs.c').read_text()
assert 'menu_save_settings_to_config(id)' in creation
assert 'return save_user_settings_to(id, settings_path, vice_ini_path);' in menu
assert 'fprintf(fp, "h_stretch_0=%d\\n", h_stretch_item[0]->value);' in menu
assert 'fprintf(fp, "volume=%d\\n", volume_item->value);' in menu
palette_menu=(root/'third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c').read_text()
assert 'strcpy(palette_item->choices[11], "Godot")' in palette_menu
palette_video=(root/'third_party/vice-3.3/src/arch/raspi/c64/videoarch_c64.c').read_text()
assert re.search(r'case 11:\s*return godot_color_palette;',palette_video)
# Production startup must have no residual diagnostic call or overlay object.
for path in ['src/main.cpp','src/kernel.cpp','src/viceapp.cpp','src/viceemulatorcore.cpp',
             'src/configs/config_boot.c','third_party/common/menu.c',
             'third_party/common/menu_configs.c','third_party/vice-3.3/src/main.c']:
    assert 'e64_diag' not in (root/path).read_text(),path
assert 'startup_diagnostic.o' not in (root/'Makefile').read_text()
code='''#include <cassert>
#include <cstdio>
#include <cstring>
#include <strings.h>
#include "configs.h"
static bool active;
extern "C" int configs_running_is_factory(void) { return active; }
extern "C" int configs_is_factory(const char *id) {return !strcmp(id,CONFIGS_FACTORY_NTSC)||!strcmp(id,CONFIGS_FACTORY_PAL);}
enum TVCHIQSoundDestination {VCHIQSoundDestinationHDMI, VCHIQSoundDestinationAuto, VCHIQSoundDestinationHeadphones};
class ViceOptions {public: TVCHIQSoundDestination m_audioOut; TVCHIQSoundDestination GetAudioOut() const;};
'''
code+="""#include <cmath>
static int volume, amp, drive_sound_emulation, drive_sound_emulation_volume;
static void ui_display_volume(int) {}
"""
code+=function('third_party/vice-3.3/src/sound.c','set_volume')+'\n'
code+=function('third_party/vice-3.3/src/drive/drive-resources.c','set_drive_sound_emulation')+'\n'
code+=function('third_party/vice-3.3/src/drive/drive-resources.c','set_drive_sound_emulation_volume')+'\n'
factory_source=(root/'src/configs/config_factory.c').read_text()
code+=factory_source[factory_source.index('static const ConfigInfo factory[]'):factory_source.index('int configs_is_factory(')]+'\n'
code+=function('src/configs/config_factory.c','configs_factory_info')+'\n'
code+=function('src/viceoptions.cpp' ,'GetAudioOut')+'\n'+function('third_party/common/menu_configs.c','config_label')
code+='''
int main(){
 assert(set_volume(100,nullptr)==0 && volume==100 && amp==4096);
 assert(set_volume(101,nullptr)==0 && volume==100);
 assert(set_volume(-1,nullptr)==0 && volume==0);
 assert(set_drive_sound_emulation(1,nullptr)==0 && drive_sound_emulation==1);
 assert(set_drive_sound_emulation_volume(1000,nullptr)==0 && drive_sound_emulation_volume==1000);
 assert(set_drive_sound_emulation_volume(4001,nullptr)==-1 && drive_sound_emulation_volume==1000);
 assert(set_drive_sound_emulation_volume(-1,nullptr)==-1);
 ViceOptions options;
 for(auto saved:{VCHIQSoundDestinationHDMI,VCHIQSoundDestinationHeadphones,VCHIQSoundDestinationAuto}) {
  options.m_audioOut=saved;active=false;assert(options.GetAudioOut()==saved);
  active=true;assert(options.GetAudioOut()==saved);
  assert(options.m_audioOut==saved);active=false;assert(options.GetAudioOut()==saved);
 }
 // Actual immutable factory metadata uses the identical formatter as custom Configs.
 ConfigInfo n=*configs_factory_info(0),p=*configs_factory_info(1),original_n=n,original_p=p;
 char ntsc[64],pal[64];config_label(&n,ntsc,sizeof(ntsc));config_label(&p,pal,sizeof(pal));
 assert(!strcmp(ntsc,"NTSC - Default"));assert(!strcmp(pal,"PAL  - Default"));
 assert(!memcmp(&n,&original_n,sizeof(n))&&!memcmp(&p,&original_p,sizeof(p)));
 assert(!strcmp(n.id,CONFIGS_FACTORY_NTSC)&&!strcmp(n.name,"Default"));
 // Contradict the factory ID's timing: only actual metadata controls the label.
 strcpy(n.machine,p.machine);config_label(&n,pal,sizeof(pal));assert(!strcmp(pal,"PAL  - Default"));
 strcpy(p.machine,original_n.machine);config_label(&p,ntsc,sizeof(ntsc));assert(!strcmp(ntsc,"NTSC - Default"));
 strcpy(n.machine,"C64");config_label(&n,ntsc,sizeof(ntsc));assert(!strcmp(ntsc,"Default"));
 ConfigInfo user={};strcpy(user.id,"user");
 const char *machines[]={"C64/NTSC/HDMI", "C128/PAL/HDMI", " VIC20 / pal / Composite ",
                         "C64", "C64/UNKNOWN/HDMI/PAL", "C64//HDMI/NTSC"};
 const char *prefixes[]={"NTSC - ","PAL  - ","PAL  - ","","",""};
 for (unsigned i=0;i<sizeof(machines)/sizeof(*machines);i++) {
  strcpy(user.machine,machines[i]);strcpy(user.name,"Original Config");
  ConfigInfo before=user;
  char label[64];config_label(&user,label,sizeof(label));
  char expected[64];snprintf(expected,sizeof(expected),"%sOriginal Config",prefixes[i]);
  assert(!strcmp(label,expected));assert(!memcmp(&before,&user,sizeof(user)));
 }
 strcpy(user.machine,"C64/PAL/HDMI");
 for (const char *name:{"NTSC - Original", "PAL  - Original", "NTSC - PAL  - Original"}) {
  strcpy(user.name,name);char label[64];config_label(&user,label,sizeof(label));
  assert(!strcmp(label,"PAL  - Original"));assert(!strcmp(user.name,name));
 }
 memset(user.name,'X',CONFIGS_MAX_NAME_LEN);user.name[CONFIGS_MAX_NAME_LEN]=0;
 char full[64];config_label(&user,full,sizeof(full));assert(strlen(full)==39);
 struct {char label[36];char guard;} small={};small.guard='!';
 config_label(&user,small.label,sizeof(small.label));
 assert(small.label[35]==0 && small.guard=='!' && strlen(user.name)==32);

}
'''
code='#include <initializer_list>\n'+code
with tempfile.TemporaryDirectory() as tmp:
    src=Path(tmp)/'test.cpp';src.write_text(code)
    subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-I'+str(root/'src/configs'),str(src),'-o',tmp+'/test'],check=True)
    subprocess.run([tmp+'/test'],check=True)
print('PASS: production global audio selection preservation, Config labels/alignment, marker and early GPIO integration')
