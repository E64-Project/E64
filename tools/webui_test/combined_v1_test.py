"""Exact authored Storage copy and cassette/fan wiring regression guards."""
from pathlib import Path
import re, xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[2];A=R/'src/webui/assets'
s=(A/'js/instructions.js').read_text();storage=s.split('  storage:')[1].split('  memory:')[0]
paragraphs=[re.sub('<[^>]*>','',x) for x in re.findall(r'<p[^>]*>(.*?)</p>',storage,re.S)]
assert paragraphs==[
'Do not connect external USB storage until E64 has finished booting.',
'The SD card normally holds the boot and system files for E64.',
'The USB volumes hold user files, games, and disk images.',
'Connected USB volumes will appear as USB1, USB2, and USB3.',
'If available, volume labels are displayed (i.e., USB1: VOLUME1).',
'Select a drive and open a folder.',
'Use Copy to create a copy of the file or folder, or Move to relocate the file or folder.',
'Upload sends files from your computer into the current folder on E64.',
'(You can also drag files into the currently open folder in File Manager.)',
'Download saves files from E64 to your computer.',
'Note: Folder downloads will be ZIP archives.',
'Commodore 64 programs tend to be extremely small.',
'A standard D64 image is 175 KB (171 KiB). In theory, a typical16 GB USB stick can hold close to 90,000 standard D64 images.',
'A reliable USB flash drive is more desirable than excessive capacity.',
'It is best to organize your files into directories, such as Games,Demos, and Utilities, to make large collections easier to navigate.']
assert 'Programs and image files' not in storage and 'table(' not in storage and '#/instructions/drives' not in storage
assert '3A supply is recommended.' in s and '2.5A supply' not in s
hardware=s.split('  hardware:')[1].split('  storage:')[0]
assert 'pin 4' not in hardware and 'pin 2 is' not in hardware
svg=(A/'fan-switch.svg').read_text();assert '5V pin 4' not in svg and 'before the supply branches' in svg
html=(A/'index.html').read_text();cassette=re.search(r'<g id="tape-cassette".*?</g>',html,re.S)[0]
body=re.search(r'<rect\b[^>]*\bwidth="([\d.]+)" height="([\d.]+)"',cassette)
assert body and abs(float(body[1])/float(body[2])-100/63.5)<1e-9
ET.parse(A/'fan-switch.svg')
print('PASS exact Storage paragraphs, removed format section/link, incoming fan supply, 3A text, and exact 100:63.5 cassette body')
