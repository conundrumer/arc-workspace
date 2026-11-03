"""The per-pick table of the unread-forms read (item 14), from the pick rows of a cut part.

  import features_dagc_unread_rows as UR
  R = UR.build('held-cut', 'live', seconds=20)     R.picks: one dict per pick key of a point; R.forms: one dict per point

A pick: point, task, line_id, kind, seed, w (walks that reach it over the point's finished walks), band, place, bits (the pick's q_bits), cls (gold's class), derived (gold is a derived option), gold_ck (the content key of gold's form),
n[set] (forms in the set), o[set] (derived options at the pick whose form is in the set), inside[set] (gold's form is in the set). Sets are those of features_unread_lib.py, from the point's scope and the pick's downset.
A form (point): mean walk total over its finished walks, `bits_mean`, and its kind. The picks of a walk whose gold is not among the options (gold_idx None) have no bits and are left out; they are counted in R.no_gold.
"""
import collections
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_dag_order as D  # noqa: E402
import features_dagc_lib as L  # noqa: E402
import features_dagc_rows as RW  # noqa: E402
import features_unread_lib as UL  # noqa: E402

ME = RW.ME
KINDS = ('RULE', 'DET', 'INIT')
_GOLD = {}


def program(part, task):
    if part.startswith(('held', 'dev')):
        if 'base' not in _GOLD:
            _GOLD['base'] = L.base_gold()
        return _GOLD['base'][task]
    if task not in _GOLD:
        _GOLD[task] = L.fit_gold([task])[task]
    return _GOLD[task]


class Result:
    pass


def build(part, steers, seconds=20, tasks=None):
    T = RW.load(part, steers, kinds=KINDS, seconds=seconds, tasks=tasks)
    pts = {}
    for x in open(ME + 'points-%s.jsonl' % part):
        p = json.loads(x)
        pts[p['line']] = p
    R = Result()
    R.files, R.conf, R.no_gold = T.files, T.conf, 0
    psets, fulls = {}, {}
    picks = []
    for (pt, k), e in T.entries.items():
        g = e['gold_idx']
        if g is None:
            R.no_gold += 1
            continue
        p = pts[pt]
        if pt not in psets:
            lines = program(part, p['task'])
            if p['task'] not in fulls:
                fulls.clear()
                fulls[p['task']] = D.ProgramDag(lines)
            psets[pt] = UL.PointSets(p['scope'], fulls[p['task']], p['key'])
        ps = psets[pt]
        sets = ps.at(e['downset'])
        ders = [x[0][2:].partition('.')[0] for x in e['opts'] if x[1] == 'relation']
        gk = e['opts'][g][0][2:].partition('.')[0] if e['opts'][g][1] == 'relation' else None
        picks.append(dict(point=pt, task=e['task'], line_id=e['line_id'], kind=e['kind'], seed=p['target_seed'], w=RW.weight(T, e), band=e['band'], place=e['place'], bits=e['q_bits'], cls=RW.cls_of(e), gold_alive=RW.gold_alive(e), derived=gk is not None, gold_ck=gk,
                          n={s: len(sets[s]) for s in UL.SETS}, o={s: sum(c in sets[s] for c in ders) for s in UL.SETS}, inside={s: gk is not None and gk in sets[s] for s in UL.SETS}, nscope=len(ps.scope_forms), key=e['key'], scope_id=e['scope_id']))
    R.picks = picks
    tot = collections.defaultdict(list)
    meta = {}
    for w in T.walks:
        if w['ok'] and w['total'] is not None:
            tot[w['point']].append(w['total'])
            meta[w['point']] = w
    R.forms = {pt: dict(point=pt, task=meta[pt]['task'], line_id=meta[pt]['line_id'], kind=meta[pt]['kind'], scope_id=meta[pt]['scope_id'], seed=pts[pt]['target_seed'], bits_mean=sum(v) / len(v), n_walks=len(v)) for pt, v in tot.items()}
    return R
