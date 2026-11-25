// Execute production Dashboard refresh against live label replacement and removal.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const read=p=>fs.readFileSync(p,'utf8');
const source=read('src/webui/assets/js/dashboard.js');
const fn=source.slice(source.indexOf('export async function refreshVolumes()'),source.indexOf('// ---- power / web UI actions ----')).replace('export ','');
const nodes=new Map(),$=id=>{if(!nodes.has(id))nodes.set(id,{style:{},textContent:'',hidden:false});return nodes.get(id);};
let volumes=[],fail=false,calls=0;
const context=vm.createContext({$,fmtKB:n=>n+' KB',api:{getVolumes:async capacity=>{assert.equal(capacity,true);calls++;if(fail)throw Error('offline');return {volumes};}}});
vm.runInContext(fn,context);
const ids=['SD','USB','USB2','USB3'],prefixes=['d-storage','d-usb-storage','d-usb2-storage','d-usb3-storage'],fallbacks=['SD Card','USB 1','USB 2','USB 3'];
const labels=['E64-SYS-V1','BMC64DATA','EXTERNALUSB','8 GB USB'];
volumes=ids.map((id,i)=>({id,label:labels[i],total_kb:1024,free_kb:256}));
await context.refreshVolumes();
for(let i=0;i<4;i++){assert.equal($(prefixes[i]+'-label').textContent,fallbacks[i]+': '+labels[i]);assert.equal($(prefixes[i]+'-bar').style.width,'75%');assert.equal($(prefixes[i]+'-txt').textContent,'256 KB free of 1024 KB');assert.equal($(prefixes[i]).hidden,false);}
volumes=[];await context.refreshVolumes();
for(let i=0;i<4;i++){assert.equal($(prefixes[i]+'-label').textContent,fallbacks[i]);assert.equal($(prefixes[i]).hidden,true);}
volumes=ids.map(id=>({id,total_kb:100,free_kb:50}));await context.refreshVolumes();
for(let i=0;i<4;i++)assert.equal($(prefixes[i]+'-label').textContent,fallbacks[i]);
volumes[1].label='REPLACEMENT';await context.refreshVolumes();assert.equal($('d-usb-storage-label').textContent,'USB 1: REPLACEMENT');
fail=true;await context.refreshVolumes();assert.equal(calls,5);
for(let i=0;i<4;i++){assert.equal($(prefixes[i]+'-label').textContent,fallbacks[i]);assert.equal($(prefixes[i]).hidden,true);}
assert(read('src/webui/webui_fs.cpp').includes('if (sd_volume_label(paths[i], label, sizeof(label)) == SD_OK && *label)'));
const html=read('src/webui/assets/index.html'),css=read('src/webui/assets/style.css');
assert.equal((html.match(/id="fb-note"/g)||[]).length,1);
assert(html.includes('id="fb-note">Drag files into this window to upload to the current folder</p></div>'));
assert(html.includes('<p class="msg" id="fb-status" role="status"></p>'));
assert(css.includes('.logo-toggle[aria-pressed="true"] .sidebar-logo { clip-path:inset(0 0 39.375% 0); }'));
assert(css.includes('grid-template-columns:168px minmax(0,1fr) auto'));
assert(css.includes('.instructions-popup[data-topic="storage"] { width:min(825px, 94vw); overflow-y:auto; }'));
console.log('PASS: production Dashboard current labels, SD included, missing/removed/replaced/error fallbacks, unchanged capacity request count/bars; single isolated instruction, shared description grid, responsive Storage and source rainbow clipping');
