#!/usr/bin/env python
"""Rejection attribution for a plain whole-clause sampler at RULE points of dev tasks.

P is a production-count prior from gold-shapes.jsonl (held out by task), run under the decoder's mask. Each draw
records its clause, its stream, the static-prune matches on it, its body table X (labels, types, rows per entry),
and whether X is empty at every entry. The feature study's rules run later on the saved X.

  scripts/run_heavy.py --cpus N --need now <runtime python> -u sample.py --out DIR [--points 50] [--draws 200]
      [--jobs N] [--seconds 60]

Writes DIR/draws.jsonl.gz (one row per draw), DIR/points.jsonl (one row per point), and prints a line per point.
A point already in DIR/points.jsonl is skipped, so a rerun extends a run.
"""
import argparse
import collections
import concurrent.futures as cf
import functools
import gzip
import hashlib
import json
import math
import os
import random
import re
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths as P  # noqa: E402
sys.path.insert(0, P.STUDY + '/frontier')
import measure as M  # noqa: E402

arclog = M.arclog
DATA = P.DATA + '/'
SHAPES = os.environ.get('SHAPES', P.SAMPLER_DATA + '/gold-shapes.jsonl')
SPLITS = DATA + 'feat-exp/stream/splits.json'
CORPUS = os.environ.get('SAMPLER_CORPUS', P.SAMPLER_DATA + '/corpus-v3mix/')  # the AST corpus: <task>/pairs.jsonl.gz (gen-v3 in slot order; corpus-v11 for a3325580)
GOLD_APPROXIMATED = os.environ.get('GOLD_APPROXIMATED', '') == '1'  # 1: the fits read a stem whose first row has approximated: true (a gold solver with @approximated); default: they leave it out


@functools.lru_cache(maxsize=None)
def stem_first_row(t):
    """The first row of task t's stem in the corpus, or None where the corpus has no pairs for t."""
    p = CORPUS + t + '/pairs.jsonl.gz'
    if not os.path.exists(p):
        return None
    with gzip.open(p, 'rt') as f:
        return json.loads(f.readline())


def left_out(t):
    """True where the fits leave task t out: its stem's first row has approximated: true, and GOLD_APPROXIMATED is not 1."""
    r = stem_first_row(t)
    return bool(r and r.get('approximated') and not GOLD_APPROXIMATED)


def first_row(t):
    """The first row of task t's stem for a fit, or None where the corpus has no pairs for t or the fits leave t out (left_out)."""
    return None if left_out(t) else stem_first_row(t)
TASKS = P.REPO + '/data/tasks/'
OPS = {'=': 'cmp:Eq', '!=': 'cmp:Ne', '<': 'cmp:Lt', '<=': 'cmp:Le', '>': 'cmp:Gt', '>=': 'cmp:Ge'}
MAX_ATOMS = 8
ALPHA = 0.5
JOIN_BOOST = float(os.environ.get('JOIN_BOOST', '4'))
ATOM_TRIES = 8
UNJOINED = 0.14


# ---------------------------------------------------------------- prior

class Prior:
    """Production counts of gold RULE atoms, by task, so that a point's task can be held out."""

    def __init__(self):
        self.rel = collections.defaultdict(collections.Counter)      # task -> rel -> atoms
        self.neg = collections.defaultdict(collections.Counter)      # task -> rel -> negated atoms
        self.kind = collections.defaultdict(collections.Counter)     # task -> (rel, kind) -> sites
        self.sites = collections.defaultdict(collections.Counter)    # task -> rel -> sites
        self.nsites = collections.defaultdict(collections.Counter)   # task -> (rel, number of sites) -> atoms
        for line in open(SHAPES):
            r = json.loads(line)
            sh, n, t = r['shape']['none'], r['count'], r['task']
            rel = sh['rel']
            self.rel[t][rel] += n
            self.neg[t][rel] += n * sh['neg']
            self.sites[t][rel] += n * len(sh['args'])
            self.nsites[t][(rel, len(sh['args']))] += n
            for _, k in sh['args']:
                self.kind[t][(rel, k.split(':')[0])] += n
        self.total = {f: sum(getattr(self, f).values(), collections.Counter()) for f in ('rel', 'neg', 'kind', 'sites', 'nsites')}

    def held_out(self, task):
        out = {}
        for f in ('rel', 'neg', 'kind', 'sites', 'nsites'):
            c = collections.Counter(self.total[f])
            c.subtract(getattr(self, f)[task])
            out[f] = c
        return out


