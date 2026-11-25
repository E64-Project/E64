#!/usr/bin/env python3
"""Run the E64 Config/native/Web regression batch without SD access."""
from pathlib import Path
import subprocess,os,json
r=Path(__file__).resolve().parents[2];os.chdir(r);env=os.environ.copy()
(r/'build').mkdir(exist_ok=True)
commands=[['node','tools/webui_test/run_tests.mjs'],['node','tools/webui_test/logical_configs_test.mjs'],['node','tools/webui_test/config_protection_test.mjs'],['node','tools/webui_test/factory_configs_test.mjs'],['python3','tools/webui_test/fs_endpoints_test.py'],['python3','tools/webui_test/asset_generator_test.py'],['python3','tools/webui_test/config_protection_test.py'],['python3','tools/webui_test/permanent_delete_endpoint_test.py']]
commands += [['python3','tools/'+name+'/run_tests.py'] for name in ['menu_final_polish_test','menu_navigation_test','menu_reorganization_test','config_dialog_test','home_navigation_test','native_cleanup_test','menu_theme_test','menu_cleanup_test','e64_ui_test','menu_title_test','menu_footer_test','network_test','rom_test']]
commands += [['bash','tools/configs_test/run_tests.sh'],['bash','tools/keyboard_test/run_tests.sh']]
results=[]
with (r/'build/config-management-regression.log').open('w') as log:
 for cmd in commands:
  run=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  results.append({'command':cmd,'exit_code':run.returncode});log.write('$ '+' '.join(cmd)+'\n'+run.stdout+'\n');log.flush();print(('PASS' if run.returncode==0 else 'FAIL')+' '+' '.join(cmd),flush=True)
(r/'build/config-management-regression-results.json').write_text(json.dumps(results,indent=2)+'\n')
if any(x['exit_code'] for x in results):raise SystemExit(1)
