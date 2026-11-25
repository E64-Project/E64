"""Verify every embedded deployment byte against its source asset."""
from pathlib import Path
import re
root=Path(__file__).resolve().parents[2]
source=(root/'src/webui/webui_assets.c').read_text()
blobs={key:bytes(int(x,16) for x in re.findall(r'0x([0-9a-f]{2})',body)) for key,body in re.findall(r'static const unsigned char (asset_\d+)\[\] = \{(.*?)\};',source,re.S)}
entries=re.findall(r'\{ "(/[^\"]*)", "[^\"]+", (asset_\d+), (\d+) \}',source)
for path,key,size in entries:
    original=(root/'src/webui/assets'/('index.html' if path=='/' else path[1:])).read_bytes()
    assert blobs[key]==original,path
    assert len(original)==int(size),path
assert len(blobs)==47
print(f'PASS: all {len(blobs)} embedded assets match source bytes and declared lengths ({len(entries)} routes)')
