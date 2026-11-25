#!/usr/bin/env python3
"""Fault and process-loss matrix against the production Config transaction.
All cards live under TemporaryDirectory; no media or workspace SD templates.
"""
from pathlib import Path
import os, re, subprocess, tempfile
root = Path(__file__).resolve().parents[2]
menu = (root/'third_party/common/menu.c').read_text()
m = re.search(r'^static int save_user_settings_to\([^;]*?\{', menu, re.M)
helper = menu[m.start():menu.index('\n}', m.end())+2]
C = r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "configs_internal.h"
#include "sd_fs.h"
static int enabled, event, target, corrupt_next_read;
static const char *mode;
static int before(void) {
 if (!enabled) return 0;
 event++;
 if(event!=target)return 0;
 if(!strcmp(mode,"before"))_exit(77);
 return !strcmp(mode,"fail") || !strcmp(mode,"short");
}
static void after(void) {if(enabled&&event==target&&!strcmp(mode,"after"))_exit(77);}
sd_file *__real_sd_open(const char*,int);
sd_file *__wrap_sd_open(const char*p,int m){if(enabled&&!strcmp(mode,"readonly")&&m!=SD_READ)return NULL;if(before())return NULL;sd_file*f=__real_sd_open(p,m);after();return f;}
int __real_sd_read(sd_file*,void*,unsigned,unsigned*);
int __wrap_sd_read(sd_file*f,void*p,unsigned n,unsigned*got){if(before()){*got=0;return SD_ERROR;}int r=__real_sd_read(f,p,n,got);if(corrupt_next_read&&*got){((char*)p)[0]^=1;corrupt_next_read=0;}after();return r;}
int __real_sd_write(sd_file*,const void*,unsigned);
int __wrap_sd_write(sd_file*f,const void*p,unsigned n){if(enabled&&!strcmp(mode,"readonly"))return SD_DENIED;if(before()){__real_sd_write(f,p,n/2);return SD_ERROR;}int r=__real_sd_write(f,p,n);after();return r;}
int __real_sd_sync(sd_file*);
int __wrap_sd_sync(sd_file*f){int bad=before();int r=__real_sd_sync(f);after();return bad?SD_ERROR:r;}
int __real_sd_close(sd_file*);
int __wrap_sd_close(sd_file*f){int bad=before();int r=__real_sd_close(f);after();return bad?SD_ERROR:r;}
int __real_sd_stat_info(const char*,sd_info*);
int __wrap_sd_stat_info(const char*p,sd_info*i){if(before())return SD_ERROR;int r=__real_sd_stat_info(p,i);after();return r;}
int __real_sd_rename(const char*,const char*);
int __wrap_sd_rename(const char*a,const char*b){if(enabled&&!strcmp(mode,"readonly"))return SD_DENIED;if(before())return SD_ERROR;int r=__real_sd_rename(a,b);if(r==SD_OK&&enabled&&!strcmp(mode,"corrupt")&&strstr(a,".e64-new"))corrupt_next_read=1;after();return r;}
int __real_sd_list_info(const char*,sd_info_cb,void*);
int __wrap_sd_list_info(const char*p,sd_info_cb cb,void*c){if(before())return SD_ERROR;int r=__real_sd_list_info(p,cb,c);after();return r;}
int __real_sd_unlink(const char*);
int __wrap_sd_unlink(const char*p){if(enabled&&!strcmp(mode,"readonly"))return SD_DENIED;if(before())return SD_ERROR;int r=__real_sd_unlink(p);after();return r;}
/* Checked writer stand-in: stdio's own write/flush/close propagation is
 * independently injected in fs_stage1_test. This exercises the exact native
 * caller with production staging, copying, commit, recovery and leases. */
