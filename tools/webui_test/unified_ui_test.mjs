import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {promptE64,confirmE64} from '../../src/webui/assets/js/dialog.js';
import {normPath} from '../../src/webui/assets/js/util.js';
class Node {
 constructor(tag=''){this.tag=tag;this.children=[];this.events={};this.attrs={};this.dataset={};this._text='';this.isConnected=true;this.open=false;this.returnValue='';}
 append(...items){for(const n of items){this.children.push(n);n.parent=this;}}
 get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
 set textContent(v){this._text=String(v);this.children=[];}
 setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(k,fn){(this.events[k] ||= []).push(fn);}
 fire(k,e={}){for(const fn of this.events[k] || [])fn(e);}
 focus(){document.activeElement=this;}
 select(){}
 showModal(){this.open=true;}
 close(v=''){if(!this.open)return;this.returnValue=v;this.open=false;this.fire('close');}
 remove(){this.isConnected=false;if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
}
const before=globalThis.document,body=new Node('body'),opener=new Node('button'),nodes=new Map();
const $=id=>{if(!nodes.has(id))nodes.set(id,new Node());return nodes.get(id);};
globalThis.document={body,activeElement:opener,createElement:tag=>new Node(tag)};
let calls=[],fail=false;
const files=fs.readFileSync('src/webui/assets/js/files.js','utf8');
const start=files.indexOf('async function makeFolder()');const fn=files.slice(start,files.indexOf('\n}',start)+2);
const context=vm.createContext({promptE64,$,normPath,fbVol:'USB',fbPath:'/disks',hasSlash:name=>/[\/\\]/.test(name),showError:text=>{$('fb-status').textContent=text;},api:{makeDir:async(...args)=>{calls.push(args);if(fail)throw Error('storage unavailable');}},loadDir:async()=>{$("fb-status").textContent="3 items";}});
vm.runInContext(fn,context);
const open=()=>{document.activeElement=opener;const work=vm.runInContext('makeFolder()',context);const dialog=body.children.at(-1);return {work,dialog,form:dialog.children[1],input:dialog.children[1].children[1]};};
const submit=f=>f.fire('submit',{preventDefault(){}});
try {
 let t=open();assert.equal(t.dialog.children[0].className,'e64-popup-header');assert.equal(t.dialog.children[0].children[0].textContent,'New Folder');assert.equal(t.form.children[0].textContent,'Enter the new folder name:');assert.equal(document.activeElement,t.input);
 assert.ok(!t.dialog.textContent.match(/\d+\.\d+\.\d+\.\d+/));
 t.form.children[3].children[0].onclick();await t.work;assert.equal(calls.length,0);assert.equal(document.activeElement,opener);
 t=open();let prevented=false;t.dialog.fire('cancel',{preventDefault(){prevented=true;}});await t.work;assert.ok(prevented);assert.equal(calls.length,0);
 t=open();t.dialog.children[0].children[1].onclick();await t.work;assert.equal(calls.length,0);
 for(const bad of ['', '  ','.','..','a/b','a\\b']){
  t=open();t.input.value=bad;submit(t.form);assert.equal(t.dialog.open,true);assert.equal(t.input.attrs['aria-invalid'],'true');assert.equal(document.activeElement,t.input);assert.equal(calls.length,0);t.form.children[3].children[0].onclick();await t.work;
 }
 t=open();t.input.value=' demos ';assert.equal(t.form.children[3].children[1].type,'submit');submit(t.form);await t.work;assert.deepEqual(calls,[['USB','/disks/demos']]);assert.equal($('fb-status').textContent,'3 items');assert.equal(document.activeElement,opener);
 calls=[];t=open();t.input.value='enter';t.input.fire('keydown',{key:'Enter',isComposing:false,preventDefault(){}});await t.work;assert.deepEqual(calls,[['USB','/disks/enter']]);
 calls=[];t=open();t.input.value='compose';t.input.fire('keydown',{key:'Enter',isComposing:true,preventDefault(){throw Error('IME must not submit');}});assert.equal(t.dialog.open,true);t.dialog.close();await t.work;assert.equal(calls.length,0);
 fail=true;t=open();t.input.value='failure';submit(t.form);await t.work;assert.ok($('fb-status').textContent.includes('storage unavailable'));
 const confirm=confirmE64('Reboot E64?\nUnsaved changes will be lost.','Reboot');const d=body.children.at(-1);assert.equal(d.children[0].children[0].textContent,'Reboot E64?');d.fire('cancel',{preventDefault(){}});assert.equal(await confirm,false);
} finally {globalThis.document=before;}
const instructions=fs.readFileSync('src/webui/assets/js/instructions.js','utf8'),css=fs.readFileSync('src/webui/assets/style.css','utf8'),html=fs.readFileSync('src/webui/assets/index.html','utf8');
assert.ok(instructions.includes('table([...referenceHeaders.slice(0, 5), ""], ieeeReference'));
assert.ok(!instructions.includes('rom-notes') && !instructions.includes('Drive ROMs Located in:'));
assert.ok(!instructions.includes('"—"'));
for(const value of ['#000000','#141414','#1F1F1F','#EEEEEE','#DD8855','#0088FF','#444444'])assert.ok(css.includes(value));
assert.ok(css.includes('border-bottom: 4px solid var(--separator)'));
assert.ok(css.includes('font-size: 18px; font-weight: 600'));
assert.ok(css.includes('flex-direction: column; align-items: flex-start; gap: 12px'));
for(const id of ['instructions-title','jiffy-commands-title','ed-title','pf-restart-title'])assert.ok(html.includes('id="'+id+'"'));
for(const path of ['files.js','configs.js','dialog.js'])assert.ok(!/\bprompt\(/.test(fs.readFileSync('src/webui/assets/js/'+path,'utf8')));
console.log('PASS: New Folder Cancel/Close/Escape/Create/Enter, validation, IME, API errors, current-volume paths and focus; shared popup headers/colors, vertical navigation and ROM columns');

assert.ok(css.includes('.rom-reference { --rom-drive-column-width: 24%; }'));
assert.ok(css.includes('.rom-reference th:first-child { width: var(--rom-drive-column-width); }'));
assert.ok(!/\.ieee-rom-reference th:first-child/.test(css), 'IEEE must share the Drive column width');
assert.ok(instructions.includes('table(referenceHeaders, standardReference'));
assert.ok(instructions.includes('table([...referenceHeaders.slice(0, 5), ""], ieeeReference'));
console.log('PASS: ROM tables share Drive column sizing and Standard ROM start; standard retains three columns, IEEE exactly two');

for(const [view,title,icon] of [['dashboard','Dashboard','▦'],['files','File Manager','▤'],['configs','Configs','☰'],['instructions','Instructions','book-icon']]){
 const viewHTML=html.match(new RegExp('<section class="view" id="view-'+view+'"[\\s\\S]*?<\\/section>'))[0];
 assert.match(viewHTML,new RegExp('<header class="page-title-box"><h1>[\\s\\S]*?'+title+'<\\/h1><\\/header>'));
 assert.ok(viewHTML.includes(icon));assert.equal([...viewHTML.matchAll(/class="page-title-box"/g)].length,1);
 assert.ok(!new RegExp('<h2[^>]*>(?:<[^>]*>[^<]*<\\/[^>]+>)*'+title+'<\\/h2>').test(viewHTML));
}
assert.ok(!html.includes('pf-summary')&&!html.includes('sidebar-version'));
assert.ok(!fs.readFileSync('src/webui/assets/js/dashboard.js','utf8').includes('sidebar-version'));
for(const [name,value] of [['page-background','#141414'],['panel-background','var(--c64-black)'],['popup-background','var(--c64-black)'],['sidebar-background','var(--c64-black)']])assert.ok(css.includes('--'+name+': '+value+';'));
assert.ok(css.includes('font-size: var(--page-title-size); font-weight: 600'));
assert.ok(css.includes('.sidebar > .nav .nav-item { height: 42px;'));
assert.ok(css.includes('.about-e64-button { height: 42px; flex: none; }'));
assert.ok(css.includes('.side-drop { min-height: 80px;'));
console.log('PASS: four shared page title boxes/icons, shared page/panel/popup/sidebar colors, title-sized Instructions links and compact sidebar contracts');

// Execute the unchanged production drop handlers on the compact target.
const dropFns=['dropTarget','droppedFiles'].map(name=>{const start=files.indexOf('function '+name+'(');return files.slice(start,files.indexOf('\n}',start)+2);}).join('\n');
const handlers={},classes=new Set(),target={addEventListener:(name,fn)=>handlers[name]=fn,classList:{add:c=>classes.add(c),remove:c=>classes.delete(c)},contains:child=>child==='inside'};
let uploaded=null,prevented=0;
const dropContext=vm.createContext({target,$,uploadFiles:items=>uploaded=items});vm.runInContext(dropFns+'\ndropTarget(target);',dropContext);
handlers.dragover({dataTransfer:{types:['text/plain']},preventDefault(){throw Error('text is not an upload');}});assert.equal(classes.size,0);
handlers.dragover({dataTransfer:{types:['Files']},preventDefault(){prevented++;}});assert.ok(classes.has('over'));
handlers.dragleave({relatedTarget:'inside'});assert.ok(classes.has('over'));handlers.dragleave({relatedTarget:null});assert.ok(!classes.has('over'));
const payload=[{name:'disk.d64'}];handlers.drop({dataTransfer:{types:['Files'],files:payload},preventDefault(){prevented++;}});assert.equal(uploaded,payload);assert.equal(prevented,2);assert.ok(!classes.has('over'));
console.log('PASS: compact File Drop preserves file-only drag feedback, child transitions, drop payload and upload handler');

assert.ok(css.includes('--tagline-bottom-gap: 10px;'));
assert.ok(css.includes('--tagline-font-size: 13px;'));
assert.ok(css.includes('--tagline-line-height: 1.55;'));
assert.ok(css.includes('padding-bottom: calc(var(--tagline-bottom-gap) * 2 + var(--tagline-font-size) * var(--tagline-line-height))'));
assert.ok(css.includes('#view-files:not([hidden]) { display: flex; flex-direction: column; flex: 1; min-height: 0; }'));
assert.ok(css.includes('#view-files .fb-card { flex: 1; height: auto; max-height: none; min-height: 0; }'));
assert.ok(css.includes('bottom: var(--tagline-bottom-gap);'));
console.log('PASS: desktop File Manager flex height reserves two equal tagline gaps; title/sidebar/mobile and listing controls remain unchanged');

for(const column of ['name','size','mod','act'])assert.ok(html.includes('class="col-'+column+'" scope="col"'));
assert.ok(files.includes('tdName.className = "col-name";'));
assert.ok(css.includes('scrollbar-width: auto; scrollbar-color: var(--file-scrollbar-thumb) var(--file-scrollbar-track); scrollbar-gutter: stable; padding-inline-end: 12px;'));
assert.ok(css.includes('.fb-table .col-size { width: var(--file-size-width); text-align: right; }'));
assert.ok(css.includes('.fb-table .col-mod { width: var(--file-modified-width); text-align: left; }'));
assert.ok(css.includes('.fb-table .col-act { width: var(--file-actions-width); text-align: right; }'));
console.log('PASS: visible native scrollbar, 12px content clearance and shared fixed table column alignment');

// Intentional toolbar/power/sidebar refinements retain existing controls.
assert.ok(css.includes('.pf-head #pf-refresh { margin-left: auto; }'));
assert.ok(css.includes('.pf-head #pf-restore { margin-left: 0; }'));
assert.ok(css.includes('.sidebar-bottom { margin-top: auto; margin-bottom: 32px;'));
assert.ok(css.includes('.nav-bottom { flex-direction: row; flex-wrap: wrap; padding: 0; gap: 8px; }'));
assert.ok(css.includes('justify-content: center; border: 1px solid var(--border); border-radius: 9px; background: var(--panel);'));
console.log('PASS: Refresh right alignment, separated themed power buttons, parent-group 32px bottom clearance; IDs/icons/handlers preserved');
