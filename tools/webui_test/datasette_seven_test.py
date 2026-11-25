"""Focused source contracts for the seven approved Datasette refinements."""
from pathlib import Path
import re, xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];A=R/'src/webui/assets'
css=(A/'style.css').read_text();html=(A/'index.html').read_text()
svg=ET.fromstring(re.search(r'<svg viewBox="0 0 560 310".*?</svg>',html,re.S)[0])
outer=svg.find(".//g[@id='tape-label-artwork']/rect")
assert outer.get('stroke') is None and outer.get('fill')=='#bfc0c2'
assert [outer.get(k) for k in ('x','y','width','height','rx')]==['60','82','303','145','21']
assert svg.find(".//g[@id='tape-assembly']/rect[@fill='#070707']").get('stroke')=='#eee'
assert '--tape-control-radius:9px' in css
for selector in ['#tape-counter','.tape-readout .btn,.tape-help','.tape-motor']:
 body=re.search(re.escape(selector)+r' \{([^}]+)',css)[1]
 assert 'border-radius:var(--tape-control-radius)' in body
assert 'border-color:#00d5ff; outline:1px solid #163bff' in css
assert css.count('background:#D0CCC4')==2 and '#e8dbc4' not in css
key=re.search(r'\.tape-transports \.btn \{([^}]+)',css)[1]
assert 'linear-gradient(#606060 0%,#353535 48%,#191919 100%)' in key
assert 'inset -2px -3px 3px #080808' in key
assert 'mask-image:url("/e64-long.png")' in css and 'width:105%; aspect-ratio:1406 / 498' in css
assert '[data-recording="true"] > span:first-child { color:#ec241a;' in css
assert '[data-tape-action="record"] > span:first-child { color:#fff;' in css
assert not re.search(r'animation|transition',re.search(r'\.tape-transports \[data-tape-action="record"\].*?\n',css)[0])
backend=(R/'third_party/vice-3.3/src/arch/raspi/vice_api.c').read_text()
assert 'case DATASETTE_CONTROL_RECORD: s->mode = EMUX_TAPE_RECORD;' in backend
assert 's->motor = web_datasette_motor;' in backend
print('PASS seven Datasette source contracts: original logo, shared corners, stripe source, key-only shading, steady REC and uniform housing')

hover=re.search(r'\.tape-transports \.btn:hover \{([^}]+)',css)[1]
assert 'outline:1px solid #080808' in hover and 'border-color:#080808' in hover
assert 'linear-gradient(#686868 0%,#3d3d3d 48%,#212121 100%)' in hover
assert not re.search(r'transform|transition|animation|filter|width|height|padding|margin',hover)
assert css.index('.tape-transports .btn:focus-visible')>css.index('.tape-transports .btn:hover')
print('PASS transport hover: static near-black outline, modest brightening, no geometry/REC changes, later keyboard focus precedence')

active=re.search(r'\.tape-transports \.btn\[aria-pressed="true"\], \.tape-transports \.btn:active\(:not\(:disabled\)\) \{([^}]+)',css)
# State and momentary activation share the same solid, stationary surface.
active=next(body for selector,body in re.findall(r'([^{}]+)\{([^{}]*)\}',css) if '.tape-transports .btn[aria-pressed="true"],' in selector)
assert 'background:#000' in active and 'color:#fff' in active and 'box-shadow:none' in active
assert not re.search(r'transform|animation|transition|width|height',active)
print('PASS depressed keys: authoritative aria-pressed or momentary :active, solid black, white labels and stationary geometry')
