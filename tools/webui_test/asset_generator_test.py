#!/usr/bin/env python3
"""No deployed backups; generator filtering tested without changing real assets."""
from pathlib import Path
import importlib.util,tempfile
root=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('asset_generator',root/'tools/gen_webui_assets.py')
gen=importlib.util.module_from_spec(spec);spec.loader.exec_module(gen)
expected=[]
for p in (root/'src/webui/assets').rglob('*'):
 if p.is_file():
  assert not gen.is_backup_component(p.name),p
  expected.append(str(p.relative_to(root/'src/webui/assets')))
assert gen.list_assets()==sorted(expected)
assert 'js/configs.js.orig' not in gen.list_assets()
with tempfile.TemporaryDirectory(prefix='e64-assets-') as tmp:
 base=Path(tmp)/'assets';base.mkdir()
 files=['index.html','js/api.js','images/logo.png','data.json','style.css',
        'js/configs.js.orig','js/api.js.bak','js/foo.orig.js','js/foo.bak.png',
        'js/foo.js.before-review','js/foo.before-review.js','js/file.js~',
        'js/.private.js','js/#file.js#','js/file.js.tmp','js/file.part.js',
        'backups/api.js','js/.git/secret.js','js/not-for-serving.txt']
 for f in files:
  p=base/f;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
 outside=Path(tmp)/'outside.js';outside.write_text('private source backup')
 (base/'js/link.js').symlink_to(outside)
 (base/'linked-dir').symlink_to(outside.parent,target_is_directory=True)
 gen.ASSET_DIR=str(base)
 assert gen.list_assets()==['data.json','images/logo.png','index.html','js/api.js','style.css']
print('PASS: asset inventory, backup/temp/hidden/unsupported file exclusion, backup directories and symlink exclusion.')
