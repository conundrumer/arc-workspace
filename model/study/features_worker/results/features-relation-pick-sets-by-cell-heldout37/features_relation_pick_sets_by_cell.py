#!/usr/bin/env python
"""Splits two reads of the relation pick on the 37 held tasks into cells, from existing tables. No walk, no engine call. Reads the rows that exist, so it runs on a partial walk.

  <runtime python> -B features_relation_pick_sets_by_cell.py HELD_ROWS [--test TEST_ROWS] [--unread-dir DIR] [--earlier-dir DIR] [--out DIR] [--commit HASH]

HELD_ROWS is feasible-walk-held.jsonl. The folder of HELD_ROWS holds the feasible reader, `feasible-read.json` and, by default, the test rows. The runtime python has numpy and zstandard.

Read 1, the feasible set, RULE forms only. The reader's picks: valid forms, gold alive by column type. Escape weight: the share of test picks with gold out of the set. The global weight is the reader's. A cell's weight is (out + 0.5) / (picks + 1) on the test picks of that cell, where the cell has at least MIN_FIT test picks, so that it stays above 0. A pick pays as the reader's `res_soft`.

The join coin: `UNJOINED` of sample2_col.py, 0.14. At an atom after the first, with some relation that can join, the sampler's chance of an atom is the mixture of two arms: weight 0.86 on the options that can join, weight 0.14 on all options. An atom that reads no bound label has chance only in the second arm. The census's relation bits, `q_bits`, are the share under the second arm alone, and the census pays the difference as `join mix`. So `saved_in_coin` compares the same picks inside that mixture, with no fit: the sampler's own mixture, against the mixture with the first arm cut to the set. A pick at a first atom saves 0. After NOT, the sampler's arms agree, and the set goes in the first arm.

Read 2, the unread forms: per-pick-unread.tsv, derived picks of valid census forms. Saving: the mixture of `features_unread_read.mix_form`, variant `options`, w from fit.json. A cell's w is `features_unread_fit.fit_one` on the fit picks of that atom position in RULE forms, derived or not, because the prior is set before the pick shows its class. Net: the saving at every relation pick and NOT pick of the cell, derived or not, from part1-forms.jsonl and walk-held-before.jsonl.zst, per derived pick.

No number here is fit on a held row.
"""
import sys

sys.dont_write_bytecode = True  # imports from the input folders must leave no files there

import argparse  # noqa: E402
import collections  # noqa: E402
import csv  # noqa: E402
import datetime  # noqa: E402
import io  # noqa: E402
import itertools  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import statistics as st  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import zstandard  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
STUDY = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
UNREAD = STUDY + 'features-worker/results/features-relation-pick-unread-forms-heldout37/'
EARLIER = STUDY + 'features-worker/results/features-init-residual-bits-split-74forms/'
CENSUS = STUDY + 'sampler/sampler-worker/sampler-relation-pick-read-heldout431-census/rel_all.jsonl'
THIN_PICKS, THIN_TASKS, MIN_FIT = 50, 8, 100
REPS = 10000
COIN = 0.14  # UNJOINED of model/study/sampler/sample2_col.py
POS = ('first', 'second', 'third', 'fourth and later')
POS_VALUES = {p: ((p,), False) for p in POS}
POS_VALUES['third and later'] = (POS[2:], True)
POS_VALUES['second and later'] = (POS[1:], True)
READER_POS = {'first atom': 'first', 'second atom': 'second', 'third atom': 'third', 'later atoms': 'fourth and later'}
OWN_BASE = ('own derived', 'own other')
SETS2 = ('unread_before', 'unread_so_far', 'unread_later')
T0 = time.time()


def say(*a):
    print('[%5.1fs]' % (time.time() - T0), *a, flush=True)


def pos_of(k):
    return POS[min(k, 4) - 1]


def quart(v):
    q = np.percentile(v, [25, 50, 75])
    return [round(float(x), 1) for x in q]


DRAWS = {}


def boot(tasks, num, den=None):
    """The readers' bootstrap: 10000 draws of the tasks of the cell, seed 0, a ratio of sums. Equal to features_feasible_read.boot where den is 1. Returns mean, 2.5%, 97.5%, unrounded."""
    ts, inv = np.unique(tasks, return_inverse=True)
    n = len(ts)
    a = np.bincount(inv, num, n)
    c = np.bincount(inv, np.ones(len(num)) if den is None else den, n)
    if c.sum() == 0:
        return None, None, None
    if n not in DRAWS:
        DRAWS[n] = np.random.default_rng(0).multinomial(n, np.full(n, 1 / n), size=REPS).astype(float)
    d = DRAWS[n]
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        r = (d @ a) / (d @ c)
    r = r[np.isfinite(r)]
    return float(a.sum() / c.sum()), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))


def cells(splits, values):
    """(split name, cell name, {dim: base values}, is a rollup) of each split, in order."""
    for dims in splits:
        for combo in itertools.product(*[values[d].items() for d in dims]):
            yield (' x '.join(dims) or 'all', ', '.join(c[0] for c in combo) or 'all', {d: c[1][0] for d, c in zip(dims, combo)}, any(c[1][1] for c in combo))


def mask_of(attrs, want, n):
    m = np.ones(n, bool)
    for d, base in want.items():
        m &= np.isin(attrs[d], list(base))
    return m


def write_tsv(name, cols, rows, out):
    with open(out + name + '.new', 'w') as f:
        f.write('\t'.join(cols) + '\n')
        for r in rows:
            f.write('\t'.join('' if r.get(c) is None else (('%.4f' % r[c]) if isinstance(r[c], float) else str(r[c])) for c in cols) + '\n')
    os.replace(out + name + '.new', out + name)
    say('wrote %s, %d rows' % (name, len(rows)))


class Checks:
    def __init__(self):
        self.rows = []

    def add(self, read, scope, what, got, want, tol=0.0):
        ok = got == want if tol == 0 else (got is not None and want is not None and abs(got - want) <= tol)
        self.rows.append(dict(read=read, scope=scope, quantity=what, got=got, reference=want, tolerance=tol, equal=int(ok)))

    def rounded(self, read, scope, what, got, want, digits=3):
        """Equal to a figure that the reference file rounds."""
        self.rows.append(dict(read=read, scope=scope, quantity=what, got=round(got, digits), reference=want, tolerance=0, equal=int(round(got, digits) == want)))


# Read 1

CLASS_VALUES = {c: ((c,), False) for c in ('derived', 'lib', 'macro', 'fact', 'NOT', 'comparison')}
CLASS_VALUES['own'] = (OWN_BASE, False)
CLASS_VALUES['own, derived'] = (('own derived',), True)
CLASS_VALUES['own, other'] = (('own other',), True)
CLASS_VALUES['derived with own'] = (('derived', 'own derived'), True)
VALUES1 = dict(position=POS_VALUES, position_in_body=POS_VALUES, relation_class=CLASS_VALUES)
SPLITS1 = [(), ('position',), ('position_in_body',), ('relation_class',), ('position', 'relation_class'), ('position_in_body', 'relation_class')]
COLS1 = ['set', 'split', 'cell', 'rollup', 'known_at_pick', 'picks', 'tasks', 'forms', 'thin', 'alive_q1', 'alive_median', 'alive_q3', 'set_q1', 'set_median', 'set_q3', 'gold_in', 'share_gold_in', 'share_lo', 'share_hi', 'share_differs_from_pool',
         'bits_paid_all', 'bits_paid_gold_in', 'log2_set_gold_in', 'prior_in_set_gold_in', 'saved_gold_in', 'saved_alive_only', 'test_picks', 'escape_global', 'saved_global', 'saved_lo', 'saved_hi', 'saved_total_bits', 'saved_differs_from_pool', 'uniform_saved_global',
         'escape_cell', 'saved_cell', 'cell_lo', 'cell_hi', 'cell_total_bits', 'coin_returned', 'saved_in_coin', 'coin_lo', 'coin_hi', 'coin_total_bits', 'gold_not_alive_picks']


