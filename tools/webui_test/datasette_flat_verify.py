#!/usr/bin/env python3
"""Compare real Firefox geometry and styles against the saved pre-change baseline."""
from pathlib import Path
import json
from PIL import Image
R=Path(__file__).resolve().parents[2]
out=R/'build/datasette-flat'
before=json.loads((out/'before/results.json').read_text())
after=json.loads((out/'after/results.json').read_text())
records=[]
assert len(before)==len(after)==33
for b,a in zip(before,after):
    assert (b['viewport'],b['phase'])==(a['viewport'],a['phase'])
    assert not a['shading'],a['shading']
    assert abs(a['gap']-.8*b['gap'])<.02
    shifts=[y['x']-x['x'] for x,y in zip(b['controlRects'][:4],a['controlRects'][:4])]
    assert max(shifts)-min(shifts)<.001
    for x,y in zip(b['controlRects'][:4],a['controlRects'][:4]):
        assert all(x[k]==y[k] for k in ('y','w','h'))
    assert a['panel']==b['panel'] and a['frame']==b['frame'] and a['drawing']==b['drawing'] and a['buttons']==b['buttons']
    # Definitions lost unused gradients; all visible drawing/HTML nodes remain in order.
    def visible(r):
        v=r['allGeometry'];return v[next(i for i,e in enumerate(v) if e['id']=='tape-assembly'):]
    bv,av=visible(b),visible(a)
    assert len(bv)==len(av)
    changed=0
    for x,y in zip(bv,av):
        assert (x['tag'],x['id'])==(y['tag'],y['id'])
        dx=y['box']['x']-x['box']['x']
        assert all(abs(x['box'][k]-y['box'][k])<.001 for k in ('y','w','h')),(x,y)
        assert abs(dx)<.001 or abs(dx-shifts[0])<.001,(x,y)
        changed+=abs(dx)>.001
    assert changed==9 # four controls, their wrapper, three digits and LED
    # Existing layout predicates must not regress (desktop-only assumptions are retained in raw results).
    assert not [k for k,v in b['checks'].items() if v and not a['checks'][k]]
    records.append(dict(viewport=a['viewport'],phase=a['phase'],original_gap=b['gap'],final_gap=a['gap'],reduction_percent=100*(1-a['gap']/b['gap']),control_shifts=shifts,pass_=True))
    # Export unobstructed desktop housing crops; telemetry sits above the panel.
    if a['phase']=='loaded' and a['viewport'][0]==1280:
        for stage,r in [('before',b),('after',a)]:
            w,h=r['viewport'];im=Image.open(out/stage/f'datasette-{w}x{h}-loaded.png')
            p=r['panel'];im.crop((int(p['x'])-3,int(p['y'])-3,int(p['x']+p['w'])+3,int(p['y']+p['h'])+5)).save(out/f'{stage}-{w}x{h}-datasette.png')
(out/'comparison.json').write_text(json.dumps(records,indent=2))
print(f'PASS: {len(records)} Firefox cases; uniform horizontal movement, 20% gap reduction, no other geometry changes, no gradients/shadows/filters, no regressed baseline checks')
print(json.dumps(records[0],indent=2))
