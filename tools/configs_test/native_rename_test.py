#!/usr/bin/env python3
"""Production native rename/list lifecycle + real Config I/O on temporary cards."""
from pathlib import Path
import subprocess,tempfile,os,re,struct,zlib
r=Path(__file__).resolve().parents[2];source=(r/'third_party/common/menu_configs.c').read_text()
def fn(name):
 m=re.search(r'^static [\w *]+\b'+name+r'\([^;]*?\)\s*\{',source,re.M);assert m,name
 return source[m.start():source.index('\n}',m.end())+2]
code=r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <strings.h>
#include <cstdarg>
#include <deque>
#include <vector>
#include <string>
#include <dirent.h>
#include "ui.h"
#include "menu_theme.h"
extern "C" {
#include "configs_internal.h"
#include "sd_fs.h"
}
enum {MENU_CONFIRM_CANCEL=100,MENU_CONFIGS_RENAME_NAME,MENU_CONFIGS_NEW_NAME,MENU_TEXT,MENU_CONFIGS_SELECT_ITEM,MENU_CONFIGS_DELETE_ITEM};
struct Page{menu_item root{};std::deque<menu_item> nodes;};
static std::vector<Page*> pages;
static std::string last_error,last_info;
static menu_item *selected,*status_item,*save_item;
static char rename_config_id[CONFIGS_MAX_ID_LEN+1];
static unsigned long new_config_timing;
static int fail_list,fail_malloc;
extern "C" int __real_sd_list_info(const char*,sd_info_cb,void*);
extern "C" int __wrap_sd_list_info(const char *p,sd_info_cb cb,void *ctx){if(fail_list&&!strcmp(p,CONFIGS_DIR))return SD_DENIED;return __real_sd_list_info(p,cb,ctx);}
extern "C" void *__real_malloc(size_t);
extern "C" void *__wrap_malloc(size_t n){if(fail_malloc){fail_malloc=0;return nullptr;}return __real_malloc(n);}
static int handles(){DIR*d=opendir("/proc/self/fd");assert(d);int n=0;while(readdir(d))n++;closedir(d);return n;}
menu_item *ui_push_menu(int w,int h){auto*p=new Page;pages.push_back(p);p->root.menu_width=w*8;p->root.menu_height=h*8;return &p->root;}
static menu_item *node(menu_item *root,const char*text,int type,int id){auto*p=pages.back();p->nodes.emplace_back();auto *item=&p->nodes.back();memset(item,0,sizeof(*item));item->type=(menu_item_type)type;item->id=id;snprintf(item->name,sizeof(item->name),"%s",text);if(!root->first_child)root->first_child=item;else{auto*last=root->first_child;while(last->next)last=last->next;last->next=item;}return item;}
menu_item *ui_menu_add_button(int id,menu_item *p,const char *s){return node(p,s,BUTTON,id);}
menu_item *ui_menu_add_read_only_heading(menu_item*p,const char*s){auto*item=node(p,s,READ_ONLY_HEADING,-1);item->disabled=1;return item;}
menu_item *ui_menu_add_divider(menu_item*p){return node(p,"",DIVIDER,-1);}
menu_item *ui_menu_add_folder(menu_item*p,char*s){return node(p,s,FOLDER,-1);}
menu_item *ui_menu_add_text_field_limit(int id,menu_item*p,const char*s,char *value,int limit){auto*item=node(p,s,TEXTFIELD,id);snprintf(item->str_value,sizeof(item->str_value),"%s",value);item->max_length=limit;return item;}
void ui_select_first_interactive_item(){selected=nullptr;for(auto&i:pages.back()->nodes)if(!i.disabled&&i.type!=DIVIDER){selected=&i;break;}}
void ui_refresh_menu_window(){}
void ui_menu_mark_option(menu_item*p,int yes){snprintf(p->displayed_value,sizeof(p->displayed_value),"%s",yes?"(*)":"( )");}
menu_item *ui_pop_menu(){assert(pages.size()>1);auto*p=pages.back();pages.pop_back();if(p->root.on_popped_off)p->root.on_popped_off(&pages.back()->root,&p->root);delete p;selected=nullptr;return &pages.back()->root;}
void ui_error(const char*f,...){char b[512];va_list a;va_start(a,f);vsnprintf(b,sizeof(b),f,a);va_end(a);last_error=b;}
void ui_info(const char*f,...){char b[512];va_list a;va_start(a,f);vsnprintf(b,sizeof(b),f,a);va_end(a);last_info=b;}
static void create_config(const char*){assert(false);}
static void config_selected(menu_item*){assert(false);}
static void delete_selected(menu_item*){assert(false);}
@FUNCTIONS@
static menu_item *find(const char *id){for(auto&i:pages.back()->nodes)if(!strcmp(i.str_value,id)&&i.type==BUTTON)return &i;return nullptr;}
static std::string text(const char*path){char b[4096];int n=sd_read_file(path,b,sizeof(b));assert(n>=0);return {b,(size_t)n};}
static ConfigFile metadata(const char*id){ConfigFile pf;assert(config_file_read(id,&pf)==CONFIGS_OK);return pf;}
static void list(){last_error.clear();show_rename_list();assert(last_error.empty()&&pages.size()==2);assert(!find(CONFIGS_FACTORY_NTSC)&&!find(CONFIGS_FACTORY_PAL));}
static void choose(const char *id){auto*p=find(id);assert(p&&p->on_value_changed);p->on_value_changed(p);assert(pages.size()==2&&selected&&selected->type==TEXTFIELD);assert(configs_list_at(1)==nullptr);assert(!strcmp(rename_config_id,id));}
static void submit(const char *name){assert(selected&&selected->type==TEXTFIELD);snprintf(selected->str_value,sizeof(selected->str_value),"%s",name);selected->on_value_changed(selected);}
static void check_all(){list();for(auto id:{"alpha","beta","guard"})assert(find(id));ui_pop_menu();assert(configs_list_at(1)==nullptr);}
int main(int argc,char**argv){assert(argc==2);pages.push_back(new Page);configs_boot_init("C64/NTSC/HDMI");std::string action=argv[1];int fd=handles();
 if(action=="empty"){
  list();bool message=false,back=false;for(auto&i:pages.back()->nodes){message|=!strcmp(i.name,"No custom Configs to rename");back|=i.id==MENU_CONFIRM_CANCEL&&!strcmp(i.name,"Back");}assert(message&&back&&selected&&selected->id==MENU_CONFIRM_CANCEL);ui_pop_menu();
 }else if(action=="list"){
  for(int n=0;n<40;n++){
   check_all();show_select_list();assert(find(CONFIGS_FACTORY_NTSC));ui_pop_menu();show_delete_list();ui_pop_menu();assert(configs_list_at(1)==nullptr);
  }
  for(auto id:{"alpha","beta",CONFIGS_FACTORY_NTSC}){assert(configs_switch_to(id)==0);configs_boot_init("C64/NTSC/HDMI");check_all();}
  assert(configs_set_protected("guard",1,0)==0);check_all();assert(configs_is_protected("guard"));
 }else if(action=="cancel"){
  auto before=text("/configs/alpha/config.txt"),selection=text(CONFIGS_ACTIVE_FILE);
  list();choose("alpha");snprintf(selected->str_value,sizeof(selected->str_value),"Cancelled rename");ui_pop_menu();assert(text("/configs/alpha/config.txt")==before&&text(CONFIGS_ACTIVE_FILE)==selection);check_all();
 }else if(action=="success"){
  assert(configs_switch_to("alpha")==0);configs_boot_init("C64/NTSC/HDMI");assert(configs_switch_to("beta")==0);assert(configs_start_once("guard")==0);assert(configs_set_protected("guard",1,0)==0);
  auto selection=text(CONFIGS_ACTIVE_FILE);
  for(auto id:{"alpha","beta","guard"}){
   auto before=metadata(id);std::string name=std::string(id)+" Renamed";list();choose(id);assert(!strcmp(selected->str_value,before.info.name));submit(name.c_str());assert(pages.size()==1&&last_info=="Config renamed");auto after=metadata(id);assert(!strcmp(after.info.name,name.c_str()));memcpy(after.info.name,before.info.name,sizeof(after.info.name));assert(!memcmp(&before,&after,sizeof(before)));assert(text(CONFIGS_ACTIVE_FILE)==selection);
  }
  assert(!strcmp(configs_running()->id,"alpha")&&!strcmp(configs_running()->name,"alpha Renamed"));assert(configs_is_protected("guard"));
  assert(configs_rename(CONFIGS_FACTORY_NTSC,"Forbidden")<0&&configs_rename(CONFIGS_FACTORY_PAL,"Forbidden")<0&&configs_rename("main","Forbidden")<0&&configs_rename("../alpha","Forbidden")<0);
 }else if(action=="duplicate"){
  auto before=text("/configs/alpha/config.txt");list();choose("alpha");submit("  bEtA  ");assert(!last_error.empty()&&pages.size()==2&&text("/configs/alpha/config.txt")==before);last_error.clear();submit("Default");assert(!last_error.empty()&&text("/configs/alpha/config.txt")==before);last_error.clear();submit("Alpha Unique");assert(last_error.empty()&&pages.size()==1);
  // Independent duplicate scanning must not close/invalidate an open list.
  int count=configs_list_open();assert(count==4);const ConfigInfo *snapshot=configs_list_at(1);std::string id=snapshot->id;assert(configs_rename("alpha","Alpha Final")==0);assert(configs_list_at(1)==snapshot&&id==snapshot->id);configs_list_close();
 }else if(action=="legacy"){
  list();assert(!find("alpha")&&find("beta")&&find("guard"));ui_pop_menu();assert(configs_rename("alpha","Forbidden")<0);
 }else if(action=="errors"){
  fail_list=1;show_rename_list();assert(pages.size()==1&&!last_error.empty()&&configs_list_at(1)==nullptr);fail_list=0;check_all();
  fail_malloc=1;show_rename_list();assert(pages.size()==1&&!last_error.empty()&&configs_list_at(1)==nullptr);check_all();
  list();assert(sd_unlink("/configs/alpha/config.txt")==0);last_error.clear();auto*p=find("alpha");p->on_value_changed(p);assert(!last_error.empty()&&pages.size()==2&&selected->type!=TEXTFIELD);ui_pop_menu();
 }else assert(false);
 assert(pages.size()==1&&handles()==fd&&configs_list_at(1)==nullptr);delete pages.back();
}
'''
functions=['config_label','push_menu','ready','list_popped','config_popup_height','add_config_buttons','show_select_list','update_name_labels','name_entered','show_name_dialog','rename_chosen','show_rename_list','show_delete_list']
code=code.replace('@FUNCTIONS@','\n'.join(fn(n) for n in functions))
with tempfile.TemporaryDirectory(prefix='e64-native-rename-') as tmp:
 t=Path(tmp);src=t/'test.cpp';src.write_text(code);objects=[]
 flags=['-fsanitize=undefined','-g','-I'+str(r/'third_party/common'),'-I'+str(r/'src/configs'),'-I'+str(r/'src/sdcard')]
 sources=[r/'tools/sdcard/sd_fs_posix.c',r/'src/sdcard/sd_fs_file.c',*sorted((r/'src/configs').glob('*.c'))]
 for n,c in enumerate(sources):
  o=t/f'{n}.o';subprocess.run(['cc','-std=gnu11',*flags,'-c',str(c),'-o',str(o)],check=True);objects.append(str(o))
 exe=t/'test';subprocess.run(['g++','-std=c++17',*flags,str(src),*objects,'-Wl,--wrap=sd_list_info,--wrap=malloc','-o',str(exe)],check=True)
 for case in ['empty','missing','list','cancel','success','duplicate','legacy','errors']:
  card=t/case;card.mkdir()
  if case!='missing':
   (card/'configs').mkdir();(card/'configs/active.txt').write_text('config=_factory-ntsc\n')
  if case not in ['empty','missing']:
   for id,name,video in [('alpha','Alpha','NTSC'),('beta','Beta','PAL'),('guard','Guard','NTSC')]:
    p=card/'configs'/id;p.mkdir();(p/'config.txt').write_text(f'name={name}\nmachine=C64/{video}/HDMI\ncategory=Apps\ndescription=Preserve details\ndisk_8=/disks/test.d64\n')
   (card/'configs/orphan').mkdir()
  if case=='legacy':
   journal=card/'system/deleted';journal.mkdir(parents=True);(card/'system/deleted.id').write_bytes(b'E64-LOGICAL-V1'.ljust(16,b'\0'))
   image=bytearray(4096);image[:8]=b'E64DEL1\0';struct.pack_into('<III',image,8,1,1,1);image[32:37]=b'alpha';image[65]=3;struct.pack_into('<I',image,66,1);struct.pack_into('<I',image,24,zlib.crc32(image))
   for slot in [0,1]:(journal/f'STATE{slot}.BIN').write_bytes(image)
  env={**os.environ,'SD_TEST_ROOT':str(card)}
  run=subprocess.run([str(exe),'empty' if case=='missing' else case],env=env,capture_output=True,text=True)
  assert run.returncode==0,(case,run.returncode,run.stdout,run.stderr)
print('PASS: production native rename opens with multiple/empty/missing lists; factory filtering and existing protected/running/Power-on/Start Once rename policy; repeated Select/Delete/Rename/switch; cancel/commit/duplicate rejection; stale-entry, allocation and directory errors; ID/metadata/selection integrity; closed OS handles and list snapshots')
