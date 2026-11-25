#!/usr/bin/env python3
"""ARM parsing only: no objects, firmware rebuild, link, or device access."""
from pathlib import Path
import runpy,subprocess
R=Path(__file__).resolve().parents[2]
v=runpy.run_path(str(R/'tools/webui_test/round3_syntax_check.py'))
paths=['third_party/vice-3.3/src/arch/raspi/vice_overlay.c','src/webui/webui_assets.c']
subprocess.run([str(v['bin']/'arm-none-eabi-gcc'),*v['flags'],'-std=gnu99','-DHAVE_CONFIG_H',*paths],cwd=R,check=True)
print('PASS ARM syntax: VICE motor callback and generated embedded assets')
