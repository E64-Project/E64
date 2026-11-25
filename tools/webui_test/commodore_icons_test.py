#!/usr/bin/env python3
"""Validate palette, text contrast and approved vector-icon geometry/rendering.
Rendering requires installed librsvg, Cairo and Pillow.
Optional --sheet writes a color/grayscale review artifact.
"""
from pathlib import Path
import re, itertools, json, argparse, hashlib, xml.etree.ElementTree as ET
from PIL import Image, ImageDraw
from svg_icon_render import CATEGORIES, SAFETY_MARGIN, TARGET_SPAN, render_svg, ink_bounds, on_black
ROOT=Path(__file__).resolve().parents[2]
css=(ROOT/'src/webui/assets/style.css').read_text()
variables=dict(re.findall(r'--([\w-]+):\s*([^;]+);',css.split('}',1)[0]))
def color(name):
 value=variables[name]
 return color(value[6:-1]) if value.startswith('var(--') else value.upper()
def lum(hexcolor):
 channels=[int(hexcolor[i:i+2],16)/255 for i in (1,3,5)]
 return sum(w*(c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4) for w,c in zip((.2126,.7152,.0722),channels))
def contrast(a,b):
 x,y=sorted((lum(a),lum(b)));return (y+.05)/(x+.05)
palette=[line.split() for line in (ROOT/'third_party/vice-3.3/data/C64/godot.vpl').read_text().splitlines() if line.strip() and not line.startswith('#')]
values=['#'+''.join(parts[:3]).upper() for parts in palette]
names=['black','white','red','cyan','purple','green','blue','yellow','orange','brown','light-red','dark-gray','medium-gray','light-green','light-blue','light-gray']
assert [color('c64-'+name) for name in names]==values
pairs=[('primary-text','page-background'),('primary-text','panel-background'),('primary-text','input-background'),('navigation-link','hover-background'),('page-heading','panel-background'),('section-heading','panel-background'),('c64-black','c64-orange'),('c64-white','selection-background'),('muted','panel-background'),('dim','panel-background')]
ratios={a+'/'+b:round(contrast(color(a),color(b)),2) for a,b in pairs}
assert all(n>=4.5 for n in ratios.values()),ratios

# The review-approved vector artwork is frozen independently of its placement.
# This catches changed colors, details, outlines or proportions, without
# retaining obsolete rectangle-only / exact 16-color artwork assumptions.
manifest=json.loads((ROOT/'tools/webui_test/icon_artwork_manifest.json').read_text())['icons']
assert set(manifest)=={name for name,_ in CATEGORIES}
def canonical(node):
 return [node.tag.split('}')[-1],sorted(node.attrib.items()),[canonical(child) for child in node]]
def uniform_transform(value):
 number=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)'
 match=re.fullmatch(r'translate\(('+number+r') ('+number+r')\) scale\(('+number+r')\) translate\(('+number+r') ('+number+r')\)',value)
 assert match,'Artwork must use one uniform scale and translations, never axis-specific scaling/stretching'
 tx,ty,scale,cx,cy=map(float,match.groups());assert (tx,ty)==(8,8) and scale>0
 return scale

def validate_geometry(svg):
 root=ET.fromstring(svg)
 assert root.attrib=={'width':'16','height':'16','viewBox':'0 0 16 16','shape-rendering':'geometricPrecision'}
 assert len(root)==1 and root[0].tag.endswith('}g') and set(root[0].attrib)=={'transform'}
 uniform_transform(root[0].attrib['transform'])
 for n in root.iter():
  assert n.tag.split('}')[-1] in {'svg','g','path','rect','circle','ellipse'},n.tag
  assert not any(k.split('}')[-1] in {'href','filter','clip-path','mask','style'} for k in n.attrib)
  assert n is root[0] or 'transform' not in n.attrib
 assert 'Gradient' not in svg
 return root

def painted_bounds(svg):
 box=ink_bounds(svg,640);left,top,right,bottom=box
 assert min(left,top,16-right,16-bottom)>=SAFETY_MARGIN-.025,box
 assert abs((left+right)/2-8)<=.025 and abs((top+bottom)/2-8)<=.025,box
 assert abs(max(right-left,bottom-top)-TARGET_SPAN)<=.025,box
 # Render an expanded viewport at the same pixel density. Any ink outside
 # the original canvas reveals hidden cropping of an outline, pin or detail.
 expanded=ET.fromstring(svg);expanded.set('width','18');expanded.set('height','18');expanded.set('viewBox','-1 -1 18 18')
 over=render_svg(ET.tostring(expanded),720);extent=over.getchannel('A').getbbox()
 assert extent and extent[0]>=40 and extent[1]>=40 and extent[2]<=680 and extent[3]<=680,('clipped artwork',extent)
 return box

