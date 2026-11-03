#!/usr/bin/env python
"""Teacher-forced walk of RULE forms that writes one row per relation pick: for each option, whether it has a nonempty join with the labels bound at that pick, on the task's train examples.

  <runtime python> -u features_feasible_walk.py --forms FORMS.json --out ROWS.jsonl [--golds POINTS.json] [--corpus DIR] [--priors-fold TEMPLATE] [--every N] [--scope parents|before] [--budget S] [--limit-forms N]

With --corpus (read at import, before the sampler code) gold comes from that corpus's first program. With --priors-fold a form walks under the priors of its task's fold. --every N keeps each Nth form.

Each pick's row is written and flushed as soon as it exists. A rerun skips the forms that have a 'form' row, and skips the probes of each pick that has a row. Prints a rate and an ETA.

The feasible set (see partial.md for the same text):

- Bound labels: the labels of the clause's prefix at the pick. Their values are the rows of the prefix's table, read from the engine (step_tables) on each train example.
- A map of relation R: one column of R, or one field of a record column, set to one bound label, as the decoder admits it. So the decoder decides which label may stand at which column. Other columns stay unnamed, and a column that R must have named takes a label or 0.
- R is feasible on an example where some map gives at least one row of the prefix joined with R. A map of two labels gives a subset of the rows of a map of one of them, so one label per map is enough.
- At a first atom of a clause, no label is bound, and R stands alone: it is feasible where its own atom gives a row.
- Inside an OR branch the engine gives no table, so the walk reads the flat clause that the branch stands for: the atoms before the OR and the branch's atoms so far, with the labels renumbered. A label that an earlier branch made and this branch has not named is not bound. The first atom of a branch of an OR at the body's start stands alone.
- A relation with no column that a bound label can stand at (dead by join) is out of the set at a later atom.
- NOT, relation pick after it: a map must both remove a row and keep a row, on the same example. Maps of up to MAX_NOT labels are read, since a map of more labels removes fewer rows.
- Comparison: an operand pair that the decoder admits must both remove a row and keep a row, or be `(= *X Y)`, which makes a label and keeps every row. The rows with keep alone are written too.
- The NOT token itself is one option, in the set where the prefix has a row.
- An option that gives no row and a stop, a fault or a capped search is undetermined and stays in the set, with `und` set.

Row of a pick: `o` has, for each option, [name, kind code, weight, dead by join, own earlier atom, u, a, eu, ea, und, tables, ms].
u: mask of train examples where some map gives a row (NOT and comparison: keeps a row). a: 1 where one map gives a row on every example with a prefix row.
eu, ea: the same for removes a row and keeps a row. tables: step_tables calls for that option. ms: wall ms of the option's probe, one thread.
"""
import argparse
import collections
import itertools
import json
import os
import pickle
import sys
import time

import features_walk_env  # noqa: F401  (sets the environment first)
import live  # noqa: E402
import or_q  # noqa: E402
import sample2_col as S  # noqa: E402
import sampler_paths as P  # noqa: E402
import search_gold as G  # noqa: E402
import live_rows  # noqa: E402

M = live.M
arclog = live.arclog
MAX_NOT = 3  # labels in a map under NOT
TABLE_CAP = 120  # step_tables calls for one option; past this the option is undetermined unless a row was found
KIND = {'lib relation': 'l', 'relation macro': 'm', 'fact relation': 'f', 'relation': 'd', 'NOT': 'N', 'CMP': 'C'}
CTX = {}
DONE = set()
OUT = [None]
CMP_NAMES = {}


def read_counts(ct):
    """{train example: rows}, {train example: why its count is not complete}, across the entries of the one table at the clause in progress."""
    T = ct.tables
    if len(T['form']) != 1:
        return None, 'step gave %d tables' % len(T['form'])
    if T['fault'][0]:
        return None, 'table fault'
    base = ct.base_tables or 0
    et, ex, ei = M.col(ct, 'entries', 'table'), M.col(ct, 'entries', 'example_kind'), M.col(ct, 'entries', 'example_index')
    ek, er = M.col(ct, 'entries', 'kind'), M.col(ct, 'entries', 'rows')
    stop, vstop, efault = ct.entries['stop_bound'], ct.entries['value_stop_bound'], ct.entries['fault']
    got, bad = {}, {}
    for e in range(len(et)):
        if et[e] - base != 0 or ex[e] != 1:
            continue
        i = int(ei[e])
        got[i] = got.get(i, 0) + int(er[e])
        if ek[e] != 0 or stop[e] or vstop[e] or efault[e]:
            bad[i] = 'kind %d stop %s value stop %s fault %s' % (ek[e], stop[e], vstop[e], str(efault[e])[:60])
    return got, bad


