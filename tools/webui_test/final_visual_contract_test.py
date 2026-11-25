"""Verify schematic electrical nets and the approved visual specification."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
A=Path(__file__).resolve().parents[2]/'src/webui/assets'
root=ET.parse(A/'fan-switch.svg').getroot(); ns={'s':'http://www.w3.org/2000/svg'}
# Wires are open, axis-aligned strokes. Closed diode/arrow outlines and
# the transistor's base electrode belong to components, not electrical wires.
segments=[]
for path in root.findall('.//s:path',ns):
 for sub in re.findall(r'M[^M]+',path.attrib['d']):
  if 'Z' in sub: continue
  x=y=0
  for cmd,args in re.findall(r'([MHVL])([^MHVL]+)',sub):
   nums=list(map(float,re.findall(r'-?\d+(?:\.\d+)?',args)))
   if cmd=='M': x,y=nums;continue
   nx,ny=(nums[0],y) if cmd=='H' else (x,nums[0]) if cmd=='V' else nums
   if (x==nx or y==ny) and not (x==nx==490 and {y,ny}=={295,345}):segments.append(((x,y),(nx,ny)))
   x,y=nx,ny
ports=[[(240,65),(535,105),(635,130)],[(535,280),(535,185),(635,170)],[(240,320),(285,320)],[(345,320),(490,320),(395,350)],[(240,410),(535,365),(395,390)]]
points=set(p for seg in segments for p in seg)|set(p for net in ports for p in net)
parent={p:p for p in points}
def find(p):
 while parent[p]!=p:p=parent[p]
 return p
def on(p,a,b):return (a[0]==b[0]==p[0] and min(a[1],b[1])<=p[1]<=max(a[1],b[1])) or (a[1]==b[1]==p[1] and min(a[0],b[0])<=p[0]<=max(a[0],b[0]))
for a,b in segments:
 for p in points:
  if on(p,a,b):parent[find(p)]=find(a)
assert all(len({find(p) for p in net})==1 for net in ports), 'Disconnected circuit net'
assert len({find(net[0]) for net in ports})==5, 'Unintended short between circuit nets'
fan=root.find('.//s:circle[@id="fan"]',ns);upper=root.find('.//s:circle[@id="fan-upper-node"]',ns);lower=root.find('.//s:circle[@id="fan-lower-node"]',ns)
assert float(fan.get('cy'))==(float(upper.get('cy'))+float(lower.get('cy')))/2
assert float(fan.get('r'))==40
assert len({c.get('cx') for c in root.findall('.//s:circle[@class="input"]',ns)})==1
text=' '.join(root.itertext());assert 'pin 6' not in text and 'Ω' not in text
for label in ['+5 VDC','GPIO Pin 23','(3.3v control)','GND','R1','R2','B','C','E']:assert label in text
s=(A/'js/instructions.js').read_text();fm=s.split('<h4>File Manager</h4>')[1].split('<hr>')[0]
assert '<br>' not in fm and fm.count('<p>')==6
for value in ['470 Ω','10 kΩ','PN2222A / 2N2222A','1N4001','5V DC (150mA Max)']:assert '<dd>'+value+'</dd>' in s
print('PASS: five isolated electrical nets, fan/diode polarity wiring, base pull-down/emitter wiring, centered circular fan, aligned terminals, final parts and unbroken File Manager sentences')
