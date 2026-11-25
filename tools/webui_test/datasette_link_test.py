#!/usr/bin/env python3
"""Check the actual firmware, including the strong native VICE bridge."""
import argparse
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--nm', default='arm-none-eabi-nm')
p.add_argument('--elf', required=True)
a = p.parse_args()
symbols = {}
for line in subprocess.check_output([a.nm, '-g', a.elf], text=True).splitlines():
    fields = line.split()
    if len(fields) == 3:
        symbols[fields[2]] = fields[1]
for name in ('web_datasette_attach', 'web_datasette_tick',
             'web_datasette_queue', 'web_datasette_status',
             'emux_web_datasette_command', 'emux_web_datasette_read',
             'emux_attach_tape_image', 'tape_image_attach'):
    if symbols.get(name) != 'T':
        raise SystemExit(f'FAIL {a.elf}: {name} must be linked as strong C text, '
                         f'got {symbols.get(name, "missing")}')
print('PASS firmware Datasette link: queue, strong VICE bridge and native tape attachment')
