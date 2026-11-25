#!/usr/bin/env python3
"""Execute production cartridge-type dispatch with hardware/file I/O mocked."""
from pathlib import Path
import re
import subprocess
import tempfile
root=Path(__file__).resolve().parents[2]
cart_menu=(root/'third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c').read_text()
ui=(root/'third_party/common/ui.c').read_text()
labels={
 'MENU_C64_ATTACH_CART_8K':'Load Raw  8K >',
 'MENU_C64_ATTACH_CART_16K':'Load Raw 16K >',
 'MENU_C64_ATTACH_CART_ULTIMAX':'Load Raw Ultimax >',
 'MENU_MAKE_CART_DEFAULT':'Set Attached Cartridge as Default',
}
common_menu=(root/"third_party/common/menu.c").read_text()
for menu_id,label in labels.items():
 if menu_id.startswith('MENU_C64_ATTACH_CART_'):
  # Approved file-first chooser uses the same final attachment IDs.
  assert label in common_menu and menu_id.replace('ATTACH_CART_', 'CART_')+'_FILE' in common_menu
 else:
  assert re.search(r'ui_menu_add_button\(\s*'+menu_id+r'\s*,\s*(?:parent|popup)\s*,\s*"'+re.escape(label)+r'"\s*\)',cart_menu+common_menu),menu_id
 # Cartridge is one expanded level: 3 cells of left inset, one at right.
 assert len(label)<=35 and 3*8+len(label)*8<=40*8-8,label
assert 'return "Load Raw Ultimax >";' in ui

s=(root/'third_party/vice-3.3/src/arch/raspi/vice_menu_cart_osd.c').read_text()
start=s.index('int emux_attach_cart(');handler=s[start:s.index('\n}',start)+2]
menu=(root/'third_party/common/menu.c').read_text()
for kind in ['8K','16K','ULTIMAX']:
 assert re.search(r'case MENU_C64_ATTACH_CART_'+kind+r':\s*show_files\(DIR_CARTS, FILTER_NONE, MENU_C64_CART_'+kind+r'_FILE, 0\);',menu)
ids=sorted(set(re.findall(r'\b(?:MENU_[A-Z0-9_]+|CARTRIDGE_[A-Z0-9_]+)',handler)))
code=r'''
#include <assert.h>
#include <string.h>
enum { @IDS@ };
static int result,seen_type,attach_calls,pops,closes,errors,refreshes;
static void emux_refresh_cartridge_menu(void){refreshes++;}
static const char *seen_filename;
static void ui_info(const char *text){assert(!strcmp(text,"Attaching..."));}
static void ui_error(const char *text){assert(!strcmp(text,"Failed to attach cart image"));errors++;}
static void ui_pop_menu(void){pops++;}
static void ui_pop_all_and_toggle(void){closes++;}
static int cartridge_attach_image(int type,char *filename){seen_type=type;seen_filename=filename;attach_calls++;return result;}
'''.replace('@IDS@',','.join(ids))+handler+r'''
int main(void){
 const int menu_ids[]={MENU_C64_CART_8K_FILE,MENU_C64_CART_16K_FILE,MENU_C64_CART_ULTIMAX_FILE,MENU_C64_CART_FILE};
 const int types[]={CARTRIDGE_GENERIC_8KB,CARTRIDGE_GENERIC_16KB,CARTRIDGE_ULTIMAX,CARTRIDGE_CRT};
 for(int i=0;i<4;i++)for(int failure=0;failure<2;failure++){
  result=failure?-1:0;attach_calls=pops=closes=errors=refreshes=0;
  char filename[]="/carts/c64/selected-file.bin";
  assert(emux_attach_cart(menu_ids[i],filename)==failure);
  assert(attach_calls==1&&seen_type==types[i]&&seen_filename==filename&&refreshes==1);
  assert(pops==failure&&errors==failure&&closes==!failure);
 }
}
'''
with tempfile.TemporaryDirectory(prefix='e64-raw-cartridge-') as directory:
 p=Path(directory)/'test.c';exe=Path(directory)/'test';p.write_text(code)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('PASS: unchanged raw file-picker IDs; real 8K/16K/Ultimax and standard CRT dispatch; exact filename preservation; success closes menus; failure retains error/pop behavior')
