import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';
import { updateHotkeys, showInstructions } from '../../src/webui/assets/js/instructions.js';

export function runTests() {
  const log = []; let passed = 0, failed = 0;
  const test = (name, fn) => { try { fn(); passed++; } catch(e) { failed++; log.push('FAIL '+name+' '+e.message); } };
  const nodes = new Map();
  const node = () => ({style:{}, dataset:{}, children:[], textContent:'', hidden:false,
    setAttribute(){}, addEventListener(){}, append(...items) { this.children.push(...items); }, replaceChildren() { this.children=[]; }});
  const $ = id => { if (!nodes.has(id)) nodes.set(id,node()); return nodes.get(id); };
  const source = readFileSync(new URL('../../src/webui/assets/js/dashboard.js', import.meta.url),'utf8');
  const thermal = source.slice(source.indexOf('function renderTemp('),source.indexOf('function scheduleStatus('));
  const {renderTemp, renderThermalFlags} = new Function('$',thermal+';return {renderTemp,renderThermalFlags};')($);
  test('Log 20 CPU temperature gauge widths, colors and missing data', () => {
    const samples = [
      [29.9, 0, 'green', 'v-ok'],
      [30, 0, 'green', 'v-ok'],
      [40, 52.870, 'green', 'v-ok'],
      [60, 84.259, 'green', 'v-ok'],
      [60.1, 84.360, 'yellow', 'v-warn'],
      [64.9, 88.872, 'yellow', 'v-warn'],
      [65, 88.959, 'orange', 'v-orange'],
      [69.9, 92.994, 'orange', 'v-orange'],
      [70, 93.071, 'red', 'v-bad'],
      [80, 100, 'red', 'v-bad'],
      [81, 100, 'red', 'v-bad'],
    ];
    for (const [temp, width, color, textClass] of samples) {
      renderTemp(temp);
      const bar = $('d-temp-bar').style;
      assert.match(bar.width, /%$/);
      assert.ok(Math.abs(parseFloat(bar.width) - width) < 0.001, `Gauge width at ${temp} °C: ${bar.width}`);
      assert.equal(bar.background, `var(--${color})`, `Gauge color at ${temp} °C`);
      assert.equal($('d-temp').className, textClass);
      assert.equal($('d-tempmeter').hidden, false);
    }
    renderTemp(null);
    assert.equal($('d-tempmeter').hidden, true);
    assert.equal($('d-temp-bar').style.width, '0%');
  });
  test('Every voltage/throttling condition is red; clear is green', () => {
    for (const [bit,id] of [[0,'d-uv'],[16,'d-uv-boot'],[1,'d-thr'],[2,'d-thr'],[3,'d-thr'],[17,'d-thr-boot'],[18,'d-thr-boot'],[19,'d-thr-boot']]) {
      renderThermalFlags(1 << bit); assert.equal($(id).className,'v-bad'); assert.ok($(id).textContent.startsWith('Yes'));
    }
    renderThermalFlags(0);
    for (const id of ['d-uv','d-uv-boot','d-thr','d-thr-boot']) { assert.equal($(id).className,'v-ok'); assert.equal($(id).textContent,'No'); }
    renderThermalFlags(null); assert.equal($('d-uv').textContent,'—');
  });
  const previous = globalThis.document;
  globalThis.document = {getElementById:$,createElement:node};
  try {
    test('Instruction index contains ten topics', () => { showInstructions(); assert.equal($('instructions-index').children.length,10); });
    test('Hotkeys update after settings changes and are rendered as text', () => {
      showInstructions('hotkeys');
      updateHotkeys(['Warp','None','None','Menu','Soft Reset','None','None','Menu']);
      assert.equal($('e64-action-0').textContent,'Warp');
      assert.equal($('e64-action-4').textContent,'Soft Reset');
      updateHotkeys(['<changed>'], 'next-config');
      assert.equal($('e64-action-0').textContent,'<changed>');
      assert.equal($('live-hotkeys').dataset.configId,'next-config');
      assert.equal($('e64-action-4').textContent,'Unavailable');
    });
  } finally { globalThis.document=previous; }
  return {passed,failed,log};
}
