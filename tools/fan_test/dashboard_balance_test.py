#!/usr/bin/env python3
"""Offline Firefox production dashboard geometry at the two requested desktop sizes.
No server, device, mobile emulation, or firmware installation.
"""
from pathlib import Path
import subprocess, tempfile, re, json, sys, os, time
from PIL import Image
R=Path(__file__).resolve().parents[2]
out=Path(sys.argv[1]) if len(sys.argv)>1 else R/'build/dashboard-balance'
out=out.resolve();out.mkdir(parents=True,exist_ok=True)
assets=R/'src/webui/assets';html=(assets/'index.html').read_text();css=(assets/'style.css').read_text()
html=re.sub(r'<script\b.*?</script>','',html,flags=re.S)
html=re.sub(r'<link\b[^>]*>','',html)
html=html.replace('</head>','<style id="production-css">'+css+'</style></head>')
html=re.sub(r'(src=")/([^\"]+)',lambda m:m[1]+(assets/m[2]).as_uri(),html)
js=r'''
for(const meter of document.querySelectorAll('#view-dashboard .meter')) meter.hidden=false;
for(const el of document.querySelectorAll('#view-dashboard dd[id]')) if(el.textContent.trim()==='—')el.textContent='Disabled';
for(const el of document.querySelectorAll('.bar-fill'))el.style.width='45%';
document.querySelector('#d-temp').textContent='52 °C';
for(const id of ['d-storage-txt','d-usb-storage-txt','d-usb2-storage-txt','d-usb3-storage-txt'])document.getElementById(id).textContent='450 MB / 1 GB';
const panels=[...document.querySelectorAll('#view-dashboard .grid > .card')];
const storage=document.querySelector('#view-dashboard .storage-card');
const hardware=panels[2],system=panels[1];
const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,b:r.bottom};};
const [quick,info,hw]=panels.map(rect), volume=rect(storage);
const fields=card=>[...card.querySelectorAll('dt')].map(e=>e.textContent);
const headings=[...panels,storage].map(e=>e.querySelector('h2').lastChild.textContent);
const swap=rect(document.querySelector('#qa-swap')),disable=rect(document.querySelector('#qa-disable'));
const checks={
 panelOrder:headings.join('|')==='Quick Actions|System Information|Hardware Status|Storage',
 systemFields:fields(system).join('|')==='REU Size|REU State|Warp Mode|IEEE-488|Drive 8|Drive 9|Drive 10|Drive 11',
 hardwareFields:fields(hardware).join('|')==='Low Voltage|Low Voltage Since Boot|CPU Throttling|CPU Throttled Since Boot|Virtual Modem Address|User Port/FTDI RS-232|Audio Output',
 temperature:hardware.querySelector('#d-tempmeter').contains(document.querySelector('#d-temp-bar')),
 fanIndicatorOnly:hardware.contains(document.querySelector('#d-fan'))&&!hardware.querySelector('form,input,select,button'),
 storagePlacement:storage.querySelectorAll('.meter[id$="storage"]').length===4&&document.querySelectorAll('.meter[id$="storage"]').length===4,
 topRow:quick.y===info.y&&info.y===hw.y&&quick.b===info.b&&info.b===hw.b&&quick.x+quick.w<info.x&&info.x+info.w<hw.x,
 fullWidth:volume.y>hw.b&&volume.x===quick.x&&Math.abs(volume.x+volume.w-hw.x-hw.w)<.1,
 swapTileMatches:Math.abs(swap.w-disable.w)<.1&&Math.abs(swap.h-disable.h)<.1,
 swapBesideDisable:getComputedStyle(document.querySelector('.tiles')).gridTemplateColumns.split(' ').length!==3||Math.abs(swap.y-disable.y)<.1,
 noPanelOverflow:[...panels,storage].every(e=>e.scrollHeight<=e.clientHeight&&e.scrollWidth<=e.clientWidth),
 withinViewport:volume.b<innerHeight&&volume.x+volume.w<=innerWidth
};
const result={viewport:[innerWidth,innerHeight],panels:[quick,info,hw,volume],checks,pass:Object.values(checks).every(Boolean)};
const bytes=new TextEncoder().encode(JSON.stringify(result));
const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=2;canvas.style='position:fixed;bottom:0;left:0;z-index:999999;width:1024px;height:2px';document.body.append(canvas);
const ctx=canvas.getContext('2d'),img=ctx.createImageData(1024,2);let data=[bytes.length>>8,bytes.length&255,...bytes];data.forEach((v,i)=>{img.data[i*4]=v;img.data[i*4+1]=80;img.data[i*4+2]=160;img.data[i*4+3]=255});ctx.putImageData(img,0,0);
'''
html=html.replace('</body>','<script>'+js+'</script></body>')
page=out/'dashboard-offline.html';page.write_text(html)
results=[]
for w,h in [(1280,1024),(1280,900),(1920,1024)]:
 with tempfile.TemporaryDirectory(prefix='e64-dashboard-firefox-') as profile:
  shot=out/f'dashboard-{w}x{h}.png'
  shot.unlink(missing_ok=True)
  with (out/f'firefox-{w}x{h}.log').open('w') as log:
   p=subprocess.Popen(['firefox','--headless','--no-remote','--profile',profile,'--window-size',f'{w},{h}','--screenshot',str(shot),page.resolve().as_uri()],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,MOZ_DISABLE_CONTENT_SANDBOX='1',MOZ_CRASHREPORTER_DISABLE='1'))
   try:
    for attempt in range(200):
     if shot.exists():
      try:
       with Image.open(shot) as check: check.load()
       break
      except OSError: pass
     if p.poll() is not None: raise RuntimeError('Firefox exited before screenshot')
     time.sleep(.1)
    else: raise RuntimeError('Firefox screenshot timeout')
   finally:
    if p.poll() is None:
     p.terminate()
     try:p.wait(timeout=3)
     except subprocess.TimeoutExpired:p.kill();p.wait()
  im=Image.open(shot).convert('RGB');values=[im.getpixel((x,y))[0] for y in [h-2,h-1] for x in range(1024)];n=values[0]*256+values[1]
  result=json.loads(bytes(values[2:2+n]));results.append(result);print(json.dumps(result),flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2))
assert all(x['pass'] for x in results)
