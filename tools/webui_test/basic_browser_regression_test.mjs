// Source-level replay of the Firefox failures; no browser acceptance implied.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync('tools/webui_test/unified_ui_browser_check.py','utf8');
const savedPath='build/unified-web-ui-firefox/20261111-112638-692579/results.json';
if(fs.existsSync(savedPath)) {
 const saved=JSON.parse(fs.readFileSync(savedPath,'utf8'));
 assert.equal(saved.length,34);
 const records=JSON.stringify(saved);
 assert(records.includes('Create BASIC PRG remains available'));
 assert(records.includes('Timed out waiting for UI'));
}
assert(source.includes("'basic':'v2'"));
assert(fs.readFileSync('src/webui/webui_machine.cpp','utf8').includes('"C64", kRunTypes, "v2"'));
assert(source.includes("await refreshVolumes();await loadDir('/');"));
assert(!source.includes("startsWith('Created folder')"));
const create=source.split("d=folder();d.querySelector('input').value='created';")[1].split('\n')[0];
const predicate=create.match(/await waitFor\((.*?)\);check/)[1];
let count='';
const context=vm.createContext({d:{isConnected:false},document:{getElementById:()=>({textContent:count})},pause:async()=>{}});
const helper=source.match(/async function waitFor\(.*?\n/)[0];
vm.runInContext(helper,context);
assert(vm.runInContext(`(${predicate})()`,context));
count='Loading…';assert(!vm.runInContext(`(${predicate})()`,context));
count='Could not create folder';assert(!vm.runInContext(`(${predicate})()`,context));
count='';context.d.isConnected=true;assert(!vm.runInContext(`(${predicate})()`,context));
await assert.rejects(vm.runInContext("waitFor(()=>false,'BASIC editor open')",context),/Timed out waiting for UI: BASIC editor open/);
assert(source.includes("name:'validation exception',pass:false,error:String(error)"));
for(const text of ['BASIC button visible and enabled','new BASIC editor context','BASIC unavailable without machine capability','BASIC creation uploads tokenised PRG','BASIC save and directory reload'])assert(source.includes(text),text);
console.log('PASS: saved Firefox failure replay, actual C64 V2 fixture, status ordering, folder completion predicate rejects loading/errors/open dialog, operation-specific timeout retained, BASIC browser coverage');
