#!/usr/bin/env python
"""Value join probes (item 11): at each relation pick of a RULE form walked in a valid order, whether each option has a nonempty join with the labels bound at the pick, on the task's train examples.

  features_dagc_env.sh 1 features_dagc_probe.py --part held-parents|test-parents [--shard K/N] [--seconds S] [--every N] [--priors-fold TEMPLATE] [--limit N]
  features_dagc_env.sh 1 features_dagc_probe.py --check [--part held-parents] [--keys 30] [--seconds S]     two orders of a form, every pick probed, shared pick keys compared
  features_dagc_env.sh 1 features_dagc_probe.py --report [--part held-parents]                              the gold-in-set shares and the join to the pick table, from the rows that exist

The walk is the walker's (features_dagc_walk.Env, steers `off`): the same points, the same first K valid orders (K from the walker's PARTS), and the same drop rule, so the picks are the pick table's picks. A pick is probed only
where its pick key (task, line_id, form, scope_id, phase, atom, downset id) has no row, so a key reached by several orders is probed once. The definitions of the feasible set are those of feasible-definition.md of the
source record (features-relation-pick-feasible-by-value-join-heldout37): bound labels are the labels of the downset, and their values are the rows of the downset's table (arclog.step_tables at that clause). Inside an OR branch
the flat clause is the atoms of the downset that stand in that branch or outside the OR. The functions that probe (Probe, probe_relation, probe_cmp, Flat, gold_atom and what they call) are copied from features_feasible_walk.py.

Only RULE forms are probed. --every N keeps each Nth RULE point (3 on test-parents, 1 on held-parents), as the source kept 327 forms of the test tasks.
Rows go to probe-held-shardKofN.jsonl and probe-test-shardKofN.jsonl in the record folder (the cat of the shards is probe-held.jsonl and probe-test.jsonl), flushed per pick; a `form` row ends each walk. A shard holds whole tasks.
A rerun skips the walks that have a `form` row and the pick keys that have a row. Prints a rate and an ETA.

Row of a pick: rec `probe`, part, task, line_id, form, scope_id, order_id, phase, atom, downset (sorted atom ids), dsid, k, labs, flat, nscope, gold (the name of gold's option), gold_kind, own, gold_idx, pre, gold_atom, ms, and `o`:
for each option, [name, kind code, weight, dead by join, own earlier atom, u, a, eu, ea, und, tables, ms]. A derived option's name is `D:<content key>.<port>`, as in the pick table's `opts`.
u: mask of train examples where some map gives a row (NOT and comparison: keeps a row). a: 1 where one map gives a row on every example with a prefix row. eu, ea: the same for removes a row and keeps a row.
und: the option gives no row and a stop, a fault or a capped search. tables: step_tables calls for that option. ms: wall ms of the option's probe, one thread.
"""
import argparse
import collections
import glob
import io
import itertools
import json
import os
import sys
import time

import zstandard

import features_dagc_lib as L
import features_dagc_walk as W

MAX_NOT = 3  # labels in a map under NOT
CHECK_WALK_SECONDS = 6.0  # --check: probing stops in a walk past this time
TABLE_CAP = 120  # step_tables calls for one option; past this the option is undetermined unless a row was found
KIND = {'lib relation': 'l', 'relation macro': 'm', 'fact relation': 'f', 'relation': 'd', 'NOT': 'N', 'CMP': 'C'}
NAME, KINDC, WGT, DEAD, OWN, U, A, EU, EA, UND, TABLES, MS = range(12)
live = M = arclog = S = None
ENV = None
PC = {}  # the probe context of the walk in progress: body_dec, nlab
PR = {}  # the point in progress: on, task, line_id, form, scope_id, order_id, leaves, part, out, done, check


def init_modules():
    global live, M, arclog, S
    import live as live_
    import sample2_col as S_
    live, M, arclog, S = live_, live_.M, live_.arclog, S_


# ---- copied from features_feasible_walk.py (the probes) ----

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
        if PR.get('deadline') and time.time() > PR['deadline']:  # --check only: a row past the walk's time is marked cut and left out of the comparison
            PR['cutoff'] = 1
            self.und = 1
            return True
        self.tables += 1
        got, bad, err = counts_at(self.fr, node.dec, self.before)
        ENV.CTX['errs'][(err or 'ok')[:40]] += 1
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


# ---- the pick key, the drawer and the run ----

def dsid_of(down):
    import features_dag_order as D
    return D.short('|'.join(sorted(down)), 12)


