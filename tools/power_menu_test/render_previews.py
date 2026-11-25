#!/usr/bin/env python3
"""Host previews from production drawing calls and the existing C64 CHARGEN.
These are isolated dialog previews, not Raspberry Pi hardware screenshots.
"""
from pathlib import Path
import argparse,os,subprocess
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=root/'build/power-confirmations-review');args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
rom_path=root/'build/e64-install-review/c64/chargen'
if not rom_path.is_file():raise SystemExit('Existing C64 CHARGEN is unavailable; no substitute glyphs will be generated.')
rom=rom_path.read_bytes();assert len(rom)>=4096
palette=[tuple(int(x,16) for x in line.split()[:3]) for line in (root/'third_party/vice-3.3/data/C64/godot.vpl').read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
subprocess.run(['python3',str(root/'tools/menu_theme_test/run_tests.py')],cwd=root,env=os.environ|{'E64_POWER_PREVIEW_DRAW_DIR':str(out)},check=True)
def glyph(image,code,x,y,color,bank=0):
 bits=rom[bank+8*code:bank+8*code+8]
 for row,value in enumerate(bits):
  for col in range(8):
   if value&(128>>col):image.putpixel((x+col,y+row),palette[color])
for file in sorted(out.glob('*.draw')):
 image=Image.new('RGB',(320,240),palette[0]);draw=ImageDraw.Draw(image)
 for line in file.read_text().splitlines():
  kind,data=line.split(' ',1)
  if kind=='R':
   x,y,w,h,color,fill=map(int,data.split());draw.rectangle((x,y,x+w-1,y+h-1),fill=palette[color] if fill else None,outline=None if fill else palette[color])
  elif kind=='G':
   code,x,y,color=map(int,data.split());glyph(image,code,x,y,color)
  else:
   x,y,color,text=data.split(' ',3);x,y,color=int(x),int(y),int(color);heading=text in ('REBOOT','SHUTDOWN')
   for char in text:
    cp=ord(char);bank=0
    if char.isalpha():
     bank=0 if heading else 0x800
     cp=ord(char.upper())-65+1 if heading else ord(char)-97+1 if char.islower() else ord(char)
    glyph(image,cp,x,y,color,bank);x+=8
 image.save(out/(file.stem+'-native.png'));image.resize((1280,960),Image.Resampling.NEAREST).save(out/(file.stem+'-4x.png'))
comparison=Image.new('RGB',(1280,480),palette[0])
for i,name in enumerate(['reboot-action','shutdown-action']):comparison.paste(Image.open(out/(name+'-native.png')).resize((640,480),Image.Resampling.NEAREST),(i*640,0))
comparison.save(out/'power-confirmations-comparison.png')
(out/'README.txt').write_text('Host-rendered isolated dialog previews, not Pi screenshots.\nGeometry/colors/glyph calls come from current production ui.c via its rendering harness.\nGlyph pixels use the existing C64 CHARGEN; palette uses the current Godot C64 palette.\nNative preview canvas: 320x240. Larger versions use nearest-neighbor magnification.\nPower content: 16x6 cells (128x48 pixels); outer frame: 18x8 cells (144x64 pixels).\nThe underlying live native menu is intentionally absent from these isolated previews.\n')
print('Host CHARGEN previews:',out)
