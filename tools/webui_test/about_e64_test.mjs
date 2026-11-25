import assert from 'node:assert/strict';
import fs from 'node:fs';
import {initAbout} from '../../src/webui/assets/js/about.js';
const html=fs.readFileSync('src/webui/assets/index.html','utf8');
const css=fs.readFileSync('src/webui/assets/style.css','utf8');
assert.ok(html.includes('Built out of a love for the Commodore 64,<br>and with thanks to those who keep it alive.'));
for(const text of ['Enhanced 64 — v1.0','For the Raspberry Pi 3B+','E64 V1 — derived from BMC64, powered by VICE and Circle'])assert.ok(html.includes(text));
const sidebar=html.match(/<aside class="sidebar">([\s\S]*?)<\/aside>/)[1];
assert.match(sidebar,/<\/dl>\s*<\/div>\s*<button class="btn about-e64-button" id="about-e64-button" type="button">About E64<\/button>/);
assert.equal([...html.matchAll(/id="about-e64-button"/g)].length,1);
assert.ok(!html.slice(html.indexOf('<main')).includes('id="about-e64-button"'));
assert.match(css,/\.sidebar \{[^}]*height: 100vh;[^}]*overflow-y: auto;/);
assert.ok(css.includes('.sidebar-bottom { margin-top: auto; margin-bottom: 32px; display: flex; flex-direction: column; gap: 8px; flex: none; }'));

assert.match(html,/<form method="dialog"><button class="btn" aria-label="Close About E64">Close<\/button><\/form>/);
assert.ok(css.includes('.about-e64-content { text-align: center; }'));
assert.ok(css.includes('.about-e64-button { width: 100%; }'));
assert.ok(css.includes('grid-template-columns: 64px minmax(0, 1fr) 64px'));
const old=globalThis.document;const listeners={};let focused=null,opens=0;
const button={isConnected:true,addEventListener:(type,fn)=>listeners['button:'+type]=fn,focus(){focused=this;}};
const close={focus(){focused=this;}};
const popup={dataset:{},open:false,addEventListener:(type,fn)=>listeners['popup:'+type]=fn,querySelector:()=>close,close(){this.open=false;listeners['popup:close']();},show(){this.open=true;opens++;}};
globalThis.document={getElementById:id=>id==='about-e64-button'?button:popup};
try {
 initAbout();listeners['button:click']();assert.equal(popup.open,true);assert.equal(focused,close);
 listeners['button:click']();assert.equal(opens,1);
 // Native method=dialog Close and native Escape both dispatch this close event.
 for(const cause of ['Close','Escape']){if(cause==='Escape'){let prevented=false;listeners['popup:cancel']({preventDefault(){prevented=true;}});assert.ok(prevented);}else popup.close();assert.equal(popup.open,false);assert.equal(focused,button,cause);listeners['button:click']();assert.equal(popup.open,true);}
 button.isConnected=false;focused=close;listeners['popup:close']();assert.equal(focused,close);
}finally{globalThis.document=old;}
console.log('PASS: About E64 placement, exact approved statement, centered responsive styles, nonmodal open/Close/Escape focus contract; real browser checks provided separately');
