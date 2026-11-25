#!/usr/bin/env python3
"""Execute production FatFs label adapter and VICE active-media checks."""
from pathlib import Path
import re,subprocess,tempfile
R=Path(__file__).resolve().parents[2]
def fn(source,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',source,re.M);assert m,name
 return source[m.start():source.index('\n}',m.end())+2]+'\n'
fat=(R/'src/sdcard/sd_fs_fatfs.c').read_text();vice=(R/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
pre=r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <strings.h>
#include <string>
#include <map>
#include "SD_HEADER"
#define FAT_PATH_LEN 640
#define FR_OK 0
#define CARTRIDGE_IDE64 39
using FRESULT=int;
static std::string label;static int label_error;
static int fat_path(const char*p,char*out,unsigned n){snprintf(out,n,"%s",p);return 0;}
static int result(int r){return r?SD_ERROR:SD_OK;}
static int f_getlabel(const char*path,char*out,void*){assert(!strcmp(path,"USB2:/"));strcpy(out,label.c_str());return label_error;}
static std::string drives[4],tape,cart;
static std::map<std::string,std::string> resources;static std::map<std::string,int> ints;
static const char*file_system_get_disk_name(unsigned unit){return drives[unit-8].c_str();}
static const char*tape_get_file_name(){return tape.c_str();}
static const char*current_cart(){return cart.c_str();}
static const char*(*cartridge_current_filename)()=current_cart;
static int resources_get_string(const char*key,const char**out){if(!resources.count(key))return -1;*out=resources[key].c_str();return 0;}
static int resources_get_int(const char*key,int*out){if(!ints.count(key))return -1;*out=ints[key];return 0;}
'''.replace('SD_HEADER',str(R/'src/sdcard/sd_fs.h'))
code=pre+fn(fat,'sd_volume_label')+fn(vice,'storage_contains_media')+fn(vice,'emux_storage_path_busy')+r'''
int main(){char out[256];
label="Games";assert(sd_volume_label("USB2:/",out,sizeof(out))==SD_OK&&!strcmp(out,"Games"));
label="\nFiles\t";assert(sd_volume_label("USB2:/",out,sizeof(out))==SD_OK&&!strcmp(out,"Files"));
label.clear();assert(sd_volume_label("USB2:/",out,sizeof(out))==SD_OK&&!out[0]);
label="Reconnected";assert(sd_volume_label("USB2:/",out,sizeof(out))==SD_OK&&!strcmp(out,"Reconnected"));
label_error=1;assert(sd_volume_label("USB2:/",out,sizeof(out))==SD_ERROR&&!out[0]);
assert(!emux_storage_path_busy("USB:/Games"));
drives[0]="USB:/Games/image.d64";assert(emux_storage_path_busy("usb:/games"));assert(emux_storage_path_busy("USB:/Games/image.d64"));assert(!emux_storage_path_busy("USB:/Games2"));assert(!emux_storage_path_busy("SD:/Games"));drives[0].clear();
tape="/Tapes/file.tap";assert(emux_storage_path_busy("SD:/Tapes"));tape.clear();
cart="USB2:/Carts/cart.crt";assert(emux_storage_path_busy("USB2:/Carts"));cart.clear();
resources["REUfilename"]="USB:/Games/image.reu";ints["REU"]=0;assert(!emux_storage_path_busy("USB:/Games"));ints["REU"]=1;assert(emux_storage_path_busy("USB:/Games"));resources.clear();ints.clear();
resources["IDE64image1"]="USB:/HD/work.hdd";ints["CartridgeType"]=CARTRIDGE_IDE64;assert(emux_storage_path_busy("USB:/HD"));resources.clear();ints.clear();
drives[0]="unresolved.d64";assert(emux_storage_path_busy("USB:/Games"));
puts("PASS: actual filesystem label read/sanitize/empty/reconnect/error; active disk/tape/cart/REU/IDE64 protection, case/volume/ancestor comparisons and conservative unresolved-media rejection");
}
'''
with tempfile.TemporaryDirectory(prefix='e64-r3-native-storage-') as tmp:
 p=Path(tmp);(p/'test.cpp').write_text(code)
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