def counts_at(fr, dec, before):
    """(rows by example, incomplete by example, error) of the clause in progress at dec, which is at an atom's end or an atom's start."""
    try:
        f = dec.fork()
        p = fr.probe(f)
        if p is None:
            return None, None, 'no probe token'
        f.step(p)
        ct = arclog.step_tables(f, *live.TABLES, True, before)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as e:  # noqa: BLE001
        return None, None, '%s: %s' % (type(e).__name__, str(e)[:80])
    got, bad = read_counts(ct)
    if got is None:
        return None, None, bad
    return got, bad, None


class Probe:
    """The maps of one option at one pick, read until one map answers on every example with a prefix row."""

    def __init__(self, fr, n0, pre, before):
        self.fr, self.n0, self.before = fr, n0, before
        self.pre = pre or {}
        self.goal = 0
        for e, c in self.pre.items():
            if c:
                self.goal |= 1 << e
        self.u = self.eu = self.a = self.ea = self.und = self.tables = self.r = 0

    def read(self, node):
        """Reads one map's table. Returns whether the option needs no further map."""
        if self.tables >= TABLE_CAP:
            self.und = 1
            return True
        self.tables += 1
        got, bad, err = counts_at(self.fr, node.dec, self.before)
        CTX['errs'][(err or 'ok')[:40]] += 1
        if err is not None:
            self.und = 1
            return False
        keep = rem = 0
        for e, c in got.items():
            if e in bad and c == 0:
                self.und = 1
                continue
            if c:
                keep |= 1 << e
            if e not in bad and c < self.pre.get(e, 0):
                rem |= 1 << e
        self.u |= keep
        self.r |= rem
        self.eu |= keep & rem
        if self.goal and keep & self.goal == self.goal:
            self.a = 1
        if self.goal and keep & rem & self.goal == self.goal:
            self.ea = 1
        return False

    def result(self):
        return self.u, self.a, self.eu, self.ea, self.und, self.tables


def is_label(fr, t):
    return fr.KIND[t] == 'label' and t != M.STAR and t != M.ZERO


def close_record(fr, y, depth=0):
    """The node after the record site at y closes: the site's END, or a fresh binder at the next field that it must name."""
    c = fr.child(y, M.END)
    if c is not None or depth > 6:
        return c
    for col in fr.admitted(y):
        if col == M.END:
            continue
        v = fr.child(y, col)
        z = None if v is None else fr.child(v, M.STAR)
        if z is not None:
            return close_record(fr, z, depth + 1)
    return None


def complete(fr, x, depth=0):
    """The atoms that end from x. A column that takes a fresh binder stays unnamed; a column that the atom must name and that takes no fresh binder takes a label or 0."""
    if fr.is_leaf(x):
        yield x
        return
    if depth > 6:
        return
    free = []
    for col in fr.admitted(x):
        v = fr.child(x, col)
        if v is None:
            continue
        vals = list(fr.admitted(v))
        if M.STAR in vals:
            free.append(v)
            continue
        for t in vals:
            if t == M.ZERO or is_label(fr, t):
                y = fr.child(v, t)
                if y is not None:
                    yield from complete(fr, y, depth + 1)
    for v in free:  # no column was forced: some free column must be named
        y = fr.child(v, M.STAR)
        if y is not None:
            yield from complete(fr, y, depth + 1)


def one_label_maps(fr, c):
    """Nodes after one bound label stands at one column or record field of the atom at c."""
    for col in fr.admitted(c):
        v = fr.child(c, col)
        if v is None:
            continue
        for t in fr.admitted(v):
            if is_label(fr, t):
                x = fr.child(v, t)
                if x is not None:
                    yield x
            elif fr.KIND[t] == 'column':
                f = fr.child(v, t)
                if f is None:
                    continue
                for u in fr.admitted(f):
                    if is_label(fr, u):
                        y = fr.child(f, u)
                        z = None if y is None else close_record(fr, y)
                        if z is not None:
                            yield z


