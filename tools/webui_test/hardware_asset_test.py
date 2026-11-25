#!/usr/bin/env python3
"""Check local asset references against source and the firmware asset table."""
from pathlib import Path
import re, xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];A=R/'src/webui/assets'
embedded=(R/'src/webui/webui_assets.c').read_text()
checked=set()
for p in A.rglob('*'):
 if p.suffix not in ['.js','.html','.css','.svg']:continue
 if any(x in p.name for x in ['.before-','.bak','.orig']):continue
 text=p.read_text()
 refs=re.findall(r'(?:src|href)=[\"\'](/[^\"\'#?]+\.(?:svg|png|json|js|css|ico))(?=["\'])',text)
 refs+=re.findall(r'url\([\"\']?(/[^)\"\']+)',text)
 if p.suffix=='.js':
  refs += ['/'+str((p.parent/x).relative_to(A)) for x in re.findall(r'from\s+[\"\'](\./[^\"\']+)',text)]
 for ref in refs:
  assert (A/ref.lstrip('/')).is_file(),(p,ref)
  assert '"'+ref+'",' in embedded,(p,ref)
  checked.add(ref)
root=ET.parse(A/'fan-switch.svg').getroot()
assert root.attrib['viewBox']=='0 0 820 470'
assert all(not e.tag.endswith('image') for e in root.iter())
print(f'PASS: {len(checked)} distinct static local asset/import paths resolve and are embedded; SVG parses and has no bitmap images')
