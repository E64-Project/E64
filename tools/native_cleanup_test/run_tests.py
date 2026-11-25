#!/usr/bin/env python3
"""Execute current disk-start and drive-sound entry points; audit native wiring."""
from pathlib import Path
import re,subprocess,tempfile
root=Path(__file__).resolve().parents[2]
def function(path,name):
 s=(root/path).read_text();m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]
menu=(root/'third_party/common/menu.c').read_text()
assert 'ui_menu_add_button(MENU_AUTOSTART, root, "Load & Run Disk >")' in menu
assert 'ui_menu_add_button(MENU_C64_ATTACH_CART, root, "Load Cartridge >")' in menu
assert "Load & Run (Drive 8)" not in menu
assert '"Load Cartridge >"' in (root/"third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c").read_text()
assert 'ui_menu_add_button(MENU_LOAD_SNAP, root, "Load Snapshot >")' in menu
assert 'ui_menu_add_button(MENU_SAVE_SNAP, root, "Save Snapshot >")' in menu
assert 'ui_menu_add_folder(root, "Snapshot")' not in menu
assert 'ui_menu_add_folder(sound_parent, "Audio Output")' in menu
assert 'move_menu_item(sound_parent, root, audio_parent)' not in menu
assert 'return joyswap ? "1=2 / 2=1" : "1=1 / 2=2";' in menu
for unit in range(8,12):
 assert 'MENU_DRIVE_CHANGE_MODEL_'+str(unit) in menu
assert 'ui_menu_add_button(model_ids[unit-8],device,"Change Model >")' in menu
assert 'emux_load_run_disk8(fullpath(DIR_DISKS, item->str_value))' in menu
assert 'show_files(DIR_DISKS, FILTER_DISK, MENU_AUTOSTART_FILE' in menu
# Reset paths must not manufacture a motor-on event; actual hardware events retained.
for path in ['iecieee/iecieee.c','tcbm/tcbm.c']:
 s=(root/'third_party/vice-3.3/src/drive'/path).read_text()
 assert 'drive_sound_reset_unit(drv->mynumber)' in s
 assert 'drive_sound_update(DRIVE_SOUND_MOTOR_ON, drv->mynumber)' not in s
for path in ['via2d.c']:
 matches=list((root/'third_party/vice-3.3/src/drive').rglob(path));assert matches
 assert any('drive_sound_update(' in p.read_text() for p in matches)
