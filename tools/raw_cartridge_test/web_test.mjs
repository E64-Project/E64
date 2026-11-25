import assert from 'node:assert/strict';
import fs from 'node:fs';
import { chooseRawCartridge, rawCartridgeTypes } from '../../src/webui/assets/js/raw_cartridge.js';
import { loadRawCartridge } from '../../src/webui/assets/js/api.js';
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.events={};this.returnValue='';this.value='';}
  append(...nodes){this.children.push(...nodes);}
  setAttribute(){}
  addEventListener(type,fn){this.events[type]=fn;}
  showModal(){this.open=true;}
  close(value=''){this.returnValue=value;this.events.close?.();}
  focus(){this.focused=true;}
  remove(){this.removed=true;}
}
const body=new Element('body'),opener=new Element('button');
globalThis.document={body,activeElement:opener,createElement:tag=>new Element(tag)};
for(const [size,types] of [[4096,['8k','ultimax']],[8192,['8k']],[12288,['16k','ultimax']],[16384,['16k','ultimax']]]){
 for(const prefix of [0,2])assert.deepEqual(rawCartridgeTypes(size+prefix),types);
}
for(const size of [0,1,4095,8191,8193,16385,16387,NaN,undefined,-1])assert.deepEqual(rawCartridgeTypes(size),[]);
function current(){const d=body.children.at(-1),f=d.children[1];return {d,f,select:f.children[2].children[1],buttons:f.children[4]};}
let response=chooseRawCartridge('KERNAL.rom',8192),v=current();
assert.equal(v.d.children[0].children[0].textContent,'Load Raw Cartridge');
assert.equal(v.f.children[0].children[0].textContent,'KERNAL.rom');
assert.equal(v.f.children[0].children[1].textContent,'8 KB');
assert.equal(v.f.children[1].children[0].textContent,'For cartridge ROMs only.\nSize does not identify cartridge type.');
assert.equal(v.f.children[1].children[1].textContent,'Loading replaces the attached cartridge.\nA failed load may detach it.');
assert.equal(v.f.children[2].children[0].textContent,'Cartridge Type');
assert.equal(v.d.className,'e64-dialog e64-confirm raw-cartridge-dialog');
assert.equal(v.select.value,'8k');assert(v.buttons.children[0].focused);
assert.equal(v.buttons.children[1].textContent,'Load & Run');
let settled=false;response.then(()=>settled=true);await Promise.resolve();assert(!settled,'Opening a ROM must not confirm');
v.buttons.children[0].onclick();assert.equal(await response,null);assert(opener.focused&&v.d.removed);
response=chooseRawCartridge('game.rom',16384);v=current();assert.equal(v.select.value,'16k');assert.equal(v.f.children[0].children[1].textContent,'16 KB');
v.select.value='ultimax';v.f.events.submit({preventDefault(){}});assert.equal(await response,'ultimax');
response=chooseRawCartridge('game.rom',8192);v=current();v.d.events.cancel({preventDefault(){}});assert.equal(await response,null);
response=chooseRawCartridge('game.rom',8192);v=current();v.d.children[0].children[1].onclick();assert.equal(await response,null);
response=chooseRawCartridge('wrong.rom',8192);v=current();v.select.value='16k';v.f.events.submit({preventDefault(){}});assert(v.select.focused);v.d.close();assert.equal(await response,null);
response=chooseRawCartridge('truncated.rom',8191);v=current();assert(v.buttons.children[1].disabled);v.d.close();assert.equal(await response,null);
// Every displayed size uses the existing File Manager formatter, including prefixes.
for (const [size, text] of [[4096,'4 KB'],[8192,'8 KB'],[8194,'9 KB'],[12288,'12 KB'],[16384,'16 KB'],[16386,'17 KB']]) {
  response=chooseRawCartridge('game.rom',size);v=current();
  assert.equal(v.f.children[0].children[1].textContent,text);
  v.d.close();assert.equal(await response,null);
}
// Exercise real polling code. Return a held pending response to prove that the
// POST's 202 alone cannot finish the operation or display success.
let requests=[],release;const originalTimer=globalThis.setTimeout;
globalThis.setTimeout=fn=>{queueMicrotask(fn);return 1;};
globalThis.fetch=async(url,init)=>{
 requests.push({url,init});
 if(init?.method==='POST')return {ok:true,json:async()=>({request_id:42})};
 return await new Promise(resolve=>release=()=>resolve({ok:true,json:async()=>({request_id:42,state:3,error:''})}));
};
let completed=false;let operation=loadRawCartridge('USB2','/game.ROM','8k').then(()=>completed=true);
for(let i=0;i<10;i++)await Promise.resolve();assert(!completed&&release);release();await operation;assert(completed);
assert(requests[0].url.includes('vol=USB2')&&requests[0].url.includes('type=8k&replace=1'));
assert.equal(requests[0].init.headers['X-BMC64-Web'],'1');
let mode='failure';globalThis.fetch=async(url,init)=>({ok:true,json:async()=>init?.method==='POST'?{request_id:7}:{request_id:mode==='id'?8:7,state:mode==='failure'?4:1,error:'Attachment Failed; Previous Cartridge May Have Been Removed'}});
await assert.rejects(loadRawCartridge('SD','/bad.rom','8k'),/May Have Been Removed/);
mode='id';await assert.rejects(loadRawCartridge('SD','/bad.rom','8k'),/Request Changed/);
mode='pending';await assert.rejects(loadRawCartridge('SD','/slow.rom','8k'),/Completion Not Confirmed/);
globalThis.setTimeout=originalTimer;
const icons=fs.readFileSync('src/webui/assets/js/file_icons.js','utf8');assert.match(icons,/crt: "cartridge"/);assert.match(icons,/rom: "rom"/);assert(!/bin:/.test(icons));
console.log('PASS: real raw dialog suggestions, all size variants/prefixes, explicit confirmation, Cancel/Close/Escape/focus and form submission; unrelated KERNAL ROM not auto-loaded; actual completion/error/ID/timeout reporting; .crt/.rom/.bin icons preserved');
