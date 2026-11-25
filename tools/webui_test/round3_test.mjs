import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {confirmE64} from '../../src/webui/assets/js/dialog.js';
import {showHelp,initHelpNavigation} from '../../src/webui/assets/js/help_dialog.js';
import {openJiffyCommands,closeJiffyCommands} from '../../src/webui/assets/js/jiffydos_commands.js';
import {showInstructions} from '../../src/webui/assets/js/instructions.js';
import {rememberVolumes,volumeLabel} from '../../src/webui/assets/js/volumes.js';
import {normPath} from '../../src/webui/assets/js/util.js';
import {initLogo,updateLogoVersion} from '../../src/webui/assets/js/logo.js';
class El {
 constructor(){this.dataset={};this.attrs={};this.events={};this.children=[];this.childNodes=[];this.isConnected=true;this.open=false;this.hidden=false;this.style={};}
 addEventListener(k,f){(this.events[k]??=[]).push(f);}
 fire(k,e={}){for(const f of this.events[k]||[])f(e);this['on'+k]?.(e);}
 append(...els){this.children.push(...els);}
 replaceChildren(...els){this.children=els;this.childNodes=els;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k];}
 show(){this.open=true;this.modal=false;}
 showModal(){this.open=true;this.modal=true;}
 close(value=''){this.returnValue=value;this.open=false;this.fire('close');}
 remove(){this.isConnected=false;}
 focus(){document.activeElement=this;}
 querySelector(sel){if(sel.includes('aria-selected'))return tabs.find(t=>t.attrs['aria-selected']==='true');return get(sel);}
 querySelectorAll(){return tabs;}
}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new El());return nodes.get(id);};
const tabs=['disk','files','programs','advanced'].map(key=>{const e=new El();e.dataset.commandTab=key;return e;});
const links=['dashboard','files','configs','instructions'].map(view=>{const e=new El();e.dataset.view=view;return e;});
const previous=globalThis.document,previousLocation=globalThis.location;
globalThis.document={body:new El(),addEventListener(){},querySelector(){return null;},getElementById:get,createElement:()=>new El(),querySelectorAll:()=>links,activeElement:null};
globalThis.location={hash:'#/instructions/hotkeys'};
try {
 initHelpNavigation();
 for(const id of ['instructions-popup','jiffydos-commands-popup','about-e64-popup']){
  const popup=get(id);showHelp(popup);assert(popup.open&&!popup.modal);
  let prevented=false;popup.fire('keydown',{key:'Escape',preventDefault(){prevented=true;},stopPropagation(){}});assert(prevented&&!popup.open);
  for(const link of links){showHelp(popup);let returned=false;popup.onclose=()=>returned=true;link.fire('click');await Promise.resolve();assert(!popup.open&&!returned);assert.equal(document.activeElement,link);}
 }
 showInstructions('hotkeys');
 const help=get('instructions-popup'),button=get('hotkeys-commands'),commands=get('jiffydos-commands-popup');
 assert(!button.hidden);button.onclick();assert(help.open&&help.hidden&&help.inert&&commands.open&&!commands.modal);
 commands.close();assert(help.open&&!help.hidden&&!help.inert);assert.equal(document.activeElement,button);
 for(const key of ['drives','sid','mouse','navigation']){showInstructions(key);assert(button.hidden);}
 showInstructions('navigation');assert(!get('navigation-help-note').hidden);
 // Actual destructive-confirmation implementation still uses showModal, and
 // the help navigation allowlist never includes the live confirmation/editor.
 const dialogSource=fs.readFileSync('src/webui/assets/js/dialog.js','utf8');
 assert(dialogSource.includes('dialog.showModal()'));
 const editorSource=fs.readFileSync('src/webui/assets/js/editor.js','utf8');
 assert(editorSource.includes('keydown'));
 const pending=confirmE64('Delete file?','Delete');
 const modal=document.body.children.at(-1);assert(modal.open&&modal.modal);
 links[0].fire('click');await Promise.resolve();assert(modal.open&&modal.modal);
 let prevented=false;modal.fire('cancel',{preventDefault(){prevented=true;}});
 assert(prevented&&!modal.open);assert.equal(await pending,false);
 let draws=[];get('logo-version-text').getContext=()=>({clearRect(){draws=[];},fillRect(...args){draws.push(args);}});
 get('logo-version').hidden=true;initLogo();updateLogoVersion('1.0-branding-test');
 assert.equal(get('logo-version-text').attrs['aria-label'],'V 1.0');assert(draws.length>20);
 get('logo-toggle').fire('click');assert(!get('logo-version').hidden);assert.equal(get('logo-toggle').attrs['aria-pressed'],'true');
 updateLogoVersion('12.34-release');assert.equal(get('logo-version-text').attrs['aria-label'],'V 12.34');
 get('logo-toggle').fire('click');assert(get('logo-version').hidden);
 updateLogoVersion('<script>');assert.equal(get('logo-version-text').attrs['aria-label'],'V 12.34');
 rememberVolumes([{id:'USB',label:'Internal'},{id:'USB2',label:'Games\u0000'}]);assert.equal(volumeLabel('USB'),'USB1: Internal');assert.equal(volumeLabel('USB2'),'USB2: Games');assert.equal(volumeLabel('USB3'),'USB3');
 rememberVolumes([{id:'USB',label:'Replacement'}]);assert.equal(volumeLabel('USB'),'USB1: Replacement');assert.equal(volumeLabel('USB2'),'USB2');
 const fileSource=fs.readFileSync('src/webui/assets/js/files.js','utf8');
 const start=fileSource.indexOf('async function transferEntry('),end=fileSource.indexOf('\n}',start)+2;
 let payload;
 const transferContext=vm.createContext({normPath,document,pickDestination:async()=>({vol:'SD',folder:'/'}),api:{transferEntry:async(...args)=>{payload=args;}},$:get,loadDir:async()=>{},showError:message=>{throw Error(message);}});
 vm.runInContext("let fbVol='USB',fbPath='/from';\n"+fileSource.slice(start,end)+"\nglobalThis.transfer=transferEntry;",transferContext);
 await transferContext.transfer('/from/file.prg','file.prg',true);
 assert.deepEqual(Array.from(payload),['USB','/from/file.prg','SD','/',true]);
 const css=fs.readFileSync('src/webui/assets/style.css','utf8'),html=fs.readFileSync('src/webui/assets/index.html','utf8');
 for(const value of ['width:min(700px, 94vw)','padding-bottom:45px','height:min(590px, 88dvh)','grid-template-columns:repeat(4, minmax(0, 1fr))','border:5px solid #FF0000','background:#FFFFFF','image-rendering:pixelated'])assert(css.includes(value),value);
 assert(!/ieee-reference-toggle.*::before/.test(css));
 assert(html.includes('Commands taken from the JiffyDOS v6.01 manual'));
 assert(html.includes('These keys control the Pi64 on-screen menu, not the webpage.'));
 assert(html.includes('id="logo-version" hidden'));
 // Production prompt/confirmation with existing fake DOM, including Escape
 // and focus, is exercised by ui_polish_test in the retained main runner.
 console.log('PASS: informational nonmodal Escape/sidebar/focus, Hotkeys Commands return, modal isolation, dynamic CHARGEN version toggle, reconnect labels and approved sizes/styles');
} finally {globalThis.document=previous;globalThis.location=previousLocation;}
