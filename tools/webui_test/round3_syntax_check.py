#!/usr/bin/env python3
"""ARM target parsing only; no object files, libraries, linking or firmware."""
from pathlib import Path
import subprocess
R=Path(__file__).resolve().parents[2]

circle='third_party/circle-stdlib/libs/circle'
flags=['-fsyntax-only','-mcpu=cortex-a53','-marm','-mfpu=neon-fp-armv8','-mfloat-abi=hard','-DAARCH=32','-DRASPPI=3','-D__circle__','-DRASPI_C64','-DSTDLIB_SUPPORT=3','-DKERNEL_MAX_SIZE=0x1000000']
# Match the application Rules.mk ordering so Circle's extended assert is used.
includes=[circle+'/include',circle+'/addon','third_party/circle-stdlib/install/arm-none-circle/include','third_party/circle-stdlib/include','third_party/vice-3.3/src','third_party/vice-3.3/src/arch/raspi','third_party/common',circle+'/addon/fatfs','third_party/zlib']
includes += ['third_party/vice-3.3/src/'+x for x in ['drive','c64','c64/cart','c64dtv','c128','vic20','pet','cbm2','plus4','raster','rs232drv','samplerdrv','sid','userport','vdrive','video','lib/p64','platform','joyport','gfxoutputdrv','tapeport','imagecontents']]
flags += ['-I'+x for x in includes]
checks=[('g++',['-std=gnu++17','-fno-exceptions','-fno-rtti'],['src/webui/webui_fs.cpp','src/webui/webui.cpp']),('gcc',['-std=gnu99'],['src/sdcard/sd_fs_fatfs.c',circle+'/addon/fatfs/ff.c']),('gcc',['-std=gnu99'],['third_party/common/ui.c']),('gcc',['-std=gnu99','-DHAVE_CONFIG_H'],['third_party/vice-3.3/src/arch/raspi/vice_api.c'])]
for compiler,extra,paths in checks:
 subprocess.run(['arm-none-eabi-'+compiler,*flags,*extra,*paths],cwd=R,check=True)
 print('PASS ARM -fsyntax-only: '+', '.join(paths),flush=True)