def make_run(env):
    """A run class whose drawer probes at the pick. The drawer is the walker's Instr, so the walk and its pick rows are the walker's."""
    base = env.or_q.GuidedRun
    instr = base.drawer_class
    CTX = env.CTX

    class ProbeInstr(instr):
        def pick(self, opts, weights):
            f = sys._getframe(1)
            while f is not None and f.f_code.co_name != 'atom':
                f = f.f_back
            Lc = f.f_locals
            n = Lc['n']
            if PR.get('on') and n.phase in ('root', 'root2') and self.force and CTX.get('leaf') is not None:
                self.dagc_probe(n, Lc, opts, weights)
            return super().pick(opts, weights)

        def dagc_probe(self, n, Lc, opts, weights):
            t0 = time.perf_counter()
            leaves = PR['leaves']
            leaf = CTX['leaf']
            if leaf >= len(leaves):
                return
            fr, V = self.fr, self.V
            atom = leaves[leaf]
            down = sorted(leaves[:leaf])
            dsid = dsid_of(down)
            pkey = (PR['task'], PR['line_id'], PR['form'], PR['scope_id'], n.phase, atom, dsid)
            k, key, scope = Lc['k'], Lc['key'], tuple(Lc['scope_types'])
            before = self.pg.before
            PR['cutoff'] = 0
            fl = Flat(fr, V, key, PC.get('nlab', 0))
            dec, labs, flat, hidden, flat_err = n.dec, n.labs, None, fr.hidden, None
            if fl.in_all:
                flat_err = 'inside ALL'
            elif fl.open:
                flat = fl
                try:
                    dec = PC['body_dec'].fork()
                    for t in fl.toks:
                        dec.step(t)
                    if n.phase == 'root2':
                        dec.step(M.NOT)
                    labs = fl.labs
                except arclog.Refusal as e:
                    flat_err = 'flat refused: %s' % str(e)[:60]
            if n.phase == 'root':  # the prefix table is read at every root pick, since the root2 pick after it reads it too
                if flat_err:
                    PC['pre'] = dict(rows=None, bad=None, err=flat_err)
                else:
                    got, bad, err = counts_at(fr, dec, before)
                    PC['pre'] = dict(rows=got, bad=bad, err=err)
            if pkey in PR['done']:
                PR['skipped'] += 1
                return
            pre = PC.get('pre')
            if pre is None:
                return
            jset = None
            if k > 1:
                jset = Lc.get('jset')
                if jset is None:
                    jset = self.joinable(n, opts, scope, key)
            n0 = S.FNode((), dec, n.phase, -1, 0, '', n.neg, labs, None)
            gold = self.force[0]
            gk = fr.KIND[gold] if gold not in M.CMP and gold != M.NOT else ('NOT' if gold == M.NOT else 'CMP')
            own = gold in key and gk in ('lib relation', 'relation macro', 'fact relation', 'relation')
            rows = pre['rows']
            row = []
            if flat is not None:
                fr.hidden = frozenset(fr.label_tok[fl.ren[fl.tok_label[t]]] for t in hidden if fl.tok_label[t] in fl.ren)
            canon = CTX['canon']
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
                name = canon(self.prog_names, V.name(o)) if kd == 'relation' else V.name(o)
                row.append([name, KIND[kd], round(w, 6), int(dj), int(o in key)] + list(res) + [round((time.perf_counter() - t1) * 1e3, 2)])
            ga = gold_atom(fr, n0, list(itertools.islice(self.force, 64)), before, flat) if rows is not None else dict(err='no prefix table')
            fr.hidden = hidden
            gname = canon(self.prog_names, V.name(gold)) if gk == 'relation' else V.name(gold)
            rec = dict(rec='probe', part=PR['part'], task=PR['task'], line_id=PR['line_id'], form=PR['form'], scope_id=PR['scope_id'], order_id=PR['order_id'], phase=n.phase, atom=atom, downset=down, dsid=dsid, k=k, labs=labs,
                       flat=flat is not None, nscope=len(scope), gold=gname, gold_kind=gk, own=own, gold_idx=opts.index(gold) if gold in opts else None, pre=pre, gold_atom=ga, ms=round((time.perf_counter() - t0) * 1e3, 1), o=row)
            if PR['cutoff']:
                rec['cut'] = 1
            PR['out'].write(json.dumps(rec, separators=(',', ':')) + '\n')
            PR['out'].flush()
            PR['done'].add(pkey)
            PR['probed'] += 1

    class ProbeRun(base):
        drawer_class = ProbeInstr

        def body(self, pg, dr, dec, kind, nlab, *a, **kw):
            if 'body_dec' not in PC:
                PC.update(body_dec=dec, nlab=nlab)
            return super().body(pg, dr, dec, kind, nlab, *a, **kw)

    env.or_q.GuidedRun = ProbeRun


