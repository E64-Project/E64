#!/usr/bin/env python3
"""Real Firefox UI checks + screenshots using production modules and an in-memory API.
Normal Devuan terminal: python3 tools/webui_test/unified_ui_browser_check.py
No SD/device/filesystem API writes: only build/ logs/profiles/screenshots.
"""
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread, Event
import argparse,json,subprocess,urllib.parse,datetime
ROOT=Path(__file__).resolve().parents[2];ASSETS=ROOT/'src/webui/assets';OUT=ROOT/'build/unified-web-ui-firefox'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--screen','--topic',default='all',choices=['all','datasette','dashboard','files','configs','instructions','hotkeys','roms','drives','ieee488','sid','mouse','navigation','new-folder','commands','editor','confirmation','destination','move-destination','storage','easter-egg','rainbow','about']);parser.add_argument("--desktop-only",action="store_true",help="Only release desktop viewports");args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
SCRIPT=r'''
import {initDatasette,setDatasetteVisible} from '/js/datasette.js';
import {initAbout} from '/js/about.js';
import {initHelpNavigation} from '/js/help_dialog.js';
import {initLogo,updateLogoVersion} from '/js/logo.js';
import {initDashboard,startStatusPolling,refreshVolumes} from '/js/dashboard.js';
import {showInstructions,hideInstructions,updateHotkeys} from '/js/instructions.js';
import {confirmE64,promptE64} from '/js/dialog.js';
import {fileIconType} from '/js/file_icons.js';
import {initFiles,loadDir,selectFilesVolume} from '/js/files.js';
import {initConfigs,loadConfigs} from '/js/configs.js';
import {setMachine} from '/js/machine.js';
import {parsePrg} from '/js/basic.js';
import {initEditor,openEditor,openBasicEditor} from '/js/editor.js';
const results=[];const check=(name,pass,measurements)=>{results.push({name,pass:!!pass,...(measurements?{measurements}:{})});return !!pass;};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function waitFor(fn,operation=fn.toString()){for(let n=0;n<120;n++){if(fn())return;await pause(20);}throw Error('Timed out waiting for UI: '+operation);}
const box=e=>e.getBoundingClientRect();
const rect=r=>({left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height});
function textRects(e){const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT),rects=[];let n;while(n=walker.nextNode()){if(!n.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(n);rects.push(...range.getClientRects());}return rects;}
function powerMeasurements(b,power){const range=document.createRange();range.selectNode(b.lastChild);return {id:b.id,button:rect(box(b)),container:rect(box(power)),icon:rect(box(b.querySelector('.ni-ico'))),label:[...range.getClientRects()].map(rect),scrollWidth:b.scrollWidth,clientWidth:b.clientWidth};}
function desktopDialogGeometry(dialog,label,width,height){
 if(innerWidth<1280)return;
 const bounds=rect(box(dialog)), tolerance=1;
 check(label+' approved desktop dimensions',Math.abs(bounds.width-width)<1&&(height===undefined||Math.abs(bounds.height-height)<1),bounds);
 check(label+' entire dialog within viewport',bounds.left>=0&&bounds.right<=innerWidth&&bounds.top>=0&&bounds.bottom<=innerHeight,bounds);
 const offenders=[], raw=[];
 const identify=e=>e.id?'#'+e.id:e.tagName.toLowerCase()+(e.getAttribute('class')?'.'+e.getAttribute('class').trim().replace(/\s+/g,'.'):'');
 const omitted=e=>{
  for(let a=e;a;a=a.parentElement){
   const s=getComputedStyle(a);
   if(s.display==='none'||s.visibility==='hidden'||s.visibility==='collapse')return true;
   // Explicit accessible-only content has no intended visible text region.
   if(a.classList.contains('sr-only')&&s.position==='absolute'&&s.overflowX==='hidden'&&s.clipPath==='inset(50%)'&&box(a).width<=1&&box(a).height<=1)return true;
   if(a===dialog)break;
  }
  return false;
 };
 const region=e=>{const r=box(e);return {left:r.left+e.clientLeft,right:r.left+e.clientLeft+e.clientWidth};};
 const outside=(r,c)=>r.left<c.left-tolerance||r.right>c.right+tolerance;
 for(const e of [dialog,...dialog.querySelectorAll('*')]){
  const s=getComputedStyle(e), r=box(e), excluded=omitted(e);
  if(e.scrollWidth>e.clientWidth+tolerance)raw.push({element:identify(e),bounds:rect(r),scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,overflowX:s.overflowX,excluded});
  if(excluded||!e.getClientRects().length)continue;
  // clientWidth is meaningful for scroll containers, not arbitrary inline/table boxes.
  if(['auto','scroll'].includes(s.overflowX)&&e.scrollWidth>e.clientWidth+tolerance)offenders.push({element:identify(e),reason:'horizontal scroll range',scrollWidth:e.scrollWidth,clientWidth:e.clientWidth});
  const samples=[];
  if(e!==dialog)samples.push({kind:'element',bounds:rect(r),start:e.parentElement});
  // Direct text only: descendants may have their own intentional clipping.
  for(const n of e.childNodes){if(n.nodeType!==3||!n.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(n);for(const t of range.getClientRects())samples.push({kind:'text',bounds:rect(t),start:e});}
  for(const sample of samples){
   for(let a=sample.start;a;a=a.parentElement){
    if(a===dialog||getComputedStyle(a).overflowX!=='visible'){
     const clip=region(a);
     if(outside(sample.bounds,clip))offenders.push({element:identify(e),reason:sample.kind+' outside clipping region',bounds:sample.bounds,container:identify(a),clip});
    }
    if(a===dialog)break;
   }
  }
 }
 const page={scrollWidth:document.documentElement.scrollWidth,clientWidth:innerWidth};
 if(page.scrollWidth>innerWidth+tolerance)offenders.push({element:'html',reason:'page horizontal scroll range',...page});
 check(label+' no horizontal clipping or scrolling',offenders.length===0,{bounds,tolerance,page,offenders,rawScrollExcess:raw});
}

const buttons=e=>[...e.querySelectorAll('button')];
function header(dialog){const h=dialog.querySelector('.e64-popup-header'),t=h?.querySelector('h2,h3'),b=h?.querySelector('form button')||h?.querySelector('button');check('header exists',!!h&&!!t&&!!b);const tr=box(t),br=box(b);check('title and Close vertically centered',Math.abs(tr.top+tr.height/2-br.top-br.height/2)<2);check('title and Close do not overlap',tr.right<=br.left+1);const divider=h;check('shared 4px orange header divider',getComputedStyle(divider).borderBottomWidth==='4px'&&getComputedStyle(divider).borderBottomColor==='rgb(221, 136, 85)');check('near-black dialog panel',getComputedStyle(dialog).backgroundColor==='rgb(0, 0, 0)');}
function view(name){for(const item of document.querySelectorAll('.sidebar > .nav .nav-item'))item.classList.toggle('active',item.getAttribute('href')==='#/'+name);for(const n of ['dashboard','files','configs','instructions','datasette'])document.getElementById('view-'+n).hidden=n!==name;}
const state=async()=>await(await fetch('/__state')).json();
function folder(){document.getElementById('fb-mkdir').focus();document.getElementById('fb-mkdir').click();return document.querySelector('dialog.e64-dialog[open]');}
const cancel=async d=>{const closed=new Promise(r=>d.addEventListener('close',r,{once:true}));buttons(d).find(b=>b.textContent==='Cancel').click();await closed;};
try{
 initDatasette();initAbout();initHelpNavigation();initLogo();initFiles();initConfigs();initEditor();initDashboard();selectFilesVolume('SD');await loadDir('/');await loadConfigs();startStatusPolling();await waitFor(()=>document.getElementById('sys-state').textContent==='System Online');await refreshVolumes();await loadDir('/');

 view('datasette');setDatasetteVisible(true);
 await waitFor(()=>document.getElementById('tape-counter').textContent==='123');
 check('Datasette navigation destination',!!document.querySelector('.nav-item[href="#/datasette"][data-view="datasette"]'));
 check('Datasette API filename rendered',document.getElementById('tape-label').textContent==='Browser fixture.tap');
 check('Datasette API transport rendered',document.getElementById('tape-status').textContent==='Playing');
 const tapeMotor=document.getElementById('tape-motor');
 check('Datasette API motor rendered',tapeMotor.dataset.on==='false'&&tapeMotor.getAttribute('aria-label')==='Tape motor off');
 const door=document.querySelector('#tape-assembly > rect[x="19"]');
 const motorGeometry={motor:rect(box(tapeMotor)),door:rect(box(door)),led:rect(box(tapeMotor.querySelector('span'))),others:[...document.querySelectorAll('#tape-assembly > rect,.tape-help,.tape-readout,#tape-counter,#tape-status,.tape-transports,.datasette-panel')].map(e=>({tag:e.id||e.getAttribute('class')||e.outerHTML,bounds:rect(box(e))}))};
 // Firefox rounds CSS layout and transformed SVG coordinates separately.
 // Allow three 1/60px layout units (0.05px), without moving the approved MOTOR.
 check('Datasette MOTOR bottom aligns with outer black door frame',Math.abs(motorGeometry.motor.bottom-motorGeometry.door.bottom)<=0.05,motorGeometry);
 const tapePanel=document.querySelector('.datasette-panel'),tapeBounds=box(tapePanel);
 // The approved desktop housing is a ::before painted over the panel border.
 // Its 1px border extension contributes to scrollWidth; measure painted bounds
 // and actual controls instead of requiring the border-box clientWidth.
 const housingStyle=getComputedStyle(tapePanel,'::before');
 const housing=innerWidth>850?{
  left:tapeBounds.left+tapePanel.clientLeft+parseFloat(housingStyle.left),
  right:tapeBounds.left+tapePanel.clientLeft+parseFloat(housingStyle.left)+parseFloat(housingStyle.width),
  top:tapeBounds.top+tapePanel.clientTop+parseFloat(housingStyle.top),
  bottom:tapeBounds.top+tapePanel.clientTop+parseFloat(housingStyle.top)+parseFloat(housingStyle.height)
 }:rect(tapeBounds);
 const tapeFit={bounds:rect(tapeBounds),housing,scrollWidth:tapePanel.scrollWidth,clientWidth:tapePanel.clientWidth,
  controls:[...tapePanel.querySelectorAll('.tape-transports button,.tape-help,.tape-readout,#tape-counter,#tape-status,#tape-motor')].map(e=>({tag:e.id||e.className,bounds:rect(box(e))}))};
 check('Datasette housing and controls fit horizontally',housing.left>=0&&housing.right<=innerWidth&&tapeFit.controls.every(e=>e.bounds.left>=housing.left&&e.bounds.right<=housing.right),tapeFit);
 // Mobile uses normal document scrolling below the stacked sidebar.
 if(innerWidth>850)check('Datasette panel fits desktop',housing.top>=0&&housing.bottom<=innerHeight&&tapeBounds.bottom<=innerHeight,tapeFit);
 const tapeButtons=[...document.querySelectorAll('.tape-transports button')];
 // The approved playing state depresses Play by 6px within the shared row.
 check('Datasette six enabled transports in one row',tapeButtons.map(b=>b.dataset.tapeAction).join('|')==='record|play|rewind|forward|stop|eject'&&tapeButtons.every(b=>!b.disabled&&Math.abs(box(b).top-box(tapeButtons[0]).top-(b.dataset.tapeAction==='play'?6:0))<1));
 check('Datasette API pressed transport rendered',tapeButtons.every(b=>b.getAttribute('aria-pressed')===String(b.dataset.tapeAction==='play')));
 setDatasetteVisible(false);
 updateLogoVersion('1.0.1');
 const logo=document.getElementById('logo-toggle'),logoImage=logo.querySelector('img'),logoPanel=document.getElementById('logo-version');
 const whiteBefore=rect(box(logoImage));logo.click();
 check('version toggle preserves original image geometry',JSON.stringify(rect(box(logoImage)))===JSON.stringify(whiteBefore));
 check('logo version exact text',document.getElementById('logo-version-text').getAttribute('aria-label')==='V 1.0.1');
 check('version stays in original rainbow bounds',Math.abs(box(logoPanel).left-(box(logoImage).left+box(logoImage).width*26/1602))<1&&Math.abs(box(logoPanel).top-(box(logoImage).top+box(logoImage).height*582/960))<1&&Math.abs(box(logoPanel).width-box(logoImage).width*1550/1602)<.1&&Math.abs(box(logoPanel).height-box(logoImage).height*352/960)<.1);
 check('version white interior and pure red frame',getComputedStyle(logoPanel).backgroundColor==='rgb(255, 255, 255)'&&getComputedStyle(logoPanel).borderTopWidth==='5px'&&getComputedStyle(logoPanel).borderTopColor==='rgb(255, 0, 0)');check('source rainbow region entirely clipped',getComputedStyle(logoImage).clipPath==='inset(0px 0px 39.375%)');logo.click();check('rainbow default restored',logoPanel.hidden&&getComputedStyle(logoImage).clipPath==='none');
 const headingDimensions=[];
 for(const page of ['dashboard','files','configs','instructions']){
  view(page);const section=document.getElementById('view-'+page),header=section.querySelector('.page-title-box'),title=header.querySelector('h1'),sidebar=document.querySelector('.sidebar');
  check('one separate title box '+page,section.querySelectorAll('.page-title-box').length===1&&section.firstElementChild===header);
  check('page header icon '+page,!!title.querySelector('.page-icon'));
  check('full-width page header '+page,Math.abs(box(header).width-box(section).width)<1&&Math.abs(box(header).height-56)<1);
  headingDimensions.push(getComputedStyle(header).padding+'|'+getComputedStyle(header).borderRadius+'|'+getComputedStyle(title).fontSize);check('shared header surface and border '+page,getComputedStyle(header).backgroundColor==='rgb(0, 0, 0)'&&getComputedStyle(header).borderColor==='rgb(68, 68, 68)');
  for(const button of section.querySelectorAll('.btn-primary')){const colors=getComputedStyle(button);check('flat orange primary action '+page,colors.backgroundColor==='rgb(221, 136, 85)'&&colors.color==='rgb(0, 0, 0)'&&colors.backgroundImage==='none');}
  const selected=document.querySelector('.sidebar > .nav .nav-item.active');check('warm flat selected navigation '+page,!!selected&&getComputedStyle(selected).backgroundColor==='rgb(102, 68, 0)'&&getComputedStyle(selected).color==='rgb(255, 255, 255)'&&getComputedStyle(selected).backgroundImage==='none');
  check('Commodore green page title '+page,getComputedStyle(title).color==='rgb(0, 204, 85)');
  check('no page horizontal clipping '+page,document.documentElement.scrollWidth<=innerWidth+1);
  if(innerWidth>820&&innerHeight>=900){check('sidebar fits without vertical scroll '+page,sidebar.scrollHeight<=sidebar.clientHeight+1);check('comfortable compact navigation '+page,[...sidebar.querySelectorAll(':scope > .nav .nav-item')].every(e=>box(e).height===42));const controls=sidebar.querySelector('.sidebar-bottom'),prior=sidebar.querySelector(':scope > .nav');check('room for one future sidebar button '+page,box(controls).top-box(prior).bottom>=42);}
  const bottomGroup=sidebar.querySelector('.sidebar-bottom'),power=bottomGroup.querySelector('.nav-bottom'),reboot=document.getElementById('nav-reboot'),shutdown=document.getElementById('nav-shutdown'),about=document.getElementById('about-e64-button');
  check('whole sidebar group reserves 32px below About '+page,getComputedStyle(bottomGroup).marginBottom==='32px');
  check('power container has no joined outer border '+page,getComputedStyle(power).borderTopWidth==='0px');
  for(const b of [reboot,shutdown]){check('power button own border and corners '+page,getComputedStyle(b).borderTopWidth==='1px'&&parseFloat(getComputedStyle(b).borderRadius)>=8);check('power button readable bounds '+page,b.scrollWidth<=b.clientWidth+1&&box(b).left>=box(power).left-1&&box(b).right<=box(power).right+1,powerMeasurements(b,power));}
  const rb=box(reboot),sb=box(shutdown);check('separate power buttons have a visible gap '+page,Math.abs(rb.top-sb.top)<1?sb.left-rb.right>=7:sb.top-rb.bottom>=7);
  const powerMinimum=b=>Math.max(parseFloat(getComputedStyle(b).flexBasis)||0,parseFloat(getComputedStyle(b).minWidth)||0);
  const powerRequired=powerMinimum(reboot)+powerMinimum(shutdown)+parseFloat(getComputedStyle(power).columnGap);
  if(box(power).width>=powerRequired)check('power buttons side by side when space permits '+page,Math.abs(rb.top-sb.top)<1,{available:box(power).width,required:powerRequired});
  if(innerWidth>820)check('About clears bottom link-preview area '+page,box(sidebar).bottom-box(about).bottom>=32);
  if(page==='configs'){const toolbar=document.querySelector('.pf-head'),refresh=document.getElementById('pf-refresh');check('Configs Refresh right aligned',Math.abs(box(toolbar).right-box(refresh).right)<1);check('Configs has no visible count',!/^\d+ (?:Configs|legacy entries)\.$/.test(document.getElementById('pf-status').textContent));}
  if(page==='files')check('sidebar drop removed',!document.getElementById('fb-drop'));
  if(page==='files'){
   const scroll=document.querySelector('#view-files .fb-scroll'),table=scroll.querySelector('.fb-table'),style=getComputedStyle(scroll),head=table.tHead.rows[0],rows=[...table.tBodies[0].rows];
   const icons=[...document.querySelectorAll('#fb-rows .file-type-icon')];check('all icon categories rendered',new Set(icons.map(i=>i.dataset.fileType)).size===9);
   await Promise.all(icons.map(i=>i.decode()));
   for(const icon of icons){const r=box(icon),row=icon.closest('tr'),name=row.querySelector('.nm');check('32px displayed file icon',r.width===32&&r.height===32&&icon.complete&&icon.naturalWidth===16);check('metadata-derived file icon',icon.dataset.fileType===fileIconType(name.textContent,icon.classList.contains('dir')));check('icon/name alignment and clearance',Math.abs(r.top+r.height/2-(box(name).top+box(name).height/2))<1&&r.right+8<=box(name).left);}
   check('native visible scrollbar width',style.scrollbarWidth==='auto'&&style.scrollbarGutter==='stable');
   check('contrasting file scrollbar colors',style.scrollbarColor.includes('rgb(187, 187, 187)')&&style.scrollbarColor.includes('rgb(31, 31, 31)'));
   const clearance=box(scroll).left+scroll.clientLeft+scroll.clientWidth-box(table).right;
   check('12px clearance before native scrollbar',Math.abs(clearance-12)<1&&style.paddingInlineEnd==='12px');
   check('long listing actually scrolls internally',scroll.scrollHeight>scroll.clientHeight&&style.overflowY==='auto');
   for(const row of rows){for(let col=0;col<4;col++){const header=head.cells[col],cell=row.cells[col];if(getComputedStyle(header).display==='none'){check('responsive metadata hidden consistently',getComputedStyle(cell).display==='none');continue;}check('shared file header/body columns',Math.abs(box(header).left-box(cell).left)<1&&Math.abs(box(header).width-box(cell).width)<1);check('file column alignment',getComputedStyle(cell).textAlign===(col===1||col===3?'right':'left')&&getComputedStyle(header).textAlign===getComputedStyle(cell).textAlign);}
    const action=row.querySelector('.act-btn');if(action){const cell=row.cells[3];check('Actions right aligned and not clipped',Math.abs(box(action).right-(box(cell).right-parseFloat(getComputedStyle(cell).paddingRight)))<1&&box(action).left>=box(cell).left&&box(action).right<=box(table).right);}
    const name=row.querySelector('.nm');if(name){const range=document.createRange();range.selectNodeContents(name);check('long filename text stays in Name column',[...range.getClientRects()].every(rect=>rect.right<=box(row.cells[0]).right+1&&rect.left>=box(row.cells[0]).left-1));}
    check('row dividers stop before scrollbar clearance',Math.abs(box(row.cells[3]).right-box(table).right)<1&&box(row.cells[3]).right<=box(scroll).left+scroll.clientWidth-11);
   }
   const titleTop=box(header).top,panelBottom=box(document.getElementById('fb-card')).bottom;
   scroll.scrollTop=scroll.scrollHeight;check('scrolling preserves title and panel geometry',Math.abs(box(header).top-titleTop)<1&&Math.abs(box(document.getElementById('fb-card')).bottom-panelBottom)<1);scroll.scrollTop=0;
  }

  if(page==='files'&&innerWidth>820&&innerHeight>=900){
   const panel=box(document.getElementById('fb-card')),tagline=box(document.querySelector('.dashboard-signature')),above=tagline.top-panel.bottom,below=innerHeight-tagline.bottom,listing=document.querySelector('#view-files .fb-scroll');
   check('File Manager gaps around tagline balanced',above>=0&&below>=0&&Math.abs(above-below)<1);
   check('File Manager panel never overlaps tagline',panel.bottom<=tagline.top);
   check('File Manager title position preserved',Math.abs(box(header).top-20)<1&&Math.abs(panel.top-(box(header).bottom+14))<1);
   check('File listing retains its scrolling area',getComputedStyle(listing).overflowY==='auto'&&listing.clientHeight>0&&box(listing).bottom<=panel.bottom);
  }

 }
 check('page header styles consistent',new Set(headingDimensions).size===1);
 if(innerWidth>820){const sidebar=document.querySelector('.sidebar'),aboutButton=document.getElementById('about-e64-button');view('files');sidebar.style.height='480px';check('short sidebar preserves normal scrolling',getComputedStyle(sidebar).overflowY==='auto'&&sidebar.scrollHeight>sidebar.clientHeight);sidebar.scrollTop=sidebar.scrollHeight;check('short sidebar About remains reachable',box(aboutButton).bottom<=box(sidebar).bottom&&box(aboutButton).top>=box(sidebar).top);sidebar.style.height='';sidebar.scrollTop=0;}
 check('sidebar branding version removed',!document.getElementById('sidebar-version'));
 check('sidebar stays very dark',getComputedStyle(document.querySelector('.sidebar')).backgroundColor==='rgb(0, 0, 0)');
 view('files');const drop=document.querySelector('.fb-card'),drag=new DataTransfer();drag.items.add(new File(['fixture'],'drop-check.d64'));drop.dispatchEvent(new DragEvent('dragover',{dataTransfer:drag,bubbles:true,cancelable:true}));check('File Drop visual feedback',drop.classList.contains('over'));drop.dispatchEvent(new DragEvent('dragleave',{dataTransfer:drag,relatedTarget:document.body,bubbles:true}));check('File Drop feedback clears',!drop.classList.contains('over'));check('file info weight and insets',getComputedStyle(document.querySelector('.fb-info')).fontWeight==='600'&&parseFloat(getComputedStyle(document.querySelector('.fb-info')).paddingLeft)>0);check('compact upload info and item count',document.getElementById('fb-note').textContent==='Drag files into this window to upload to the current folder'&&document.getElementById('fb-status').textContent==='');
 {const info=document.querySelector('.fb-info'),note=document.getElementById('fb-note'),crumbs=document.getElementById('fb-crumbs');
 info.scrollIntoView({block:'center'});
 check('instruction occupies former count position',note.parentElement===info&&document.querySelectorAll('#fb-note').length===1&&getComputedStyle(note).textAlign==='right'&&getComputedStyle(note).fontWeight==='600'&&getComputedStyle(note).color==='rgb(221, 136, 85)'&&Math.abs(box(note).right-(box(info).right-parseFloat(getComputedStyle(info).paddingRight)))<1);
 check('Path and instruction never overlap',box(crumbs).right<=box(note).left&&box(note).bottom<box(info).bottom);
 check('orange separator preserved',getComputedStyle(info).borderBottomColor==='rgb(221, 136, 85)'&&getComputedStyle(info).borderBottomWidth==='1px');
 const drives=['SD','USB','USB2','USB3'].map(v=>document.getElementById('fb-vol-'+v));check('fixed SD and USB dimensions with empty short and full labels',drives.every((e,i)=>Math.abs(box(e).width-(i?174:72))<.1&&Math.abs(box(e).height-38)<.1));
 for(const drive of drives){check('drive label fits one line '+drive.id,drive.scrollWidth<=drive.clientWidth&&textRects(drive).length===1);}check('Create BASIC PRG remains available',!document.getElementById('fb-newbasic').hidden);
 const driveWidths=drives.map(e=>box(e).width);for(const drive of drives){const original=drive.textContent;for(const label of ['', 'A', 'ABCDEFGHIJK']){drive.textContent=drive.id==='fb-vol-SD'?'SD':'USB1: '+label;check('drive width constant across label lengths '+drive.id,Math.abs(box(drive).width-driveWidths[drives.indexOf(drive)])<.1&&drive.scrollWidth<=drive.clientWidth);}drive.textContent=original;}
 for(const vol of ['USB','USB2','USB3','SD']){selectFilesVolume(vol);await loadDir('/');check('drive width constant during switching '+vol,drives.every((e,i)=>Math.abs(box(e).width-driveWidths[i])<.1));}
 // Exercise the real toolbar listener, editor, tokeniser and upload API.
 const basicButton=document.getElementById('fb-newbasic');
 for(const vol of ['SD','USB','USB2','USB3']){
  selectFilesVolume(vol);await loadDir('/');
  check('BASIC button visible and enabled '+vol,!basicButton.hidden&&!basicButton.disabled&&box(basicButton).width>0&&box(basicButton).height===38);
  basicButton.focus();basicButton.click();
  await waitFor(()=>!document.getElementById('editor').hidden,'Create BASIC PRG opens editor '+vol);
  check('new BASIC editor context '+vol,document.getElementById('ed-title').textContent==='New BASIC program'&&document.getElementById('ed-path').textContent===vol+':/');
  document.getElementById('ed-close').click();await pause(0);
 }
 setMachine({machine:'Unsupported',caps:{run:[],basic:''}});await loadDir('/');
 check('BASIC unavailable without machine capability',basicButton.hidden);
 setMachine(await (await fetch('/api/status')).json());selectFilesVolume('SD');await loadDir('/');
 basicButton.click();document.getElementById('ed-name').value='browser-basic.prg';
 const listing=document.getElementById('ed-text');listing.value='10 PRINT "E64"';listing.dispatchEvent(new Event('input',{bubbles:true}));
 document.getElementById('ed-save').click();
 await waitFor(()=>document.getElementById('editor').hidden&&document.getElementById('fb-status').textContent==='','BASIC save and directory reload');
 const saved=(await state()).writes.at(-1);
 check('BASIC creation uploads tokenised PRG',saved.vol==='SD'&&saved.path==='/browser-basic.prg'&&parsePrg(new Uint8Array(saved.bytes))?.lines[0].num===10);
 const editing=openBasicEditor({vol:'SD',dir:'/',path:saved.path,name:'browser-basic.prg',parsed:parsePrg(new Uint8Array(saved.bytes))});
 check('existing BASIC listing opens for editing',document.getElementById('ed-title').textContent==='Edit listing'&&listing.value.includes('E64'));
 listing.value='20 PRINT "EDITED"';listing.dispatchEvent(new Event('input',{bubbles:true}));document.getElementById('ed-save').click();
 check('existing BASIC listing saves', (await editing).saved);
 const edited=(await state()).writes.at(-1);check('BASIC edit uploads updated program with overwrite',edited.overwrite&&parsePrg(new Uint8Array(edited.bytes))?.lines[0].num===20);

 check('File Manager has no horizontal page overflow',document.documentElement.scrollWidth<=innerWidth);
 window.scrollTo(0,0);}
 view('configs');
 check('Config summary removed',!document.getElementById('pf-summary'));
 for(const card of document.querySelectorAll('.pf-card')){
  check('no Power-on badge',![...card.querySelectorAll('.pf-badge')].some(e=>e.textContent==='Power-on'));
  check('no redundant machine/technical badge',!card.querySelector('.pf-chip,.pf-detail'));
  const name=card.querySelector('.pf-name'),standard=card.querySelector('.video-standard');
  const footer=card.querySelector('.pf-card-footer'),top=card.querySelector('.pf-top'),start=card.querySelector('.pf-start'),actions=footer.querySelector('.pf-more');
  check('Config name has full row width',Math.abs(box(name).width-box(top).width)<1&&!top.querySelector('.pf-badge'));
  check('Config name/start/footer vertical order',box(name).bottom<=box(start).top&&box(start).bottom<=box(footer).top);
  if(standard){check('video badge at lower left',footer.firstElementChild===standard&&Math.abs(box(standard).left-box(footer).left)<1&&box(name).bottom<=box(standard).top);check('video badge color',getComputedStyle(standard).color===(standard.textContent==='NTSC'?'rgb(0, 136, 255)':'rgb(204, 68, 204)'));const statuses=footer.querySelector('.pf-badges');if(statuses)check('status immediately right of video badge',box(statuses).left>=box(standard).right&&box(statuses).left-box(standard).right<=7);}
  if(actions)check('existing Actions stays at footer right',Math.abs(box(actions).right-box(footer).right)<1);
  if(name.querySelector('.pf-name-text')?.textContent==='Default'){check('factory names fit one line when space permits',box(name).height<=parseFloat(getComputedStyle(name).lineHeight)+1);check('no invented factory actions',!actions);}

  const running=card.querySelector('.pf-running-row .run');if(running&&standard)check('Running directly above left-aligned video badge',Math.abs(box(running).left-box(standard).left)<1&&box(running).bottom<=box(standard).top);
  check('Config actions not clipped',card.scrollWidth<=card.clientWidth+1);
 }
 for(const grid of document.querySelectorAll('.pf-grid')){const cards=[...grid.querySelectorAll('.pf-card')];if(cards.length)check('consistent Config card heights',cards.every(card=>Math.abs(box(card).height-box(cards[0]).height)<1));}
 const unknown=[...document.querySelectorAll('.pf-card')].find(c=>c.querySelector('.pf-name-text')?.textContent==='NTSC in name only');check('standard never guessed from name',unknown&&!unknown.querySelector('.video-standard'));
 view('dashboard');
 const aboutButton=document.getElementById('about-e64-button'),about=document.getElementById('about-e64-popup'),pane=aboutButton.parentElement,info=aboutButton.previousElementSibling;
 check('single About button directly below sidebar System Information',document.querySelectorAll('#about-e64-button').length===1&&aboutButton.closest('.sidebar')&&info.classList.contains('sys-card'));
 for(const page of ['dashboard','files','configs','instructions']){
  view(page);const sidebar=aboutButton.closest('.sidebar');sidebar.scrollTop=0;
  const visible=()=>{const b=box(aboutButton),s=box(sidebar);return b.width>0&&b.height>0&&b.left>=s.left&&b.right<=s.right&&b.top>=Math.max(0,s.top)&&b.bottom<=Math.min(innerHeight,s.bottom);};
  if(innerWidth>820&&innerHeight>=780)check('About visible at normal desktop height '+page,visible());
  if(!visible())aboutButton.scrollIntoView({block:'nearest'});
  check('About accessible from '+page,visible());
  aboutButton.focus();aboutButton.click();check('About opens from '+page,about.open);
  let closed=new Promise(r=>about.addEventListener('close',r,{once:true}));about.querySelector('button').click();await closed;check('About Close focus from '+page,document.activeElement===aboutButton);
  aboutButton.click();closed=new Promise(r=>about.addEventListener('close',r,{once:true}));about.dispatchEvent(new Event('cancel',{cancelable:true}));await closed;check('About Escape focus from '+page,document.activeElement===aboutButton&&!about.open);
 }
 view('dashboard');
 aboutButton.click();header(about);check('About opens',about.open);
 const credit=about.querySelector('.about-e64-content p:last-child');
 check('exact About credits',credit.textContent==='Based on BMC64, powered by VICE and Circle');
 const approvedAbout=rect(box(about));credit.textContent='Derived from BMC64, VICE, & Circle';const priorAbout=rect(box(about));credit.textContent='Based on BMC64, powered by VICE and Circle';
 check('About approved layout unchanged',JSON.stringify(approvedAbout)===JSON.stringify(priorAbout),{current:approvedAbout,previous:priorAbout});
 check('exact two-line approved statement',about.querySelector('.about-e64-statement').innerHTML==='Built out of a love for the Commodore 64,<br>and with thanks to those who keep it alive.');
 for(const p of about.querySelectorAll('.about-e64-content p'))check('About content centered',getComputedStyle(p).textAlign==='center');
 const title=box(document.getElementById('about-e64-title'));check('About title centered',Math.abs(title.left+title.width/2-(box(about).left+box(about).width/2))<1);
 check('About fits viewport',box(about).left>=0&&box(about).right<=innerWidth&&about.scrollWidth<=about.clientWidth);
 let closed=new Promise(r=>about.addEventListener('close',r,{once:true}));about.querySelector('button').click();await closed;check('About Close restores focus',!about.open&&document.activeElement===aboutButton);
 aboutButton.click();closed=new Promise(r=>about.addEventListener('close',r,{once:true}));about.dispatchEvent(new Event('cancel',{cancelable:true}));await closed;check('About Escape restores focus',!about.open&&document.activeElement===aboutButton);
 view('instructions');showInstructions();
 // Exact approved index: original topics plus Hardware and Batch 06 additions.
 const expectedTopics=['drives','sid','mouse','hotkeys','commands','navigation','hardware','storage','memory','advanced'];
 const links=[...document.querySelectorAll('#instructions-index a')];
 check('ten vertical Instruction links',links.length===expectedTopics.length&&links.every((a,i)=>!i||box(a).top>=box(links[i-1]).bottom+8));
 check('Instruction link color/font',links.every(a=>getComputedStyle(a).color==='rgb(0, 136, 255)'&&getComputedStyle(a).fontSize===getComputedStyle(document.querySelector('#view-instructions .page-title-box h1')).fontSize&&+getComputedStyle(a).fontWeight>=600));
 check('Instruction destinations preserved',links.map(a=>a.getAttribute('href')).join('|')===expectedTopics.map(t=>'#/instructions/'+t).join('|'));
 for(const topic of ['drives','roms','ieee488','sid','mouse','hotkeys']){showInstructions(topic);header(document.getElementById('instructions-popup'));}
 showInstructions('sid');const approvedRule=getComputedStyle(document.querySelector('#instructions-content hr'));
 const ruleStyle={borderTopWidth:approvedRule.borderTopWidth,borderTopColor:approvedRule.borderTopColor,marginTop:approvedRule.marginTop,marginBottom:approvedRule.marginBottom};
 for(const [topic,count] of [['drives',2],['roms',2],['ieee488',0],['mouse',1]]){showInstructions(topic);if(topic==='drives'||topic==='roms'){const reference=document.getElementById('ieee-reference'),toggle=document.querySelector('.ieee-reference-toggle');check('reference initially collapsed before geometry '+topic,reference.hidden&&toggle.getAttribute('aria-expanded')==='false');check('Setup accessible while collapsed '+topic,box(document.querySelector('.ieee-setup')).width>0);toggle.click();check('reference visible before geometry '+topic,!reference.hidden&&toggle.getAttribute('aria-expanded')==='true');}const article=document.getElementById('instructions-content'),rules=[...article.querySelectorAll('hr')];check('major section divider count '+topic,rules.length===count);check('no unnecessary bottom divider '+topic,article.lastElementChild.tagName!=='HR');for(const hr of rules){const style=getComputedStyle(hr);check('section divider matches Dual SID '+topic,Object.entries(ruleStyle).every(([name,value])=>style[name]===value)&&style.borderTopWidth==='1px'&&style.borderTopColor==='rgb(221, 136, 85)'&&Math.abs(box(hr).left-box(article).left)<1&&Math.abs(box(hr).right-box(article).right)<1);}}

 const popup=document.getElementById('instructions-popup');showInstructions('hotkeys');
 updateHotkeys(['Warp','None','Swap Joysticks','Menu','Reset','Status','Snapshot','Menu'],'config-a');updateHotkeys(['Changed','None','Swap Joysticks','Menu','Reset','Status','Snapshot','Menu'],'config-b');check('live E64 mappings preserved',document.getElementById('e64-action-0').textContent==='Changed');
 const table=document.getElementById('live-hotkeys'),scroll=table.parentElement;
 const rows=[...table.querySelectorAll('tbody tr')];check('five columns and four pairs',rows.length===4&&rows.every(r=>r.cells.length===5));
 const intersects=(a,b)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
 function hotkeyGeometry(){
  if(table.offsetWidth<=scroll.clientWidth-20)check('complete table centered in popup',Math.abs(box(table).left+box(table).width/2-(box(popup).left+box(popup).width/2))<1);
  else check('mobile table uses horizontal scroll without shrinking',scroll.scrollWidth>scroll.clientWidth&&table.offsetWidth>=602&&getComputedStyle(scroll).overflowX==='auto'&&scroll.tabIndex===0);
  for(const row of rows){
   const t=box(table),r=box(row),key=row.querySelector('.c64-keycap'),k=box(key),left=row.querySelector('.hotkey-divider-left'),right=row.querySelector('.hotkey-divider-right'),l=box(left),q=box(right);
   check('dividers flush with table edges and symmetric',Math.abs(r.left-l.left)<0.1&&Math.abs(q.right-r.right)<0.1&&l.left>=r.left-0.1&&q.right<=r.right+0.1&&Math.abs(r.left-l.left-(q.right-r.right))<0.1);
   check('neither divider protrudes beyond actual table',Math.abs(t.left-l.left)<0.1&&Math.abs(q.right-t.right)<0.1&&l.left>=t.left-0.1&&q.right<=t.right+0.1);
   check('dividers never cross F keycap',l.right<=k.left-15&&q.left>=k.right+15&&!intersects(l,k)&&!intersects(q,k));
   check('16px symmetric keycap clearance',Math.abs(k.left-l.right-16)<1&&Math.abs(q.left-k.right-16)<1&&Math.abs(k.left-l.right-(q.left-k.right))<1);
   check('matching thin orange divider segments',l.height===1&&q.height===1&&getComputedStyle(left).backgroundColor==='rgb(221, 136, 85)'&&getComputedStyle(left).backgroundColor===getComputedStyle(right).backgroundColor);
   check('F keycap stays inside physical column',k.left>=box(row.cells[2]).left&&k.right<=box(row.cells[2]).right&&k.width===96&&k.height===62);
   for(const col of [1,3])for(const e of row.cells[col].querySelectorAll('.hotkey-cell')){
    const rects=textRects(e),c=box(e);
    check('18px heavier descriptions',getComputedStyle(e).fontSize==='18px'&&+getComputedStyle(e).fontWeight>=600);
    check('no F-keycap overlaps adjacent action text',rects.length>0&&rects.every(t=>!intersects(t,k)));
    check('no action text is clipped',e.scrollWidth<=e.clientWidth+1&&e.scrollHeight<=e.clientHeight+1&&rects.every(t=>t.left>=c.left-1&&t.right<=c.right+1&&t.top>=c.top-1&&t.bottom<=c.bottom+1));
    if(col===3)check('JiffyDOS labels stay on one readable line',rects.length===1);
   }
  }
 }
 check('compact table dimensions',table.offsetWidth===602&&rows.every((row,i)=>Math.abs(box(row).height-(i===rows.length-1?108:109))<1));
 // Round 3 deliberately widened Hotkeys from the Round 2 750px layout.
 if(innerWidth===1280)check('compact desktop popup width',Math.abs(box(popup).width-700)<1,rect(box(popup)));
 desktopDialogGeometry(popup,'Hotkeys',700,634);
 if(innerWidth===1280&&innerHeight>=900){check('desktop Hotkeys compact height',box(popup).height<=innerHeight*.88+1);check('desktop Hotkeys has no internal vertical scrolling',popup.scrollHeight<=popup.clientHeight+1&&scroll.scrollHeight<=scroll.clientHeight+1&&popup.querySelector('article').scrollHeight<=popup.querySelector('article').clientHeight+1);check('desktop Hotkeys fits viewport',box(popup).top>=0&&box(popup).bottom<=innerHeight);}
 hotkeyGeometry();
 // Exercise real running-Config strings, including the longest native action names.
 updateHotkeys(['Virtual Keyboard','40/80 Column Key','Status Toggle','Cycle Display','Custom Key 6','Swap Ports','Hard Reset','Flush Disks'],'long-actions');hotkeyGeometry();
 if(scroll.scrollWidth>scroll.clientWidth){scroll.focus();check('mobile reference accepts keyboard focus',document.activeElement===scroll);scroll.scrollLeft=scroll.scrollWidth;hotkeyGeometry();check('mobile can reach far-right SHIFT caps',box(rows[0].cells[4]).right<=box(scroll).right+1);scroll.scrollLeft=0;}
 check('28px Commodore caps',[...table.querySelectorAll('.commodore-keycap')].every(e=>box(e).width===28&&box(e).height===28));check('48x28 CTRL SHIFT caps',[...table.querySelectorAll('.modifier-keycap:not(.commodore-keycap)')].every(e=>box(e).width===48&&box(e).height===28));
 const th=[...table.querySelectorAll('thead th')],first=rows[0];for(const i of [1,2,3]){check('column heading centered',Math.abs(box(th[i]).left+box(th[i]).width/2-(box(first.cells[i]).left+box(first.cells[i]).width/2))<1);}
 check('Hotkeys contains reference only',!popup.querySelector('.function-reference-actions,.config-restore-note'));
 check('4px orange table bottom',getComputedStyle(table).borderBottomWidth==='4px'&&getComputedStyle(table).borderBottomColor==='rgb(221, 136, 85)');
 for(const side of table.querySelectorAll('.e64-side,.jiffy-side'))check('black action background',getComputedStyle(side).backgroundColor==='rgb(0, 0, 0)');
 check('Hotkeys header buttons fit without wrapping',[...popup.querySelectorAll('.e64-popup-header .btn')].every(e=>e.scrollWidth<=e.clientWidth&&textRects(e).length===1));
 if(innerWidth>=1280)check('Hotkeys desktop width',Math.abs(box(popup).width-700)<1);
 const sideLeft=box(table).left-box(popup).left,sideRight=box(popup).right-box(table).right;if(innerWidth>=1280)check('Hotkeys matching side margins',sideLeft>=45&&sideLeft<=50&&sideRight>=45&&sideRight<=50&&Math.abs(sideLeft-sideRight)<1,{sideLeft,sideRight});
 check('Hotkeys approved bottom margin',parseFloat(getComputedStyle(popup).paddingBottom)===45);
 check('matching visible logo heights',box(table.querySelector('.hotkeys-e64-logo')).width===70&&Math.abs(box(table.querySelector('.jiffydos-logo')).height-23.5)<.1);
 const e64=table.querySelector('.hotkeys-e64-wordmark');const baseline=table.cloneNode(true);baseline.removeAttribute('id');baseline.style.position='absolute';baseline.style.visibility='hidden';baseline.style.left='0';baseline.querySelector('.c64-key-heading').replaceWith(document.createTextNode('C64 KEY'));const oldJiffy=baseline.querySelector('.jiffydos-logo');oldJiffy.style.width='75px';oldJiffy.style.height='auto';table.parentElement.append(baseline);const baselineGap=box(baseline.querySelector('.e64-heading')).bottom-box(baseline.querySelector('.hotkeys-e64-wordmark')).bottom;const currentGap=box(th[1]).bottom-box(e64).bottom;check('E64 header divider gap preserved',Math.abs(currentGap-baselineGap)<.1&&Math.abs(currentGap-23.25)<.1,{baselineGap,currentGap});baseline.remove();check('wordmark excludes rainbow bars',box(e64).height===23.5&&getComputedStyle(e64).overflow==='hidden');
 const jiffy=table.querySelector('.jiffydos-logo');check('authentic white JiffyDOS',jiffy.getAttribute('src')==='/jiffydos.png'&&getComputedStyle(jiffy).filter==='invert(1)');
 showInstructions('commands');header(document.getElementById('jiffydos-commands-popup'));check('standalone Commands popup',document.getElementById('jiffydos-commands-popup').open&&!popup.open);document.getElementById('jiffydos-commands-popup').close();await pause(0);
 showInstructions('navigation');header(popup);const navigationHelp=document.getElementById('instructions-content').textContent;check('removed navigation subsections',!navigationHelp.includes('Attach / Remove')&&!navigationHelp.includes('Text-entry fields'));for(const text of ['CRSR Keys','RETURN','← Key','Extended Menu Navigation','HOME','↑ Key','not the cursor-up key','Safe Start','during boot to load the Default Profile'])check('navigation help '+text,navigationHelp.includes(text));check('ten instruction topics linked',document.querySelectorAll('#instructions-index a').length===expectedTopics.length);
 for(const id of ['commands','navigation'])check('independent instruction topic '+id,!!document.querySelector('#instructions-index a[href="#/instructions/'+id+'"]'));
 showInstructions('drives');const toggle=document.querySelector('.ieee-reference-toggle'),reference=document.getElementById('ieee-reference');
 check('IEEE button dimensions match',Math.abs(box(toggle).width-box(document.querySelector('.ieee-setup')).width)<.1&&Math.abs(box(toggle).height-box(document.querySelector('.ieee-setup')).height)<.1);
 check('IEEE initially collapsed',reference.hidden&&toggle.getAttribute('aria-expanded')==='false');toggle.focus();check('IEEE keyboard focus',document.activeElement===toggle);toggle.click();check('IEEE expands',!reference.hidden&&toggle.getAttribute('aria-expanded')==='true');toggle.click();check('IEEE collapses',reference.hidden);toggle.click();
 check('drive descriptions aligned',Math.abs(box(document.querySelector('.drive-section-heading .drive-section-description')).left-box(document.querySelector('.ieee-reference-heading .drive-section-description')).left)<.1);
 check('sixth IEEE column blank', [...reference.querySelectorAll('tr')].every(r=>r.cells[5].textContent==='')&&document.querySelector('.combined-drive-reference th:last-child').textContent==='JiffyDOS ROM');
 const setup=document.querySelector('.ieee-setup');check('Setup right of heading',box(setup).left>=box(toggle).right&&setup.getAttribute('href')==='#/instructions/ieee488');
 const tables=[...document.querySelectorAll('.combined-drive-reference')];check('six combined columns',tables.length===2&&tables.every(t=>[...t.rows].every(r=>r.cells.length===6)));check('all models retained including verified 1570',tables[0].tBodies[0].rows.length===7&&!document.querySelector('.drive-rom-note'));check('all IEEE drives retained',tables[1].tBodies[0].rows.length===7);
 for(const t of tables){for(const row of t.tBodies[0].rows)check('thin reference borders',[...row.cells].every(e=>getComputedStyle(e).borderBottomWidth==='1px'));}
 if(innerWidth<700){const scroller=tables[0].parentElement;scroller.scrollLeft=scroller.scrollWidth;check('combined ROM columns reachable',box(tables[0].rows[0].cells[5]).right<=box(scroller).right+1);}
 // Independent mobile scrollers may be at different offsets after reachability checks.
 for(let i=0;i<6;i++){const a=box(tables[0].rows[0].cells[i]),b=box(tables[1].rows[0].cells[i]),ta=box(tables[0]),tb=box(tables[1]);check('identical equal column boundaries '+i,Math.abs((a.left-ta.left)-(b.left-tb.left))<1&&Math.abs(a.width-ta.width/6)<2&&Math.abs(b.width-tb.width/6)<2,{first:rect(a),second:rect(b),firstTable:rect(ta),secondTable:rect(tb)});}
 if(innerWidth>=1280){check('IEEE heading one line',box(toggle).height<40);for(const p of document.querySelectorAll('.drive-number-group p'))check('mechanism explanation one line',box(p).height<30);}
 location.hash="#/instructions/drives";popup.scrollTop=80;const oldScroll=popup.scrollTop;setup.focus();showInstructions('ieee488');popup.close();await pause(0);check('Setup Close returns to reference route',location.hash==='#/instructions/drives');showInstructions('drives');check('Setup restores expansion and focus',!document.getElementById('ieee-reference').hidden&&document.activeElement===setup);check('Setup restores scroll',popup.scrollTop===oldScroll);
 showInstructions('ieee488');popup.dispatchEvent(new Event('cancel',{cancelable:true}));popup.close();await pause(0);check('Setup Escape returns to reference route',location.hash==='#/instructions/drives');showInstructions('drives');
 showInstructions('storage');check('Storage boot warning and link',document.querySelector('.storage-boot-warning').textContent==='Do not connect external USB storage until E64 has finished booting.'&&!!document.querySelector('#instructions-index a[href="#/instructions/storage"]'));
 desktopDialogGeometry(popup,'Storage',825);check('Storage scrolling retained',getComputedStyle(popup).overflowY==='auto');
 showInstructions('navigation');
 for(const grid of document.querySelectorAll('.navigation-keys')){
  const cells=[...grid.children],colons=cells.filter((_,i)=>i%3===1),descs=cells.filter((_,i)=>i%3===2);
  check('navigation colons and descriptions aligned',colons.every(e=>Math.abs(box(e).left-box(colons[0]).left)<.1)&&descs.every(e=>Math.abs(box(e).left-box(descs[0]).left)<.1));
 }
 const note=document.getElementById('navigation-help-note'),lower=document.querySelector('.navigation-lower-divider'),safe=document.querySelector('.safe-start');
 const finalDivider=document.querySelector('.navigation-footer-divider');check('Safe Start between separators and footer at bottom',box(lower).bottom<=box(safe).top&&box(safe).bottom<=box(finalDivider).top&&box(finalDivider).bottom<=box(note).top&&getComputedStyle(note).textAlign==='center');
 const safeHeading=safe.querySelector('h4'),safeDescription=safe.querySelector('p');check('Safe Start heading and description share line',Math.abs(box(safeHeading).top+box(safeHeading).height/2-box(safeDescription).top-box(safeDescription).height/2)<1);
 check('Safe Start instruction stays on one line',box(safeDescription).height<=32&&getComputedStyle(safeDescription).whiteSpace==='nowrap');check('Safe Start graphic centered',Math.abs(box(safe.querySelector('img')).top+box(safe.querySelector('img')).height/2-box(safeHeading).top-box(safeHeading).height/2)<1);
 showInstructions('navigation');desktopDialogGeometry(popup,'Navigation',690);if(innerWidth>=1280){check('navigation desktop width',box(popup).width>=650&&box(popup).width<=700);check('navigation fits without scrolling',popup.scrollHeight<=popup.clientHeight);}
 view('configs');const factoryName=document.querySelector('.pf-factory-name'),userName=document.querySelector('.pf-name:not(.pf-factory-name)');check('factory and user profile fixtures present',factoryName&&userName);if(factoryName&&userName){for(const prop of ['fontFamily','fontSize','fontWeight','letterSpacing','lineHeight'])check('matching profile name '+prop,getComputedStyle(factoryName)[prop]===getComputedStyle(userName)[prop]);}
 view('instructions');showInstructions('mouse');check('balanced mouse note',document.querySelector('#instructions-content .mouse-compatibility-note').textContent==='Note: The 1351 protocol does not exposethe scroll wheel or middle button.');
 showInstructions('ieee488');check('IEEE redundant footer removed',!document.querySelector('#instructions-content a[href="#/instructions/roms"]')&&document.getElementById('instructions-content').lastElementChild.tagName==='OL');check('redundant ROM navigation removed',!document.querySelector('#instructions-index a[href="#/instructions/roms"]'));check('file paths remain intact',[...document.querySelectorAll('#instructions-content code')].every(e=>getComputedStyle(e).whiteSpace==='nowrap'));check('duplicate mechanism descriptions removed',!document.querySelector('.drive-number-group'));
 const parentClosed=new Promise(r=>popup.addEventListener('close',r,{once:true}));hideInstructions();await parentClosed;
 view('files');let before=(await state()).writes.length;let d=folder();header(d);check('New Folder input auto focus',document.activeElement===d.querySelector('input'));check('no IP address',!d.textContent.match(/\d+\.\d+\.\d+\.\d+/));await cancel(d);check('Cancel restores focus and writes nothing',document.activeElement===document.getElementById('fb-mkdir')&&(await state()).writes.length===before);
 d=folder();d.querySelector('input').value='bad/name';buttons(d).find(b=>b.textContent==='Create').click();check('invalid folder stays open',d.open&&d.querySelector('input').getAttribute('aria-invalid')==='true');await cancel(d);check('invalid folder creates nothing',(await state()).writes.length===before);
 d=folder();const esc=new Promise(r=>d.addEventListener('close',r,{once:true}));d.dispatchEvent(new Event('cancel',{cancelable:true}));await esc;check('Escape cancellation writes nothing',(await state()).writes.length===before);
 d=folder();d.querySelector('input').value='created';buttons(d).find(b=>b.textContent==='Create').click();await waitFor(()=>!d.isConnected&&document.getElementById('fb-status').textContent==='');check('Create uses current volume/path',(await state()).writes.at(-1).path==='/created');
 d=folder();d.querySelector('input').value='entered';d.querySelector('input').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));await waitFor(()=>!d.isConnected&&document.getElementById('fb-status').textContent==='');check('Enter creates folder',(await state()).writes.at(-1).path==='/entered');
 document.getElementById('fb-mkdir').focus();const confirm=confirmE64('Reboot E64?\nUnsaved changes will be lost.','Reboot');d=document.querySelector('dialog.e64-dialog[open]');header(d);await cancel(d);check('confirmation Cancel unchanged',await confirm===false);

 view('instructions');location.hash='#/instructions/hotkeys';showInstructions('hotkeys');
 const commandButton=document.getElementById('hotkeys-commands');commandButton.click();await pause(0);
 const commandDialog=document.getElementById('jiffydos-commands-popup');
 check('Hotkeys opens nonmodal Commands',commandDialog.open&&!commandDialog.matches(':modal')&&popup.hidden);
 const commandBounds=rect(box(commandDialog));
 for(const tab of commandDialog.querySelectorAll('[role="tab"]')){tab.click();desktopDialogGeometry(commandDialog,'Commands '+tab.textContent,620,590);check('Commands table and footer fit '+tab.textContent,commandDialog.scrollHeight<=commandDialog.clientHeight+1&&(innerWidth<1280||document.getElementById('jiffy-command-panel').scrollHeight<=document.getElementById('jiffy-command-panel').clientHeight+1),{dialog:{bounds:rect(box(commandDialog)),scrollHeight:commandDialog.scrollHeight,clientHeight:commandDialog.clientHeight},panel:{bounds:rect(box(document.getElementById('jiffy-command-panel'))),scrollHeight:document.getElementById('jiffy-command-panel').scrollHeight,clientHeight:document.getElementById('jiffy-command-panel').clientHeight},footer:rect(box(commandDialog.querySelector('.jiffy-command-source')))});check('semi-bold tab '+tab.textContent,getComputedStyle(tab).fontWeight==='600');check('orange selected tab with black text '+tab.textContent,getComputedStyle(tab).backgroundColor==='rgb(221, 136, 85)'&&getComputedStyle(tab).color==='rgb(0, 0, 0)');check('Commands outer bounds stable '+tab.textContent,JSON.stringify(rect(box(commandDialog)))===JSON.stringify(commandBounds),rect(box(commandDialog)));}
 // Narrow screens wrap the longer ADVANCED descriptions. The reference panel
 // explicitly supports scrolling; require the final row and footer to remain reachable.
 if(innerWidth<1280){const panel=document.getElementById('jiffy-command-panel'),footer=commandDialog.querySelector('.jiffy-command-source');panel.scrollTop=panel.scrollHeight;const last=panel.querySelector('tbody tr:last-child');check('mobile Commands final row and footer reachable',getComputedStyle(panel).overflowY==='auto'&&box(last).bottom<=box(panel).top+panel.clientHeight+1&&box(footer).top>=box(panel).bottom-1&&box(footer).bottom<=box(commandDialog).bottom,{last:rect(box(last)),panel:rect(box(panel)),footer:rect(box(footer))});panel.scrollTop=0;}
 const commandTabs=[...commandDialog.querySelectorAll('[role="tab"]')];check('equal Commands tab dimensions',commandTabs.every(t=>Math.abs(box(t).width-box(commandTabs[0]).width)<1&&Math.abs(box(t).height-box(commandTabs[0]).height)<1));
 commandDialog.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));await pause(0);
 check('Commands Escape returns to Hotkeys',!commandDialog.open&&popup.open&&!popup.hidden&&document.activeElement===commandButton);
 for(const link of document.querySelectorAll('.sidebar .nav-item[data-view]')){
  location.hash='#/instructions/hotkeys';view('instructions');showInstructions('hotkeys');
  // Browser hit testing requires viewport coordinates. Help focus can scroll
  // the normal-flow mobile sidebar away; bring the actual target into view.
  link.scrollIntoView({block:'start',inline:'nearest'});
  const middle=box(link);check('sidebar hit target while help open',link.contains(document.elementFromPoint(middle.left+middle.width/2,middle.top+middle.height/2)),{link:rect(middle),scrollY,hit:document.elementFromPoint(middle.left+middle.width/2,middle.top+middle.height/2)?.outerHTML.slice(0,180)});
  link.click();await pause(0);check('sidebar closes help',!popup.open&&!commandDialog.open);check('sidebar navigation hash',location.hash===link.getAttribute('href'));check('sidebar focus',document.activeElement===link);
 }
 view('files');const destructive=confirmE64('Delete file?','Delete');const actualModal=document.querySelector('dialog.e64-dialog[open]');
 check('destructive confirmation stays genuinely modal',actualModal.matches(':modal'));
 const sidebarLink=document.querySelector('.sidebar .nav-item[data-view]'),sidebarBox=box(sidebarLink);check('modal blocks sidebar hit target',!sidebarLink.contains(document.elementFromPoint(sidebarBox.left+sidebarBox.width/2,sidebarBox.top+sidebarBox.height/2)));await cancel(actualModal);await destructive;
 const edit=openEditor({vol:'SD',path:'/notes.txt',name:'notes.txt'});await waitFor(()=>!document.getElementById('editor').hidden);header(document.querySelector('.ed-dialog'));document.getElementById('ed-close').click();await edit;
 check('page color',getComputedStyle(document.body).backgroundColor==='rgb(20, 20, 20)');
 for(const e of document.querySelectorAll('.card,.pf-card,.sys-card,.page-title-box'))check('shared near-black panel color',getComputedStyle(e).backgroundColor==='rgb(0, 0, 0)');

 for(const verb of ['Copy','Move']){
 view('files');selectFilesVolume('SD');await loadDir('/');
 const row=[...document.querySelectorAll('#fb-rows tr')].find(r=>r.textContent.includes('demo.d64'));row.querySelector('.act-btn').click();
 [...document.querySelectorAll('.act-item')].find(b=>b.textContent===verb+' To >').click();
 await waitFor(()=>document.querySelector('.destination-dialog[open]'));
 const d=document.querySelector('.destination-dialog'),sel=d.querySelector('select'),action=verb;
 await waitFor(()=>!d.querySelector('.destination-current').disabled);
 check(action+' root wording',d.querySelector('.destination-current').textContent.startsWith(action+' to the root of: '));
 check(action+' computed selector dimensions',box(sel).width===230,{bounds:rect(box(sel)),width:getComputedStyle(sel).width,minWidth:getComputedStyle(sel).minWidth,maxWidth:getComputedStyle(sel).maxWidth,flex:getComputedStyle(sel).flex,boxSizing:getComputedStyle(sel).boxSizing,padding:getComputedStyle(sel).padding,parent:rect(box(sel.parentElement)),parentDisplay:getComputedStyle(sel.parentElement).display,appearance:getComputedStyle(sel).appearance});
 const sizes=[...d.querySelectorAll('.destination-controls .btn')].map(e=>rect(box(e)));
 check(action+' fixed dropdown and matching controls',Math.abs(box(sel).width-230)<.1&&sizes.every(r=>Math.abs(r.height-38)<.1)&&sizes.slice(1).every(r=>Math.abs(r.width-72)<.1));
 const font=getComputedStyle(sel),ctx=document.createElement('canvas').getContext('2d');ctx.font=font.font;
 const widest=Math.max(...[...'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'].map(c=>ctx.measureText(c).width));
 const budget=ctx.measureText('USB2: ').width+11*widest+parseFloat(font.paddingLeft)+parseFloat(font.paddingRight)+2+32;
 check(action+' widest 11-character label and arrow fit',budget<=box(sel).width,{budget,width:box(sel).width,example:ctx.measureText('USB2: EXTERNALUSB').width,arrowAllowance:32});
 const width=box(sel).width;for(const opt of sel.options){sel.value=opt.value;sel.dispatchEvent(new Event('change'));await waitFor(()=>!d.querySelector('.destination-current').disabled);check(action+' dropdown constant across drives',box(sel).width===width);}
 for(const label of ['USB1: BMC64DATA','USB2: EXTERNALUSB','USB3: ABCDEFGHIJK','USB1']){
  const opt=sel.options[0],original=opt.textContent;opt.textContent=label;sel.value=opt.value;
  const required=ctx.measureText(label).width+parseFloat(font.paddingLeft)+parseFloat(font.paddingRight)+2+32;
  check(action+' complete label fits '+label,box(sel).width===230&&required<=box(sel).width,{label,required,bounds:rect(box(sel)),arrowAllowance:32});opt.textContent=original;
 }
 const folder=buttons(d.querySelector('.destination-folders')).find(b=>b.textContent==='demos');folder.click();await waitFor(()=>!d.querySelector('.destination-current').disabled&&d.querySelector('.destination-current').textContent.includes('/demos'));
 check(action+' folder navigation works',!buttons(d.querySelector('.destination-controls')).find(b=>b.textContent==='↑ Up').disabled);
 buttons(d.querySelector('.destination-controls')).find(b=>b.textContent==='↑ Up').click();await waitFor(()=>!d.querySelector('.destination-current').disabled&&d.querySelector('.destination-current').textContent.includes('to the root of:'));
 check(action+' root remains selectable',!d.querySelector('.destination-current').disabled&&!buttons(d.querySelector('.destination-controls')).find(b=>b.textContent===action).disabled);
 await cancel(d);
 }
}catch(error){results.push({name:'validation exception',pass:false,error:String(error)});}
// Always prepare the requested screen, even after a validation failure.
const screen=new URL(location.href).searchParams.get('screen');let captureReady=false;
try{
 await Promise.all([...document.querySelectorAll('dialog[open]')].map(d=>new Promise(resolve=>{d.addEventListener('close',resolve,{once:true});d.close();})));
 if(!document.getElementById('editor').hidden)document.getElementById('ed-close').click();
 await pause(0);await waitFor(()=>!document.querySelector('dialog[open]')&&document.getElementById('editor').hidden);
 document.getElementById('pf-restart').hidden=true;
 const help=['hotkeys','roms','drives','ieee488','sid','mouse','navigation','storage'];
 const expectedView=help.includes(screen)||screen==='commands'?'instructions':['new-folder','editor','destination','move-destination'].includes(screen)?'files':['about','confirmation','easter-egg','rainbow'].includes(screen)?'dashboard':screen;
 view(expectedView);
 if(help.includes(screen))showInstructions(screen);
 else if(screen==='datasette'){setDatasetteVisible(true);await waitFor(()=>document.getElementById('tape-counter').textContent==='123');}
 else if(screen==='instructions')showInstructions();
 else if(screen==='rainbow'){}
 else if(screen==='about')document.getElementById('about-e64-button').click();
 else if(screen==='new-folder')folder();
 else if(screen==='commands'){showInstructions('commands');}
 else if(screen==='confirmation')confirmE64('Reboot E64?\nUnsaved changes will be lost.','Reboot');
 else if(screen==='editor'){openEditor({vol:'SD',path:'/notes.txt',name:'notes.txt'});await waitFor(()=>!document.getElementById('editor').hidden&&document.getElementById('ed-hint').textContent!=='Loading…');}
 else if(screen==='easter-egg'){document.getElementById('logo-toggle').click();}
 else if(screen==='destination'||screen==='move-destination'){const row=[...document.querySelectorAll('#fb-rows tr')].find(r=>r.textContent.includes('demo.d64'));row.querySelector('.act-btn').click();[...document.querySelectorAll('.act-item')].find(b=>b.textContent===(screen==='move-destination'?'Move To >':'Copy To >')).click();await waitFor(()=>document.querySelector('.destination-dialog[open]'));
 }
 await document.fonts.ready;await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
 const visible=[...document.querySelectorAll('section.view')].filter(e=>!e.hidden).map(e=>e.id),dialogs=[...document.querySelectorAll('dialog[open]')];
 const popup=document.getElementById('instructions-popup');
 const expectedDialogs=screen==='commands'?['jiffydos-commands-popup']:help.includes(screen)?['instructions-popup']:screen==='about'?['about-e64-popup']:['new-folder','confirmation','destination','move-destination'].includes(screen)?['dynamic']:[];
 const actualDialogs=dialogs.map(d=>d.id||'dynamic');
 const correctOverlay=screen==='editor'?!document.getElementById('editor').hidden&&document.getElementById('ed-title').textContent==='notes.txt':document.getElementById('editor').hidden;
 const correctTopic=!help.includes(screen)||popup.dataset.topic===(screen==='roms'?'drives':screen);
 captureReady=visible.length===1&&visible[0]==='view-'+expectedView&&actualDialogs.join('|')===expectedDialogs.join('|')&&correctOverlay&&correctTopic;
 check('requested screenshot view and overlay verified',captureReady);
 document.documentElement.dataset.captureScreen=captureReady?screen:'UNVERIFIED';
}catch(error){results.push({name:'screenshot preparation exception',pass:false,error:String(error)});}
await fetch('/__results',{method:'POST',body:JSON.stringify({screen,capture_ready:captureReady,checks:results})});
'''
ready=Event();results=[];capture_state={};writes=[];dirs=set()
html=(ASSETS/'index.html').read_text().replace('<script type="module" src="/js/app.js"></script>','<script type="module">'+SCRIPT+'</script><img hidden src="/__hold" alt="">')
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ASSETS),**kw)
 def log_message(self,*a):pass
 def send_json(self,payload,status=200):
  data=json.dumps(payload).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
 def do_GET(self):
  u=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(u.query)
  if u.path=='/__hold':
   ready.wait(45);self.send_response(200);self.send_header('Content-Type','image/svg+xml');self.end_headers();self.wfile.write(b'<svg xmlns="http://www.w3.org/2000/svg"/>');return
  if u.path=='/__preview':
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(html.encode());return
  if u.path=='/__state':return self.send_json({'writes':writes})
  if u.path=='/api/datasette':return self.send_json({'supported':1,'attached':1,'writable':1,'filename':'USB:/tapes/Browser fixture.tap','counter':123,'mode':1,'motor':0,'pending':0,'error':0})
  if u.path=='/api/status':return self.send_json({'machine':'C64','version':'1.0.1','config_id':'browser','config_name':'Browser Check','hostname':'e64','uptime_secs':3723,'ip':'192.0.2.64','net_status':1,'net_text':'Connected','soc_temp_c':43,'throttled':0,'warp':0,'reu':1,'reu_size':512,'ieee488':0,'drives':[1542,0,0,0],'hotkeys':['Warp','Status Toggle','Swap Ports','Menu','Virtual Keyboard','40/80 Column Key','Hard Reset','Flush Disks'],'caps':{'run':['d64','d71','d81','d82','g64','x64','t64','tap','prg','p00','crt'],'basic':'v2'}})
  if u.path in ['/api/volumes','/api/fs/volumes']:return self.send_json({'volumes':[{'id':v,'label':label,'total_kb':1024,'free_kb':512} for v,label in [('SD',''),('USB','BMC64DATA'),('USB2','EXTERNALUSB'),('USB3','ABCDEFGHIJK')]]})
  if u.path=='/api/configs/protection':return self.send_json({'ready':True,'protected':['_factory-ntsc','_factory-pal']})
  if u.path=='/api/configs/deleted':return self.send_json({'ready':True,'deleted':[]})
  if u.path=='/api/fs/list':
   path=q.get('path',['/'])[0];entries=[{'name':name,'dir':True} for name in ['browser','pal-fixture','unknown-fixture']] if path=='/configs' else ([{'name':d,'dir':True,'mtime':'2026-11-09T12:34:56'} for d in sorted(dirs)]+[{'name':n,'size':123,'mtime':'2026-11-09T12:34:56'} for n in ['disk.DHD','cart.CRT','tape.T64','program.PRG','state.VSF','chip.ROM','unknown.BIN']]+[{'name':'demo.d64','size':174848,'mtime':'2026-11-09T12:34:56'},{'name':'notes.txt','size':20,'edit':True,'mtime':'2026-11-09T12:34:56'},{'name':'A-very-long-filename-with-no-clipping-'+('long-name-'*10)+'.d64','size':1048576,'mtime':'2026-11-09T12:34:56'}]) if path=='/' else []
   return self.send_json({'vol':q.get('vol',['SD'])[0],'path':path,'entries':entries})
  if u.path=='/api/fs/download':
   path=q.get('path',[''])[0];text={'/configs/browser/config.txt':'name=Browser Check\nmachine=C64/NTSC/HDMI/VICE 768x525 @ 59.827 Hz\n','/configs/pal-fixture/config.txt':'name=PAL Metadata\nmachine=C64/PAL/HDMI/VICE 720x576 @ 50 Hz\n','/configs/unknown-fixture/config.txt':'name=NTSC in name only\nmachine=C64\n','/configs/active.txt':'config=browser\n','/notes.txt':'E64 browser fixture\n'}.get(path,'');self.send_response(200);self.end_headers();self.wfile.write(text.encode());return
  return super().do_GET()
 def do_POST(self):
  u=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(u.query);body=self.rfile.read(int(self.headers.get('Content-Length',0)))
  if u.path=='/__results':
   payload=json.loads(body);results.extend(payload['checks']);capture_state.update(payload);ready.set();return self.send_json({'ok':True})
  if u.path=='/api/fs/upload':
   path=q.get('path',[''])[0]
   if path.lower().startswith('/firmware/'):return self.send_json({'error':'that path is protected'},403)
   writes.append({'vol':q.get('vol',[''])[0],'path':path,'bytes':list(body),'overwrite':q.get('overwrite',['0'])[0]=='1'});return self.send_json({'ok':True})
  if u.path=='/api/fs/mkdir':
   path=q.get('path',[''])[0];dirs.add(path.lstrip('/'));writes.append({'vol':q.get('vol',[''])[0],'path':path});return self.send_json({'ok':True})
  return self.send_json({'error':'Unexpected mutation'},400)
