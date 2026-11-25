import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync('src/webui/assets/js/datasette.js', 'utf8');
const actions = ['record', 'play', 'rewind', 'forward', 'stop', 'eject', 'zero'];
const nodes = new Map();
const node = id => {
  if (!nodes.has(id)) nodes.set(id, { setAttribute(k,v) { this[k]=v; }, toggleAttribute(k,v) { this[k]=v; }, addEventListener() {} });
  return nodes.get(id);
};
const buttons = actions.map(action => ({ dataset: { tapeAction: action }, setAttribute(k,v) { this[k]=v; }, addEventListener(k,v) { this[k]=v; } }));
const base = { supported:1, attached:1, writable:1, filename:'test.tap', mode:0, pending:0, counter:0 };
let state = {...base}, requests = [], reads = [], timers = [];
const context = vm.createContext({
  document: { hidden:false, getElementById:node, querySelectorAll:()=>buttons, addEventListener() {} },
  controlDatasette: action => new Promise((resolve,reject) => requests.push({action,resolve,reject})),
  getDatasette: () => new Promise((resolve,reject) => reads.push({resolve,reject})),
  setTimeout: (f,ms) => { timers.push({f,ms}); return timers.length; }, clearTimeout() {}
});
vm.runInContext(source.replace(/^import .*;\n/m,'').replaceAll('export function','function'),context);
context.initDatasette();
context.renderDatasette(state);
const click = action => buttons[actions.indexOf(action)].click();
const flush = () => new Promise(setImmediate);
// Repeated/conflicting clicks cannot duplicate requests; STOP remains available.
const play = click('play');
for (const action of actions) assert.equal(buttons[actions.indexOf(action)].disabled,false);
click('play'); click('forward'); click('stop'); click('stop');
assert.deepEqual(requests.map(r=>r.action),['play']);
assert(buttons.every(b=>b['aria-pressed']==='false')); // no optimistic latch
requests[0].resolve(); await play;
click('play'); assert.equal(requests.length,1); // accepted but not confirmed
context.setDatasetteVisible(true);
reads.shift().resolve({...base,pending:1,mode:1}); await flush();
assert(buttons.every(b=>!b.disabled));
assert.equal(buttons[1]['aria-pressed'],'true');
assert.equal(requests.length,1);
const poll = context.poll(); reads.shift().resolve({...base,mode:1}); await poll;
assert.deepEqual(requests.map(r=>r.action),['play','stop']);
click('stop'); assert.equal(requests.length,2); // repeated STOP is coalesced
requests[1].resolve(); await flush();
reads.shift().resolve({...base}); await flush();
assert(buttons.every(b=>b['aria-pressed']==='false'));
// Every latch is determined by emulator mode, including REC+PLAY; momentary keys never latch.
for (const [mode,pressed] of [[1,['play']],[2,['record','play']],[3,['rewind']],[4,['forward']],[0,[]]]) {
  context.renderDatasette({...base,mode});
  assert.deepEqual(buttons.filter(b=>b['aria-pressed']==='true').map(b=>b.dataset.tapeAction),pressed);
}
// A poll started before a command must not overwrite its confirmation guard or visuals.
const oldPoll = context.poll();
const rewind = click('rewind'); requests.at(-1).resolve(); await rewind;
reads.shift().resolve({...base,mode:4}); await oldPoll;
assert.equal(buttons[3]['aria-pressed'],'false');
click('forward'); assert.equal(requests.length,3);
assert.equal(timers.at(-1).ms,0); // refresh immediately, no command cooldown
const confirm = context.poll(); reads.shift().resolve({...base,mode:3}); await confirm;
assert.equal(buttons[2]['aria-pressed'],'true');
const eject = click('eject'); requests.at(-1).resolve(); await eject;
reads.shift().resolve({...base,attached:0}); await flush();
assert(buttons.every(b=>b.disabled && b['aria-pressed']==='false'));
context.renderDatasette({...base,writable:0});
assert.equal(buttons[0].disabled,true); assert(buttons.slice(1).every(b=>!b.disabled));
context.renderDatasette({...base,supported:0}); assert(buttons.every(b=>b.disabled));
context.setDatasetteVisible(false);
console.log('PASS Datasette transport: duplicate/racing commands, pending acceptance, queued responsive STOP, stale polling, actual latches, momentary keys and availability');

// Display-only suffix stripping preserves authoritative path, title and overflow sizing.
for (const [name,display] of [['game.tap','game'],['game.TAP','game'],['game.TaP','game'],['game.d64','game.d64'],['game','game'],['one.two.tap','one.two'],['one.tap.backup','one.tap.backup'],['x'.repeat(500)+'.tap','x'.repeat(500)]]) {
  const filename='USB:/tapes/'+name;
  context.renderDatasette({...base,filename});
  assert.equal(node('tape-label').textContent,display);
  assert.equal(node('tape-label').title,filename);
  assert.equal(vm.runInContext("state.filename",context),filename);
}
// Actual transport + live motor, never optimistic clicks or pending acceptance.
for (const [changes,recording] of [[{mode:2,motor:1},true],[{mode:2,motor:0},false],[{mode:0,motor:1},false],[{mode:1,motor:1},false],[{mode:2,motor:1,attached:0},false],[{mode:2,motor:1,supported:0},false]]) {
  context.renderDatasette({...base,...changes});
  assert.equal(buttons[0]['data-recording'],String(recording));
}
context.renderDatasette({...base,mode:2,motor:1});
context.fail(new Error('offline'));
assert.equal(buttons[0]['data-recording'],'false');
console.log('PASS display-only TAP suffix cases and authoritative REC/motor/STOP/removal/unavailable transitions');
