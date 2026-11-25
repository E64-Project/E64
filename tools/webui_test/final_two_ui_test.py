"""Preserve checkpoint content apart from the two authorized corrections."""
from pathlib import Path
import tarfile
R=Path(__file__).resolve().parents[2]
with tarfile.open(R/'E64-Source-Backups/final-two-ui-before-20261111-133430.tar.gz') as checkpoint:
    for member in checkpoint.getmembers():
        if not member.isfile() or not member.name.startswith('src/webui/') or member.name=='src/webui/webui_assets.c':
            continue
        before=checkpoint.extractfile(member).read()
        expected=before
        if member.name.endswith('assets/index.html'):
            expected=before.replace(b'Derived from BMC64, VICE, &amp; Circle', b'Based on BMC64, powered by VICE and Circle')
        elif member.name.endswith('assets/js/files.js'):
            expected=before.replace(b'width:230px;min-width:230px;flex:0 0 230px;',b'width:230px;min-width:230px;max-width:230px;flex:0 0 230px;')
        assert (R/member.name).read_bytes()==expected, member.name
assert b'max-width:230px;flex:0 0 230px;box-sizing:border-box' in (R/'src/webui/assets/js/files.js').read_bytes()
print('PASS: exact two source corrections; all other Web UI source, styles, About markup/layout, actions and license text byte-identical to checkpoint')
