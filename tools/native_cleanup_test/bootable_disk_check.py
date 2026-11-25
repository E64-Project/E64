#!/usr/bin/env python3
"""Real VICE CPU check: a disk program must execute, not merely attach.
Normal terminal: python3 tools/native_cleanup_test/bootable_disk_check.py
Requires a usable display, x64sc, c1541 and locally supplied legal C64 ROMs.
Optional: --rom-dir /path/containing/kernal/basic/chargen
Only temporary computer files are written. No SD access.
"""
from pathlib import Path
import argparse,subprocess,tempfile,shutil,json
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--rom-dir',type=Path);a=p.parse_args()
r=Path(__file__).resolve().parents[2];out=r/'build/config-management-disk-boot-check';out.mkdir(exist_ok=True)
if not shutil.which('x64sc') or not shutil.which('c1541'):raise SystemExit('BLOCKED: x64sc and c1541 required')
with tempfile.TemporaryDirectory(prefix='e64-disk-run-') as tmp:
 d=Path(tmp);prg=d/'executed.prg';disk=d/'boot.d64'
 # 10 SYS2061; machine code writes exit code 37 to the VICE debug cartridge.
 prg.write_bytes(bytes([1,8,11,8,10,0,0x9e])+b'2061'+bytes([0,0,0,0xa9,37,0x8d,0xff,0xd7,0x4c,0x0d,8]))
 subprocess.run(['c1541','-format','E64 RUN TEST,01','d64',str(disk),'-write',str(prg),'RUNTEST'],check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 base=['x64sc','-default','-console','+sound','-warp','-debugcart','-limitcycles','20000000']
 if a.rom_dir:
  for option,name in [('kernal','kernal'),('basic','basic'),('chargen','chargen')]:base+=['-'+option,str(a.rom_dir/name)]
 results=[]
 for name,arg in [('autostart','-autostart'),('attach-only','-8')]:
  try:
   run=subprocess.run(base+[arg,str(disk)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90)
   (out/(name+'.log')).write_text(run.stdout);results.append({'case':name,'exit_code':run.returncode})
  except subprocess.TimeoutExpired as e:
   results.append({'case':name,'timeout':True});continue
 (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 if results[0].get('exit_code')!=37:
  print('BLOCKED/FAIL: program execution not verified; inspect '+str(out));raise SystemExit(2)
 if results[1].get('exit_code')==37:raise SystemExit('FAIL: attach-only unexpectedly executed the program')
 print('PASS: disk autostart executed BASIC/SYS program (debug-cart exit37); attachment alone did not')