class Arrays1:
    """One array per measure over the reader's picks. For a set v: n, inside, `tail`: bits inside the set, or bits inside the options outside it."""

    def __init__(self, ds):
        self.ds = ds
        self.n = len(ds)
        self.task = np.array([d['task'] for d in ds])
        self.form = np.array(['%s %d' % (d['task'], d['line']) for d in ds])
        self.bits = np.array([d['q_bits'] for d in ds])
        self.attrs = attrs1(ds)
        self.size, self.inside, self.tail, self.uni, self.in_coin = {}, {}, {}, {}, {}
        self.alive = np.array([sum(not x[R1.DEAD] for x in d['o']) for d in ds])
        self.base_coin = np.array([coin_bits(d) for d in ds])
        alive_save = []
        for v in R1.VARIANTS:
            size, inside, tail, uni, in_coin = [], [], [], [], []
            for d in ds:
                g = d['gold_idx']
                w = np.array([x[R1.W] for x in d['o']], float)
                q = w / w.sum()
                m = np.array([R1.in_set(d, x, v) for x in d['o']], bool)
                al = np.array([not x[R1.DEAD] for x in d['o']], bool)
                ing = bool(m[g])
                size.append(int(m.sum()))
                inside.append(ing)
                if ing:
                    tail.append(-math.log2(q[g] / q[m].sum()))
                    uni.append(math.log2(int(m.sum())))
                else:
                    rest = al & ~m
                    tail.append(-math.log2(q[g] / q[rest].sum()))
                    uni.append(math.log2(max(int(rest.sum()), 1)))
                if v == 'any':
                    alive_save.append(d['q_bits'] + math.log2(q[g] / q[al].sum()))
                if d['k'] > 1 and m.any():
                    in_coin.append(-math.log2((1 - COIN) * (q[g] / q[m].sum() if ing and joined(d) else 0.0) + COIN * q[g]))
                else:
                    in_coin.append(d['q_bits'])
            self.size[v], self.inside[v], self.tail[v], self.uni[v], self.in_coin[v] = np.array(size), np.array(inside), np.array(tail), np.array(uni), np.array(in_coin)
        self.alive_save = np.array(alive_save)

    def soft(self, v, lam, uniform=False):
        """Bits under the set with escape weight lam, as the reader's res_soft (uni_soft with uniform)."""
        t = self.uni[v] if uniform else self.tail[v]
        return np.where(self.inside[v], -math.log2(1 - lam), -math.log2(lam)) + t


def joined(d):
    """Whether gold's atom reads a bound label. A pick with no table of gold's atom counts as joined."""
    return d['gold_atom'].get('reads', 1) > 0


def coin_bits(d):
    """Bits of gold's relation pick in the sampler's mixture over the join coin: `q_bits` where the coin does not change this pick."""
    g = d['gold_idx']
    w = [x[R1.W] for x in d['o']]
    can_join = any(not x[R1.DEAD] and x[R1.KIND] not in ('N', 'C') for x in d['o'])
    if d['k'] <= 1 or d['phase'] != 'root' or not can_join:
        return d['q_bits']
    q = w[g] / sum(w)
    arm = 0.0 if d['o'][g][R1.DEAD] or not joined(d) else w[g] / sum(x[R1.W] for x in d['o'] if not x[R1.DEAD])
    return -math.log2((1 - COIN) * arm + COIN * q)


def attrs1(ds):
    def cls(d):
        c = R1.cls(d)
        return c if c != 'own' else ('own derived' if d['gold_kind'] == 'relation' else 'own other')
    return dict(position=np.array([READER_POS[R1.position(d)] for d in ds]), position_in_body=np.array([pos_of(d['k']) for d in ds]), relation_class=np.array([cls(d) for d in ds]))


def pooled1(a, lam, chk, scope, ref, read1_bits=True):
    """Compares a's pooled figures with feasible-read.json, whose figures come from the same rows."""
    chk.add('feasible', scope, 'picks', a.n, ref['picks'])
    chk.add('feasible', scope, 'tasks', len(set(a.task)), ref['tasks'])
    chk.add('feasible', scope, 'forms', len(set(a.form)), ref['forms'])
    chk.rounded('feasible', scope, 'prior bits', float(a.bits.mean()), ref['prior_bits'])
    for v in R1.VARIANTS:
        i = a.inside[v]
        b = ref['bits'][v]
        chk.add('feasible', scope, 'gold in set, %s' % v, int(i.sum()), b['gold_in'])
        chk.rounded('feasible', scope, 'prior, gold in set, %s' % v, float(a.bits[i].mean()), b['prior_same_picks'])
        chk.rounded('feasible', scope, 'log2 set, gold in set, %s' % v, float(a.uni[v][i].mean()), b['uniform_set'])
        chk.rounded('feasible', scope, 'prior in set, %s' % v, float(a.tail[v][i].mean()), b['prior_in_set'])
        s = a.bits - a.soft(v, lam[v])
        m, lo, hi = boot(a.task, s)
        chk.rounded('feasible', scope, 'saved with escape, %s' % v, m, b['soft']['saved_prior'][0])
        chk.rounded('feasible', scope, 'saved with escape, 2.5%%, %s' % v, lo, b['soft']['saved_prior'][1])
        chk.rounded('feasible', scope, 'saved with escape, 97.5%%, %s' % v, hi, b['soft']['saved_prior'][2])
        chk.rounded('feasible', scope, 'uniform with escape, %s' % v, float(a.soft(v, lam[v], True).mean()), b['soft']['uniform'])
    posit = a.attrs['position']
    for name, p in READER_POS.items():
        if name in ref['sizes']:
            m = posit == p
            chk.add('feasible', scope, 'picks, %s' % name, int(m.sum()), ref['sizes'][name]['picks'])
            chk.add('feasible', scope, 'any set quartiles, %s' % name, quart(a.size['any'][m]), ref['sizes'][name]['any'])
            chk.add('feasible', scope, 'alive quartiles, %s' % name, quart(a.alive[m]), ref['sizes'][name]['alive'])
    base = a.attrs['relation_class']
    for c, r in ref['bits_by_class'].items():
        m = np.isin(base, list(CLASS_VALUES[c][0]))
        chk.add('feasible', scope, 'picks, class %s' % c, int(m.sum()), r['picks'])
        chk.add('feasible', scope, 'gold in any, class %s' % c, int((m & a.inside['any']).sum()), r['gold_in_any'])


def read1(a_held, a_test, lam, skipped):
    rows = []
    pool = {}
    for v in R1.VARIANTS:
        s = a_held.bits - a_held.soft(v, lam[v])
        m, lo, hi = boot(a_held.task, s)
        sh, shlo, shhi = boot(a_held.task, a_held.inside[v].astype(float))
        pool[v] = dict(saved=m, lo=lo, hi=hi, share=sh, total=float(s.sum()))
    for v in R1.VARIANTS:
        for split, cell, want, roll in cells(SPLITS1, VALUES1):
            m = mask_of(a_held.attrs, want, a_held.n)
            n = int(m.sum())
            if not n:
                continue
            t = a_held.task[m]
            i = a_held.inside[v][m]
            tm = mask_of(a_test.attrs, want, a_test.n)
            nt = int(tm.sum())
            s = a_held.bits[m] - a_held.soft(v, lam[v])[m]
            uni = a_held.bits[m] - a_held.soft(v, lam[v], True)[m]
            cs = a_held.base_coin[m] - a_held.in_coin[v][m]
            coin = boot(t, cs)
            mean, lo, hi = boot(t, s)
            sh, shlo, shhi = boot(t, i.astype(float))
            tasks = len(set(t))
            r = dict(set=v, split=split, cell=cell, rollup=int(roll), known_at_pick=int('relation_class' not in want), picks=n, tasks=tasks, forms=len(set(a_held.form[m])), thin=int(n < THIN_PICKS or tasks < THIN_TASKS), gold_in=int(i.sum()), share_gold_in=sh, share_lo=shlo, share_hi=shhi,
                     share_differs_from_pool=int(not shlo <= pool[v]['share'] <= shhi), bits_paid_all=float(a_held.bits[m].mean()), saved_alive_only=float(a_held.alive_save[m].mean()), test_picks=nt, escape_global=round(lam[v], 4), saved_global=mean, saved_lo=lo, saved_hi=hi, saved_total_bits=float(s.sum()),
                     saved_differs_from_pool=int(not lo <= pool[v]['saved'] <= hi), uniform_saved_global=float(uni.mean()), coin_returned=float((a_held.bits[m] - a_held.base_coin[m]).mean()), saved_in_coin=coin[0], coin_lo=coin[1], coin_hi=coin[2], coin_total_bits=float(cs.sum()), gold_not_alive_picks=int(mask_of(skipped['attrs'], want, skipped['n']).sum()))
            r.update(zip(('alive_q1', 'alive_median', 'alive_q3'), quart(a_held.alive[m])))
            r.update(zip(('set_q1', 'set_median', 'set_q3'), quart(a_held.size[v][m])))
            if i.any():
                r.update(bits_paid_gold_in=float(a_held.bits[m][i].mean()), log2_set_gold_in=float(np.log2(a_held.size[v][m][i]).mean()), prior_in_set_gold_in=float(a_held.tail[v][m][i].mean()), saved_gold_in=float((a_held.bits[m][i] - a_held.tail[v][m][i]).mean()))
            if nt >= MIN_FIT:
                out = int((~a_test.inside[v][tm]).sum())
                lc = (out + .5) / (nt + 1)
                sc = a_held.bits[m] - a_held.soft(v, lc)[m]
                cm, clo, chi = boot(t, sc)
                r.update(escape_cell=round(lc, 4), saved_cell=cm, cell_lo=clo, cell_hi=chi, cell_total_bits=float(sc.sum()))
            rows.append(r)
    return rows, pool


