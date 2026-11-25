import assert from 'node:assert/strict';
import fs from 'node:fs';
import {fileIconType, createFileIcon, FILE_ICON_TYPES} from '../../src/webui/assets/js/file_icons.js';
const extensions={floppy:['d64','d71','d81','g64','d67','d80','d82','d1m','d2m','d4m'],harddisk:['dhd'],cartridge:['crt'],tape:['tap','t64'],program:['prg','p00'],snapshot:['vsf'],rom:['rom']};
// Display dimensions differ from the original SVG/viewBox and image attributes.
const css=fs.readFileSync('src/webui/assets/style.css','utf8');
const iconStyle=css.match(/\.file-type-icon\s*\{([^}]+)\}/)?.[1];
assert.ok(iconStyle,'Shared file icon display rule exists');
for(const declaration of [/width:\s*32px\s*;/,/height:\s*32px\s*;/,/flex:\s*0\s+0\s+32px\s*;/,/image-rendering:\s*pixelated\s*;/])assert.match(iconStyle,declaration);
assert.match(css,/\.fname \.ic\s*\{[^}]*width:\s*32px;[^}]*height:\s*32px;/,'Row-specific rule must not shrink displayed icons');
let tested=0;
for(const [type,exts] of Object.entries(extensions))for(const ext of exts)for(const spelling of [ext,ext.toUpperCase(),ext[0].toUpperCase()+ext.slice(1)]){
 assert.equal(fileIconType('complete.name.'+spelling,false),type);
 assert.equal(fileIconType('/roms/disks/deep/file.'+spelling,false),type);
 assert.equal(fileIconType('directory.'+spelling,true),'directory');tested++;
}
for(const name of ['roms','disk.d64','tape.tap','cartridge.CRT','snapshot.vsf','program.prg','ROM.rom','/deep/games.dhd'])assert.equal(fileIconType(name,true),'directory');
for(const name of ['rom','dos1541','kernel.bin','disk.img','text.txt','archive.zip','test.sid','file','file.','.rom','.d64','file.unknown','file.constructor','file.__proto__','file.toString','dir.rom/file.bin','folder.d64/actual.txt'])assert.equal(fileIconType(name,false),'unknown',name);
const previous=globalThis.document;
globalThis.document={createElement(tag){return {tag,attrs:{},dataset:{},setAttribute(k,v){this.attrs[k]=v;}};}};
try{
 for(const [type,[asset,label]] of Object.entries(FILE_ICON_TYPES)){
  const ext=extensions[type]?.[0];const name=ext?'unchanged.long.filename.'+ext:'unchanged.name';
  const node=createFileIcon(name,type==='directory');
  assert.equal(node.tag,'img');assert.equal(node.dataset.fileType,type);
  assert.equal(node.attrs.src,'/icons/'+asset+'.svg');assert.equal(node.attrs.width,'16');assert.equal(node.attrs.height,'16');
  assert.equal(node.attrs.alt,label);assert.ok(label);assert.ok(!node.attrs.tabindex,'Icons must not add a keyboard stop');
  const svg=fs.readFileSync('src/webui/assets/icons/'+asset+'.svg','utf8');assert.ok(svg.includes('viewBox="0 0 16 16"')&&svg.includes('shape-rendering="geometricPrecision"'));
  assert.match(svg, /<svg[^>]*width="16"[^>]*height="16"/,'Intrinsic dimensions stay 16px; CSS supplies the 32px display size');
 }
}finally{globalThis.document=previous;}
console.log(`PASS: ${tested} extension/case cases, directory-first and nested paths, ambiguous/unknown/prototype names, nine accessible 32px displayed / 16px intrinsic original SVG icon categories`);
