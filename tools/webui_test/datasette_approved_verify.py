#!/usr/bin/env python3
"""Verify approved Datasette styling against the unmodified functional baseline."""
from pathlib import Path
import json, re
from PIL import Image, ImageChops
R=Path(__file__).resolve().parents[2]
O=R/'build/datasette-approved'
before=json.loads((O/'before/results.json').read_text())
after=json.loads((O/'after/results.json').read_text())
assert len(before)==len(after)==33
records=[]
def close(a,b): return abs(a-b)<.025
def same(a,b): return all(close(a[k],b[k]) for k in ('x','y','w','h'))
def separate(a,b): return a['x']+a['w']<=b['x']+.1 or b['x']+b['w']<=a['x']+.1 or a['y']+a['h']<=b['y']+.1 or b['y']+b['h']<=a['y']+.1
for b,a in zip(before,after):
    assert (b['viewport'],b['phase'])==(a['viewport'],a['phase'])
    assert a['panel']==b['panel'] and a['frame']==b['frame'] and a['drawing']==b['drawing'] and a['buttons']==b['buttons']
    assert a['gap']==b['gap'] and a['statusMeasurements']==b['statusMeasurements']
    dy=24 if a['viewport'][0]==1280 else 0
    for i,(x,y) in enumerate(zip(b['controlRects'],a['controlRects'])):
        assert all(close(x[k],y[k]) for k in ('x','w','h'))
        assert close(y['y']-x['y'],dy if i in (1,2) else 0)
    # Every original visible DOM/SVG node remains at the same bounds, except the readout.
    def visible(r):
        v=r['allGeometry'];return v[next(i for i,e in enumerate(v) if e['id']=='tape-assembly'):]
    av=[e for e in visible(a) if not (e['tag']=='SPAN' and e['box']==a['logoMeasurements']['box'])]
    bv=visible(b)
    assert len(av)==len(bv)
    moved_indices=set()
    for i,e in enumerate(bv):
        if e['id']=='tape-counter': moved_indices.update(range(i-1,i+5)) # wrapper, counter, digits, RESET
    for i,(x,y) in enumerate(zip(bv,av)):
        assert (x['tag'],x['id'])==(y['tag'],y['id'])
        expected=dict(x['box']);expected['y']+=dy if i in moved_indices else 0
        assert same(expected,y['box']),(i,x,y)
    assert not [k for k,v in b['checks'].items() if v and not a['checks'][k] and k!='resetPositionPreserved']
    assert not a['overlaps'] and a['textOverflow']==b['textOverflow']
    logo=a['logoMeasurements'];c=a['controlRects'][1];reset=a['controlRects'][2];motor=a['controlRects'][3]
    assert logo['mask'] and logo['background']=='rgb(0, 0, 0)'
    assert close(logo['box']['x']+logo['box']['w']/2,c['x']+c['w']/2)
    assert abs(logo['box']['w']/logo['box']['h']-1406/498)<.003
    assert all(separate(logo['box'],x) for x in a['controlRects'])
    assert close(reset['y']-c['y']-c['h'],4)
    assert reset['y']+reset['h']<=motor['y']+.1
    # Only transport keys receive shading, including their active/pressed states.
    assert len(a['shading'])==7 and all(s['tag'] in ('BUTTON','A') and s['p'] is None for s in a['shading'])
    app=a['appearance']
    assert app['motorTag']=='DIV' and app['motor']['background']=='rgb(195, 174, 141)'
    assert app['motor']['image']=='none' and app['motor']['shadow']=='none'
    assert app['load']['border']=='rgb(10, 10, 10)' and app['load']['outline']=='none'
    assert app['help']['border']=='rgb(0, 213, 255)' and app['help']['outlineColor']=='rgb(22, 59, 255)'
    assert app['help']['outlineWidth']=='1px' and app['help']['image']=='none' and app['help']['shadow']=='none'
    # Headless Firefox programmatic focus does not activate its keyboard modality.
    # Focusability is checked by the fixture; verify the production focus-visible rule below.
    records.append(dict(viewport=a['viewport'],phase=a['phase'],counterShift=dy,logo=logo['box'],counter=c,reset=reset,motor=motor,resetMotorGap=motor['y']-reset['y']-reset['h'],pass_=True))
    if a['viewport'][0]==1280 and a['phase']=='loaded':
        w,h=a['viewport']
        bi=Image.open(O/'before'/f'datasette-{w}x{h}-loaded.png').convert('RGB')
        ai=Image.open(O/'after'/f'datasette-{w}x{h}-loaded.png').convert('RGB')
        # Exact pixel comparison of the entire approved silver frame and contents.
        f=a['frame'];box=(int(f['x'])-2,int(f['y'])-2,int(f['x']+f['w'])+2,int(f['y']+f['h'])+2)
        assert ImageChops.difference(bi.crop(box),ai.crop(box)).getbbox() is None
        # Sidebar source and rendered logo also remain unchanged (exclude telemetry).
        assert ImageChops.difference(bi.crop((0,13,235,h)),ai.crop((0,13,235,h))).getbbox() is None
        p=a['panel'];crop=(int(p['x'])-3,int(p['y'])-3,int(p['x']+p['w'])+3,int(p['y']+p['h'])+5)
        ai.crop(crop).save(O/f'after-{w}x{h}-datasette.png')
        # Mask must actually render black lettering, with beige holes and margins.
        l=logo['box'];pixels=list(ai.crop((int(l['x']),int(l['y']),int(l['x']+l['w']),int(l['y']+l['h']))).getdata())
        assert sum(max(px)<20 for px in pixels)>len(pixels)*.35
        assert sum(px==(232,219,196) for px in pixels)>len(pixels)*.1
# Production source artwork, transport/controller code, and SVG remain untouched.
A=R/'src/webui/assets';backup=O/'backups/src/webui/assets'
old=(backup/'index.html').read_text();new=(A/'index.html').read_text()
css=(A/'style.css').read_text()
focus=re.search(r'\.tape-transports \.btn:focus-visible, \.tape-help:focus-visible \{([^}]+)',css)[1]
assert 'outline:2px solid var(--blue)' in focus and 'outline-offset:3px' in focus
assert re.search(r'<svg viewBox="0 0 560 310".*?</svg>',old,re.S)[0]==re.search(r'<svg viewBox="0 0 560 310".*?</svg>',new,re.S)[0]
(O/'comparison.json').write_text(json.dumps(records,indent=2))
print('PASS: 33 Firefox cases; exact approved frame/sidebar pixels at both desktop sizes; all original geometry preserved except authorized counter/RESET shifts; original logo rendered; no new overlaps/clipping; only seven keys shaded; HELP/LOAD keyboard focus retained.')
print(json.dumps(records[0],indent=2))
