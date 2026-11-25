#!/usr/bin/env python3
"""Offline Firefox checks of the approved Datasette, desktop only. Fixtures call the production renderer; no hardware is contacted."""
from pathlib import Path
import re, json, os, subprocess, tempfile, time, base64
from PIL import Image
R=Path(__file__).resolve().parents[2]
A=R/'src/webui/assets'
out=R/'build/datasette-seven'/os.environ.get('DATASETTE_STAGE','before');out.mkdir(parents=True,exist_ok=True)
html=(A/'index.html').read_text()
html=re.sub(r'<script\b.*?</script>','',html,flags=re.S)
html=re.sub(r'<link\b[^>]*>','',html)
css=(A/'style.css').read_text().replace('/e64-long.png', 'data:image/png;base64,'+base64.b64encode((A/'e64-long.png').read_bytes()).decode())
html=html.replace('</head>','<style>'+css+'</style></head>')
# Production functions, offline: no API, firmware or device access.
js=(A/'js/datasette.js').read_text()
js=re.sub(r'^import .*?;\n','',js,flags=re.M).replace('export function','function')
js+=r'''
 document.querySelector('#view-dashboard').hidden=true;
 document.querySelector('#view-datasette').hidden=false;
 const loaded=PHASE!=='empty';
 initDatasette();
 const fixtureModes={loaded:0,empty:0,long:0,waiting:1,running:1,rewind:3,forward:4,record:2,stop:0,help:0,error:0};
 const filename=PHASE==='long'?'Long actual tape name <é & name> '.repeat(14)+'.tap':'USB:/tapes/Actual Commodore Game.tap';
 renderDatasette({supported:1,attached:loaded,writable:1,counter:PHASE==='running'?7:123,mode:fixtureModes[PHASE],motor:['running','record','rewind','forward'].includes(PHASE)?1:0,filename,error:PHASE==='error'?5:0});
 if(PHASE==='help') document.querySelector('#tape-help-toggle').click();
 window.addEventListener('load',()=>{
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height};};
 const panel=document.querySelector('.datasette-panel'),drawing=document.querySelector('#tape-drawing'),label=document.querySelector('#tape-label');
 const buttons=[...document.querySelectorAll('.tape-transports .btn')];
 const r=rect(panel),b=buttons.map(rect),d=rect(drawing),l=rect(label);
 const status=document.querySelector('#tape-status'),counter=document.querySelector('#tape-counter'),reset=document.querySelector('[data-tape-action=zero]');
 const helpButton=document.querySelector('#tape-help-toggle');helpButton.focus({preventScroll:true});
 const pins=[...document.querySelectorAll('#tape-spindles circle')],reels=[...document.querySelectorAll('#tape-reels use')];
 const controls=[helpButton,counter,reset,document.querySelector('#tape-motor'),status,...buttons,...(PHASE==='error'?[document.querySelector('#tape-error')]:[])];
 const inside=(a,b)=>a.x>=b.x-.1&&a.y>=b.y-.1&&a.x+a.w<=b.x+b.w+.1&&a.y+a.h<=b.y+b.h+.1;
 const separate=(a,b)=>a.x+a.w<=b.x+.1||b.x+b.w<=a.x+.1||a.y+a.h<=b.y+.1||b.y+b.h<=a.y+.1;
 const boxes=controls.map(rect);
 const windowBox=document.querySelectorAll('#tape-assembly > rect')[3].getBoundingClientRect();
 const led=rect(document.querySelector("#tape-motor span"));
 const frame=rect(document.querySelector("#tape-assembly > rect"));
 const helpBox=rect(document.querySelector("#tape-help"));
 const checks={helpAligned:Math.abs(rect(helpButton).y-frame.y)<.1,rightOrder:rect(helpButton).y+rect(helpButton).h<rect(counter).y&&rect(counter).y+rect(counter).h<rect(reset).y&&rect(reset).y+rect(reset).h<rect(document.querySelector("#tape-motor")).y,digitWindows:counter.children.length===3&&[...counter.children].every(x=>x.textContent.length===1),helpContained:PHASE!=="help"||(helpBox.x>=0&&helpBox.y>=0&&helpBox.x+helpBox.w<=innerWidth&&helpBox.y+helpBox.h<=innerHeight&&separate(helpBox,r)),labelInBay:!loaded||(l.y>=windowBox.y&&l.y+l.h<=windowBox.bottom),headingAbsent:!panel.querySelector("h2")&&panel.getAttribute("aria-label")==="Datasette",frameLowered:Math.abs(frame.y-r.y-(25+(26.33333333333333+16-.5)*d.w/560))<1&&Math.abs(frame.w-410*d.w/560)<1&&frame.h>297,motorCircular:Math.abs(led.w-led.h)<.01&&led.w===19,statusUnderWindow:rect(status).y>=windowBox.bottom&&inside(rect(status),frame),assemblyNearKeys:b[0].y-(frame.y+frame.h)>0&&b[0].y-(frame.y+frame.h)<52,housingWidth:Math.abs(r.w-640)<.1,housingHeight:Math.abs(r.h-(563.7167+(PHASE==="error"?38.2:0)))<.1,controlsInside:boxes.every(x=>inside(x,r)),controlsSeparate:boxes.every((x,i)=>boxes.slice(i+1).every(y=>separate(x,y))),controlsClearOfWindow:boxes.every(x=>separate(x,{x:windowBox.x,y:windowBox.y,w:windowBox.width,h:windowBox.height})),controlTextFits:controls.every(x=>x.scrollWidth<=x.clientWidth&&x.scrollHeight<=x.clientHeight),keyboardFocus:document.activeElement===helpButton,pinGeometry:pins.every((p,i)=>p.getAttribute('cx')===reels[i].getAttribute('x')&&p.getAttribute('cy')===reels[i].getAttribute('y')),windingVisibility:(getComputedStyle(document.querySelector('#tape-winding')).display!=='none')===loaded,accessibleReadouts:status.getAttribute('role')==='status'&&counter.getAttribute('aria-label')==='Tape counter',statusFits:status.scrollHeight<=status.clientHeight,withinViewport:r.x>=0&&r.y>=0&&r.x+r.w<=innerWidth&&r.y+r.h<=innerHeight,noHorizontalOverflow:document.documentElement.scrollWidth<=innerWidth,buttonRow:b.every(x=>Math.abs(x.y-b[0].y)<7),buttonTextFits:buttons.every(x=>x.scrollHeight<=x.clientHeight),buttonOrder:buttons.map(x=>(x.dataset.tapeAction||'load')).join(',')==='record,play,rewind,forward,stop,load,eject',drawingProportion:Math.abs(d.w/d.h-560/310)<.02,loadedDrawing:(getComputedStyle(document.querySelector('#tape-cassette')).display!=='none')===loaded,filename:!loaded||label.textContent===filename.split('/').pop().replace(/\.tap$/i,''),labelFits:!loaded||(l.x>=d.x&&l.x+l.w<=d.x+d.w&&getComputedStyle(label).textOverflow==='ellipsis'),loadLink:document.querySelector('.tape-load').getAttribute('href')==='#/files',counter:counter.textContent===(loaded?(PHASE==='running'?'007':'123'):'000'),status:status.textContent===(loaded?['Stopped','Playing','Recording','Rewinding','Fast Forward'][fixtureModes[PHASE]]:'No tape loaded'),disabled:buttons.filter(x=>x.tagName==='BUTTON').every(x=>x.disabled===!loaded),led:document.querySelector('#tape-motor').getAttribute('data-on')===String(['running','record','rewind','forward'].includes(PHASE)),pressed:buttons.filter(x=>x.tagName==='BUTTON').every(x=>x.getAttribute('aria-pressed')===String(loaded&&((x.dataset.tapeAction==='play'&&[1,2].includes(fixtureModes[PHASE]))||(x.dataset.tapeAction==='record'&&fixtureModes[PHASE]===2)||(x.dataset.tapeAction==='rewind'&&fixtureModes[PHASE]===3)||(x.dataset.tapeAction==='forward'&&fixtureModes[PHASE]===4)))),help:document.querySelector('#tape-help').hidden===(PHASE!=='help')&&document.querySelector('#tape-help-toggle').getAttribute('aria-expanded')===String(PHASE==='help')};
 const textOverflow=controls.filter(x=>x.scrollWidth>x.clientWidth||x.scrollHeight>x.clientHeight).map(x=>[x.id||x.dataset.tapeAction||x.className,x.clientWidth,x.scrollWidth,x.clientHeight,x.scrollHeight]);
 const overlaps=boxes.flatMap((a,i)=>boxes.slice(i+1).flatMap((b,j)=>separate(a,b)?[]:[{first:controls[i].id||controls[i].className,second:controls[i+j+1].id||controls[i+j+1].className,a,b}]));
 // Measure blue aperture against the complete orange/reel assembly, including stroke.
 const orange=document.querySelector('#tape-winding').parentElement.querySelector('rect');
 const blue=document.querySelector('#cassette-well rect');
 const point=(node,y)=>new DOMPoint(0,y).matrixTransform(node.getScreenCTM()).y;
 const top=point(orange,108)-point(document.querySelector('#tape-label-artwork'),89.5);
 const bottom=point(document.querySelector('#tape-label-artwork'),219.5)-point(orange,156);
 const opening=document.querySelector('#tape-assembly > rect[x="25"]');
 const screen=(node,x,y)=>new DOMPoint(x,y).matrixTransform(node.getScreenCTM());
 const tapeMin=screen(orange,113,108),tapeMax=screen(orange,309,156);
 const tapeCenter={x:(tapeMin.x+tapeMax.x)/2,y:(tapeMin.y+tapeMax.y)/2};
 const frameCenter=screen(opening,211.5,157.33333333333333);
 const clearances={top,bottom,tapeCenter,frameCenter:{x:frameCenter.x,y:frameCenter.y},bounds:{left:tapeMin.x,top:tapeMin.y,right:tapeMax.x,bottom:tapeMax.y}};
 checks.outerFrameCentered=Math.abs(tapeCenter.x-frameCenter.x)<0.0001&&Math.abs(tapeCenter.y-frameCenter.y)<0.0001;
 checks.tapeInsideBlue=top>=0&&bottom>=0&&tapeMin.x>=screen(blue,67.5,89.5).x&&tapeMax.x<=screen(blue,355.5,219.5).x;
 checks.labelInsideBlue=!loaded||(l.y>=point(document.querySelector('#tape-label-artwork'),89.5)&&l.y+l.h<=point(orange,108)&&Math.abs(l.x+l.w/2-(d.x+211.5*d.w/560))<0.01);
 const margins={left:b[0].x-r.x,right:r.x+r.w-(b[6].x+b[6].w)};
 checks.symmetricHousingMargins=Math.abs(margins.left-margins.right)<0.0001;
 const skin=getComputedStyle(panel,'::before');
 const housing={x:r.x,y:r.y+1+parseFloat(skin.top),w:r.w,h:parseFloat(skin.height)};
 const blackBottom=rect(document.querySelector('.tape-transports')).y+rect(document.querySelector('.tape-transports')).h-2;
 const housingMeasurements={housing,topMargin:point(document.querySelector('#tape-assembly > rect'),26.33333333333333-.5)-housing.y,bottomGap:housing.y+housing.h-blackBottom,blackBottom};
 checks.topMargin34=Math.abs(housingMeasurements.topMargin-34)<.02;
 checks.bottomFlush=Math.abs(housingMeasurements.bottomGap-18)<.02;
 checks.housingControlsInside=boxes.filter((_,i)=>PHASE!=='error'||i<boxes.length-1).every(x=>inside(x,housing));
 checks.housingRadius=skin.borderTopLeftRadius==='52px'&&skin.borderBottomLeftRadius==='52px';
 const cr=controls.slice(0,5).map(rect);
 checks.uniformColumn=cr.slice(0,4).every(x=>Math.abs(x.w-cr[0].w)<.02&&Math.abs(x.x+x.w-cr[0].x-cr[0].w)<.02);
 checks.helpResetSize=Math.abs(cr[0].h-cr[2].h)<.02;
 checks.counterGap=Math.abs(cr[2].y-cr[1].y-cr[1].h-4)<.02;
 checks.motorStatusAligned=Math.abs(cr[3].y-cr[4].y)<.02&&Math.abs(cr[3].h-cr[4].h)<.02;
 checks.resetPositionPreserved=Math.abs(cr[2].y-292.916687)<.03;
 const statusShape=document.querySelector('#tape-assembly > rect[fill="#070707"]');
 const scale=statusShape.getScreenCTM().a;
 const statusMeasurements={bounds:rect(statusShape),height:statusShape.height.baseVal.value*scale,radius:statusShape.rx.baseVal.value*scale,outerHeight:(statusShape.height.baseVal.value+1)*scale,outerRadius:(statusShape.rx.baseVal.value+.5)*scale,overlayRadius:parseFloat(getComputedStyle(status).borderTopLeftRadius),overlayHeight:rect(status).h};
 checks.statusSemicircles=Math.abs(statusMeasurements.radius*2-statusMeasurements.height)<1e-8&&Math.abs(statusMeasurements.outerRadius*2-statusMeasurements.outerHeight)<1e-8;
 checks.statusOverlaySemicircles=Math.abs(statusMeasurements.overlayRadius*2-statusMeasurements.overlayHeight)<.02;
 const allGeometry=[...panel.querySelectorAll('*')].map(e=>({tag:e.tagName,id:e.id,box:rect(e)}));
 const frameStroke=0.5*document.querySelector("#tape-assembly > rect").getScreenCTM().a;
 // Firefox getBoundingClientRect already includes this rect’s outer stroke.
 const gap=rect(counter).x-(frame.x+frame.w);
 const shading=[...panel.querySelectorAll("*"),panel].flatMap(e=>[null,"::before","::after"].flatMap(p=>{const c=getComputedStyle(e,p);return /gradient\(/.test(c.backgroundImage)||c.boxShadow!=="none"||c.textShadow!=="none"||c.filter!=="none"?[{id:e.id,tag:e.tagName,p,background:c.backgroundImage,shadow:c.boxShadow,text:c.textShadow,filter:c.filter}]:[]}));
 const stripe=document.querySelector('#tape-assembly > rect[x="19"]');
 const edge=new DOMPoint(211.5,44.33333333333333).matrixTransform(stripe.getScreenCTM()).y;
 const logo=rect(document.querySelector('.tape-e64-logo'));
 const radii=[counter,reset,document.querySelector('#tape-motor'),helpButton].map(e=>getComputedStyle(e).borderTopLeftRadius);
 // Apply the exact authored :hover declarations through a fixture class to
 // inspect all seven keys without depending on a headless pointer location.
 const hoverStyle=document.createElement('style');
 hoverStyle.textContent=[...document.styleSheets].flatMap(sheet=>{try{return [...sheet.cssRules]}catch{return []}}).filter(rule=>rule.selectorText?.includes('.tape-transports')&&rule.selectorText.includes(':hover')).map(rule=>rule.cssText.replaceAll(':hover','.fixture-hover')).join('\n');
 document.head.append(hoverStyle);
 const hoverChecks=buttons.map(key=>{
 const before=rect(key),normal=getComputedStyle(key).backgroundImage,dot=getComputedStyle(buttons[0].firstElementChild).color;
 key.classList.add('fixture-hover');
 const c=getComputedStyle(key),hovered={outline:c.outlineColor,width:c.outlineWidth,background:c.backgroundImage,animation:c.animationName,transition:c.transitionDuration};
 const stable=JSON.stringify(before)===JSON.stringify(rect(key))&&dot===getComputedStyle(buttons[0].firstElementChild).color;
 key.classList.remove('fixture-hover');
 return stable&&hovered.outline==='rgb(8, 8, 8)'&&hovered.width==='1px'&&(key.getAttribute('aria-pressed')==='true'?getComputedStyle(key).backgroundColor==='rgb(0, 0, 0)':hovered.background!==normal)&&hovered.animation==='none'&&hovered.transition==='0s'&&getComputedStyle(key).backgroundImage===normal;
  });hoverStyle.remove();
 const activeStyle=document.createElement('style');
 activeStyle.textContent=[...document.styleSheets].flatMap(sheet=>{try{return [...sheet.cssRules]}catch{return []}}).filter(rule=>rule.selectorText?.includes('.tape-transports')&&rule.selectorText.includes(':active')).map(rule=>rule.cssText.replaceAll(':active','.fixture-active').replaceAll(':hover','.fixture-hover').replaceAll(':not(:disabled)','')).join('\n');
 document.head.append(activeStyle);
 const activeChecks=buttons.map(key=>{
 const before=rect(key),dot=getComputedStyle(buttons[0].firstElementChild).color;
 key.classList.add('fixture-active');
 const c=getComputedStyle(key);
 const ok=c.backgroundColor==='rgb(0, 0, 0)'&&c.backgroundImage==='none'&&c.color==='rgb(255, 255, 255)'&&c.transform==='none'&&JSON.stringify(before)===JSON.stringify(rect(key))&&dot===getComputedStyle(buttons[0].firstElementChild).color;
 key.classList.remove('fixture-active');return ok;
 });activeStyle.remove();
 const seven={activeChecks,hoverChecks,edge,logo,radii,housingColor:getComputedStyle(panel,'::before').backgroundColor,recColor:getComputedStyle(buttons[0].firstElementChild).color};
 const result={seven,shading,gap,allGeometry,statusMeasurements,controlRects:cr,housingMeasurements,margins,clearances,overlaps,textOverflow,viewport:[innerWidth,innerHeight],phase:PHASE,panel:r,frame,drawing:d,buttons:b,checks,pass:Object.values(checks).every(Boolean)};
 const bytes=new TextEncoder().encode(JSON.stringify(result));
 const canvas=document.createElement('canvas');canvas.width=innerWidth;canvas.height=128;canvas.style='position:absolute;left:0;z-index:999999;width:100vw;height:128px;top:0;bottom:auto';document.documentElement.append(canvas);
 const ctx=canvas.getContext('2d'),im=ctx.createImageData(innerWidth,128);
 [bytes.length>>8,bytes.length&255,...bytes].forEach((v,i)=>{im.data[i*4]=v;im.data[i*4+1]=80;im.data[i*4+2]=160;im.data[i*4+3]=255});ctx.putImageData(im,0,0);
});
'''
html=re.sub(r'(src=")/([^\"]+)',lambda m:m[1]+(A/m[2]).as_uri(),html)
results=[]
for topic,w,h,phase in [('datasette',w,h,p) for w,h in [(1280,1024),(1280,900),(390,780)] for p in ['loaded','empty','long','waiting','running','rewind','forward','record','stop','help','error']]:
  page=out/f'{topic}-{w}x{h}-{phase}.html'
  page.write_text(html.replace('</body>','<script>'+js.replace('PHASE',json.dumps(phase)).replace('TOPIC',json.dumps(topic))+'</script></body>'))
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
  im=Image.open(shot).convert('RGB');data=[im.getpixel((x,y))[0] for y in range(128) for x in range(w)];n=data[0]*256+data[1]
  result=json.loads(bytes(data[2:2+n]));results.append(result);print(json.dumps(result),flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2))
# Desktop legacy predicates are recorded; dedicated before/after comparisons validate this change.
