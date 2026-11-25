#!/usr/bin/env python3
"""Execute production timing UI and Config-save callbacks against temporary storage."""
from pathlib import Path
import re, subprocess, tempfile
root = Path(__file__).resolve().parents[2]
def function(path, name):
    s=(root/path).read_text()
    m=re.search(r'^(?:static )?[\w:* ]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M)
    assert m,name
    return s[m.start():s.index('\n}',m.end())+2]
def stripped(path):
    return re.sub(r'^#include .*$', '', (root/path).read_text(), flags=re.M)
code=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "configs_internal.h"
#include "sd_fs.h"
enum {MENU_TEXT, MENU_START_CALC_TIMING, MENU_SAVE_CALC_TIMING, MENU_CONFIRM_CANCEL,
      MENU_CONFIGS_NEW_NAME, READ_ONLY_HEADING};
enum {MACHINE_TIMING_NTSC_HDMI, MACHINE_TIMING_PAL_HDMI,
      MACHINE_TIMING_NTSC_CUSTOM_HDMI, MACHINE_TIMING_PAL_CUSTOM_HDMI};
#include "menu_theme.h"
struct menu_item {
 int id, disabled, menu_left, menu_top, menu_width, menu_height;
 char name[64],str_value[256];
 struct menu_item *next, *first_child;
 void (*on_popped_off)(struct menu_item *,struct menu_item *);
 void (*on_value_changed)(struct menu_item *);
};
static struct menu_item stack[12];static int depth;
static int errors, reboots, settings_saves, mode;
static unsigned long ticks;
static struct menu_item *ui_push_menu(int w,int h){
 struct menu_item *m=&stack[++depth];memset(m,0,sizeof(*m));
 m->menu_width=w*8;m->menu_height=h*8;m->menu_left=20;m->menu_top=40;return m;
}
static struct menu_item *ui_menu_add_button(int id,struct menu_item *p,const char *name){
 struct menu_item *m=calloc(1,sizeof(*m));assert(m);m->id=id;
 snprintf(m->name,sizeof(m->name),"%s",name);
 struct menu_item **tail=&p->first_child;while(*tail)tail=&(*tail)->next;*tail=m;return m;
}
static struct menu_item *ui_menu_add_divider(struct menu_item *p){return ui_menu_add_button(-1,p,"");}
static struct menu_item *ui_menu_add_read_only_heading(struct menu_item *p,const char *n){return ui_menu_add_button(READ_ONLY_HEADING,p,n);}
static struct menu_item *ui_menu_add_text_field_limit(int id,struct menu_item *p,char *n,char *v,int limit){
 (void)limit;struct menu_item *m=ui_menu_add_button(id,p,n);strcpy(m->str_value,v);return m;
}
static void ui_pop_menu(void){
 struct menu_item *old=&stack[depth--];
 if(old->on_popped_off)old->on_popped_off(&stack[depth],old);
}
static void ready(void){}
static void ui_error(const char *s,...){(void)s;errors++;}
static void ui_info(const char *s,...){(void)s;}
static void update_name_labels(void){}
static void fan_prepare_shutdown(void){}
static void reboot(void){reboots++;}
static void menu_configs_before_reboot(void){configs_before_reboot();}
static int menu_save_settings_to_config(const char *id){(void)id;settings_saves++;return 0;}
static unsigned long circle_get_ticks(void){return ticks;}
static int circle_get_machine_timing(void){return mode;}
static char rename_config_id[CONFIGS_MAX_ID_LEN + 1];
static unsigned long new_config_timing;static int new_config_ntsc;
'''
for name in ['create_config','name_entered','show_name_dialog','menu_configs_save_timing']:
    code += function('third_party/common/menu_configs.c',name)+'\n'
# Use the real C64 formula and its production constants.
header=(root/'third_party/vice-3.3/src/c64/c64.h').read_text()
for line in header.splitlines():
    if re.match(r'#define C64_(?:PAL|NTSC)_(?:CYCLES_PER_LINE|SCREEN_LINES)\s',line):
        code+=line+'\n'
code+=function('third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c','emux_calculate_timing')+'\n'
code+=stripped('third_party/common/menu_timing.c')+r'''
static struct menu_item *find(int id){
 for(struct menu_item *m=stack[depth].first_child;m;m=m->next)if(m->id==id)return m;
 return NULL;
}
static void click(int id){struct menu_item *m=find(id);assert(m&&m->on_value_changed);m->on_value_changed(m);}
static void begin(int timing){
 depth=0;mode=timing;ticks=0;hdmi_timing_count=0;
 struct menu_item *page=ui_push_menu(40,25);build_timing_menu(page);
 assert(!strcmp(page->first_child->name,"TIMING CALIBRATION CORRECTION"));
 assert(!strcmp(find(MENU_START_CALC_TIMING)->name,"Start Calculation"));
 click(MENU_START_CALC_TIMING);
 assert(start_item->disabled && !start_item->name[0]);
 assert(stack[depth].menu_left==page->menu_left+(page->menu_width-240)/2);
 assert(stack[depth].menu_top==page->menu_top+176);
 assert(stack[depth].menu_top+stack[depth].menu_height+8<=page->menu_top+page->menu_height);
 assert(!strcmp(g_countdown_item->name,"600 Seconds Remaining"));
 ticks=1000000;hdmi_timing_hook();assert(!strcmp(g_countdown_item->name,"599 Seconds Remaining"));
}
static void finish(unsigned count){
 hdmi_timing_count=count;ticks=600000000;hdmi_timing_hook();
 assert(!hdmi_timing_active && !start_item->disabled);
}
int main(int argc,char **argv){
 assert(argc==2);assert(!setenv("SD_TEST_ROOT",argv[1],1));
 configs_boot_init("C64/PAL/HDMI");
 assert(sd_mkdir("/configs")==SD_OK);
 assert(configs_switch_to(CONFIGS_FACTORY_PAL)==CONFIGS_OK);configs_boot_init("C64/PAL/HDMI");
 // Back during the test and Cancel at results do not create or save anything.
 begin(MACHINE_TIMING_PAL_HDMI);ui_pop_menu();assert(!hdmi_timing_active&&!reboots&&!settings_saves);
 begin(MACHINE_TIMING_PAL_HDMI);finish(30000);assert(find(MENU_SAVE_CALC_TIMING));
 assert(measured_cycles==982800 && measured_ntsc==0);ui_pop_menu();
 assert(!settings_saves&&!reboots&&configs_running_is_factory());
 // Factory save offers a name dialog. Cancel or an empty name changes nothing.
 begin(MACHINE_TIMING_PAL_HDMI);finish(30000);click(MENU_SAVE_CALC_TIMING);
 assert(find(MENU_CONFIGS_NEW_NAME)&&find(MENU_CONFIRM_CANCEL));
 click(MENU_CONFIGS_NEW_NAME);assert(!settings_saves&&!reboots);ui_pop_menu();
 // Confirming creates a writable custom Config using the existing settings path.
 click(MENU_SAVE_CALC_TIMING);struct menu_item *name=find(MENU_CONFIGS_NEW_NAME);
 strcpy(name->str_value,"PAL Hardware Calibration");click(MENU_CONFIGS_NEW_NAME);
 assert(settings_saves==1&&reboots==1);
 configs_boot_init("C64/PAL/HDMI");assert(!configs_running_is_factory());
 assert(configs_running_timing(0)==982800 && !configs_running_timing(1));
 // Existing custom Config save updates timing only; the NTSC slot stays intact.
 assert(configs_save_timing(configs_running()->id,1,1025700)==CONFIGS_OK);
 begin(MACHINE_TIMING_PAL_HDMI);finish(30000);click(MENU_SAVE_CALC_TIMING);
 assert(reboots==2&&settings_saves==1);configs_boot_init("C64/PAL/HDMI");
 assert(configs_running_timing(0)==982800&&configs_running_timing(1)==1025700);
 // NTSC calculation and save likewise preserve the hardware-measured PAL slot.
 begin(MACHINE_TIMING_NTSC_HDMI);finish(36000);assert(measured_ntsc&&measured_cycles==1025700);
 click(MENU_SAVE_CALC_TIMING);configs_boot_init("C64/PAL/HDMI");
 assert(configs_running_timing(0)==982800&&configs_running_timing(1)==1025700);

 // Exact Pi 3B+ hardware result: 35,896 refreshes in 600 seconds.
 configs_machine_switched("C64/NTSC/HDMI");configs_boot_init("C64/NTSC/HDMI");
 begin(MACHINE_TIMING_NTSC_CUSTOM_HDMI);finish(35896);
 assert(measured_cycles==1022736&&measured_ntsc);
 int hardware_fps_shown=0;
 for(struct menu_item *m=stack[depth].first_child;m;m=m->next)
   if(!strcmp(m->name,"Actual fps = 59.826667"))hardware_fps_shown=1;
 assert(hardware_fps_shown);click(MENU_SAVE_CALC_TIMING);configs_boot_init("C64/NTSC/HDMI");
 assert(configs_running_timing(1)==1022736&&configs_running_timing(0)==982800);
 int prior=errors;
 begin(MACHINE_TIMING_PAL_HDMI);finish(36000);assert(errors==prior+1&&!find(MENU_SAVE_CALC_TIMING));
 begin(MACHINE_TIMING_NTSC_HDMI);finish(30000);assert(errors==prior+2);
 begin(MACHINE_TIMING_PAL_HDMI);finish(0);assert(errors==prior+3);
 puts("PASS: timing UI layout/countdown, cancellation, factory creation, NTSC/PAL validation, Pi 3B+ hardware NTSC 1022736/PAL 982800 results and persistence");
}
'''
with tempfile.TemporaryDirectory(dir=root/'build',prefix='timing-ui-') as tmp:
    tmp=Path(tmp);(tmp/'test.c').write_text(code)
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Wno-unused-parameter','-I'+str(root/'src/configs'),'-I'+str(root/'src/sdcard'),'-I'+str(root/'third_party/common'),str(tmp/'test.c'),str(root/'tools/sdcard/sd_fs_posix.c'),str(root/'src/sdcard/sd_fs_file.c'),*[str(p) for p in (root/'src/configs').glob('*.c')],'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test'),str(tmp)],check=True)