def partitions(rows, keyset, chk, read, totals):
    """Each split's cells that are not rollups sum to the pool, for each quantity."""
    for v, pool in totals.items():
        for split in {r['split'] for r in rows if r['set'] == v}:
            sub = [r for r in rows if r['set'] == v and r['split'] == split and not r['rollup']]
            for q, f, tol in keyset:
                chk.add(read, 'current rows', 'sum over cells, %s, %s, %s' % (v, split, q), sum(f(r) for r in sub), pool[q], tol)


def by_position(a_held, a_test, dim, v, lam):
    """Bits saved per pick with the escape weight of each position, all from test picks."""
    bits = np.zeros(a_held.n)
    for p in POS:
        tm = a_test.attrs[dim] == p
        n = int(tm.sum())
        lc = (int((~a_test.inside[v][tm]).sum()) + .5) / (n + 1) if n >= MIN_FIT else lam[v]
        m = a_held.attrs[dim] == p
        bits[m] = a_held.soft(v, lc)[m]
    return boot(a_held.task, a_held.bits - bits)


def coin_policy(a, dead_rows):
    """Inside the join coin, every pick with gold among the options. A pick with gold dead has chance only in the second arm, with or without the set, so it saves 0."""
    out = []
    dq = np.array([d['q_bits'] for d in dead_rows])
    dc = np.array([coin_bits(d) for d in dead_rows])
    dt = np.array([d['task'] for d in dead_rows])
    task = np.concatenate([a.task, dt])
    for v in R1.VARIANTS:
        sv = np.concatenate([a.base_coin - a.in_coin[v], np.zeros(len(dq))])
        r = dict(read='feasible', set=v, policy='every pick with gold among the options, the set in the join coin first arm, no fit', picks=len(task), tasks=len(set(task)), parameter=COIN)
        r.update(zip(('saved', 'lo', 'hi'), boot(task, sv)))
        out.append(r)
    r = dict(read='feasible', set='-', policy='join coin: q_bits less the pick in the coin, per pick, these rows, gold alive or dead', picks=len(task), tasks=len(set(task)), parameter=COIN)
    r.update(zip(('saved', 'lo', 'hi'), boot(task, np.concatenate([a.bits - a.base_coin, dq - dc]))))
    out.append(r)
    r = dict(read='feasible', set='-', policy='join coin: q_bits less the pick in the coin, per pick, gold alive only', picks=a.n, tasks=len(set(a.task)), parameter=COIN)
    r.update(zip(('saved', 'lo', 'hi'), boot(a.task, a.bits - a.base_coin)))
    out.append(r)
    return out


def coverage(picks):
    """Census rows against the rows that the walk has so far, by position and by class. The census rows hold every pick of the census, gold alive or not."""
    groups = collections.defaultdict(lambda: [0, 0.0, 0, 0.0])
    for line in open(CENSUS):
        d = json.loads(line)
        if d['rec'] != 'rel' or not math.isfinite(d['q_bits']):
            continue
        walked = (d['task'], d['line'], d['ord'], d['phase']) in picks
        c = 'own' if d['own'] else R1.CLASS.get(d['gold_kind'], d['gold_kind'])
        for g in ('all', 'position: ' + READER_POS[R1.position(d)], 'class: ' + c):
            e = groups[g]
            e[0] += 1
            e[1] += d['q_bits']
            if walked:
                e[2] += 1
                e[3] += d['q_bits']
    return [dict(group=g, census_rows=e[0], walked_rows=e[2], share_walked=e[2] / e[0], census_bits=e[1] / e[0], walked_bits=e[3] / e[2] if e[2] else None) for g, e in sorted(groups.items())]


# Read 2

def place_base(ctx):
    br = ' br' in ctx or ctx.startswith('br')
    if 'key' in ctx:
        return 'key, in a branch' if br else 'key, no branch'
    if 'port' in ctx:
        return 'port, in a branch' if br else 'port, no branch'
    if 'outside' in ctx:
        return 'outside'
    return 'branch' if br else 'top'


KEYS = ('key, no branch', 'key, in a branch')
PORTS = ('port, no branch', 'port, in a branch')
PLACE_VALUES = {'top': (('top',), False), 'key': (KEYS, False), 'port': (PORTS, False), 'branch': (('branch',), False), 'outside': (('outside',), False)}
PLACE_VALUES.update({k: ((k,), True) for k in KEYS + PORTS})
PLACE_VALUES['key or port'] = (KEYS + PORTS, True)
PLACE_VALUES['any branch'] = (('branch', 'key, in a branch', 'port, in a branch'), True)
KIND_VALUES = {k: ((k,), False) for k in ('RULE', 'INIT', 'DET')}
READ_VALUES = {'first read': (('first read',), False), 'repeat': (('repeat',), False)}
VALUES2 = dict(position=POS_VALUES, kind=KIND_VALUES, read=READ_VALUES, place=PLACE_VALUES)
SPLITS2 = [(), ('position',), ('kind',), ('read',), ('place',), ('position', 'kind'), ('position', 'read'), ('position', 'place'), ('kind', 'read'), ('kind', 'place')]
COLS2 = ['set', 'split', 'cell', 'rollup', 'known_at_pick', 'picks', 'tasks', 'forms', 'thin', 'forms_q1', 'forms_median', 'forms_q3', 'options_q1', 'options_median', 'options_q3', 'gold_in', 'share_gold_in', 'share_lo', 'share_hi', 'share_differs_from_pool',
         'bits_paid_all', 'bits_paid_gold_in', 'log2_forms_gold_in', 'log2_options_gold_in', 'w_global', 'saved_global', 'saved_lo', 'saved_hi', 'saved_total_bits', 'saved_differs_from_pool', 'top5_share', 'w_source', 'w_cell', 'fit_picks', 'fit_derived_picks', 'saved_cell', 'cell_lo', 'cell_hi', 'cell_total_bits',
         'other_picks', 'net_per_derived', 'net_lo', 'net_hi', 'net_total_bits', 'net_cell_per_derived', 'net_cell_total_bits', 'net_note']
COLS_POOL = ['arm', 'split', 'cell', 'rollup', 'picks', 'tasks', 'thin', 'readable', 'found', 'found_share', 'found_lo', 'found_hi', 'found_differs_from_pool', 'target_forms', 'target_forms_found', 'unread_found_q1', 'unread_found_median', 'unread_found_q3', 'unread_end_median', 'log2_found_mean', 'bits_found_mean', 'log2_end_mean', 'bits_read_mean',
             'in_unread_end', 'in_unread_end_share', 'bits_in_unread_end', 'log2_end_in_unread_end', 'log2_found_in_unread_end']


JOIN_MIX = {}


def num(x):
    return None if x == '' else float(x)


def load_table(path):
    rows = list(csv.DictReader(open(path), delimiter='\t'))
    keep = [r for r in rows if r['form_valid'] == '1' and r['has_bits'] == '1']
    return rows, keep


def load_all_picks(d):
    """Every relation pick and NOT pick of the forms of the mixture read, derived or not, with the option counts of each set."""
    forms = [json.loads(x) for x in open(d + 'part1-forms.jsonl')]
    golds = {p['task']: L.Gold(L.lines_of(p['gold_sexp'])) for p in json.load(open(L.BASE + 'points-base.json'))}
    walk = {}
    with open(d + 'walk-held-before.jsonl.zst', 'rb') as f:
        for x in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            r = json.loads(x)
            walk[r['task'], r['line']] = r
            if len(walk) % 200 == 0:
                say('walk rows read', len(walk))
    bad = 0
    for f in forms:
        if (f['task'], f['line']) in walk and f['census']:
            bad += not R2.attach_walk(f, golds[f['task']], walk)
    assert bad == 0
    t0, _none = R2.over(forms)
    returned, picks = 0.0, 0
    for k_, w in walk.items():
        if w['kind'] == 'RULE' and k_ in t0:
            picks += len(w['picks'])
            for (_ctx, _text, bits), det in zip(w['atoms'], w['detail']):
                if bits is not None:
                    returned += sum(det['cur'].values()) - bits
    JOIN_MIX.update(returned=returned / picks, picks=picks)
    out = []
    for f in forms:
        if (f['task'], f['line']) not in t0:
            continue
        for a in f['atoms']:
            for key, bits in (('op', a['op_bits']), ('rel', a['rel_bits'])):
                if bits is None:
                    continue
                der = key == 'rel' and 'target' in a
                out.append(dict(task=f['task'], line=f['line'], kind=f['kind'], k=a['k'], ctx=a['ctx'], derived=der, bits=bits, c={s: a['o_' + key][s] for s in SETS2}, inside={s: bool(der and a['inside'][s] and a.get('offered')) for s in SETS2}))
    return out


def mix(bits, w, c, inside):
    """L.mix_bits over arrays."""
    p = 2.0 ** -bits
    q = (1 - w) * p + np.where(inside & (c > 0), w / np.maximum(c, 1), 0.0)
    return np.where(c > 0, -np.log2(np.where(c > 0, q, 1.0)), bits)


