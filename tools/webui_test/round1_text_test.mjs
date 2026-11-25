import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {readFile} from '../../src/webui/assets/js/api.js';
const originalFetch=globalThis.fetch;
try {
 globalThis.fetch=async()=>new Response('oversize',{headers:{'Content-Length':'262145'}});
 await assert.rejects(readFile('USB','/large.txt',262144),/256 KB/);
 globalThis.fetch=async()=>new Response(new Uint8Array(262145));
 await assert.rejects(readFile('SD','/large.txt',262144),/256 KB/);
 globalThis.fetch=async()=>new Response('valid');
 assert.equal(new TextDecoder().decode(await readFile('SD','/small.txt',262144)),'valid');
 globalThis.fetch=async()=>new Response('unavailable',{status:503});
 await assert.rejects(readFile('USB','/missing.txt',262144),/503/);
} finally {globalThis.fetch=originalFetch;}
class Element {
 constructor(){this.hidden=false;this.disabled=false;this.value='';this.readOnly=false;this.events={};this.classList={add(){},remove(){}};}
 addEventListener(k,f){this.events[k]=f;}
 setAttribute(){}
 closest(){return this.hiddenParent?{}:null;}
 focus(){document.activeElement=this;}
 setSelectionRange(){}
}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
const document={activeElement:new Element(),body:new Element()};
get('editor').querySelectorAll=()=>['ed-close','ed-text','ed-name','ed-save','ed-save-reboot','ed-cancel'].map(get);
let payload,saves=[],failRead=false,failSave=false,answer=false,questions=[];
const api={async readFile(vol,path,max){assert(['USB','SD'].includes(vol));assert.equal(max,262144);if(failRead)throw Error('unavailable');return payload;},async saveFile(vol,path,text){if(failSave)throw Error('storage failure');saves.push({vol,path,text});}};
const code=fs.readFileSync('src/webui/assets/js/editor.js','utf8').replace(/^import .*;\n/gm,'').replaceAll('export function ','function ');
const context=vm.createContext({document,window:{addEventListener(){}},$:get,api,TextDecoder,TextEncoder,Uint8Array,confirmE64:async text=>{questions.push(text);return answer;},normPath:s=>s,rebootNow:async()=>{},BasicError:Error});
vm.runInContext(code+'\ninitEditor();globalThis.open=openEditor;',context);
const settle=async()=>{for(let i=0;i<15;i++)await Promise.resolve();};
const text=s=>payload=new TextEncoder().encode(s).buffer;
const key=async(key,ctrlKey=false)=>{get('editor').events.keydown({key,ctrlKey,preventDefault(){}});await settle();};
for(const vol of ['SD','USB']) {
 text('\uFEFFfirst\r\nsecond\r\n');let result=context.open({vol,path:'/mixed-case.TXT',name:'mixed-case.TXT',readOnly:true});await settle();
 assert(get('ed-text').readOnly);assert(get('ed-save').hidden&&get('ed-save-reboot').hidden);
 // Even a programmatic textarea mutation cannot activate Save in View.
 get('ed-text').value='changed';get('ed-text').events.input();assert(get('ed-save').disabled);
 await key('s',true);assert.equal(saves.length,0);await key('Escape');assert.equal((await result).saved,false);assert.equal(questions.length,0);
 text('\uFEFFfirst\r\nsecond\r\n');result=context.open({vol,path:'/notes.txt',name:'notes.txt'});await settle();
 get('ed-text').value='first\nchanged\n';get('ed-text').events.input();await key('s',true);assert.equal((await result).saved,true);
 assert.equal(saves.at(-1).text,'\uFEFFfirst\r\nchanged\r\n');assert.equal(saves.at(-1).vol,vol);
 saves=[];
}
text('original\n');let pending=context.open({vol:'USB',path:'/notes.txt',name:'notes.txt'});await settle();get('ed-text').value='dirty\n';
await key('Escape');assert(!get('editor').hidden);assert(questions.at(-1).includes('Discard'));
answer=true;await key('Escape');assert.equal((await pending).saved,false);assert.equal(saves.length,0);
for(const bytes of [new Uint8Array([0xff]),new Uint8Array([0,65])]){
 payload=bytes.buffer;pending=context.open({vol:'SD',path:'/bad.txt',name:'bad.txt'});await settle();assert(get('ed-save').disabled&&get('ed-msg').textContent.includes('UTF-8'));await key('Escape');await pending;
}
text('one\r\ntwo\n');pending=context.open({vol:'SD',path:'/mixed.txt',name:'mixed.txt'});await settle();assert(get('ed-save').disabled&&get('ed-msg').textContent.includes('line endings'));await key('Escape');await pending;
failRead=true;pending=context.open({vol:'SD',path:'/error.txt',name:'error.txt'});await settle();assert(get('ed-msg').textContent.includes('unavailable')&&get('ed-save').disabled);await key('Escape');await pending;failRead=false;
text('saved\n');pending=context.open({vol:'USB',path:'/notes.txt',name:'notes.txt'});await settle();get('ed-text').value='changed\n';failSave=true;await key('s',true);assert(!get('editor').hidden&&get('ed-msg').textContent.includes('storage failure'));await key('Escape');await pending;
console.log('PASS: SD/USB read-only View and Ctrl+S hard guard; Edit Save/Cancel/discard; BOM/CRLF preservation; UTF-8/binary/mixed-ending/storage failures; streamed and declared 256KB limits');
