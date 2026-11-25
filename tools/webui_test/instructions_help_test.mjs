import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { showInstructions, updateHotkeys, hideInstructions } from "../../src/webui/assets/js/instructions.js";
const nodes = new Map();
const node = () => ({ dataset:{}, children:[],childNodes:[], innerHTML:"", textContent:"", open:false,
  listeners:{}, setAttribute(){},querySelector(){return {addEventListener(){},focus(){}};}, addEventListener(type,fn){this.listeners[type]=fn;}, append(...items){this.children.push(...items);}, replaceChildren(){this.children=[];},
  show(){this.open=true;}, close(){this.open=false;} });
const get = id => {if(!nodes.has(id))nodes.set(id,node());return nodes.get(id);};
const previous=globalThis.document;
globalThis.document={getElementById:get,createElement:node};
function page(id){showInstructions(id);return get("instructions-content").innerHTML;}
try {
  showInstructions();
  const links=get("instructions-index").children;
  assert.equal(links.length,10);assert.equal(links.filter(link=>link.textContent==="Hotkeys").length,1);
  assert.ok(!links.some(link=>link.textContent==="E64 Hotkeys" || link.textContent==="JiffyDOS Hotkeys"));
  for (const id of ["hotkeys","jiffy"]) {
    const html=page(id), body=html.match(/<tbody>([\s\S]*?)<\/tbody>/)[1];
    const rows=[...body.matchAll(/<tr class="hotkey-pair">([\s\S]*?)<\/tr>/g)];
    assert.equal(rows.length,4);
    rows.forEach((r,i)=>{
      assert.equal([...r[1].matchAll(/<td\b/g)].length,5);
      assert.ok(r[1].indexOf("commodore-c-logo.svg")<r[1].indexOf(">CTRL<"));
      assert.ok(r[1].includes(`id="e64-action-${i}"`));
      assert.ok(r[1].includes(`id="e64-action-${i+4}"`));
      assert.ok(r[1].includes(`class="key-upper">F${2*i+1}<`));
      assert.ok(r[1].includes(`class="key-lower">F${2*i+2}<`));
    });
    const descriptions=["Directory","DList","Load","TList","Load/Run","Save","Load ML","Scratch"];
    for(const text of descriptions)assert.ok(html.includes(`>${text}</div>`),text);
    assert.ok(!html.includes('config-restore-note')&&!html.includes('function-reference-actions'));
    assert.equal(get('instructions-content').children.length,0);
    rows.forEach(r=>{const cells=[...r[1].matchAll(/<td\b[^>]*>([\s\S]*?)<\/td>/g)];assert.ok(cells[4][1].includes('>SHIFT<'));assert.ok(!/>(F[1-8])<\//.test(cells[4][1]));});
    assert.ok(!html.includes('artwork-credit') && !html.includes('Alien426'));
    assert.equal(get('instructions-title').textContent,'Hotkeys');
  }
  const navigation=page("navigation");
  for(const text of ["CRSR Keys","RETURN","← Key","Extended Menu Navigation","HOME","↑ Key","not the cursor-up key","Exits the menu.","Move Up and Down through menu items."] )assert.ok(navigation.includes(text),text);
  assert.equal(get("instructions-index").children.length,10);
  const first=["one","two","three","four","five","six","seven","eight"];
  updateHotkeys(first,"config-a");
  first[0]="changed outside API";
  for(let i=0;i<8;i++)assert.equal(get("e64-action-"+i).textContent,["one","two","three","four","five","six","seven","eight"][i]);
  page("sid");page("hotkeys");assert.equal(get("e64-action-0").textContent,"one");
  updateHotkeys(["<img onerror=bad>","replacement"],"config-b");
  assert.equal(get("live-hotkeys").dataset.configId,"config-b");
  assert.equal(get("e64-action-0").textContent,"<img onerror=bad>");
  assert.equal(get("e64-action-7").textContent,"Unavailable");
  updateHotkeys(undefined,"config-c");assert.equal(get("e64-action-0").textContent,"Unavailable");
  let html=page("drives");assert.equal([...html.matchAll(/<th scope="col">Type<\/th>/g)].length,2);
  assert.ok(html.includes('8/9 or 10/11') && html.includes('SFD-1001'));
  html=page("roms");assert.ok(!html.includes('Bytes'));
  for(const text of ['ROM','JiffyDOS','d1541II','JD-d1541II','dosCMDHD'])assert.ok(html.includes(text));
  html=page("sid");for(const text of ['Dual SID','SID2 Address','SID2 Model','0xD420','Pseudo Stereo','custom Config'])assert.ok(html.includes(text));
  assert.ok(html.includes('Both SIDs receive the same register writes.'));
  assert.ok(html.includes("It's the differences in their characteristics<br>that produce the pseudo-stereo effect."));
  assert.ok(html.includes('Choose different chip models, such as<br>a 6581 for SID1 and an 8580 for SID2.'));
  assert.equal([...html.matchAll(/<hr>/g)].length,2);
  html=page("mouse");
  assert.ok(html.includes('Note: </span><span>The 1351 protocol does not expose<br>the scroll wheel or middle button.'));
  assert.ok(!html.includes('MicroMys'));
  assert.deepEqual([...html.matchAll(/<li>(.*?)<\/li>/g)].map(m=>m[1]),['Connect a USB mouse.','Open Joyports and set Port 1 to USB Mouse (1351).','Save your custom Config.','Start GEOS and select the 1351 Mouse driver.']);
  html=page("ieee488");for(const text of ['/carts/eprom.bin','Change Drive Model','matching disk image'])assert.ok(html.includes(text));
  for(const [topic,count] of [['drives',2],['roms',2],['ieee488',0],['mouse',1],['sid',2]]) {
    const content=page(topic);
    assert.equal([...content.matchAll(/<hr>/g)].length,count,topic);
    assert.ok(!/<hr>\s*$/.test(content),topic+' no trailing rule');
    assert.ok(!/<li>[^<]*<hr>/.test(content),topic+' no instruction rules');
  }
  let sections=page('ieee488');
  assert.ok(sections.endsWith('matching disk image.</li></ol>'));
  assert.ok(!sections.includes('Dual Mechanism'));
  sections=page('mouse');assert.ok(sections.includes('select the 1351 Mouse driver.</li></ol><hr><h4>Mouse Compatibility</h4>'));
  const driveHelp=page('drives');
  assert.ok(driveHelp.includes('href="#/instructions/ieee488"')&&!driveHelp.includes('href="#/instructions/roms"'));
  assert.ok(driveHelp.endsWith('</section>'));
  assert.ok(!get('instructions-index').children.some(link=>link.href==='#/instructions/ieee488'));
  const ieeeHelp=page('ieee488');
  assert.ok(!ieeeHelp.includes('href="#/instructions/roms"'));
  assert.ok(ieeeHelp.endsWith('</ol>'), 'No empty footer paragraph or spacing');
  assert.ok(!get('instructions-index').children.some(link=>link.href==='#/instructions/roms'));
  for(const topic of ['commands','navigation'])assert.ok(get('instructions-index').children.some(link=>link.href==='#/instructions/'+topic));
  assert.ok(navigation.includes('Safe Start')&&navigation.includes('during boot to load the Default Profile'));
  hideInstructions();assert.equal(get("instructions-popup").open,false);
  const svg=readFileSync(new URL('../../src/webui/assets/commodore-c-logo.svg',import.meta.url));
  assert.equal(createHash('sha1').update(svg).digest('hex'),'132e51b7e1acb7d04fc4fc8cd9fe30d2926c74c2');
  const attribution=JSON.parse(readFileSync(new URL('../../src/webui/assets/commodore-c-logo.attribution.json',import.meta.url)));
  assert.equal(attribution.license,'CC BY-SA 4.0');
  assert.equal(attribution.author,'Alien426');
  const docs=readFileSync(new URL('../../docs/COMMODORE-ARTWORK.md',import.meta.url),'utf8');
  assert.ok(docs.includes('Alien426') && docs.includes('DigitalIceAge') && docs.includes('CC BY-SA 4.0'));
  assert.equal(attribution.sha256,createHash('sha256').update(svg).digest('hex'));
} finally {globalThis.document=previous;}
console.log('PASS: approved five-column/four-pair/eight-JiffyDOS Help; Config change and unavailable hotkey handling; native-menu terminology, ROM tables, exact GEOS steps; authentic SVG and attribution');
