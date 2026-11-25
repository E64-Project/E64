#!/usr/bin/env python3
"""Approved Datasette vector geometry and exact generated deployment bytes."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2]
A=R/'src/webui/assets'
html=(A/'index.html').read_text()
svg=re.search(r'<svg viewBox="0 0 560 310".*?</svg>',html,re.S)[0]
tree=ET.fromstring(svg)
assert tree.get('preserveAspectRatio','xMidYMid meet')=='xMidYMid meet'
cassette=tree.find(".//g[@id='tape-cassette']")
shell=cassette.find('rect')
assert abs(float(shell.get('width'))/float(shell.get('height'))-100/63.5)<.00001
assert shell.get('fill') is None # inherits the selected C64 label color
assert tree.find(".//g[@id='tape-spindles']") is not None
pins=tree.findall(".//g[@id='tape-spindles']/circle")
reels=tree.findall(".//g[@id='tape-reels']/use")
assert [(p.get('cx'),p.get('cy')) for p in pins]==[(p.get('x'),p.get('y')) for p in reels]
assert [float(p.get('cx')) for p in pins]==[137,285]
assert float(reels[1].get("x"))-float(reels[0].get("x"))==148
assert tree.find(".//clipPath[@id='orange-well']/rect").get('width')=='140'
hub=tree.find(".//g[@id='cassette-hub']")
assert [float(c.get('r')) for c in hub.findall('circle')]==[24,19.5] # 75% of 32/26
assert all(float(p.get('r'))==13.5 for p in pins)
assert tree.find(".//*[@id='tape-vents']") is None
assert [p.get('transform') for p in hub.findall('path')]==[f'rotate({a})' for a in range(0,360,60)]
assert tree.find(".//g[@id='tape-assembly']").get('transform')=='translate(0 16)'
assert 'scale(' not in svg and '<image' not in svg and '<text' not in svg
assert 'id="datasette-title"' not in html
assert 'class="datasette-panel" aria-label="Datasette"' in html
frame=tree.find(".//g[@id='tape-assembly']/rect")
assert abs(float(frame.get('y'))-79/3)<1e-10 and frame.get('height')=='306.5'
assert frame.get('x')=='7' and float(frame.get('x'))+float(frame.get('width'))==416
assert len(cassette.findall('rect'))==1 # Solid blue label, no label outlines.
assert hub.findall('circle')[1].get('fill')=='#555555'
assert len(hub.findall('path'))==6 and all(p.get('fill')=='#d3d3d3' for p in hub.findall('path'))
orange=tree.find(".//g[@transform='translate(0.5 35.666666666666667)']/rect")
half_stroke=float(orange.get('stroke-width'))/2
assert float(orange.get('y'))-half_stroke==132-24
assert float(orange.get('y'))+float(orange.get('height'))+half_stroke==132+24

css=(A/'style.css').read_text()
readout=re.search(r'\.tape-readout \{([^}]+)',css)[1]
assert '#tape-counter::after' not in css
assert '#tape-vents' not in css
assert float(frame.get('y'))+float(frame.get('height'))+16==322.5+79/3 # Bottom extended by half the original 29-unit status height.
window=tree.find(".//g[@id='tape-label-artwork']/rect")
assert [float(window.get(k)) for k in ('x','y','width','height','rx')]==[60,82,303,145,21]
border=tree.find(".//g[@id='tape-label-artwork']/rect[@x='64']")
blue=tree.find(".//clipPath[@id='cassette-well']/rect")
assert [float(border.get(k)) for k in ('y','height','rx','stroke-width')]==[86,137,20,7]
assert [float(blue.get(k)) for k in ('x','y','width','height','rx')]==[67.5,89.5,288,130,16.5]
silver=tree.find(".//clipPath[@id='upper-silver-frame']/rect")
assert [float(silver.get(k)) for k in ('x','y','width','height')]==[25,44.33333333333333,373,16.16666666666667]
# The black stroke begins exactly at the preserved silver overlap's lower edge.
assert float(border.get('y'))-22-float(border.get('stroke-width'))/2==18+42.5 # Original upper rim geometry preserved; group alone moves.
assert 67.5-25==398-(67.5+288)==42.5
# Lower edges and tape coordinates stay fixed while only the window top changes.
assert float(blue.get('y'))+float(blue.get('height'))==219.5
assert float(border.get('y'))+float(border.get('height'))==223
label=re.search(r'\.tape-label \{([^}]+)',css)[1]
assert all(rule in label for rule in ['left:16.3392857143%','top:calc(100% * 109.25 / 310)','width:42.8571428571%','text-align:center','font:bold 19px/1.4 monospace'])
assert 310*.29 > 16-22+float(blue.get('y'))
print('PASS restored rounded upper black border; exchanged upper/lower silver; side silver preserved; filename centered inside upper blue area')
assert 'left:78.075%' in readout and 'width:21%' in readout
assert 'bottom:calc(100% + 4px)' in css # Counter sits four pixels above RESET.
led=re.search(r'\.tape-motor span \{([^}]+)',css)[1]
assert all(rule in led for rule in ['width:19px','height:19px','aspect-ratio:1','flex:0 0 19px','box-sizing:border-box','border-radius:50%'])
c=(R/'src/webui/webui_assets.c').read_text()
for route,source in [('/index.html','index.html'),('/style.css','style.css'),('/js/datasette.js','js/datasette.js')]:
 entry=re.search(r'\{ "'+re.escape(route)+r'", "[^"]+", (asset_\d+), (\d+) \}',c)
 body=re.search(r'static const unsigned char '+entry[1]+r'\[\] = \{(.*?)\};',c,re.S)[1]
 data=bytes(int(x,16) for x in re.findall(r'0x([0-9a-f]{2})',body))
 expected=(A/source).read_bytes()
 assert data[:int(entry[2])]==expected
 assert int(entry[2])==len(expected)
print(f'PASS vector geometry, true 100:63.5 cassette, blue label, shared pin coordinates and occlusion, no raster/static readouts; SVG {len(svg.encode())} bytes; 3 generated assets match source exactly')

status=tree.find(".//g[@id='tape-assembly']/rect[@fill='#070707']")
assert [float(status.get(k)) for k in ('x','y','width','height')]==[20,285.3333333333333,383,34.5]
# Visible lower silver: door ends at 250; inner white rim ends at 302.5.
# Side rim inner edges are 11 and 412; status stroke is one unit wide.
assert abs(float(status.get('y'))-.5-(250+79/3)-8.5)<1e-10
assert abs((302.5+79/3)-(float(status.get('y'))+34.5+.5)-8.5)<1e-10
assert float(status.get('rx'))==float(status.get('height'))/2 and status.get('fill')=='#070707' and status.get('stroke')=='#eee'
assert tree.find(".//clipPath[@id='orange-well']/rect").get('x')=='141'
assert 'left:3.5714285714%' in css and 'top:97.2043010753%' in css and 'width:68.3928571429%' in css and 'height:11.1290322581%' in css
assert 'align-items:center; justify-content:center' in css
print('PASS centered status: equal 8.5-unit visible silver centerline margins, stroke accounted for; semicircular status ends and frame preserved')

# Complete outer tape border moves rigidly inside the silver compartment.
art=tree.find(".//g[@id='tape-label-artwork']")
dy=float(re.search(r'translate\(0 ([^)]+)',art.get('transform'))[1])
outer=art.find('rect')
top=float(outer.get('y'))+dy-1-(18+79/3)
bottom=(244+79/3)-(float(outer.get('y'))+float(outer.get('height'))+dy+1)
assert abs(bottom-top*2)<1e-10
print(f'PASS complete tape clearance: top {top}, bottom {bottom} SVG units, ratio {bottom/top}')

# Measure stroke-inclusive orange and reel bounds against the outer black frame opening.
shift_x,shift_y=.5,35.666666666666667
bounds=(min(137-24,141-half_stroke)+shift_x, min(132-24,109.5-half_stroke)+shift_y,
        max(285+24,141+140+half_stroke)+shift_x, max(132+24,109.5+45+half_stroke)+shift_y)
opening=tree.find(".//g[@id='tape-assembly']/rect[@x='25']")
center=((bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2+dy+16)
frame_center=(float(opening.get('x'))+float(opening.get('width'))/2,float(opening.get('y'))+float(opening.get('height'))/2+16)
assert all(abs(a-b)<1e-10 for a,b in zip(center,frame_center))
assert bounds[0]>=67.5 and bounds[2]<=355.5 and bounds[1]>=89.5 and bounds[3]<=219.5
print(f'PASS full tape visible bounds {bounds}; drawing center {center}; outer black frame opening center {frame_center}')
