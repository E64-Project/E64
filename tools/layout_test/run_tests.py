#!/usr/bin/env python3
"""Exercise production ROM search and README policy, and audit review staging."""
from pathlib import Path
import importlib.util
import re
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]

def function(path, name):
    text = path.read_text()
    start = re.search(r'^[\w *]+\b' + re.escape(name) + r'\([^;]*?\)\s*\{', text, re.M).start()
    end = text.index('\n}', start) + 2
    return text[start:end]

pre = r'''
#include <assert.h>
#include <ctype.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#define ARCHDEP_FINDPATH_SEPARATOR_STRING ":"
static char *default_path;
static const char *archdep_boot_path(void) { return ""; }
static char *lib_stralloc(const char *s) { return strdup(s); }
#define lib_free free
static char *util_concat(const char *first, ...) {
    char out[1024] = "";
    va_list ap; va_start(ap, first);
    for (const char *p = first; p; p = va_arg(ap, const char *)) strcat(out, p);
    va_end(ap); return strdup(out);
}
'''
pre += '\n#define BOOTSTAT_WHAT_STAT 1\n#define BOOTSTAT_WHAT_FAIL 2\n#include "' + str(ROOT/'src/bootstat_c64.h') + '"\n'
code = pre + function(ROOT/'src/new_io.cpp', 'strend') + '\n' + function(ROOT/'third_party/vice-3.3/src/arch/raspi/archdep.c', 'archdep_default_sysfile_pathlist')
code += '\n' + function(ROOT/'third_party/common/menu.c', 'menu_is_documentation')
code += r'''
int main(void) {
    assert(!strcmp(archdep_default_sysfile_pathlist("C64"), "/c64:/drives:/carts:"));
    free(default_path); default_path = NULL;
    assert(!strcmp(archdep_default_sysfile_pathlist("PLUS4"), "/plus4:/drives:/carts:"));
    free(default_path);
    for (int i=0;i<dflt_bootStatNum;i++) {
        const char *entry=dflt_bootStatFile[i];
        const char *base=strrchr(entry, '/');
        if (base && !strncmp(base+1,"dos",3)) {
            char drive[80]; snprintf(drive,sizeof(drive),"/drives/%s",base+1);
            assert(!strend(drive,entry)); assert(strend(entry,entry));
        } else assert(strncmp(entry,"dos",3));
    }
    const char *hidden[] = {"README.txt", "README-c64.txt", "readme", "ReAdMe-drives.txt", "README.d64"};
    for (unsigned i=0;i<sizeof(hidden)/sizeof(*hidden);i++) assert(menu_is_documentation(hidden[i]));
    const char *shown[] = {"kernal", "dos1541", "eprom.bin", "game.d64", "my-readme.d64"};
    for (unsigned i=0;i<sizeof(shown)/sizeof(*shown);i++) assert(!menu_is_documentation(shown[i]));
}
'''
(ROOT/'build').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='layout-test-') as tmp:
    tmp=Path(tmp); source=tmp/'layout.c'; source.write_text(code)
    exe=tmp/'layout'
    subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
    spec=importlib.util.spec_from_file_location('stage_e64',ROOT/'tools/stage_e64.py')
    staging=importlib.util.module_from_spec(spec);spec.loader.exec_module(staging)
    dest=tmp/'review';staging.stage(dest)
    assert {p.name for p in dest.iterdir() if p.is_dir()} == {'c64','drives','carts','configs','firmware','system'}
    for folder in ['c64','drives','carts','configs','firmware','system']:
        assert (dest/folder/f'README-{folder}.txt').is_file()
    assert (dest/'README.txt').is_file()
    assert not (dest/'carts/eprom.bin').exists()
    assert not (dest/'drives/dos2031').exists()
    assert not list((dest/'c64').glob('dos*'))
    for line in (dest/'c64/bootstat.txt').read_text().splitlines():
        if line.startswith('fail,') and 'dos' in line:
            assert line.split(',')[1].startswith('/c64/dos')
    assert sorted(p.name for p in (dest/'configs').iterdir()) == ['README-configs.txt']
    assert (dest/'system/machines.txt').is_file()
    assert (dest/'system/network.cfg').is_file()
    assert not (dest/'profiles').exists()
    for p in dest.rglob('*'):
        if p.is_dir(): assert p.name == p.name.lower()
print('PASS: production lowercase ROM search, cartridge path and README policy; clean Main staging, six lowercase directories and ROM separation.')
