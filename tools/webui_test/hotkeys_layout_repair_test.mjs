import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const css=fs.readFileSync('src/webui/assets/style.css','utf8');
const html=fs.readFileSync('src/webui/assets/js/instructions.js','utf8');
assert.ok(!/\.hotkey-pair::(?:before|after)/.test(css),'Row pseudo-elements must not create anonymous table cells');
assert.ok(html.includes('<col class="action-col"><col class="physical-key-col"><col class="action-col">'));
assert.ok(css.includes('--action-width: 185px')&&css.includes('--physical-width: 128px'));
assert.ok(css.includes('white-space: nowrap;')&&css.includes('overflow-wrap: normal; text-wrap: balance;'));
assert.ok(css.includes('.hotkey-divider-left { right: 100%; }')&&css.includes('.hotkey-divider-right { left: 100%; }'));
assert.ok(css.includes('var(--action-width)'));
assert.ok(html.includes('class="hotkeys-scroll" tabindex="0" role="region"'));
const tableRule=css.match(/\.instructions \.hotkeys-table \{ --modifier-width:[^}]+/)[0];
const dimension=name=>Number(tableRule.match(new RegExp('(?:^|[;{])\\s*'+name+': (\\d+)px'))[1]);
const physical=css.match(/\.c64-keycap \{[^}]+/)[0];
const capWidth=Number(physical.match(/width: (\d+)px/)[1]);
assert.equal(dimension('width'),602);
assert.equal(2*dimension('--modifier-width')+2*dimension('--action-width')+dimension('--physical-width'),602);
assert.equal((dimension('--physical-width')-capWidth)/2,16,'Compact caps retain full 16px gaps');
assert.ok(css.includes('height: 108px;'));
assert.ok(css.includes('font-size: 18px; font-weight: 600'));
assert.ok(!/transform:\s*scale\(/.test(tableRule+physical),'Use actual layout dimensions');
const python=fs.readFileSync('tools/webui_test/unified_ui_browser_check.py','utf8');
const script=python.split("SCRIPT=r'''\n")[1].split("\n'''")[0];
assert.ok(script);
for(const condition of ['l.right<=k.left-15&&q.left>=k.right+15','!intersects(l,k)&&!intersects(q,k)','no F-keycap overlaps adjacent action text','no action text is clipped','complete table centered in popup','mobile can reach far-right SHIFT caps','Math.abs(k.left-l.right-16)<1','Math.abs(q.left-k.right-16)<1','Math.abs(r.left-l.left)<0.1','Math.abs(q.right-r.right)<0.1','neither divider protrudes beyond actual table','l.left>=t.left-0.1&&q.right<=t.right+0.1'])assert.ok(script.includes(condition));
assert.ok(python.includes('if verified and temporary.exists():temporary.rename(shot)'));
// Run the actual screenshot-preparation code with an earlier validation failure.
// Every requested screen must replace the stale Hotkeys modal before capture.
const prepare=script.slice(script.indexOf('// Always prepare the requested screen'));
const screens=['dashboard','files','configs','instructions','hotkeys','roms','drives','ieee488','sid','mouse','navigation','new-folder','commands','editor','confirmation','destination','move-destination','storage','easter-egg','rainbow','about'];
for(const screen of screens){
 const views=['dashboard','files','configs','instructions'].map(id=>({id:'view-'+id,hidden:id!=='instructions'}));
 const dialogs=[];const add=id=>{let d=dialogs.find(d=>d.id===id);if(!d){d={id,open:false,dataset:{},events:{},addEventListener(type,fn){this.events[type]=fn;},close(){this.open=false;this.events.close?.();}};dialogs.push(d);}d.open=true;return d;};
 const help=add('instructions-popup');help.dataset.topic='hotkeys';
 const editor={hidden:true},title={textContent:''},nodes={'editor':editor,'ed-title':title,'ed-hint':{textContent:''},'logo-toggle':{click(){}},'pf-restart':{hidden:true},'instructions-popup':help,'about-e64-button':{click:()=>add('about-e64-popup')},'ed-close':{click(){editor.hidden=true;}}};
 const results=[{name:'injected earlier layout failure',pass:false}];let posted;
 const document={getElementById:id=>nodes[id],documentElement:{dataset:{}},fonts:{ready:Promise.resolve()},querySelectorAll:q=>q==='dialog[open]'?dialogs.filter(d=>d.open):q==='section.view'?views:q==='.act-item'?['Copy To >','Move To >'].map(textContent=>({textContent,click:()=>add('')})):[],querySelector:q=>q==='.function-reference-actions button'?{click:()=>add('jiffydos-commands-popup')}:q==='.destination-dialog[open]'?dialogs.find(d=>!d.id&&d.open):q==='dialog[open]'?dialogs.find(d=>d.open):null};
 document.querySelectorAllBase=document.querySelectorAll;
 document.querySelectorAll=q=>q==='#fb-rows tr'?[{textContent:'demo.d64',querySelector:()=>({click(){}})}]:document.querySelectorAllBase(q);
 const context=vm.createContext({document,URL,location:{href:'http://fixture/?screen='+screen},results,check:(name,pass)=>results.push({name,pass:!!pass}),view:name=>views.forEach(v=>v.hidden=v.id!=='view-'+name),showInstructions:topic=>{if(topic==='commands')add('jiffydos-commands-popup');else if(topic)add('instructions-popup').dataset.topic=topic==='roms'?'drives':topic;},folder:()=>add(''),confirmE64:()=>add(''),openEditor:()=>{editor.hidden=false;title.textContent='notes.txt';},pause:async()=>{},waitFor:async fn=>assert.ok(fn(),'preparation wait'),requestAnimationFrame:fn=>fn(),fetch:async(url,{body})=>{posted=JSON.parse(body);}});
 await vm.runInContext('(async()=>{'+prepare+'})()',context);
 assert.equal(posted.screen,screen);assert.equal(posted.capture_ready,true,screen);assert.equal(posted.checks[0].pass,false,'validation failure must remain a failure');assert.equal(document.documentElement.dataset.captureScreen,screen);
}
console.log('PASS: Hotkeys explicit columns/independent dividers and geometry guards; all 21 screenshot targets prepare correctly despite a prior validation failure, including editor replacing Hotkeys');
