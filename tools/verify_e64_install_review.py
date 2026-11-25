#!/usr/bin/env python3
"""Verify staged bytes, execute production Main/ROM/network code on host."""
from pathlib import Path
import os,re,subprocess,tempfile
from prepare_e64_install_review import ROOT,DEST,AUDIT,digest,snapshot,validate

def function(path,name):
    s=(ROOT/path).read_text()
    m=re.search(r'^[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M)
    assert m,name
    return s[m.start():s.index('\n}',m.end())+2]

def verify_manifest():
    expected={}
    for line in (AUDIT/'SHA256SUMS.txt').read_text().splitlines():
        h,name=line.split('  ',1);expected[name]=h
    assert snapshot(DEST)==expected, 'Staged file set or SHA-256 mismatch'

def run():
    verify_manifest();initial=snapshot(DEST)
    for path,expected in [('third_party/vice-3.3/src/drive/iec/iec-resources.c',{'dos1541','d1541II','dos1570','dos1571','dos1581','dos2000','dos4000','dosCMDHD'}),('third_party/vice-3.3/src/drive/ieee/ieee-resources.c',{'dos2031','dos2040','dos3040','dos4040','dos1001'})]:
        defaults=set(re.findall(r'\{ "DosName[^\"]+", "([^\"]+)"',(ROOT/path).read_text()))
        assert expected<=defaults
        assert all((DEST/'drives'/name).is_file() for name in expected)
    assert '"/carts/eprom.bin"' in (ROOT/'third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c').read_text()
    with tempfile.TemporaryDirectory(dir=AUDIT,prefix='host-check-') as tmp:
        tmp=Path(tmp);source=tmp/'main.c';exe=tmp/'main'
        source.write_text(r'''
#include <assert.h>
#include <string.h>
#include "configs.h"
int main(void) {
 configs_protection_init("SD"); configs_boot_init("C64/NTSC/HDMI");
 assert(configs_protection_ready() && configs_management_ready());
 assert(configs_running_is_main()); assert(!strcmp(configs_running()->name,CONFIGS_MAIN_NAME));
 assert(!*configs_boot_message()); assert(configs_list_open()==1);
 assert(!strcmp(configs_list_at(0)->id,"main")); assert(configs_list_at(1)==0);
 assert(configs_is_protected("main"));assert(configs_deleted_count()==0);
 assert(configs_set_protected("main",0,1)==CONFIGS_ERROR);
 assert(!strcmp(configs_settings_file("/settings.txt"),"/settings.txt"));
 assert(configs_vice_config()==0);assert(!*configs_autostart());
 for(int i=0;i<4;i++)assert(!*configs_startup_disk(i));
 assert(!configs_protection_can_write("/settings.txt"));
 assert(!configs_protection_can_write("/vice.ini"));
 assert(!configs_protection_external_allowed("/E64SET.NEW",1));
 assert(!configs_protection_external_allowed("/E64SET.OLD",1));
 configs_main_save_begin();assert(configs_main_save_allowed("/settings.txt"));
 assert(configs_main_save_allowed("/vice.ini"));assert(configs_main_save_allowed("/E64SET.NEW"));
 configs_main_save_end();configs_list_close();return 0;
}
''')
        subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src/configs'),str(source),str(ROOT/'tools/sdcard/sd_fs_posix.c'),str(ROOT/'src/sdcard/sd_fs_file.c'),*[str(p) for p in (ROOT/'src/configs').glob('*.c')],'-o',str(exe)],check=True)
        subprocess.run([str(exe)],env={**os.environ,'SD_TEST_ROOT':str(DEST)},check=True)
        print('PASS: production Config boot selects only protected Main; no startup media, errors, deletion state or protection journals; native save/recovery path guards intact.')
        source=tmp/'rom.c';exe=tmp/'rom'
        source.write_text(r'''
#include <assert.h>
#include <ctype.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
static const char *card;
static int c64rom_log;
static void log_error(int id,const char *fmt,...) {(void)id;(void)fmt;}
#define lib_free free
static char *lib_stralloc(const char *s){return strdup(s);}
static char *util_concat(const char *first,...) {
 char buf[2048]="";va_list a;va_start(a,first);
 for(const char *p=first;p;p=va_arg(a,const char*))strcat(buf,p);
 va_end(a);return strdup(buf);
}
static char *default_path;
#define ARCHDEP_FINDPATH_SEPARATOR_STRING ":"
static const char *archdep_boot_path(void){return "";}
SEARCH
static FILE *sysfile_open(const char *name,char **path,const char *mode) {
 char dirs[256];snprintf(dirs,sizeof(dirs),"%s",archdep_default_sysfile_pathlist("C64"));
 for(char *dir=strtok(dirs,":");dir;dir=strtok(NULL,":")) {
  char file[2048];snprintf(file,sizeof(file),"%s%s/%s",card,dir,name);
  FILE *f=fopen(file,mode);if(f){if(path)*path=strdup(file);return f;}
 }
 return NULL;
}
static long util_file_length(FILE *f){long pos=ftell(f);assert(!fseek(f,0,SEEK_END));long n=ftell(f);assert(!fseek(f,pos,SEEK_SET));return n;}
READER
int main(int argc,char **argv){assert(argc==2);card=argv[1];uint8_t data[8192];
 assert(!strcmp(archdep_default_sysfile_pathlist("C64"),"/c64:/drives:/carts:"));
 assert(read_rom_image("basic",data,8192)==0);assert(read_rom_image("kernal",data,8192)==0);
 assert(read_rom_image("chargen",data,4096)==0);assert(read_rom_image("JD-kernal",data,8192)==0);
 assert(read_rom_image("kernal-Green-on-Black",data,8192)==0);
 free(default_path);return 0;}
'''.replace('SEARCH',function('third_party/vice-3.3/src/arch/raspi/archdep.c','archdep_default_sysfile_pathlist')).replace('READER',function('third_party/vice-3.3/src/c64/c64rom.c','read_rom_image')))
        subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True)
        subprocess.run([str(exe),str(DEST)],check=True)
        print('PASS: production ROM-search builder and C64 ROM reader load actual staged stock/custom/JiffyDOS files with correct sizes; DOS filenames match production resource defaults.')
        source=tmp/'network.cpp';exe=tmp/'network'
        source.write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <string>
#include "network_config.h"
static const char *card;
extern "C" FILE *__real_fopen(const char *,const char *);
extern "C" FILE *__wrap_fopen(const char *name,const char *mode) {
 assert(!strcmp(name,"/system/network.cfg"));
 FILE *f=__real_fopen((std::string(card)+name).c_str(),mode);assert(f);return f;
}
int main(int argc,char **argv){assert(argc==2);card=argv[1];BmcNetworkConfig c;assert(LoadBmcNetworkConfig(&c));return 0;}
''')
        subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'src'),str(source),str(ROOT/'src/network_config.cpp'),'-Wl,--wrap=fopen','-o',str(exe)],check=True)
        subprocess.run([str(exe),str(DEST)],check=True)
        print('PASS: production network parser accepts preserved /system/network.cfg (credentials not printed).')
    assert snapshot(DEST)==initial,'Host verification modified staged files'
    verify_manifest();summary=validate()
    (AUDIT/'host-verification.txt').write_text('PASS: staged hashes; production Main boot/protection/save guards; production ROM search/reader; DOS default filenames/sizes; production network parser; staged files unchanged.\n')
    return summary
if __name__=='__main__':run()