class Arrays2:
    def __init__(self, keep):
        self.n = len(keep)
        self.task = np.array([r['task'] for r in keep])
        self.form = np.array(['%s %s' % (r['task'], r['form_line']) for r in keep])
        self.bits = np.array([float(r['bits_relation']) for r in keep])
        self.attrs = dict(position=np.array([pos_of(int(r['atom_k'])) for r in keep]), kind=np.array([r['form_kind'] for r in keep]), read=np.array(['repeat' if r['repeat_relation'] == '1' else 'first read' for r in keep]), place=np.array([place_base(r['place']) for r in keep]))
        self.n_forms = {s: np.array([int(r['n_' + s]) for r in keep]) for s in SETS2}
        self.n_opts = {s: np.array([int(r['options_' + s]) for r in keep]) for s in SETS2}
        self.inside = {s: np.array([r['in_' + s] == '1' for r in keep]) for s in SETS2}
        self.offered = np.array([r['target_offered'] == '1' for r in keep])
        self.rows = keep


class ArraysAll:
    def __init__(self, picks):
        self.n = len(picks)
        self.task = np.array([p['task'] for p in picks])
        self.bits = np.array([p['bits'] for p in picks])
        self.derived = np.array([p['derived'] for p in picks])
        self.attrs = dict(position=np.array([pos_of(p['k']) for p in picks]), kind=np.array([p['kind'] for p in picks]), place=np.array([place_base(p['ctx']) for p in picks]))
        self.c = {s: np.array([p['c'][s] for p in picks]) for s in SETS2}
        self.inside = {s: np.array([p['inside'][s] for p in picks]) for s in SETS2}


def fit_cells(fit_rows, w_global, chk):
    """w by atom position on RULE forms of fit-picks.jsonl, for each set, on every pick of the position."""
    picks = [p for r in fit_rows if r['valid'] and 'test' in r['part'] for p in r['picks']]
    for s in SETS2:
        w = RF.fit_one(picks, s, 'options')
        chk.add('unread', 'fit picks', 'w of all fit picks, %s' % s, round(w, 5), w_global[s], 2e-5)
    chk.add('unread', 'fit picks', 'fit picks', len(picks), 4193)
    out = {}
    for name, (base, _roll) in POS_VALUES.items():
        sub = [p for p in picks if pos_of(p['k']) in base]
        der = sum(p['derived'] for p in sub)
        out[name] = dict(n=len(sub), der=der, w={})
        if len(sub) >= MIN_FIT:
            for s in SETS2:
                out[name]['w'][s] = round(RF.fit_one(sub, s, 'options'), 5)
    return out


def read2(a, b, w_global, fits):
    rows = []
    pool = {}
    for s in SETS2:
        ins = a.inside[s] & a.offered
        saved = a.bits - mix(a.bits, w_global[s], a.n_opts[s], ins)
        m, lo, hi = boot(a.task, saved)
        sh, _, _ = boot(a.task, a.inside[s].astype(float))
        pool[s] = dict(saved=m, lo=lo, hi=hi, share=sh, total=float(saved.sum()))
    for s in SETS2:
        ins = a.inside[s] & a.offered
        saved_all = a.bits - mix(a.bits, w_global[s], a.n_opts[s], ins)
        all_saved = b.bits - mix(b.bits, w_global[s], b.c[s], b.inside[s])
        for split, cell, want, roll in cells(SPLITS2, VALUES2):
            m = mask_of(a.attrs, want, a.n)
            n = int(m.sum())
            pick_time = 'read' not in want
            bm = mask_of(b.attrs, {k: v for k, v in want.items() if k != 'read'}, b.n) if pick_time else None
            if not n and not (pick_time and bm.any()):
                continue
            r = dict(set=s, split=split, cell=cell, rollup=int(roll), known_at_pick=int(pick_time), picks=n, w_global=w_global[s])
            kinds = sorted(set(a.attrs['kind'][m]))
            is_rule_position = want.get('kind') == ('RULE',) and 'position' in want and 'read' not in want and 'place' not in want
            if kinds == ['RULE']:
                r['w_source'] = 'fit.json, RULE fit picks'
            elif kinds:
                r['w_source'] = 'fit.json; the w of RULE fit picks, as %s forms have no non-held rows' % ' and '.join(k for k in kinds if k != 'RULE')
            if n:
                t = a.task[m]
                tasks = len(set(t))
                i = a.inside[s][m]
                sv = saved_all[m]
                mean, lo, hi = boot(t, sv)
                big = np.sort(sv)[::-1]
                r['top5_share'] = float(big[:5].sum() / sv.sum()) if sv.sum() > 0 else None
                sh, shlo, shhi = boot(t, i.astype(float))
                r.update(tasks=tasks, forms=len(set(a.form[m])), thin=int(n < THIN_PICKS or tasks < THIN_TASKS), gold_in=int(i.sum()), share_gold_in=sh, share_lo=shlo, share_hi=shhi, share_differs_from_pool=int(not shlo <= pool[s]['share'] <= shhi), bits_paid_all=float(a.bits[m].mean()),
                         saved_global=mean, saved_lo=lo, saved_hi=hi, saved_total_bits=float(sv.sum()), saved_differs_from_pool=int(not lo <= pool[s]['saved'] <= hi))
                r.update(zip(('forms_q1', 'forms_median', 'forms_q3'), quart(a.n_forms[s][m])))
                r.update(zip(('options_q1', 'options_median', 'options_q3'), quart(a.n_opts[s][m])))
                if i.any():
                    r.update(bits_paid_gold_in=float(a.bits[m][i].mean()), log2_forms_gold_in=float(np.log2(a.n_forms[s][m][i]).mean()), log2_options_gold_in=float(np.log2(a.n_opts[s][m][ins[m]]).mean()) if ins[m].any() else None)
            if is_rule_position:
                p = cell.split(', ')[0]
                f = fits[p]
                r.update(fit_picks=f['n'], fit_derived_picks=f['der'])
                if s in f['w'] and n:
                    wc = f['w'][s]
                    sc = a.bits[m] - mix(a.bits[m], wc, a.n_opts[s][m], ins[m])
                    cm, clo, chi = boot(a.task[m], sc)
                    r.update(w_cell=wc, saved_cell=cm, cell_lo=clo, cell_hi=chi, cell_total_bits=float(sc.sum()))
            if pick_time:
                nsum = all_saved[bm]
                r['other_picks'] = int((~b.derived[bm]).sum())
                r['net_total_bits'] = float(nsum.sum())
                if b.derived[bm].any():
                    nm, nlo, nhi = boot(b.task[bm], nsum, b.derived[bm].astype(float))
                    r.update(net_per_derived=nm, net_lo=nlo, net_hi=nhi)
                if r.get('w_cell') is not None:
                    ns = b.bits[bm] - mix(b.bits[bm], r['w_cell'], b.c[s][bm], b.inside[s][bm])
                    r.update(net_cell_total_bits=float(ns.sum()), net_cell_per_derived=float(ns.sum() / b.derived[bm].sum()))
            else:
                r['net_note'] = 'none: a pick that is not derived has no first read or repeat, so the class has no picks that are not derived'
            rows.append(r)
    return rows, pool