def join_maps(fr, c):
    for x in one_label_maps(fr, c):
        yield from complete(fr, x)


def not_maps(fr, c, size):
    """Atoms under NOT of `size` labels. Under NOT a column takes a label or 0, and an unnamed column reads any value."""
    if size == 1:
        yield from join_maps(fr, c)
        return
    for x in one_label_maps(fr, c):
        yield from not_maps(fr, x, size - 1)


def probe_relation(fr, n0, o, k, pre, before):
    p = Probe(fr, n0, pre, before)
    c = fr.child(n0, o)
    if c is None:
        return p.result()
    if k == 1 and n0.phase == 'root':  # a first atom stands alone
        seen = False
        for x in itertools.islice(complete(fr, c), TABLE_CAP):
            seen = True
            p.read(x)
            if p.u:
                break
        if not seen:
            p.und = 1
        return p.result()
    if n0.phase == 'root2':
        for size in range(1, MAX_NOT + 1):
            for x in not_maps(fr, c, size):
                if p.read(x) or p.ea:
                    return p.result()
            if not p.r:
                break  # a map of more labels removes fewer rows, so where a map of this size removes none, a larger one removes none
        return p.result()
    for x in join_maps(fr, c):
        if p.read(x) or p.a:
            break
    return p.result()


def probe_cmp(fr, n0, o, pre, before):
    p = Probe(fr, n0, pre, before)
    c = fr.child(n0, o)
    if c is None:
        return p.result()
    for a in fr.admitted(c):
        v = fr.child(c, a)
        if v is None:
            continue
        for b in fr.admitted(v):
            x = fr.child(v, b)
            if x is None:
                continue
            if p.read(x) or p.ea:
                return p.result()
            if a == M.STAR and p.u:  # (= *X Y) makes a label and keeps every row
                p.eu |= p.u
                p.ea = p.a
                if p.ea:
                    return p.result()
    return p.result()


class Flat:
    """The flat clause of a pick inside an OR: `toks` are the tokens to step from the body's start, `ren` takes a label number of the walk to its number in the flat clause, and `labs` counts the flat clause's labels."""

    def __init__(self, fr, V, key, nlab):
        self.fr = fr
        self.tok_label = {t: i for i, t in fr.label_tok.items()}
        all_tok = V.id('ALL')
        stack, prev = [], None
        for i, t in enumerate(key):
            if t == M.OR:
                stack.append(['OR', i, i])
            elif t == live.ALSO_TOK:
                stack[-1][2] = i
            elif t == M.END:
                stack.pop()
            elif t == all_tok:
                stack += [['ALL', i, i], ['ALL', i, i]]
            elif prev is not None and V.kind(t) == 'column' and V.kind(prev) == 'column':
                stack.append(['REC', i, i])
            prev = t
        self.in_all = any(x[0] == 'ALL' for x in stack)
        self.open = [x for x in stack if x[0] == 'OR']
        cut = set()
        for _k, a, b in self.open:
            cut.update(range(a, b + 1))
        self.orig, self.labs, self.ren, self.toks = nlab, nlab, {i: i for i in range(nlab)}, []
        for i, t in enumerate(key):
            if i in cut:
                self.orig += t == M.STAR
            else:
                self.toks.append(self.map(t))

    def map(self, t):
        if t == M.STAR:
            self.ren[self.orig] = self.labs
            self.orig += 1
            self.labs += 1
            return t
        i = self.tok_label.get(t)
        if i is None or t == M.ZERO:
            return t
        if i in self.ren:
            return self.fr.label_tok[self.ren[i]]
        self.ren[i] = self.labs  # a label that an earlier branch made: this branch names it first here
        self.labs += 1
        return M.STAR


