#!/usr/bin/env python3
"""Execute the production root sorter and shared ROM menu shortcut on host."""
from pathlib import Path
import re,subprocess,tempfile
R=Path(__file__).resolve().parents[2];s=(R/'third_party/common/menu.c').read_text()
def fn(n):
 m=re.search(r'^(?:static )?[\w *]+\b'+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 return s[m.start():s.index('\n}',m.end())+2]
ids=sorted(set(re.findall(r'\bMENU_[A-Z0-9_]+\b','\n'.join(fn(n) for n in ['menu_root_priority','show_raw_rom_menu']))))
code='''
#include <cassert>
#include <cstring>
#include <vector>
#include <string>
#include <algorithm>
#include "ui.h"
#include "menu_theme.h"
enum {'''+','.join(ids)+'''};
static menu_item popup,rows[7];
static int row_count;
static std::vector<int> calls;
static std::vector<std::string> names;
static int selected;
static menu_item*ui_push_menu(int w,int h){assert(w==34&&h==9);popup.menu_width=w*8;row_count=0;popup.first_child=nullptr;return &popup;}
static void ui_menu_add_read_only_heading(menu_item *p,const char *n){assert(p==&popup);}
static void ui_menu_add_divider(menu_item *p){assert(p==&popup);}
static void ui_menu_add_button(int id,menu_item *p,const char *n){assert(p==&popup);calls.push_back(id);names.push_back(n);}
static void ui_select_first_interactive_item(){selected++;}
'''
# ui.h declares these functions extern; use its actual compatible signatures instead.
code=code.replace('static menu_item*ui_push_menu','menu_item*ui_push_menu').replace('static void ui_menu_add_read_only_heading','menu_item *ui_menu_add_read_only_heading').replace('static void ui_menu_add_divider','menu_item *ui_menu_add_divider').replace('static void ui_menu_add_button','menu_item *ui_menu_add_button').replace('static void ui_select_first_interactive_item','void ui_select_first_interactive_item')
code=code.replace('assert(p==&popup);}','assert(p==&popup);auto *row=&rows[row_count++];memset(row,0,sizeof(*row));if(!p->first_child)p->first_child=row;else rows[row_count-2].next=row;return row;}').replace('assert(p==&popup);}','assert(p==&popup);auto *row=&rows[row_count++];memset(row,0,sizeof(*row));if(!p->first_child)p->first_child=row;else rows[row_count-2].next=row;return row;}').replace('names.push_back(n);}','names.push_back(n);auto *row=&rows[row_count++];memset(row,0,sizeof(*row));row->id=id;if(!p->first_child)p->first_child=row;else rows[row_count-2].next=row;return row;}')
code+='\nint ui_text_width(const char *s){return strlen(s)*8;}\nstatic void attach_cart(int id, menu_item *item){calls.push_back(id);names.push_back(item->str_value);}\n'+fn('file_label_prefix')+'\n'+fn('fit_file_size_label')+'\n'+fn('raw_rom_type_selected')+'\n'+fn('menu_root_priority')+'\n'+fn('show_raw_rom_menu')+'''
int main(){
 const int expected[]={MENU_AUTOSTART,MENU_C64_ATTACH_CART,MENU_LOAD_ROM_IMAGE,MENU_LOAD_SNAP,MENU_SAVE_SNAP,MENU_SWAP_JOYSTICKS,MENU_WARP_MODE};
 std::vector<menu_item> items(7);for(int i=0;i<7;i++){items[i].id=expected[i];assert(menu_root_priority(&items[i])==i+1);}
 std::reverse(items.begin(),items.end());std::stable_sort(items.begin(),items.end(),[](const menu_item&a,const menu_item&b){return menu_root_priority(&a)<menu_root_priority(&b);});for(int i=0;i<7;i++)assert(items[i].id==expected[i]);
 const int raw_ids[]={MENU_C64_CART_8K_FILE,MENU_C64_CART_16K_FILE,MENU_C64_CART_ULTIMAX_FILE};
 const char *labels[]={"Load Raw  8K >","Load Raw 16K >","Load Raw Ultimax >"};
 menu_item selected_file={};strcpy(selected_file.str_value,"selected.rom");strcpy(selected_file.displayed_value,"16 KB");show_raw_rom_menu(&selected_file);assert(selected==1&&calls.size()==3&&row_count==7);for(auto &r:rows)assert(r.menu_top==0);for(int i=0;i<3;i++){assert(calls[i]==raw_ids[i]&&names[i]==labels[i]);}
 for(int i=0;i<3;i++){assert(!strcmp(rows[4+i].str_value,selected_file.str_value));assert(rows[4+i].on_value_changed);rows[4+i].on_value_changed(&rows[4+i]);assert(calls.back()==raw_ids[i]&&names.back()==selected_file.str_value);}
 calls.clear();names.clear();show_raw_rom_menu(&selected_file);assert(selected==2&&calls.size()==3);for(int i=0;i<3;i++)assert(calls[i]==raw_ids[i]&&names[i]==labels[i]);

}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['c++','-std=c++17','-fpermissive','-I'+str(R/'third_party/common'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
for id,label in [('MENU_AUTOSTART','Load & Run Disk >'),('MENU_C64_ATTACH_CART','Load Cartridge >'),('MENU_LOAD_ROM_IMAGE','Load ROM Image >'),('MENU_LOAD_SNAP','Load Snapshot >'),('MENU_SAVE_SNAP','Save Snapshot >'),('MENU_SWAP_JOYSTICKS','Swap Joysticks')]:
 assert f'ui_menu_add_button({id}, root, "{label}")' in s;assert len(label)<=36
assert 'show_files(DIR_DISKS, FILTER_DISK, MENU_AUTOSTART_FILE, 0);' in s
assert 'case MENU_LOAD_ROM_IMAGE:\n    show_files(DIR_CARTS, FILTER_NONE, MENU_C64_CART_8K_FILE, 0);' in s
assert 'ui_menu_add_toggle(MENU_WARP_MODE, root,' in s
print('PASS: exact seven-entry production priorities, original IDs, shared raw submenu with original dispatch IDs, first selection, labels/arrows/40-column fit, disk picker and toggles preserved')
