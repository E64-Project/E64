#!/usr/bin/env python3
"""Rebuild E64 VICE objects using headers from this tree only."""
from pathlib import Path
import subprocess,re
root=Path(__file__).resolve().parents[1]
import os
os.chdir(root)
# Rebuild changed translation units explicitly: the kernel Makefile links VICE
# archives but does not rebuild their members.
targets={'third_party/vice-3.3/src':['autostart.o','resources.o','main.o','keyboard.o'], 'third_party/vice-3.3/src/arch/raspi':['libarch.a'], 'third_party/vice-3.3/src/arch/raspi/c64':['libarch_c64.a'], 'third_party/vice-3.3/src/drive':['libdrive.a'], 'third_party/vice-3.3/src/drive/iecieee':['libdriveiecieee.a'], 'third_party/vice-3.3/src/drive/tcbm':['libdrivetcbm.a']}
for directory,objects in targets.items():
 p=Path(directory);s=(p/'Makefile').read_text();flags=re.search(r'^CFLAGS = (.*)$',s,re.M).group(1)
 subprocess.run(['make','-C',directory,'-j2','-o','Makefile','-o','config.h','CFLAGS='+flags,*objects],check=True)
