#!/usr/bin/env python3
"""Execute E64 policy and bundled VICE PRG loader/state transitions without disk I/O.
Uses in-memory fileio fixtures; no disk image or source PRG is written.
This is a host integration test, not execution of a C64 KERNAL/CPU.
"""
from pathlib import Path
import re, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[2]
def read(p): return (ROOT/p).read_text()
def fn(text, name):
    m=re.search(r'^(?:static )?(?:[\w]+\s+|\*\s*)+'+re.escape(name)+r'\([^;]*?\)\s*\{',text,re.M)
    assert m, name
    start=m.start(); pos=m.end(); depth=1
    while depth:
        if text[pos]=='{': depth+=1
        elif text[pos]=='}': depth-=1
        pos+=1
    return text[start:pos]
api=read('third_party/vice-3.3/src/arch/raspi/vice_api.c')
auto=read('third_party/vice-3.3/src/autostart.c')
prg=read('third_party/vice-3.3/src/autostart-prg.c')
mem=read('third_party/vice-3.3/src/c64/c64mem.c')
# Verify actual callers: native, queued Web requests, configured startup and
# post-restore ordering. These paths must continue using the guarded API.
menu=read('third_party/common/menu.c'); ui=read('third_party/common/ui.c')
assert 'emux_autostart_file' in fn(menu,'menu_autostart')
assert 'ui_error("Autostart failed")' in fn(menu,'menu_autostart')
assert 'emux_autostart_file(fullpath' in menu
assert 'menu_autostart(path)' in ui and 'emux_load_prg_file(path)' in ui
assert 'ui_error("PRG load failed")' in ui
assert 'emu_autostart_interrupt' in read('third_party/common/menu_configs.c')
assert 'emu_autostart_interrupt' in read('src/webui/webui_fs.cpp')
assert 'emu_load_prg_interrupt' in read('src/webui/webui_fs.cpp')
assert 'emux_load_settings_done();' in menu
restore=fn(api,'emux_load_settings_done')
assert restore.index('emux_machine_load_settings_done();') < restore.index('ensure_prg_ram_injection()')
assert 'autostart_disk(filename,NULL,0,AUTOSTART_MODE_RUN)' in fn(api,'emux_load_run_disk8')
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <stdarg.h>
typedef int log_t;
#define LOG_DEFAULT 0
#define LOG_ERR 0
#define DBG(x) ((void)0)
#define AUTOSTART_PRG_MODE_VFS 0
#define AUTOSTART_PRG_MODE_INJECT 1
#define AUTOSTART_PRG_MODE_DISK 2
#define BMC64_MACHINE_CLASS_C64 0
#define VICE_MACHINE_C64 1
#define VICE_MACHINE_C64SC 2
#define VICE_MACHINE_C64DTV 3
#define VICE_MACHINE_SCPU64 4
#define VICE_MACHINE_C128 5
#define CARTRIDGE_CRT 7
#define AUTOSTART_MODE_RUN 1
#define AUTOSTART_MODE_LOAD 2
#define AUTOSTART_MODE_NONE 0
#define AUTOSTART_HASDISK 3
#define AUTOSTART_INJECT 4
#define AUTOSTART_WAITLOADREADY 5
#define FILEIO_FORMAT_RAW 1
#define FILEIO_FORMAT_P00 2
#define FILEIO_COMMAND_READ 4
#define FILEIO_COMMAND_FSNAME 8
#define FILEIO_TYPE_PRG 16
#define IOUTIL_MKDIR_RWXU 0700
#define ATTACH_DEVICE_FS 1
static int emux_machine_class=BMC64_MACHINE_CLASS_C64, machine_class=VICE_MACHINE_C64;
static int AutostartPrgMode=2, autostart_basic_load, autostart_log;
static int autostart_enabled=1, autostart_run_mode, autostartmode;
static int AutostartDelayRandom, c128_column4080_key=1, warp;
static const char *AutostartRunCommand="RUN\r", *AutostartPrgDiskImage="/autostart-C64.d64";
static int handle_drive_true_emulation_overridden=1,orig_drive_true_emulation_state=1,orig_device_traps_state;
static int fail_set, fail_get, ignore_set, errors, reboots, closes, menu_updates, side_effects;
static int media_kind, disk_calls, tape_calls, disabled, warp_disabled;
static unsigned requested_number, last_runmode;
static char keys[80];
static uint8_t mem_ram[65536];
static void log_error(int log,const char *fmt,...){(void)log;(void)fmt;errors++;}
static void log_message(int log,const char *fmt,...){(void)log;(void)fmt;}
static int resources_set_int(const char *name,int value){assert(!strcmp(name,"AutostartPrgMode"));if(fail_set)return -1;if(!ignore_set)AutostartPrgMode=value;return 0;}
static int resources_get_int(const char *name,int *value){assert(!strcmp(name,"AutostartPrgMode"));if(fail_get)return -1;*value=AutostartPrgMode;return 0;}
static int network_connected(void){return 0;}
static int event_record_active(void){return 0;}
static int event_playback_active(void){return 0;}
static int cmdline_get_autostart_mode(void){return 0;}
static void kbdbuf_feed(const char *s){strcat(keys,s);}
static void kbdbuf_feed_runcmd(const char *s){kbdbuf_feed(s);}
static void kbdbuf_feed_cmdline(void){assert(0);}
static void init_drive_emulation_state(int unit){assert(unit==8);}
static void ui_update_menus(void){menu_updates++;}
static void disable_warp_if_was_requested(void){warp_disabled++;}
static void autostart_disable(void){disabled++;}
static void reboot_for_autostart(const char *name,int mode,unsigned runmode){assert(!name&&mode==AUTOSTART_INJECT);reboots++;autostart_run_mode=runmode;autostartmode=mode;}
static void set_true_drive_emulation_mode(int x,int unit){(void)x;(void)unit;side_effects++;}
static int get_true_drive_emulation_state(int unit){(void)unit;return 1;}
static void set_device_traps_state(int x){(void)x;side_effects++;}
static int get_device_traps_state(void){return 0;}
static void file_system_detach_disk(int unit){(void)unit;side_effects++;}
static void setup_for_disk(int unit){(void)unit;side_effects++;}
// Every possible temporary-image/write path is a hard failure, not a no-op.
static int ioutil_mkdir(const char *s,int mode){(void)s;(void)mode;assert(!"mkdir forbidden");return -1;}
static void util_fname_split(const char *s,char **d,void *b){(void)s;(void)d;(void)b;assert(!"disk path forbidden");}
typedef struct {const uint8_t *bytes; size_t size,pos,read_limit;const char *name;} fileio_info_t;
static fileio_info_t input;
static fileio_info_t *fileio_open(const char *name,void *path,int format,int command,int type){
 assert(!path&&format==(FILEIO_FORMAT_RAW|FILEIO_FORMAT_P00)&&command==(FILEIO_COMMAND_READ|FILEIO_COMMAND_FSNAME)&&type==FILEIO_TYPE_PRG);
 input.pos=0;input.name=name;return media_kind==0?&input:NULL;
}
static unsigned fileio_get_bytes_left(fileio_info_t *f){return f->size-f->pos;}
static unsigned fileio_read(fileio_info_t *f,uint8_t *out,unsigned n){unsigned got=0;while(got<n&&f->pos<f->size&&f->pos<f->read_limit)out[got++]=f->bytes[f->pos++];return got;}
static void fileio_close(fileio_info_t *f){assert(f==&input);closes++;}
#define lib_malloc malloc
#define lib_free free
typedef struct {uint8_t *data;uint16_t start_addr;uint32_t size;} autostart_prg_t;
static autostart_prg_t *inject_prg;
static int autostart_prg_with_virtual_fs(const char *name,fileio_info_t *f,int log){(void)name;(void)f;(void)log;assert(!"VFS fallback forbidden");return -1;}
static int autostart_prg_with_disk_image(const char *name,fileio_info_t *f,int log,const char *image){(void)name;(void)f;(void)log;(void)image;assert(!"disk creation forbidden");return -1;}
static int autostart_disk(const char *name,const char *program,unsigned n,unsigned mode){(void)name;assert(!program);disk_calls++;requested_number=n;last_runmode=mode;return media_kind==1?0:-1;}
static int autostart_tape(const char *name,const char *program,unsigned n,unsigned mode){(void)name;assert(!program);tape_calls++;requested_number=n;last_runmode=mode;return media_kind==2?0:-1;}
static int autostart_snapshot(const char *name,const char *program){(void)name;assert(!program);return -1;}
static int cartridge_attach_image(int type,const char *name){(void)name;assert(type==CARTRIDGE_CRT);return -1;}
'''
for source,names in [(mem,['mem_get_basic_text','mem_set_basic_text','mem_inject']),
                     (prg,['load_prg','free_prg','autostart_prg_with_ram_injection','autostart_prg_perform_injection']),
                     (auto,['setup_for_prg','autostart_prg','autostart_autodetect','advance_inject','autostart_finish']),
                     (api,['ensure_prg_ram_injection','emux_autostart_file','emux_load_prg_file','emux_autostart_image_file'])]:
    for name in names: code+='\n'+fn(source,name)+'\n'
# Execute the actual post-restoration hook (including an emulated saved mode 2).
code+=r'''
static void restore_drive_selection_modes(void){}
static struct {int value;} *keyboard_mapping_item;
static int vice_keymap_index_to_bmc(int x){return x;}
static void ui_set_keyboard_mapping(int x){(void)x;}
static void emux_machine_load_settings_done(void){AutostartPrgMode=2;}
static void ui_error(const char *text){assert(strstr(text,"RAM injection"));errors++;}
'''+restore+r'''
static void fixture(const uint8_t *p,size_t size){input.bytes=p;input.size=size;input.read_limit=size;media_kind=0;keys[0]=0;memset(mem_ram,0xa5,sizeof(mem_ram));mem_set_basic_text(0x801,0x801);}
int main(void){
 // Tokenized standalone BASIC: 10 PRINT "E64" (including next-line and end pointers).
 static const uint8_t basic[]={1,8,0x0c,8,10,0,0x99,0x22,'E','6','4',0x22,0,0,0};
 uint8_t original[sizeof basic];memcpy(original,basic,sizeof basic);
 for(int w=0;w<2;w++)for(int path=0;path<3;path++)for(int random=0;random<2;random++){
  fixture(basic,sizeof basic);AutostartPrgMode=2;warp=w;AutostartDelayRandom=random;
  int before=reboots;
  int result=path==0?emux_autostart_file("basic.prg"):path==1?emux_load_prg_file("basic.prg"):emux_autostart_image_file("basic.prg",0);
  assert(result==0&&AutostartPrgMode==1&&warp==w&&reboots==before+1);
  assert(autostartmode==AUTOSTART_INJECT&&keys[0]==0);
  advance_inject();assert(autostartmode==AUTOSTART_WAITLOADREADY&&!inject_prg);
  assert(!memcmp(mem_ram+0x801,basic+2,sizeof basic-2));
  assert(mem_ram[0x800]==0xa5&&mem_ram[0x801+sizeof basic-2]==0xa5);
  uint16_t start,end;mem_get_basic_text(&start,&end);assert(start==0x801&&end==0x801+sizeof basic-2);
  for(int addr=0x2d;addr<=0x31;addr+=2)assert((mem_ram[addr]|mem_ram[addr+1]<<8)==end);
  assert((mem_ram[0xae]|mem_ram[0xaf]<<8)==end);
  autostart_finish();assert(!strcmp(keys,path==1?"":"RUN\r"));
  assert(!memcmp(original,basic,sizeof basic)&&side_effects==0&&warp==w);
 }
 // Saved mode 2 must be overridden AFTER machine restoration.
 AutostartPrgMode=0;emux_load_settings_done();assert(AutostartPrgMode==1);
 // Resetting mode to 2 between operations cannot re-enable image creation.
 for(int media=1;media<=2;media++)for(int w=0;w<2;w++){
  media_kind=media;warp=w;AutostartPrgMode=2;int before=reboots;
  assert(emux_autostart_image_file(media==1?"boot.d64":"boot.tap",3)==0);
  assert(requested_number==3&&last_runmode==AUTOSTART_MODE_RUN&&warp==w&&reboots==before);
 }
 // Failed policy/readback refuses dispatch instead of quietly falling back.
 for(int failure=0;failure<3;failure++){
  fixture(basic,sizeof basic);AutostartPrgMode=2;fail_set=failure==0;fail_get=failure==1;ignore_set=failure==2;
  int before=disk_calls;assert(emux_autostart_file("basic.prg")==-1&&disk_calls==before);
  assert(emux_load_prg_file("basic.prg")==-1&&disk_calls==before);
  assert(emux_autostart_image_file("basic.prg",0)==-1&&disk_calls==before);
  fail_set=fail_get=ignore_set=0;
 }
 // Invalid header, address overflow, truncated read, unavailable file: no reset, RUN or image.
 static const uint8_t short_header[]={1};
 static const uint8_t overflow[]={0xff,0xff,1,2};
 for(int invalid=0;invalid<4;invalid++){
  fixture(invalid==0?short_header:invalid==1?overflow:basic,invalid==0?sizeof short_header:invalid==1?sizeof overflow:sizeof basic);
  if(invalid==2)input.read_limit=3;if(invalid==3)media_kind=3;
  int before=reboots;assert(emux_autostart_file("bad.prg")==-1&&reboots==before&&keys[0]==0&&!inject_prg);
 }
 int before=disabled;advance_inject();assert(disabled==before+1&&warp_disabled==1);
 // Policies for other VICE machines are not changed by this C64 update.
 emux_machine_class=99;AutostartPrgMode=2;assert(ensure_prg_ram_injection()==0&&AutostartPrgMode==2);
 assert(errors>0&&closes>0&&menu_updates>0&&disk_calls>0&&tape_calls>0);
 puts("PASS: actual VICE RAM staging/injection, bytes, BASIC pointers, RUN/LOAD; native/Web/startup policy; restored mode 2; Warp 0/1 unchanged; disk/tape dispatch; invalid/failure refusal; no temporary-image/write path; source unchanged");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-prg-ram-') as d:
    source=Path(d)/'test.c';exe=Path(d)/'test';source.write_text(code)
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