def key_of(r):
    return (r['task'], r['line_id'], r['form'], r['scope_id'], r['phase'], r['atom'], r['dsid'])


def read_rows(path):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            if line.endswith('\n') and line.strip():
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def walk_one(env, p, text, order_idx, out, check):
    """Walks one order of a point with the probe on. Returns (ok, why, form row)."""
    D = env.D
    dag = D.FormDag(text)
    leaves = dag.leaves(dag.written_order())
    scope = p['scope']
    scope_id = p.get('scope_id') or D.short(''.join(sorted(D.ProgramDag(scope).content.values())), 16)
    PC.clear()
    PR.update(on=True, task=p['task'], line_id=p['line_id'], form=p.get('form_key') or p['form'], scope_id=scope_id, order_id=D.short('|'.join(leaves), 12), leaves=leaves, out=out, probed=0, skipped=0)
    PR['deadline'] = None
    if check:
        PR['done'] = set()  # every pick is probed
        PR['deadline'] = time.time() + CHECK_WALK_SECONDS
    try:
        q, picks, aligned, heads_ok, sec, dag2, leaves2, _e, _c = env.walk(p['task'], p['kind'], scope, text, scope_id)
    finally:
        PR['on'] = False
    why = q.get('error') or (q.get('bad') or [''])[0] if (q.get('error') or q.get('bad')) else q.get('dead') or ('left %d' % q['left'] if q.get('left') else None) or (None if aligned else 'misaligned') or (None if heads_ok is not False else 'heads differ')
    msg = ' '.join(str(why).split()[:6]) if why else None
    form = dict(rec='form', part=PR['part'], point=p['line'], order_idx=order_idx, task=p['task'], line_id=p['line_id'], form=PR['form'], order_id=PR['order_id'], ok=why is None, drop=msg, total=q.get('total'), seconds=sec, picks=len(picks),
                probed=PR['probed'], skipped=PR['skipped'])
    out.write(json.dumps(form) + '\n')
    out.flush()
    return why is None, msg, form


