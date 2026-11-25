#!/usr/bin/env python3
"""Exercise fixed /dir/C64 lookup without touching emulator/SD data."""
from pathlib import Path
import argparse
import re
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root/'third_party/common/menu.c').read_text()
header = (root/'third_party/common/menu.h').read_text()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline', type=Path)
args = parser.parse_args()

def function(text, name):
    match = re.search(r'^(?:static )?[\w *]+\b'+name+r'\([^;]*?\)\s*\{', text, re.M)
    assert match, name
    return text[match.start():text.index('\n}', match.end())+2]

assert 'Look For Files In' not in source
assert 'dir_convention' not in source
assert 'MENU_DIR_CONVENTION' not in source
assert 'MenuDirConvention' not in header
assert 'MENU_RESERVED_DIR_CONVENTION,' in header
assert source.index('  load_settings();') < source.index('  set_current_dir_names();', source.index('void build_menu('))
if args.baseline:
    before = args.baseline.read_text()
    for name in ['fullpath', 'list_files', 'remove_dir']:
        assert function(source,name) == function(before,name),name
    old_save = function(before,'save_settings_to')
    assert function(source,'save_settings_to') == old_save.replace('  fprintf(fp, "dir_convention=%d\\n", dir_convention_item->value);\n','')
    old_load = function(before,'load_settings')
    assert function(source,'load_settings') == old_load.replace('    } else if (strcmp(name, "dir_convention") == 0) {\n      dir_convention_item->value = value;\n','')
    before_header = args.baseline.with_name('menu.h').read_text()
    old_ids = re.search(r'MENU_USERPORT_TYPE,\s*MENU_DIR_CONVENTION,\s*MENU_DRIVE_FLUSH,',before_header)
    assert old_ids and re.search(r'MENU_USERPORT_TYPE,\s*MENU_RESERVED_DIR_CONVENTION,[^\n]*\n\s*MENU_DRIVE_FLUSH,',header)

api = (root/'third_party/common/emux_api.h').read_text()
dirs = re.search(r'typedef enum \{\s*DIR_ROOT,.*?\} DirType;',api,re.S).group()
defaults = re.search(r'static const char default_dir_names\[NUM_DIR_TYPES\]\[16\] = \{.*?\};',source,re.S).group()
code = r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#define NUM_DIR_TYPES 7
''' + dirs + defaults + r'''
static char current_dir_names[NUM_DIR_TYPES][256],machine_sub_dir[16];
static char current_volume_name[8],full_path_str[1024];
''' + function(source,'set_current_dir_names') + '\n' + function(source,'fullpath') + r'''
int main(){
 for(const char *machine:{"/c64","/c128","/vic20"}){
  strcpy(machine_sub_dir,machine);set_current_dir_names();
  for(int i=0;i<NUM_DIR_TYPES;i++){
   char expected[256];
   if(i==DIR_ROMS)strcpy(expected,machine);
   else if(i==DIR_IEC)strcpy(expected,"/");
   else snprintf(expected,sizeof(expected),"%s%s",default_dir_names[i==DIR_ROOT?DIR_DISKS:i],machine);
   assert(!strcmp(current_dir_names[i],expected));
   for(const char *volume:{"SD:","USB:","USB2:"}){
    strcpy(current_volume_name,volume);char path[512];
    snprintf(path,sizeof(path),"%s%s%sExample.img",volume,expected,expected[strlen(expected)-1]=='/'?"":"/");
    assert(!strcmp(fullpath((DirType)i,(char*)"Example.img"),path));
    assert(!strcmp(current_dir_names[i],expected));
   }
  }
  // Reinitialization keeps the exact fixed default after browser navigation.
  strcpy(current_dir_names[DIR_DISKS],"/temporary/browser/path");
  set_current_dir_names();char expected[256];snprintf(expected,sizeof(expected),"/disks%s",machine);
  assert(!strcmp(current_dir_names[DIR_DISKS],expected));
 }
 strcpy(machine_sub_dir,"/c64");set_current_dir_names();
 assert(!strcmp(current_dir_names[DIR_DISKS],"/disks/c64"));
 assert(!strcmp(current_dir_names[DIR_TAPES],"/tapes/c64"));
 assert(!strcmp(current_dir_names[DIR_CARTS],"/carts/c64"));
 assert(!strcmp(current_dir_names[DIR_SNAPS],"/snapshots/c64"));
 assert(!strcmp(current_dir_names[DIR_ROMS],"/c64"));
}
'''
with tempfile.TemporaryDirectory(prefix='e64-directory-preference-') as directory:
    path=Path(directory)/'test.cpp';exe=Path(directory)/'test';path.write_text(code)
    subprocess.run(['c++','-std=c++11','-Wall','-Wextra','-Werror',str(path),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('PASS: no control or obsolete setting state/save/load/callback; stable menu IDs; fixed original-default directory lookup, all seven directory types, ROM/root/IEC exceptions, three machine folders, SD/USB paths and reinitialization')
