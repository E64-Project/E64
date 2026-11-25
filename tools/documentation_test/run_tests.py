#!/usr/bin/env python3
"""Audit E64 directory guides against production defaults and staged bytes."""
from pathlib import Path
import argparse,hashlib,json,re
parser=argparse.ArgumentParser()
parser.add_argument("--source-only", action="store_true", help="Audit current source guides without comparing an older review installation")
args=parser.parse_args()
ROOT=Path(__file__).resolve().parents[2]
folders=['c64','drives','carts','configs','firmware','system']
paths=['README.txt']+[f'{d}/README-{d}.txt' for d in folders]
texts={p:(ROOT/'sdcard'/p).read_text(encoding='ascii') for p in paths}
for p,s in texts.items():
 assert s.startswith('='*72+'\n E64 - Enhanced 64\n'),p
 assert s.endswith('\n') and '\t' not in s and '\r' not in s,p
 assert max(map(len,s.splitlines()))<=78,p
 assert '-'*72 in s and '/profiles' not in s,p
 assert not any(line.rstrip()!=line for line in s.splitlines()),p
 # Upstream names may occur only in explicit attribution.
 for line in s.splitlines():
  if 'BMC64' in line:assert 'upstream BMC64 5.2.6' in line
assert (ROOT/'README.txt').read_bytes()==(ROOT/'sdcard/README.txt').read_bytes()
for d in folders:assert '/'+d in texts['README.txt']
header=(ROOT/'src/configs/configs.h').read_text()
assert '#define CONFIGS_MAX_NAME_LEN 32' in header
assert 'CONFIGS_MAIN_NAME' not in header
assert '#define CONFIGS_FACTORY_NTSC "_factory-ntsc"' in header
config=texts['configs/README-configs.txt']
for term in ['32 UTF-8 bytes','Default NTSC','Default PAL','Start once','Save Settings','/E64SET.NEW','/E64SET.OLD']:assert term in config,term
for p in ['settings.txt','vice.ini','E64SET.NEW','E64SET.OLD','bootcode.bin','start.elf','fixup.dat','kernel8-32.img']:assert p in texts['README.txt']
assert 'Shift+C= for PAL' not in config
assert 'Shift+C= has no special recovery function' in config
assert 'Select protected Default PAL normally' in config
# Audit exact DOS defaults and sizes against the production headers/resources.
doc=texts['drives/README-drives.txt']
resources='\n'.join((ROOT/f'third_party/vice-3.3/src/drive/{kind}/{kind}-resources.c').read_text() for kind in ['iec','ieee'])
sizes=dict((n,int(v,16)) for n,v in re.findall(r'^#define\s+DRIVE_ROM(\w+)_SIZE\s+(0x[0-9A-Fa-f]+)',(ROOT/'third_party/vice-3.3/src/drive/driverom.h').read_text(),re.M))
names={'dos1541':'1541','d1541II':'1541II','dos1570':'1570','dos1571':'1571','dos1581':'1581','dos2000':'2000','dos4000':'4000','dosCMDHD':'CMDHD','dos2031':'2031','dos2040':'2040','dos3040':'3040','dos4040':'4040','dos1001':'1001'}
for name,key in names.items():
 assert '"'+name+'"' in resources,name
 assert re.search(r'^  '+name+r'\s+'+str(sizes[key])+r' bytes',doc,re.M),name
for name,key in [('JD-d1541II','1541II'),('JD-dos1571','1571'),('JD-dos1581','1581')]:
 assert re.search(r'^  '+name+r'\s+'+str(sizes[key])+r' bytes',doc,re.M)
assert '"/carts/eprom.bin"' in (ROOT/'third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c').read_text()
# Explicit migration facts include details absent from the prior staged notes.
for fact in ['v2.80','D2M directory/file writes','D4M directory/file writes','DHD operation','D64, D71, D81, D82 and G64','1570','8 or 10','not 9 or 11','JiffyDOS switching','full 8250']:assert fact in doc,fact
c64=texts['c64/README-c64.txt'];carts=texts['carts/README-carts.txt']
for suffix in ['Green-on-Black','LightBlue-on-Blue','LightGray-on-Blue','LightGreen-on-Black']:
 for prefix in ['kernal-','JD-kernal-']:assert prefix+suffix in c64
for name in ['basic','chargen','kernal','JD-kernal','rpi_pos.vkm','*.vkm','*.vpl','bootstat.txt']:assert name in c64
for fact in ['eprom.bin','4096 bytes','absolute path','restarts','not enabled by default']:assert fact in carts
assert 'network.cfg' in texts['system/README-system.txt']
assert "generated('c64/ROM-Notes.txt'" not in (ROOT/'tools/prepare_e64_install_review.py').read_text()
assert not (ROOT/'sdcard/c64/ROM-Notes.txt').exists()
assert (ROOT/'docs/upstream/README-BMC64.md').read_text().startswith('# BMC64\n')
# Optional complete stage audit; never write to the source or any stage here.
stage=ROOT/'build/e64-docs-review';audit=ROOT/'build/e64-docs-review-audit'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if stage.exists() and not args.source_only:
 assert not list(stage.rglob('ROM-Notes.txt'))
 for p in paths:assert (stage/p).read_bytes()==(ROOT/'sdcard'/p).read_bytes(),p
 manifest=dict((p,h) for h,p in (line.split('  ',1) for line in (audit/'SHA256SUMS.txt').read_text().splitlines()))
 assert {str(p.relative_to(stage)):sha(p) for p in stage.rglob('*') if p.is_file()}==manifest
 for name,key in names.items():assert (stage/'drives'/name).stat().st_size==sizes[key]
 for name,size in [('basic',8192),('chargen',4096),('kernal',8192)]:assert (stage/'c64'/name).stat().st_size in [size,size+2]
 for p in (stage/'c64').iterdir():
  if 'kernal' in p.name:assert p.name in c64 and p.stat().st_size in [8192,8194]
 for name in ['brcmfmac43455-sdio.bin','brcmfmac43455-sdio.txt','brcmfmac43455-sdio.clm_blob']:
  assert (stage/'firmware'/name).is_file() and name in texts['firmware/README-firmware.txt']
 assert (stage/'carts/eprom.bin').stat().st_size==4096
 assert sha(stage/'kernel8-32.img')==sha(ROOT/'kernel8-32.img')
 before=json.loads((audit/'source-stage.json').read_text())
 allowed=set(paths)|{'c64/ROM-Notes.txt','system/network-readme.txt','kernel8-32.img'}
 for p,h in before.items():
  if p not in allowed:assert manifest[p]==h,p
 print('PASS: complete revised stage inventory/hashes, documented ROM sizes, all ROM/map/credential/boot-setting/license bytes preserved')
print('PASS: seven ASCII E64 guides; formatting, names, production DOS defaults/sizes, Config bounds, root/recovery paths, migration facts and retired ROM-notes generator')
