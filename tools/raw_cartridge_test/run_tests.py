#!/usr/bin/env python3
"""Execute production raw adapter, queue and VICE raw readers in temporary fixtures."""
from pathlib import Path
import re,subprocess,tempfile
R=Path(__file__).resolve().parents[2]
def read(p):return (R/p).read_text()
def fn(s,n):
 m=re.search(r'^(?:static )?(?:[\w]+\s+|\*\s*)+'+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 a=m.start();p=m.end();depth=1
 while depth:
  if s[p]=='{':depth+=1
  elif s[p]=='}':depth-=1
  p+=1
 return s[a:p]
api=read('third_party/vice-3.3/src/arch/raspi/vice_api.c');ui=read('third_party/common/ui.c');cart=read('third_party/vice-3.3/src/c64/cart/c64cart.c');generic=read('third_party/vice-3.3/src/c64/cart/c64-generic.c')
code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include "raw_cartridge.h"
#define BMC64_MACHINE_CLASS_C64 0
#define CARTRIDGE_GENERIC_8KB -3
#define CARTRIDGE_GENERIC_16KB -2
#define CARTRIDGE_ULTIMAX -6
#define MACHINE_RESET_MODE_SOFT 0
#define MACHINE_RESET_MODE_HARD 1
#define UTIL_FILE_LOAD_SKIP_ADDRESS 1
#define UTIL_FILE_LOAD_FILL 2
#define MODE_READ "rb"
#define LOG_ERR 0
#define LOG_DEFAULT 0
#define DBG(x) ((void)0)
static int c64cartridge_reset,emux_machine_class,reset_count,attach_count,refresh_count;
static int late_failure,get_failure,set_failure,restore_failure,attached,locks,read_failure,stat_truncated;
static int wanted_restore;
static uint8_t rawcart[32768];
static void log_error(int log,const char *fmt,...){(void)log;(void)fmt;}
static int util_check_null_string(const char *s){return !s||!*s;}
static size_t util_file_length(FILE *f){long p=ftell(f);fseek(f,0,SEEK_END);long n=ftell(f);fseek(f,p,SEEK_SET);return (size_t)n;}
static void machine_trigger_reset(int mode){assert(mode==MACHINE_RESET_MODE_HARD);reset_count++;}
static int generic_common_attach(int type){attached=type;return 0;}
static int resources_get_int(const char *name,int *value){assert(!strcmp(name,"CartridgeReset"));if(get_failure)return -1;*value=c64cartridge_reset;wanted_restore=*value;return 0;}
static int resources_set_int(const char *name,int value){assert(!strcmp(name,"CartridgeReset"));if(set_failure){set_failure=0;return -1;}if(restore_failure&&value==wanted_restore&&attach_count)return -1;c64cartridge_reset=value;return 0;}
static void emux_refresh_cartridge_menu(void){refresh_count++;}
static void circle_lock_acquire(void){assert(!locks);locks++;}
static void circle_lock_release(void){assert(locks==1);locks--;}
static size_t checked_read(void *p,size_t n,size_t count,FILE *f){return read_failure?0:fread(p,n,count,f);}
#define fread checked_read
static int checked_stat(const char *p,struct stat *s){int result=stat(p,s);if(!result&&stat_truncated)s->st_size=8192;return result;}
#define stat(p,s) checked_stat(p,s)
'''
code+='\n'+fn(read('third_party/vice-3.3/src/util.c'),'util_file_load')
for n in ['generic_8kb_bin_attach','generic_16kb_bin_attach','generic_ultimax_bin_attach']:code+='\n'+fn(generic,n)
code+='\n'+fn(cart,'cart_power_off')+'\n'+fn(api,'emux_reset')+r'''
// Mirrors VICE's known pre-validation detach and successful power-off calls.
// The raw file parsing itself above is the real bundled VICE implementation.
static int cartridge_attach_image(int type,const char *path){
 assert(!locks&&c64cartridge_reset==0);attach_count++;
 attached=0;cart_power_off();cart_power_off();
 if(late_failure)return -1;
 int result=type==CARTRIDGE_GENERIC_8KB?generic_8kb_bin_attach(path,rawcart):type==CARTRIDGE_GENERIC_16KB?generic_16kb_bin_attach(path,rawcart):generic_ultimax_bin_attach(path,rawcart);
 if(result==0)cart_power_off();return result;
}
'''+fn(api,'emux_load_raw_cartridge')+r'''
#define PENDING_EMU_AUTOSTART_MAX 560
static char raw_cart_path[PENDING_EMU_AUTOSTART_MAX],raw_cart_error[160];
static unsigned raw_cart_serial;
static int raw_cart_state,raw_cart_type;
'''
for n in ['emu_raw_cartridge_submit','emu_raw_cartridge_status','emu_raw_cartridge_process']:code+='\n'+fn(ui,n)
code+=r'''
static void fixture(const char *path,unsigned size){
 FILE *f=fopen(path,"wb");assert(f);for(unsigned i=0;i<size;i++)fputc((int)(i&255),f);assert(!fclose(f));
}
static void clear(int old){c64cartridge_reset=old;attach_count=reset_count=refresh_count=0;get_failure=set_failure=restore_failure=late_failure=read_failure=stat_truncated=0;attached=42;}
int main(void){
 char error[160];const char *path="test.rom";
 for(int old=0;old<=1;old++)for(int type=1;type<=3;type++)for(unsigned payload=4096;payload<=16384;payload+=4096)for(unsigned prefix=0;prefix<=2;prefix+=2){
  fixture(path,payload+prefix);clear(old);int result=emux_load_raw_cartridge(path,type,error,sizeof(error));
  int valid=e64_raw_cartridge_size_valid(payload+prefix,type);
  assert((result==0)==valid&&c64cartridge_reset==old);
  assert(reset_count==valid&&attach_count==valid&&refresh_count==valid);
  if(valid){assert(attached==(type==1?-3:type==2?-2:-6));assert(!error[0]);}
  else assert(attached==42&&strstr(error,"Size"));
 }
 for(int type=-1;type<=4;type+=5){fixture(path,8192);clear(1);assert(emux_load_raw_cartridge(path,type,error,sizeof(error))<0&&!attach_count&&!reset_count);}
 for(unsigned size=0;size<=8193;size+=2731){fixture(path,size);clear(1);assert(emux_load_raw_cartridge(path,1,error,sizeof(error))<0&&!attach_count&&!reset_count);}
 fixture(path,8192);
 for(int old=0;old<=1;old++){
  clear(old);late_failure=1;assert(emux_load_raw_cartridge(path,1,error,sizeof(error))<0&&!reset_count&&c64cartridge_reset==old&&attached==0&&strstr(error,"May Have Been Removed"));
  clear(old);set_failure=1;assert(emux_load_raw_cartridge(path,1,error,sizeof(error))<0&&!reset_count&&!attach_count&&c64cartridge_reset==old);
  clear(old);get_failure=1;assert(emux_load_raw_cartridge(path,1,error,sizeof(error))<0&&!reset_count&&!attach_count&&c64cartridge_reset==old);
 }
 clear(1);restore_failure=1;assert(emux_load_raw_cartridge(path,1,error,sizeof(error))<0&&!reset_count&&strstr(error,"Cannot Restore"));
 clear(1);read_failure=1;assert(emux_load_raw_cartridge(path,1,error,sizeof(error))<0&&!attach_count&&!reset_count);
 fixture(path,100);clear(1);stat_truncated=1;assert(emux_load_raw_cartridge(path,1,error,sizeof(error))<0&&!attach_count&&!reset_count);
 fixture(path,8192);clear(1);assert(emux_load_raw_cartridge("test.bin",1,error,sizeof(error))<0&&!attach_count&&!reset_count);
 // Queueing and polling have no cartridge side effects. Only processing does.
 clear(1);assert(!emu_raw_cartridge_submit(path,1,0));unsigned id=emu_raw_cartridge_submit(path,1,1);assert(id&&!attach_count&&!reset_count);
 assert(emu_raw_cartridge_status(id,error,sizeof(error))==1&&!emu_raw_cartridge_submit(path,2,1));
 assert(emu_raw_cartridge_process()==1&&attach_count==1&&reset_count==1);
 assert(emu_raw_cartridge_status(id,error,sizeof(error))==3&&!error[0]);assert(!emu_raw_cartridge_process());
 clear(0);late_failure=1;unsigned next=emu_raw_cartridge_submit(path,1,1);assert(next!=id&&!emu_raw_cartridge_status(id,error,sizeof(error)));
 assert(emu_raw_cartridge_process()&&emu_raw_cartridge_status(next,error,sizeof(error))==4&&!reset_count&&c64cartridge_reset==0);
 assert(strstr(error,"May Have Been Removed"));
 // Source file has not been changed by any loader operation.
 FILE *f=fopen(path,"rb");assert(f);for(unsigned i=0;i<8192;i++)assert(fgetc(f)==(int)(i&255));assert(fgetc(f)==EOF);fclose(f);
 puts("PASS: real VICE raw readers, 4K/8K/12K/16K and prefixes; wrong/truncated/read failures; resource restoration 0/1; replacement warning; attach success one reset/failure zero; queue IDs, busy and actual completion; source unchanged");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-raw-cart-') as d:
 p=Path(d)/'test.c';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(R/'third_party/common'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],cwd=d,check=True)
# Ensure the explicit .rom route is separate; original CRT/.bin/icon paths stay intact.
files=read('src/webui/assets/js/files.js');routes=read('src/webui/webui.cpp')
assert 'extOf(e.name) === "rom" && machineName() === "C64"' in files
assert 'label: "Load ROM..."' in files and 'chooseRawCartridge(entry.name, entry.size)' in files
assert 'extOf(name) === "crt" ? "Attach cartridge" : "Load & Run"' in files
assert '"rom"' not in read('src/webui/webui_machine.cpp')
assert 'WebUiFsRawCartridge(socket, query, is_post)' in routes
print('PASS: .rom explicit-only C64 UI route; CRT generic autostart untouched; no .bin association')
# Compile and execute the production HTTP handler with socket/filesystem doubles.
endpoint=fn(read('src/webui/webui_fs.cpp'),'WebUiFsRawCartridge')
cpp=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <strings.h>
#include <cstdlib>
#include <string>
#include <map>
#include "raw_cartridge.h"
using boolean=bool;
#define TRUE true
#define SD_OK 0
struct CSocket {int status;std::string body;};
static std::map<std::string,std::string> query;
namespace webhttp {
static bool QueryParam(const char*,const char *key,char *out,unsigned size){auto i=query.find(key);if(i==query.end()||i->second.size()>=size)return false;snprintf(out,size,"%s",i->second.c_str());return true;}
static void SendText(CSocket *s,int code,const char*,const char *body){s->status=code;s->body=body;}
static void SendResponse(CSocket *s,int code,const char*,const char*,const char *body,unsigned n){s->status=code;s->body.assign(body,n);}
}
struct ConfigRequestLease {explicit ConfigRequestLease(CSocket*){}bool acquired(){return true;}};
struct Machine {const char *name;};static Machine machine={"C64"};static Machine *WebUiMachineGet(){return &machine;}
static const char *path="USB:/game.ROM";
static int ResolveTarget(CSocket*,const char*,char *out,unsigned size,bool){snprintf(out,size,"%s",path);return 0;}
struct sd_info {unsigned size;int is_dir;};static sd_info info={8192,0};static int stat_result=0;
static int sd_stat_info(const char*,sd_info *out){*out=info;return stat_result;}
static unsigned calls=0,job=42;static int state=1;
static unsigned emu_raw_cartridge_submit(const char *p,int type,int replace){assert(!strcmp(p,path)&&replace==1&&type>=1&&type<=3);calls++;return job;}
static int emu_raw_cartridge_status(unsigned id,char *out,unsigned n){snprintf(out,n,"%s",state==4?"Attachment Failed; Previous Cartridge May Have Been Removed":"");return id==42?state:0;}
'''+endpoint+r'''
int main(){
 CSocket socket;query={{"type","8k"},{"replace","1"}};
 WebUiFsRawCartridge(&socket,"",true);assert(socket.status==202&&calls==1&&socket.body.find("42")!=std::string::npos);
 query["type"]="16k";WebUiFsRawCartridge(&socket,"",true);assert(socket.status==400&&calls==1);
 query["type"]="8k";query["replace"]="0";WebUiFsRawCartridge(&socket,"",true);assert(socket.status==400&&calls==1);
 query["replace"]="1";path="USB:/file.bin";WebUiFsRawCartridge(&socket,"",true);assert(socket.status==400&&calls==1);
 path="USB:/game.ROM";info.is_dir=1;WebUiFsRawCartridge(&socket,"",true);assert(socket.status==404&&calls==1);info.is_dir=0;
 machine.name="C128";WebUiFsRawCartridge(&socket,"",true);assert(socket.status==400&&calls==1);machine.name="C64";
 job=0;WebUiFsRawCartridge(&socket,"",true);assert(socket.status==409);
 query={{"id","42"}};
 for(int value=1;value<=4;value++){state=value;WebUiFsRawCartridge(&socket,"",false);assert(socket.status==200&&socket.body.find("\"state\":"+std::to_string(value))!=std::string::npos);}
 query["id"]="43";WebUiFsRawCartridge(&socket,"",false);assert(socket.status==409);
 for(const char *id:{"0","bad","4294967296","42x"}){query["id"]=id;WebUiFsRawCartridge(&socket,"",false);assert(socket.status==400);}
 puts("PASS: actual HTTP handler accepts explicit typed/replacement request; C64/extension/size/directory/busy validation; request-correlated queued/running/success/failure results");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-raw-http-') as d:
 p=Path(d)/'test.cpp';p.write_text(cpp);exe=Path(d)/'test'
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(R/'third_party/common'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
