#!/usr/bin/env python3
"""Execute production blank-TAP creation with filesystem writes mocked."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[2]
source=(root/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
start=source.index('void emux_create_tape(');create=source[start:source.index('\n}',start)+2]
menu=(root/'third_party/common/menu.c').read_text()
for identifier,label in [('MENU_ATTACH_TAPE','Attach Tape >'),('MENU_DETACH_TAPE','Remove Tape'),('MENU_CREATE_TAP','Create Empty Tape >')]:
 assert f'ui_menu_add_button({identifier}, parent, "{label}");' in menu
assert 'case MENU_ATTACH_TAPE:\n    show_files(DIR_TAPES, FILTER_TAPE, MENU_TAPE_FILE, 0);' in menu
assert 'case MENU_CREATE_TAP:\n    show_files(DIR_TAPES, FILTER_NONE, MENU_CREATE_TAP_FILE, 0);' in menu
assert 'emux_attach_tape_image(fullpath(DIR_TAPES, item->str_value))' in menu
assert 'case MENU_DETACH_TAPE:\n    ui_info("Removing...");\n    emux_detach_tape();' in menu
code=r'''
#include <assert.h>
#include <string.h>
#include <strings.h>
#include <stdio.h>
#include "ui.h"
#define DIR_TAPES 2
#define DISK_IMAGE_TYPE_TAP 2
static int result,calls,pops,errors;
static char path[256],seen_path[256],last_info[64],last_error[64];
typedef char *(*fullpath_func)(int,char*);
static char *fullpath(int type,char *name){assert(type==DIR_TAPES);snprintf(path,sizeof(path),"SD:/tapes/c64/%s",name);return path;}
static int cbmimage_create_image(const char *name,int type){assert(type==DISK_IMAGE_TYPE_TAP);strcpy(seen_path,name);calls++;return result;}
void ui_info(const char *text, ...){strcpy(last_info,text);}
void ui_error(const char *text, ...){strcpy(last_error,text);errors++;}
struct menu_item *ui_pop_menu(void){pops++;return NULL;}
'''+create+r'''
static void reset(void){calls=pops=errors=0;last_info[0]=last_error[0]=0;}
int main(void){
 struct menu_item item={0};item.type=TEXTFIELD;
 result=0;reset();strcpy(item.str_value,"blank");emux_create_tape(&item,fullpath);
 assert(calls==1&&!strcmp(seen_path,"SD:/tapes/c64/blank.tap")&&pops==2&&!errors&&!strcmp(last_info,"Tape Created"));
 reset();strcpy(item.str_value,"blank.TAP");emux_create_tape(&item,fullpath);assert(calls==1&&!strcmp(seen_path,"SD:/tapes/c64/blank.TAP"));
 result=-1;reset();emux_create_tape(&item,fullpath);assert(calls==1&&pops==1&&errors==1&&!strcmp(last_error,"Create tape image failed"));
 reset();item.str_value[0]=0;emux_create_tape(&item,fullpath);assert(!calls&&errors==1&&!strcmp(last_error,"Empty filename"));
 reset();strcpy(item.str_value,"wrong.d64");emux_create_tape(&item,fullpath);assert(!calls&&errors==1&&!strcmp(last_error,"Wrong extension"));
 reset();item.type=BUTTON;strcpy(item.str_value,"existing.tap");emux_create_tape(&item,fullpath);assert(!calls&&!pops&&!errors);
}
'''
with tempfile.TemporaryDirectory(prefix='e64-tape-labels-') as directory:
 p=Path(directory)/'test.c';exe=Path(directory)/'test';p.write_text(code)
 subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-Wno-sign-compare','-I'+str(root/'third_party/common'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('PASS: exact Tape labels/IDs, attachment/removal/creation wiring; production TAP type/path/extension; existing-file guard, success and failure handling')
