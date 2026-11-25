#!/usr/bin/env python3
"""Execute the current IDE64 attachment/reset handler without disk access."""
from pathlib import Path
import re
import subprocess
import tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
start=source.index('int emux_handle_ide64_image_change(')
handler=source[start:source.index('\n}',start)+2]
menu=(root/'third_party/common/menu.c').read_text()
cart=(root/'third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c').read_text()
assert 'MENU_CREATE_EMPTY_DISK_MENU, drive_parent,\n                       "Create Empty Disk >"' in menu
assert 'case MENU_CREATE_EMPTY_DISK_MENU:\n    show_create_empty_disk_menu();' in menu
assert 'MENU_IDE64_IMAGE_1 + device, device_menu, "Attach Disk >"' in cart
assert 'for (int device = 0; device < 4; device++)' in cart
code=r'''
#include <assert.h>
#include <string.h>
#define MACHINE_RESET_MODE_HARD 2
static int result,calls,resets,seen_device;
static const char *seen_path;
static int resources_set_string_sprintf(const char *key,const char *path,int device){
 assert(!strcmp(key,"IDE64Image%i"));seen_device=device;seen_path=path;calls++;return result;
}
static void machine_trigger_reset(int type){assert(type==MACHINE_RESET_MODE_HARD);resets++;}
'''+handler+r'''
int main(void){
 for(int device=1;device<=4;device++)for(int outcome=0;outcome<2;outcome++){
  result=outcome?-7:0;calls=resets=0;
  assert(emux_handle_ide64_image_change(device,"/disks/c64/example.dhd")==result);
  assert(calls==1&&seen_device==device&&!strcmp(seen_path,"/disks/c64/example.dhd"));
  assert(resets==(result==0));
 }
 calls=resets=0;
 assert(emux_handle_ide64_image_change(0,"ignored")==-1);
 assert(emux_handle_ide64_image_change(5,"ignored")==-1);
 assert(calls==0&&resets==0);
}
'''
with tempfile.TemporaryDirectory(prefix='e64-ide64-labels-') as directory:
 p=Path(directory)/'test.c';exe=Path(directory)/'test';p.write_text(code)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('PASS: creation/menu IDs unchanged; all four ATA devices retain attachment paths; successful IDE64 attach hard-resets exactly once; failure/invalid device never resets')
