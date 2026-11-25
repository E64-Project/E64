#!/usr/bin/env python3
"""Offline Firefox checks of production Hardware Help, desktop only."""
from pathlib import Path
import re, json, os, subprocess, tempfile, time
from PIL import Image
R=Path(__file__).resolve().parents[2]
A=R/'src/webui/assets'
out=R/'build/final-visual-20261112-013819/hardware';out.mkdir(parents=True,exist_ok=True)
html=(A/'index.html').read_text()
html=re.sub(r'<script\b.*?</script>','',html,flags=re.S)
html=re.sub(r'<link\b[^>]*>','',html)
html=html.replace('</head>','<style>'+(A/'style.css').read_text()+'</style></head>')
# Production functions, offline: no API, firmware or device access.
js=(A/'js/instructions.js').read_text()
js=re.sub(r'^import .*?;\n','',js,flags=re.M).replace('export function','function')
js='window.onerror=(m)=>{document.body.innerHTML=String(m);};function closeJiffyCommands(){};function openJiffyCommands(){};\n'+(A/'js/help_dialog.js').read_text().replace('export function','function')+'\n'+js
js+=r'''
 document.querySelector('#view-dashboard').hidden=true;
 document.querySelector('#view-instructions').hidden=false;
 showInstructions();
 const navigation=document.querySelector('#instructions-index');
 const hardwareLink=[...navigation.children].find(a=>a.textContent==='Hardware');
 const routeOK=hardwareLink?.getAttribute('href')==='#/instructions/hardware';
 showInstructions('hardware');
 const popup=document.querySelector('#instructions-popup');
 const image=popup.querySelector('.hardware-schematic img');
 image.src=SCHEMATIC;
 window.addEventListener('load',()=>{
 const finish=()=>{
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
 const r=rect(popup),i=rect(image);
 popup.scrollTop=0;
 const top=popup.scrollTop===0;
 popup.scrollTop=popup.scrollHeight;
 const bottom=popup.scrollTop>0&&popup.scrollTop+popup.clientHeight>=popup.scrollHeight-2;
 const checks={routeOK,title:document.querySelector('#instructions-title').textContent==='Hardware',open:popup.open,withinViewport:r.x>=0&&r.y>=0&&r.x+r.w<=innerWidth&&r.y+r.h<=innerHeight,noHorizontalOverflow:popup.scrollWidth<=popup.clientWidth,partsAligned:new Set([...popup.querySelectorAll('.fan-parts dd')].map(e=>e.getBoundingClientRect().left)).size===1,balancedGap:Math.abs(parseFloat(getComputedStyle(popup.querySelector('.hardware-schematic')).marginBottom)-parseFloat(getComputedStyle(popup.querySelector('.fan-circuit-heading')).marginBottom))<1,imageLoaded:image.complete&&image.naturalWidth>0,imageReadable:i.w>=800,topAccessible:top,bottomAccessible:bottom};
 if(PHASE==='schematic')popup.scrollTop=image.offsetTop-popup.offsetTop-85;
 else if(PHASE==='top')popup.scrollTop=0;
 else popup.scrollTop=popup.scrollHeight;
 const result={viewport:[innerWidth,innerHeight],phase:PHASE,popup:r,image:i,checks,pass:Object.values(checks).every(Boolean)};
 const bytes=new TextEncoder().encode(JSON.stringify(result));
 const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=2;canvas.style='position:fixed;bottom:0;left:0;z-index:999999;width:1024px;height:2px';document.body.append(canvas);
 const ctx=canvas.getContext('2d'),im=ctx.createImageData(1024,2);
 [bytes.length>>8,bytes.length&255,...bytes].forEach((v,i)=>{im.data[i*4]=v;im.data[i*4+1]=80;im.data[i*4+2]=160;im.data[i*4+3]=255});ctx.putImageData(im,0,0);
 };
 image.onload=finish;image.onerror=()=>{throw Error('Schematic failed to load');};
 if(image.complete&&image.naturalWidth)finish();
});
'''
js=js.replace('SCHEMATIC',json.dumps((A/'fan-switch.svg').as_uri()))
html=re.sub(r'(src=")/([^\"]+)',lambda m:m[1]+(A/m[2]).as_uri(),html)
results=[]
for w,h in [(1280,1024),(1280,900)]:
 for phase in ['top','schematic','bottom']:
  page=out/f'hardware-{w}x{h}-{phase}.html'
  page.write_text(html.replace('</body>','<script>'+js.replace('PHASE',json.dumps(phase))+'</script></body>'))
  shot=page.with_suffix('.png');shot.unlink(missing_ok=True)
  with tempfile.TemporaryDirectory(prefix='e64-hardware-firefox-') as profile:
   with page.with_suffix('.log').open('w') as log:
    p=subprocess.Popen(['firefox','--headless','--no-remote','--profile',profile,'--window-size',f'{w},{h}','--screenshot',str(shot),page.as_uri()],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,MOZ_DISABLE_CONTENT_SANDBOX='1',MOZ_CRASHREPORTER_DISABLE='1'))
    try:
     for _ in range(200):
      if shot.exists():
       try:
        with Image.open(shot) as im:im.load()
        break
       except OSError:pass
      if p.poll() is not None:raise RuntimeError('Firefox exited; see '+str(page.with_suffix('.log')))
      time.sleep(.1)
     else:raise RuntimeError('Firefox screenshot timeout')
    finally:
     if p.poll() is None:
      p.terminate()
      try:p.wait(timeout=3)
      except subprocess.TimeoutExpired:p.kill();p.wait()
  im=Image.open(shot).convert('RGB');data=[im.getpixel((x,y))[0] for y in [h-2,h-1] for x in range(1024)];n=data[0]*256+data[1]
  result=json.loads(bytes(data[2:2+n]));results.append(result);print(json.dumps(result),flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2))
assert all(r['pass'] for r in results)
