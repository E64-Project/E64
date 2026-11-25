#!/usr/bin/env python3
"""Offline production-renderer Firefox checks; no device or firmware access."""
from pathlib import Path
import re,json,os,subprocess,tempfile,time,base64
from PIL import Image
R=Path(__file__).resolve().parents[2]; A=R/'src/webui/assets'; O=R/'build/datasette-final-design'; O.mkdir(exist_ok=True,parents=True)
base=(A/'index.html').read_text();base=re.sub(r'<script\b.*?</script>','',base,flags=re.S);base=re.sub(r'<link\b[^>]*>','',base)
css=(A/'style.css').read_text().replace('/e64-long.png','data:image/png;base64,'+base64.b64encode((A/'e64-long.png').read_bytes()).decode())
base=base.replace('</head>','<style>'+css+'</style></head>');base=re.sub(r'(src=")/([^\"]+)',lambda m:m[1]+(A/m[2]).as_uri(),base)
source=re.sub(r'^import .*?;\n','',(A/'js/datasette.js').read_text(),flags=re.M).replace('export function','function')
script=r'''
document.querySelector('#view-dashboard').hidden=true;document.querySelector('#view-datasette').hidden=false;
let randomCalls=0;Math.random=()=>{randomCalls++;return (COLOR+.25)/16;};
initDatasette();
const s={supported:1,attached:1,writable:1,filename:PHASE==='long'?'USB:/tapes/'+('Very long actual filename <é & game> '.repeat(14))+'.tap':'USB:/tapes/Actual Commodore Game.tap',counter:123,mode:0,motor:0,pending:0,serial:1};
renderDatasette(s);const initialColor=document.querySelector('#tape-cassette').getAttribute('fill');
for(let mode=0;mode<5;mode++)renderDatasette({...s,mode,motor:1,serial:mode+2});
renderDatasette(s);setDatasetteVisible(false);renderDatasette(s);
const stable=randomCalls===1&&document.querySelector('#tape-cassette').getAttribute('fill')===initialColor;
renderDatasette({...s,attached:0});const emptyCounter=document.querySelector('#tape-counter').textContent;
const emptyClear=['tape-cassette','tape-label','tape-reels','tape-winding'].every(id=>getComputedStyle(document.getElementById(id)).display==='none');
renderDatasette(s);const reattach=randomCalls===2;
document.dispatchEvent(new Event('datasette-attached'));renderDatasette(s);const sameFileAttach=randomCalls===3;
const fixtureModes={play:1,record:2,rewind:3,forward:4};const mode=fixtureModes[PHASE]||0;
renderDatasette({...s,attached:PHASE!=='empty',mode,motor:mode?1:0});
if(PHASE==='help')document.querySelector('#tape-help-toggle').click();
window.addEventListener('load',()=>{
const el=id=>document.getElementById(id),rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
const panel=document.querySelector('.datasette-panel'),label=el('tape-label'),drawing=el('tape-drawing'),loaded=PHASE!=='empty',buttons=[...document.querySelectorAll('[data-tape-action]')];
const l=rect(label),d=rect(drawing);const point=(x,y)=>new DOMPoint(x,y).matrixTransform(el('tape-label-artwork').getScreenCTM());
const reelTop=point(0,35.666666666666667+108).y;
const nameStyle=getComputedStyle(label),motorStyle=getComputedStyle(el('tape-motor'));
const disk=el('tape-drive-disks'),pins=el('tape-spindles');
const checks={stable,reattach,sameFileAttach,emptyClear,emptyCounter:emptyCounter==='000',palette:initialColor===cassetteColors[COLOR],filename:label.textContent===(loaded?s.filename.split('/').pop().replace(/\.tap$/i,''):''),whiteNameplate:!loaded||(nameStyle.backgroundColor==='rgb(255, 255, 255)'&&nameStyle.color==='rgb(8, 8, 8)'),nameplateCentered:!loaded||Math.abs(l.x+l.w/2-point(211.5,0).x)<.05,nameplateClearOfWheels:!loaded||l.y+l.h<reelTop,nameplateTextHeight:!loaded||parseFloat(nameStyle.fontSize)*1.4<=l.h-2+.1,nameplateFixedHeight:!loaded||Math.abs(l.h-d.h*26/310)<.05,nameplateWithinWindow:!loaded||(l.x>=point(67.5,0).x&&l.x+l.w<=point(355.5,0).x),ellipsis:nameStyle.textOverflow==='ellipsis',motorSilver:motorStyle.backgroundColor==='rgb(216, 219, 222)'&&motorStyle.backgroundImage==='none',status:el('tape-status').textContent===(loaded?['Stopped','Playing','Recording','Rewinding','Fast Forward'][mode]:'No Tape Loaded'),counter:el('tape-counter').textContent===(loaded?'123':'000'),visibility:['tape-cassette','tape-label','tape-reels','tape-winding'].every(id=>(getComputedStyle(el(id)).display!=='none')===loaded),mechanismVisible:getComputedStyle(disk).display!=='none'&&getComputedStyle(pins).display!=='none',diskGeometry:[...disk.children].every((e,i)=>e.getAttribute('cx')===[...pins.children][i].getAttribute('cx')&&e.getAttribute('cy')===[...pins.children][i].getAttribute('cy')&&e.getAttribute('r')==='19.5'),emptyBackground:el('tape-label-artwork').querySelectorAll('rect')[1].getAttribute('fill')==='#D0CCC4',disabled:buttons.every(b=>b.disabled===!loaded),led:el('tape-motor').getAttribute('data-on')===String(!!mode),pressed:buttons.every(b=>b.getAttribute('aria-pressed')===String(loaded&&((b.dataset.tapeAction==='play'&&[1,2].includes(mode))||(b.dataset.tapeAction==='record'&&mode===2)||(b.dataset.tapeAction==='rewind'&&mode===3)||(b.dataset.tapeAction==='forward'&&mode===4)))),help:el('tape-help').hidden===(PHASE!=='help'),loadLink:document.querySelector('.tape-load').getAttribute('href')==='#/files',noHorizontalOverflow:document.documentElement.scrollWidth<=innerWidth,statusWeight:getComputedStyle(el('tape-status')).fontWeight==='600',keyWeight:[...document.querySelectorAll('.tape-transports .btn > span:last-child')].every(e=>getComputedStyle(e).fontWeight==='600')};
const geometry=[...panel.querySelectorAll('*')].filter(e=>!e.closest('#tape-drive-disks')&&e.id!=='tape-label').map(e=>({tag:e.tagName,id:e.id,box:rect(e)}));
const result={viewport:[innerWidth,innerHeight],phase:PHASE,color:COLOR,checks,pass:Object.values(checks).every(Boolean),label:l,panel:rect(panel),geometry};
const bytes=new TextEncoder().encode(JSON.stringify(result));const canvas=document.createElement('canvas');canvas.width=innerWidth;canvas.height=128;canvas.style='position:absolute;left:0;top:0;z-index:999999';document.documentElement.append(canvas);const ctx=canvas.getContext('2d'),im=ctx.createImageData(innerWidth,128);[bytes.length>>8,bytes.length&255,...bytes].forEach((v,i)=>{im.data[i*4]=v;im.data[i*4+1]=80;im.data[i*4+2]=160;im.data[i*4+3]=255});ctx.putImageData(im,0,0);
});
'''

