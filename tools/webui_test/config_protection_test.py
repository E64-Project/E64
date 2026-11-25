#!/usr/bin/env python3
"""Production HTTP protection route: forged Main/Off requests and busy handling."""
from pathlib import Path
import re,tempfile,subprocess
root=Path(__file__).resolve().parents[2];source=(root/'src/webui/webui.cpp').read_text()
a=source.index('  if (strcmp(target, "/api/configs/protection") == 0) {');b=source.index('  if (strcmp(target, "/api/configs/deleted")',a);route=source[a:b]
a=source.index('boolean IsConfigId(');b=source.index('\n}',a)+2;valid=source[a:b]
pre=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdarg>
#include <string>
#include <map>
#include "HEADER"
using boolean=bool;
#define TRUE true
#define FALSE false
struct CSocket{int status;std::string body;};
static std::map<std::string,std::string> params;static bool header=true,queue_ready=true;static int calls,on_value,confirmed_value;static std::string queued_id;
static bool HasHeader(const char*,const char*){return header;}
static void SendText(CSocket*s,int n,const char*,const char*t){s->status=n;s->body=t;}
static void SendResponse(CSocket*s,int n,const char*,const char*,const char*t,unsigned){s->status=n;s->body=t;}
static void JsonText(const char*p,char*out,unsigned n){snprintf(out,n,"%s",p);}
static void menu_configs_clear_start_error(){}
static const char*menu_configs_start_error(){return "";}
static bool emu_config_protection_interrupt(const char*id,int on,int confirmed){if(!queue_ready)return false;calls++;queued_id=id;on_value=on;confirmed_value=confirmed;return true;}
extern "C" int configs_is_factory(const char *id){return id && (!strcmp(id,CONFIGS_FACTORY_NTSC)||!strcmp(id,CONFIGS_FACTORY_PAL));}
extern "C" int configs_protection_read_begin(){return 1;}
extern "C" void configs_protection_read_end(){}
extern "C" int configs_protection_ready(){return 1;}
extern "C" const char*configs_protection_error(){return "";}
extern "C" unsigned configs_protected_count(){return 1;}
extern "C" const char*configs_protected_id(unsigned){return "geos";}
namespace webhttp{
static bool QueryParam(const char*,const char*k,char*out,unsigned n){auto i=params.find(k);if(i==params.end())return false;snprintf(out,n,"%s",i->second.c_str());return true;}
class CChunkedResponse{CSocket*s;public:CChunkedResponse(CSocket*p,int n,const char*,const char*):s(p){s->status=n;s->body.clear();}void Write(const char*p){s->body+=p;}void Printf(const char*f,...){char b[1024];va_list args;va_start(args,f);vsnprintf(b,sizeof(b),f,args);va_end(args);s->body+=b;}void Finish(){}};
}
'''.replace('HEADER',str(root/'src/configs/configs.h'))
body='static bool request(CSocket*socket,bool is_post){const char*target="/api/configs/protection",*request="",*query="";\n'+route+'return false;\n}\n'
tests=r'''
int main(){CSocket s;params={{"id","geos"},{"on","0"}};
request(&s,true);assert(s.status==409&&calls==0);
params["confirmed"]="1";params["id"]="main";request(&s,true);assert(s.status==400&&calls==0);
params["id"]=CONFIGS_FACTORY_NTSC;request(&s,true);assert(s.status==403&&calls==0);
params["id"]=CONFIGS_FACTORY_PAL;request(&s,true);assert(s.status==403&&calls==0);
params["id"]="../main";request(&s,true);assert(s.status==400&&calls==0);
params["id"]="geos";header=false;request(&s,true);assert(s.status==403&&calls==0);
header=true;request(&s,true);assert(s.status==202&&calls==1&&queued_id=="geos"&&!on_value&&confirmed_value);
params["on"]="1";params.erase("confirmed");request(&s,true);assert(s.status==202&&calls==2&&on_value&&!confirmed_value);
queue_ready=false;request(&s,true);assert(s.status==409&&calls==2);
request(&s,false);assert(s.status==200&&s.body.find("main_protected")==std::string::npos&&s.body.find("geos")!=std::string::npos);
}
'''
with tempfile.TemporaryDirectory(prefix='e64-protection-web-') as tmp:
 p=Path(tmp)/'test.cpp';p.write_text(pre+valid+'\n'+body+tests);exe=Path(tmp)/'test'
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('PASS: production HTTP route rejects retired identities and factory Off, unconfirmed Off, invalid IDs, missing header and busy queue; factory identities protected; retired snapshot field absent.')
