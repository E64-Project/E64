#!/usr/bin/env python3
"""Exercise production transfer/tree/ZIP code with fault-injected storage/transport."""
from pathlib import Path
import re, subprocess, tempfile, zipfile, io
R=Path(__file__).resolve().parents[2]
s=(R/'src/webui/webui_fs.cpp').read_text()
def fn(name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M);assert m,name
 return s[m.start():s.index('\n}',m.end())+2]+'\n'
pre=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <strings.h>
#include <cstdlib>
#include <cstdint>
#include <string>
#include <map>
#include <vector>
#include <fstream>
#include "SD_HEADER"
using boolean=bool;using u8=unsigned char;
#define TRUE true
#define FALSE false
struct CSocket {int status=0;std::string bytes;int budget=-1;};
namespace webhttp {
bool QueryParam(const char*q,const char*k,char*out,unsigned size){std::string qs=q?q:"",key=std::string(k)+"=";auto at=qs.find(key);if(at==std::string::npos)return false;auto end=qs.find('&',at);auto value=qs.substr(at+key.size(),end==std::string::npos?end:end-at-key.size());if(value.size()>=size)return false;strcpy(out,value.c_str());return true;}
void SendText(CSocket*s,int code,const char*,const char*text){s->status=code;s->bytes=text;}
void SendResponse(CSocket*s,int code,const char*,const char*,const char*text,unsigned len){s->status=code;s->bytes.assign(text,len);}
bool SendAll(CSocket*s,const void*p,unsigned n){if(s->budget==0)return false;if(s->budget>0)--s->budget;s->bytes.append((const char*)p,n);return true;}
}
class CScheduler {public:static CScheduler*Get(){static CScheduler s;return &s;}void Yield(){}};
class ConfigRequestLease {public:ConfigRequestLease(CSocket*){}bool acquired(){return true;}};
struct Node{bool dir;std::string data;};static std::map<std::string,Node> fs;
static bool fail_write=false,corrupt=false,fail_rename=false;static int write_calls=0,fail_after=0;static unsigned max_io=0;static int handles=0;static std::string busy;
struct sd_file {std::string path;unsigned pos;int mode;};
int sd_stat_info(const char*p,sd_info*i){auto at=fs.find(p);if(at==fs.end())return SD_NOT_FOUND;if(std::string(p).back()=='/')return SD_INVALID;if(i){memset(i,0,sizeof(*i));i->is_dir=at->second.dir;i->size=at->second.data.size();auto slash=std::string(p).rfind('/');strcpy(i->name,p+slash+1);}return SD_OK;}
int sd_list_info(const char*p,sd_info_cb cb,void*ctx){auto at=fs.find(p);if(at==fs.end()||!at->second.dir)return SD_NOT_FOUND;std::string prefix=p;if(prefix.back()!='/')prefix+='/';std::vector<std::string> names;for(auto &kv:fs){if(kv.first.find(prefix)!=0)continue;auto tail=kv.first.substr(prefix.size());if(!tail.empty()&&tail.find('/')==std::string::npos)names.push_back(kv.first);}for(auto &name:names){sd_info info;assert(sd_stat_info(name.c_str(),&info)==SD_OK);if(cb(ctx,&info))break;}return SD_OK;}
sd_file*sd_open(const char*p,int mode){if(mode==SD_READ){if(!fs.count(p)||fs[p].dir)return nullptr;}else{if(fs.count(p))return nullptr;fs[p]={false,""};}++handles;return new sd_file{p,0,mode};}
uint32_t sd_size(sd_file*f){return fs[f->path].data.size();}
int sd_read(sd_file*f,void*p,unsigned n,unsigned*got){assert(n<=32768);max_io=std::max(max_io,n);auto &data=fs[f->path].data;*got=std::min(n,(unsigned)data.size()-f->pos);memcpy(p,data.data()+f->pos,*got);f->pos+=*got;return SD_OK;}
int sd_write(sd_file*f,const void*p,unsigned n){assert(n<=32768);if(fail_write|| (fail_after && ++write_calls>=fail_after))return SD_ERROR;fs[f->path].data.append((const char*)p,n);if(corrupt&&fs[f->path].data.size()==n)fs[f->path].data[0]^=1;return SD_OK;}
int sd_close(sd_file*f){--handles;delete f;return SD_OK;}
int sd_set_mtime(const char*,const sd_time*){return SD_OK;}
int sd_mkdir(const char*p){if(fs.count(p))return SD_EXISTS;fs[p]={true,""};return SD_OK;}
int sd_unlink(const char*p){std::string prefix=std::string(p)+"/";for(auto &kv:fs)if(kv.first.find(prefix)==0)return SD_DENIED;return fs.erase(p)?SD_OK:SD_NOT_FOUND;}
int sd_rename(const char*a,const char*b){if(fail_rename)return SD_ERROR;if(fs.count(b)||!fs.count(a))return SD_EXISTS;std::map<std::string,Node> moved;std::string prefix=std::string(a)+"/";for(auto it=fs.begin();it!=fs.end();){if(it->first==a||it->first.find(prefix)==0){moved[std::string(b)+it->first.substr(strlen(a))]=it->second;it=fs.erase(it);}else ++it;}fs.insert(moved.begin(),moved.end());return SD_OK;}
static bool configs_path_allowed(const char*p){return !strstr(p,"deleted");}
static bool configs_protection_external_allowed(const char*p,int){return !strstr(p,"/system/protect");}
static bool configs_path_is_managed(const char*p){return strstr(p,"/configs")!=nullptr;}
static bool configs_protection_can_remove(const char*p){return !strstr(p,"factory");}
static bool IsProtectedPath(const char*p){return strstr(p,"/firmware")||strstr(p,"config.txt");}
static int emux_storage_path_busy(const char*p){return !busy.empty()&&(busy==p||busy.find(std::string(p)+"/")==0);}
static const char*RelPath(const char*p){return strchr(p,':')+1;}
static const char*WEBUI_DATA_VOLUME="USB";static const unsigned WEBUI_FS_MAX_ENTRIES=6000;static u8 s_io_buffer[32768];
static const unsigned short kCp850High[128]={0x00c7};
'''.replace('SD_HEADER',str(R/'src/sdcard/sd_fs.h'))
# ResolveTarget uses only production path parsing and guards.
code=pre+'\n'.join(fn(n) for n in ['AllowedVolume','FatVolume','PathVolume','SanitizeRelPath','ResolveTarget','CiEqual','ProbeDirectory'])+'\n'+(R/'src/webui/webui_fs_tree.h').read_text()+'\n'+fn('WebUiFsTransfer')+fn('WebUiFsDownloadFolder')
test=r'''
static void reset(){assert(handles==0);fs.clear();for(auto v:{"SD:/","USB:/","USB2:/","USB3:/"})fs[v]={true,""};fail_write=corrupt=fail_rename=false;write_calls=fail_after=0;busy.clear();}
static void folder(){fs["USB:/Games"]={true,""};fs["USB:/Games/nested"]={true,""};fs["USB:/Games/nested/a.prg"]={false,std::string(100000,'a')};fs["USB:/Games/empty"]={true,""};}
static void transfer(CSocket&s,const char*q){s={};WebUiFsTransfer(&s,q);assert(handles==0);}
int main(int argc,char**argv){CSocket s;
// Root API destination and fully qualified filename forms on all target volumes.
for(auto v:{"SD","USB","USB2","USB3"}){reset();fs["USB:/from"]={true,""};fs["USB:/from/file.prg"]={false,"abc"};std::string q="vol=USB&path=/from/file.prg&dest_vol="+std::string(v)+"&dest_path=/&move=1";transfer(s,q.c_str());assert(s.status==200);assert(!fs.count("USB:/from/file.prg"));assert(fs[std::string(v)+":/file.prg"].data=="abc");}
// Populated roots must behave exactly like empty roots, for files and folders.
for(auto v:{"SD","USB","USB2","USB3"})for(int count:{0,1,4})for(bool dir:{false,true}){
 reset();std::string root=std::string(v)+":/";
 for(int i=0;i<count;++i)fs[root+"existing"+std::to_string(i)]={true,""};
 fs["USB:/from"]={true,""};fs["USB:/from/payload"]={dir,dir?"":"file data"};
 if(dir)fs["USB:/from/payload/child"]={false,"child data"};
 std::string q="vol=USB&path=/from/payload&dest_vol="+std::string(v)+"&dest_path=/&move=1";
 transfer(s,q.c_str());assert(s.status==200&&!fs.count("USB:/from/payload"));
 assert(fs.count(root+"payload"));if(dir)assert(fs[root+"payload/child"].data=="child data");
 for(int i=0;i<count;++i)assert(fs.count(root+"existing"+std::to_string(i)));
}
reset();folder();fs["USB:/Other"]={true,""};transfer(s,"vol=USB&path=/Games&dest_vol=USB&dest_path=/Other/Games&move=1");assert(s.status==200&&fs.count("USB:/Other/Games/nested/a.prg")&&!fs.count("USB:/Games"));
reset();folder();fs["USB:/Other"]={true,""};assert(sd_rename("USB:/Games","USB:/Other/Games")==SD_OK);transfer(s,"vol=USB&path=/Other/Games&dest_vol=USB&dest_path=/&move=1");assert(s.status==200&&fs.count("USB:/Games/nested/a.prg"));
reset();folder();transfer(s,"vol=USB&path=/Games&dest_vol=SD&dest_path=/Games&move=1");assert(s.status==200&&!fs.count("USB:/Games")&&fs["SD:/Games/nested/a.prg"].data==std::string(100000,'a'));
reset();folder();fs["SD:/Games"]={true,""};transfer(s,"vol=USB&path=/Games&dest_vol=SD&dest_path=/Games&move=1");assert(s.status==409&&fs.count("USB:/Games/nested/a.prg"));
for(auto dest:{"/Games","/Games/nested/Games","/games/next"}){reset();folder();std::string q="vol=USB&path=/Games&dest_vol=USB&dest_path="+std::string(dest)+"&move=1";transfer(s,q.c_str());assert(s.status==409&&fs.count("USB:/Games/nested/a.prg"));}
for(int failure=0;failure<3;++failure){reset();folder();fail_write=failure==0;corrupt=failure==1;fail_rename=failure==2;transfer(s,"vol=USB&path=/Games&dest_vol=SD&dest_path=/Games&move=1");assert(s.status==500&&fs["USB:/Games/nested/a.prg"].data==std::string(100000,'a')&&!fs.count("SD:/Games"));}
reset();folder();fail_after=2;transfer(s,"vol=USB&path=/Games&dest_vol=SD&dest_path=/Games&move=1");assert(s.status==500&&fs["USB:/Games/nested/a.prg"].data==std::string(100000,'a')&&fs["SD:/Games.part/nested/a.prg"].data.size()==32768);
reset();fs["USB:/file"]={false,"original"};fs["SD:/file"]={false,"existing"};transfer(s,"vol=USB&path=/file&dest_vol=SD&dest_path=/&move=1");assert(s.status==409&&fs["USB:/file"].data=="original"&&fs["SD:/file"].data=="existing");
reset();folder();busy="USB:/Games/nested/a.prg";transfer(s,"vol=USB&path=/Games&dest_vol=SD&dest_path=/Games&move=1");assert(s.status==403&&fs.count("USB:/Games"));
reset();folder();fs["USB:/Games/config.txt"]={false,"secret"};transfer(s,"vol=USB&path=/Games&dest_vol=SD&dest_path=/Games&move=1");assert(s.status==409&&!fs.count("SD:/Games.part"));
reset();folder();transfer(s,"vol=USB&path=/Games&dest_vol=SD&dest_path=/../Games&move=1");assert(s.status==400);
reset();folder();fs["USB:/Games/config.txt"]={false,"secret"};s={};WebUiFsDownloadFolder(&s,"vol=USB&path=/Games");assert(handles==0);assert(s.bytes.find("Content-Type: application/zip")!=std::string::npos);std::ofstream(argv[1],std::ios::binary)<<s.bytes;
reset();folder();s={};s.budget=4;WebUiFsDownloadFolder(&s,"vol=USB&path=/Games");assert(handles==0&&s.bytes.find(std::string("PK\x05\x06",4))==std::string::npos);
reset();folder();fs["USB:/Games/zero"]={false,""};fs["USB:/Games/\x80.prg"]={false,"OEM"};s={};WebUiFsDownloadFolder(&s,"vol=USB&path=/Games");assert(handles==0);std::ofstream(std::string(argv[1])+"-unicode",std::ios::binary)<<s.bytes;
reset();folder();for(unsigned i=0;i<6000;++i)fs["USB:/Games/file"+std::to_string(i)]={false,""};transfer(s,"vol=USB&path=/Games&dest_vol=SD&dest_path=/Games&move=1");assert(s.status==409&&fs.count("USB:/Games/nested/a.prg")&&!fs.count("SD:/Games.part"));
assert(TreeContains("USB:/\x81", "USB:/\x9a/child"));
assert(max_io==32768);puts("PASS: production root/file/folder/same/cross-volume moves, collisions/self/descendant/traversal/protection/active media, write/corruption/rename failures preserve source; ZIP and disconnect close handles; 32 KB I/O bound");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-r3-storage-') as tmp:
 p=Path(tmp);cpp=p/'test.cpp';cpp.write_text(code+test)
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=undefined',str(cpp),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test'),str(p/'response')],check=True)
 response=(p/'response').read_bytes();headers,body=response.split(b'\r\n\r\n',1)
 length=int(re.search(rb'Content-Length: (\d+)',headers)[1]);assert len(body)==length
 assert b'filename="Games.zip"' in headers
 with zipfile.ZipFile(io.BytesIO(body)) as z:
  assert z.testzip() is None
  assert set(z.namelist())=={'Games/','Games/nested/','Games/empty/','Games/nested/a.prg'}
  assert z.read('Games/nested/a.prg')==b'a'*100000
  assert all(x.compress_type==zipfile.ZIP_STORED for x in z.infolist())
 with zipfile.ZipFile(io.BytesIO((p/'response-unicode').read_bytes().split(b'\r\n\r\n',1)[1])) as z:
  assert z.testzip() is None and z.read('Games/Ç.prg')==b'OEM' and z.read('Games/zero')==b''
 print('PASS: Python independent ZIP parser verifies CRCs, STORE, hierarchy, empty folders, protected exclusion and HTTP content length')