masks={};pixels={};geometry={}
for name,_ in CATEGORIES:
 path=ROOT/'src/webui/assets/icons'/f'{name}.svg';svg=path.read_text();root=validate_geometry(svg)
 digest=hashlib.sha256(json.dumps([canonical(n) for n in root[0]],separators=(',',':')).encode()).hexdigest()
 assert digest==manifest[name]['artwork_sha256'],(name,'Approved shapes/colors/details changed')
 geometry[name]=painted_bounds(svg)
 image=on_black(render_svg(svg,32));assert image.size==(32,32);pixels[name]=image
 # Grayscale foreground recognition, not a text-contrast conformance claim.
 # The approved dark violet body remains visible at 1.5:1; semantic icon alt
 # labels provide the type independently. Exact approved colors are frozen above.
 mask=tuple(contrast('#%02X%02X%02X'%pixel,'#000000')>=1.5 for pixel in image.getdata())
 assert sum(mask)>=120,(name,'Insufficient visible shape area');masks[name]=mask
separation={a+'/'+b:sum(x!=y for x,y in zip(masks[a],masks[b])) for a,b in itertools.combinations(masks,2)}
assert min(separation.values())>=48,separation
gradient_selectors={'.tape-transports .btn[aria-pressed="true"], .tape-transports .btn:active:not(:disabled)', '.tape-transports .btn:hover', '.tape-transports .btn[aria-pressed="true"]:hover, .tape-transports .btn:active:not(:disabled):hover', '.rainbow','.datasette-panel','.tape-transports .btn','#tape-counter','.tape-readout .btn','.tape-readout .btn,.tape-help,.tape-load','.tape-readout .btn,.tape-help','#tape-counter > span'}
for selector,body in re.findall(r'([^{}]+)\{([^{}]*)\}',re.sub(r'/\*.*?\*/','',css,flags=re.S)):
 if 'linear-gradient' in body:
  assert selector.strip() in gradient_selectors,('Unexpected gradient outside approved branding/Datasette',selector)
# Negative controls: do not silently accept stretch or hidden viewport cropping.
try:uniform_transform('translate(8 8) scale(1.2 1.1) translate(-8 -8)')
except AssertionError:pass
else:raise AssertionError('Nonuniform stretch was accepted')
clipped='<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16"><rect width="16" height="16" fill="#FFFFFF" stroke="#000000" stroke-width="1"/></svg>'
try:painted_bounds(clipped)
except AssertionError:pass
else:raise AssertionError('Clipped outline was accepted')
# Separate overscan negative control exercises the hidden-clipping check itself.
expanded=ET.fromstring(clipped);expanded.set('width','18');expanded.set('height','18');expanded.set('viewBox','-1 -1 18 18')
over=render_svg(ET.tostring(expanded),720).getchannel('A').getbbox();assert over[0]<40 and over[2]>680
print('PASS: exact 16 Godot CSS colors; text contrast >=4.5:1; nine approved vector designs/colors unchanged; uniform scaling, centered maximal occupancy, full-outline/pin overscan safety; stretch/clipping negative controls; grayscale shape difference >=48 pixels (minimum '+str(min(separation.values()))+')')
parser=argparse.ArgumentParser();parser.add_argument('--sheet',type=Path);args=parser.parse_args()
if args.sheet:
 args.sheet.mkdir(parents=True,exist_ok=True);sheet=Image.new('RGB',(648,170),'#000000');draw=ImageDraw.Draw(sheet)
 for i,(name,image) in enumerate(pixels.items()):
  x=i*72;sheet.paste(image,(x,20));sheet.paste(image.resize((64,64),Image.Resampling.NEAREST),(x,58));sheet.paste(image.convert('L').convert('RGB'),(x,130));draw.text((x,2),name,fill='#EEEEEE')
 sheet.save(args.sheet/'icon-sheet.png');(args.sheet/'palette-icon-metrics.json').write_text(json.dumps({'text_contrast':ratios,'grayscale_shape_distances':separation,'rendered_bounds':geometry},indent=2)+'\n')