def body_hazard(dev):
    """P(END after k atoms | k atoms), from the RULE bodies of the corpus gold of dev tasks, less the tasks that left_out names."""
    lens = collections.Counter()
    for t in dev:
        r = first_row(t)
        if r is None:
            continue
        for e in M_sexprs(r['gold_sexp']):
            if e and e[0] == 'RULE':
                lens[len([a for a in e[2:] if isinstance(a, list)])] += 1
    h = {}
    for k in range(1, MAX_ATOMS + 1):
        at = sum(v for n, v in lens.items() if n >= k)
        h[k] = (lens[k] + 0.5) / (at + 1.0) if at else 1.0
    return h, lens


def M_sexprs(text):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    out, stack = [], []
    for t in toks:
        if t == '(':
            stack.append([])
        elif t == ')':
            e = stack.pop()
            (stack[-1] if stack else out).append(e)
        else:
            (stack[-1] if stack else out).append(t)
    return out


# ---------------------------------------------------------------- one draw

class Drawer:
    def __init__(self, V, counts, hazard, rng):
        self.V, self.c, self.h, self.rng = V, counts, hazard, rng
        self.fr = None

    def frontier(self, dec):
        if self.fr is None:
            self.fr = M.Frontier(dec, self.V)
        else:
            self.fr.root = M.Node((), dec, 'root', -1, 0, '', False)
        return self.fr

    def pick(self, opts, weights):
        tot = sum(weights)
        x = self.rng.random() * tot
        for o, w in zip(opts, weights):
            x -= w
            if x <= 0:
                return o, w / tot
        return opts[-1], weights[-1] / tot

    def rel_name(self, tok):
        name = self.V.name(tok)
        kind = self.fr.KIND[tok]
        if kind == 'relation':
            return 'declared'
        if name in OPS:
            return OPS[name]
        return name

    def atom(self, dec):
        """One atom by descent through the atom grammar; (node, log q, rel, text) or (None, reason)."""
        fr = self.frontier(dec)
        n, lq, rel, joined = fr.root, 0.0, None, False
        c = self.c
        while True:
            opts = fr.options(n)
            leaf = fr.is_leaf(n)
            if n.phase in ('root', 'root2'):
                if not opts:
                    return None, 'no atom start'
                nrel = sum(1 for o in opts if fr.KIND[o] == 'relation') or 1
                ws = []
                for o in opts:
                    if o == M.NOT:
                        ws.append(sum(c['neg'].values()) + ALPHA)
                        continue
                    r = self.rel_name(o)
                    w = c['rel'][r] + ALPHA
                    if r == 'declared':
                        w = (c['rel']['declared'] + sum(v for k, v in c['rel'].items() if k.startswith('port:'))) / nrel + ALPHA
                    if n.phase == 'root2':
                        w = c['neg'][r] + ALPHA
                    ws.append(w)
                o, q = self.pick(opts, ws)
                if o != M.NOT:
                    rel = self.rel_name(o)
            elif n.phase == 'cols':
                k = n.text.count('(:')
                at_k = c['nsites'][(rel, k)] + 0.05
                at_least = sum(v for (r_, j), v in c['nsites'].items() if r_ == rel and j >= k) + 0.1
                stop = min(at_k / at_least, 0.98)
                if leaf and (not opts or self.rng.random() < stop):
                    return (n, lq + math.log(stop if opts else 1.0), rel, fr.render(n), joined), None
                if not opts:
                    return None, 'atom cannot close'
                o, q = self.pick(opts, [(0.5 if leaf else 0.2) ** i for i in range(len(opts))])
                q *= (1 - stop) if leaf else 1.0
            elif n.phase == 'val':
                fresh = c['kind'][(rel, 'fresh')] + ALPHA
                join = c['kind'][(rel, 'join')] + c['kind'][(rel, 'rep')] + ALPHA
                zero = c['kind'][(rel, 'zero')] + ALPHA * 0.1
                labs = [o for o in opts if fr.KIND[o] == 'label']
                ws = []
                for o in opts:
                    if o == M.STAR:
                        ws.append(fresh)
                    elif o == M.ZERO:
                        ws.append(zero)
                    elif o == M.CARET:
                        ws.append(0.0)
                    else:
                        recent = o == max(labs, key=lambda t: int(self.V.name(t)[1:]))
                        boost = JOIN_BOOST if not joined else 1.0
                        ws.append(boost * join * (0.5 if recent else 0.5 / max(len(labs) - 1, 1)) * (2 if len(labs) == 1 else 1))
                if sum(ws) == 0:
                    return None, 'no value'
                o, q = self.pick(opts, ws)
            elif n.phase in ('op', 'done'):
                if n.phase == 'done':
                    return (n, lq, rel, fr.render(n), True), None
                ws = [0.1 if o == M.ZERO else (0.0 if o in (M.STAR, M.CARET) else 1.0) for o in opts]
                if not opts or sum(ws) == 0:
                    return None, 'no operand'
                o, q = self.pick(opts, ws)
            else:
                return None, 'phase %s' % n.phase
            lq += math.log(q)
            if n.phase == 'val' and fr.KIND[o] == 'label':
                joined = True
            ch = fr.child(n, o)
            if ch is None:
                return None, 'refused %s' % self.V.name(o)
            n = ch


