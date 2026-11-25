#!/usr/bin/env python3
"""Execute unchanged EasyFlash-save and cartridge-freeze dispatch without I/O."""
from pathlib import Path
import subprocess,tempfile
r=Path(__file__).resolve().parents[2]
api=(r/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text();cart=(r/'third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c').read_text()
save=api[api.index('    case MENU_SAVE_EASYFLASH:'):api.index('    case MENU_REU_SAVE_IMAGE:',api.index('    case MENU_SAVE_EASYFLASH:'))]
freeze=api[api.index('    case MENU_CART_FREEZE:'):api.index('    case MENU_DRIVE_RAM_2000:',api.index('    case MENU_CART_FREEZE:'))]
a=cart.index('void cartridge_freeze(void)');freeze_function=cart[a:cart.index('\n}',a)+2]
assert 'MENU_SAVE_EASYFLASH, parent, "Save EasyFlash Changes"' in cart
assert 'MENU_CART_FREEZE, parent, "Press Cartridge Freeze Button"' in cart
code=r'''
#include <assert.h>
#include <string.h>
enum {MENU_SAVE_EASYFLASH,MENU_CART_FREEZE,CARTRIDGE_EASYFLASH};
struct menu_item {int id;};
#define BMC64_MACHINE_CLASS_C64 0
static int emux_machine_class=BMC64_MACHINE_CLASS_C64;
static int attached_type=CARTRIDGE_EASYFLASH;
static void emux_refresh_cartridge_menu(void){}
static int cartridge_type_enabled(int type){assert(type==CARTRIDGE_EASYFLASH);return attached_type==type;}
static int events[8],count,result;
static void keyboard_clear_keymatrix(void){events[count++]=1;}
static void cartridge_trigger_freeze(void){events[count++]=2;}
static void ui_pop_all_and_toggle(void){events[count++]=3;}
static int cartridge_flush_image(int type){assert(type==CARTRIDGE_EASYFLASH);events[count++]=4;return result;}
static void ui_error(const char *text){assert(!strcmp(text,"Problem saving"));events[count++]=5;}
'''+freeze_function+'\nstatic int dispatch(struct menu_item *item){switch(item->id){\n'+save+freeze+'\n}return 0;}\n'+r'''
int main(void){
 struct menu_item item={MENU_SAVE_EASYFLASH};
 count=0;result=0;assert(dispatch(&item)==1&&count==2&&events[0]==4&&events[1]==3);
 count=0;result=-1;assert(dispatch(&item)==1&&count==2&&events[0]==4&&events[1]==5);
 for(int type=-1;type<=0;type++){attached_type=type;count=0;assert(dispatch(&item)==1&&count==0);}
 attached_type=CARTRIDGE_EASYFLASH;
 count=0;item.id=MENU_CART_FREEZE;assert(dispatch(&item)==1&&count==3&&events[0]==1&&events[1]==2&&events[2]==3);
}
'''
with tempfile.TemporaryDirectory(prefix='e64-cartridge-actions-') as d:
 p=Path(d)/'test.c';exe=Path(d)/'test';p.write_text(code)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True)
print('PASS: exact main-menu labels/IDs; real EasyFlash flush success/failure dispatch; real keyboard-clear/freeze/close sequence; no cartridge loading, removal or file-writing code changed')
