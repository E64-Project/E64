#!/usr/bin/env python3
"""Live type/availability and unchanged real BIN/CRT saving, using temp files."""
from pathlib import Path
import re,subprocess,tempfile
root=Path(__file__).resolve().parents[2]
def read(name):return (root/name).read_text()
def fn(source,name):
 m=re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{',source,re.M);assert m,name
 return source[m.start():source.index('\n}',m.end())+2]
cart=read('third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c');api=read('third_party/vice-3.3/src/arch/raspi/vice_api.c');menu=read('third_party/common/menu.c');osd=read('third_party/vice-3.3/src/arch/raspi/vice_menu_cart_osd.c')
core=read('third_party/vice-3.3/src/c64/cart/c64cart.c');header=read('third_party/vice-3.3/src/cartridge.h');ef=read('third_party/vice-3.3/src/c64/cart/easyflash.c');crt=read('third_party/vice-3.3/src/c64/cart/crt.c');util=read('third_party/vice-3.3/src/util.c')
refresh=fn(cart,'emux_refresh_cartridge_menu');assert 'filename' not in refresh and 'cartridge_type_enabled(CARTRIDGE_EASYFLASH)' in refresh
assert 'emux_refresh_cartridge_menu();' in fn(menu,'menu_about_to_activate')
assert 'emux_refresh_cartridge_menu();' in fn(menu,'main_menu_cursor_listener')
assert 'emux_refresh_cartridge_menu();' in fn(api,'emux_detach_cart')
assert 'emux_refresh_cartridge_menu();' in fn(osd,'emux_attach_cart')
assert 'emux_refresh_cartridge_menu();' in fn(cart,'emux_add_cartridge_options')
def defines(names):
 return '\n'.join(re.search(r'^#define '+n+r'\s+[^\n]+',header,re.M).group() for n in names)+'\n'
state_code=r'''
#include <assert.h>
#include <stddef.h>
'''+defines(['CARTRIDGE_NONE','CARTRIDGE_EASYFLASH','CARTRIDGE_GENERIC_8KB'])+r'''
struct menu_item {int disabled;};
static struct menu_item *easyflash_save_item;
static int attached_type=CARTRIDGE_NONE,queries;
static int cart_getid_slotmain(void){queries++;return attached_type;}
static int cart_type_enabled(int type){(void)type;return 0;}
'''+fn(core,'cartridge_type_enabled')+'\n'+refresh+r'''
int main(void){
 emux_refresh_cartridge_menu();assert(queries==0);
 static struct menu_item save={0};easyflash_save_item=&save;
 int types[]={CARTRIDGE_NONE,CARTRIDGE_GENERIC_8KB,CARTRIDGE_EASYFLASH,CARTRIDGE_NONE,CARTRIDGE_EASYFLASH,CARTRIDGE_GENERIC_8KB};
 for(unsigned i=0;i<sizeof(types)/sizeof(types[0]);i++){attached_type=types[i];emux_refresh_cartridge_menu();assert(save.disabled==(types[i]!=CARTRIDGE_EASYFLASH));}
 assert(queries==6);
}
'''
chip=re.search(r'typedef struct crt_chip_header_s \{.*?\} crt_chip_header_t;',read('third_party/vice-3.3/src/c64/cart/crt.h'),re.S).group()
writer_code=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define MODE_WRITE "wb"
#define EASYFLASH_N_BANK_BITS 6
#define EASYFLASH_N_BANKS (1 << EASYFLASH_N_BANK_BITS)
'''+defines(['CARTRIDGE_EASYFLASH','CARTRIDGE_FILETYPE_BIN','CARTRIDGE_FILETYPE_CRT','CARTRIDGE_NAME_EASYFLASH'])+chip+r'''
static const char STRING_EASYFLASH[]=CARTRIDGE_NAME_EASYFLASH;
static char *easyflash_filename;
static int easyflash_filetype,easyflash_crt_optimize=1;
static uint8_t low_data[EASYFLASH_N_BANKS*0x2000],high_data[EASYFLASH_N_BANKS*0x2000];
struct flash_state {uint8_t *flash_data;};
static struct flash_state low={low_data},high={high_data};
static struct flash_state *easyflash_state_low=&low,*easyflash_state_high=&high;
'''+re.search(r'^const char CRT_HEADER\[\].*$',crt,re.M).group()+'\n'+re.search(r'^static const char CHIP_HEADER\[\].*$',crt,re.M).group()+'\n'
for source,names in [(util,['util_dword_to_be_buf','util_word_to_be_buf']),(crt,['crt_write_chip','crt_create']),(ef,['easyflash_write_chip_if_not_empty','easyflash_bin_save','easyflash_crt_save','easyflash_flush_image'])]:
 for name in names:writer_code+=fn(source,name)+'\n'
writer_code+=r'''
int main(int argc,char**argv){
 assert(argc==2);char path[1024];
 for(int bank=0;bank<EASYFLASH_N_BANKS;bank++){memset(low_data+bank*0x2000,bank^0x5a,0x2000);memset(high_data+bank*0x2000,bank^0xa5,0x2000);}
 snprintf(path,sizeof(path),"%s/saved.bin",argv[1]);easyflash_filename=path;easyflash_filetype=CARTRIDGE_FILETYPE_BIN;assert(easyflash_flush_image()==0);
 snprintf(path,sizeof(path),"%s/saved.crt",argv[1]);easyflash_filetype=CARTRIDGE_FILETYPE_CRT;assert(easyflash_flush_image()==0);
 snprintf(path,sizeof(path),"%s/missing-parent/fail.crt",argv[1]);assert(easyflash_flush_image()==-1);
 easyflash_filename=NULL;assert(easyflash_flush_image()==-2);
}
'''
with tempfile.TemporaryDirectory(prefix='e64-easyflash-') as directory:
 d=Path(directory)
 for name,source in [('availability',state_code),('writers',writer_code)]:
  p=d/(name+'.c');exe=d/name;p.write_text(source)
  subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True)
  subprocess.run([str(exe)]+([str(d)] if name=='writers' else []),check=True)
 expected=b''.join(bytes([bank^0x5a])*0x2000+bytes([bank^0xa5])*0x2000 for bank in range(64))
 assert (d/'saved.bin').read_bytes()==expected
 data=(d/'saved.crt').read_bytes();assert data[:16]==b'C64 CARTRIDGE   ' and int.from_bytes(data[0x16:0x18],'big')==32
 offset=0x40
 for bank in range(64):
  for address,value in [(0x8000,bank^0x5a),(0xa000,bank^0xa5)]:
   head=data[offset:offset+16];assert head[:4]==b'CHIP' and int.from_bytes(head[4:8],'big')==0x2010
   assert int.from_bytes(head[8:10],'big')==2 and int.from_bytes(head[10:12],'big')==bank
   assert int.from_bytes(head[12:14],'big')==address and int.from_bytes(head[14:16],'big')==0x2000
   assert data[offset+16:offset+0x2010]==bytes([value])*0x2000;offset+=0x2010
 assert offset==len(data)
print('PASS: actual VICE cartridge-type API and availability transitions; construction/open/navigation/attach/detach refresh wiring; unchanged real EasyFlash BIN and CRT writers preserve all 64 banks; save failures reported; temporary files only')
