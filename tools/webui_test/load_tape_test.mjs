import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync('src/webui/assets/js/files.js', 'utf8');
let calls = [], failure = false;
const status = {};
const context = vm.createContext({
  LOAD_ADDRESS: 0x801, localStorage: {getItem: () => 'USB'}, location: {hash:'#/files'},
  $: () => status, canRun: ext => ['tap','prg','d64','crt'].includes(ext),
  machineName: () => 'C64', hasBasicEditor: () => false,
  api: {downloadFolderUrl: () => '', downloadUrl: () => '', autostart: async (...args) => calls.push(['autostart',...args]),
    loadTape: async (...args) => {calls.push(['tape',...args]);if(failure) throw Error('drive unavailable');}}
});
vm.runInContext(source.replace(/^import .*;\n/gm,'').replaceAll('export function','function').replaceAll('export async function','async function'),context);
for (const vol of ['SD','USB','USB2','USB3']) {
  vm.runInContext('fbVol='+JSON.stringify(vol),context);
  for (const name of ['manual.tap','manual.TAP','manual.TaP']) {
    const actions=context.rowActions({name,dir:false},'/tapes/'+name);
    const tape=actions.find(a=>a.label==='Load Tape');assert(tape);
    calls=[];await tape.run();assert.deepEqual(calls,[['tape',vol,'/tapes/'+name]]);
    assert.equal(context.location.hash,'#/files');
    calls=[];await actions.find(a=>a.label==='Load & Run').run();
    assert.deepEqual(calls,[['autostart',vol,'/tapes/'+name]]);
  }
}
for (const name of ['x.prg','x.d64','x.crt','x.rom','x.txt']) {
  assert(!context.rowActions({name,dir:false},'/'+name).some(a=>a.label==='Load Tape'));
}
assert(!context.rowActions({name:'folder.tap',dir:true},'/folder.tap').some(a=>a.label==='Load Tape'));
failure=true;calls=[];context.location.hash='#/files';
await context.loadTape('/missing.tap','missing.tap');
assert.deepEqual(calls,[['tape','USB3','/missing.tap']]);
assert.equal(context.location.hash,'#/files');assert.match(status.textContent,/drive unavailable/);assert.equal(status.className,'msg err');
// Datasette LOAD session: attach only, retain navigation across storage, retry and cancel.
failure=false;
for (const vol of ['SD','USB','USB2','USB3']) {
 context.beginTapeSelection();context.selectFilesVolume(vol);context.location.hash='#/files/tapes';
 const actions=context.rowActions({name:'selected.TAP',dir:false},'/tapes/selected.TAP');
 assert.deepEqual(Array.from(actions,a=>a.label),['Load Tape']);
 calls=[];await actions[0].run();
 assert.deepEqual(calls,[['tape',vol,'/tapes/selected.TAP']]);
 assert.equal(context.location.hash,'#/datasette');
}
context.beginTapeSelection();context.location.hash='#/files';failure=true;
await context.loadTape('/bad.tap','bad.tap');assert.equal(context.location.hash,'#/files');
assert.match(status.textContent,/drive unavailable/);
failure=false;await context.loadTape('/retry.tap','retry.tap');assert.equal(context.location.hash,'#/datasette');
context.beginTapeSelection();context.location.hash='#/files/deep';context.cancelTapeSelection();
assert.equal(context.location.hash,'#/datasette');
context.location.hash='#/files';context.cancelTapeSelection();assert.equal(context.location.hash,'#/files');
// Leaving selection invalidates late completion, and normal TAP clicks retain Load & Run.
context.beginTapeSelection();context.endTapeSelection();await context.loadTape('/normal.tap','normal.tap');
assert.equal(context.location.hash,'#/files');
assert(context.rowActions({name:'normal.tap',dir:false},'/normal.tap').some(a=>a.label==='Load & Run'));
const api=await import('../../src/webui/assets/js/api.js');
let requests=[],states=[],httpFailure=false;
globalThis.fetch=async (url,init)=>{
  requests.push({url,init});
  if(httpFailure)return {ok:false,status:404,text:async()=> 'no such file'};
  return {ok:true,json:async()=>url.startsWith('/api/fs/load-tape?')?{request_id:7}:states.shift()};
};
states=[{serial:7,pending:1},{serial:7,pending:0,error:0,attached:1,filename:'USB2:/tapes/a & b.TAP',mode:0}];
const state=await api.loadTape('USB2','/tapes/a & b.TAP');
assert.equal(state.mode,0);assert.equal(state.filename,'USB2:/tapes/a & b.TAP');
assert.equal(requests[0].url,'/api/fs/load-tape?vol=USB2&path=%2Ftapes%2Fa%20%26%20b.TAP');
assert.equal(requests[0].init.method,'POST');assert.equal(requests[0].init.headers['X-BMC64-Web'],'1');
assert(requests.slice(1).every(r=>r.url==='/api/datasette'));
for (const state of [{serial:7,pending:0,error:5,attached:1},{serial:8,pending:0,error:0,attached:1}]) {
 states=[state];await assert.rejects(api.loadTape('SD','/bad.tap'),/attachment failed|superseded/);
}
httpFailure=true;await assert.rejects(api.loadTape('USB','/missing.tap'),/404.*no such file/);
assert(requests.every(r=>! /autostart|control|reset|keyboard/.test(r.url)));
console.log('PASS Load Tape: case-insensitive TAP-only menu, all volumes, preserved Load & Run, attachment-only requests, authenticated POST, completion/state, errors and no autostart/transport/reset/keys');