def load_points(part, every):
    path = str(L.OUT_DIR / ('points-%s.jsonl' % part))
    pts = [json.loads(x) for x in open(path)]
    pts = [p for p in pts if p['kind'] == 'RULE'][::every]
    return pts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--part', default='held-parents', choices=['held-parents', 'test-parents'])
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--seconds', type=float, default=None)
    ap.add_argument('--every', type=int, default=None)
    ap.add_argument('--priors-fold', default='')
    ap.add_argument('--limit', type=int, default=None, help='stop after this many walks')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--keys', type=int, default=30, help='--check: shared pick keys to compare')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--check-report', action='store_true', help='compare the shared pick keys of the check rows that exist')
    ap.add_argument('--out', default=str(L.OUT_DIR))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.check_report:
        return report_check(a, None)
    if a.report:
        return report(a)
    shard, shards = map(int, a.shard.split('/'))
    source, K, corpus = W.PARTS[a.part]
    every = a.every or (3 if a.part.startswith('test') else 1)
    pts = load_points(a.part, every)
    orders = W.load_orders(source)
    tag = 'held' if a.part.startswith('held') else 'test'
    path = os.path.join(a.out, ('probe-check-rows-shard%dof%d.jsonl' % (shard, shards) if a.check else 'probe-%s-shard%dof%d.jsonl' % (tag, shard, shards)))
    tasks = sorted({p['task'] for p in pts})
    keep = {t for j, t in enumerate(tasks) if j % shards == shard}
    todo = [p for p in pts if p['task'] in keep and (p['task'], p['line_id']) in orders]
    if a.check:  # forms whose first two orders share pick keys (an atom with the same downset), the smallest forms first
        import features_dag_order as D

        def shared(p):
            r = orders[p['task'], p['line_id']]['orders']
            if len(r) < 2:
                return 0, 0
            seen = []
            for text in r[:2]:
                dag = D.FormDag(text)
                lv = dag.leaves(dag.written_order())
                seen.append({(x, frozenset(lv[:j])) for j, x in enumerate(lv)})
            return len(seen[0] & seen[1]), len(seen[0])
        sh = {id(p): shared(p) for p in todo}
        todo = sorted((p for p in todo if sh[id(p)][0] >= 2), key=lambda p: (sh[id(p)][1], p['task'], p['line_id']))
    got_forms, done = {}, set()
    for r in read_rows(path):
        if r['rec'] == 'form':
            got_forms[r['point'], r['order_idx']] = r['ok']
        else:
            done.add(key_of(r))
    print('%s: %d RULE points (every %d) of %d tasks, %d in shard %d/%d, %d walks held, %d pick keys held, K %d' % (a.part, len(pts), every, len(tasks), len(todo), shard, shards, len(got_forms), len(done), K), flush=True)
    env = W.Env('fit' if corpus == 'fit' else 'held', 'off', False, a.priors_fold)
    init_modules()
    global ENV
    ENV = env
    make_run(env)
    want = 0
    for p in todo:
        r = orders[p['task'], p['line_id']]
        n_ok = sum(1 for i in range(len(r['orders'])) if got_forms.get((p['line'], i)))
        want += max(0, min(2 if a.check else K, len(r['orders'])) - n_ok)
    print('%d walks to do' % want, flush=True)
    PR.update(part=a.part, done=done, on=False)
    t0, walked, drops, probed, skipped = time.time(), 0, 0, 0, 0
    msgs = collections.Counter()
    with open(path, 'a') as out:
        for p in todo:
            if (a.seconds and time.time() - t0 > a.seconds) or (a.limit and walked >= a.limit):
                print('stopped: budget spent', flush=True)
                break
            r = orders[p['task'], p['line_id']]
            n_ok = sum(1 for i in range(len(r['orders'])) if got_forms.get((p['line'], i)))
            for i, text in enumerate(r['orders']):
                if n_ok >= (2 if a.check else K):
                    break
                if (p['line'], i) in got_forms:
                    continue
                if a.seconds and time.time() - t0 > a.seconds:
                    break
                ok, msg, form = walk_one(env, p, text, i, out, a.check)
                got_forms[p['line'], i] = ok
                walked += 1
                probed += form['probed']
                skipped += form['skipped']
                if ok:
                    n_ok += 1
                else:
                    drops += 1
                    msgs[msg] += 1
                if walked % 10 == 0:
                    el = time.time() - t0
                    print('[%d/%d walks %.0fs %.2f walks/s %.2f probes/s eta %.0fs] probed %d, skipped %d, drops %d %s' % (walked, want, el, walked / el, probed / el, el / walked * max(0, want - walked), probed, skipped, drops, dict(msgs.most_common(3))), flush=True)
    el = time.time() - t0
    print('done: %d walks in %.0f s (%.2f walks/s), %d picks probed (%.2f per s), %d skipped as held, %d dropped %s' % (walked, el, walked / max(el, 1e-9), probed, probed / max(el, 1e-9), skipped, drops, dict(msgs)), flush=True)
    if a.check:
        report_check(a, path)


def masks(r):
    """{option name: (u, a, eu, ea, und)} of a probe row. eu and ea are read only for a comparison or a pick after NOT (the sets use them there); for a plain relation the probe stops at the first map that gives a row on every example,
    so its eu and ea depend on which map came first (label numbers follow the order), and they are left out as (0, 0)."""
    out = {}
    for x in r['o']:
        filt = x[KINDC] == 'C' or r['phase'] == 'root2'
        out[x[NAME]] = (x[U], x[A], x[EU] if filt else 0, x[EA] if filt else 0, x[UND])
    return out


def report_check(a, path):
    """Pick keys that two orders reach: the masks u, a, eu, ea of each option agree. Appends to probe-check.txt."""
    by = collections.defaultdict(dict)
    for r in (r for q in sorted(glob.glob(os.path.join(a.out, 'probe-check-rows-shard*.jsonl'))) for r in read_rows(q)):
        if r['rec'] == 'probe' and not r.get('cut'):
            by[key_of(r)][r['order_id']] = r
    shared = {k: v for k, v in by.items() if len(v) >= 2}
    bad_opts = bad_pre = bad_set = by_prod = 0
    detail = []
    for k, v in shared.items():
        rs = list(v.values())
        m0 = masks(rs[0])
        for r in rs[1:]:
            m = masks(r)
            if set(m) != set(m0):
                bad_set += 1
                detail.append((k, 'option names differ'))
                continue
            diff = [n for n in m0 if m0[n] != m[n]]
            if diff:
                bad_opts += 1
                detail.append((k, 'masks differ on %s' % diff[:3]))
            by_prod += sum(1 for x, y in zip(sorted(rs[0]['o']), sorted(r['o'])) if x[NAME] == y[NAME] and x[KINDC] != 'C' and rs[0]['phase'] != 'root2' and x[EU:EA + 1] != y[EU:EA + 1])
            if rs[0]['pre']['rows'] != r['pre']['rows']:
                bad_pre += 1
                detail.append((k, 'prefix rows differ'))
    nopt = sum(len(next(iter(v.values()))['o']) for v in shared.values())
    line = 'probe check: %d pick keys held, %d reached by two or more orders (%d options); keys with option names differing %d, with masks u/a (and eu/ea where read) differing %d, with prefix rows differing %d (plain relation options whose eu/ea differ, which no set reads: %d); first differences %s' % (
        len(by), len(shared), nopt, bad_set, bad_opts, bad_pre, by_prod, detail[:5])
    print(line, flush=True)
    with open(os.path.join(a.out, 'probe-check.txt'), 'a') as f:
        f.write('%s %s\n' % (time.strftime('%H:%M:%S'), line))


