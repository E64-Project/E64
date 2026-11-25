import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const read=p=>fs.readFileSync(new URL('../../'+p,import.meta.url),'utf8');
const source=read('src/webui/assets/js/dashboard.js');
const render=source.match(/function renderJoystickSwap\(s\) \{[\s\S]*?\n\}/)[0];
const nodes=new Map();
const $=id=>{if(!nodes.has(id))nodes.set(id,{setAttribute(k,v){this[k]=v;}});return nodes.get(id);};
const context=vm.createContext({$,joystickSwapBusy:false});vm.runInContext(render,context);
for(const [value,label,disabled,pressed] of [[0,'Normal',false,'false'],[1,'Reversed',false,'true'],[undefined,'Unavailable',true,'false'],['1','Unavailable',true,'false']]){
 context.s={joystick_swap:value};vm.runInContext('renderJoystickSwap(s)',context);
 assert.equal($('qa-swap-sub').textContent,label);assert.equal($('qa-swap').disabled,disabled);assert.equal($('qa-swap')['aria-pressed'],pressed);
}
context.joystickSwapBusy=true;context.s={joystick_swap:1};vm.runInContext('renderJoystickSwap(s)',context);assert.equal($('qa-swap').disabled,true);
const css=read('src/webui/assets/style.css');
assert(css.includes('#qa-swap:hover:not(:disabled), #qa-swap:focus-visible { border-color: var(--green); }'));
assert(css.includes('#qa-swap:focus-visible { outline-color: var(--green); }'));
assert(css.includes('#qa-swap .tile-ico, #qa-swap .tile-t { color: var(--green); }'));
assert(css.includes('border: 1px solid var(--border);'));
assert(css.includes('.tile:hover:not(:disabled) {\n  border-color: currentColor;'));
console.log('PASS: joystick presentation, unchanged numeric status contract, busy/unavailable states, scoped green hover/focus and preserved normal/peer borders');
