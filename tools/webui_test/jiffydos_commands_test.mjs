import assert from "node:assert/strict";
import { openJiffyCommands, closeJiffyCommands } from "../../src/webui/assets/js/jiffydos_commands.js";
// User-supplied JiffyDOS v6.01 reference is the contract, independent of rendering.
const expected = {
  disk: [["@","Drive status"],["@$","Directory"],["@#","Set default device"],["CTRL+D","Change default device"],["@I","Initialize drive"],["@UJ","Reset drive"],["@V","Validate disk"],["@N","Format disk"],["@B","Disable 1541 head rattle"]],
  files: [["@R","Rename"],["@S","Scratch (delete)"],["@C","Copy on same disk"],["@L","Lock/unlock"],["@D","List BASIC file"],["@T","List text file"],["@O","Un-NEW BASIC"]],
  programs: [["/file","Load BASIC"],["↑file","Load and run BASIC"],["←file","Save BASIC"],["%file","Load machine language"],["£file","Load and run machine language"],["SHIFT+RUN/STOP","Load and run first disk program"]],
  advanced: [["@G","Set interleave"],["@P","Toggle printer output"],["CTRL+P","Print screen"],["@F","Disable function keys"],["@Q","Disable commands"],["@X","Destination device"],["CTRL+A","Toggle all files for copy"],["CTRL+W","Toggle one file for copy"],["SYS 58451","Re-enable commands"],["SYS 58551","Re-enable commands and function keys"]],
};
class Element {
  constructor(){this.children=[];this.dataset={};this.attributes={};this.events={};this.open=false;this.isConnected=true;this._text="";}
  get textContent(){return this._text+this.children.map(c=>c.textContent).join("");}
  set textContent(value){this._text=value;this.children=[];}
  append(...nodes){this.children.push(...nodes);}
  replaceChildren(){this.children=[];this._text="";}
  setAttribute(key,value){this.attributes[key]=value;}
  addEventListener(key,fn){(this.events[key] ||= []).push(fn);}
  fire(key,event={}){for(const fn of this.events[key] || [])fn(event);}
  focus(){document.activeElement=this;}
  show(){this.open=true;}
  close(){this.open=false;this.fire("close");}
}
const previous=globalThis.document,nodes=new Map();
const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
const tabs=Object.keys(expected).map(key=>{const t=new Element();t.dataset.commandTab=key;return t;});
const popup=get("jiffydos-commands-popup");popup.querySelectorAll=()=>tabs;
popup.querySelector=()=>tabs.find(t=>t.attributes["aria-selected"]==="true");
globalThis.document={getElementById:get,createElement:()=>new Element()};
try {
  const trigger=new Element();openJiffyCommands(trigger);assert.equal(popup.open,true);
  for(const [index,[key,rows]] of Object.entries(Object.entries(expected))){
    tabs[index].fire("click");
    const actual=get("jiffy-command-rows").children.map(row=>row.children.map(c=>c.textContent));
    assert.deepEqual(actual,rows,key);
    assert.equal(tabs.filter(t=>t.attributes["aria-selected"]==="true").length,1);
    assert.equal(get("jiffy-command-panel").attributes["aria-labelledby"],"jiffy-tab-"+key);
    assert.equal(tabs[index].tabIndex,0);
    assert.equal(popup.scrollTop,0);
  }
  let prevented=false;
  tabs[3].fire("keydown",{key:"ArrowRight",preventDefault(){prevented=true;}});
  assert.ok(prevented);assert.equal(document.activeElement,tabs[0]);
  tabs[0].fire("keydown",{key:"ArrowLeft",preventDefault(){}});assert.equal(document.activeElement,tabs[3]);
  tabs[3].fire("keydown",{key:"Home",preventDefault(){}});assert.equal(document.activeElement,tabs[0]);
  tabs[0].fire("keydown",{key:"End",preventDefault(){}});assert.equal(document.activeElement,tabs[3]);
  closeJiffyCommands();assert.equal(popup.open,false);assert.equal(document.activeElement,trigger);
  openJiffyCommands(trigger);assert.equal(get("jiffy-command-rows").children.length,9);
  assert.ok(tabs.every(t=>t.events.click.length===1 && t.events.keydown.length===1));
  closeJiffyCommands();closeJiffyCommands();
} finally {globalThis.document=previous;}
console.log("PASS: all 32 exact JiffyDOS command/description pairs, four tabs, selected states, keyboard wrapping/Home/End, focus return, reopen defaults and no duplicate handlers");