def table_summary(tb):
    if tb is None:
        return None
    per = []
    for ex, asg, rows in tb['entries']:
        per.append([ex[0], ex[1], len(rows)])
    return dict(labels=tb['labels'], types=[str(t) for t in tb['types']], entries=per,
                empty_all=all(n == 0 for k, _, n in per if k == 1) if any(k == 1 for k, _, _ in per) else None)


def table_rows(tb, cap=500):
    if tb is None:
        return None
    return [[list(ex), sorted([list(r) for r in rows])[:cap], len(rows),
             {str(k): sorted(map(list, v[0])) for k, v in asg.items()}] for ex, asg, rows in tb['entries']]


def static_prune(prog_text, clause_index, settings):
    try:
        sp = arclog.StudyProgram.from_sexp(prog_text + '\n(OUT (input ^P ^Col))', settings)
        js = json.loads(sp.static_prune_json())
    except Exception as e:  # noqa: BLE001
        return None, '%s: %s' % (type(e).__name__, str(e)[:200])
    return js, None


def n_forms(text):
    return len(M_sexprs(text))


# ---------------------------------------------------------------- one point

SETTINGS = None


def settings():
    global SETTINGS
    if SETTINGS is None:
        SETTINGS = arclog.DecodeSettings(table_work_cap=1048576 * 16, rule_tests=False)
    return SETTINGS


