"""Reads cause/mass.jsonl (C) and cause/mass-covered.jsonl (covered): per form, the atom-start picks of the S and R walks summed by the class of gold's
option (derived = a read relation, lib = a builtin, op = NOT or a comparison), and the S - R bits of each class split in two:
  dilution  = -log2(1 - share of the non-ancestor derived options) at each S pick (the bits that removing those options alone gives back);
  reweight  = the rest: S bits - dilution - R bits (the options that both walks share took other weights).
Also the gold option's steer factor f and P share, S against R, and the relation-steer features of gold's option that differ. Prints tables; writes cause/split.tsv."""
import collections
import json
import math
import statistics
import sys

REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
L2 = math.log(2)


def load(path):
    by = collections.defaultdict(dict)
    for l in open(path):
        r = json.loads(l)
        if r.get('walk'):
            by[(r['arm'], r['task'], r['g'])][r['walk']] = r
    return {k: v for k, v in by.items() if 'S' in v and 'R' in v and not v['S']['bad'] and not v['R']['bad'] and not v['S']['dead'] and not v['R']['dead'] and not v['S']['left'] and not v['R']['left']}


def pick_stats(p):
    g = next(o for o in p['opts'] if o['gold'])
    sh = {o['tok']: o['share'] for o in p['opts']}
    non = sum(o['share'] for o in p['opts'] if o['cls'] == 'derived' and o['anc'] is False and not o['gold'])
    unk = sum(o['share'] for o in p['opts'] if o['cls'] == 'derived' and o['anc'] is None and not o['gold'])
    anc_other = sum(o['share'] for o in p['opts'] if o['cls'] == 'derived' and o['anc'] is True and not o['gold'])
    lib = sum(o['share'] for o in p['opts'] if o['cls'] == 'lib' and not o['gold'])
    op = sum(o['share'] for o in p['opts'] if o['cls'] == 'op' and not o['gold'])
    nder = sum(o['cls'] == 'derived' for o in p['opts'])
    nnon = sum(o['cls'] == 'derived' and o['anc'] is False for o in p['opts'])
    nanc = sum(o['cls'] == 'derived' and o['anc'] is True for o in p['opts'])
    # gold's rank among derived options by final weight
    return dict(cls=p['gold_cls'], phase=p['phase'], bits=-math.log2(g['share']) if g['share'] > 0 else math.inf, gshare=g['share'], non=non, unk=unk, anc_other=anc_other, lib=lib, op=op,
                nder=nder, nnon=nnon, nanc=nanc, f=g['f'], p=g['p'], group=p['group'], rel_off=p['rel_off'], feats=p['gold_feats'] or {}, k=p['k'],
                der_mass=sum(o['share'] for o in p['opts'] if o['cls'] == 'derived'))


def form_split(S, R):
    out = {}
    sp, rp = [pick_stats(p) for p in S['picks']], [pick_stats(p) for p in R['picks']]
    for c in ('derived', 'lib', 'op'):
        s = [x for x in sp if x['cls'] == c]
        r = [x for x in rp if x['cls'] == c]
        sb, rb = sum(x['bits'] for x in s), sum(x['bits'] for x in r)
        dil = sum(-math.log2(max(1 - x['non'] - x['unk'], 1e-12)) for x in s)
        out[c] = dict(n=len(s), nR=len(r), S=sb, R=rb, gap=sb - rb, dil=dil, rew=sb - rb - dil)
    out['picks'] = (sp, rp)
    return out


