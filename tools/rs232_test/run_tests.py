#!/usr/bin/env python3
"""Host regressions for the serial bridge, USB driver and RS-232 menu."""
from pathlib import Path
import subprocess,tempfile,os
root=Path(__file__).resolve().parents[2]
circle=root/'third_party/circle-stdlib/libs/circle'
def run(cmd,**kw): subprocess.run([str(x) for x in cmd],check=True,timeout=60,**kw)
with tempfile.TemporaryDirectory(prefix='e64-rs232-') as tmp:
 t=Path(tmp);(t/'circle/usb').mkdir(parents=True)
 (t/'circle/spinlock.h').write_text('#pragma once\n#include <mutex>\nclass CSpinLock {std::mutex lock;public:void Acquire(){lock.lock();}void Release(){lock.unlock();}};\n')
 exe=t/'bridge'
 run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=undefined','-pthread','-I'+str(t),'-I'+str(root/'src'),root/'src/rs232_usb_bridge.cpp',Path(__file__).with_name('bridge_test.cpp'),'-o',exe]);run([exe])
 # Native test double headers for platform boundaries, actual driver/request code.
 exec(Path(__file__).with_name('usb_fixture.py').read_text())
run(['python3',Path(__file__).with_name('controller_contract_test.py')])
run(['python3',Path(__file__).with_name('menu_test.py')])
