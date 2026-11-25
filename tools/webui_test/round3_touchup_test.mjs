// Execute the production picker against empty and populated roots, without DOM libraries.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {normPath,parentPath} from '../../src/webui/assets/js/util.js';
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.events={};this.style={};this.disabled=false;this.isConnected=true;}
 set textContent(t){this.text=t;this.children=[];} get textContent(){return (this.text||'')+this.children.map(e=>e.textContent).join('');}
 append(...children){this.children.push(...children);} appendChild(e){this.children.push(e);}
 setAttribute(){} addEventListener(k,f){(this.events[k]??=[]).push(f);}
 fire(k){if(k==='click'&&this.disabled)return;for(const f of this.events[k]||[])f();}
 showModal(){this.open=true;} close(){this.open=false;this.fire('close');} remove(){this.isConnected=false;} focus(){}
}
const source=fs.readFileSync('src/webui/assets/js/files.js','utf8');
const picker=source.slice(source.indexOf('function pickDestination('),source.indexOf('\nasync function transferEntry('));
const flush=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
for(const verb of ['Move','Copy'])for(const vol of ['SD','USB','USB2','USB3'])for(const count of [0,1,4]){
 const document={body:new Element(),activeElement:new Element(),createElement:t=>new Element(t)};
 const calls=[];const context=vm.createContext({document,normPath,parentPath,volumeLabel:v=>v==='USB'?'USB1: BMC64DATA':v==='USB2'?'USB2: EXTERNALUSB':v,createFileIcon:()=>new Element(),createPopupHeader:()=>new Element(),api:{listDir:async(path,v)=>{calls.push([path,v]);return {entries:Array.from({length:count},(_,i)=>({name:'folder'+i,dir:true}))};}}});
 vm.runInContext(`let fbVol=${JSON.stringify(vol)};let availableVolumes=['SD','USB','USB2','USB3'];${picker};globalThis.pick=pickDestination`,context);
 const pending=context.pick(verb,'payload',true);await flush();const dialog=document.body.children[0];
 const current=dialog.children.find(e=>e.className==='btn destination-current');
 const folders=dialog.children.find(e=>e.className==='destination-folders');
 assert.equal(folders.children.length,count||1);assert.equal(current.disabled,false);assert.equal(current.textContent,verb+' to the root of: '+(vol==='USB'?'USB1: BMC64DATA':vol==='USB2'?'USB2: EXTERNALUSB':vol)+':/');
 current.fire('click');assert.deepEqual(JSON.parse(JSON.stringify(await pending)),{vol,folder:'/'});assert.deepEqual(calls,[['/',vol]]);
 // Browsing folders and Up remains independent of choosing the current directory.
 if(count){const again=context.pick(verb,'payload',true);await flush();const d=document.body.children.at(-1),list=d.children.find(e=>e.className==='destination-folders'),bar=d.children.at(-1);list.children[0].fire('click');await flush();assert.equal(calls.at(-1)[0],'/folder0');assert(d.children.find(e=>e.className==='btn destination-current').textContent.startsWith('Use this directory: '));bar.children[1].fire('click');await flush();assert.equal(calls.at(-1)[0],'/');bar.children[3].fire('click');assert.equal((await again).folder,'/');}
}
// A failed listing cannot select a stale directory.
{
 const document={body:new Element(),createElement:t=>new Element(t)};
 const context=vm.createContext({document,normPath,parentPath,volumeLabel:v=>v,createFileIcon:()=>new Element(),createPopupHeader:()=>new Element(),api:{listDir:async()=>{throw Error('disconnected');}}});
 vm.runInContext(`let fbVol='USB',availableVolumes=['USB'];${picker};globalThis.pick=pickDestination`,context);
 const pending=context.pick('Move','payload',true);await flush();const d=document.body.children[0];assert(d.children.find(e=>e.className==='btn destination-current').disabled);assert(d.children.at(-1).children[3].disabled);d.children.at(-1).children[4].fire('click');assert.equal(await pending,null);
}
// Starting each supported media name retains the count, while failures remain visible.
{
 let status={textContent:'12 items',className:'msg'},fail=false;
 const start=source.indexOf('async function runFile('),end=source.indexOf('\nasync function mountDisk(',start);
 const context=vm.createContext({$:()=>status,api:{autostart:async()=>{if(fail)throw Error('device error');}}});
 vm.runInContext(`let fbVol='USB';${source.slice(start,end)};globalThis.run=runFile`,context);
 for(const name of ['Show Colors.prg','Delay-Joy.crt','Utilities.d64','tape.t64']){await context.run('/'+name,name);assert.equal(status.textContent,'12 items');}
 fail=true;await context.run('/bad.prg','bad.prg');assert.match(status.textContent,/Could not start.*device error/);
}
console.log('PASS: production Move/Copy picker explicitly selects empty/populated/multiple-folder roots on all four volumes; navigation/Up, failed listing disablement, start count retention and errors');
// Routine operations retain the refreshed count; media operations restore it.
{
 const status={textContent:'12 items',className:'msg'};
 let fail=false;
 const operation=async()=>{if(fail)throw Error('device failure');};
 const context=vm.createContext({$:()=>status,fbVol:'USB',fbPath:'/',normPath,
  promptE64:async()=> 'renamed',hasSlash:()=>false,
  showError:text=>{status.className='msg err';status.textContent=text;},
  chooseRawCartridge:async()=> 'normal',
  openEditor:async()=>({saved:true}),
  loadDir:async()=>{status.className='msg';status.textContent='13 items';},
  api:{makeDir:operation,renameEntry:operation,mountDisk:operation,loadPrg:operation,loadRawCartridge:operation}});
 for(const name of ['makeFolder','renameEntry','mountDisk','loadPrg','loadRawCartridge','editFile','savedBasic']){
  const start=source.indexOf('async function '+name+'('),end=source.indexOf('\n}',start)+2;
  vm.runInContext(source.slice(start,end),context);
 }
 vm.runInContext('let itemCount="12 items";'+source.slice(source.indexOf('function restoreItemCount()'),source.indexOf('// ---- run (autostart) ----')),context);
 for(const expression of ['makeFolder()','renameEntry("/old","old")','savedBasic({saved:true,name:"new.prg",size:42})','editFile("/notes","notes")']){
  await vm.runInContext(expression,context);assert.equal(status.textContent,'13 items',expression);
 }
 for(const expression of ['mountDisk("/disk","disk",8)','loadPrg("/prg","prg")','loadRawCartridge("/cart",{name:"cart",size:8192})']){
  await vm.runInContext(expression,context);assert.equal(status.textContent,'',expression);
  fail=true;await vm.runInContext(expression,context);assert.match(status.textContent,/device failure/);fail=false;
 }
 fail=true;await vm.runInContext('makeFolder()',context);assert.match(status.textContent,/Could not create.*device failure/);
 await vm.runInContext('renameEntry("/old","old")',context);assert.match(status.textContent,/Could not rename.*device failure/);
}
console.log('PASS: folder creation, rename, BASIC/text saves and cartridge/mount/load success retain counts; storage and media errors remain visible');
{
 const status={textContent:'12 items',className:'msg'};let fail=false;
 const context=vm.createContext({$:()=>status,fbVol:'USB',fbPath:'/',normPath,fbNames:new Set(),uploading:false,
  pickDestination:async()=>({vol:'SD',folder:'/'}),confirmE64:async()=>true,setUploading:()=>{},
  api:{transferEntry:async()=>{if(fail)throw Error('transfer error');}},
  uploadWithRetry:async()=>{if(fail)throw Error('upload error');return 'ok';},
  loadDir:async()=>{status.textContent='13 items';status.className='msg';},
  showError:text=>{status.textContent=text;status.className='msg err';}});
 for(const name of ['transferEntry','uploadFiles']){const start=source.indexOf('async function '+name+'(');vm.runInContext(source.slice(start,source.indexOf('\n}',start)+2),context);}
 for(const expr of ['transferEntry("/file","file",true)','transferEntry("/file","file",false)','uploadFiles([{name:"file"}])']){
  await vm.runInContext(expr,context);assert.equal(status.textContent,'13 items');
  fail=true;await vm.runInContext(expr,context);assert.match(status.textContent,/error/);assert.equal(status.className,'msg err');fail=false;
 }
}
console.log('PASS: Copy/Move/upload success retain counts; transfer and upload errors survive refresh');
