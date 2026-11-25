#!/usr/bin/env python3
"""Offline Firefox validation of production Help and unchanged Datasette geometry."""
from pathlib import Path
import json
# Reuse the existing offline asset embedding and Firefox screenshot runner.
exec((Path(__file__).with_name('datasette_final_browser_check.py')).read_text().split('results=[]\nfor w,h')[0])
O=R/'build/datasette-help-refinement';O.mkdir(parents=True,exist_ok=True)
before=(O/'before.css').read_text()
script=r'''
const commands=[];async function controlDatasette(action){commands.push(action);}
initDatasette();
document.querySelector('#view-dashboard').hidden=true;document.querySelector('#view-datasette').hidden=false;
const s={supported:1,attached:1,writable:1,filename:'USB:/tapes/Example.tap',counter:123,mode:0,motor:0,pending:0,serial:1};renderDatasette(s);
window.addEventListener('load',async()=>{
const panel=document.querySelector('.datasette-panel'),help=document.querySelector('#tape-help'),toggle=document.querySelector('#tape-help-toggle');
const rect=e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
const geometry=()=>[panel,...panel.querySelectorAll('*')].map(rect);
const original=document.querySelector('style').textContent;
document.querySelector('style').textContent=BEFORE;const baseline=geometry();document.querySelector('style').textContent=original;
const closed=geometry();toggle.click();const opened=geometry(),p=rect(panel),h=rect(help),sidebar=rect(document.querySelector('.sidebar'));
const same=(a,b)=>a.every((r,i)=>Object.keys(r).every(k=>Math.abs(r[k]-b[i][k])<.03));
const separate=(a,b)=>a.x+a.w<=b.x||b.x+b.w<=a.x||a.y+a.h<=b.y||b.y+b.h<=a.y;
const gap=h.y>=p.y+p.h?h.y-p.y-p.h:h.x-p.x-p.w;
const checks={geometryPreserved:same(baseline,closed)&&same(closed,opened),opens:!help.hidden&&toggle.getAttribute('aria-expanded')==='true',separate:separate(p,h),gap:gap>=24&&gap<=32,sidebar:separate(h,sidebar),bounds:h.x>=0&&h.x+h.w<=innerWidth,wrap:help.scrollWidth<=help.clientWidth,noHorizontalScroll:document.documentElement.scrollWidth<=innerWidth,width:innerWidth<500||Math.abs(h.w-450)<.1};
toggle.click();checks.closes=help.hidden&&toggle.getAttribute('aria-expanded')==='false';toggle.click();
for(const button of document.querySelectorAll('[data-tape-action]')){renderDatasette(s);button.click();await Promise.resolve();await Promise.resolve();}
checks.controls=['zero','record','play','rewind','forward','stop','eject'].every(action=>commands.includes(action));
renderDatasette({...s,attached:0});checks.ejectCounter=document.querySelector('#tape-counter').textContent==='000';renderDatasette(s);
checks.loadLink=document.querySelector('#tape-load').getAttribute('href')==='#/files';
const result={viewport:[innerWidth,innerHeight],panel:p,help:h,gap,checks,pass:Object.values(checks).every(Boolean)};
if(CLEAN){if(SCROLL)document.querySelector('#app').style.transform='translateY(-'+Math.max(0,h.y-20)+'px)';return;}
const bytes=new TextEncoder().encode(JSON.stringify(result));const canvas=document.createElement('canvas');canvas.width=innerWidth;canvas.height=128;canvas.style='position:fixed;left:0;top:0;z-index:999999';document.documentElement.append(canvas);const ctx=canvas.getContext('2d'),im=ctx.createImageData(innerWidth,128);[bytes.length>>8,bytes.length&255,...bytes].forEach((v,i)=>{im.data[i*4]=v;im.data[i*4+1]=80;im.data[i*4+2]=160;im.data[i*4+3]=255});ctx.putImageData(im,0,0);
});
'''
results=[]
for w,h in [(1920,1080),(1280,1024),(1280,900),(390,780)]:
 for clean,scroll,label in [(False,False,'metrics'),(True,False,'help-open'),(True,True,'help-text')]:
  js=script.replace('BEFORE',json.dumps(before)).replace('CLEAN',str(clean).lower()).replace('SCROLL',str(scroll).lower())
  page=O/f'{w}x{h}-{label}.html';shot=page.with_suffix('.png');shot.unlink(missing_ok=True)
  page.write_text(base.replace('</body>','<script>'+source+js+'</script></body>'))
  firefox(page.resolve(),shot.resolve(),w,h)
  if not clean:
   with Image.open(shot) as im:
    im=im.convert('RGB');data=[im.getpixel((x,y))[0] for y in range(128) for x in range(w)];n=data[0]*256+data[1];result=json.loads(bytes(data[2:2+n]))
   results.append(result);print(json.dumps(result),flush=True)
(O/'results.json').write_text(json.dumps(results,indent=2))
assert all(r['pass'] for r in results)
