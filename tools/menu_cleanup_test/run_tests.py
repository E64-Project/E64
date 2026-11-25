#!/usr/bin/env python3
"""Production menu construction, GPL token preservation and ROM-picker policy."""
from pathlib import Path
import re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
def function(path,name):
 s=(ROOT/path).read_text();m=re.search(r'^[\w *]+\b'+name+r'\([^;]*?\)\s*\{',s,re.M)
 assert m,name
 return s[m.start():s.index('\n}',m.end())+2]
menu='third_party/common/menu.c';vice='third_party/vice-3.3/src/arch/raspi/vice_api.c'
funcs='\n'.join(function(menu,n) for n in ['menu_is_documentation','menu_is_rom_candidate','show_create_empty_disk_menu','show_about','show_license'])
funcs+='\n'+function(vice,'emux_drive_change_model')
funcs+='\n'+function('third_party/common/ui.c','ui_fit_message_dialog')
ids=sorted(set(re.findall(r'\b(?:MENU_|DRIVE_TYPE_)[A-Z0-9_]+',funcs))-{'MENU_ID_DO_NOTHING'})
code=r'''
#include <cassert>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <strings.h>
#include <string>
#include <deque>
#include <vector>
#include "ui.h"
#include "../../src/configs/configs.h"
#include "menu_theme.h"
#include "text.c"
enum {IDS};
static menu_item root;
static int current_menu=1,menu_window_top[NUM_MENU_ROOTS],menu_window_bottom[NUM_MENU_ROOTS];
static std::deque<menu_item> nodes;
menu_item *ui_push_menu(int w,int h){
 nodes.clear();memset(&root,0,sizeof(root));
 root.menu_width=(w<0?40:w)*8;root.menu_height=(h<0?25:h)*8;
 root.menu_left=16+(320-root.menu_width)/2;root.menu_top=24+(200-root.menu_height)/2;
 return &root;
}
static menu_item *add(menu_item *parent,const char *name,menu_item_type type,int id){
 nodes.emplace_back();auto *p=&nodes.back();memset(p,0,sizeof(*p));
 snprintf(p->name,sizeof(p->name),"%s",name);p->type=type;p->id=id;
 p->menu_left=parent->menu_left;p->menu_top=parent->menu_top;
 p->menu_width=parent->menu_width;p->menu_height=parent->menu_height;
 if(parent->first_child){auto *last=parent->first_child;while(last->next)last=last->next;last->next=p;}
 else parent->first_child=p;
 return p;
}
menu_item *ui_menu_add_button(int id,menu_item *parent,const char *name){
 auto *p=add(parent,name,BUTTON,id);strcpy(p->displayed_value," ");return p;
}
menu_item *ui_menu_add_read_only_heading(menu_item *parent,const char *name){return add(parent,name,READ_ONLY_HEADING,-1);}
menu_item *ui_menu_add_divider(menu_item *parent){return add(parent,"",DIVIDER,-1);}
static int selected_calls,render_calls,fit_calls;
menu_item *ui_push_selection_popup(int h){return ui_push_menu(-1,h);}
int ui_fit_selection_popup(menu_item*){fit_calls++;return 1;}
void ui_menu_mark_option(menu_item *p,int selected){strcpy(p->displayed_value,selected?"(*)":"( )");}
void ui_select_first_interactive_item(){selected_calls++;}
void ui_render_single_frame(){assert(selected_calls>render_calls);render_calls++;}
static int automatic,current_type;
static int resources_get_int_sprintf(const char *name,int *out,int unit){assert(unit==8);*out=strstr(name,"AutoType")?automatic:current_type;return 0;}
static int machine_drive_rom_check_loaded(int){return 0;}
static void ieeerom_load_2031(){} static void ieeerom_load_2040(){}
static void ieeerom_load_3040(){} static void ieeerom_load_4040(){} static void ieeerom_load_1001(){}
static int drive_check_type(int,int){return 1;}
FUNCTIONS
static std::string tokens(const std::string &s){std::string out;for(unsigned char c:s)if(!isspace(c))out+=c;return out;}
int main(){
 // Drive builder's actual automatic/manual metadata still chooses one row.
 for(int mode:{0,1}){
  automatic=mode;current_type=DRIVE_TYPE_1541II;emux_drive_change_model(8);
  assert(!strcmp(nodes[0].name,"Auto"));int count=0;
  for(auto &n:nodes){assert(!strstr(n.name,"Auto Detect"));if(strstr(n.displayed_value,"(*)")){
   count++;assert(mode?n.id==MENU_DRIVE_AUTO_TYPE:!strcmp(n.name,"1541II"));}}
  assert(count==1);
 }
 // Keep the established panel position; choose and render before returning.
 show_create_empty_disk_menu();assert(root.menu_height==160);
 assert(root.menu_top==24+(200-160)/2);
 assert(selected_calls==1 && render_calls==1 && fit_calls==2);
 assert(!strcmp(nodes[0].name,"Create Empty Disk") && nodes[1].type==DIVIDER);
 assert(!strcmp(nodes[2].name," Type   Drive Model") && nodes[3].type==DIVIDER);
 for(auto &n:nodes)assert(n.menu_top==root.menu_top);
 show_about();assert(root.menu_width==240 && root.menu_height==88 && nodes.size()==7);
 const char *about[]={"E64 - v1.0","","DERIVED FROM","BMC64, VICE, & CIRCLE","For The Pi 3B+","","License >"};
 for(int i=0;i<7;i++){assert(!strcmp(nodes[i].name,about[i]));assert(nodes[i].type==(i==1||i==5?DIVIDER:i==6?BUTTON:READ_ONLY_HEADING));assert(strlen(nodes[i].name)<36 && nodes[i].menu_top%8==0);}
 assert(nodes[6].id==MENU_LICENSE);
 // Wrapped name/alias messages have space for every line and the inset.
 ui_push_menu(30,4);for(int i=0;i<5;i++)ui_menu_add_read_only_heading(&root,"Message line");
 ui_fit_message_dialog(&root);assert(root.menu_height==6*8 && menu_window_bottom[1]==5);
 for(auto &n:nodes)assert(n.menu_height==root.menu_height && n.menu_top==root.menu_top);
 show_license();assert(!strcmp(root.name,"LICENSE"));
 assert(!strcmp(nodes[0].name,"GNU GENERAL PUBLIC LICENSE"));
 assert(!strcmp(nodes[1].name,"Version 2, June 1991"));assert(!nodes[2].name[0]);
 std::string original,rendered;for(int i=0;i<NUM_LICENSE_LINES;i++)original+=std::string(license[i])+" ";
 bool address=false,postal=false;for(auto &n:nodes){
  assert(strlen(n.name)<=MAX_MENU_STR-1);rendered+=std::string(n.name)+" ";
  if(strstr(n.name,"59 Temple Place"))address=true;
  if(strstr(n.name,"02111-1307"))postal=true;
 }
 assert(tokens(original)==tokens(rendered) && address && postal);
 assert(nodes.size()>300); // All license sections remain, not only the opening.
 const char *valid[]={"basic","chargen","kernal","kernal-Green-on-Black","JD-kernal","JD-d1541II","dosCMDHD","eprom.bin","replacement.rom","custom.kernel.bin"};
 for(auto name:valid)assert(menu_is_rom_candidate(name));
 const char *hidden[]={"rpi_pos.vkm","USER.VKM","RASPI.vpl","README.txt","readme-drives.txt","ROM-Notes.txt","bootstat.txt","vice.ini","config.txt","LICENSE","PUT_ROMS_HERE","game.d64","game.prg",".hidden","old.rom.bak"};
 for(auto name:hidden)assert(!menu_is_rom_candidate(name));
}
'''.replace('IDS',','.join(ids)).replace('FUNCTIONS',funcs)
with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='menu-cleanup-test-') as tmp:
 tmp=Path(tmp);source=tmp/'test.cpp';source.write_text(code);exe=tmp/'test'
 subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror','-I'+str(ROOT/'third_party/common'),str(source),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
# Generated Web constants must agree with the single native source of truth.
header=(ROOT/'src/configs/configs.h').read_text();js=(ROOT/'src/webui/assets/js/config_limits.js').read_text()
assert int(re.search(r'CONFIGS_MAX_NAME_LEN (\d+)',header)[1])==int(re.search(r'MAX_CONFIG_NAME = (\d+)',js)[1])
assert 'Default Configuration' not in js
assert 'name: MAIN_CONFIG_NAME' not in (ROOT/'src/webui/assets/js/configs.js').read_text()
assert '[[MAIN_ID, MAIN_CONFIG_NAME]' not in (ROOT/'src/webui/assets/js/configs.js').read_text()
ui=(ROOT/'third_party/common/ui.c').read_text();start=ui.index('} else if (is_file_selection) {');end=ui.index('} else if (menu_stack_index',start)
assert 'E64_MENU_FRAME_PADDING, 0)' in ui[start:end]
assert 'dir_type == DIR_ROMS && !menu_is_rom_candidate' in (ROOT/menu).read_text()
print('PASS: actual drive Auto/selection metadata; disk/About construction; GPL opening, address, all original non-whitespace characters; ROM support filtering; rounded picker routing and shared native/Web Config limits.')
