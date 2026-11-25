// Exercise production Config rendering/actions and dialog outcomes without hardware.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import * as data from '../../src/webui/assets/js/configs_data.js';
import { confirmE64 } from '../../src/webui/assets/js/dialog.js';
class Node {
  constructor(tag = '') { this.tag = tag; this.children = []; this.events = {}; this.hidden = false; this.className = ''; this._text = ''; this.open = false; this.returnValue = ''; }
  set textContent(value) { this._text = value; this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  append(...nodes) { this.children.push(...nodes); }
  appendChild(node) { if(node.tag === 'fragment') this.children.push(...node.children); else this.children.push(node); return node; }
  replaceChildren(...nodes) { this.children = nodes; this._text = ''; }
  setAttribute() {}
  addEventListener(type, fn) { this.events[type] = fn; }
  get classList() { return { add: c => {this.className += ' '+c;}, remove() {} }; }
  focus() { this.focused = true; }
  showModal() { this.open = true; }
  close(value = '') { this.open = false; this.returnValue = value; this.events.close?.(); }
  remove() { this.removed = true; }
}
const nodes = new Map();
const $ = id => { if (!nodes.has(id)) nodes.set(id, new Node()); return nodes.get(id); };
const body = new Node('body'), opener = new Node('button');
globalThis.document = { body, activeElement: opener, createElement: tag => new Node(tag), createDocumentFragment: () => new Node('fragment') };
let response = confirmE64('Reboot E64?\nUnsaved changes will be lost.', 'Reboot');
let dialog = body.children.at(-1);
assert.equal(dialog.children[0].children[0].textContent, 'Reboot E64?');
assert.equal(dialog.children[0].children[1].textContent,'Close');
assert.equal(dialog.children[1].textContent, 'Unsaved changes will be lost.');
assert.equal(dialog.children[2].children[0].textContent, 'Cancel');
assert.equal(dialog.children[2].children[1].textContent, 'Reboot');
assert(dialog.children[2].children[0].focused);
dialog.children[2].children[0].onclick(); assert.equal(await response, false); assert(dialog.removed); assert(opener.focused);
response = confirmE64('Delete Config?', 'Delete'); dialog = body.children.at(-1); dialog.children[2].children[1].onclick(); assert.equal(await response, true);
response = confirmE64('Restore Config?', 'Restore'); dialog = body.children.at(-1); dialog.close(); assert.equal(await response, false);
let calls = [], menu, answer = 'Copied Config';
const files = {
 '/configs/active.txt': 'config=work\n',
 '/configs/work/config.txt': 'name=Work\nmachine=C64/NTSC\n# Keep this comment\n',
 '/configs/trash/config.txt': 'name=Deleted\nmachine=C64/NTSC\n',
};
const context = vm.createContext({ ...data, $, document, TextDecoder, TextEncoder, Date,
 setTimeout: fn => {fn();}, location: {}, promptE64: async () => answer,
 confirmE64: async () => true, setMachine() {}, openEditor() {}, filesHash: p => p, selectFilesVolume() {},
 toggleMenu: (_button, items) => {menu = items;},
 api: {
  getStatus: async () => ({machine:'C64', config_id:'work'}),
  listDir: async (path) => ({entries: path === '/configs' ? [{name:'work',dir:true},{name:'trash',dir:true}] : [
   {name:'config.txt'}, {name:'settings-C64.txt'}, {name:'vice.ini'}, {name:'vice.ini.e64-new'},
  ]}),
  readFile: async (_vol, path) => { if (!(path in files)) throw Error('missing'); return new TextEncoder().encode(files[path]); },
  getConfigProtection: async () => ({ready:true, protected:['work']}),
  getDeletedConfigs: async () => ({ready:true, deleted:[{id:'trash',remaining:2}]}),
  makeDir: async (...args) => calls.push(['mkdir',...args]),
  transferEntry: async (...args) => calls.push(['copy',...args]),
  saveFile: async (...args) => calls.push(['save',...args]),
 }
});
const source = fs.readFileSync('src/webui/assets/js/configs.js','utf8');
vm.runInContext(source.replace(/^import[\s\S]*?from\s+"[^"\n]+";\n/gm,'').replace(/export /g,''),context);
await vm.runInContext('loadConfigs()', context);
assert.equal($('pf-status').textContent,'','No visible Config count after a successful load');
const descendants = node => node.children.flatMap(c => [c, ...descendants(c)]);
let cards = descendants($('pf-list')).filter(n => n.tag === 'article');
assert.equal(cards.length, 2); assert(!cards.some(c => c.textContent.includes('Deleted')));
const work = cards.find(c => c.textContent.includes('Work'));
assert(work.textContent.includes('Switch To')); assert(work.textContent.includes('Start Once'));
assert(!work.textContent.includes('config.txt')); assert(!work.textContent.includes('Help'));
const actionButton = descendants(work).find(n => n.tag === 'button' && n.textContent === 'Actions ▾'); actionButton.events.click();
for (const label of ['config.txt','settings','vice.ini','Rename…','Copy…']) assert(menu.some(m => m.label === label), label);
assert(!menu.some(m => m.label === 'Delete')); // Running/protected Config.
assert.equal(vm.runInContext('configActions(FACTORY_CONFIGS[0]).menu.length',context),0);
assert.equal(vm.runInContext('configActions({id:"editable",name:"Editable",machine:"C64"}).menu.some(m => m.label === "Delete")',context),true);
assert.equal(descendants(work).filter(n => n.tag === 'a').length,0);
await vm.runInContext('restoring = true; loadConfigs()',context);
cards = descendants($('pf-list')).filter(n => n.tag === 'article'); assert.equal(cards.length,1); assert(cards[0].textContent.includes('trash')); assert(cards[0].textContent.includes('Delete Permanently')); assert.equal($('pf-restore').textContent,'Back to Configs');
await vm.runInContext('copyConfig({id:"work",name:"Work"})',context);
assert.equal(calls[0][0],'mkdir'); assert.equal(calls.filter(c => c[0]==='copy').length,2);
assert(!calls.some(c => c.some(v => typeof v === 'string' && v.endsWith('.e64-new'))));
assert.equal(calls.at(-1)[0],'save'); assert(calls.at(-1)[2].endsWith('/config.txt')); assert.equal(calls.at(-1)[3], 'name=Copied Config\nmachine=C64/NTSC\n# Keep this comment\n');
calls=[]; answer=null; await vm.runInContext('copyConfig({id:"work",name:"Work"})',context); assert.equal(calls.length,0);
console.log('PASS: E64 dialog Cancel/accept/Escape/focus; compact Config actions, editable Rename, factory and running protection, legacy cleanup view/back label; copy payloads and config-last publication, recovery-file exclusion, cancellation.');

// Cards show saved video standards, never names or technical machine details.
for (const [machine,name,expected] of [
 ['C64/NTSC/HDMI/VICE 768x525 @ 59.827 Hz','PAL named Config','NTSC'],
 ['C64 / PAL / HDMI / VICE 720x576 @ 50 Hz','NTSC named Config','PAL'],
 ['C64','NTSC in name only',''], ['C64/unknown','PAL','']
]) {
 const p={id:'test-card',name,machine,start:'switch',disks:[],autostart:''};
 context.testCard=p;
 const rendered=vm.runInContext('configCard(testCard,{running:"test-card",powerOn:"test-card",once:"",protectionReady:true,protectedIds:new Set(["test-card"])},{buttons:[],menu:[]})',context);
 const all=descendants(rendered),standards=all.filter(n=>n.className.includes('video-standard'));
 assert.equal(standards.length,expected?1:0);
 if(expected)assert.equal(standards[0].textContent,expected);
 assert.equal(all.find(n=>n.className==='pf-name-text').textContent,name);
 const top=rendered.children[0],footer=rendered.children.at(-1);
 assert.ok(top.className==='pf-top'&&top.children.length===1&&top.children[0].className.includes('pf-name'));
 assert.ok(footer.className.includes('pf-card-footer'));
 if(expected)assert.equal(footer.children[0],standards[0]);
 assert.ok(footer.children.some(n=>n.className==='pf-badges'&&n.textContent.includes('Protected: On')));
 assert.equal(rendered.children.at(-2).className,'pf-running-row');
 assert.ok(rendered.children.at(-2).textContent.includes('Running'));

 assert.ok(!all.some(n=>n.className.includes('pf-chip')||n.className.includes('pf-detail')));
 assert.ok(!rendered.textContent.includes('Power-on')&&!rendered.textContent.includes('HDMI')&&!rendered.textContent.includes('VICE'));
 assert.ok(rendered.textContent.includes('Running')&&rendered.textContent.includes('Protected: On'));
 assert.ok(rendered.textContent.includes('Switch To')&&rendered.textContent.includes('Start Once'));
}
assert.ok(!source.includes('renderSummary')&&!source.includes('pf-summary'));
console.log('PASS: simplified Config cards use actual video metadata, preserve names/actions/protection/Running, and omit Power-on, machine and technical badges/summary');

for(const factory of data.FACTORY_CONFIGS){
 context.factoryCard=factory;
 const card=vm.runInContext('configCard(factoryCard,{running:"",powerOn:factoryCard.id,once:"",protectionReady:true,protectedIds:new Set()},configActions(factoryCard))',context);
 const footer=card.children.at(-1);
 assert.equal(footer.children[0].textContent,data.configVideoStandard(factory.machine));
 assert.ok(footer.textContent.includes('Protected: On'));
 assert.ok(!descendants(card).some(n=>n.tag==='button'&&n.textContent==='Actions ▾'));
 assert.ok(card.textContent.includes('Start Once'));
 assert.equal(descendants(card).find(n=>n.className==='pf-name-text').textContent,factory.name);
}
console.log('PASS: full-width Config name, existing start buttons in middle, metadata/status footer and protected factory actions and approved Start Once');
