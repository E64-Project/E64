import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync('src/webui/assets/js/datasette.js','utf8');
const nodes=new Map();
const node=id=>{if(!nodes.has(id))nodes.set(id,{textContent:'',hidden:false,setAttribute(k,v){this[k]=v;},toggleAttribute(k,v){this[k]=v;},addEventListener(k,v){this[k]=v;}});return nodes.get(id);};
const actions=['record','play','rewind','forward','stop','eject','zero'];
const buttons=actions.map(a=>({dataset:{tapeAction:a},setAttribute(k,v){this[k]=v;},addEventListener(k,v){this[k]=v;}}));
let state={supported:1,attached:1,writable:1,filename:'USB:/tapes/Actual <é & name>.tap',counter:123,mode:1,motor:0},calls=[],failure=false,timers=[];
const context=vm.createContext({document:{hidden:false,getElementById:node,querySelectorAll:()=>buttons,addEventListener(){}},getDatasette:async()=>{if(failure)throw Error('HTTP 503 test');return state;},controlDatasette:async a=>{calls.push(a);if(failure)throw Error('HTTP 409 test');},setTimeout:(f,ms)=>{timers.push({f,ms});return timers.length;},clearTimeout(){}});
vm.runInContext(source.replace(/^import .*;\n/m,'').replaceAll('export function','function'),context);
context.renderDatasette(state);
assert.equal(node('tape-label').textContent,'Actual <é & name>');assert.equal(node('tape-label').title,state.filename);
assert.equal(node('tape-counter').textContent,'123');assert.equal(node('tape-cassette').hidden,false);assert(buttons.every(b=>!b.disabled));
context.renderDatasette({...state,counter:7,mode:2,motor:1});assert.equal(node('tape-counter').textContent,'007');assert.match(node('tape-status').textContent,/^Recording$/);
context.renderDatasette({...state,writable:0});assert(buttons[0].disabled);assert(buttons.slice(1).every(b=>!b.disabled));
context.renderDatasette({...state,pending:1});assert(buttons.every(b=>!b.disabled));
context.renderDatasette({...state,attached:0,filename:''});assert(node('tape-cassette').hidden);assert(node('tape-label').hidden);assert.equal(node('tape-counter').textContent,'000');assert(buttons.every(b=>b.disabled));
context.renderDatasette({...state,supported:0});assert(buttons.every(b=>b.disabled));
context.renderDatasette({...state,filename:'SD:/'+('Long'.repeat(100))+'.tap',error:2});assert.equal(node('tape-label').textContent.length,400);assert.match(node('tape-error').textContent,/event playback/);
// Confirmed backend modes drive latches, including recording's coupled keys.
for(const mode of [0,1,2,3,4,0]) {
 context.renderDatasette({...state,mode,motor:mode===1?1:0});
 for(const b of buttons) assert.equal(b['aria-pressed'],String((b.dataset.tapeAction==='play'&&[1,2].includes(mode))||(b.dataset.tapeAction==='record'&&mode===2)||(b.dataset.tapeAction==='rewind'&&mode===3)||(b.dataset.tapeAction==='forward'&&mode===4)));
 assert.equal(node('tape-motor')['data-on'],String(mode===1));
 assert(!/Motor|Read only|queued/.test(node('tape-status').textContent));
}
context.initDatasette();
for(const button of buttons){context.renderDatasette(state);await button.click();}
assert.deepEqual(calls,actions);
context.setDatasetteVisible(true);await new Promise(setImmediate);
assert.equal(node('tape-label').textContent,'Actual <é & name>');
state={...state,filename:'USB2:/Other.tap',counter:891};await context.poll();assert.equal(node('tape-label').textContent,'Other');assert.equal(node('tape-counter').textContent,'891');
failure=true;await context.poll();assert(buttons.every(b=>b.disabled));assert.match(node('tape-error').textContent,/HTTP 503/);assert.equal(timers.at(-1).ms,5000);
failure=false;await context.poll();failure=true;await buttons[1].click();assert.match(node('tape-error').textContent,/HTTP 409/);assert(buttons.every(b=>b.disabled));
context.setDatasetteVisible(false);const count=timers.length;await context.poll();assert.equal(timers.length,count);
// Exercise the production API helpers, including real response failures.
let request;
const api=await import('../../src/webui/assets/js/api.js');
globalThis.fetch=async(url,init)=>{request={url,init};return {ok:true,json:async()=>state};};
await api.controlDatasette('rewind');assert.equal(request.url,'/api/datasette/control?action=rewind');assert.equal(request.init.method,'POST');assert.equal(request.init.headers['X-BMC64-Web'],'1');
await api.getDatasette();assert.equal(request.init.cache,'no-store');
globalThis.fetch=async()=>({ok:false,status:409,text:async()=> 'Datasette busy'});await assert.rejects(api.controlDatasette('play'),/HTTP 409 Datasette busy/);
console.log('PASS Batch 07: loaded/empty/actual and long filenames, real counter rendering, sync, all controls, read-only/pending/unavailable disabled states, polling bounds, API failure and headers');

// Production routing selects the new page without triggering volume scans.
let refreshed=0,shown;
const routeNodes=new Map();
const routeNode=id=>{if(!routeNodes.has(id))routeNodes.set(id,{hidden:false});return routeNodes.get(id);};
const noOp=()=>{};
const routing={location:{hash:'#/datasette'},$:routeNode,document:{querySelectorAll:()=>[]},window:{addEventListener:noOp},setDatasetteVisible:v=>{shown=v;},refreshVolumes:()=>{refreshed++;},hideInstructions:noOp,showInstructions:noOp,loadDir:noOp,pathFromHash:noOp,loadConfigs:noOp};
for(const f of ['initDatasette','initDashboard','initAbout','initLogo','initHelpNavigation','initFiles','endTapeSelection','initEditor','initConfigs','loadMachine','startStatusPolling','syncDriveActivity'])routing[f]=noOp;
vm.runInNewContext(fs.readFileSync('src/webui/assets/js/app.js','utf8').replace(/^import .*;\n/gm,'').replace('await loadMachine();','loadMachine();'),routing);
assert.equal(routeNode('view-datasette').hidden,false);assert.equal(shown,true);assert.equal(refreshed,0);
for(const view of ['files','configs','instructions','dashboard']){routing.location.hash='#/'+view;routing.route();assert.equal(routeNode('view-'+view).hidden,false);assert.equal(routeNode('view-datasette').hidden,true);}
assert.equal(refreshed,1);
console.log('PASS production navigation: Datasette and all existing pages; no volume scan on Datasette route');
