#!/usr/bin/env python3
"""Offline production-renderer checks in actual headless Firefox; no device access."""
from pathlib import Path
import re,json,os,subprocess,tempfile,time,base64
from PIL import Image,ImageChops
R=Path(__file__).resolve().parents[2];A=R/'src/webui/assets';out=R/'build/datasette-reel-animation';out.mkdir(exist_ok=True,parents=True)
checks=r'''
const checks={}; const check=(name,ok)=>{checks[name]=!!ok;};
visible=true;
const s={supported:1,attached:1,writable:1,filename:'USB:/test.tap',mode:0,motor:0,counter:0};
renderDatasette(s);check('stopped creates no animations',!reelAnimations);
renderDatasette({...s,mode:1,motor:1});
const original=[...reelAnimations];
check('two animations',original.length===2);
check('play forward',reelRate===1);
original.forEach(a=>{a.currentTime=600;});
const uses=[...document.querySelectorAll('#tape-reels use')];
check('Firefox correct origins',uses.every((u,i)=>getComputedStyle(u).transformOrigin===(i?'285px 132px':'137px 132px')));
check('quarter turn Firefox transform',uses.every(u=>{const m=new DOMMatrix(getComputedStyle(u).transform);return Math.abs(m.a)<.001&&Math.abs(m.b+1)<.001&&Math.abs(m.c-1)<.001&&Math.abs(m.d)<.001;}));
renderDatasette({...s,mode:1,motor:1});
check('poll preserves instances and angles',reelAnimations.every((a,i)=>a===original[i]&&Math.abs(a.currentTime-600)<1));
for(const [mode,motor,rate] of [[1,0,0],[2,1,1],[2,0,0],[4,1,4],[3,1,-4],[0,1,0]]) {
 renderDatasette({...s,mode,motor});check('mode '+mode+' motor '+motor,reelRate===rate);
 if(!rate)check('paused '+mode,original.every(a=>a.playState==='paused'));
}
renderDatasette({...s,mode:3,motor:1});check('reverse has time before zero',original.every(a=>a.currentTime>2400));
renderDatasette({...s,mode:1,motor:1,attached:0});check('eject',reelRate===0&&document.querySelector('#tape-reels').hasAttribute('hidden'));
renderDatasette({...s,mode:1,motor:1,filename:'another.tap'});check('reattach',reelRate===1&&!document.querySelector('#tape-reels').hasAttribute('hidden'));
fail(new Error('offline'));check('failure pauses',reelRate===0&&original.every(a=>a.playState==='paused'));
renderDatasette({...s,mode:1,motor:1});setDatasetteVisible(false);check('navigation pauses',reelRate===0);
visible=true;renderDatasette({...s,mode:1,motor:1});check('return reuses animations',reelAnimations.every((a,i)=>a===original[i])&&uses.every(u=>u.getAnimations().length===1));
for(const motor of [undefined,null,2]){renderDatasette({...s,mode:1,motor});check('unknown motor '+motor,reelRate===0);}
renderDatasette({...s,mode:99,motor:1});check('unknown transport',reelRate===0);
renderDatasette({...s,supported:0,mode:1,motor:1});check('unsupported',reelRate===0);
for(const value of [0,101,808]){renderDatasette({...s,counter:value});check('counter '+value,document.querySelector('#tape-counter').textContent===String(value).padStart(3,'0')&&document.querySelector('#tape-counter').children.length===3);}
// Cancel only in this fixture to capture the original stationary spoke angle.
original.forEach(a=>a.cancel());
'''
results=[]
for w,h in [(1920,1080),(1280,1024),(1280,900),(390,780)]:
 for variant in ['before','after']:
  for counter in [0,101,808]:
   html=(A/'index.html').read_text();html=re.sub(r'<script\b.*?</script>','',html,flags=re.S);html=re.sub(r'<link\b[^>]*>','',html)
   css=(out/'backups/style.css').read_text() if variant=='before' else (A/'style.css').read_text()
   css=css.replace('/e64-long.png','data:image/png;base64,'+base64.b64encode((A/'e64-long.png').read_bytes()).decode())
   html=html.replace('</head>','<style>'+css+'</style></head>')
   js=(out/'backups/src/webui/assets/js/datasette.js').read_text() if variant=='before' else (A/'js/datasette.js').read_text()
   js=re.sub(r'^import .*?;\n','',js,flags=re.M).replace('export function','function')
   js+='\nMath.random=()=>.9;initDatasette();document.querySelector("#view-dashboard").hidden=true;document.querySelector("#view-datasette").hidden=false;\n'
   js+=(checks if variant=='after' else 'const checks={};')
   js+='\nrenderDatasette({supported:1,attached:1,writable:1,filename:"USB:/test.tap",mode:0,motor:0,counter:'+str(counter)+'});\n'
   js+=r'''
window.addEventListener('load',()=>{
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
 const result={checks,geometry:[...document.querySelectorAll('#view-datasette svg *,#tape-counter,#tape-counter > span,.tape-transports > *,.datasette-panel')].map(e=>({tag:e.tagName,id:e.id,box:rect(e)})),counter:rect(document.querySelector('#tape-counter')),font:getComputedStyle(document.querySelector('#tape-counter')).fontSize};
 const bytes=new TextEncoder().encode(JSON.stringify(result));
 const canvas=document.createElement('canvas');canvas.width=innerWidth;canvas.height=128;canvas.style='position:fixed;left:0;bottom:0;z-index:999999';document.documentElement.append(canvas);
 const ctx=canvas.getContext('2d'),im=ctx.createImageData(innerWidth,128);
 [bytes.length>>8,bytes.length&255,...bytes].forEach((v,i)=>{im.data[i*4]=v;im.data[i*4+1]=80;im.data[i*4+2]=160;im.data[i*4+3]=255});ctx.putImageData(im,0,0);
});
'''
   html=re.sub(r'(src=")/([^\"]+)',lambda m:m[1]+(A/m[2]).as_uri(),html)
   page=out/f'{variant}-{w}x{h}-{counter:03}.html';page.write_text(html.replace('</body>','<script>'+js+'</script></body>'));shot=page.with_suffix('.png');shot.unlink(missing_ok=True)
   with tempfile.TemporaryDirectory(prefix='e64-reel-firefox-') as profile:
    with page.with_suffix('.log').open('w') as log:
     p=subprocess.Popen(['firefox','--headless','--no-remote','--profile',profile,'--window-size',f'{w},{h}','--screenshot',str(shot),page.as_uri()],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,MOZ_DISABLE_CONTENT_SANDBOX='1',MOZ_CRASHREPORTER_DISABLE='1'))
     try:
      for _ in range(200):
       if shot.exists():
        try:
         with Image.open(shot) as im:im.load()
         break
        except OSError:pass
       if p.poll() is not None:raise RuntimeError('Firefox exited: '+str(page))
       time.sleep(.1)
      else:raise RuntimeError('Firefox timeout: '+str(page))
     finally:
      if p.poll() is None:
       p.terminate()
       try:p.wait(timeout=3)
       except subprocess.TimeoutExpired:p.kill();p.wait()
   im=Image.open(shot).convert('RGB');data=[im.getpixel((x,y+h-128))[0] for y in range(128) for x in range(w)];n=data[0]*256+data[1];result=json.loads(bytes(data[2:2+n]));result.update(viewport=[w,h],variant=variant,value=counter)
   assert all(result['checks'].values()),result['checks']
   results.append(result);print(variant,w,h,counter,'PASS',flush=True)
# Stationary artwork and all geometry must match, with pixel changes confined to zeros.
for w,h in [(1920,1080),(1280,1024),(1280,900),(390,780)]:
 for value in [0,101,808]:
  b=next(r for r in results if r['viewport']==[w,h] and r['variant']=='before' and r['value']==value)
  a=next(r for r in results if r['viewport']==[w,h] and r['variant']=='after' and r['value']==value)
  assert b['geometry']==a['geometry'],('geometry changed',w,h,value)
  assert b['font']==a['font']
  before=Image.open(out/f'before-{w}x{h}-{value:03}.png').convert('RGB');after=Image.open(out/f'after-{w}x{h}-{value:03}.png').convert('RGB')
  diff=ImageChops.difference(before,after);diff.paste((0,0,0),(0,h-128,w,h))
  box=a['counter'];x,y,cw,ch=[box[k] for k in ['x','y','w','h']]
  diff.paste((0,0,0),(int(x),int(y),int(x+cw+1),int(y+ch+1)))
  assert not diff.getbbox(),('pixels changed outside counter',w,h,value,diff.getbbox())
(out/'firefox-results.json').write_text(json.dumps(results,indent=2));print('PASS all Firefox checks, exact geometry and stationary artwork outside counter')
