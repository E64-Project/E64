#!/usr/bin/env python3
"""Host tests of actual Web UI endpoint/list functions with filesystem/network doubles."""
from pathlib import Path
import json,re,subprocess,tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'src/webui/webui_fs.cpp').read_text()
def function(text,name):
 m=re.search(r'^(?:static )?(?:int|void) '+name+r'\([^;]*?\{',text,re.M);assert m,name
 return text[m.start():text.index('\n}',m.end())+2]+'\n'
state=re.search(r'struct ListState \{.*?\n\};',source,re.S).group()
pre=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdarg>
#include <string>
#include <map>
#include "SD_HEADER"
using boolean=bool;
#define TRUE true
#define FALSE false
struct CSocket {int status=0;std::string body;};
namespace webhttp {
static bool QueryParam(const char*q,const char*k,char*out,unsigned n){(void)k;if(q&&strstr(q,"capacity=")){snprintf(out,n,"%s",strchr(q,'=')+1);return true;}return false;}
static void SendText(CSocket*s,int status,const char*reason,const char*body){(void)reason;s->status=status;s->body=body;}
class CChunkedResponse {CSocket*s;public:
 CChunkedResponse(CSocket*p,int status,const char*,const char*):s(p){s->status=status;s->body.clear();}
 bool Write(const char*p){s->body+=p;return true;}
 bool Printf(const char*f,...){char b[2048];va_list a;va_start(a,f);vsnprintf(b,sizeof(b),f,a);va_end(a);s->body+=b;return true;}
 bool Finish(){return true;} bool Failed(){return false;}
};}
using webhttp::CChunkedResponse;
class CScheduler{public:static CScheduler*Get(){static CScheduler s;return &s;}void Yield(){}};
static const unsigned WEBUI_FS_MAX_ENTRIES=6000,WEBUI_FS_EDIT_MAX=256*1024;
static void JsonString(CChunkedResponse*r,const char*p){r->Write("\"");r->Write(p);r->Write("\"");}
static void WriteDateTime(CChunkedResponse*r,const sd_time*t){(void)r;(void)t;}
static bool IsEditablePath(const char*p){(void)p;return false;}
static bool IsProtectedPath(const char*p){(void)p;return false;}
static const char*RelPath(const char*p){return strchr(p,':')+1;}
static const char*PathVolume(const char*p){(void)p;return "USB";}
static std::string target="USB:/";
static int ResolveTarget(CSocket*,const char*,char*out,unsigned n,bool){snprintf(out,n,"%s",target.c_str());return 0;}
static int probes,lists,space_calls,entries,late_error,capacity_error,hidden_entries;
static std::string volume_label;
extern "C" int sd_volume_label(const char*,char*out,unsigned n){snprintf(out,n,"%s",volume_label.c_str());return SD_OK;}
static std::map<std::string,int> status;
int ProbeDirectory(void*,const sd_info*);
extern "C" int sd_list_info(const char*p,sd_info_cb cb,void*ctx){
 if(cb==ProbeDirectory){probes++;return status.count(p)?status[p]:SD_OK;}
 lists++;sd_info entry={};strcpy(entry.name,"file.txt");
 for(int i=0;i<entries;i++){strcpy(entry.name,hidden_entries&&i==0?"deleted":"file.txt");if(cb(ctx,&entry))break;}
 return late_error?SD_ERROR:SD_OK;
}
extern "C" int sd_space_kb_path(const char*,uint32_t*total,uint32_t*available){space_calls++;*total=1024;*available=512;return capacity_error?SD_ERROR:SD_OK;}
'''.replace('SD_HEADER',str(root/'src/sdcard/sd_fs.h'))
test=r'''
static void reset(){status.clear();probes=lists=space_calls=entries=late_error=capacity_error=hidden_entries=0;target="USB:/";}
int main(){CSocket s;
 reset();status["USB2:/"]=SD_ERROR;WebUiFsVolumes(&s,nullptr);assert(s.status==200&&probes==4&&lists==0&&space_calls==0);assert(s.body.find("USB2")==std::string::npos);puts(s.body.c_str());
 reset();volume_label="Games";WebUiFsVolumes(&s,nullptr);assert(s.body.find("\"id\":\"SD\",\"kind\":\"sdcard\",\"label\":\"Games\"")!=std::string::npos);assert(space_calls==0);volume_label.clear();
 reset();WebUiFsVolumes(&s,"capacity=1");assert(space_calls==4&&s.body.find("total_kb")!=std::string::npos);puts(s.body.c_str());
 reset();capacity_error=1;WebUiFsVolumes(&s,"capacity=1");assert(space_calls==4&&s.body.find("capacity_error")!=std::string::npos&&s.body.find("USB2")!=std::string::npos);puts(s.body.c_str());
 reset();WebUiFsVolumes(&s,"capacity=0");assert(space_calls==0);
 for(int rc:{SD_ERROR,SD_NOT_FOUND,SD_INVALID,SD_DENIED}){reset();status["USB:/"]=rc;WebUiFsList(&s,nullptr);assert(s.status==(rc==SD_ERROR?503:rc==SD_DENIED?403:404));assert(lists==0&&space_calls==0);assert(s.body.find("entries")==std::string::npos);}
 reset();target="USB:/gone";status[target]=SD_NOT_FOUND;WebUiFsList(&s,nullptr);assert(s.status==404&&lists==0);
 reset();WebUiFsList(&s,nullptr);assert(s.status==200&&lists==1&&probes==1&&space_calls==0);assert(s.body.find("\"entries\":[]")!=std::string::npos&&s.body.find("error")==std::string::npos);puts(s.body.c_str());
 reset();entries=1;late_error=1;WebUiFsList(&s,nullptr);assert(s.status==200&&s.body.find("\"error_status\":503")!=std::string::npos);puts(s.body.c_str());
 reset();entries=1;hidden_entries=1;target="SD:/configs";WebUiFsList(&s,nullptr);assert(s.body.find("\"entries\":[]")!=std::string::npos);
 reset();entries=2;hidden_entries=1;target="SD:/configs";WebUiFsList(&s,nullptr);assert(s.body.find("deleted")==std::string::npos&&s.body.find("file.txt")!=std::string::npos);
 reset();entries=6001;WebUiFsList(&s,nullptr);assert(s.body.find("\"truncated\":true")!=std::string::npos);assert(space_calls==0);
 return 0;
}
'''
lease=re.search(r'class ConfigRequestLease \{.*?\n\};',source,re.S).group()
pre += r"""
static int web_leases=0,web_busy=0;
static int configs_web_begin(){if(web_busy)return 0;web_leases++;return 1;}
static void configs_web_end(){web_leases--;}
static int configs_path_allowed(const char *path){return strstr(path,"deleted")==nullptr;}
static int configs_protection_external_allowed(const char *path,int writing){(void)writing;return strstr(path,"system/protect")==nullptr;}
""" + lease + "\n"
test=test.replace(' return 0;', ' web_busy=1;reset();WebUiFsList(&s,nullptr);assert(s.status==409&&lists==0);WebUiFsVolumes(&s,nullptr);assert(s.status==409&&probes==0&&web_leases==0);\n return 0;')
functions='\n'.join(function(source,n) for n in ['ListEntry','ProbeDirectory','SendDirectoryFailure','WebUiFsVolumes','WebUiFsList'])
# Test the real FatFs directory adapter too, including close failures.
fs=(root/'src/sdcard/sd_fs_fatfs.c').read_text()
adapter=r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "SD_HEADER"
typedef int FRESULT;
#define FR_OK 0
#define FAT_PATH_LEN 560
typedef struct {int n;} DIR;
typedef struct {char fname[256];} FILINFO;
static int open_error,read_error,close_error;
static int fat_path(const char*p,char*out,unsigned n){snprintf(out,n,"%s",p);return 0;}
static int result(int rc){return rc?SD_ERROR:SD_OK;}
static int f_opendir(DIR*d,const char*p){(void)p;d->n=0;return open_error;}
static int f_readdir(DIR*d,FILINFO*f){if(read_error)return 1;strcpy(f->fname,d->n++?"":"entry");return 0;}
static int f_closedir(DIR*d){(void)d;return close_error;}
static void to_info(const FILINFO*f,sd_info*i){memset(i,0,sizeof(*i));strcpy(i->name,f->fname);}
static int first(void*c,const sd_info*i){(void)c;(void)i;return 1;}
'''.replace('SD_HEADER',str(root/'src/sdcard/sd_fs.h'))+function(fs,'sd_list_info')+r'''
int main(void){assert(sd_list_info("USB:/",first,0)==SD_OK);close_error=1;assert(sd_list_info("USB:/",first,0)==SD_ERROR);close_error=0;read_error=1;assert(sd_list_info("USB:/",first,0)==SD_ERROR);read_error=0;open_error=1;assert(sd_list_info("USB:/",first,0)==SD_ERROR);return 0;}
'''
with tempfile.TemporaryDirectory(prefix='e64-web-fs-') as tmp:
 cpp=Path(tmp)/'endpoint.cpp';cpp.write_text(pre+state+'\n'+functions+test)
 exe=Path(tmp)/'endpoint';subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=undefined',str(cpp),'-o',str(exe)],check=True)
 lines=subprocess.check_output([str(exe)],text=True).splitlines();parsed=[json.loads(line) for line in lines]
 assert parsed[-1]['error_status']==503 and parsed[-2]['entries']==[]
 c=Path(tmp)/'adapter.c';c.write_text(adapter);exe=Path(tmp)/'adapter'
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(c),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('PASS: actual endpoint functions: lightweight volumes (zero free-space scans), explicit capacity, capacity failure, root/path errors, empty/partial/truncated listings; actual adapter open/read/close errors.')
