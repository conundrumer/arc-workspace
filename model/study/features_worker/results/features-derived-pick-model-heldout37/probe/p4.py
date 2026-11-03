"""Probe 4: how close the training sources' picks come to the picks of the read, by pick statistics only (no fit, no row of the 37 enters a fit).

    python3 p4.py
Sources: probe/p2.jsonl (N600), probe/p2-c120.jsonl (C120), and for comparison the S walks of ../features-scope-loss-c-read-heldout37-ramp22/cause/mass.jsonl
(C) and mass-covered.jsonl (covered), one order a form. Per source, at read picks (gold takes a derived option) and builtin picks (gold takes a lib option):
picks, forms, the count of derived options, the count of derived options equal to gold's table, today's steered within-derived share of gold in bits over an
even split, the share of picks where gold has the largest derived weight, and the derived total at builtin picks.
"""
import json
import math
import statistics as st

HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-derived-pick-model-heldout37'
REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'


def picks_p2(path):
    out = []
    for l in open(path):
        r = json.loads(l)
        keys = r['rels']
        for p in r['picks']:
            D = [o for o in p['opts'] if o['cls'] == 'derived']
            g = next((o for o in p['opts'] if o['gold']), None)
            if g is None:
                continue
            gk = keys.get('%s|%s' % tuple(g['base']), {}).get('key') if g['cls'] == 'derived' else None
            npos = sum(1 for o in D if keys.get('%s|%s' % tuple(o['base']), {}).get('key') == gk) if gk else None
            out.append(dict(form=(r['task'], r['g']), gcls=g['cls'], D=[o['w'] for o in D], gw=g['w'], tot=sum(o['w'] for o in p['opts']), npos=npos, place=p['place'], phase=p['phase'], steered=p['steered']))
    return out


def picks_mass(path):
    out = []
    for l in open(path):
        r = json.loads(l)
        if r.get('walk') != 'S':
            continue
        for p in r['picks']:
            D = [o for o in p['opts'] if o['cls'] == 'derived']
            g = next((o for o in p['opts'] if o['gold']), None)
            if g is None:
                continue
            out.append(dict(form=(r['arm'], r['task'], r['g']), gcls=g['cls'], D=[o['share'] for o in D], gw=g['share'], tot=1.0, npos=None, place=p.get('place'), phase=p['phase'], steered=not p.get('rel_off')))
    return out


def summ(name, ps):
    rd = [p for p in ps if p['gcls'] == 'derived']
    bl = [p for p in ps if p['gcls'] == 'lib']
    over = [math.log2(p['gw'] / sum(p['D'])) + math.log2(len(p['D'])) for p in rd if sum(p['D']) > 0]
    first = sum(1 for p in rd if p['gw'] >= max(p['D'])) / max(len(rd), 1)
    dtot = [sum(p['D']) / p['tot'] for p in bl if p['tot'] > 0]
    gb = [-math.log2(p['gw'] / p['tot']) for p in rd]
    print('%-10s forms %4d | read picks %4d: derived opts med %4.1f, equal-table opts med %s, gold over even %.2f bits (med), first %.2f, gold bits med %.2f, unsteered %d '
          '| builtin picks %4d: derived opts med %4.1f, derived total med %.2f' % (
              name, len({p['form'] for p in ps}), len(rd), st.median([len(p['D']) for p in rd]) if rd else float('nan'),
              st.median([p['npos'] for p in rd if p['npos']]) if any(p['npos'] for p in rd) else 'NA', st.median(over) if over else float('nan'), first,
              st.median(gb) if gb else float('nan'), sum(1 for p in rd if not p['steered']), len(bl), st.median([len(p['D']) for p in bl]) if bl else float('nan'), st.median(dtot) if dtot else float('nan')))


summ('N600', picks_p2(HERE + '/probe/p2.jsonl'))
summ('C120', picks_p2(HERE + '/probe/p2-c120.jsonl'))
summ('37 C', picks_mass(REC + '/cause/mass.jsonl'))
summ('37 cov', picks_mass(REC + '/cause/mass-covered.jsonl'))
