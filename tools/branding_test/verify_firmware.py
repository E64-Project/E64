#!/usr/bin/env python3
"""Verify candidate asset table, archive linkage and preserved implementation bytes."""
from pathlib import Path
import struct,subprocess,hashlib,json
R=Path(__file__).resolve().parents[2];B=R/'build/E64-v1.0-branding-corrected-test'
s=(R/'build/E64-v1-filesystem-stage2a/verify_link.py').read_text();ns={'__file__':str(R/'build/E64-v1-filesystem-stage2a/verify_link.py')};exec(s[:s.index('exe=root/')],ns)
E=ns['ELF'];check=ns['check_function'];candidate=B/'E64-v1.0-branding-corrected-test.elf';approved=R/'build/E64-stage3a-2a/kernel8-32-E64-stage3a-2a.elf'
e=E(candidate);a=E(approved)
assert hashlib.sha256(approved.with_suffix('.img').read_bytes()).hexdigest()=='dcfd93751ad4abbbc3fb494cb9a9b021791d0fb094f81bdee7dcaab5873f27f6'
obj=R/'third_party/common/menu.o'
assert subprocess.check_output(['arm-none-eabi-ar','p',str(obj.parent/'libbmc64common.a'),'menu.o'])==obj.read_bytes()
check(obj,candidate,'bmc64_version_string')
check(obj,candidate,'ui_set_hotkeys') if 'ui_set_hotkeys' in E(obj).symbols else None
for p,names in [('src/viceapp.o',None),('src/webui/webui_assets.o',[])]:
 o=E(R/p)
 for name,(v,n,i,info) in o.symbols.items():
  if n and info&15==2 and (names is None or name in names) and name in e.symbols:check(R/p,candidate,name)
for p in ['src/new_io.o','src/sdcard/sd_fs_fatfs.o','src/sdcard/sd_fs_file.o','third_party/common/ui.o','third_party/common/kbd.o','src/configs/config_protection.o','src/configs/config_store.o','src/configs/config_boot.o','third_party/vice-3.3/src/arch/raspi/vice_api.o','third_party/vice-3.3/src/core/scsi.o']+['third_party/circle-stdlib/libs/circle/lib/usb/'+name+'.o' for name in ['usbmassdevice','usbhostcontroller','usbstandardhub','dwhcidevice','dwhcixferstagedata','usbrequest','dwhcixactqueue','dwhcicompletionqueue','usbsubmission']]+['third_party/circle-stdlib/libs/circle/addon/fatfs/ff.o','third_party/circle-stdlib/libs/circle/addon/fatfs/diskio.o']:
 o=E(R/p)
 for name,(v,n,i,info) in o.symbols.items():
  if info&15==2 and n and name in a.symbols:
   check(R/p,approved,name);check(R/p,candidate,name)
print('PASS approved USB, filesystem, configs, ROM, drive, CMD HD, hotkey and CHARGEN implementations match their original objects excluding relocation words')
def at(address,n):
 for sh in e.sections:
  if sh[1]!=8 and sh[3]<=address and address+n<=sh[3]+sh[5]:
   off=sh[4]+address-sh[3];return e.data[off:off+n]
 raise AssertionError(hex(address))
def cstr(address):
 out=b''
 for i in range(512):
  c=at(address+i,1)
  if c==b'\0':return out.decode()
  out+=c
 raise AssertionError('unterminated table string')
count=struct.unpack('<I',e.code('g_webui_asset_count'))[0]
table=e.code('g_webui_assets');assert len(table)==count*16
paths=[]
for i in range(count):
 path,mime,data,size=struct.unpack_from('<4I',table,i*16);path=cstr(path);paths.append(path)
 disk=R/'src/webui/assets'/('index.html' if path=='/' else path.lstrip('/'))
 assert disk.is_file(),path
 assert at(data,size)==disk.read_bytes(),path
 assert not any(t in path for t in ['.orig','.bak','.before-','.tmp','backups/'])
assert '/bmc64-heading.png' not in paths and '/favicon.png' not in paths
assert all('/icons/e64-'+str(n)+'.png' in paths for n in [16,32,48,180,192])
for s in [b'Enhanced 64 v1.0 (test)',b'1.0-branding-test',b'Enhanced 64 v%s',b'Built on BMC64 v5.2.6']:assert s in e.data,s
print('PASS',count,'linked asset routes match source byte-for-byte; no obsolete logo/favicon or backup routes; test identification linked')
subprocess.run(['arm-none-eabi-objcopy','-O','binary',str(candidate),str(B/'verified-image.bin')],check=True)
assert (B/'verified-image.bin').read_bytes()==candidate.with_suffix('.img').read_bytes();(B/'verified-image.bin').unlink()
end=e.symbols['_end'][0];assert end<0x1008000
print(subprocess.check_output(['arm-none-eabi-size',str(candidate)],text=True));print('STATIC SPAN',end-0x8000,'END',hex(end),'HEADROOM',0x1008000-end)
print('SHA256',hashlib.sha256(candidate.with_suffix('.img').read_bytes()).hexdigest())