code=r'''
#include <cassert>
#include <cstring>
#include <cstdint>
#define DRIVE_NUM 4
#define DRIVE_SOUND_MOTOR_ON 4
#define DRIVE_SOUND_MOTOR_OFF 5
static int motor_on[4],stepvol[4],drive_sound_emulation=1,drive_sound_offset,stored;
static int sample0,sample1,sample2,sample3,sample4,sample5;
static int *nosound=&sample0,*spinup=&sample1,*spindown=&sample2,*bump=&sample3,*stepping=&sample4,*stepping2=&sample5;
static int *motor[4],*step[4];
static struct {int chip_enabled;} drive_sound;
static void sound_store(uint16_t,int,int){stored++;}
@SOUND@
struct image_contents_file_list_t {const char *type;image_contents_file_list_t *next;};
struct image_contents_t {image_contents_file_list_t *file_list;};
static image_contents_file_list_t prg={"PRG",nullptr},seq={"SEQ",nullptr};
static image_contents_t contents;
static int valid=1,destroyed,started,result;
#define AUTOSTART_MODE_RUN 1
static image_contents_t *diskcontents_filesystem_read(char*){return valid?&contents:nullptr;}
static void image_contents_destroy(image_contents_t*){destroyed++;}
static int autostart_disk(char *f,void *n,int number,int mode){assert(!strcmp(f,"boot.d64")&&!n&&number==0&&mode==AUTOSTART_MODE_RUN);started++;return result;}
@START@
enum {MENU_DETACH_DISK_8,MENU_DETACH_DISK_9,MENU_DETACH_DISK_10,MENU_DETACH_DISK_11,MENU_DETACH_TAPE,MENU_DETACH_CART};
static char attached_disk_name[4][64];
static int removed_unit,removed_tape,removed_cart,closed;
static void ui_info(const char *text){assert(!strcmp(text,"Removing..."));}
static void emux_detach_disk(int unit){removed_unit=unit;}
static void emux_detach_tape(){removed_tape++;}
static void emux_detach_cart(int bank){assert(bank==0);removed_cart++;}
static void ui_error(const char*){assert(false);}
static void ui_pop_all_and_toggle(){closed++;}
static void remove_selected(int id){struct {int id;} chosen={id};auto*item=&chosen;switch(id){
@REMOVE@
}}
int main(){
 for(int unit=8;unit<=11;unit++){
  for(int n=0;n<4;n++)strcpy(attached_disk_name[n],"existing.d64");
  remove_selected(MENU_DETACH_DISK_8+unit-8);assert(removed_unit==unit&&closed==unit-7);
  for(int n=0;n<4;n++)assert((attached_disk_name[n][0]==0)==(n==unit-8));
 }
 remove_selected(MENU_DETACH_TAPE);assert(removed_tape==1&&closed==5);
 remove_selected(MENU_DETACH_CART);assert(removed_cart==1&&closed==6);
 drive_sound_stop();stored=0;
 drive_sound_update(DRIVE_SOUND_MOTOR_OFF,0);assert(!stored&&!drive_sound.chip_enabled);
 drive_sound_update(DRIVE_SOUND_MOTOR_ON,0);assert(stored==1&&motor[0]==spinup&&drive_sound.chip_enabled);
 drive_sound_update(DRIVE_SOUND_MOTOR_ON,0);assert(stored==1);
 drive_sound_head(20,1,0);assert(stored==2&&step[0]==stepping2);
 drive_sound_reset_unit(0);assert(stored==2&&!drive_sound.chip_enabled&&motor[0]==nosound&&step[0]==nosound);
 drive_sound_update(DRIVE_SOUND_MOTOR_OFF,0);assert(stored==2);
 drive_sound_update(DRIVE_SOUND_MOTOR_ON,0);drive_sound_update(DRIVE_SOUND_MOTOR_ON,1);
 drive_sound_reset_unit(0);assert(drive_sound.chip_enabled&&motor[1]==spinup);
 drive_sound_update(DRIVE_SOUND_MOTOR_OFF,1);assert(motor[1]==spindown);
 drive_sound_stop();assert(!drive_sound.chip_enabled);
 contents.file_list=&prg;char file[]="boot.d64";
 assert(emux_load_run_disk8(file)==0&&started==1&&destroyed==1);
 result=-1;assert(emux_load_run_disk8(file)==-1&&started==2);
 valid=0;assert(emux_load_run_disk8(file)==-1&&started==2);
 valid=1;contents.file_list=&seq;assert(emux_load_run_disk8(file)==-1&&started==2);
 contents.file_list=nullptr;assert(emux_load_run_disk8(file)==-1&&started==2);
}
'''
code=code.replace('@SOUND@','\n'.join(function('third_party/vice-3.3/src/drive/drive-sound.c',n) for n in ['drive_sound_update','drive_sound_reset_unit','drive_sound_head','drive_sound_stop'])).replace('@START@',function('third_party/vice-3.3/src/arch/raspi/vice_api.c','emux_load_run_disk8'))
# Execute the real six removal dispatcher branches without any mounted media.
removals=['MENU_DETACH_DISK_'+str(unit) for unit in range(8,12)]+['MENU_DETACH_TAPE','MENU_DETACH_CART']
branches=[]
for name in removals:
 match=re.search(r'  case '+name+r':.*?    return;',menu,re.S);assert match,name
 branches.append(match.group())
code=code.replace('@REMOVE@','\n'.join(branches))
assert '"Remove Tape"' in menu and '"Removing..."' in menu
assert 'Detach any disk image' not in (root/'src/webui/assets/js/files.js').read_text()
with tempfile.TemporaryDirectory(prefix='e64-native-cleanup-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(code)
 subprocess.run(['g++','-std=c++17','-fsanitize=undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
print('PASS: native action/snapshot/audio/advanced-drive/joystick wiring; production disk RUN preflight/error propagation and real motor/head/reset sound transitions; six real media-removal branches and cleared per-drive attachment labels')