def summarize(name, forms):
    print('=' * 30, name, '%d forms' % len(forms))
    rows = []
    for k, v in sorted(forms.items()):
        fs = form_split(v['S'], v['R'])
        sp, rp = fs['picks']
        rows.append((k, v, fs))
    for c in ('derived', 'lib', 'op'):
        xs = [fs[c] for _, _, fs in rows if fs[c]['n']]
        if not xs:
            continue
        print('%-8s forms %2d  gap sum %6.1f median %5.2f | dilution sum %6.1f median %5.2f | reweight sum %6.1f median %5.2f' % (
            c, len(xs), sum(x['gap'] for x in xs), statistics.median(x['gap'] for x in xs), sum(x['dil'] for x in xs), statistics.median(x['dil'] for x in xs),
            sum(x['rew'] for x in xs), statistics.median(x['rew'] for x in xs)))
    # derived picks: shares
    sp_all = [x for _, _, fs in rows for x in fs['picks'][0]]
    rp_all = [x for _, _, fs in rows for x in fs['picks'][1]]
    for c in ('derived', 'lib'):
        s = [x for x in sp_all if x['cls'] == c]
        r = [x for x in rp_all if x['cls'] == c]
        if not s:
            continue
        med = lambda xs, f: statistics.median(f(x) for x in xs) if xs else float('nan')  # noqa: E731
        print('  %s picks S %d R %d' % (c, len(s), len(r)))
        print('    gold share     S %.3f  R %.3f' % (med(s, lambda x: x['gshare']), med(r, lambda x: x['gshare'])))
        print('    non-anc derived share S %.3f (picks with any: %d)   other-anc derived S %.3f R %.3f' % (med(s, lambda x: x['non'] + x['unk']), sum(x['non'] + x['unk'] > 0 for x in s),
              med(s, lambda x: x['anc_other']), med(r, lambda x: x['anc_other'])))
        print('    all derived mass S %.3f R %.3f | lib (non-gold) S %.3f R %.3f | op S %.3f R %.3f' % (med(s, lambda x: x['der_mass']), med(r, lambda x: x['der_mass']),
              med(s, lambda x: x['lib']), med(r, lambda x: x['lib']), med(s, lambda x: x['op']), med(r, lambda x: x['op'])))
        print('    derived options S %.0f (non-anc %.0f, anc %.0f) R %.0f' % (med(s, lambda x: x['nder']), med(s, lambda x: x['nnon']), med(s, lambda x: x['nanc']), med(r, lambda x: x['nder'])))
        sf = [x for x in s if x['f'] is not None]
        rf = [x for x in r if x['f'] is not None]
        print('    gold steer f   S %.2f  R %.2f (picks with the steer: S %d R %d) | gold P share S %.3f R %.3f' % (med(sf, lambda x: x['f']), med(rf, lambda x: x['f']), len(sf), len(rf),
              med([x for x in s if x['p'] is not None], lambda x: x['p']), med([x for x in r if x['p'] is not None], lambda x: x['p'])))
        grp = collections.Counter((a['group'], b['group']) for a, b in zip(s, r))
    # group differences per form
    gd = collections.Counter()
    for k, v, fs in rows:
        gs = {p['group'] for p in v['S']['picks']}
        gr = {p['group'] for p in v['R']['picks']}
        gd['same' if gs == gr else '%s vs %s' % (sorted(gs), sorted(gr))] += 1
    print('  point group (tilt table) S vs R:', dict(gd))
    # features of gold option that differ S vs R (by class), paired by gold token kind and order of picks of the class
    for c in ('derived', 'lib'):
        diff = collections.defaultdict(list)
        npair = 0
        for k, v, fs in rows:
            s = [x for x in fs['picks'][0] if x['cls'] == c and x['feats']]
            r = [x for x in fs['picks'][1] if x['cls'] == c and x['feats']]
            for a, b in zip(s, r):
                npair += 1
                for n in set(a['feats']) | set(b['feats']):
                    va, vb = a['feats'].get(n, 0.0), b['feats'].get(n, 0.0)
                    if abs(va - vb) > 1e-6:
                        diff[n].append(va - vb)
        top = sorted(diff.items(), key=lambda kv: -len(kv[1]))[:22]
        print('  %s gold-option features that differ S - R (%d paired picks): name: picks differing, median diff' % (c, npair))
        print('   ', '; '.join('%s %d %+.2f' % (n, len(d), statistics.median(d)) for n, d in top))
    return rows


def main():
    c = load(REC + '/cause/mass.jsonl')
    v = load(REC + '/cause/mass-covered.jsonl')
    rc = summarize('C', c)
    rv = summarize('covered', v)
    with open(REC + '/cause/split.tsv', 'w') as fh:
        fh.write('set\tarm\ttask\tg\tkind\tscope_n\tS_walk\tR_walk\t' + '\t'.join('%s_%s' % (c_, x) for c_ in ('derived', 'lib', 'op') for x in ('n', 'S', 'R', 'gap', 'dil', 'rew')) + '\n')
        for name, rows in (('C', rc), ('covered', rv)):
            for k, w, fs in rows:
                fh.write('\t'.join([name, *map(str, k), w['S']['kind'], str(w['S']['scope_n']), str(w['S']['total']), str(w['R']['total'])] +
                                   ['%.3f' % fs[c_][x] if x != 'n' else str(fs[c_][x]) for c_ in ('derived', 'lib', 'op') for x in ('n', 'S', 'R', 'gap', 'dil', 'rew')]) + '\n')


main()