static int save_settings_to(const char*n,const char*v){
 char b[128];int rc=sd_read_file(v,b,sizeof(b));
 if(rc>=0)assert(!strcmp(b,"[OTHER]\nkeep=unchanged\n[C64]\nold=1\n"));
 else if(sd_stat(v,NULL,NULL)!=SD_NOT_FOUND)return 1;
 sd_file*f=sd_open(v,SD_WRITE);if(!f)return 1;
 const char*vice="[OTHER]\nkeep=unchanged\n[C64]\nnew=2\n";
 int ok=sd_write(f,vice,strlen(vice))==SD_OK;
 if(sd_sync(f)!=SD_OK)ok=0;if(sd_close(f)!=SD_OK)ok=0;if(!ok)return 1;
 f=sd_open(n,SD_WRITE);if(!f)return 1;
 ok=sd_write(f,"native=new\n",11)==SD_OK;
 if(sd_sync(f)!=SD_OK)ok=0;if(sd_close(f)!=SD_OK)ok=0;
 return !ok;
}
HELPER
int main(int argc,char**argv){
 assert(argc==5);if(strcmp(argv[1],"recover"))configs_boot_init("C64/PAL/HDMI");
 mode=argv[2];target=atoi(argv[3]);const char*kind=argv[4];
 const char*path=!strcmp(kind,"legacy")?"/configs/geos/settings.txt":"/configs/geos/settings-c64.txt";
 if(!strcmp(argv[1],"lease")){
  assert(configs_storage_begin("main")==CONFIGS_ERROR);
  assert(configs_storage_begin(CONFIGS_FACTORY_NTSC)==CONFIGS_ERROR);
  assert(configs_storage_begin(CONFIGS_FACTORY_PAL)==CONFIGS_ERROR);
  assert(configs_storage_begin("geos")==CONFIGS_OK);
  assert(configs_storage_begin("geos")==CONFIGS_ERROR);
  assert(configs_storage_recover("geos")==CONFIGS_ERROR);
  assert(configs_delete("geos")==CONFIGS_ERROR);
  configs_storage_end();
  assert(configs_storage_recover("geos")==CONFIGS_OK);
  return 0;
 }
 if(!strcmp(argv[1],"boot-main")){
  assert(configs_running_is_factory());return 0;
 }
 if(!strcmp(argv[1],"boot")){
  assert(!strcmp(configs_running()->id,"geos"));return 0;
 }
 if(!strcmp(argv[1],"save")){
  enabled=1;int rc;
  if(!strcmp(kind,"web")){
   rc=configs_storage_begin("geos");
   if(rc==CONFIGS_OK){
    char next[CONFIGS_MAX_PATH_LEN];
    rc=configs_storage_prepare("/configs/geos/config.txt",next,sizeof(next),0);
    if(rc==CONFIGS_OK)rc=sd_write_file(next,"name=New Name\nmachine=C64\n",26);
    if(rc==CONFIGS_OK)rc=configs_storage_commit_backup("/configs/geos/config.txt");
    configs_storage_end();
   }
  }else if(!strcmp(kind,"metadata")){
   ConfigFile pf;memset(&pf,0,sizeof(pf));strcpy(pf.info.name,"New Name");strcpy(pf.info.machine,"C64");
   rc=config_file_write("geos",&pf);
  }else rc=save_user_settings_to("geos",path,"/configs/geos/vice.ini");
  enabled=0;printf("%d %d\n",event,rc);return 0;
 }
 if(!strcmp(argv[1],"recover")){
  enabled=1;int rc=configs_storage_recover("geos");enabled=0;
  printf("%d %d\n",event,rc);return 0;
 }
 return 1;
}
'''.replace('HELPER', helper)
wrap = ['sd_open','sd_read','sd_write','sd_sync','sd_close','sd_stat_info','sd_rename','sd_unlink','sd_list_info']
checks = 0
with tempfile.TemporaryDirectory(prefix='e64-storage-fault-') as tmp:
    tmp = Path(tmp); src = tmp/'test.c'; src.write_text(C); exe = tmp/'test'
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=undefined',
                    '-I'+str(root/'src/configs'),'-I'+str(root/'src/sdcard'),str(src),
                    str(root/'tools/sdcard/sd_fs_posix.c'),str(root/'src/sdcard/sd_fs_file.c')]+
                   [str(p) for p in (root/'src/configs').glob('*.c')]+
                   ['-Wl,--wrap='+n for n in wrap]+['-o',str(exe)],check=True)
    card = tmp/'card'; folder=card/'configs/geos';folder.mkdir(parents=True)
    env=dict(os.environ,SD_TEST_ROOT=str(card))
    old_meta=b'name=Original Name\nmachine=C64\ncustom=retain-on-read\n'
    old_vice=b'[OTHER]\nkeep=unchanged\n[C64]\nold=1\n'
    new_vice=b'[OTHER]\nkeep=unchanged\n[C64]\nnew=2\n'
    def setup(kind, existing=True):
        for p in folder.iterdir(): p.unlink()
        if existing or kind not in ('metadata','web'): (folder/'config.txt').write_bytes(old_meta)
        if existing:
            (folder/('settings.txt' if kind=='legacy' else 'settings-c64.txt')).write_bytes(b'native=old\n')
            (folder/'vice.ini').write_bytes(old_vice)
    def run(action,mode='none',event=0,kind='metadata'):
        r=subprocess.run([str(exe),action,mode,str(event),kind],env=env,capture_output=True,text=True)
        assert r.returncode in (0,77),(r.returncode,r.stdout,r.stderr,action,mode,event,kind)
        return r
    def verify(kind,existing=True):
        global checks
        r=run('recover',kind=kind);assert r.stdout.split()[-1]=='0',r.stdout
        meta=(folder/'config.txt').read_bytes() if (folder/'config.txt').exists() else None
        if kind in ('metadata','web'): assert meta in ((old_meta,b'name=New Name\nmachine=C64\n') if existing else (None,b'name=New Name\nmachine=C64\n')),meta
        else:
            assert meta==old_meta
            native=folder/('settings.txt' if kind=='legacy' else 'settings-c64.txt')
            assert (not native.exists() and not existing) or native.read_bytes() in (b'native=old\n',b'native=new\n')
            vice=folder/'vice.ini'
            assert (not vice.exists() and not existing) or vice.read_bytes() in (old_vice,new_vice)
        assert not any('.e64-' in p.name for p in folder.iterdir())
        before={p.name:p.read_bytes() for p in folder.iterdir()}
        run('recover',kind=kind)
        assert before=={p.name:p.read_bytes() for p in folder.iterdir()}
        checks+=1
    for kind in ('metadata','native','legacy','web'):
        for existing in (True,False):
            setup(kind,existing)
            total=int(run('save',kind=kind).stdout.split()[0])
            for mode in ('fail','before','after'):
                for event in range(1,total+1):
                    setup(kind,existing)
                    r=run('save',mode,event,kind)
                    if mode!='fail': assert r.returncode==77,(mode,event,total)
                    verify(kind,existing)
            print(f'PASS: {kind}, existing={existing}: {total} operation boundaries, errors and power loss before/after')
    for kind in ('metadata','native','legacy','web'):
        setup(kind)
        r=run('save','corrupt',kind=kind)
        assert r.stdout.split()[-1]!='0'
        verify(kind)
        assert (folder/'config.txt').read_bytes()==old_meta
        if kind not in ('metadata','web'): assert (folder/'vice.ini').read_bytes()==old_vice
    # Complete namespace-state matrix: unfinished NEW must never be promoted,
    # OLD wins even over a corrupt final, and recovery can itself be repeated.
    for final in (False,True):
        for old in (False,True):
            for pending in (False,True):
                setup('metadata',False)
                if final: (folder/'config.txt').write_bytes(old_meta if not old else b'corrupt final')
                if old: (folder/'config.txt.e64-old').write_bytes(old_meta)
                if pending: (folder/'config.txt.e64-new').write_bytes(b'incomplete')
                verify('metadata',final or old)
    setup('legacy');run('lease',kind='legacy');checks+=1
    # Verify the production boot path resolves sidecars before reading metadata
    # and deciding whether settings.txt or settings-c64.txt should be loaded.
    setup('legacy')
    (folder/'config.txt.e64-old').write_bytes(old_meta)
    (folder/'config.txt').write_bytes(b'corrupt final')
    (folder/'settings.txt.e64-old').write_bytes(b'native=old\n')
    (folder/'settings.txt').unlink()
    (card/'configs/active.txt').write_text('config=geos\n')
    run('boot',kind='legacy');verify('legacy')
    (card/'configs/active.txt').unlink()
    setup('legacy')
    (folder/'config.txt.e64-old').write_bytes(old_meta)
    (folder/'config.txt').unlink()
    (folder/'settings-custom.txt.e64-old').write_bytes(b'custom=old\n')
    (folder/'settings-custom.txt.e64-new').write_bytes(b'partial')
    run('boot-main',kind='legacy');verify('legacy')
    assert (folder/'settings-custom.txt').read_bytes()==b'custom=old\n'

    # Repeat faults and power loss during recovery itself, with both OLD and
    # a replacement present (the rollback unlink/rename gap is included).
    for mode in ('fail','before','after'):
        setup('native');(folder/'settings-c64.txt.e64-old').write_bytes(b'native=old\n')
        (folder/'settings-c64.txt').write_bytes(b'native=new\n')
        total=int(run('recover',kind='native').stdout.split()[0])
        for event in range(1,total+1):
            setup('native');(folder/'settings-c64.txt.e64-old').write_bytes(b'native=old\n')
            (folder/'settings-c64.txt').write_bytes(b'native=new\n')
            run('recover',mode,event,'native');verify('native')
            assert (folder/'settings-c64.txt').read_bytes()==b'native=old\n'
    setup('legacy')
    snapshot={p.name:p.read_bytes() for p in folder.iterdir()}
    assert run('recover','readonly',kind='legacy').stdout.split()[-1]=='0'
    assert snapshot=={p.name:p.read_bytes() for p in folder.iterdir()};checks+=1
    setup('native')
    (folder/'vice.ini.e64-ne~').write_bytes(old_vice)
    verify('native')
    # Existing legacy payloads are byte-for-byte unchanged by recovery.
    setup('legacy');verify('legacy')
    print(f'PASS: {checks} production transaction/restart/recovery scenarios; idempotent recovery and legacy bytes preserved')
