#!/usr/bin/env python3
"""Execute production Datasette HTTP routes with mocked socket and queue."""
from pathlib import Path
import subprocess,tempfile
R=Path(__file__).resolve().parents[2]
s=(R/'src/webui/webui.cpp').read_text();start=s.index('  if (is_get && strcmp(target, "/api/datasette")');end=s.index('  if (is_get && strcmp(target, "/api/status")',start)
code=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include "web_datasette.h"
#define FALSE false
static int status,queued,queue_result=1;
static bool header=true;
static std::string payload;
static WebDatasette sample;
void web_datasette_status(WebDatasette *s){*s=sample;}
int web_datasette_queue(int c){queued=c;return queue_result;}
static bool HasHeader(const char *,const char *key){assert(!strcmp(key,"x-bmc64-web:"));return header;}
static void SendText(int,int code,const char *,const char *body){status=code;payload=body;}
static void SendResponse(int,int code,const char *,const char *,const char *body,unsigned n){status=code;payload.assign(body,n);}
namespace webhttp {static bool QueryParam(const char *q,const char *,char *out,unsigned n){if(!q||strlen(q)>=n)return false;strcpy(out,q);return true;}}
static bool route(bool is_get,bool is_post,const char *target,const char *query){
 int socket=0;const char *request="test";
'''+s[start:end]+r'''
 return false;
}
int main(){
 sample.supported=sample.attached=sample.writable=1;sample.counter=456;sample.mode=2;sample.motor=1;
 strcpy(sample.filename,"USB:/é \\\" <actual>\n.tap");
 route(true,false,"/api/datasette","");assert(status==200);assert(payload.find("\"counter\":456")!=std::string::npos);
 assert(payload.find("é")!=std::string::npos);assert(payload.find("\\u000a")!=std::string::npos);assert(payload.find("\\\"")!=std::string::npos);
 const char *a[]={"stop","play","record","rewind","forward","reset","zero","eject"};
 for(int i=0;i<8;i++){queued=-1;route(false,true,"/api/datasette/control",a[i]);assert(status==202&&queued==i);}
 queued=-1;route(false,true,"/api/datasette/control","invented");assert(status==400&&queued==-1);
 header=false;route(false,true,"/api/datasette/control","play");assert(status==403&&queued==-1);header=true;
 for(int r=-2;r<=0;r++){queue_result=r;route(false,true,"/api/datasette/control","play");assert(status==(r==-1?501:409));}
 puts("PASS production Datasette API: state JSON/UTF-8/control escaping, all command mappings, 202 queued, invalid action 400, missing header 403, unavailable 501, busy/read-only 409");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-datasette-http-') as d:
 p=Path(d)/'test.cpp';exe=Path(d)/'test';p.write_text(code)
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(R/'third_party/common'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
# All routes remain behind the established PIN auth gate.
assert s.index('int auth = CheckAuth(request)')<start
print('PASS existing PIN authentication precedes new routes')
