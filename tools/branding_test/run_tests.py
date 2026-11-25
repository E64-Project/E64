#!/usr/bin/env python3
"""Final Web UI branding corrections, with an exact pre-edit preservation oracle."""
from pathlib import Path
import hashlib,json,re,importlib.util
from PIL import Image
R=Path(__file__).resolve().parents[2];B=R/'build/E64-v1.0-branding-corrected-test';A=R/'src/webui/assets'
count=0
def check(ok,message):
 global count
 assert ok,message
 count+=1
html=(A/'index.html').read_text();css=(A/'style.css').read_text();js=(A/'js/dashboard.js').read_text()
oldhtml=(B/'before/src/webui/assets/index.html').read_text();oldcss=(B/'before/src/webui/assets/style.css').read_text();oldjs=(B/'before/src/webui/assets/js/dashboard.js').read_text()
label='Enhanced 64 v1.0';tagline='Everything You Remember. More Than You Imagined.'
check(html.count('id="sidebar-version"')==1,'one sidebar identity label')
check(f'class="sidebar-version">{label}</span>' in html,'correct identity before first API response')
check('$("sidebar-version").textContent = "Enhanced 64 v1.0";' in js,'status updates preserve approved label')
check('s.version ? "v" + s.version' not in js,'no test suffix substituted into sidebar')
check(tagline in html and 'From Bare Metal to Beautiful' not in html,'official tagline')
check('width="400" height="110"' in re.search(r'<img class="sidebar-logo"[^>]*>',html)[0],'intrinsic artwork dimensions')
check('aspect-ratio: 347 / 79' not in css,'old letterbox ratio removed')
check('width: calc(100% + 16px); height: auto; align-self: center; flex-shrink: 0; object-fit: contain;' in css,'larger naturally proportional centered logo')
check('.sidebar-version { align-self: center; text-align: center;' in css,'centered label')
# Undo only approved changes; every other markup, style and behavior byte must match.
normalized=html.replace('alt="Enhanced 64" width="400" height="110"','alt="Enhanced 64" width="347" height="79"').replace(f'class="sidebar-version">{label}</span>','class="sidebar-version">—</span>').replace(tagline,'Enhanced 64 v1.0 — From Bare Metal to Beautiful')
check(normalized==oldhtml,'no other HTML changes')
normalized=css.replace('max-width: 208px; margin: 4px auto 15px; flex-shrink: 0;','max-width: 208px; margin: 4px auto 15px;').replace('.sidebar-logo { display: block; width: calc(100% + 16px); height: auto; align-self: center; flex-shrink: 0; object-fit: contain; }','.sidebar-logo { display: block; width: 100%; height: auto; aspect-ratio: 347 / 79; object-fit: contain; }').replace('.sidebar-version { align-self: center; text-align: center;','.sidebar-version { align-self: flex-end;')
check(normalized==oldcss,'all other CSS including tagline font/color/position unchanged')
check(js.replace('$("sidebar-version").textContent = "Enhanced 64 v1.0";','$("sidebar-version").textContent = s.version ? "v" + s.version : "—";')==oldjs,'status/network/drive behavior unchanged')
# At native desktop sizing: inner sidebar width=236-28 padding-1 border.
inner=207;old_art=inner*79/347*400/110;new_width=inner+16
check(new_width/old_art>1.29,'approximately 30 percent wider than previous fitted artwork')
check(new_width<236 and (236-new_width)/2>=6,'logo fits sidebar with centered side clearance')
check(new_width*110/400>inner*79/347,'height increases proportionally')
check('sidebar-motto' not in html+css,'removed rainbow card remains absent')
master=Image.open(B/'artwork/E64.png').convert('RGB')
check((A/'e64-long.png').read_bytes()==(B/'artwork/E64 - Long Logo.png').read_bytes(),'logo artwork unchanged')
for n in [16,32,48,180,192]:
 p=A/'icons'/f'e64-{n}.png';im=Image.open(p)
 check(im.size==(n,n),'icon dimensions '+str(n))
 check(im.convert('RGB').tobytes()==master.resize((n,n),Image.Resampling.LANCZOS).tobytes(),'favicon artwork unchanged '+str(n))
manifest=(A/'manifest.json').read_text()
for n in [16,32,48,180,192]:check(f'/icons/e64-{n}.png' in html+manifest,'icon reference retained '+str(n))
check('/favicon.png' not in html and '/bmc64-heading.png' not in html,'no obsolete artwork references')
check('Test Candidate</title>' in html,'test identification retained outside sidebar')
spec=importlib.util.spec_from_file_location('assets',R/'tools/gen_webui_assets.py');gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
check(all(not gen.is_backup_component(c) for p in gen.list_assets() for c in p.split('/')),'asset hygiene')
allowed=set(json.loads((B/'affected-files.json').read_text()))
for p,h in json.loads((B/'before-source-sha256.json').read_text()).items():
 if p not in allowed:check(hashlib.sha256((R/p).read_bytes()).hexdigest()==h,'unrelated source/asset unchanged '+p)
print(f'PASS {count} corrected-branding/layout/artwork/preservation checks')
