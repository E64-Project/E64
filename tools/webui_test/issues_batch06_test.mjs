import assert from 'node:assert/strict';
import fs from 'node:fs';
import {showInstructions,hideInstructions} from '../../src/webui/assets/js/instructions.js';
const oldDocument=globalThis.document,oldLocation=globalThis.location;
const nodes=new Map();
const node=()=>({dataset:{},children:[],childNodes:[],open:false,addEventListener(){},querySelector(){return null},append(...x){this.children.push(...x)},replaceChildren(){this.children=[]},show(){this.open=true},close(){this.open=false}});
const get=id=>{if(!nodes.has(id))nodes.set(id,node());return nodes.get(id)};
globalThis.document={getElementById:get,createElement:node};globalThis.location={hash:''};
try {
 for(const [topic,title,phrases] of [
 ['storage','Storage',['How Much Storage Do You Really Need?','175 KB','90,000','16 GB','D64','Do not connect external USB storage']],
 ['memory','Memory Expansion',['64 KB','128k, 256k, 512k, 1024k, 2048k, 4096k, 8192k, or 16384k','without a forced C64 reset','custom Config','not a snapshot','Clear Image','Save Now','GEOS','does not enlarge ordinary BASIC memory']],
 ['advanced','Advanced Drive Settings',['Change Model >','IEC FileSystem','Select IEC Dir >','True Drive Emulation','Virtual Devices','CMDHD Mode','Initialization','Configuration','Parallel Cable','None, Standard, Dolphin DOS, and Formel 64','RAM 2000','RAM 4000','RAM 6000','RAM 8000','RAM A000','not C64 memory or an REU']]]) {
  location.hash='#/instructions/'+topic;showInstructions(topic);
  assert.equal(get('instructions-title').textContent,title);assert(get('instructions-popup').open);
  const html=get('instructions-content').innerHTML;for(const text of phrases)assert(html.includes(text),text);
  for(const [,route] of html.matchAll(/href="#\/instructions\/([^\"]+)"/g))assert(get('instructions-index').children.some(n=>n.href==='#/instructions/'+route));
  get('instructions-popup').onclose();assert.equal(location.hash,'#/instructions');hideInstructions();assert(!get('instructions-popup').open);
 }
 const source=fs.readFileSync('third_party/vice-3.3/src/arch/raspi/c64/menu_c64.c','utf8');
 for(const size of ['128k','256k','512k','1024k','2048k','4096k','8192k','16384k'])assert(source.includes('"'+size+'"'));
 const native=fs.readFileSync('third_party/vice-3.3/src/arch/raspi/vice_api.c','utf8');
 for(const name of ['CMDHD Mode','Normal','Initialization','Configuration','True Drive Emulation','Parallel Cable','RAM 2000','RAM 4000','RAM 6000','RAM 8000','RAM A000'])assert(native.includes('"'+name+'"'));
 console.log('PASS: Batch 06 content, all topic links, dialog close/reopen, native sizes and settings');
} finally {globalThis.document=oldDocument;globalThis.location=oldLocation}
