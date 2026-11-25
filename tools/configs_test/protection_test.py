#!/usr/bin/env python3
"""Actual independent protection/policy/config code, on disposable POSIX cards."""
from pathlib import Path
import os,subprocess,tempfile,shutil,re
root=Path(__file__).resolve().parents[2]
menu=(root/'third_party/common/menu_configs.c').read_text()
menu_core=(root/'third_party/common/menu.c').read_text()
def function(name):
 m=re.search(r'^static void '+name+r'\([^;]*?\{',menu,re.M);return menu[m.start():menu.index('\n}',m.end())+2]
C=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "configs_internal.h"
#include "sd_fs.h"
static const char *fault="";
static sd_file*writing;
int __real_sd_write(sd_file*,const void*,unsigned);
int __wrap_sd_write(sd_file*f,const void*p,unsigned n){if(f==writing&&!strcmp(fault,"write")){__real_sd_write(f,p,n/2);return SD_ERROR;}return __real_sd_write(f,p,n);}
sd_file *__real_sd_open(const char*,int);
sd_file *__wrap_sd_open(const char*p,int m){if(m!=SD_READ&&strstr(p,"system/protect/")&&!strcmp(fault,"open"))return NULL;sd_file*f=__real_sd_open(p,m);if(m!=SD_READ&&strstr(p,"system/protect/"))writing=f;return f;}
int __real_sd_sync(sd_file*);
int __wrap_sd_sync(sd_file*f){int rc=__real_sd_sync(f);return f==writing&&!strcmp(fault,"sync")?SD_ERROR:rc;}
int __real_sd_close(sd_file*);
int __wrap_sd_close(sd_file*f){int bad=f==writing&&writing;int rc=__real_sd_close(f);if(bad)writing=NULL;return bad&&!strcmp(fault,"close")?SD_ERROR:rc;}
#define MENU_CONFIGS_UNPROTECT_CONFIRM 1
#define MENU_CONFIRM_CANCEL 2
struct menu_item {char name[128],str_value[256];void(*on_value_changed)(struct menu_item*);};
static struct menu_item items[4],*protection_item;
static int item_count;
static struct menu_item *push_menu(int w,int h,const char*t){(void)w;(void)h;(void)t;item_count=0;return NULL;}
static struct menu_item *ui_menu_add_button(int id,struct menu_item*r,const char*t){(void)id;(void)r;struct menu_item*p=&items[item_count++];memset(p,0,sizeof(*p));snprintf(p->name,sizeof(p->name),"%s",t);return p;}
static void ui_error(const char*f,...){(void)f;}
static void ui_info(const char*f,...){(void)f;}
static void ui_pop_menu(void){}
static void ready(void){}
MENU_FUNCTIONS
static int saves;
static int save_settings_to(const char*settings,const char*vice){
 saves++;
 assert(vice);
 return sd_write_file(settings,"port_1=2\n",9)||
        sd_write_file(vice,"[C64]\n",6);
}
SAVE_FUNCTIONS
int main(int argc,char**argv){assert(argc>=2);configs_protection_init("SD");configs_boot_init("C64/PAL/HDMI");const char*cmd=argv[1];fault=argc>2?argv[2]:"";
 if(!strcmp(cmd,"on")){int rc=configs_set_protected("geos",1,0);if(rc)return 10;}
 else if(!strcmp(cmd,"off")){int rc=configs_set_protected("geos",0,1);if(rc)return 10;}
 else if(!strcmp(cmd,"unconfirmed")){assert(configs_set_protected("geos",0,0)<0);}
 else if(!strcmp(cmd,"delete")){if(configs_delete("geos")<0)return 10;}
 else if(!strcmp(cmd,"main")){
  assert(configs_is_protected("main"));assert(configs_set_protected("main",0,1)<0);assert(configs_set_protected("main",1,0)<0);
  assert(configs_delete("main")<0);assert(configs_rename_running("Oops")<0);
  ConfigFile pf;memset(&pf,0,sizeof(pf));assert(config_file_write("main",&pf)<0);
  assert(configs_set_autostart("SD:/x.prg")<0);
  const char*paths[]={"/vice.ini","/settings.txt","/configs/main/c64.txt"};
  for(unsigned i=0;i<3;i++){
   for(int mode=SD_WRITE;mode<=SD_UPDATE;mode++)assert(sd_open(paths[i],mode)==NULL);
   assert(sd_unlink(paths[i])==SD_DENIED);assert(sd_rename(paths[i],"/elsewhere")==SD_DENIED);assert(sd_rename("/elsewhere",paths[i])==SD_DENIED);
  }
  unsigned removed=0;assert(sd_remove_tree("/configs",&removed,NULL,NULL)==SD_DENIED);assert(sd_remove_tree("/",&removed,NULL,NULL)==SD_DENIED);
  assert(!configs_protection_can_write("0:/CONFIGS/main./c64.txt"));assert(!configs_protection_can_write("SD:/x/../vice.ini."));
  assert(!configs_protection_can_write("/SETTIN~1.TXT"));
  assert(!configs_protection_can_write("/SETTI~10.TXT"));assert(!configs_protection_can_write("/SET~ABCD.TXT"));assert(configs_protection_can_write("USB:/vice.ini"));
  assert(!configs_protection_external_allowed("SD:/system/protect./STATE0.BIN",0));assert(!configs_protection_external_allowed("/system/protect.id",1));
  change_protection();assert(item_count==0);
  assert(save_settings()==1&&saves==0);
  assert(!configs_protection_external_allowed("/settings.txt",1));
  assert(!configs_protection_external_allowed("/vice.ini",1));
  assert(!configs_protection_external_allowed("/E64SET.NEW",1));
  assert(!configs_protection_external_allowed("/E64SET.OLD",1));
  assert(menu_save_settings_to_config("main")==1&&saves==0);
 }
 else if(!strcmp(cmd,"clone-main")){
  char id[33];assert(configs_running_is_factory());assert(configs_create("Main Copy",id,sizeof(id))==0);
  assert(!configs_is_protected(id));assert(menu_save_settings_to_config(id)==0&&saves==1);return 0;
 }
 else if(!strcmp(cmd,"menu-off")||!strcmp(cmd,"menu-cancel")){
  assert(configs_switch_to("geos")==0);configs_boot_init("C64/PAL/HDMI");assert(configs_is_protected("geos"));
  change_protection();assert(item_count==2);assert(strstr(items[0].name,"Confirm"));assert(!strcmp(items[1].name,"Cancel"));
  assert(configs_is_protected("geos")); // Opening/canceling the dialog changes nothing.
  if(!strcmp(cmd,"menu-cancel"))return 0;
  items[0].on_value_changed(&items[0]);assert(!configs_is_protected("geos"));return 0;
 }
 else if(!strcmp(cmd,"switch")){
  assert(configs_switch_to("geos")==0);configs_boot_init("C64/PAL/HDMI");assert(configs_is_protected("geos"));
  assert(configs_switch_to("work")==0);configs_boot_init("C64/PAL/HDMI");assert(!configs_is_protected("work"));assert(configs_is_protected("geos"));
  assert(configs_start_once("geos")==0);configs_boot_init("C64/PAL/HDMI");assert(configs_is_protected("geos"));
  assert(configs_rename_running("Protected Name")==0);
  char id[33];assert(configs_create("New",id,sizeof(id))==0);assert(!configs_is_protected(id));
  assert(sd_write_file("/configs/geos/settings-c64.txt","volume=45\n",10)==0);return 0;
 }
 else if(strcmp(cmd,"status"))return 99;
 printf("%d %d %d\n",configs_protection_ready(),configs_is_protected("main"),configs_is_protected("geos"));return 0;
}
'''
C=C.replace('MENU_FUNCTIONS','\n'.join(function(n) for n in ['protection_label','unprotect_confirmed','change_protection']))
def core_function(name):
 m=re.search(r'^(?:static )?int '+name+r'\([^;]*?\{',menu_core,re.M);return menu_core[m.start():menu_core.index('\n}',m.end())+2]
C=C.replace('SAVE_FUNCTIONS',core_function('save_user_settings_to')+'\n'+core_function('save_settings')+'\n'+core_function('menu_save_settings_to_config'))
def tree(p):return {str(f.relative_to(p)):None if f.is_dir() else f.read_bytes() for f in p.rglob('*')}
with tempfile.TemporaryDirectory(prefix='e64-protection-') as tmp:
 tmp=Path(tmp);src=tmp/'test.c';src.write_text(C);exe=tmp/'test'
 cmd=['cc','-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-I'+str(root/'src/configs'),'-I'+str(root/'src/sdcard'),str(src),str(root/'tools/sdcard/sd_fs_posix.c'),str(root/'src/sdcard/sd_fs_file.c')]+[str(p) for p in (root/'src/configs').glob('*.c')]+['-Wl,--wrap='+n for n in ['sd_write','sd_open','sd_close','sd_sync']]+['-o',str(exe)]
 subprocess.run(cmd,check=True);card=tmp/'card';checks=0
 def setup():
  if card.exists():shutil.rmtree(card)
  for id in ['main','geos','work']:(card/'configs'/id).mkdir(parents=True)
  for id in ['geos','work']:(card/'configs'/id/'config.txt').write_text('name='+id+'\nmachine=C64\n')
  (card/'configs/active.txt').write_text('config=_factory-ntsc\n')
  (card/'configs/main/c64.txt').write_text('autostart=SD:/safe.prg\n')
  (card/'vice.ini').write_text('[C64]\nKernalName="jiffy"\n')
  (card/'settings.txt').write_text('port_1=2\n')
 def run(action,fault='',rc=0,unchanged=True):
  global checks
  before=tree(card/'configs');main=(card/'vice.ini').read_bytes(),(card/'settings.txt').read_bytes()
  result=subprocess.run([str(exe),action,fault],capture_output=True,text=True,env={**os.environ,'SD_TEST_ROOT':str(card)})
  assert result.returncode==rc,(action,fault,result.returncode,result.stdout,result.stderr)
  if unchanged:assert tree(card/'configs')==before,action
  assert main==((card/'vice.ini').read_bytes(),(card/'settings.txt').read_bytes())
  checks+=1;return result.stdout.strip()
 setup();assert run('status')=='1 1 0';run('main');assert not (card/'system/protect').exists()
 run('clone-main',unchanged=False)
 assert run('on')=='1 1 1';run('delete',rc=10);assert not (card/'system/deleted').exists();data=tree(card/'system/protect');run('unconfirmed');assert tree(card/'system/protect')==data
 assert run('status')=='1 1 1';before=tree(card/'system/protect');run('menu-cancel',unchanged=False);assert tree(card/'system/protect')==before
 run('menu-off',unchanged=False);assert run('status')=='1 1 0';run('on');run('switch',unchanged=False);assert run('status')=='1 1 1'
 assert run('off')=='1 1 0';(card/'configs/active.txt').write_text('config=_factory-ntsc\n');run('delete',unchanged=False);assert not (card/'configs/geos').exists() # Explicit permanent deletion after unprotect.
 for fault in ['open','write','sync','close']:
  setup();run('on',fault,rc=10);assert run('status')=='0 1 1';run('delete',rc=10)
 for corrupt in ['slot','missing','anchor','directory']:
  setup();run('on')
  if corrupt=='slot':
   p=card/'system/protect/STATE0.BIN';b=bytearray(p.read_bytes());b[100]^=1;p.write_bytes(b)
  elif corrupt=='missing':(card/'system/protect/STATE1.BIN').unlink()
  elif corrupt=='anchor':(card/'system/protect.id').unlink()
  else:shutil.rmtree(card/'system/protect')
  assert run('status')=='0 1 1';run('delete',rc=10);run('off',rc=10)
 print(f'PASS: {checks} independent protection/confirmation/persistence/deletion/policy/fault checks; retired files protected and user Config integrity retained.')