def run_point(spec, draws, seconds, counts, hazard, out_dir):
    task, case, point = spec['task'], spec['case'], spec['point']
    t0 = time.time()
    st = settings()
    sess = arclog.Session(arclog.Task.from_json(open(TASKS + task + '.json').read(), arclog.World.Closed), st)
    gp = arclog.StudyProgram.from_sexp(spec['gold_sexp'], st)
    ids, model, paths = gp.decode_stream()
    V = sess.decoder().vocabulary
    by = M.atoms_of(paths, ids, model, point)
    first = list(by.values())[0][0]
    dec = sess.decoder()
    before = None
    for i in range(first):
        if model[i]:
            dec.step(ids[i])
            before = arclog.step_tables(dec, task, case, True, before)
    prefix_ids = [(ids[i], model[i]) for i in range(first)]
    base_forms = n_forms(dec.program_form())
    END = M.END
    rng = random.Random(M.seed_of(task, case, point))
    dr = Drawer(V, counts, hazard, rng)
    rows = []
    retries = collections.Counter()
    gold_atoms = [[ids[i] for i in idx if model[i]] for idx in by.values()]

    def finish(d, toks, atoms_text, lq, prefix_tables, fail):
        rec = dict(task=task, case=case, point=point, draw=len(rows), gold=d is None and fail == 'gold', atoms=atoms_text,
                   n_atoms=len(atoms_text), logq=lq, fail=fail, prefix=[table_summary(t) for t in prefix_tables])
        return rec

    def evaluate(cur, toks, atoms_text, lq, prefix_tables, is_gold):
        rec = dict(task=task, case=case, point=point, draw=len(rows), gold=is_gold, atoms=atoms_text, n_atoms=len(atoms_text),
                   logq=lq, fail=None)
        tb, err = M.body_table(dr.frontier(cur), task, case, cur, before, [])
        rec['x'] = table_summary(tb)
        rec['x_err'] = err
        rec['x_rows'] = table_rows(tb)
        rec['prefix_empty'] = [(table_summary(t) or {}).get('empty_all') for t in prefix_tables]
        f = cur.fork()
        try:
            f.step(END)
        except arclog.Refusal as e:
            rec['fail'] = 'end refused: %s' % e
            return rec
        rec['clause'] = f.program_form().split('\n')[base_forms] if base_forms < n_forms(f.program_form()) else None
        rec['stream'] = toks + [END]
        js, perr = static_prune(f.program_form(), base_forms, st)
        rec['static'] = js
        rec['static_err'] = perr
        return rec

    # gold first, through the same evaluation
    cur = dec.fork()
    gtoks, gtext, gprefix = [], [], []
    try:
        for a in gold_atoms:
            for x in a:
                cur.step(x)
            gtoks += a
            gtext.append(' '.join(V.name(x) for x in a))
            tb, _ = M.body_table(dr.frontier(cur), task, case, cur, before, [])
            gprefix.append(tb)
        rows.append(evaluate(cur, gtoks, gtext, 0.0, gprefix, True))
    except Exception as e:  # noqa: BLE001
        rows.append(dict(task=task, case=case, point=point, draw=0, gold=True, fail='gold: %s: %s' % (type(e).__name__, e)))

    while len(rows) <= draws and time.time() - t0 < seconds:
        cur = dec.fork()
        toks, text, lq, prefix_tables, fail = [], [], 0.0, [], None
        try:
            for k in range(1, MAX_ATOMS + 2):
                for _ in range(ATOM_TRIES):
                    res, why = dr.atom(cur)
                    if res is None or k == 1 or res[4] or rng.random() < UNJOINED:
                        break
                    retries['unjoined'] += 1
                if res is None:
                    fail = 'atom %d: %s' % (k, why)
                    break
                node, alq, rel, atext, _ = res
                cur = node.dec
                toks += list(node.toks)
                text.append(atext)
                lq += alq
                tb, _ = M.body_table(dr.frontier(cur), task, case, cur, before, [])
                prefix_tables.append(tb)
                mk = cur.admissible()
                can_end = mk[END >> 3] >> (END & 7) & 1
                if can_end and (k >= MAX_ATOMS or rng.random() < hazard.get(k, 1.0)):
                    lq += math.log(hazard.get(k, 1.0)) if k < MAX_ATOMS else 0.0
                    break
                if k >= MAX_ATOMS:
                    fail = 'not safe at %d atoms' % k
                    break
                if can_end:
                    lq += math.log(1 - hazard.get(k, 1.0))
            if fail:
                rows.append(dict(task=task, case=case, point=point, draw=len(rows), gold=False, atoms=text, n_atoms=len(text),
                                 logq=lq, fail=fail, prefix_empty=[t['empty_all'] if (t := table_summary(x)) else None
                                                                   for x in prefix_tables]))
            else:
                rows.append(evaluate(cur, toks, text, lq, prefix_tables, False))
        except Exception as e:  # noqa: BLE001
            rows.append(dict(task=task, case=case, point=point, draw=len(rows), gold=False, atoms=text,
                             fail='error: %s: %s' % (type(e).__name__, str(e)[:200])))
    return dict(task=task, case=case, point=point, seconds=round(time.time() - t0, 2), draws=len(rows) - 1,
                prefix_len=len(prefix_ids), retries=dict(retries)), rows


