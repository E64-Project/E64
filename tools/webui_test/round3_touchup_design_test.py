#!/usr/bin/env python3
"""Source contracts and real artwork bounds; rendered geometry is checked by Firefox."""
from pathlib import Path
from PIL import Image
import re
R=Path(__file__).resolve().parents[2];A=R/'src/webui/assets'
css=(A/'style.css').read_text();html=(A/'index.html').read_text();js=(A/'js/instructions.js').read_text()
for text in ['CRSR Keys','RETURN','← Key','HOME','↑ Key']:
 assert f'<strong>{text}</strong>' in js,text
for text in ['Move Up and Down through menu items.','Selects an item or opens a menu.','Exits the menu.','Closes all expanded menus and returns to the Main Menu.','Closes only the current submenu section.<br>Other menu sections will stay as they are.','Note: This is the up-arrow character key, not the cursor-up key.','<span>Hold down the</span> ${commodore} <span>key during boot to load the Default Profile</span>']:
 assert text in js,text
assert 'including its expanded children' not in js
assert 'grid-template-columns:max-content max-content minmax(0,1fr)' in css
assert 'navigation-note-slot' in js and 'append(navigationNote)' in js
assert 'storage: ["Storage"' in js
for text in ['Do not connect external USB storage until E64 has finished booting.','Leave the boot SD card installed.','permanently installed internal USB drive','ZIP archives']:
 assert text in js.replace('<br>', ''),text
assert 'border:5px solid #FF0000; background:#FFFFFF' in css
assert 'ctx.fillStyle = "#0000FF"' in (A/'js/logo.js').read_text()
# The actual PNG differs from the HTML's legacy width/height attributes. The
# containing block now follows its intrinsic aspect ratio, not the button box.
im=Image.open(A/'e64-long.png').convert('RGBA');assert im.size==(1602,960)
assert im.crop((0,550,1602,960)).getbbox()==(26,32,1576,384)
for rule in ['aspect-ratio:1602 / 960','left:calc(100% * 26 / 1602)','top:60.625%','width:calc(100% * 1550 / 1602)','height:calc(100% * 352 / 960)']:
 assert rule in css,rule
assert '.logo-toggle:hover { outline:0; box-shadow:none; }' in css
assert '.logo-toggle:focus-visible' in css
# E64 size and header cell height remain identical to Round 3.
assert 'width:70px; height:23.5px' in css
assert '.instructions .hotkeys-table th { height:68px; background:black; }' in css
assert 'width:min(700px, 94vw); padding-bottom:45px' in css
assert 'height:min(590px, 88dvh)' in css
assert 'width:174px; min-width:174px; flex:0 0 174px' in css
bar=html.split('<div class="fb-bar">')[1].split('</div>')[0];assert 'fb-crumbs' not in bar
assert '<div class="fb-info"><div class="crumbs" id="fb-crumbs"></div>' in html
assert html.index('id="fb-note"')<html.index('id="fb-status"')<html.index('class="fb-scroll"')
print('PASS: exact key wording/grid, annotation and Storage contracts, actual PNG rainbow bounds/full replacement, pure RGB colors, retained E64/header sizes and approved control geometry')

# Clipping removes every source pixel below y=582; the white E64 ends at y=521.
assert 'clip-path:inset(0 0 39.375% 0)' in css
assert 960 * (1 - .39375) == 582
white = [(x,y) for y in range(im.height) for x in range(im.width) if (lambda c:c[3]>0 and c[0]==c[1]==c[2] and c[0]>180)(im.getpixel((x,y)))]
assert max(y for x,y in white) < 582
assert im.crop((0,582,1602,960)).getbbox() == (26,0,1576,352)
print('PASS: original rainbow region fully excluded by active clipping; entire white E64 artwork remains above clip boundary; inactive state uses unchanged original PNG')