def gold_atom(fr, n0, toks, before, flat=None):
    """Gold's atom from the pick: the labels it reads, its fresh binders, its 0s, and its rows by example."""
    node, i, reads, fresh, zero = n0, 0, 0, 0, 0
    while i < len(toks):
        t = toks[i]
        if node.phase == 'done' or (node.phase == 'cols' and fr.KIND[t] != 'column'):
            break
        ph = node.phase
        if flat is not None:
            t = flat.map(t)
        c = fr.child(node, t)
        if c is None:
            return dict(err='gold token refused at %d' % i)
        if ph in ('val', 'fval', 'op'):
            reads += is_label(fr, t)
            fresh += t == M.STAR
            zero += t == M.ZERO
        node = c
        i += 1
    got, bad, err = counts_at(fr, node.dec, before)
    return dict(reads=reads, fresh=fresh, zero=zero, rows=got, bad=bad, err=err)


class Instr(or_q.GuidedDrawer):
    def pick(self, opts, weights):
        f = sys._getframe(1)
        while f is not None and f.f_code.co_name != 'atom':
            f = f.f_back
        L = f.f_locals
        n = L['n']
        rec = None
        if n.phase in ('root', 'root2') and self.force:
            if n.phase == 'root':
                CTX['ord'] = CTX.get('ord', 0) + 1
            pk = (CTX['task'], CTX['line'], CTX['ord'], n.phase)
            CTX['pending'].append(pk)
            if pk not in DONE:
                rec = self.snapshot(n, L, opts, weights)
        o, q = super().pick(opts, weights)
        if rec is not None:
            rec['q_bits'] = round(or_q.bits(q), 4)
            OUT[0].write(json.dumps(rec, separators=(',', ':')) + '\n')
            OUT[0].flush()
            CTX['written'] += 1
        return o, q

    def snapshot(self, n, L, opts, weights):
        t0 = time.perf_counter()
        fr, V = self.fr, self.V
        k, key, scope = L['k'], L['key'], tuple(L['scope_types'])
        gold = self.force[0]
        before = self.pg.before
        fl = Flat(fr, V, key, CTX.get('nlab', 0))
        dec, labs, flat, hidden, flat_err = n.dec, n.labs, None, fr.hidden, None
        if fl.in_all:
            flat_err = 'inside ALL'
        elif fl.open:
            flat = fl
            try:
                dec = CTX['body_dec'].fork()
                for t in fl.toks:
                    dec.step(t)
                if n.phase == 'root2':
                    dec.step(M.NOT)
                labs = fl.labs
            except arclog.Refusal as e:
                flat_err = 'flat refused: %s' % str(e)[:60]
        if n.phase == 'root':
            if flat_err:
                CTX['pre'] = dict(rows=None, bad=None, err=flat_err)
            else:
                got, bad, err = counts_at(fr, dec, before)
                CTX['pre'] = dict(rows=got, bad=bad, err=err)
        pre = CTX['pre']
        jset = None
        if k > 1:
            jset = L.get('jset')
            if jset is None:
                jset = self.joinable(n, opts, scope, key)
        n0 = S.FNode((), dec, n.phase, -1, 0, '', n.neg, labs, None)
        gk = fr.KIND[gold] if gold not in M.CMP and gold != M.NOT else ('NOT' if gold == M.NOT else 'CMP')
        own = gold in key and gk in ('lib relation', 'relation macro', 'fact relation', 'relation')
        rows = pre['rows']
        row = []
        if flat is not None:
            fr.hidden = frozenset(fr.label_tok[fl.ren[fl.tok_label[t]]] for t in hidden if fl.tok_label[t] in fl.ren)
        for o, w in zip(opts, weights):
            kd = fr.KIND[o] if o not in M.CMP and o != M.NOT else ('NOT' if o == M.NOT else 'CMP')
            isrel = kd not in ('NOT', 'CMP')
            dj = bool(isrel and jset is not None and o not in jset)
            t1 = time.perf_counter()
            if o == M.NOT or dj:
                res = 0, 0, 0, 0, 0, 0
            elif rows is None:
                res = 0, 0, 0, 0, 1, 0
            elif not isrel:
                res = probe_cmp(fr, n0, o, rows, before)
            else:
                res = probe_relation(fr, n0, o, k, rows, before)
            row.append([V.name(o), KIND[kd], round(w, 6), int(dj), int(o in key)] + list(res) + [round((time.perf_counter() - t1) * 1e3, 2)])
        ga = gold_atom(fr, n0, list(itertools.islice(self.force, 64)), before, flat) if rows is not None else dict(err='no prefix table')
        fr.hidden = hidden
        return dict(rec='pick', task=CTX['task'], line=CTX['line'], ord=CTX['ord'], phase=n.phase, k=k, ctx=self.rng.ctx, labs=labs, flat=flat is not None, scope=list(scope), gold=V.name(gold), gold_kind=gk, own=own,
                    gold_idx=opts.index(gold) if gold in opts else None, pre=pre, gold_atom=ga, ms=round((time.perf_counter() - t0) * 1e3, 1), o=row)


