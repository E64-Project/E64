#!/usr/bin/env python3
"""Production streamed Web Config save helper + production storage on temp cards."""
from pathlib import Path
import re, subprocess, tempfile, os
root=Path(__file__).resolve().parents[2]
s=(root/'src/webui/webui_fs.cpp').read_text()
def function(name):
    m=re.search(r'^(?:boolean|BodyResult|void|const char \*)\s*'+name+r'\([^;]*?\{',s,re.M)
    assert m,name
    return s[m.start():s.index('\n}',m.end())+2]+'\n'
C=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <cstdlib>
#include "configs.h"
#include "sd_fs.h"
using boolean=bool;
#define TRUE true
#define FALSE false
static unsigned char s_io_buffer[8];
struct CSocket {
 int status=0;std::string body,input;unsigned pos=0;bool abort=false;
 int Receive(void*p,unsigned n,int){if(abort)return -1;unsigned k=input.size()-pos;if(k>n)k=n;memcpy(p,input.data()+pos,k);pos+=k;return k;}
};
class CScheduler {public:static CScheduler*Get(){static CScheduler x;return &x;}void Yield(){}};
namespace webhttp {
static void SendText(CSocket*s,int n,const char*,const char*p){s->status=n;s->body=p;}
static void SendResponse(CSocket*s,int n,const char*,const char*,const char*p,unsigned size){s->status=n;s->body.assign(p,size);}
static bool QueryParam(const char*q,const char*,char*p,unsigned n){if(!q||!*q)return false;snprintf(p,n,"2025-01-02T03:04:06");return true;}
}
static const char*RelPath(const char*p){const char*c=strchr(p,':');return c?c+1:p;}
static bool CiEqual(const char*a,const char*b){return !strcasecmp(a,b);}
static bool IsConfigFilePath(const char*p){return strstr(p,"/configs/")!=nullptr&&strchr(strstr(p,"/configs/")+9,'/')!=nullptr;}
static bool ParseDateTime(const char*,sd_time*t){memset(t,0,sizeof(*t));t->year=2025;t->month=1;t->day=2;t->hour=3;t->minute=4;t->second=6;return true;}
enum BodyResult {BODY_OK,BODY_CREATE_FAILED,BODY_WRITE_FAILED,BODY_TRUNCATED,BODY_HAS_NUL};
'''+function('InConfigsFolder')+function('ReceiveBodyToFile')+function('SendBodyFailure')+function('SaveUserConfig')+r'''
static void put(const char*p,const char*b){assert(sd_write_file(p,b,strlen(b))==SD_OK);}
static std::string read(const char*p){char b[1024];int n=sd_read_file(p,b,sizeof(b));assert(n>=0);return std::string(b,n);}
int main(){
 configs_boot_init("C64/PAL/HDMI");assert(sd_mkdir("/configs")==SD_OK);assert(sd_mkdir("/configs/geos")==SD_OK);
 const char*path="/configs/geos/config.txt";
 put(path,"name=Original\nmachine=C64\nunknown=keep\n");
 auto old=read(path);CSocket socket;socket.input="name=Browser Name\nmachine=C64\nunknown=still here\n";
 assert(SaveUserConfig(&socket,"",path,nullptr,0,socket.input.size(),true,true));assert(socket.status==200);
 assert(read(path)==socket.input&&read("/configs/geos/config.txt.bak")==old);
 assert(socket.body.find("\"ok\":true")!=std::string::npos);
 old=read(path);socket={};socket.input="bad";
 assert(SaveUserConfig(&socket,"",path,nullptr,0,3,false,false)&&socket.status==409);assert(read(path)==old);
 socket={};socket.input="partial";socket.abort=true;
 assert(SaveUserConfig(&socket,"",path,nullptr,0,20,true,true)&&socket.status!=200);assert(read(path)==old);
 socket={};unsigned char nul[]={1,0,2};
 assert(SaveUserConfig(&socket,"",path,nul,3,3,true,true)&&socket.status!=200);assert(read(path)==old);
 socket={};socket.input="replacement";
 assert(configs_storage_begin("geos")==0);
 assert(SaveUserConfig(&socket,"",path,nullptr,0,11,true,true)&&socket.status==409);configs_storage_end();assert(read(path)==old);
 /* Upload preserves mtime and never changes the editor's existing backup. */
 socket={};socket.input="[C64]\ncustom=1\n";
 assert(SaveUserConfig(&socket,"mtime", "/configs/geos/vice.ini",nullptr,0,socket.input.size(),false,true)&&socket.status==200);
 sd_info info;assert(sd_stat_info("/configs/geos/vice.ini",&info)==0&&info.mtime.year==2025&&info.mtime.second==6);
 /* Recovery precedes overwrite checks, so an OLD-only file still exists. */
 assert(sd_rename(path,"/configs/geos/config.txt.e64-old")==0);
 socket={};socket.input="new";
 assert(SaveUserConfig(&socket,"",path,nullptr,0,3,false,false)&&socket.status==409);assert(read(path)==old);
 socket={};assert(!SaveUserConfig(&socket,"","/other/file.txt",nullptr,0,0,true,true));assert(socket.status==0);
 socket={};assert(!SaveUserConfig(&socket,"","/configs/main/config.txt",nullptr,0,0,true,true));
 assert(!configs_protection_external_allowed("/configs/main/config.txt",1));
 assert(configs_storage_recover_all()==0);
 puts("PASS: production Web Config stream/save/upload, exact bytes, .bak, overwrite checks after recovery, aborted/NUL body, busy lease, retired-file protection and upload mtime");
}
'''
# Both production entry points must dispatch to the tested helper.
for name in ['WebUiFsSave','WebUiFsUpload']:
    assert 'SaveUserConfig(' in function(name)
with tempfile.TemporaryDirectory(prefix='e64-web-storage-') as tmp:
    tmp=Path(tmp);card=tmp/'card';card.mkdir();src=tmp/'test.cpp';src.write_text(C)
    inc=['-I'+str(root/'src/configs'),'-I'+str(root/'src/sdcard')]
    objects=[]
    for i,p in enumerate([root/'tools/sdcard/sd_fs_posix.c',root/'src/sdcard/sd_fs_file.c',*(root/'src/configs').glob('*.c')]):
        obj=tmp/f'{i}.o';objects.append(str(obj))
        subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=undefined',*inc,'-c',str(p),'-o',str(obj)],check=True)
    exe=tmp/'test'
    subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=undefined',*inc,str(src),*objects,'-o',str(exe)],check=True)
    subprocess.run([str(exe)],env=dict(os.environ,SD_TEST_ROOT=str(card)),check=True)
