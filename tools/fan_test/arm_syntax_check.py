#!/usr/bin/env python3
"""Parse E64 fan integration for ARM; never compile/link firmware."""
import runpy, subprocess
from pathlib import Path
R=Path(__file__).resolve().parents[2]
v=runpy.run_path(str(R/'tools/webui_test/round3_syntax_check.py'))
vc4='third_party/circle-stdlib/libs/circle/addon/vc4'
v['flags'] += ['-I'+vc4+'/'+p for p in ['interface/bcm_host','interface/khronos/include','interface/khronos/common','interface/vcos/pthreads','host_applications/linux/libs/bcm_host/include','interface/vcos','interface/vmcs_host','interface/vchi','interface/vchiq_arm']]
v['flags'] += ['-I'+vc4,'-D__VCCOREVER__=0x04000000','-DUSE_VCHIQ_SOUND']
for compiler,extra,paths in [
 ('g++',['-std=c++17','-fno-exceptions','-fno-rtti','-DBMC64_NETWORK'],['src/fan_gpio.cpp','src/viceapp.cpp','src/kernel.cpp','src/main.cpp','src/power/power.cpp','src/webui/webui.cpp']),
 ('gcc',['-std=gnu99','-DBMC64_NETWORK','-URASPI_C64'],['src/fan_control.c','third_party/common/menu.c','third_party/common/menu_configs.c','third_party/common/menu_switch.c']),
]:
 subprocess.run([str(v['bin']/('arm-none-eabi-'+compiler)),*v['flags'],*extra,*paths],cwd=R,check=True)
 print('PASS ARM fan integration: '+', '.join(paths))
