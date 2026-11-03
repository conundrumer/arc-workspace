import json, os, sys, time
os.environ['ARCLOG_THREADS'] = '1'
sys.path.insert(0, os.environ['SAMPLER_CODE'])
import arclog, live, live_try, or_q, superdag as D, search_gold as G
s = live.Sampler(G.MODELS, tuple(live.STEERS))
p = s.pri
print(len(p['comps']))
for c, w in sorted(p['comps'].items(), key=lambda x: -x[1]):
    cp = p['comp_ports'].get(c)
    print(c, round(w, 1), 'keyed', round(p['keyed'].get(c, 0), 1), cp)
print({k: v for k, v in list(p['ports'].items())[:60]})
print(p.get('families'))
print(dir(arclog))
print([x for x in dir(D) if 'table' in x.lower()])
