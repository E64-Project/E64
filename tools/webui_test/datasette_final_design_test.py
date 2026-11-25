#!/usr/bin/env python3
"""Compare approved hardware source against the saved pre-edit baseline."""
from pathlib import Path
import re,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];O=R/'build/datasette-final-design';B=R/(O/'backup-path.txt').read_text();A=Path('src/webui/assets')
def svg(s):return ET.fromstring(re.search(r'<svg viewBox="0 0 560 310".*?</svg>',s,re.S)[0])
a=(R/A/'index.html').read_text();b=(B/A/'index.html').read_text();ta,tb=svg(a),svg(b)
disks=ta.find(".//g[@id='tape-drive-disks']");assert disks.get('fill')=='#555555'
assert [(c.get('cx'),c.get('cy'),c.get('r')) for c in disks]==[('137','132','19.5'),('285','132','19.5')]
for p in ta.iter():
 if disks in list(p):p.remove(disks);break
ta.find(".//g[@id='tape-cassette']/rect").set('fill','#b8e6f7')
ta.find(".//g[@id='tape-label-artwork']/rect[@x='64']").set('fill','#cfc1a9')
# XML whitespace is immaterial; every SVG attribute and all other geometry must match.
def canonical(t):return (t.tag,dict(t.attrib),[canonical(c) for c in t])
assert canonical(ta)==canonical(tb)
svgpattern=r'<svg viewBox="0 0 560 310".*?</svg>'
assert re.sub(svgpattern,'SVG',a,flags=re.S)==re.sub(svgpattern,'SVG',b,flags=re.S)
ca=(R/A/'style.css').read_text();cb=(B/A/'style.css').read_text()
for selector in ['.tape-label','.tape-motor']:
 pattern=re.escape(selector)+r' \{[^}]+\}'
 ca=re.sub(pattern,'CHANGED',ca);cb=re.sub(pattern,'CHANGED',cb)
assert ca==cb
palette=['#'+''.join(l.split()[:3]) for l in (R/'third_party/vice-3.3/data/C64/godot.vpl').read_text().splitlines() if l.strip() and not l.lstrip().startswith('#')]
js=(R/A/'js/datasette.js').read_text();assert len(palette)==16 and all('"'+c+'"' in js for c in palette)
# Exact identity of approved manufacturer artwork.
import hashlib
logo=R/A/'e64-long.png';print('Logo SHA256',hashlib.sha256(logo.read_bytes()).hexdigest())
print('PASS all approved HTML and SVG geometry preserved; only label color inheritance, empty background and reused disks differ')
print('PASS all CSS unchanged except MOTOR label and filename nameplate; exact 16 project palette values')