def pick_table_keys(part):
    """The set of pick keys (task, line_id, form, scope_id, phase, atom, dsid) of the walker's pick rows of a part, steers off, from the walks/ files that exist."""
    keys = set()
    for p in sorted(glob.glob(str(L.OUT_DIR / 'walks' / ('%s-off-*.jsonl.zst' % part)))):
        try:
            with open(p, 'rb') as f:
                for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
                    if line.startswith('{"rec": "pick"'):
                        r = json.loads(line)
                        keys.add((r['task'], r['line_id'], r['form'], r['scope_id'], r['phase'], r['atom'], dsid_of(r['downset'])))
        except zstandard.ZstdError:
            pass
    return keys


def in_any(r, x):
    """Whether option x of probe row r is in the `any` set (features_feasible_read.in_set)."""
    if x[DEAD]:
        return False
    rows = r['pre']['rows']
    if x[KINDC] == 'N':
        return rows is None or any(c > 0 for c in rows.values())
    filt = x[KINDC] == 'C' or r['phase'] == 'root2'
    if x[UND]:
        return True
    return (x[EU] if filt else x[U]) > 0


def report(a):
    """Gold in the `any` set by class, from the probe rows that exist, against feasible-read.json of the source record; and the join to the pick table."""
    CLS = {'relation': 'derived', 'lib relation': 'lib', 'relation macro': 'macro', 'fact relation': 'fact', 'NOT': 'NOT', 'CMP': 'comparison'}
    tag = 'held' if a.part.startswith('held') else 'test'
    rows = [r for p in sorted(glob.glob(os.path.join(a.out, 'probe-%s-shard*.jsonl' % tag))) for r in read_rows(p)]
    forms = {(r['point'], r['order_idx']): r for r in rows if r['rec'] == 'form'}
    probes = [r for r in rows if r['rec'] == 'probe']
    alive = [r for r in probes if r['gold_idx'] is not None and not r['o'][r['gold_idx']][DEAD]]
    by = collections.defaultdict(lambda: [0, 0])
    for r in alive:
        c = 'own' if r['own'] else CLS[r['gold_kind']]
        by[c][0] += 1
        by[c][1] += in_any(r, r['o'][r['gold_idx']])
        by['all'][0] += 1
        by['all'][1] += in_any(r, r['o'][r['gold_idx']])
    src = json.load(open(L.SCRATCH / 'records/features-relation-pick-feasible-by-value-join-heldout37/feasible-read.json'))['bits_by_class']
    lines = ['%s probe rows: %d picks probed, %d walks, %d gold-alive picks' % (tag, len(probes), len(forms), len(alive))]
    for c in ('all', 'derived', 'lib', 'own', 'macro', 'fact', 'NOT', 'comparison'):
        if c in by:
            n, g = by[c]
            ref = src.get(c)
            lines.append('  %-10s picks %5d  gold in any %5d  share %.3f   source share %s' % (c, n, g, g / n, ('%.3f' % (ref['gold_in_any'] / ref['picks'])) if ref else '0.9675 (all picks)' if c == 'all' else 'n/a'))
    if tag == 'held':
        keys = pick_table_keys('held-parents')
        mine = {key_of(r) for r in probes}
        lines.append('  join to the pick table (walks/held-parents-off-*, as far as they exist): %d probed keys, %d in the pick table; %d keys in the pick table' % (len(mine), len(mine & keys), len(keys)))
    print('\n'.join(lines))
    with open(os.path.join(a.out, 'probe-report.txt'), 'a') as f:
        f.write(time.strftime('%H:%M:%S ') + '\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
