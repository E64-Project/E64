#!/usr/bin/env python3
"""Source-level fan verification with real policy, prefs and GPIO glue.
Circle GPIO/mailbox/time are mocked; no hardware or firmware is touched.
"""
from pathlib import Path
import subprocess, tempfile, re, tarfile, difflib
R=Path(__file__).resolve().parents[2]
def run(args): subprocess.run(args,cwd=R,check=True)
with tempfile.TemporaryDirectory(prefix='e64-fan-') as tmp:
 t=Path(tmp); (t/'circle').mkdir()
 mock=r'''
#pragma once
#include <mutex>
#include <cassert>
using u32=unsigned;
#define FALSE false
#define HIGH 1
#define LOW 0
#define TEMPERATURE_ID 0
#define PROPTAG_GET_TEMPERATURE 1
extern unsigned ticks, reads, gpio_writes, gpio_mode, gpio_value, mock_temp;
extern bool sensor_ok;
enum TGPIOMode {GPIOModeInputPullDown, GPIOModeOutput};
class CGPIOPin {
public:
 CGPIOPin(unsigned p,TGPIOMode m){assert(p==11);gpio_mode=m;}
 void Write(unsigned v){gpio_value=v;++gpio_writes;}
 void SetMode(TGPIOMode m,bool init){assert(!init);assert(gpio_value==0);gpio_mode=m;}
};
class CSpinLock {std::mutex m;public:void Acquire(){m.lock();}void Release(){m.unlock();}};
class CTimer {public:static unsigned GetClockTicks(){return ticks;}};
struct TPropertyTagTemperature {unsigned nTemperatureId,nValue;};
class CBcmPropertyTags {public:bool GetTag(unsigned,TPropertyTagTemperature *p,unsigned,unsigned){++reads;p->nValue=mock_temp;return sensor_ok;}};
'''
 (t/'circle/mock.h').write_text(mock)
 for name in ['gpiopin','spinlock','timer','bcmpropertytags']:(t/f'circle/{name}.h').write_text('#include "mock.h"\n')
 code=r'''
#include "fan_control.h"
#include "sdcard/sd_fs.h"
#include "circle/mock.h"
#include <map>
#include <string>
#include <cstring>
#include <cstdio>
unsigned ticks,reads,gpio_writes,gpio_mode,gpio_value,mock_temp=52000;
bool sensor_ok=true,write_fail=false;
unsigned disk_writes;
std::map<std::string,std::string> files;
extern "C" int sd_mkdir(const char*){return SD_OK;}
extern "C" int sd_stat(const char*p,uint32_t*,int*){return files.count(p)?SD_OK:SD_NOT_FOUND;}
extern "C" int sd_read_file(const char*p,char*b,int size){if(!files.count(p))return SD_NOT_FOUND;auto s=files[p];if((int)s.size()>=size)return SD_ERROR;strcpy(b,s.c_str());return s.size();}
extern "C" int sd_write_file(const char*p,const char*b,int n){++disk_writes;if(write_fail)return SD_ERROR;files[p]=std::string(b,n);return SD_OK;}
extern "C" int sd_rename(const char*a,const char*b){if(!files.count(a)||files.count(b))return SD_ERROR;files[b]=files[a];files.erase(a);return SD_OK;}
extern "C" int sd_unlink(const char*p){return files.erase(p)?SD_OK:SD_NOT_FOUND;}
static FanStatus status(){FanStatus s;fan_get_status(&s);return s;}
static void poll(int temp){ticks+=1000000u;mock_temp=temp;fan_service();}
static void request(int enabled,int on=55,int off=50){FanSettings p={enabled,on,off};assert(!fan_request(&p));fan_service();assert(!status().pending&&!status().error);}
// Native callbacks compiled from production menu.c below.
struct menu_item {int value,disabled,render_index;char name[36],displayed_value[64];};
static int ui_errors;
static void ui_error(const char*){++ui_errors;}
'''
 menu=(R/'third_party/common/menu.c').read_text()
 a=menu.index('static struct menu_item *fan_enabled_item');b=menu.index('static void main_menu_cursor_listener',a)
 code+=menu[a:b]
 # Compile the actual Web endpoint block and video-selection guard against mocks.
 web=(R/'src/webui/webui.cpp').read_text()
 a=web.index('  if (is_post && strcmp(target, "/api/fan") == 0) {')
 b=web.index('  if (is_post && strcmp(target, "/api/webui/disable")',a)
 code+=r'''
#define FALSE false
using CSocket=int;
static int http_status;
static bool HasHeader(const char *request,const char*){return !strcmp(request,"authorized");}
static void SendText(CSocket*,int status,const char*,const char*){http_status=status;}
namespace webhttp {
 bool QueryParam(const char*q,const char*key,char*out,unsigned size){
  std::string query=q,needle=std::string(key)+"=";size_t start=query.find(needle);
  if(start==std::string::npos)return false;start+=needle.size();size_t end=query.find('&',start);
  std::string value=query.substr(start,end==std::string::npos?end:end-start);
  if(value.size()>=size)return false;strcpy(out,value.c_str());return true;
 }
}
static bool endpoint(const char*query,const char*request="authorized"){
 bool is_post=true;const char *target="/api/fan";CSocket *socket=nullptr;
'''+web[a:b]+r'''
 return false;
}
static int applied;
enum {BMC64_VIDEO_OUT_DPI=2,BMC64_VIDEO_OUT_HDMI=1};
struct machine_entry {int video_out;};struct s_cfg_flags {int flags;};
static int circle_get_model(){return 3;}
static int apply_config(machine_entry*,int,s_cfg_flags*){++applied;return 0;}
static int apply_cmdline(machine_entry*,s_cfg_flags*){++applied;return 0;}
'''
 switch=(R/'third_party/common/menu_switch.c').read_text()
 a=switch.index('int switch_apply_files(');b=switch.index('// Capture boot inputs',a)
 code+="\n#undef RASPI_C64\n"+switch[a:b]
 code+=r'''
int main(int argc,char**argv){
 machine_entry dpi_mode={BMC64_VIDEO_OUT_DPI},hdmi_mode={BMC64_VIDEO_OUT_HDMI};
 assert(switch_apply_files(&dpi_mode)&&!applied);assert(!switch_apply_files(&hdmi_mode)&&applied==2);
 endpoint("enabled=1&on=55&off=50");assert(http_status==409);

 FanSettings p;assert(!fan_prefs_load(&p));assert(!p.enabled&&p.on_c==55&&p.off_c==50);assert(!disk_writes);
 // Corruption, ordering, ranges, integer overflow: disabled defaults retained.
 for(auto bad:{"fan_enabled=3\nfan_on_c=55\nfan_off_c=50\n","fan_enabled=1\nfan_on_c=50\nfan_off_c=55\n","fan_enabled=1\nfan_on_c=81\nfan_off_c=50\n","fan_enabled=1\nfan_on_c=55\nfan_off_c=29\n","fan_enabled=9999999999999999999999999\nfan_on_c=55\nfan_off_c=50\n","fan_enabled=1\nfan_on_c=55\nfan_off_c=50\nextra=1"}) {
  files[FAN_PREFS_FILE]=bad;assert(fan_prefs_load(&p));assert(!p.enabled&&p.on_c==55&&p.off_c==50);
 }
 files.clear();
 // Interrupted rename recovers the old global preferences, without Config IO.
 files[FAN_PREFS_FILE ".old"]="fan_enabled=1\nfan_on_c=60\nfan_off_c=51\n";
 assert(!fan_prefs_load(&p)&&p.enabled&&p.on_c==60&&p.off_c==51);files.clear();
 fan_gpio_init(1);assert(!status().available&&!gpio_writes);
 fan_gpio_init(0);assert(status().available&&gpio_value==0&&gpio_mode==GPIOModeOutput);
 if(argc>1 && !strcmp(argv[1],"persisted"))files[FAN_PREFS_FILE]="fan_enabled=1\nfan_on_c=55\nfan_off_c=50\n";
 fan_start();
 if(argc>1 && !strcmp(argv[1],"disabled-shutdown")){fan_prepare_shutdown();assert(!status().output&&gpio_value==0);puts("PASS disabled shutdown remains LOW");return 0;}
 if(argc>1){assert(status().settings.enabled);assert(!status().output);sensor_ok=false;poll(0);assert(status().output);puts("PASS persisted boot + sensor fail-safe");return 0;}
 assert(!status().settings.enabled&&!status().output&&!reads&&!disk_writes);
 request(1);assert(!status().output); // initial 52C, cold hysteresis
 poll(54999);assert(!status().output);
 poll(55000);assert(status().output&&gpio_value==1);
 poll(52000);assert(status().output);
 poll(50001);assert(status().output);
 poll(50000);assert(!status().output);
 poll(52000);assert(!status().output);
 sensor_ok=false;poll(0);assert(status().output);sensor_ok=true;
 poll(0);assert(status().output);poll(126000);assert(status().output);
 poll(52000);assert(status().output);poll(49000);assert(!status().output);
 unsigned r=reads,w=disk_writes;for(int i=0;i<100;i++)fan_service();assert(reads==r&&disk_writes==w);
 ticks+=999999;fan_service();assert(reads==r);ticks++;fan_service();assert(reads==r+1);
 ticks=0xffffff00u;fan_service();ticks=999744u;fan_service();assert(reads==r+3); // wrap
 FanSettings bad={1,50,50};assert(fan_request(&bad));assert(!status().pending);
 request(0);assert(!status().output);r=reads;poll(90000);assert(reads==r&&!status().output);
 request(1,60,51);assert(status().output);assert(!fan_prefs_load(&p)&&p.enabled&&p.on_c==60&&p.off_c==51);
 // Failed saves keep the previously committed runtime and persistent settings.
 write_fail=true;p={0,55,50};assert(!fan_request(&p));assert(fan_request(&p));fan_service();assert(status().error&&status().settings.enabled);write_fail=false;
 // Execute production Web validation, cross-site defense and shared configuration.
 endpoint("enabled=1&on=62&off=51","unauthorized");assert(http_status==403);
 for(auto query:{"enabled=2&on=55&off=50","enabled=1&on=50&off=55","enabled=1&on=81&off=50","enabled=1&on=5.5&off=50","enabled=1&on=9999&off=50","enabled=1&on=55"}){endpoint(query);assert(http_status==400);}
 endpoint("enabled=1&on=62&off=51");assert(http_status==202);fan_service();assert(status().settings.on_c==62);
 request(1,60,51);
 // Native edits and web requests (same API) see the same committed settings.
 menu_item en={},on={},off={},save={};fan_enabled_item=&en;fan_on_item=&on;fan_off_item=&off;fan_save_item=&save;
 fan_menu_render(nullptr);assert(!save.displayed_value[0]);assert(en.value==2&&on.value==60&&off.value==51);
 unsigned before=disk_writes, gpio_before=gpio_writes;
 fan_menu_next(&en);assert(!en.value&&!status().pending&&status().settings.enabled);
 fan_menu_previous(&en);assert(en.value==2&&!status().pending);
 on.value=61;fan_menu_changed(&on);assert(!status().pending&&status().settings.on_c==60);
 off.value=62;fan_menu_changed(&off);assert(ui_errors==1&&off.value==51);
 for(auto row:{&on,&off})for(int dir:{1,-1}){
  fan_menu_discard();
  for(int i=0;i<4;i++){
   int old=row->value;row->value+=dir;fan_menu_changed(row);
   fan_service();fan_menu_render(nullptr);assert(row->value==old+dir);
   assert(!status().pending&&disk_writes==before&&gpio_writes==gpio_before);
  }
 }
 fan_menu_discard();assert(on.value==60&&off.value==51&&en.value==2);
 en.value=0;fan_menu_changed(&en);on.value=64;fan_menu_changed(&on);
 fan_menu_save(nullptr);assert(status().pending&&disk_writes==before&&status().settings.enabled);
 fan_menu_save(nullptr);assert(disk_writes==before); // occupied request cannot be queued twice
 fan_service();fan_menu_refresh();assert(disk_writes==before+1&&!status().settings.enabled&&!status().output);
 assert(!fan_prefs_load(&p)&&!p.enabled&&p.on_c==64&&p.off_c==51);
 assert(!strcmp(save.displayed_value,"Saved"));
 en.value=1;fan_menu_changed(&en);assert(!save.displayed_value[0]);write_fail=true;fan_menu_save(nullptr);fan_service();fan_menu_refresh();
 assert(status().error&&!status().settings.enabled&&en.value==1&&fan_dirty&&!save.displayed_value[0]);
 write_fail=false;before=disk_writes;fan_menu_save(nullptr);fan_service();fan_menu_refresh();
 assert(disk_writes==before+1&&status().settings.enabled==FAN_ON&&!fan_dirty&&!strcmp(save.displayed_value,"Saved"));
 assert(!fan_prefs_load(&p)&&p.enabled==FAN_ON&&p.on_c==64&&p.off_c==51);
 r=reads;poll(30000);assert(status().output&&gpio_value==1&&reads==r);
 assert(fan_decide(&p,1,0,30000)&&!fan_decide(&p,0,0,30000));
 // A Web commit during native editing invalidates the local draft.
 on.value=65;fan_menu_changed(&on);FanSettings base=fan_edit_base,stale=fan_edits;
 endpoint("enabled=1&on=67&off=52");fan_service();before=disk_writes;
 assert(fan_request_if_current(&stale,&base)&&disk_writes==before&&!status().pending);
 fan_menu_refresh();assert(!fan_dirty&&on.value==67&&off.value==52);
 // Leaving rows discards edits; returning sees Web commits.
 on.render_index=2;off.render_index=3;en.render_index=1;save.render_index=4;
 on.value=65;fan_menu_changed(&on);fan_menu_cursor(9);assert(on.value==67&&!fan_dirty);
 endpoint("enabled=0&on=66&off=52");fan_service();fan_menu_refresh();assert(!en.value&&on.value==66&&off.value==52);
 request(0,56,49);fan_menu_refresh();assert(!en.value&&on.value==56&&off.value==49&&!status().output);
 request(1,56,49);fan_prepare_shutdown();assert(status().output&&gpio_value==1);r=reads;poll(30000);assert(reads==r&&status().output);assert(fan_request(&p));
 puts("PASS GPIO ownership/startup, transitions, thresholds, hysteresis, sensor failures, cadence/wrap, invalid prefs, persistence/recovery/save failure, native/shared API, shutdown");
}
'''
 (t/'test.cpp').write_text(code)
 run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-c','src/fan_control.c','-o',str(t/'policy.o')])
 run(['c++','-std=gnu++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-misleading-indentation','-DRASPI_C64','-DRASPPI=3','-I'+str(t),'-Isrc',str(t/'test.cpp'),'src/fan_gpio.cpp',str(t/'policy.o'),'-o',str(t/'test')])
 run([str(t/'test')]);run([str(t/'test'),'persisted']);run([str(t/'test'),'disabled-shutdown'])
