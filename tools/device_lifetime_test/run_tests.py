#!/usr/bin/env python3
"""Production dormant registry; deterministic schedules, limit injection, native races."""
from pathlib import Path
import tempfile,subprocess
root=Path(__file__).resolve().parents[2];circle=root/'third_party/circle-stdlib/libs/circle'
with tempfile.TemporaryDirectory(prefix='e64-lifetime-') as name:
 t=Path(name);(t/'circle').mkdir()
 (t/'assert.h').write_text('#include \"/usr/include/assert.h\"\n')
 (t/'circle/types.h').write_text('#pragma once\n#include <cstdint>\nusing u32=uint32_t;using u64=uint64_t;using boolean=bool;\n#define TRUE true\n#define FALSE false\n')
 exe=t/'test'
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-pthread','-I'+str(t),'-I'+str(circle/'include'),'-DLIFETIME_SOURCE="'+str(circle/'lib/devicelifetime.cpp')+'"',str(Path(__file__).with_name('test.cpp')),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=60)
print('PASS: actual production lifetime methods; host integer shim only; no real devices accessed')
