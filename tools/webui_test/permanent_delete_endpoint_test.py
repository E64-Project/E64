#!/usr/bin/env python3
"""Compile the production permanent-deletion HTTP route in isolation."""
from pathlib import Path
import subprocess,tempfile
r=Path(__file__).resolve().parents[2];source=(r/'src/webui/webui.cpp').read_text()
# Reuse the existing HTTP test transport without executing its tests.
ns={'__file__':str(r/'tools/webui_test/config_protection_test.py')}
prefix=(r/'tools/webui_test/config_protection_test.py').read_text().split("body='static bool request",1)[0];exec(prefix,ns)
pre=ns['pre'];a=source.index('  if (strcmp(target, "/api/configs/deleted")');b=source.index('  if (is_post && strcmp(target, "/api/configs/start")',a);route=source[a:b]
pre+=r'''
static int legacy_value;
static unsigned emu_config_logical_interrupt(const char*id,int legacy){if(!queue_ready)return 0;calls++;queued_id=id;legacy_value=legacy;return 42;}
extern "C" int configs_web_begin(){return 1;}
extern "C" void configs_web_end(){}
extern "C" int configs_management_ready(){return 1;}
extern "C" int configs_deleted_count(){return 1;}
extern "C" const char *configs_deleted_id(unsigned){return "old";}
extern "C" const char *configs_deleted_name(unsigned){return "Old Config";}
static void menu_configs_delete_status(unsigned *serial,int *state,char *id,unsigned n,char *error,unsigned m){*serial=42;*state=-1;snprintf(id,n,"test");snprintf(error,m,"disk error");}
'''
body='static bool request(CSocket*socket,bool is_post){const char*target="/api/configs/deleted",*request="",*query="";\n'+route+'return false;\n}\n'
tests=r'''
int main(){CSocket s;params={{"id","test"}};
request(&s,true);assert(s.status==400&&!calls);
params["permanent"]="1";request(&s,true);assert(s.status==400&&!calls);
params["confirmed"]="1";header=false;request(&s,true);assert(s.status==403&&!calls);
header=true;for(auto id:{"main","../test",CONFIGS_FACTORY_NTSC,CONFIGS_FACTORY_PAL}){params["id"]=id;request(&s,true);assert(s.status==400&&!calls);}
params["id"]="test";params["restore"]="1";request(&s,true);assert(s.status==400&&!calls);params.erase("restore");
request(&s,true);assert(s.status==202&&calls==1&&queued_id=="test"&&!legacy_value&&s.body.find("42")!=std::string::npos);
params["legacy"]="1";request(&s,true);assert(s.status==202&&calls==2&&legacy_value);
queue_ready=false;request(&s,true);assert(s.status==409&&calls==2);
request(&s,false);assert(s.status==200&&s.body.find("Old Config")!=std::string::npos&&s.body.find("disk error")!=std::string::npos&&s.body.find("request_id")!=std::string::npos&&s.body.find("remaining")==std::string::npos);
}
'''
with tempfile.TemporaryDirectory(prefix='e64-delete-endpoint-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(pre+ns['valid']+body+tests)
 subprocess.run(['g++','-std=c++17','-fsanitize=undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True);subprocess.run([str(p/'test')],check=True)
print('PASS: production deletion endpoint requires header and confirmed permanent request; rejects factories/invalid/stale Restore; explicit legacy flag, busy queue and operation-specific result')
