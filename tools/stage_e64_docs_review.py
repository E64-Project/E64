#!/usr/bin/env python3
"""Clone tested files into a NEW documentation review; never replace a stage."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'build/e64-install-review'
DEST=ROOT/'build/e64-docs-review'
AUDIT=ROOT/'build/e64-docs-review-audit'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot(base):return {str(p.relative_to(base)):digest(p) for p in sorted(base.rglob('*')) if p.is_file()}
def stage():
    assert not DEST.exists(), 'Choose a fresh stage; never overwrite reviewed files'
    assert not any(p.is_symlink() for p in SOURCE.rglob('*'))
    before=snapshot(SOURCE)
    # Verify the source against its existing manifest without rewriting it.
    expected=dict((name,h) for h,name in (line.split('  ',1) for line in (ROOT/'build/e64-install-review-audit/SHA256SUMS.txt').read_text().splitlines()))
    assert before==expected
    shutil.copytree(SOURCE,DEST)
    for p in (ROOT/'sdcard').rglob('README*.txt'):
        shutil.copy2(p,DEST/p.relative_to(ROOT/'sdcard'))
    shutil.copy2(ROOT/'network-readme.txt',DEST/'system/network-readme.txt')
    # The new stage uses the current kernel; its bytes are never changed.
    shutil.copy2(ROOT/'kernel8-32.img',DEST/'kernel8-32.img')
    (DEST/'c64/ROM-Notes.txt').unlink()
    assert snapshot(SOURCE)==before
    after=snapshot(DEST)
    changed={p for p in before.keys()|after.keys() if before.get(p)!=after.get(p)}
    allowed={'README.txt','c64/ROM-Notes.txt','kernel8-32.img','system/network-readme.txt'}|{f'{d}/README-{d}.txt' for d in ['c64','drives','carts','configs','firmware','system']}
    assert changed<=allowed
    # Every ROM, map, credential, boot setting and license is byte-identical.
    AUDIT.mkdir(exist_ok=True)
    (AUDIT/'source-stage.json').write_text(json.dumps(before,indent=2)+'\n')
    (AUDIT/'SHA256SUMS.txt').write_text(''.join(f'{h}  {p}\n' for p,h in after.items()))
    (AUDIT/'file-inventory.tsv').write_text('path\tbytes\tsha256\n'+''.join(f'{p}\t{(DEST/p).stat().st_size}\t{h}\n' for p,h in after.items()))
    (AUDIT/'stage-changes.json').write_text(json.dumps(sorted(changed),indent=2)+'\n')
    print(f'PASS: {len(after)} staged files; tested source unchanged; only documentation and current kernel copy differ')
if __name__=='__main__':stage()