def read_pool(keep, chk, summary):
    rows = []
    run = [r for r in keep if r['task'] not in L.NOT_IN_RUN]
    attrs = dict(position=np.array([pos_of(int(r['atom_k'])) for r in run]), kind=np.array([r['form_kind'] for r in run]), read=np.array(['repeat' if r['repeat_relation'] == '1' else 'first read' for r in run]), place=np.array([place_base(r['place']) for r in run]))
    tasks = np.array([r['task'] for r in run])
    for arm, q in (('control_search', 'control_'), ('factored_search', 'factored_')):
        found_all = np.array([num(r[q + 'found']) if r[q + 'found'] != '' else np.nan for r in run])
        readable = ~np.isnan(found_all)
        pool_share = float(np.nansum(found_all) / readable.sum())
        for split, cell, want, roll in cells(SPLITS2, VALUES2):
            m = mask_of(attrs, want, len(run))
            if not m.any():
                continue
            sub = [r for r, x in zip(run, m) if x]
            read = [r for r in sub if r[q + 'found'] != '']
            found = [r for r in read if r[q + 'found'] == '1']
            nt = len({r['task'] for r in sub})
            e = dict(arm=arm, split=split, cell=cell, rollup=int(roll), picks=len(sub), tasks=nt, thin=int(len(sub) < THIN_PICKS or nt < THIN_TASKS), readable=len(read), found=len(found), target_forms=len({(r['task'], r['target_line']) for r in read}), target_forms_found=len({(r['task'], r['target_line']) for r in found}))
            if read:
                rm = m & readable
                sh, lo, hi = boot(tasks[rm], found_all[rm])
                ends = [float(r[q + 'unread_end']) for r in read]
                e.update(found_share=sh, found_lo=lo, found_hi=hi, found_differs_from_pool=int(not lo <= pool_share <= hi), unread_end_median=st.median(ends), log2_end_mean=sum(math.log2(x) for x in ends) / len(ends), bits_read_mean=sum(float(r['bits_relation']) for r in read) / len(read))
            if found:
                u = [float(r[q + 'unread_at_found']) for r in found]
                qs = np.percentile(u, [25, 50, 75])
                e.update(unread_found_q1=float(qs[0]), unread_found_median=float(qs[1]), unread_found_q3=float(qs[2]), log2_found_mean=sum(math.log2(max(1, x)) for x in u) / len(u), bits_found_mean=sum(float(r['bits_relation']) for r in found) / len(found))
                un = [r for r in found if r[q + 'in_unread_end'] == '1']
                nodes = [r for r in found if r[q + 'covering_node'] != '']
                e.update(in_unread_end=len(un), in_unread_end_share=len(un) / len(nodes) if nodes else None)
                if un:
                    e.update(bits_in_unread_end=sum(float(r['bits_relation']) for r in un) / len(un), log2_end_in_unread_end=sum(math.log2(float(r[q + 'unread_end'])) for r in un) / len(un), log2_found_in_unread_end=sum(math.log2(max(1, float(r[q + 'unread_at_found']))) for r in un) / len(un))
            rows.append(e)
    # check against the summary's pool rows and each split's cells against the arm's whole
    for s in summary['pool']:
        cell = 'all' if s['group'] == 'all' else s['group']
        split = 'all' if s['group'] == 'all' else 'kind'
        r = next(x for x in rows if x['arm'] == s['arm'] and x['split'] == split and x['cell'] == cell)
        scope = '%s, %s' % (s['arm'], s['group'])
        chk.add('pool', scope, 'picks', r['picks'], s['picks'])
        chk.add('pool', scope, 'readable', r['readable'], s['readable'])
        chk.add('pool', scope, 'found', r['found'], s['found'])
        chk.add('pool', scope, 'target forms', r['target_forms'], s['target_forms'])
        chk.add('pool', scope, 'target forms found', r['target_forms_found'], s['target_forms_found'])
        chk.add('pool', scope, 'unread at found, median', r['unread_found_median'], float(s['unread_at_found_median']))
        chk.add('pool', scope, 'unread at end, median', r['unread_end_median'], float(s['unread_end_median']))
        chk.add('pool', scope, 'log2 at found', r['log2_found_mean'], s['log2_at_found_mean'], 1e-9)
        chk.add('pool', scope, 'log2 at end', r['log2_end_mean'], s['log2_end_mean'], 1e-9)
        chk.add('pool', scope, 'bits at found', r['bits_found_mean'], s['bits_found_mean'], 1e-9)
        chk.add('pool', scope, 'bits read', r['bits_read_mean'], s['bits_read_mean'], 1e-9)
        chk.add('pool', scope, 'target unread at end', r['in_unread_end'], s['unread_end_inside'])
    for arm in ('control_search', 'factored_search'):
        allr = next(x for x in rows if x['arm'] == arm and x['split'] == 'all')
        for split in {r['split'] for r in rows}:
            sub = [r for r in rows if r['arm'] == arm and r['split'] == split and not r['rollup']]
            for q in ('picks', 'readable', 'found'):
                chk.add('pool', arm, 'sum over cells, %s, %s' % (split, q), sum(r[q] for r in sub), allr[q])
    return rows


def checks2(a, b, rows, pool, summary, w_global, chk):
    chk.add('unread', 'table', 'derived picks of valid forms', a.n, summary['sizes'][0]['picks'])
    der = b.derived
    chk.add('unread', 'walk against table', 'derived picks', int(der.sum()), a.n)
    chk.add('unread', 'walk against table', 'bits', float(b.bits[der].sum()), float(a.bits.sum()), 1e-6)
    for s in SETS2:
        chk.add('unread', 'walk against table', 'option counts equal, %s' % s, int((b.c[s][der] == a.n_opts[s]).all()), 1)
        chk.add('unread', 'walk against table', 'gold inside equal, %s' % s, int((b.inside[s][der] == (a.inside[s] & a.offered)).all()), 1)
    group = {g['group']: g for g in summary['sizes']}
    name_pos = {'first': 'first', 'second': 'second', 'third': 'third', 'later': 'fourth and later'}
    for g, e in group.items():
        if g == 'all':
            split, cell = 'all', 'all'
        elif ',' not in g:
            split, cell = 'kind', g
        else:
            k, p = g.split(', ')
            split, cell = ('position', name_pos[p]) if k == 'all' else ('position x kind', '%s, %s' % (name_pos[p], k))
        for s in SETS2:
            r = next(x for x in rows if x['set'] == s and x['split'] == split and x['cell'] == cell)
            chk.add('unread', g, 'picks', r['picks'], e['picks'])
            chk.add('unread', g, 'tasks', r['tasks'], e['tasks'])
            chk.add('unread', g, 'median forms in set, %s' % s, r['forms_median'], float(e[s]['median']))
            chk.add('unread', g, 'gold in, %s' % s, r['gold_in'], e[s]['inside'])
            chk.add('unread', g, 'bits paid', r['bits_paid_all'], e['bits'], 1e-9)
            if e[s]['inside']:
                chk.add('unread', g, 'bits, gold in, %s' % s, r['bits_paid_gold_in'], e[s]['bits_inside'], 1e-9)
                chk.add('unread', g, 'log2 forms, gold in, %s' % s, r['log2_forms_gold_in'], e[s]['log2_inside'], 1e-9)
    for m in summary['mixture']:
        if m['variant'] != 'options':
            continue
        s = m['set']
        allr = next(x for x in rows if x['set'] == s and x['split'] == 'all')
        chk.add('unread', 'mixture', 'w, %s' % s, allr['w_global'], m['w'])
        chk.add('unread', 'mixture', 'derived picks, %s' % s, allr['picks'], m['derived_picks'])
        chk.add('unread', 'mixture', 'all relation picks, %s' % s, b.n, m['relation_picks'])
        chk.add('unread', 'mixture', 'saved per derived pick, %s' % s, allr['saved_global'], m['saved_per_derived_pick'], 1e-9)
        chk.add('unread', 'mixture', 'net per derived pick, %s' % s, allr['net_per_derived'], m['net_saved_per_derived_pick'], 1e-9)
        by = collections.defaultdict(lambda: [0.0, 0])
        ins = a.inside[s] & a.offered
        sv = a.bits - mix(a.bits, m['w'], a.n_opts[s], ins)
        for t, x in zip(a.task, sv):
            by[t][0] += float(x)
            by[t][1] += 1
        lo, hi = R2.bootstrap({k: tuple(v) for k, v in by.items()})
        chk.add('unread', 'mixture', "reader's bootstrap, 2.5%%, %s" % s, lo, m['ci95'][0], 1e-9)
        chk.add('unread', 'mixture', "reader's bootstrap, 97.5%%, %s" % s, hi, m['ci95'][1], 1e-9)
        chk.add('unread', 'mixture', "this script's 2.5%% against the reader's, %s" % s, allr['saved_lo'], m['ci95'][0], 0.004)
        chk.add('unread', 'mixture', "this script's 97.5%% against the reader's, %s" % s, allr['saved_hi'], m['ci95'][1], 0.004)


def earlier(d, rows2, a):
    """How the earlier 167 of 267 relates to this table: the counts of the earlier record by place and by held status, then this table's cells."""
    out = []
    for r in csv.DictReader(open(d + 'read-counts.tsv'), delimiter='\t'):
        n, c = int(r['reads']), int(r['unread_before_gold_in'])
        out.append(dict(source='earlier record, %s tasks' % r['set'], place=r['place'], reads=n, gold_in=c, share=c / n))
    for set_ in ('all', 'not held', 'held'):
        sub = [x for x in out if x['source'] == 'earlier record, %s tasks' % set_]
        n, c = sum(x['reads'] for x in sub), sum(x['gold_in'] for x in sub)
        out.append(dict(source='earlier record, %s tasks' % set_, place='key and port', reads=n, gold_in=c, share=c / n))
    form = [json.loads(x) for x in open(d + 'form-set.jsonl')]
    held = [f for f in form if f['held']]
    out.append(dict(source='earlier record, forms', place='all %d forms, %d tasks; held %d forms, %d tasks' % (len(form), len({f['task'] for f in form}), len(held), len({f['task'] for f in held}))))
    m = (a.attrs['kind'] == 'INIT') & np.isin(a.attrs['place'], list(KEYS + PORTS)) & np.isin(a.task, sorted({f['task'] for f in held}))
    sh, lo, hi = boot(a.task[m], a.inside['unread_before'][m].astype(float))
    out.append(dict(source='this table, unread_before, the held tasks of the earlier record', place='INIT, key or port', reads=int(m.sum()), gold_in=int(a.inside['unread_before'][m].sum()), share=sh, lo=lo, hi=hi, tasks=len(set(a.task[m]))))
    for cell in ('INIT, key', 'INIT, port', 'INIT, key or port', 'INIT, key, no branch', 'INIT, port, no branch'):
        r = next((x for x in rows2 if x['set'] == 'unread_before' and x['split'] == 'kind x place' and x['cell'] == cell), None)
        if r:
            out.append(dict(source='this table, unread_before', place=cell, reads=r['picks'], gold_in=r['gold_in'], share=r['share_gold_in'], lo=r['share_lo'], hi=r['share_hi'], tasks=r['tasks']))
    r = next(x for x in rows2 if x['set'] == 'unread_before' and x['split'] == 'kind' and x['cell'] == 'INIT')
    out.append(dict(source='this table, unread_before', place='INIT', reads=r['picks'], gold_in=r['gold_in'], share=r['share_gold_in'], lo=r['share_lo'], hi=r['share_hi'], tasks=r['tasks']))
    r = next(x for x in rows2 if x['set'] == 'unread_before' and x['split'] == 'all')
    out.append(dict(source='this table, unread_before', place='all derived picks', reads=r['picks'], gold_in=r['gold_in'], share=r['share_gold_in'], lo=r['share_lo'], hi=r['share_hi'], tasks=r['tasks']))
    return out