# Ownership/lifecycle guard and unchanged timing code against pre-edit checkpoint.
app=(R/'src/viceapp.cpp').read_text();switch=(R/'third_party/common/menu_switch.c').read_text()
assert app.index('if (mViceOptions.DPIEnabled())')<app.index('if (!mEmulatorCore->Init')
dpi=app[app.index('void ViceScreenApp::SetupGPIOForDPI'):app.index('void ViceScreenApp::SetupGPIO()')]
assert dpi.index('return;')<dpi.index('new CGPIOPin')
mode=switch[switch.index('int switch_apply_files'):switch.index('// Capture boot inputs')]
assert mode.index('BMC64_VIDEO_OUT_DPI')<mode.index('apply_config(')
assert 'fan_dpi_allowed()' in mode and '#if defined(RASPI_C64)' not in mode
# No GPIO11 input assignment; other consumers still operate on the original array.
normal=app[app.index('void ViceScreenApp::SetupGPIOForInput'):app.index('// Setup GPIO pins for DPI')]
assert not re.search(r'new CGPIOPin\(11\s*,',normal)
assert not any('CSPIMaster' in p.read_text() for base in [R/'src',R/'third_party/common'] for p in base.rglob('*') if p.suffix in ['.c','.cpp','.h'])
checkpoints=sorted((R/'E64-Source-Backups').glob('automatic-fan-hdmi-before-*.tar.gz'))
if checkpoints:
 with tarfile.open(checkpoints[-1]) as tar:
  for name in ['src/viceemulatorcore.cpp','src/plus4emulatorcore.cpp','src/vicescreen.cpp','src/vicesound.cpp','src/viceoptions.cpp','src/webui/assets/js/files.js']:
   assert tar.extractfile(name).read()==(R/name).read_bytes(),name
  for name in ['src/kernel.cpp','src/viceapp.cpp']:
   old=tar.extractfile(name).read().decode();new=(R/name).read_text()
   if name.endswith('kernel.cpp'):
    expected=old.replace('      mKernel->DrainLogging();','      mKernel->DrainLogging();\n      fan_service();').replace('      DrainLogging();','      DrainLogging();\n      fan_service();').replace('ViceApp::TShutdownMode CKernel::Run(void) {','ViceApp::TShutdownMode CKernel::Run(void) {\n  fan_start();')
    assert new=='#include "fan_control.h"\n'+expected
   else: assert old[old.index('unsigned ViceApp::GetCyclesPerSecond') if 'unsigned ViceApp::GetCyclesPerSecond' in old else old.index('#if defined(RASPI_PLUS4)'):old.index('//\n// ViceScreenApp impl')]==new[new.index('unsigned ViceApp::GetCyclesPerSecond') if 'unsigned ViceApp::GetCyclesPerSecond' in new else new.index('#if defined(RASPI_PLUS4)'):new.index('//\n// ViceScreenApp impl')]
 print('PASS historical source comparison for emulator timing, video, audio and file actions')
else:
 print('SKIP historical source comparison: automatic-fan-hdmi backup is absent from this workspace')
assert 'Based on BMC64, powered by VICE and Circle<' in (R/'src/webui/assets/index.html').read_text()
print('PASS DPI startup/selection defenses, GPIO ownership and About credits')