# ---------------------------------------------------------------- driver

def pick_points(n, dev):
    order = sorted(dev, key=lambda t: hashlib.sha256(t.encode()).hexdigest())
    for t in order:
        p = CORPUS + t + '/pairs.jsonl.gz'
        if not os.path.exists(p):
            continue
        with gzip.open(p, 'rt') as f:
            for line in f:
                r = json.loads(line)
                if r['kind'] == 'Rule':
                    yield dict(task=t, case=r['case'], point=json.loads(r['point']) if isinstance(r['point'], str) else r['point'],
                               gold_sexp=r['gold_sexp'])
                    break
        n -= 1
        if n <= 0:
            return


def worker(args):
    spec, draws, seconds, counts, hazard, out = args
    try:
        return run_point(spec, draws, seconds, counts, hazard, out)
    except Exception as e:  # noqa: BLE001
        return dict(task=spec['task'], case=spec['case'], point=spec['point'], error='%s: %s' % (type(e).__name__, e),
                    trace=traceback.format_exc()[-800:]), []


def summarize(rows):
    c = collections.Counter()
    for r in rows:
        if r.get('gold'):
            continue
        if r.get('fail'):
            c['fail:' + re.sub(r'\d+', 'k', r['fail'].split(':')[0])] += 1
            continue
        if r.get('x') is None:
            c['no_x'] += 1
            continue
        st = r.get('static')
        fired = bool(st and st.get('matches'))
        if r.get('static_err'):
            c['static_err'] += 1
        if r['x'].get('empty_all'):
            c['empty'] += 1
        if fired:
            c['static_prune'] += 1
        if not r['x'].get('empty_all') and not fired:
            c['pass_so_far'] += 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--points', type=int, default=50)
    ap.add_argument('--draws', type=int, default=200)
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    done = set()
    pp = os.path.join(a.out, 'points.jsonl')
    if os.path.exists(pp):
        for line in open(pp):
            r = json.loads(line)
            done.add((r['task'], r['case'], tuple(r['point'])))
    splits = json.load(open(SPLITS))
    dev = [t for t, s in splits.items() if s == 'dev']
    prior = Prior()
    hazard, lens = body_hazard(dev)
    print('hazard', {k: round(v, 2) for k, v in hazard.items()}, 'bodies', sum(lens.values()), flush=True)
    specs = [s for s in pick_points(a.points, dev) if (s['task'], s['case'], tuple(s['point'])) not in done]
    print('points', len(specs), flush=True)
    t0 = time.time()
    total = collections.Counter()
    with cf.ProcessPoolExecutor(a.jobs) as ex, open(pp, 'a') as pf, gzip.open(os.path.join(a.out, 'draws.jsonl.gz'), 'at') as df:
        futs = [ex.submit(worker, (s, a.draws, a.seconds, prior.held_out(s['task']), hazard, a.out)) for s in specs]
        for i, fu in enumerate(cf.as_completed(futs), 1):
            info, rows = fu.result()
            for r in rows:
                df.write(json.dumps(r) + '\n')
            df.flush()
            c = summarize(rows)
            total.update(c)
            info['summary'] = dict(c)
            g = rows[0] if rows else {}
            info['gold'] = dict(fail=g.get('fail'), empty=(g.get('x') or {}).get('empty_all'),
                                static=bool((g.get('static') or {}).get('matches')), static_err=g.get('static_err'))
            pf.write(json.dumps(info) + '\n')
            pf.flush()
            el = time.time() - t0
            print('[%d/%d %.0fs eta %.0fs] %s %s %s %s draws=%s gold=%s %s' % (
                i, len(futs), el, el / i * (len(futs) - i), info['task'], info['case'], info['point'], info.get('error', ''),
                info.get('draws'), info['gold'], dict(c)), flush=True)
    print('TOTAL', dict(total), flush=True)


if __name__ == '__main__':
    main()
