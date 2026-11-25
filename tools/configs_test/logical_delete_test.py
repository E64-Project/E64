#!/usr/bin/env python3
"""Permanent deletion and frozen legacy journals on isolated synthetic cards."""
from pathlib import Path
import os,subprocess,tempfile,shutil,struct,zlib
root=Path(__file__).resolve().parents[2]
C=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "configs_internal.h"
#include "sd_fs.h"
static const char *fault="";static sd_file *written;
static int runtime(const char *id){return !strcmp(id,"victim");}
int __real_sd_remove_tree(const char*,unsigned*,void(*)(void*),void*);
int __wrap_sd_remove_tree(const char*p,unsigned*n,void(*cb)(void*),void*ctx){if(!strcmp(fault,"child")&&strstr(p,"associated.bin"))return SD_ERROR;return __real_sd_remove_tree(p,n,cb,ctx);}
int __real_sd_unlink(const char*);
int __wrap_sd_unlink(const char*p){if((!strcmp(fault,"metadata")&&strstr(p,"victim/config.txt"))||(!strcmp(fault,"folder")&&!strcmp(p,"/configs/victim")))return SD_ERROR;return __real_sd_unlink(p);}
sd_file *__real_sd_open(const char*,int);
sd_file *__wrap_sd_open(const char*p,int m){if(m!=SD_READ&&strstr(p,"system/deleted")&&!strcmp(fault,"open"))return NULL;sd_file*f=__real_sd_open(p,m);if(m!=SD_READ&&strstr(p,"system/deleted"))written=f;return f;}
int __real_sd_write(sd_file*,const void*,unsigned);
int __wrap_sd_write(sd_file*f,const void*p,unsigned n){if(f==written&&!strcmp(fault,"write"))return SD_ERROR;return __real_sd_write(f,p,n);}
int __real_sd_sync(sd_file*);
int __wrap_sd_sync(sd_file*f){int rc=__real_sd_sync(f);return f==written&&!strcmp(fault,"sync")?SD_ERROR:rc;}
int __real_sd_close(sd_file*);
int __wrap_sd_close(sd_file*f){int bad=f==written;int rc=__real_sd_close(f);if(bad){written=NULL;if(!strcmp(fault,"close"))return SD_ERROR;}return rc;}
int main(int argc,char**argv){assert(argc>1);configs_boot_init("C64/NTSC/HDMI");const char*action=argv[1];fault=argc>2?argv[2]:"";int rc=0;
 if(!strcmp(action,"delete"))rc=configs_delete("victim");
 else if(!strcmp(action,"cleanup"))rc=configs_purge_legacy("victim");
 else if(!strcmp(action,"startup")){for(int i=0;i<20;i++){configs_successful_startup();configs_boot_init("C64/NTSC/HDMI");}return 0;}
 else if(!strcmp(action,"reuse")){assert(configs_delete("victim")==0);char id[33];assert(configs_create("Victim",id,sizeof(id))==0&&!strcmp(id,"victim"));assert(configs_create("Victim",id,sizeof(id))==0&&!strcmp(id,"victim-2"));assert(configs_protection_status("victim")==0);return 0;}
 else if(!strcmp(action,"lease")){int lease=configs_path_acquire("SD:/configs/victim/vice.ini");assert(lease>0);assert(configs_delete("victim")<0);configs_path_release(lease);return 0;}
 else if(!strcmp(action,"web")){assert(configs_web_begin());assert(configs_delete("victim")<0);configs_web_end();return 0;}
 else if(!strcmp(action,"runtime")){configs_set_runtime_guard(runtime);assert(configs_delete("victim")<0);return 0;}
 else if(!strcmp(action,"protect")){assert(configs_set_protected("victim",1,0)==0);assert(configs_delete("victim")<0);return 0;}
 else if(!strcmp(action,"factory")){assert(configs_delete(CONFIGS_FACTORY_NTSC)<0&&configs_delete(CONFIGS_FACTORY_PAL)<0);assert(configs_delete("main")<0);assert(configs_delete("../victim")<0);assert(configs_delete(NULL)<0);return 0;}
 else if(!strcmp(action,"legacy-blocked")){assert(!configs_is_active("victim"));assert(configs_delete("victim")<0);assert(configs_restore("victim")<0);char id[33];assert(configs_make_id("Victim",id,sizeof(id))==0&&strcmp(id,"victim"));return 0;}
 else if(!strcmp(action,"legacy-reuse")){assert(configs_purge_legacy("victim")==0);assert(configs_deleted_count()==1);char id[33];assert(configs_create("Victim",id,sizeof(id))==0&&!strcmp(id,"victim"));return 0;}
 else if(!strcmp(action,"pal")){int count=configs_list_open(),factory=0;for(int i=0;i<count;i++){const ConfigInfo*p=configs_list_at(i);if(configs_is_factory(p->id)){factory++;assert(!strcmp(p->id,CONFIGS_FACTORY_NTSC)&&!strcmp(p->name,"Default"));}}assert(factory==1);configs_list_close();assert(configs_switch_to(CONFIGS_FACTORY_PAL)==0);configs_boot_init("C64/PAL/HDMI");assert(!strcmp(configs_running()->name,"Default"));char id[33];assert(configs_create("PAL Custom",id,sizeof(id))==0);ConfigFile pf;assert(config_file_read(id,&pf)==0&&!strcmp(pf.info.machine,"C64/PAL/HDMI"));configs_machine_switched("C64/NTSC/HDMI");ActiveFile af;assert(active_file_read(&af)==0&&!strcmp(af.config,CONFIGS_FACTORY_NTSC));configs_machine_switched("C64/PAL/HDMI");assert(active_file_read(&af)==0&&!strcmp(af.config,CONFIGS_FACTORY_PAL));return 0;}
 else return 99;
 if(rc){puts(configs_management_error());return 10;}return 0;
}
'''
def snapshot(p):return {str(f.relative_to(p)):f.read_bytes() for f in p.rglob('*') if f.is_file()}
with tempfile.TemporaryDirectory(prefix='e64-permanent-delete-') as directory:
 t=Path(directory);(t/'test.c').write_text(C);exe=t/'test';card=t/'card';checks=0
 cmd=['cc','-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-I'+str(root/'src/configs'),'-I'+str(root/'src/sdcard'),str(t/'test.c'),str(root/'tools/sdcard/sd_fs_posix.c'),str(root/'src/sdcard/sd_fs_file.c')]+[str(p) for p in (root/'src/configs').glob('*.c')]+['-Wl,--wrap='+name for name in ['sd_remove_tree','sd_unlink','sd_open','sd_write','sd_sync','sd_close']]+['-o',str(exe)]
 subprocess.run(cmd,check=True)
 def setup(selection='config=_factory-ntsc\n',legacy=False):
  if card.exists():shutil.rmtree(card)
  for name in ['victim','work']:
   path=card/'configs'/name;path.mkdir(parents=True);(path/'config.txt').write_text('name='+name.title()+'\nmachine=C64\n');(path/'vice.ini').write_text('[C64]\nKernalName=kernal\n')
  (card/'configs/victim/associated.bin').write_bytes(bytes(range(256)));(card/'configs/victim/subdir').mkdir();(card/'configs/victim/subdir/notes.txt').write_text('owned asset')
  (card/'configs/victim/empty').mkdir();(card/'control').write_text('preserve');
  if selection is not None:(card/'configs/active.txt').write_text(selection)
  if legacy:
   (card/'configs/old-other').mkdir();(card/'configs/old-other/config.txt').write_text('name=Other old\nmachine=C64\n')
   journal=card/'system/deleted';journal.mkdir(parents=True);(card/'system/deleted.id').write_bytes(b'E64-LOGICAL-V1'.ljust(16,b'\0'))
   image=bytearray(4096);image[:8]=b'E64DEL1\0';struct.pack_into('<III',image,8,1,1,2)
   for index,name in enumerate(['victim','old-other']):
    offset=32+index*40;image[offset:offset+len(name)]=name.encode();image[offset+33]=3;struct.pack_into('<I',image,offset+34,1)
   struct.pack_into('<I',image,24,zlib.crc32(image));
   for slot in [0,1]:(journal/f'STATE{slot}.BIN').write_bytes(image)
 def run(action,fault='',code=0):
  global checks
  result=subprocess.run([str(exe),action,fault],env={**os.environ,'SD_TEST_ROOT':str(card)},capture_output=True,text=True);assert result.returncode==code,(action,fault,result.returncode,result.stdout,result.stderr);checks+=1;return result.stdout
 setup();before=snapshot(card);run('delete');assert not(card/'configs/victim').exists();assert not(card/'system/deleted').exists();assert (card/'configs/active.txt').read_bytes()==before['configs/active.txt'];assert (card/'control').read_text()=='preserve'
 setup();run('reuse');assert(card/'configs/victim/config.txt').exists()and(card/'configs/victim-2/config.txt').exists()
 for action in ['lease','web','runtime','factory']:
  setup();before=snapshot(card);run(action);assert snapshot(card)==before
 setup();run('protect');assert(card/'configs/victim/associated.bin').exists()
 for selection in ['config=victim\n','config=work\nonce=victim\n',None,'config=missing\n','config=../bad\n']:
  setup(selection);before=snapshot(card);run('delete',code=10);assert snapshot(card)==before
 for owner,file,text in [('work','vice.ini','[C64]\nKernalName="SD:/configs/victim/kernal"\n'),('work','config.txt','name=Work\nmachine=C64\ndisk_8=/configs/victim/test.d64\n')]:
  setup();(card/'configs'/owner/file).write_text(text);before=snapshot(card);run('delete',code=10);assert snapshot(card)==before
 for fault in ['child','metadata','folder']:
  setup();run('delete',fault,10);assert(card/'configs/victim').exists()
  if fault!='folder':assert(card/'configs/victim/config.txt').exists();run('delete');assert not(card/'configs/victim').exists()
 setup(legacy=True);before=snapshot(card);run('startup');run('legacy-blocked');assert snapshot(card)==before
 setup(legacy=True);run('legacy-reuse');assert(card/'configs/victim/config.txt').exists();assert(card/'configs/old-other/config.txt').exists()
 setup(legacy=True);run('cleanup');assert not(card/'configs/victim').exists();assert(card/'configs/old-other/config.txt').exists()
 for fault in ['open','write','sync','close']:
  setup(legacy=True);run('cleanup',fault,10);assert not(card/'configs/victim').exists();assert(card/'configs/old-other/config.txt').exists()
 setup(legacy=True);(card/'system/deleted/STATE0.BIN').write_bytes(b'bad');before=snapshot(card);run('startup');run('delete',code=10);assert snapshot(card)==before
 setup();run('pal');assert(card/'configs/pal-custom/config.txt').read_text().endswith('machine=C64/PAL/HDMI\n')
print(f'PASS: {checks} permanent/legacy deletion, protected selections/leases/assets, filesystem failures, ID reuse/duplicates, single Default and PAL compatibility checks; fixtures only')
