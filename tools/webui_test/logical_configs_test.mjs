// Exercise both real confirmation stages and request-specific completion.
import fs from 'node:fs';import vm from 'node:vm';import assert from 'node:assert/strict';
const source=fs.readFileSync('src/webui/assets/js/configs.js','utf8');
const start=source.indexOf('async function changeDeleted('),end=source.indexOf('async function changeProtection(',start),action=source.slice(start,end);
let answers=[],calls=[],questions=[],refreshes=0,messages=[],state={ready:true,operation:{request_id:7,id:'geos',state:2}};
const context=vm.createContext({confirmE64:async(...args)=>{questions.push(args);return answers.shift();},sleep:async()=>{},setMsg:(...args)=>messages.push(args),loadConfigs:async()=>{refreshes++;},api:{deleteConfigPermanent:async(...args)=>{calls.push(args);return {request_id:7};},getDeletedConfigs:async()=>state}});
vm.runInContext(action,context);
for(const response of [[false],[true,false]]){answers=[...response];const before=calls.length;await vm.runInContext('deleteConfig({id:"geos",name:"GEOS"})',context);assert.equal(calls.length,before);}
answers=[true,true];questions=[];await vm.runInContext('deleteConfig({id:"geos",name:"GEOS"})',context);assert.deepEqual(calls,[['geos',false]]);assert.equal(refreshes,1);
assert.deepEqual(questions,[['Delete Config "GEOS"?','Yes','No'],['Confirm permanent deletion of "GEOS"?','Yes, Delete','No']]);
answers=[true,true];await vm.runInContext('changeDeleted({id:"geos",name:"GEOS"},true)',context);assert.deepEqual(calls.at(-1),['geos',true]);
state={ready:true,operation:{request_id:7,id:'geos',state:-1,error:'Power-on Config is protected'}};answers=[true,true];await vm.runInContext('deleteConfig({id:"geos",name:"GEOS"})',context);assert.ok(messages.at(-1)[0].includes('protected'));
const done=refreshes;state={ready:true,operation:{request_id:6,id:'geos',state:2}};answers=[true,true];await vm.runInContext('deleteConfig({id:"geos",name:"GEOS"})',context);assert.equal(refreshes,done);assert.ok(messages.at(-1)[0].includes('pending'));
state={ready:false};answers=[true,true];await vm.runInContext('deleteConfig({id:"geos",name:"GEOS"})',context);assert.equal(refreshes,done);
for(const name of ['Delete','Rename'])assert.ok(fs.readFileSync('src/webui/webui_fs.cpp','utf8').split('void WebUiFs'+name+'(')[1].split('\nvoid ')[0].includes('configs_path_is_managed'));
assert.ok(!source.includes('Restore Deleted Config')&&!source.includes('Reboots Remaining'));
console.log('PASS: first No/second No cancel; two Yes delete; exact labels, legacy cleanup, stale-request/protection/storage errors; file-manager guards retained');
