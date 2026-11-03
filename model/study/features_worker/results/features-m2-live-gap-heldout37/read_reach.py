"""Part (b), best-first form: the search's visits enumerate clauses best first (superdag_search.py docstring), so at most 2^S clauses come before gold's clause in an
opening's order. An opening reaches gold's clause by this bound where its slot tries are at least 2^S, that is, the shortfall S - log2(tries) is 0 or below.
Over the walked held-with-kind openings (mapped, both walks valid; a PPS-drawn opening counts once): shortfall by arm, openings and forms within the bound.

    python -I read_reach.py
"""
import collections, glob, json, math, os, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = ['m2c_s0', 'm2s_s0', 'm2c_s1', 'm2s_s1']
W = {}
for p in glob.glob(HERE + '/walks*.jsonl'):
    for l in open(p):
        y = json.loads(l)
        W[(y['job'], y['task'], y['g'], y['i'])] = y
res = {}
for j in JOBS:
    rows = [y for k, y in W.items() if k[0] == j and y['status'] == 'mapped' and y['S']['off'].get('valid') and y['S']['M2'].get('valid')]
    unm = sum(1 for k, y in W.items() if k[0] == j and y['status'] != 'mapped')
    sf = {a: [y['S'][a]['total'] - math.log2(y['tries']) for y in rows] for a in ('off', 'M2')}
    reach = {a: [y for y, s in zip(rows, sf[a]) if s <= 0] for a in ('off', 'M2')}
    new = [y for y, so, sm in zip(rows, sf['off'], sf['M2']) if sm <= 0 < so]
    near = {a: sum(1 for s in sf[a] if s <= 3) for a in ('off', 'M2')}
    r = dict(openings=len(rows), unmapped=unm, med_S_off=statistics.median(y['S']['off']['total'] for y in rows), med_S_M2=statistics.median(y['S']['M2']['total'] for y in rows),
             med_log2_tries=statistics.median(math.log2(y['tries']) for y in rows), med_short_off=statistics.median(sf['off']), med_short_M2=statistics.median(sf['M2']),
             reach_off=len(reach['off']), reach_M2=len(reach['M2']), within3_off=near['off'], within3_M2=near['M2'], m2_new=len(new),
             forms_reach_off=sorted({'%s:%d' % (y['task'], y['g']) for y in reach['off']}), forms_reach_M2=sorted({'%s:%d' % (y['task'], y['g']) for y in reach['M2']}))
    res[j] = r
    print('%s openings %d (unmapped %d): median S off %.1f M2 %.1f, log2 tries %.1f, shortfall off %.1f M2 %.1f; within bound off %d M2 %d (M2 only %d), within 3 bits off %d M2 %d; forms within bound off %s M2 %s' % (
        j, r['openings'], unm, r['med_S_off'], r['med_S_M2'], r['med_log2_tries'], r['med_short_off'], r['med_short_M2'], r['reach_off'], r['reach_M2'], r['m2_new'], near['off'], near['M2'],
        r['forms_reach_off'], r['forms_reach_M2']))
json.dump(res, open(HERE + '/reach_summary.json', 'w'), indent=1)
