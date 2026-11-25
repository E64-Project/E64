// Execute the browser harness predicates without starting a browser.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync('tools/webui_test/unified_ui_browser_check.py','utf8');
const helper=source.slice(source.indexOf('function desktopDialogGeometry('),source.indexOf('\n\nconst buttons='));
const widthPredicate=source.match(/check\('compact desktop popup width',([^,]+),rect/)[1];
const checks=[];
function element(width=700,height=680,props={}){
 const e={bounds:{left:200,right:200+width,top:50,bottom:50+height,width,height},tagName:'DIV',id:'',scrollWidth:width,clientWidth:width,clientLeft:0,childNodes:[],parentElement:null,
 style:{display:'block',visibility:'visible',overflowX:'visible'},classList:{contains:()=>false},getAttribute:()=>'',getClientRects(){return [this.bounds];},querySelectorAll(){return this.children||[];},...props};return e;
}
const context=vm.createContext({innerWidth:1280,innerHeight:900,document:{documentElement:{scrollWidth:1280},createRange:()=>({selectNodeContents(n){this.n=n;},getClientRects(){return [this.n.bounds];}})},getComputedStyle:e=>e.style,box:e=>e.bounds,rect:r=>r,check:(name,pass,measurements)=>checks.push({name,pass,measurements}),popup:element()});
vm.runInContext(helper,context);
function run(child,pass=true){
 context.popup=element();if(child){child.parentElement=context.popup;context.popup.children=[child];}
 checks.length=0;vm.runInContext("desktopDialogGeometry(popup,'test',700,680)",context);
 const result=checks.find(c=>c.name.includes('no horizontal'));
 assert.equal(result.pass,pass,JSON.stringify(result));
 if(!pass)assert(result.measurements.offenders.length);
 return result;
}
for(const [width,height] of [[700,680],[690,594],[620,640]]){
 context.popup=element(width,height);checks.length=0;
 vm.runInContext(`desktopDialogGeometry(popup,'test',${width},${height})`,context);assert(checks.every(c=>c.pass));
}
context.popup=element();assert(vm.runInContext(widthPredicate,context));
context.popup=element(750);assert(!vm.runInContext(widthPredicate,context));
// Inline/table metrics and outward absolute decorations are not clipping regions.
run(element(100,20,{clientWidth:0,scrollWidth:100}));
const decoration=element(100,20,{bounds:{left:310,right:410,top:60,bottom:61,width:100,height:1}});
const owner=element(80,30,{scrollWidth:210,children:[decoration]});decoration.parentElement=owner;
context.popup=element();owner.parentElement=context.popup;context.popup.children=[owner,decoration];checks.length=0;
vm.runInContext("desktopDialogGeometry(popup,'test',700,680)",context);assert(checks.every(c=>c.pass));
run(element(1,1,{scrollWidth:100,style:{display:'block',position:'absolute',overflowX:'hidden',clipPath:'inset(50%)'},classList:{contains:c=>c==='sr-only'}}));
run(element(100,20,{style:{display:'none'},scrollWidth:500}));
run(element(100,20,{scrollWidth:101,style:{overflowX:'auto'}}));
// Borders use the inner client region; padding is already included in clientWidth.
run(element(100,20,{clientLeft:2,clientWidth:96,childNodes:[{nodeType:3,textContent:'fits',bounds:{left:202,right:298,width:96,height:12}}],style:{overflowX:'hidden'}}));
run(element(100,20,{style:{overflowX:'hidden'},childNodes:[{nodeType:3,textContent:'rounding',bounds:{left:199.5,right:300.5,width:101,height:12}}]}));
// A hidden-overflow class name alone cannot exempt visible clipped text.
run(element(1,1,{classList:{contains:c=>c==='sr-only'},style:{overflowX:'hidden'},childNodes:[{nodeType:3,textContent:'visible',bounds:{left:200,right:250,width:50,height:1}}]}),false);
// Genuine scroll ranges, right AND left escape, and clipped text must fail.
run(element(100,20,{scrollWidth:103,style:{overflowX:'auto'}}),false);
run(element(100,20,{bounds:{left:950,right:1050,width:100,height:20}}),false);
run(element(100,20,{bounds:{left:190,right:290,width:100,height:20}}),false);
run(element(100,20,{style:{overflowX:'hidden'},childNodes:[{nodeType:3,textContent:'too wide',bounds:{left:200,right:310,width:110,height:20}}]}),false);
run(element(100,20,{childNodes:[{nodeType:3,textContent:'escaped text',bounds:{left:200,right:1100,width:900,height:20}}]}),false);
const clippedChild=element(110,20);
const clipper=element(100,20,{style:{overflowX:'hidden'}});clippedChild.parentElement=clipper;
context.popup=element();clipper.parentElement=context.popup;context.popup.children=[clipper,clippedChild];checks.length=0;
vm.runInContext("desktopDialogGeometry(popup,'test',700,680)",context);
assert(checks.some(c=>!c.pass&&c.measurements.offenders.some(o=>o.reason==='element outside clipping region')));
context.document.documentElement.scrollWidth=1283;run(null,false);context.document.documentElement.scrollWidth=1280;
console.log('PASS: actual browser geometry helper accepts intentional geometry and rejects scrolling, left/right escape and clipped text; failures include numeric diagnostics');
if(process.argv[2]){
 const records=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));assert.equal(records.length,34);
 for(const record of records)assert.deepEqual(record.checks.filter(c=>!c.pass).map(c=>c.name),['Hotkeys','Commands DISK','Commands FILES','Commands PROGRAMS','Commands ADVANCED'].map(n=>n+' no horizontal clipping or scrolling'));
 console.log('PASS: saved Firefox failures isolated to five old overflow predicates. No numeric offender evidence; corrected helper requires another Firefox run.');
}