def policy_rule(b, w_global, fits):
    """RULE forms, every relation pick and NOT pick: bits saved per pick with one w, against w by atom position. All w from fit picks."""
    m = b.attrs['kind'] == 'RULE'
    t = b.task[m]
    bits = b.bits[m]
    posn = b.attrs['position'][m]
    out = []
    for s in SETS2:
        c, ins = b.c[s][m], b.inside[s][m]
        sv = bits - mix(bits, w_global[s], c, ins)
        r = dict(read='unread', set=s, policy='RULE forms, every relation pick, one w', picks=int(m.sum()), tasks=len(set(t)), parameter=w_global[s])
        r.update(zip(('saved', 'lo', 'hi'), boot(t, sv)))
        out.append(r)
        new = np.zeros(len(bits))
        ws = {}
        for p in POS:
            w = fits[p]['w'].get(s, w_global[s])
            ws[p] = w
            k = posn == p
            new[k] = mix(bits[k], w, c[k], ins[k])
        r = dict(read='unread', set=s, policy='RULE forms, every relation pick, w by position', picks=int(m.sum()), tasks=len(set(t)), parameter=json.dumps(ws))
        r.update(zip(('saved', 'lo', 'hi'), boot(t, bits - new)))
        out.append(r)
    return out


# Report

def fmt(x, d=3):
    return '-' if x is None else ('%.*f' % (d, x))


def ivl(r, a='saved_global', lo='saved_lo', hi='saved_hi'):
    return '%s (%s to %s)' % (fmt(r.get(a)), fmt(r.get(lo)), fmt(r.get(hi)))


def table(head, rows):
    out = ['| ' + ' | '.join(head) + ' |', '|' + '---|' * len(head)]
    out += ['| ' + ' | '.join(str(c) for c in r) + ' |' for r in rows]
    return out + ['']


def signal_rows(rows1, rows2):
    out = []
    for read, rows, setname in (('feasible', rows1, None), ('unread', rows2, None)):
        for r in rows:
            if r.get('thin') == 0 and (r.get('saved_differs_from_pool') or r.get('share_differs_from_pool')):
                e = {k: r.get(k) for k in ('set', 'split', 'cell', 'rollup', 'known_at_pick', 'picks', 'tasks', 'gold_in', 'share_gold_in', 'share_lo', 'share_hi', 'share_differs_from_pool', 'saved_global', 'saved_lo', 'saved_hi', 'saved_total_bits', 'saved_differs_from_pool', 'saved_in_coin', 'coin_lo', 'coin_hi', 'net_per_derived', 'net_lo', 'net_hi')}
                e['read'] = read
                e['net_total_bits'] = r.get('net_total_bits')
                out.append(e)
    out.sort(key=lambda x: -x['saved_total_bits'])
    return out


