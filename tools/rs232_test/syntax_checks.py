#!/usr/bin/env python3
"""Target compiler syntax/preprocessing checks only: no objects or firmware emitted."""
from pathlib import Path
import subprocess,re,tempfile
root=Path(__file__).resolve().parents[2]
v=root/'third_party/vice-3.3/src';c=root/'third_party/circle-stdlib/libs/circle'
includes=[root/'third_party/circle-stdlib/install/arm-none-circle/include',root/'third_party/circle-stdlib/include',c/'include',c/'addon',c/'addon/fatfs',c/'addon/vc4',c/'addon/vc4/interface/khronos/include',root/'third_party/common',v/'arch/raspi',v,root/'src']
# VICE uses machine-local include directories in its individual sub-Makefiles.
for makefile in [v/'c64/Makefile',v/'arch/raspi/Makefile']:
 text=makefile.read_text()
 block=re.search(r'^AM_CPPFLAGS = ((?:.*\\\n)*.*)',text,re.M).group(1)
 for relative in re.findall(r'-I\$\(top_(?:src|build)dir\)/([^\s\\]+)',block):
  includes.append(v.parent/relative)
args=['-DAARCH=32','-DRASPPI=3','-DRASPI_C64','-D__circle__','-DSTDLIB_SUPPORT=3','-D__VCCOREVER__=0x04000000','-U__unix__','-U__linux__','-march=armv8-a','-marm','-mfpu=neon-fp-armv8','-mfloat-abi=hard','-ffreestanding']
args+=['-I'+str(p) for p in includes]
cs=['c64/c64cia1.c','c64/c64cia2.c','rs232drv/rsuser.c','arch/raspi/vice_api.c']
for source in cs:
 subprocess.run(['arm-none-eabi-gcc','-fsyntax-only','-Werror=implicit-function-declaration',*args,str(v/source)],check=True,timeout=60)
 print('PASS C syntax:',source)
for source in cs[:2]:
 text=subprocess.check_output(['arm-none-eabi-gcc','-E',*args,str(v/source)],text=True,timeout=60)
 assert ('rsuser_tx_byte(byte)' in text) if 'cia1' in source else ('rsuser_read_ctrl(byte)' in text and 'rsuser_set_tx_bit' in text and 'rsuser_write_ctrl(byte)' in text)
 print('PASS BMC-only CIA preprocessed hooks:',source)
cpps=[root/'src/rs232_usb.cpp',root/'src/rs232_usb_bridge.cpp',root/'src/kernel.cpp']
cpps += [c/('lib/usb/'+n+'.cpp') for n in ['usbserial','usbserialhost','usbserialft231x','usbrequest','dwhcidevice']]
# The repository sysconfig defines multicore itself. -D alone cannot select
# the opposite mode: include it once, then explicitly undef for the single-core
# syntax pass, and verify the effective preprocessor state in each pass.
with tempfile.TemporaryDirectory(prefix='rs232-syntax-') as directory:
 single=Path(directory)/'single_core.h'
 single.write_text('#include <circle/sysconfig.h>\n#undef ARM_ALLOW_MULTI_CORE\n')
 for multi in (False,True):
  mode=['-include','circle/sysconfig.h'] if multi else ['-include',str(single)]
  flags=['-std=c++17','-fno-exceptions','-fno-rtti','-I'+str(c/'include'),*args,*mode]
  macros=subprocess.check_output(['arm-none-eabi-g++','-dM','-E','-x','c++',*flags,'/dev/null'],text=True)
  assert ('#define ARM_ALLOW_MULTI_CORE' in macros)==multi
  for source in cpps:
   subprocess.run(['arm-none-eabi-g++','-fsyntax-only',*flags,str(source)],check=True,timeout=60)
   print('PASS C++ syntax:',source.relative_to(root),'effective_multicore='+str(multi))
print('PASS: target syntax only; no object, archive, ELF or firmware image built')
