#!/usr/bin/env python3
"""Check ARM parsing without generating objects or firmware."""
from pathlib import Path
import runpy, subprocess
r=Path(__file__).resolve().parents[2]
ns=runpy.run_path(str(r/'tools/webui_test/round3_syntax_check.py'))
# Common library is shared and is built without a per-machine define.
flags=[f for f in ns['flags'] if f!='-DRASPI_C64']
subprocess.run([str(ns['bin']/'arm-none-eabi-gcc'),*flags,'-std=gnu99','third_party/common/menu_configs.c'],cwd=r,check=True)
print('PASS ARM -fsyntax-only: shared menu_configs.c (without RASPI_C64)')
