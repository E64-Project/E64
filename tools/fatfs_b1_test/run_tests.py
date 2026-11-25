#!/usr/bin/env python3
"""Real FatFs + formatter-created FAT16/FAT32 volumes; all writes stay in host RAM."""
from pathlib import Path
import subprocess,tempfile,shutil
root=Path(__file__).resolve().parents[2];fat=root/'third_party/circle-stdlib/libs/circle/addon/fatfs'
formatter=shutil.which('mkfs.fat') or '/sbin/mkfs.fat'
with tempfile.TemporaryDirectory(prefix='e64-b1-') as name:
 t=Path(name);exe=t/'fatfs'
 command=['cc','-std=c11','-O2','-g','-Wall','-Wextra','-Werror','-Wno-overflow','-Wno-unused-function','-fsanitize=undefined','-DFF_SOURCE="'+str(fat/'ff.c')+'"','-I'+str(fat),str(Path(__file__).with_name('harness.c')),str(fat/'ffunicode.c'),'-o',str(exe)]
 subprocess.run(command,check=True)
 before=t/'before';old=root/'build/E64-stage2b-b1/before/third_party/circle-stdlib/libs/circle/addon/fatfs/ff.c'
 original=command.copy();original[original.index('-DFF_SOURCE=\"'+str(fat/'ff.c')+'\"')]='-DFF_SOURCE=\"'+str(old)+'\"';original[-1]=str(before);subprocess.run(original,check=True)
 count=0
 for bits,size,kind in [(16,32*1024*1024,2),(32,64*1024*1024,3)]:
  image=t/f'fat{bits}.img'
  with image.open('wb') as f:f.truncate(size)
  subprocess.run([formatter,'-F',str(bits),'-s','1',str(image)],check=True,stdout=subprocess.DEVNULL)
  modes=['success','primary','secondary','partial-secondary','sync','close-sync','directory','file-primary','file-secondary']+(['fsinfo','file-fsinfo'] if bits==32 else [])
  for mode in modes:subprocess.run([str(exe),str(image),str(kind),mode],check=True,timeout=30);count+=1
  baseline=subprocess.check_output([str(before),str(image),str(kind),'success'],text=True)
  corrected=subprocess.check_output([str(exe),str(image),str(kind),'success'],text=True)
  assert baseline==corrected,(baseline,corrected)
  print(f'PASS: FAT{bits} successful write trace and complete image digest unchanged versus original FatFs')
  for mode in ['secondary','sync']+(['fsinfo'] if bits==32 else []):
   r=subprocess.run([str(before),str(image),str(kind),mode],capture_output=True,text=True,timeout=30)
   assert r.returncode==-6 and 'Assertion' in r.stderr,(mode,r.returncode,r.stderr)
   print(f'PASS: pre-fix production FatFs reproduces FAT{bits} {mode} defect')
 print(f'PASS: {count} real FatFs metadata/retry scenarios; production configuration and Unicode code; no SD/USB access')
