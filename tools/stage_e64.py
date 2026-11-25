#!/usr/bin/env python3
"""Stage the E64 V1 C64 review layout inside build; never access devices."""
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / 'build/e64-review'

def stage(destination=None):
    global STAGE
    if destination is not None:
        STAGE = Path(destination).resolve()
    if not STAGE.is_relative_to((ROOT / "build").resolve()):
        raise SystemExit("Staging is restricted to this source tree build directory")
    if STAGE.exists():
        raise SystemExit('Review directory already exists; choose a fresh build tree or review it first.')
    STAGE.mkdir(parents=True)
    for name in ['c64', 'drives', 'carts', 'configs', 'firmware', 'system']:
        (STAGE / name).mkdir()
    for name in ['config.txt', 'cmdline.txt']:
        shutil.copy2(ROOT / 'sdcard' / name, STAGE / name)
    for name in ['bootcode.bin', 'start.elf', 'fixup.dat']:
        shutil.copy2(ROOT / 'release/common_release_files' / name, STAGE / name)
    shutil.copytree(ROOT / 'sdcard/c64', STAGE / 'c64', dirs_exist_ok=True)
    for item in (ROOT / 'release/c64_release_files/C64').iterdir():
        dest = 'drives' if item.name.startswith('dos') else 'c64'
        shutil.copy2(item, STAGE / dest / item.name)
    shutil.copytree(ROOT / 'release/c64_release_files/carts', STAGE / 'carts', dirs_exist_ok=True)
    shutil.copy2(ROOT / 'sdcard/machines.txt', STAGE / 'system/machines.txt')
    shutil.copy2(ROOT / 'sdcard/wpa_supplicant.conf.example', STAGE / 'system/wpa_supplicant.conf.example')
    for name in ['network.cfg', 'demo.txt', 'LICENSE', 'network-readme.txt', 'wifi-settings.conf.example']:
        shutil.copy2(ROOT / name, STAGE / 'system' / name)
    for path in (ROOT / 'sdcard').rglob('README*.txt'):
        shutil.copy2(path, STAGE / path.relative_to(ROOT / 'sdcard'))
    # Include verified, separately licensed WLAN firmware.
    wlan = ROOT / 'third_party/circle-stdlib/libs/circle/addon/wlan/firmware'
    for pattern in ('*.bin', '*.txt', '*.clm_blob'):
        for item in sorted(wlan.glob(pattern)):
            shutil.copy2(item, STAGE / 'firmware' / item.name)

    for name in ['WLAN-COPYRIGHT.txt', 'WLAN-SHA256SUMS']:
        shutil.copy2(ROOT / 'licenses' / name, STAGE / 'firmware' / name)

    shutil.copy2(
        ROOT / 'licenses/Raspberry-Pi-LICENCE.broadcom',
        STAGE / 'Raspberry-Pi-LICENCE.broadcom'
    )
    shutil.copy2(
        ROOT / 'licenses/RASPBERRY-PI-BOOT-SHA256SUMS',
        STAGE / 'RASPBERRY-PI-BOOT-SHA256SUMS'
    )

    image = ROOT / 'kernel8-32.img'
    if image.exists():
        shutil.copy2(image, STAGE / image.name)
    print(STAGE)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination')
    stage(parser.parse_args().destination)
