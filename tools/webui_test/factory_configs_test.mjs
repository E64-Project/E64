import assert from 'node:assert/strict';
import fs from 'node:fs';
import {FACTORY_CONFIGS, isFactory, idValid, parseActive} from '../../src/webui/assets/js/configs_data.js';
const source=fs.readFileSync(new URL('../../src/webui/assets/js/configs.js',import.meta.url),'utf8');
const actions=source.match(/function configActions\(p\) \{([\s\S]*?)\n\}/)[1];
const configActions=new Function('p','isFactory',actions);
for(const config of FACTORY_CONFIGS){
 assert(idValid(config.id));assert(isFactory(config.id));
 assert.deepEqual(configActions(config,isFactory),{buttons:[],menu:[]});
 assert.equal(parseActive(`config=${config.id}\n`).config,config.id);
}
assert.equal(FACTORY_CONFIGS.length,1);assert.equal(FACTORY_CONFIGS[0].name,'Default');assert(isFactory('_factory-pal'));assert(idValid('_factory-pal'));
assert.equal(idValid('_user'),false);
assert(source.includes('row.appendChild(make(!first))'));
assert(!source.includes('if (!isFactory(p.id)) row.appendChild(make(!first))'));
assert(source.includes('"pf-active-marker", p.id === state.running ? "*" : ""'));
assert(source.includes('"pf-name-text", p.name'));
assert(source.includes('if (p && !isFactory(p.id)) configs.push(p)'));
console.log('PASS: Web factory entries, immutable actions, persistent IDs, active markers and aligned labels');
