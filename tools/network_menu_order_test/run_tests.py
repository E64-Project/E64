#!/usr/bin/env python3
"""Execute the Network menu prefix and existing save/reboot dispatch, mocked."""
from pathlib import Path
import subprocess,tempfile
r=Path(__file__).resolve().parents[2];s=(r/'third_party/common/menu.c').read_text()
a=s.index('  parent = ui_menu_add_folder(machine_parent, "Network");');b=s.index('  child = network_device_item =',a);prefix=s[a:b]
assert s.count('ui_menu_add_button(MENU_NET_SAVE, network_folder,')==1
opened=s[s.index('  case MENU_NETWORKING:'):s.index('  case MENU_NET_IP_MODE:',s.index('  case MENU_NETWORKING:'))]
saved=s[s.index('  case MENU_NET_SAVE:'):s.index('  case MENU_NETWORK_ENABLED:',s.index('  case MENU_NET_SAVE:'))]
code=r'''
#include <assert.h>
#include <string.h>
enum {MENU_NETWORKING=1,MENU_NET_SAVE=2,FOLDER=3,BUTTON=4,DIVIDER=5,HEADING=6};
struct menu_item {int id,type;const char *name;struct menu_item *first_child,*next;};
static struct menu_item nodes[8],*network_status_item;
static int count,events[8],event_count,network_result,global_result,errors;
static struct menu_item*add(struct menu_item*p,int id,int type,const char*name){struct menu_item*n=&nodes[count++];n->id=id;n->type=type;n->name=name;if(p){struct menu_item**link=&p->first_child;while(*link)link=&(*link)->next;*link=n;}return n;}
static struct menu_item*ui_menu_add_folder(struct menu_item*p,const char*n){return add(p,-1,FOLDER,n);}
static struct menu_item*ui_menu_add_button(int id,struct menu_item*p,const char*n){return add(p,id,BUTTON,n);}
static void ui_menu_add_divider(struct menu_item*p){add(p,-1,DIVIDER,"");}
static struct menu_item*ui_menu_add_read_only_heading(struct menu_item*p,const char*n){return add(p,-1,HEADING,n);}
static int save_network_menu(void){events[event_count++]=1;return network_result;}
static int save_global_network_prefs(void){events[event_count++]=2;return global_result;}
static void menu_configs_before_reboot(void){events[event_count++]=3;}
static void fan_prepare_shutdown(void){}
static void reboot(void){events[event_count++]=4;}
static void ui_error(const char*s){assert(!strcmp(s,"Cannot save global network settings"));errors++;}
static void menu_update_network_status(void){events[event_count++]=5;}
static void load_network_menu(void){events[event_count++]=6;}
static void chosen(int id){switch(id){
'''+opened+saved+r'''
}}
int main(void){
 struct menu_item system={0},*machine_parent=&system,*parent=0;
'''+prefix+r'''
 assert(network_folder==system.first_child&&network_folder->id==MENU_NETWORKING);
 struct menu_item*save=network_folder->first_child;
 assert(save->id==MENU_NET_SAVE&&!strcmp(save->name,"Save Network Settings & Reboot"));
 assert(save->next->type==DIVIDER&&save->next->next==network_status_item&&network_status_item->next==0);
 assert(!event_count);chosen(MENU_NETWORKING);assert(event_count==2&&events[0]==5&&events[1]==6);
 for(int failure=0;failure<3;failure++){
  event_count=errors=0;network_result=failure==1?-1:0;global_result=failure==2?-1:0;
  chosen(MENU_NET_SAVE);
  assert(event_count==(failure==0?4:failure==1?1:2));
  for(int i=0;i<event_count;i++)assert(events[i]==i+1);
  assert(errors==(failure==2));
 }
}
'''
with tempfile.TemporaryDirectory(prefix='e64-network-menu-') as d:
 p=Path(d)/'test.c';exe=Path(d)/'test';p.write_text(code)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('PASS: one unchanged Network save/reboot action first, one following divider; opening only refreshes settings/status; original successful-save/reboot sequence and both failure paths')
