#!/usr/bin/env python3
"""Execute the production TAP handler with mocked storage and shared queue."""
from pathlib import Path
import subprocess, tempfile
R=Path(__file__).resolve().parents[2]
s=(R/'src/webui/webui_fs.cpp').read_text()
handler=s[s.index('void WebUiFsLoadTape('):s.index('void WebUiFsMount(')]
code=r'''
#include <cassert>
#include <cstring>
#include <cstdio>
#include <strings.h>
#include <string>
using CSocket=int;
#define TRUE true
#define SD_OK 0
static int status,queued,result=1,stat_result=0;
static bool lease=true,is_dir=false,available=true;
static std::string response,path;
struct ConfigRequestLease {ConfigRequestLease(CSocket*){} bool acquired(){return lease;}};
struct sd_info {bool is_dir;};
namespace webhttp {
void SendText(CSocket*,int c,const char*,const char *body){status=c;response=body;}
void SendResponse(CSocket*,int c,const char*,const char*,const char*body,unsigned n){status=c;response.assign(body,n);}
}
static int ResolveTarget(CSocket*s,const char*q,char*out,unsigned n,bool){
 if(!available){webhttp::SendText(s,503,"Unavailable","drive unavailable");return -1;}
 assert(strlen(q)<n);strcpy(out,q);return 0;
}
static bool CiEqual(const char*a,const char*b){return !strcasecmp(a,b);}
static int sd_stat_info(const char*,sd_info *s){s->is_dir=is_dir;return stat_result;}
static int web_datasette_attach(const char *p,unsigned *serial){queued++;path=p;*serial=42;return result;}
'''+handler+r'''
int main(){
 for(const char*vol:{"SD","USB","USB2","USB3"}){
  std::string p=std::string(vol)+":/tapes/actual.TaP";int before=queued;
  WebUiFsLoadTape(nullptr,p.c_str());assert(status==202&&queued==before+1&&path==p);
  assert(response=="{\"request_id\":42}");
 }
 for(const char *p:{"USB:/a.prg","USB:/a.d64","USB:/a.crt","USB:/tap"}){
  int before=queued;WebUiFsLoadTape(nullptr,p);assert(status==400&&queued==before);
 }
 int before=queued;
 stat_result=-1;WebUiFsLoadTape(nullptr,"SD:/missing.tap");assert(status==404&&queued==before);stat_result=0;
 is_dir=true;WebUiFsLoadTape(nullptr,"SD:/folder.tap");assert(status==404&&queued==before);is_dir=false;
 available=false;WebUiFsLoadTape(nullptr,"USB:/gone.tap");assert(status==503&&queued==before);available=true;
 result=0;WebUiFsLoadTape(nullptr,"USB:/busy.tap");assert(status==409);
 result=-1;WebUiFsLoadTape(nullptr,"SD:/unsupported.tap");assert(status==501);
 before=queued;lease=false;WebUiFsLoadTape(nullptr,"SD:/blocked.tap");assert(queued==before);
 puts("PASS TAP HTTP handler: all volumes, mixed-case TAP, request ID, unsupported types, missing files/directories, unavailable drives, busy/unsupported Datasette and config lease");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-load-tape-') as d:
 p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
route=(R/'src/webui/webui.cpp').read_text()
start=route.index('  if (is_post && strcmp(target, "/api/fs/load-tape")')
end=route.index('  if (is_post && strcmp(target, "/api/fs/mount")',start)
assert route.index('int auth = CheckAuth(request)')<start
assert 'HasHeader(request, "x-bmc64-web:")' in route[start:end]
assert all(x not in handler for x in ['autostart','keyboard','reset','emu_load_prg'])
api=(R/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
attach=api.split('if (command == 8) {')[1].split('  }')[0]
assert 'emux_attach_tape_image((char *)expected)' in attach
assert all(x not in attach for x in ['autostart_', 'keyboard_', 'emux_tape_control(', 'machine_reset('])
print('PASS authenticated route/header and native attachment reuse without autostart, transport, keys or reset')