def fallback(reason):
 records=[];page=OUT/'startup-probe.html';page.write_text('<p>Firefox startup probe only; full UI checks require the normal-terminal localhost harness.</p>')
 for w,h in ([(1280,1024),(1280,900)] if args.desktop_only else [(1280,1024),(1280,900),(390,780)]):
  profile=OUT/f'probe-{w}x{h}';profile.mkdir(exist_ok=True)
  try:
   run=subprocess.run(['firefox','--headless','--no-remote','--profile',str(profile),'--window-size',f'{w},{h}','--screenshot',str(OUT/f'PROBE-ONLY-{w}x{h}.png'),page.as_uri()],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
   (OUT/f'probe-{w}x{h}.log').write_text(run.stdout+'\nExit: '+str(run.returncode)+'\n');records.append({'width':w,'height':h,'status':'blocked','reason':reason,'firefox_exit':run.returncode,'ui_checks':[]})
  except subprocess.TimeoutExpired:records.append({'width':w,'height':h,'status':'blocked','reason':reason+'; Firefox startup timed out','ui_checks':[]})
 (OUT/'results.json').write_text(json.dumps(records,indent=2)+'\n');print('BLOCKED:',reason);print('Logs:',OUT);return 2
try:server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
except PermissionError as error:raise SystemExit(fallback(str(error)))
Thread(target=server.serve_forever,daemon=True).start();records=[]
try:
 screens=['datasette','dashboard','files','configs','instructions','hotkeys','roms','drives','ieee488','sid','mouse','navigation','new-folder','commands','editor','confirmation','destination','move-destination','storage','easter-egg','rainbow','about'] if args.screen=='all' else [args.screen]
 for w,h in ([(1280,1024),(1280,900)] if args.desktop_only else [(1280,1024),(1280,900),(390,780)]):
  for screen in screens:
   ready.clear();results.clear();capture_state.clear();writes.clear();dirs.clear();dirs.update(['demos','ROMs.d64','nested.ROM']+[f'folder-{n:02d}' for n in range(40)]);profile=OUT/f'firefox-{w}x{h}';profile.mkdir(exist_ok=True);shot=OUT/f'{screen}-{w}x{h}.png';temporary=OUT/f'UNVERIFIED-{screen}-{w}x{h}.png'
   try:
    run=subprocess.run(['firefox','--headless','--no-remote','--profile',str(profile),'--window-size',f'{w},{h}','--screenshot',str(temporary),f'http://127.0.0.1:{server.server_port}/__preview?screen={screen}'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
    (OUT/f'{screen}-{w}x{h}.log').write_text(run.stdout)
    verified=capture_state.get('screen')==screen and capture_state.get('capture_ready') is True
    if verified and temporary.exists():temporary.rename(shot)
    passed=run.returncode==0 and verified and bool(results) and all(c['pass'] for c in results) and shot.exists()
    records.append({'width':w,'height':h,'screen':screen,'status':'passed' if passed else 'failed','exit_code':run.returncode,'capture_ready':verified,'checks':list(results),'screenshot':str(shot) if shot.exists() else None,'unverified_capture':str(temporary) if temporary.exists() else None});print('PASS' if passed else 'FAIL',w,h,screen,flush=True)
   except subprocess.TimeoutExpired:records.append({'width':w,'height':h,'screen':screen,'status':'blocked','reason':'Firefox timed out'})
 (OUT/'results.json').write_text(json.dumps(records,indent=2)+'\n')
finally:server.shutdown();server.server_close()
print('Screenshots and results:',OUT)
raise SystemExit(0 if records and all(r['status']=='passed' for r in records) else 1)