def write_partial(out, info, rows1, pool1, rows2, pool2, poolr, sig, cov, early, policy, nchk, nbad):
    L_ = ['# Relation pick sets by cell, held 37 tasks: partial', '', 'Generated by features_relation_pick_sets_by_cell.py. The numbers change as held rows land.', '']
    L_ += ['## Rows', '']
    L_ += ['- Feasible read: %d picks, %d tasks, %d forms, of %d pick rows at this run. The census has 1761 gold-alive picks. Left out: %d picks of invalid forms, %d picks where gold is not among the options, %d picks where gold is dead by join. A pick with gold dead has no price in the reader.' % (info['p1'], info['t1'], info['f1'], info['rows1'], info['invalid1'], info['none1'], info['dead1'])]
    L_ += ['- Escape weight: %d test picks, %d tasks. Global weights %s.' % (info['test_picks'], info['test_tasks'], json.dumps(info['lam']))]
    L_ += ['- The feasible walk holds RULE forms only, so its rows have no form kind split.']
    L_ += ['- Unread read: %d derived picks of valid forms, %d tasks. Left out: %d rows of invalid forms or of forms with no census row: %s.' % (info['p2'], info['t2'], info['left2'], info['left2_kinds'])]
    L_ += ['- Net saving: %d relation picks and NOT picks of the same forms, from part1-forms.jsonl and walk-held-before.jsonl.zst. per-pick-unread.tsv alone holds derived picks only.' % info['all2']]
    L_ += ['- Pool read: %d derived picks on the run\'s 35 tasks.' % info['p3'], '- Fit picks: %d, RULE forms of the test tasks.' % info['fit_picks'], '']
    L_ += ['Totals: %d checks in totals-check.tsv, %d not equal.' % (nchk, nbad), '']
    L_ += ['## Terms', '']
    L_ += ['- `position`: in the feasible read, the reader\'s count of atoms over the form. A second branch\'s first atom is not a first atom here.']
    L_ += ['- `position_in_body`, and `position` in the unread read: the census\'s `k`, which starts again at each body and branch.']
    L_ += ['- Feasible class `own`: gold\'s relation is in the form\'s earlier atoms, whatever its kind. So a repeat of a derived form is in `own`, and the unread read counts it as derived. `derived with own` is the cell to set against the unread read\'s derived picks.']
    L_ += ['- `known_at_pick`: 1 where the cell is known before the pick. A class cell is known only after gold is drawn. An escape weight or a w of such a cell is no prior, so read it as an upper bound.']
    L_ += ['- `thin`: under %d picks or under %d tasks.' % (THIN_PICKS, THIN_TASKS)]
    L_ += ['- A cell differs from the pool where the pooled figure is outside the cell\'s 95% task interval.']
    L_ += ['- `saved_in_coin`, feasible read: the saving inside the sampler\'s join coin, as the script\'s docstring says. The escape savings compare with `q_bits`, the share of one arm of the coin. The census adds the rest of the coin to each atom as `join mix`. The coin acts on an atom, and this figure applies it to each pick.', '']
    L_ += ['## Feasible set, `any`, single splits', '']
    L_ += table(['Cell', 'Picks', 'Tasks', 'Thin', 'Set Q1, median, Q3', 'Gold in', 'Bits paid, gold in', 'log2 set, gold in', 'Saved, global escape', 'Total bits', 'Escape of cell', 'Saved, escape of cell', 'Alive only', 'Saved in join coin'],
                [[('%s: %s' % (r['split'], r['cell']) if r['split'] != 'all' else 'all'), r['picks'], r['tasks'], r['thin'], '%s, %s, %s' % (r['set_q1'], r['set_median'], r['set_q3']), '%.3f' % r['share_gold_in'], fmt(r.get('bits_paid_gold_in')), fmt(r.get('log2_set_gold_in')), ivl(r), '%.1f' % r['saved_total_bits'], r.get('escape_cell', '-'), ivl(r, 'saved_cell', 'cell_lo', 'cell_hi'), fmt(r['saved_alive_only']), ivl(r, 'saved_in_coin', 'coin_lo', 'coin_hi')]
                 for r in rows1 if r['set'] == 'any' and r['split'] in ('all', 'position', 'position_in_body', 'relation_class')])
    L_ += ['## Unread forms, `unread_before`, single splits', '']
    L_ += table(['Cell', 'Picks', 'Tasks', 'Thin', 'Options in set Q1, median, Q3', 'Gold in', 'Bits paid, gold in', 'log2 options, gold in', 'Saved, global w', 'Total bits', 'Other picks', 'Net per derived', 'Net total'],
                [[('%s: %s' % (r['split'], r['cell']) if r['split'] != 'all' else 'all'), r['picks'], r.get('tasks'), r.get('thin'), '%s, %s, %s' % (r.get('options_q1'), r.get('options_median'), r.get('options_q3')), fmt(r.get('share_gold_in')), fmt(r.get('bits_paid_gold_in')), fmt(r.get('log2_options_gold_in')), ivl(r), fmt(r.get('saved_total_bits'), 1), r.get('other_picks', '-'), ivl(r, 'net_per_derived', 'net_lo', 'net_hi'), fmt(r.get('net_total_bits'), 1)]
                 for r in rows2 if r['set'] == 'unread_before' and r['split'] in ('all', 'position', 'kind', 'read', 'place')])
    L_ += ['## RULE cells with w fit on fit picks', '', 'The fit reads every pick of the position, derived or not. Other cells use the global w: fit-picks.jsonl has no `place` and no repeat column, and INIT and DET forms have no non-held rows.', '']
    L_ += table(['Set', 'Cell', 'Picks', 'Fit picks', 'w of cell', 'Saved, w of cell', 'Saved, global w', 'Net, w of cell', 'Net, global w'],
                [[r['set'], r['cell'], r['picks'], r.get('fit_picks'), r.get('w_cell', '-'), ivl(r, 'saved_cell', 'cell_lo', 'cell_hi'), ivl(r), fmt(r.get('net_cell_per_derived')), fmt(r.get('net_per_derived'))] for r in rows2 if r['split'] == 'position x kind' and r['cell'].endswith('RULE') and not r['rollup']])
    L_ += ['## Pool forms, control_search', '']
    L_ += table(['Cell', 'Picks', 'Thin', 'Readable', 'Found, 95%', 'Unread at found Q1, median, Q3', 'log2 at found', 'Bits at found', 'log2 at end', 'Bits read'],
                [[('%s: %s' % (r['split'], r['cell']) if r['split'] != 'all' else 'all'), r['picks'], r['thin'], r['readable'], ivl(r, 'found_share', 'found_lo', 'found_hi'), '%s, %s, %s' % (r.get('unread_found_q1'), r.get('unread_found_median'), r.get('unread_found_q3')), fmt(r.get('log2_found_mean'), 2), fmt(r.get('bits_found_mean'), 2), fmt(r.get('log2_end_mean'), 2), fmt(r.get('bits_read_mean'), 2)]
                 for r in poolr if r['arm'] == 'control_search' and r['split'] in ('all', 'position', 'kind', 'read', 'place')])
    L_ += ['## The earlier 167 of 267', '']
    L_ += table(['Source', 'Place', 'Reads', 'Gold in', 'Share', '95%'], [[r['source'], r['place'], r.get('reads', '-'), r.get('gold_in', '-'), fmt(r.get('share')), ('%s to %s' % (fmt(r['lo']), fmt(r['hi']))) if 'lo' in r else '-'] for r in early])
    L_ += ['## Priors that a search can set before the pick', '']
    L_ += table(['Read', 'Set', 'Policy', 'Picks', 'Parameter', 'Saved per pick, 95%'], [[r['read'], r['set'], r['policy'], r['picks'], r['parameter'], ivl(r, 'saved', 'lo', 'hi')] for r in policy])
    L_ += ['## Rows walked against the census', '']
    L_ += table(['Group', 'Census rows', 'Walked', 'Share', 'Mean bits, census', 'Mean bits, walked'], [[r['group'], r['census_rows'], r['walked_rows'], fmt(r['share_walked']), fmt(r['census_bits']), fmt(r['walked_bits'])] for r in cov])
    L_ += ['## Cells that differ from the pool, not thin', '', 'All rows are in signal-cells.tsv: %d rows. Pool: feasible %s; unread %s.' % (len(sig), json.dumps({k: round(v['saved'], 3) for k, v in pool1.items()}), json.dumps({k: round(v['saved'], 3) for k, v in pool2.items()})), '']
    for name, rows, s in (('feasible `any`', rows1, 'any'), ('unread `unread_before`', rows2, 'unread_before')):
        t = [r for r in rows if r['set'] == s and r.get('thin') == 0 and not r['rollup'] and r['split'] != 'all']
        d = [r for r in t if r.get('saved_differs_from_pool')]
        L_ += ['- %s: %d cells that are not thin and not rollups, so about %.0f outside the interval by chance. %d have the pooled saving outside, %d of them known at the pick.' % (name, len(t), .05 * len(t), len(d), sum(r['known_at_pick'] for r in d))]
    above = [r for r in rows2 if r.get('net_lo') is not None and r['net_lo'] > 0 and r.get('thin') == 0]
    L_ += ['- Unread read, cells that are not thin with the net saving\'s interval above 0: %d. %s' % (len(above), '; '.join('%s %s: %s' % (r['set'], r['cell'], ivl(r, 'net_per_derived', 'net_lo', 'net_hi')) for r in above)), '']
    L_ += table(['Read', 'Set', 'Cell', 'Known at pick', 'Picks', 'Tasks', 'Gold in', 'Saved', 'Total bits', 'Saved differs', 'Share differs'],
                [[r['read'], r['set'], '%s: %s' % (r['split'], r['cell']), r['known_at_pick'], r['picks'], r['tasks'], '%.3f (%.3f to %.3f)' % (r['share_gold_in'], r['share_lo'], r['share_hi']), ivl(r), '%.1f' % r['saved_total_bits'], r['saved_differs_from_pool'], r['share_differs_from_pool']] for r in sig if r['set'] in ('any', 'unread_before') and not r['rollup']])
    with open(out + 'partial.md', 'w') as f:
        f.write('\n'.join(L_) + '\n')
    say('wrote partial.md')


