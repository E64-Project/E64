#!/usr/bin/env python3
"""Run all existing host regression entry points; retain individual results."""
from pathlib import Path
import os,subprocess,json,re,datetime
R=Path(__file__).resolve().parents[2];os.chdir(R)
env=os.environ.copy()
out=R/'build/improvements-round1'/('verification-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));out.mkdir(parents=True)
commands=[['python3',str(p)] for p in sorted(Path('tools').glob('*test/run_tests.py'))]
commands += [['bash',str(p)] for p in sorted(Path('tools').glob('*test/run_tests.sh'))]
commands += [['node','tools/webui_test/run_tests.mjs']]
runner=Path('tools/webui_test/run_tests.mjs').read_text()
commands += [['node',str(p)] for p in sorted(Path('tools/webui_test').glob('*test.mjs')) if './'+p.name not in runner]
commands += [['python3',str(p)] for p in sorted(Path('tools/webui_test').glob('*test.py'))]
commands += [['node','tools/raw_cartridge_test/web_test.mjs'],['python3','tools/raw_cartridge_test/dialog_browser_check.py','--self-test'],['python3','docs/test_main_recovery_model.py'],['python3','tools/documentation_test/run_tests.py','--source-only']]
results=[]
for n,cmd in enumerate(commands):
 q=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 log=out/(str(n).zfill(2)+'-'+Path(cmd[1]).parent.name+'-'+Path(cmd[1]).stem+'.log');log.write_text(q.stdout)
 results.append({'command':cmd,'exit':q.returncode,'log':str(log.relative_to(R))});print(('PASS' if not q.returncode else 'FAIL')+' '+' '.join(cmd),flush=True)
 (out/'results.json').write_text(json.dumps(results,indent=2))
print('RESULTS',out,flush=True)
raise SystemExit(any(r['exit'] for r in results))
