#!/usr/bin/env python3
"""Exercise global fan preferences across host processes using the real SD API.
Only a disposable /tmp folder is used, never a mounted card.
"""
from pathlib import Path
import tempfile, subprocess, os
R=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='e64-fan-prefs-') as name:
 t=Path(name);card=t/'mock-card';card.mkdir();(card/'system').mkdir()
 source=t/'test.c';source.write_text(r'''
#include "fan_control.h"
#include <assert.h>
int main(int argc,char**argv){
 FanSettings p;
 if(argc==1){p=(FanSettings){1,63,48};assert(!fan_prefs_save(&p));}
 else {assert(!fan_prefs_load(&p));assert(p.enabled==1&&p.on_c==63&&p.off_c==48);}
 return 0;
}
''')
 binary=t/'test'
 subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Isrc',str(source),'src/fan_control.c','src/sdcard/sd_fs_file.c','tools/sdcard/sd_fs_posix.c','-o',str(binary)],cwd=R,check=True)
 env={**os.environ,'SD_TEST_ROOT':str(card)}
 subprocess.run([str(binary)],env=env,check=True)
 subprocess.run([str(binary),'read'],env=env,check=True)
 (card/'system/fan-prefs.txt').rename(card/'system/fan-prefs.txt.old')
 subprocess.run([str(binary),'recover'],env=env,check=True)
 assert (card/'system/fan-prefs.txt').read_text()=='fan_enabled=1\nfan_on_c=63\nfan_off_c=48\n'
 assert not (card/'configs').exists()
 print('PASS real global SD preference API: save, fresh-process reload, interrupted-rename recovery, exact bytes, no Config storage')