Orig = or_q.GuidedRun


class RunX(Orig):
    drawer_class = Instr

    def drawer(self, pg, kind, dec, place=None, prior=None):
        dr = super().drawer(pg, kind, dec, place, prior)
        dr.pg = pg
        return dr

    def body(self, pg, dr, dec, kind, nlab, *a, **kw):
        if 'body_dec' not in CTX:
            CTX.update(body_dec=dec, nlab=nlab)
        return super().body(pg, dr, dec, kind, nlab, *a, **kw)


or_q.GuidedRun = RunX


def gold_lines(task, golds):
    if golds is not None:
        return [x for x in golds[task].splitlines() if x.strip()]
    import gzip
    with gzip.open(S.CORPUS + task + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--forms', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--golds', default='')
    ap.add_argument('--budget', type=float, default=1e9)
    ap.add_argument('--limit-forms', type=int, default=0)
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--corpus', default='')
    ap.add_argument('--priors-fold', default='')
    ap.add_argument('--scope', default='parents', choices=('parents', 'before'))
    a = ap.parse_args()
    forms = json.load(open(a.forms))[::a.every]
    done_forms = set()
    if os.path.exists(a.out):
        for line in open(a.out):
            if not line.endswith('\n'):
                continue
            d = json.loads(line)
            if d['rec'] == 'form':
                done_forms.add((d['task'], d['line']))
            else:
                DONE.add((d['task'], d['line'], d['ord'], d['phase']))
    todo = [r for r in forms if (r[4], r[5]) not in done_forms]
    if a.limit_forms:
        todo = todo[:a.limit_forms]
    print('%d forms, %d done, %d to do, %d picks with rows' % (len(forms), len(done_forms), len(todo), len(DONE)), flush=True)
    golds = {x['task']: x['gold_sexp'] for x in json.load(open(a.golds))} if a.golds else None
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    pri = {}
    t0 = time.time()
    picks = 0
    OUT[0] = open(a.out, 'a')
    for c, row in enumerate(todo, 1):
        task, line = row[4], row[5]
        if time.time() - t0 > a.budget:
            print('budget ends the run after %d forms' % (c - 1), flush=True)
            break
        if a.priors_fold:
            fold = live_rows.fold_of(task, live_rows.FOLDS)
            if fold not in pri:
                with open(a.priors_fold.format(fold), 'rb') as f:
                    pri[fold] = pickle.load(f)
            sampler.pri = pri[fold]
        lines = gold_lines(task, golds)
        target = lines[line]
        keep_lines = live_rows.parents(lines, line) if a.scope == 'parents' else list(range(line))
        G.gold_of = lambda t, c_, p, ls=[lines[j] for j in keep_lines] + [target]: (t, ls)
        CTX.clear()
        CTX.update(task=task, line=line, errs=collections.Counter(), pending=[], written=0)
        t1 = time.time()
        rows = []
        try:
            q = or_q.one(sampler, task, 'RULE', [len(keep_lines), 0], 'RULE', rows)
        except Exception as e:  # noqa: BLE001
            q = dict(error=repr(e)[:200])
        picks += CTX['written']
        OUT[0].write(json.dumps(dict(rec='form', task=task, line=line, orf='(OR ' in target, natoms=len(q.get('atoms', [])), total=q.get('total'), bad=q.get('bad'), dead=q.get('dead'), error=q.get('error'), picks=len(CTX['pending']),
                                     secs=round(time.time() - t1, 3), errs=dict(CTX['errs'])), separators=(',', ':')) + '\n')
        OUT[0].flush()
        el = time.time() - t0
        print('[%d/%d %.0fs %.2f forms/s %.2f picks/s eta %.0fs] %s %s %.1fs' % (c, len(todo), el, c / el, picks / el, el / c * (len(todo) - c), task, line, time.time() - t1), flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