def firefox(page,shot,w,h):
 with tempfile.TemporaryDirectory(prefix='e64-final-firefox-',dir=O) as profile:
  with page.with_suffix('.log').open('w') as log:
   p=subprocess.Popen(['firefox','--headless','--no-remote','--profile',str(Path(profile).resolve()),'--window-size',f'{w},{h}','--screenshot',str(shot),page.as_uri()+('#view-datasette' if '-review' in page.stem and w<500 else '')],stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,MOZ_DISABLE_CONTENT_SANDBOX='1',MOZ_CRASHREPORTER_DISABLE='1'))
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
results=[]
for w,h in [(1280,1024),(1280,900),(390,780)]:
 for phase,color in [('blue',6),('green',5),('white',1),('empty',6),('long',1),('play',6),('record',6),('rewind',6),('forward',6),('help',6)]+([('palette',i) for i in range(16)] if h==1024 else []):
  stem=f'{w}x{h}-{phase}-{color}';page=O/(stem+'.html');shot=page.with_suffix('.png');shot.unlink(missing_ok=True)
  js=script.replace('COLOR',str(color)).replace('PHASE',json.dumps(phase))
  content=base.replace('</body>','<script>'+source+js+'</script></body>');page.write_text(content)
  firefox(page.resolve(),shot.resolve(),w,h)
  with Image.open(shot) as im:
   im=im.convert('RGB'); data=[im.getpixel((x,y))[0] for y in range(128) for x in range(w)];n=data[0]*256+data[1];result=json.loads(bytes(data[2:2+n]))
  results.append(result);print(stem, 'PASS' if result['pass'] else [k for k,v in result['checks'].items() if not v],flush=True)
  # A second browser capture produces clean, unmodified review screenshots.
  if phase in ['blue','green','white','empty','long']:
   clean=O/(stem+'-review.html');clean.write_text(content.replace("document.documentElement.append(canvas);", "if(innerWidth<500)document.querySelector('#app').style.transform='translateY(-'+(document.querySelector('#view-datasette').getBoundingClientRect().y-10)+'px)';"));(O/(stem+'-review.png')).unlink(missing_ok=True);firefox(clean.resolve(),(O/(stem+'-review.png')).resolve(),w,h)
(O/'firefox-results.json').write_text(json.dumps(results,indent=2))
assert all(r['pass'] for r in results), 'See firefox-results.json'
print('PASS all Firefox checks')
