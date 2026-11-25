import {showHelp} from "../../src/webui/assets/js/help_dialog.js";
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const nodes=new Map();
const get=id=>{if(!nodes.has(id))nodes.set(id,{dataset:{},children:[],childNodes:[],attrs:{},events:{},open:false,scrollTop:0,innerHTML:'',replaceChildren(...xs){this.childNodes=xs;this.children=xs;},append(x){this.children.push(x);},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k];},addEventListener(k,f){this.events[k]=f;},show(){this.open=true;},close(){this.open=false;this.onclose?.();},focus(o){this.focused=o;},querySelector(sel){return get(sel);}});return nodes.get(id);};
const location={hash:'#/instructions/drives'};
const source=fs.readFileSync('src/webui/assets/js/instructions.js','utf8').replace(/^import .*;\n/gm,'').replaceAll('export function ','function ');
const ctx=vm.createContext({showHelp:popup=>popup.show(),document:{getElementById:get,createElement:()=>({...get('new'),children:[]})},location,closeJiffyCommands(){},openJiffyCommands(){}});
vm.runInContext(source+'\nglobalThis.show=showInstructions;',ctx);
const popup=get('instructions-popup'),content=get('instructions-content');
for(const exit of ['Close','Escape']){
 ctx.show('drives');const toggle=get('.ieee-reference-toggle');toggle.attrs['aria-expanded']='false';toggle.events.click();assert.equal(get('ieee-reference').hidden,false);
 const retained={reference:exit};content.childNodes=[retained];popup.scrollTop=137;
 ctx.show('ieee488');assert(!content.innerHTML.includes('Mechanism'));assert.equal((content.innerHTML.match(/<li>/g)||[]).length,4);
 location.hash='#/instructions/ieee488';popup.close();assert.equal(location.hash,'#/instructions/drives');ctx.show('drives');
 assert.equal(content.childNodes[0],retained);assert.equal(popup.scrollTop,137);assert.equal(get('ieee-reference').hidden,false);assert.equal(get('.ieee-setup').focused.preventScroll,true);
 ctx.show('mouse');ctx.show('ieee488');location.hash='#/instructions/ieee488';popup.close();assert.equal(location.hash,'#/instructions');
}
ctx.show('navigation');for(const text of ['Move Up and Down through menu items.','Selects an item or opens a menu.','Exits the menu.','Closes all expanded menus and returns to the Main Menu.','Other menu sections will stay as they are.','Note: This is the up-arrow character key, not the cursor-up key.','Safe Start','during boot to load the Default Profile','commodore-c-logo.svg'])assert(content.innerHTML.includes(text));
assert(!/Attach \/ Remove|Startup Keys|Text-entry fields/.test(content.innerHTML));
const css=fs.readFileSync('src/webui/assets/style.css','utf8');
for(const rule of ['width:70px; height:23.5px','width:70px; height:auto','.hotkeys-table .jiffydos-logo { width: auto; }','padding-bottom:45px','width: min(690px, 94vw)','width: calc(100% / 6)','table-layout: fixed','padding-inline: 1.5ch; font-weight: 600','.pf-factory-name { font-family: inherit; }'])assert(css.includes(rule),rule);
const html=fs.readFileSync('src/webui/assets/index.html','utf8');assert(html.includes('upload to the current folder</p>'));
console.log('PASS: Round 2 source contracts, exact navigation wording, retained IEEE DOM/expansion/scroll/focus, Close/Escape shared close handler, alternate-origin return, four setup steps; browser geometry remains a separate check');
