#!/usr/bin/env python3
"""Run production VICE bridge/transport and bounded queue with in-memory media.
No source TAP, SD file, firmware, or live emulator is accessed.
"""
from pathlib import Path
import re, subprocess, tempfile
R=Path(__file__).resolve().parents[2]
def fn(s,name):
 m=re.search(r'^(?:static )?(?:void|int) '+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 i=m.end();depth=1
 while depth:
  if s[i]=='{':depth+=1
  if s[i]=='}':depth-=1
  i+=1
 return s[m.start():i]
api=(R/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
ui=(R/'third_party/common/ui.c').read_text()
ds=(R/'third_party/vice-3.3/src/datasette.c').read_text()
head=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "web_datasette.h"
#include "datasette.h"
enum {EMUX_TAPE_STOP,EMUX_TAPE_PLAY,EMUX_TAPE_RECORD,EMUX_TAPE_REWIND,EMUX_TAPE_FASTFORWARD,EMUX_TAPE_RESET,EMUX_TAPE_ZERO};
#define DBG(x) ((void)0)
struct {int mode,read_only,counter,cycle_counter;} image,*current_image=&image;
typedef __typeof__(image) tap_t;
struct {void *data;int type;const char *name;} tape={&image,1,"USB:/actual.tap"}, *tape_image_dev1=&tape;
static int enabled=1,playback,network,attached=1,detach_error,detaches,events,locks;
static int attaches,attach_error;
static int emux_attach_tape_image(char *path){assert(strstr(path,".TAP"));attaches++;if(attach_error)return -1;tape.name="USB2:/manual.TAP";attached=1;image.mode=0;return 0;}
int web_datasette_motor;
static void resources_get_int(const char *k,int *v){assert(!strcmp(k,"Datasette"));*v=enabled;}
static int tape_tap_attached(void){return attached;}
static const char *tape_get_file_name(void){return tape.name;}
static int event_playback_active(void){return playback;}
static int network_connected(void){return network;}
static int tape_image_detach(int unit){assert(unit==1);detaches++;if(detach_error)return -1;attached=0;return 0;}
static void circle_lock_acquire(void){assert(!locks++);}
static void circle_lock_release(void){assert(locks--==1);}
static const double ds_c1=DS_V_PLAY/DS_D/PI,ds_c2=(DS_R*DS_R)/(DS_D*DS_D),ds_c3=DS_R/DS_D;
static int datasette_counter_offset;
static double datasette_cycles_per_second=985248.0;
static int displayed_counter;
static void ui_display_tape_counter(int value){displayed_counter=value;}
static void datasette_internal_reset(void){image.counter=0;}
static void datasette_forward(void){}
static void datasette_rewind(void){}
static void datasette_start_motor(void){}
static void tapeport_set_tape_sense(int a,int b){(void)a;(void)b;}
static void ui_display_tape_control_status(int mode){assert(mode==image.mode);}
static void datasette_event_record(int command){(void)command;events++;}
static int datasette_list_item,notape_mode,datasette_motor,last_write_clk,last_tap,next_tap;
static struct {int id;} datasette_device;
'''
code=head+fn(ds,'datasette_update_ui_counter')+'\n'+fn(ds,'datasette_reset_counter')+'\n'+fn(ds,'datasette_control_internal')+'\n'+fn(ds,'datasette_control')+'\n'+fn(api,'emux_tape_control')+'\n'+fn(api,'emux_web_datasette_read')+'\n'+fn(api,'emux_web_datasette_command')
# Execute the exact production queue/storage, omitting only weak fallback stubs.
queue=ui[ui.index('static WebDatasette web_tape;'):]
queue=re.sub(r'__attribute__\(\(weak\)\) void emux_web_datasette_read.*?\n__attribute__\(\(weak\)\) int emux_web_datasette_command.*?\n}', '',queue,flags=re.S)
code+='\n'+queue+r'''
int main(void){
 WebDatasette s;
 unsigned serial=0;
 web_datasette_tick();
 int before_attach_events=events;
 assert(web_datasette_attach("USB2:/manual.TAP",&serial)==1);
 assert(serial>0&&attaches==0);
 assert(web_datasette_attach("SD:/other.TAP",&serial)==0);
 web_datasette_tick();web_datasette_status(&s);
 assert(attaches==1&&s.attached&&!s.pending&&!s.error&&s.mode==0);
 assert(!strcmp(s.filename,"USB2:/manual.TAP")&&events==before_attach_events);
 attach_error=1;assert(web_datasette_attach("SD:/bad.TAP",&serial)==1);
 web_datasette_tick();web_datasette_status(&s);assert(s.error==5&&!s.pending);
 attach_error=0;network=1;assert(web_datasette_attach("SD:/blocked.TAP",&serial)==1);
 web_datasette_tick();web_datasette_status(&s);assert(s.error==2&&attaches==2);network=0;
 attached=1;tape.name="USB:/actual.tap";
 web_datasette_tick();web_datasette_status(&s);
 assert(s.supported&&s.attached&&s.writable&&!strcmp(s.filename,"USB:/actual.tap"));
 int cmds[]={EMUX_TAPE_RECORD,EMUX_TAPE_PLAY,EMUX_TAPE_REWIND,EMUX_TAPE_FASTFORWARD,EMUX_TAPE_STOP};
 int modes[]={DATASETTE_CONTROL_RECORD,DATASETTE_CONTROL_START,DATASETTE_CONTROL_REWIND,DATASETTE_CONTROL_FORWARD,DATASETTE_CONTROL_STOP};
 for(int i=0;i<5;i++){
  int before=events;assert(web_datasette_queue(cmds[i])==1);assert(web_datasette_queue(cmds[i])==0);
  web_datasette_status(&s);assert(s.pending&&events==before);
  web_datasette_tick();web_datasette_status(&s);assert(!s.pending&&!s.error&&image.mode==modes[i]&&s.mode==cmds[i]);assert(events==before+1);
 }
 // Execute VICE's real cycle-to-counter formula and real counter reset.
 image.cycle_counter=1234567;datasette_update_ui_counter();web_datasette_tick();web_datasette_status(&s);
 assert(s.counter==displayed_counter&&s.counter>0);
 int earlier=s.counter;image.cycle_counter+=1000000;datasette_update_ui_counter();web_datasette_tick();web_datasette_status(&s);assert(s.counter>earlier);
 // Counter is copied from VICE, including reset by the native implementation.
 image.counter=831;web_datasette_tick();web_datasette_status(&s);assert(s.counter==831);
 assert(web_datasette_queue(EMUX_TAPE_ZERO)==1);web_datasette_tick();web_datasette_status(&s);assert(s.counter==0);
 image.read_only=1;web_datasette_tick();assert(web_datasette_queue(EMUX_TAPE_RECORD)==-2);
 image.read_only=0;web_datasette_tick();assert(web_datasette_queue(EMUX_TAPE_RECORD)==1);image.read_only=1;
 web_datasette_tick();web_datasette_status(&s);assert(s.error==3);
 image.read_only=0;web_datasette_tick();assert(web_datasette_queue(EMUX_TAPE_PLAY)==1);tape.name="USB:/changed.tap";
 web_datasette_tick();web_datasette_status(&s);assert(s.error==1&&!strcmp(s.filename,tape.name));
 assert(web_datasette_queue(EMUX_TAPE_PLAY)==1);playback=1;web_datasette_tick();web_datasette_status(&s);assert(s.error==2);playback=0;
 assert(web_datasette_queue(EMUX_TAPE_PLAY)==1);network=1;web_datasette_tick();web_datasette_status(&s);assert(s.error==2);network=0;
 assert(web_datasette_queue(7)==1);detach_error=1;web_datasette_tick();web_datasette_status(&s);assert(s.error==4&&s.attached);
 assert(web_datasette_queue(7)==1);detach_error=0;web_datasette_tick();web_datasette_status(&s);assert(!s.error&&!s.attached&&!s.filename[0]);assert(detaches==2);
 assert(web_datasette_queue(EMUX_TAPE_PLAY)==-2);enabled=0;web_datasette_tick();assert(web_datasette_queue(EMUX_TAPE_STOP)==-1);
 attached=1;tape_image_dev1=0;web_datasette_tick();web_datasette_status(&s);assert(!s.attached);
 assert(!locks);puts("PASS production queue and VICE: five transport modes, actual media/counter, native counter reset, read-only, tape change, event/network blocks, eject success/failure, empty/unsupported states");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-datasette-') as d:
 p=Path(d)/'test.c';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['cc','-std=gnu99','-Wall','-Wextra','-Wno-return-type','-I'+str(R/'third_party/common'),'-I'+str(R/'third_party/vice-3.3/src'),str(p),'-lm','-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
# Structural checks: HTTP cannot access media, state reader cannot perform I/O;
# File Manager still uses the established autostart path without a duplicate TAP path.
http=(R/'src/webui/webui.cpp').read_text();fs=(R/'src/webui/webui_fs.cpp').read_text()
assert 'web_datasette_status(&s)' in http and 'web_datasette_queue(command)' in http
for name in ['emux_web_datasette_read','emux_web_datasette_command']:
 body=fn(api,name)
 assert not any(x in body for x in ['fopen(', 'fwrite(', 'f_mkfs(', 'f_unlink('])
assert 'emu_autostart_interrupt(clean);' in fs
assert 'emux_attach_tape_image(fullpath' in (R/'third_party/common/menu.c').read_text()
print('PASS read-only snapshot/no temporary writes; File Manager and native TAP attachment paths preserved')