def main():
    global R1, R2, RF, L
    ap = argparse.ArgumentParser()
    ap.add_argument('held')
    ap.add_argument('--test', default=None)
    ap.add_argument('--unread-dir', default=UNREAD)
    ap.add_argument('--earlier-dir', default=EARLIER)
    ap.add_argument('--out', default=HERE)
    ap.add_argument('--commit', default=None)
    a = ap.parse_args()
    held = os.path.abspath(a.held)
    fdir = os.path.dirname(held) + '/'
    test = a.test or fdir + 'feasible-walk-test.jsonl'
    out = os.path.join(a.out, '')
    os.makedirs(out, exist_ok=True)
    sys.path[:0] = [fdir, a.unread_dir]
    import features_feasible_read as R1
    import features_unread_fit as RF
    import features_unread_lib as L
    import features_unread_read as R2
    say('modules read')
    chk = Checks()

    # Read 1
    held_tasks = set(L.held_tasks())
    p_held, f_held = R1.load(held)
    p_test, f_test = R1.load(test)
    say('held pick rows %d, test pick rows %d' % (len(p_held), len(p_test)))
    assert not {d['task'] for d in p_test.values()} & held_tasks
    assert {d['task'] for d in p_held.values()} <= held_tasks
    P = [d for d in p_held.values() if R1.valid(d, f_held) and R1.gold_alive(d)]
    T = [d for d in p_test.values() if R1.valid(d, f_test) and R1.gold_alive(d)]
    a_test = Arrays1(T)
    say('test arrays')
    a_held = Arrays1(P)
    say('held arrays')
    lam = {v: float((~a_test.inside[v]).mean()) for v in R1.VARIANTS}
    ref = json.load(open(fdir + 'feasible-read.json'))
    chk.add('feasible', 'test rows', 'test picks', a_test.n, ref['escape']['test_picks'])
    for v in R1.VARIANTS:
        chk.rounded('feasible', 'test rows', 'escape weight, %s' % v, lam[v], ref['escape']['weight'][v], 4)
    # The reader's file comes from the rows that existed when it ran: the same count of pick rows, from the start of the file.
    # Its last form may have had no form row yet, and the reader counts the picks of such a form as valid.
    k = ref['picks_any_context']
    pre, fpre, last = {}, {}, None
    for line in open(held):
        if not line.endswith('\n'):
            continue
        d = json.loads(line)
        if d['rec'] == 'form':
            if len(pre) < k:
                fpre[d['task'], d['line']] = d
            else:
                last = d
                break
        elif len(pre) >= k:
            break
        else:
            pre[d['task'], d['line'], d['ord'], d['phase']] = d
    use = [d for d in pre.values() if R1.valid(d, fpre) and R1.gold_alive(d)]
    if len(use) != ref['picks'] and last is not None:
        fpre[last['task'], last['line']] = last
        use = [d for d in pre.values() if R1.valid(d, fpre) and R1.gold_alive(d)]
    pooled1(Arrays1(use), lam, chk, 'first %d pick rows, as feasible-read.json' % k, ref)
    say('reader check done')
    bad = [d for d in p_held.values() if not (R1.valid(d, f_held) and R1.gold_alive(d))]
    dead = [d for d in bad if R1.valid(d, f_held) and d['gold_idx'] is not None]
    skipped = dict(attrs=attrs1(dead), n=len(dead)) if dead else dict(attrs={k_: np.array([]) for k_ in VALUES1}, n=0)
    rows1, pool1 = read1(a_held, a_test, lam, skipped)
    say('feasible cells', len(rows1))
    keys1 = (('picks', lambda r: r['picks'], 0), ('gold in', lambda r: r['gold_in'], 0), ('bits paid', lambda r: r['picks'] * r['bits_paid_all'], 1e-6), ('saved', lambda r: r['saved_total_bits'], 1e-6))
    tot1 = {v: {'picks': a_held.n, 'gold in': int(a_held.inside[v].sum()), 'bits paid': float(a_held.bits.sum()), 'saved': pool1[v]['total']} for v in R1.VARIANTS}
    partitions(rows1, keys1, chk, 'feasible', tot1)
    cov = coverage(p_held)
    say('census coverage done')
    write_tsv('feasible-cells.tsv', COLS1, rows1, out)
    write_tsv('feasible-coverage.tsv', ['group', 'census_rows', 'walked_rows', 'share_walked', 'census_bits', 'walked_bits'], cov, out)
    policy = []
    for v in R1.VARIANTS:
        for name, dim in (('one test weight', None), ('test weight by position over the form', 'position'), ('test weight by position in the body', 'position_in_body')):
            r = dict(read='feasible', set=v, policy='gold-alive picks, ' + name, picks=a_held.n, tasks=len(set(a_held.task)), parameter=round(lam[v], 4) if dim is None else 'by position')
            r.update(zip(('saved', 'lo', 'hi'), boot(a_held.task, a_held.bits - a_held.soft(v, lam[v])) if dim is None else by_position(a_held, a_test, dim, v, lam)))
            policy.append(r)
    policy += coin_policy(a_held, [d for d in dead if d['gold_idx'] is not None])

    # Read 2
    d2 = os.path.join(a.unread_dir, '')
    all_rows, keep = load_table(d2 + 'per-pick-unread.tsv')
    summary = json.load(open(d2 + 'summary.json'))
    fit = json.load(open(d2 + 'fit.json'))
    w_global = {s: fit['w']['test'][s + ':options']['w'] for s in SETS2}
    aa = Arrays2(keep)
    say('unread table', aa.n)
    b = ArraysAll(load_all_picks(d2))
    say('all relation picks', b.n)
    fit_rows = [json.loads(x) for x in open(d2 + 'fit-picks.jsonl')]
    assert not {r['task'] for r in fit_rows} & held_tasks
    fits = fit_cells(fit_rows, w_global, chk)
    say('w by position', json.dumps({k_: v['w'] for k_, v in fits.items()}))
    rows2, pool2 = read2(aa, b, w_global, fits)
    say('unread cells', len(rows2))
    checks2(aa, b, rows2, pool2, summary, w_global, chk)
    keys2 = (('picks', lambda r: r['picks'], 0), ('gold in', lambda r: r.get('gold_in', 0), 0), ('saved', lambda r: r.get('saved_total_bits', 0.0), 1e-6))
    tot2 = {s: {'picks': aa.n, 'gold in': int(aa.inside[s].sum()), 'saved': pool2[s]['total']} for s in SETS2}
    partitions(rows2, keys2, chk, 'unread', tot2)
    for s in SETS2:
        whole = float((b.bits - mix(b.bits, w_global[s], b.c[s], b.inside[s])).sum())
        for split in {r['split'] for r in rows2 if r['known_at_pick']}:
            sub = [r for r in rows2 if r['set'] == s and r['split'] == split and not r['rollup']]
            chk.add('unread', 'current rows', 'sum over cells, %s, %s, net total' % (s, split), sum(r['net_total_bits'] for r in sub), whole, 1e-6)
    write_tsv('unread-cells.tsv', COLS2, rows2, out)
    poolr = read_pool(keep, chk, summary)
    write_tsv('pool-cells.tsv', COLS_POOL, poolr, out)
    early = earlier(os.path.join(a.earlier_dir, ''), rows2, aa)
    write_tsv('earlier-read-relation.tsv', ['source', 'place', 'reads', 'gold_in', 'share', 'lo', 'hi', 'tasks'], early, out)
    policy += policy_rule(b, w_global, fits)
    policy.append(dict(read='feasible', set='-', policy="join coin: the sum of an atom's picks less the atom's bits, per pick, RULE forms of walk-held-before, every earlier form in scope, all picks of the atom", picks=JOIN_MIX['picks'], tasks=len(set(aa.task)), parameter=COIN, saved=JOIN_MIX['returned']))
    write_tsv('prior-set-before-pick.tsv', ['read', 'set', 'policy', 'picks', 'tasks', 'parameter', 'saved', 'lo', 'hi'], policy, out)
    sig = signal_rows(rows1, rows2)
    write_tsv('signal-cells.tsv', ['read', 'set', 'split', 'cell', 'rollup', 'known_at_pick', 'picks', 'tasks', 'gold_in', 'share_gold_in', 'share_lo', 'share_hi', 'share_differs_from_pool', 'saved_global', 'saved_lo', 'saved_hi', 'saved_total_bits', 'saved_differs_from_pool', 'saved_in_coin', 'coin_lo', 'coin_hi', 'net_per_derived', 'net_lo', 'net_hi', 'net_total_bits'], sig, out)
    write_tsv('totals-check.tsv', ['read', 'scope', 'quantity', 'got', 'reference', 'tolerance', 'equal'], chk.rows, out)
    nbad = sum(not r['equal'] for r in chk.rows)
    for r in chk.rows:
        if not r['equal']:
            say('NOT EQUAL', r)
    left2 = collections.Counter(r['form_kind'] for r in all_rows if not (r['form_valid'] == '1' and r['has_bits'] == '1'))
    info = dict(p1=a_held.n, t1=len(set(a_held.task)), f1=len(set(a_held.form)), rows1=len(p_held), invalid1=sum(not R1.valid(d, f_held) for d in p_held.values()), none1=sum(R1.valid(d, f_held) and d['gold_idx'] is None for d in p_held.values()), dead1=len([d for d in dead if d['gold_idx'] is not None]),
                test_picks=a_test.n, test_tasks=len(set(a_test.task)), lam={k_: round(v, 4) for k_, v in lam.items()}, p2=aa.n, t2=len(set(aa.task)), left2=len(all_rows) - len(keep), left2_kinds=json.dumps(left2), all2=b.n, p3=sum(r['task'] not in L.NOT_IN_RUN for r in keep), fit_picks=sum(len(r['picks']) for r in fit_rows if r['valid'] and 'test' in r['part']))
    write_partial(out, info, rows1, pool1, rows2, pool2, poolr, sig, cov, early, policy, len(chk.rows), nbad)
    mpath = out + 'manifest.json'
    old = json.load(open(mpath)) if os.path.exists(mpath) else {}
    json.dump(dict(name='features-relation-pick-sets-by-cell-heldout37', purpose='The feasible set read and the unread forms read of the relation pick, split by atom position, form kind and relation class, from existing tables',
                   start=old.get('start', datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')), last_run=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), commit=a.commit or old.get('commit'), wheel_engine='none', budget='no search, no walk, no engine call; one process, seconds',
                   task_set='the 37 held tasks of sampler/sampler-worker/held/tasks.txt. Feasible read: the tasks with rows at this run. Pool read: the 35 tasks of search-pool-factored-priors-heldout35-600s-ship7, arm control_search as headline',
                   gold_revision='feasible rows and unread table as their own manifests say: gold-v3-helper-forms-a036da074 base view',
                   command='<runtime python> -B ' + os.path.abspath(__file__) + ' ' + ' '.join(sys.argv[1:]), runtime_python=STUDY + 'ast/run/runtime-kaggle-py313/venv/bin/python',
                   inputs=dict(held=held, test=test, unread=a.unread_dir, earlier=a.earlier_dir, census=CENSUS), counts=info,
                   fit_rule='escape weights from feasible-walk-test.jsonl, w from fit.json and fit-picks.jsonl. No held row fits a number. The script asserts that the test tasks and the fit tasks hold no held task',
                   measures=['picks, tasks, set size quartiles, share with gold inside, bits paid against log2 of the set, bits saved with a 95% task bootstrap, per cell', 'pool: target found, unread size at found, log2 against bits paid, per cell'],
                   records={'feasible-cells.tsv': 'feasible read, one row per set and cell', 'unread-cells.tsv': 'unread read, one row per set and cell', 'pool-cells.tsv': 'pool read, one row per arm and cell', 'signal-cells.tsv': 'cells that are not thin and differ from the pool', 'prior-set-before-pick.tsv': 'pooled savings of priors that use only what is known before the pick', 'earlier-read-relation.tsv': 'the earlier 167 of 267 against this table', 'feasible-coverage.tsv': 'walked rows against the census', 'totals-check.tsv': 'each total against its pooled figure', 'partial.md': 'the tables'}),
              open(mpath + '.new', 'w'), indent=1)
    os.replace(mpath + '.new', mpath)
    say('checks %d, not equal %d' % (len(chk.rows), nbad))


if __name__ == '__main__':
    main()
