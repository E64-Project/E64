#!/usr/bin/env python3
"""Final approved single-removal design, original auto-save and popup Back."""
from pathlib import Path
import re,subprocess,tempfile
R=Path(__file__).resolve().parents[2]
def read(p):return (R/p).read_text()
def fn(s,n):
 m=re.search(r'^(?:static )?[\w *]+\b'+n+r'\([^;]*?\)\s*\{',s,re.M);assert m,n
 return s[m.start():s.index('\n}',m.end())+2]
menu=read('third_party/common/menu.c');cart=read('third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c');api=read('third_party/vice-3.3/src/arch/raspi/vice_api.c');ui=read('third_party/common/ui.c');ef=read('third_party/vice-3.3/src/c64/cart/easyflash.c')
old=R/'E64-Source-Backups/before-cartridge-rom-separation-20261110-130937'
assert fn(api,'emux_detach_cart')==fn((old/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text(),'emux_detach_cart')
# Compare attachment/removal behavior, allowing the approved read-only ROM lookup API.
for name in ['emux_handle_rom_change']:
 assert fn(api,name)==fn((old/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text(),name)
for p in ['third_party/vice-3.3/src/c64/cart/c64cart.c','third_party/vice-3.3/src/cartridge.h']:
 assert read(p)==(old/p).read_text(),p
for forbidden in ['emux_cartridge_image_kind','emux_remove_cartridge_image','cartridge_current_image_type','MENU_REMOVE_ROM','"Remove ROM"','"ROM Images"']:
 assert forbidden not in menu+cart+api+read('third_party/common/menu.h'),forbidden
original=(old/'third_party/common/menu.c').read_text()
def removal(s):return re.search(r'  case MENU_DETACH_CART:.*?    return;',s,re.S).group()
assert removal(menu)==removal(original)
assert len(re.findall(r'ui_menu_add_button\(MENU_DETACH_CART\b',cart))==1
assert 'ui_menu_add_button(MENU_LOAD_ROM_IMAGE, parent, "Load ROM Image >")' in cart
assert 'ui_menu_add_button(MENU_LOAD_ROM_IMAGE, root, "Load ROM Image >")' in menu
assert 'case MENU_LOAD_ROM_IMAGE:\n    show_files(DIR_CARTS, FILTER_NONE, MENU_C64_CART_8K_FILE, 0);' in menu
assert 'label: "Load ROM...", run: () => loadRawCartridge(path, e)' in read('src/webui/assets/js/files.js')
# Execute the actual detach-time EasyFlash auto-save decision and actual
# native popup stack push/pop. No real media or saved Config is touched.
code=r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "ui.h"
#include "menu_theme.h"
static int easyflash_crt_write,writes,shutdowns,unregisters,export_res;
static void *easyflash_state_low,*easyflash_state_high,*easyflash_io1_list_item,*easyflash_io2_list_item;
static char *easyflash_filename;
static int easyflash_flush_image(){writes++;return 0;}
static void flash040core_shutdown(void*){shutdowns++;}
static void lib_free(void *p){free(p);}
static void io_source_unregister(void*){unregisters++;}
static void export_remove(void*){}
'''+fn(ef,'easyflash_detach')+r'''
static menu_item menu_roots[NUM_MENU_ROOTS];
static int current_menu,menu_width_chars=40,menu_height_chars=25;
static int menu_cursor[NUM_MENU_ROOTS],menu_window_top[NUM_MENU_ROOTS],menu_window_bottom[NUM_MENU_ROOTS];
static void ui_text_cursor_reset(){}
static void ui_clear_menu(int i){menu_roots[i].first_child=nullptr;}
static int calc_root_menu_left(){return 8;}
static int calc_root_menu_top(){return 8;}
static int ui_row_pitch(int){return 10;}
'''+fn(ui,'ui_push_menu')+'\n'+fn(ui,'ui_pop_menu')+r'''
int main(){
 for(int value=0;value<=1;value++){
  easyflash_crt_write=value;writes=shutdowns=unregisters=0;
  easyflash_detach();assert(writes==value&&easyflash_crt_write==value&&shutdowns==2&&unregisters==2);
 }
 // Quick Access and the expanded Cartridge section both live in root page 0.
 // Pop the common raw chooser back to either original cursor/expansion state.
 for(int from_cartridge=0;from_cartridge<=1;from_cartridge++){
  current_menu=0;menu_cursor[0]=from_cartridge?31:3;menu_window_top[0]=from_cartridge?19:0;
  menu_item cartridge={};cartridge.type=FOLDER;cartridge.is_expanded=from_cartridge;menu_roots[0].first_child=&cartridge;
  menu_roots[0].menu_width=320;menu_roots[0].menu_height=200;
  auto*raw=ui_push_menu(-1,-1);assert(raw==&menu_roots[1]&&current_menu==1);
  // Raw file picker is another level; Back first returns to the raw chooser.
  auto*picker=ui_push_menu(-1,-1);assert(picker==&menu_roots[2]);
  assert(ui_pop_menu()==raw&&current_menu==1);
  assert(ui_pop_menu()==&menu_roots[0]&&current_menu==0);
  assert(menu_cursor[0]==(from_cartridge?31:3)&&menu_window_top[0]==(from_cartridge?19:0));
  assert(menu_roots[0].first_child==&cartridge&&cartridge.is_expanded==from_cartridge);
 }
}
'''
with tempfile.TemporaryDirectory(prefix='e64-final-rom-menu-') as d:
 p=Path(d)/'test.cpp';p.write_text(code);exe=Path(d)/'test'
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-I'+str(R/'third_party/common'),str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('PASS: both shared ROM entry points; original detach dispatcher/API restored; no origin-tracking or save suppression; actual EasyFlash auto-save Off/On; actual popup Back to raw chooser and each unchanged parent cursor/scroll/expansion; one removal; Web ROM wording')
