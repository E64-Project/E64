import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync('src/webui/assets/js/configs.js','utf8');
const a=source.indexOf('async function changeProtection('),b=source.indexOf('// The card\'s file buttons',a);
let accepted=false,calls=[],on=true,refresh=0,messages=[];
const context=vm.createContext({confirmE64:async()=>accepted,sleep:async()=>{},loadConfigs:async()=>refresh++,setMsg:(...x)=>messages.push(x),
api:{setConfigProtection:async(id,value,confirmed)=>{calls.push([id,value,confirmed]);on=value;},getConfigProtection:async()=>({ready:true,error:'',protected:on?['geos']:[]})}});
vm.runInContext(source.slice(a,b),context);
await vm.runInContext('changeProtection({id:"geos",name:"GEOS"},false)',context);assert.equal(calls.length,0);
accepted=true;await vm.runInContext('changeProtection({id:"geos",name:"GEOS"},false)',context);assert.deepEqual(calls,[['geos',false,true]]);
accepted=false;await vm.runInContext('changeProtection({id:"geos",name:"GEOS"},true)',context);assert.deepEqual(calls.at(-1),['geos',true,false]);assert.equal(refresh,2);
assert(!source.includes('function mainActions('));
assert(!source.includes('MAIN_CONFIG_NAME'));

assert(source.includes('lastState.protectedIds.has(p.id) || [lastState.running'));
console.log('PASS: browser Cancel sends no unprotect request; confirmed Off and On use distinct consent; retired Config UI absent; protected Delete hidden.');
