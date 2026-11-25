#!/usr/bin/env python3
"""Prevent retired Config architecture from returning to active firmware/UI."""
from pathlib import Path
import re
root = Path(__file__).resolve().parents[2]
paths = [p for d in ['src', 'third_party/common', 'third_party/vice-3.3/src/arch/raspi']
         for p in (root/d).rglob('*')
         if p.is_file() and p.suffix in {'.c', '.h', '.cpp', '.js', '.css'}]
retired = re.compile(r'\b(?:CONFIGS_MAIN_\w+|configs_(?:running_is_main|reset_to_main|main_\w+|remember_main_machine)|sd_main_settings_\w+|main_machine|switch_safe|emu_safe_mode_interrupt|boot_safe_recovery)\b|Default Configuration|"Default Config"|main_protected|pf-main')
for path in paths:
    match = retired.search(path.read_text())
    assert not match, (str(path.relative_to(root)), match.group() if match else '')
for filename in ['src/keyboard/keyboard_router.c', 'third_party/common/kbd.c']:
    assert 'video_reset' not in (root/filename).read_text(), filename
sampler = (root/'src/keyboard/gpio_recovery.c').read_text()
assert 'f7' not in sampler.lower() and '5000000' not in sampler
ui = (root/'src/webui/assets/js/configs.js').read_text()
assert 'mainActions' not in ui and '/configs/main/' not in ui
assert 'p.id === state.running ? "*" : ""' in ui
menu = (root/'third_party/common/menu_configs.c').read_text()
# Factory and custom entries share the machine-metadata label path.
label=menu[menu.index('static void config_label('):menu.index('// Pushes a menu')]
assert 'configs_is_factory' not in label
assert "strchr(info->machine, '/')" in label and 'const char *name = info->name;' in label
assert 'Restore Deleted Config >' not in menu and '"Manage Configs"' not in menu
# Root files stay protected rather than being reused or recovered.
policy = (root/'src/configs/config_protection.c').read_text()
for path in ['/configs/main', '/e64set.new', '/e64set.old', '/vice.ini', '/settings.txt']:
    assert path in policy, path
print('PASS: active-code Stage 2 audit; retired identities/save/reset/UI aliases absent; preserved-file protections and running marker retained')
