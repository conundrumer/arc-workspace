#!/usr/bin/env python
"""Frontier measurement: legal next atoms at each prefix of gold's body, and which keep gold reachable.

Run with the study runtime, through run_heavy:

  scripts/run_heavy.py --cpus 1 --need now \
    /Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-66f08471/venv/bin/python -I \
    measure.py --points points.json --out OUT.jsonl [--only 0,3] [--mutants]

`--points` is a JSON list of objects with `task`, `case`, `point` (the layout of
feat-exp/sample/points.json, whose entries also have `kind` and `pairs`).
Outputs:
  OUT.jsonl           one row per (point, step, candidate atom)
  OUT.steps.jsonl     one row per (point, step): counts and sample sizes
  OUT.points.jsonl    one row per point: seconds, gold checks
  OUT.mutants.jsonl   with --mutants: stored one-edit mutants and the label check

Method (see pilot/notes.md): one Decoder run per point. P = gold's first `step`
atoms. A table is read with `step_tables(bodies=True)` after the atoms and one
probe atom start (the engine gives a body table only at such a token). Gold's
kept DET assignments come from the study evaluator and select entries by value.
reachable: rows of gold's final body table, projected on the labels that P+a
and gold's final table share, are all in the rows of P+a at the same kept
assignment, on every example. reachable_p: the same on the labels of P alone.
"""
import argparse
import statistics
import collections
import csv
import gzip
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

WORKTREE = str(Path(__file__).resolve().parents[4])
STUDY = WORKTREE + '/model/study'
sys.path[:0] = [STUDY, STUDY + '/judgetool', STUDY + '/judge3']
sys.dont_write_bytecode = True
import arclog  # noqa: E402
from study_paths import DATA_ROOT, MAIN_ROOT  # noqa: E402

DATA = str(DATA_ROOT) + '/'
TASKS = str(MAIN_ROOT / 'data/tasks') + '/'

FMT = {'uint8': 'B', 'int32': 'i', 'uint32': 'I', 'int64': 'q', 'uint64': 'Q'}
WIDE = {'Box', 'Position', 'Offset'}
CMP = (18, 19, 20, 21, 22, 23)
NOT, OR, END, STAR, ZERO, CARET = 14, 8, 11, 15, 17, 16
RELK = ('lib relation', 'fact relation', 'relation', 'relation macro')


def col(ct, part, key):
    v = getattr(ct, part)[key]
    if isinstance(v, (bytes, bytearray, memoryview)):
        return memoryview(v).cast('B').cast(FMT[ct.dtypes[part + '.' + key]])
    return v


def slot_no(name):
    m = re.fullmatch(r'(?:slot |&r)([0-9]+)', name)
    return int(m[1]) if m else name


class Fail(Exception):
    pass


# ---------------------------------------------------------------- tables

def parse_table(ct):
    """The one body table of a step_tables result: labels, widths and rows per (example, assignment)."""
    T = ct.tables
    n = len(T['form'])
    if n != 1:
        raise Fail('step gave %d tables' % n)
    if T['fault'][0]:
        raise Fail('table fault: %s' % (T['fault'][0],))
    base = ct.base_tables or 0
    labels = list(T['column_labels'][0])
    types = list(T['column_types'][0])
    widths = [4 if t in WIDE else 1 for t in types]
    offs = [sum(widths[:i]) for i in range(len(widths))]
    tw = sum(widths)
    det_rel = list(T['det_relations'][0])
    det_types = list(T['det_types'][0])
    det_w = list(T['det_widths'][0])
    V = memoryview(ct.values).cast('B').cast('i')
    et, ex, ei = col(ct, 'entries', 'table'), col(ct, 'entries', 'example_kind'), col(ct, 'entries', 'example_index')
    ek, er, eo = col(ct, 'entries', 'kind'), col(ct, 'entries', 'rows'), col(ct, 'entries', 'offset')
    stop, vstop, efault = ct.entries['stop_bound'], ct.entries['value_stop_bound'], ct.entries['fault']
    ae, ad, ar, ao = (col(ct, 'assigned', k) for k in ('entry', 'det', 'rows', 'offset'))
    by_entry = collections.defaultdict(list)
    for a in range(len(ae)):
        by_entry[ae[a]].append(a)
    entries = []
    for e in range(len(et)):
        if et[e] - base != 0:
            continue
        if ek[e] != 0 or stop[e] or vstop[e] or efault[e]:
            raise Fail('entry %d incomplete (kind %d, stop %s %s, fault %s)' % (e, ek[e], stop[e], vstop[e], efault[e]))
        rows = set()
        for r in range(er[e]):
            o = eo[e] + r * tw
            rows.add(tuple(V[o:o + tw]))
        asg = {}
        for a in by_entry[e]:
            d = ad[a]
            w = det_w[d]
            drows = frozenset(tuple(V[ao[a] + r * w:ao[a] + (r + 1) * w]) for r in range(ar[a]))
            asg[slot_no(det_rel[d])] = (drows, 'Ident' in det_types[d] or any('Ident' in str(t) for t in det_types[d]))
        entries.append(((int(ex[e]), int(ei[e])), asg, rows))
    return dict(labels=labels, types=types, widths=widths, offs=offs, entries=entries)


def kept_match(asg, kept):
    """Whether an entry's DET assignment agrees with one kept assignment (Ident-typed DETs are not compared)."""
    for slot, (rows, ident) in asg.items():
        if ident or slot not in kept:
            continue
        if rows != kept[slot]:
            return False
    return True


def view(tbl, kept_list):
    """For each kept assignment, rows per example (union over the entries that match it)."""
    out = []
    for kept in kept_list:
        per = {}
        for ex, asg, rows in tbl['entries']:
            if kept_match(asg, kept):
                per.setdefault(ex, set()).update(rows)
        out.append(per)
    return out


def cells(tbl, label):
    i = tbl['labels'].index(label)
    return list(range(tbl['offs'][i], tbl['offs'][i] + tbl['widths'][i]))


def reach(gold, gview, cand, cview, labels):
    """Whether gold's rows projected on `labels` are in cand's rows, for every kept assignment and example."""
    common = [l for l in labels if l in gold['labels'] and l in cand['labels']
              and gold['types'][gold['labels'].index(l)] == cand['types'][cand['labels'].index(l)]]
    gi = [c for l in common for c in cells(gold, l)]
    ci = [c for l in common for c in cells(cand, l)]
    for kv_g, kv_c in zip(gview, cview):
        for ex, grows in kv_g.items():
            g = {tuple(r[c] for c in gi) for r in grows}
            c_ = {tuple(r[c] for c in ci) for r in kv_c.get(ex, ())}
            if not g <= c_:
                return False, len(common)
    return True, len(common)


def size(v):
    return sum(len(r) for r in v[0].values()) if v else 0


def productive(r):
    """Whether an atom's table is not noise: not empty, adds a column or cuts rows, copies no column, and the added
    columns are not all fixed enumerations."""
    if not r.get('size_pa'):
        return False
    if r['new_cols'] == 0 and r['size_pa'] >= r['size_p']:
        return False
    if r['new_copy'] > 0:
        return False
    return not (r['new_cols'] > 0 and r['new_fixed'] == r['new_cols'])


def column_facts(tp, ta, av):
    """The columns P+a adds over P, and whether each is constant within every example, the same value set in every
    example (a fixed enumeration), or a copy of an older column; the new columns' types; a constant column's value per
    example.
    `new_nd` is the largest, over the new columns, of the median per-example count of distinct values."""
    old = set(tp['labels']) if tp else set()
    new = [l for l in ta['labels'] if l not in old]
    rows_by_ex = av[0] if av else {}
    const = copy = fixed = 0
    nd = []
    types = [ta['types'][ta['labels'].index(l)] for l in new]
    vals = {}
    for l in new:
        ci = cells(ta, l)
        per = [{tuple(r[c] for c in ci) for r in rows} for rows in rows_by_ex.values() if rows]
        if per and all(len(s) == 1 for s in per):
            const += 1
            vals[l] = [list(next(iter(s))) for s in per]
        if len(per) > 1 and all(s == per[0] for s in per[1:]):
            fixed += 1
        if any(all(tuple(r[c] for c in ci) == tuple(r[c] for c in cells(ta, o)) for rows in rows_by_ex.values() for r in rows)
               for o in ta['labels'] if o != l and ta['widths'][ta['labels'].index(o)] == len(ci)):
            copy += 1
        nd.append(statistics.median(len(s) for s in per) if per else 0)
    return dict(cols_p=len(old), cols_pa=len(ta['labels']), new_cols=len(new), new_const=const, new_copy=copy, new_fixed=fixed,
                new_nd=max(nd) if nd else None, new_types=[str(t) for t in types], new_const_vals=vals)


# ---------------------------------------------------------------- one point

class Env:
    """Session-wide objects: the study evaluator, and a session per task."""

    def __init__(self, deadline, seed):
        from evaluator import ReplayEvaluator
        self.ev = ReplayEvaluator(deadline=deadline)
        self.settings = arclog.DecodeSettings(table_work_cap=1048576 * 64, rule_tests=False)
        self.sessions = {}
        self.seed = seed

    def session(self, task):
        if task not in self.sessions:
            self.sessions[task] = arclog.Session(arclog.Task.from_json(open(TASKS + task + '.json').read(), arclog.World.Closed), self.settings)
        return self.sessions[task]


class Node:
    __slots__ = ('toks', 'dec', 'phase', 'last', 'need', 'text', 'mask', 'kids', 'neg')

    def __init__(self, toks, dec, phase, last, need, text, neg):
        self.toks, self.dec, self.phase, self.last, self.need, self.text, self.neg = toks, dec, phase, last, need, text, neg
        self.mask = None
        self.kids = {}


class Frontier:
    """The grammar of one atom over the Decoder's token mask, with memoised nodes."""

    def __init__(self, dec, V):
        self.V = V
        self.nv = len(V)
        self.KIND = [V.kind(i) for i in range(self.nv)]
        self.starts = {i for i in range(self.nv) if self.KIND[i] in RELK}
        self.closers = self.starts | {END, NOT} | set(CMP)
        self.values = {i for i in range(self.nv) if self.KIND[i] == 'label'} | {STAR, ZERO, CARET}
        self.cols = {i: int(V.name(i)[1:]) for i in range(self.nv) if self.KIND[i] == 'column' and V.name(i)[1:].isdigit()}
        self.root = Node((), dec, 'root', -1, 0, '', False)
        self.created = 0

    def mask(self, n):
        if n.mask is None:
            m = n.dec.admissible()
            n.mask = [j for j in range(self.nv) if m[j >> 3] >> (j & 7) & 1]
        return n.mask

    def options(self, n):
        mk = self.mask(n)
        if n.phase in ('root', 'root2'):
            out = [j for j in mk if j in self.starts or j in CMP or (j == NOT and n.phase == 'root')]
        elif n.phase == 'cols':
            out = [j for j in mk if j in self.cols and self.cols[j] > n.last]
        elif n.phase == 'val':
            out = [j for j in mk if j in self.values]
        elif n.phase == 'op':
            out = [j for j in mk if j in self.values and j != STAR]
        else:
            out = []
        return out

    def is_leaf(self, n):
        if n.phase not in ('cols', 'done'):
            return False
        mk = self.mask(n)
        return any(j in self.closers for j in mk)

    def child(self, n, tok):
        if tok in n.kids:
            return n.kids[tok]
        f = n.dec.fork()
        try:
            r = f.step(tok)
        except arclog.Refusal:
            n.kids[tok] = None
            return None
        self.created += 1
        V, ph = self.V, n.phase
        text, last, need, neg = n.text, n.last, n.need, n.neg
        if ph in ('root', 'root2'):
            if tok == NOT:
                nph, neg = 'root2', True
            elif tok in CMP:
                nph, need, text = 'op', 2, '(%s' % V.name(tok)
            else:
                nph, last, text = 'cols', -1, '(%s' % V.name(tok)
        elif ph == 'cols':
            nph, last, text = 'val', self.cols[tok], n.text + ' (:%d' % self.cols[tok]
        elif ph == 'val':
            nph = 'cols'
            text = n.text + ' %s)' % ((('*' if tok == STAR else '^') + V.name(r[0][0])) if tok in (STAR, CARET) and r[0] else V.name(tok))
        else:  # op
            need -= 1
            nph = 'done' if need == 0 else 'op'
            text = n.text + ' ' + V.name(tok)
        c = Node(n.toks + (tok,), f, nph, last, need, text, neg)
        n.kids[tok] = c
        return c

    def render(self, n):
        t = n.text + ')'
        return '(NOT %s)' % t if n.neg else t


def sorted_atom(fr, toks):
    """Gold's atom tokens with the columns in ascending order, or None when the atom is outside the grammar."""
    toks = list(toks)
    pre = []
    if toks and toks[0] == NOT:
        pre, toks = [NOT], toks[1:]
    if not toks:
        return None
    if toks[0] in CMP:
        return tuple(pre + toks) if len(toks) == 3 else None
    if toks[0] not in fr.starts or (len(toks) - 1) % 2:
        return None
    pairs = [(toks[i], toks[i + 1]) for i in range(1, len(toks), 2)]
    if any(c not in fr.cols or v not in fr.values for c, v in pairs) or len({c for c, _ in pairs}) != len(pairs):
        return None
    pairs.sort(key=lambda cv: fr.cols[cv[0]])
    return tuple(pre + [toks[0]] + [t for cv in pairs for t in cv])


def enumerate_exact(fr, budget):
    """All leaves by depth-first walk, or None when the walk needs more than `budget` new nodes."""
    start = fr.created
    leaves = []
    stack = [fr.root]
    while stack:
        n = stack.pop()
        if fr.created - start > budget:
            return None
        if fr.is_leaf(n):
            leaves.append(n)
        for t in fr.options(n):
            c = fr.child(n, t)
            if c is not None:
                stack.append(c)
    return leaves


def probe_leaves(fr, rng, probes, seconds):
    """Knuth random descents: (estimate of the leaf count, relative standard error, {leaf: weight})."""
    t0 = time.time()
    weights = {}
    hits = collections.Counter()
    ests = []
    for _ in range(probes):
        if time.time() - t0 > seconds:
            break
        n, w = fr.root, 1.0
        got = 0.0
        while True:
            opts = fr.options(n)
            leaf = fr.is_leaf(n)
            k = len(opts) + (1 if leaf else 0)
            if k == 0:
                break
            w *= k
            i = rng.randrange(k)
            if leaf and i == k - 1:
                got = w
                weights[n] = w
                hits[n] += 1
                break
            c = fr.child(n, opts[i])
            if c is None:
                break
            n = c
        ests.append(got)
    m = len(ests)
    if m == 0:
        return 0.0, None, weights, hits, 0
    mean = sum(ests) / m
    var = sum((x - mean) ** 2 for x in ests) / max(m - 1, 1)
    rse = (var / m) ** 0.5 / mean if mean > 0 else None
    return mean, rse, weights, hits, m


def rel_of(V, toks):
    toks = list(toks)
    if toks and toks[0] == NOT:
        toks = toks[1:]
    return V.name(toks[0]) if toks else '?'


def table_id(tbl, kept_list):
    """Digest of a table's rows at gold's kept assignments, columns ordered by label."""
    order = sorted(range(len(tbl['labels'])), key=lambda i: tbl['labels'][i])
    idx = [(c) for i in order for c in range(tbl['offs'][i], tbl['offs'][i] + tbl['widths'][i])]
    h = hashlib.md5()
    h.update(json.dumps([tbl['labels'][i] for i in order]).encode())
    for per in view(tbl, kept_list):
        for ex in sorted(per):
            h.update(repr((ex, sorted(tuple(r[c] for c in idx) for r in per[ex]))).encode())
    return h.hexdigest()[:12]


def hard_tokens(toks):
    return any(t == NOT or t == OR or t in CMP for t in toks)


def seed_of(*parts):
    return int(hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:12], 16)


def probe_token(fr, dec):
    n = Node((), dec, 'root', -1, 0, '', False)
    mk = fr.mask(n)
    inp = fr.V.id('input')
    if inp is not None and inp in mk:
        return inp
    for j in mk:
        if fr.KIND[j] == 'lib relation':
            return j
    for j in mk:
        if j in fr.starts:
            return j
    return None


def body_table(fr, task, case, parent_dec, parent_before, toks):
    """Table of the body after `toks` on top of the parent state; None with a reason on failure."""
    f = parent_dec.fork()
    try:
        for t in toks:
            f.step(t)
    except arclog.Refusal as e:
        return None, 'refused: %s' % e
    p = probe_token(fr, f)
    if p is None:
        return None, 'no probe token'
    try:
        f.step(p)
        ct = arclog.step_tables(f, task, case, True, parent_before)
        return parse_table(ct), None
    except Fail as e:
        return None, str(e)
    except (Exception, BaseException) as e:  # engine faults, panics and stops are reported, not hidden
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        return None, '%s: %s' % (type(e).__name__, e)


def tables_equal(a, b):
    if a is None or b is None:
        return a is b
    key = lambda t: (t['labels'], sorted((e[0], sorted((k, sorted(v[0])) for k, v in e[1].items()), sorted(e[2])) for e in t['entries']))
    return key(a) == key(b)


def kept_of(env, task, ids, model):
    te = env.ev.task_evaluator(task)
    gold = te.from_stream(ids, list(model))
    rep = json.loads(te.gold_kept(gold))
    if rep.get('status') != 'complete' or not rep.get('kept_assignments'):
        raise Fail('gold kept: %s' % rep.get('status'))
    kept = []
    for choice in rep['kept_assignments']:
        kept.append({slot_no(d['relation']): frozenset(tuple(r) for r in d['rows']) for d in choice})
    return kept


def corpus_record(task, case, point):
    for line in gzip.open(DATA + 'ast/run/corpus-v11/%s/pairs.jsonl.gz' % task, 'rt'):
        r = json.loads(line)
        if r['case'] == case and r['point'] == point:
            return r
    raise Fail('no corpus record for %s %s %s' % (task, case, point))


def corpus_records(task, case, point):
    for line in gzip.open(DATA + 'ast/run/corpus-v11/%s/pairs.jsonl.gz' % task, 'rt'):
        r = json.loads(line)
        if r['case'] == case and r['point'] == point:
            yield r


def atoms_of(paths, ids, model, point):
    """token indices per atom index of the body at `point`."""
    L = len(point)
    by = collections.OrderedDict()
    for i, p in enumerate(paths):
        if p and len(p) > L and list(p[:L]) == list(point):
            by.setdefault(p[L], []).append(i)
    return by


def measure_point(env, spec, args, out, steps_out, mut_out):
    task, case, point = spec['task'], spec['case'], list(spec['point'])
    t_point = time.time()
    rec = corpus_record(task, case, point)
    sess = env.session(task)
    gp = arclog.StudyProgram.from_sexp(rec['gold_sexp'], env.settings)
    ids, model, paths = gp.decode_stream()
    V = sess.decoder().vocabulary
    kept = kept_of(env, task, ids, model)
    by = atoms_of(paths, ids, model, point)
    natoms = len(by)
    if natoms == 0:
        raise Fail('no atoms at point')
    atom_idx = list(by.values())
    first = atom_idx[0][0]
    atom_toks = [[ids[i] for i in idx if model[i] == 1] for idx in atom_idx]
    hard = [hard_tokens(t) for t in atom_toks]

    dec = sess.decoder()
    before = None
    i = 0

    def advance(stop):
        nonlocal i, before
        while i < stop:
            if model[i] == 1:
                dec.step(ids[i])
                before = arclog.step_tables(dec, task, case, True, before)
            i += 1

    advance(first)
    fr0 = Frontier(dec, V)
    states = []  # (decoder, before) at the start of each atom, and after the last
    for k in range(natoms):
        states.append((dec.fork(), before))
        advance(atom_idx[k][-1] + 1)
    states.append((dec.fork(), before))

    # gold's final body table, with the same decoder
    gfin, err = body_table(fr0, task, case, states[natoms][0], states[natoms][1], [])
    if gfin is None:
        raise Fail('gold final table: %s' % err)
    gview = view(gfin, kept)
    if not any(gview):
        raise Fail('no entry matches gold kept assignment')
    gold_labels = gfin['labels']

    checks = collections.Counter()
    step_rows = []
    P_tables = []
    for k in range(natoms + 1):
        tp, err = body_table(fr0, task, case, states[k][0], states[k][1], [])
        P_tables.append((tp, err))

    def row_for(k, tp, ta, toks, text, is_gold, in_enum, mark_a, ncols=None):
        later = any(hard[k:])
        mark = '+'.join(x for x, f in (('atom', mark_a), ('later', later)) if f) or None
        r = dict(task=task, case=case, point=point, step=k, atom=text, gold=is_gold, in_enum=in_enum,
                 size_p=size(view(tp, kept)) if tp else None, size_pa=None, reachable=None, reachable_p=None, mark=mark)
        if ta is None:
            return r
        av = view(ta, kept)
        r['size_pa'] = size(av)
        r['reachable'], r['ncommon'] = reach(gfin, gview, ta, av, ta['labels'])
        pl = tp['labels'] if tp else []
        r['reachable_p'], _ = reach(gfin, gview, ta, av, pl)
        r.update(column_facts(tp, ta, av))
        return r

    for k in range(natoms):
        t_step = time.time()
        dk, bk = states[k]
        tp, perr = P_tables[k]
        fr = Frontier(dk, V)
        rng = random.Random(seed_of(env.seed, task, case, point, k))
        rel_legal = collections.Counter()
        leaves = enumerate_exact(fr, args.budget)
        exact = leaves is not None
        rse = None
        if exact:
            n_legal = len(leaves)
            for n in leaves:
                rel_legal[rel_of(V, n.toks)] += 1
            pool = leaves
            if args.productive:
                pool = rng.sample(pool, len(pool))
            elif len(pool) > args.max_eval:
                pool = rng.sample(pool, args.max_eval)
        else:
            est, rse, weights, hits, nprobes = probe_leaves(fr, rng, args.probes, args.step_seconds)
            n_legal = est
            for n, h in hits.items():
                rel_legal[rel_of(V, n.toks)] += h * weights[n] / nprobes
            items = list(weights.items())
            pool = []
            keys = [n for n, _ in items]
            ws = [w for _, w in items]
            seen = set()
            tries = 0
            want = len(items) if args.productive else min(args.max_eval, len(items))
            while len(pool) < want and tries < 20 * want:
                tries += 1
                n = rng.choices(keys, weights=ws)[0]
                if n in seen:
                    continue
                seen.add(n)
                pool.append(n)
        # gold's atom
        gtoks = tuple(atom_toks[k])
        gnode = None
        srt = sorted_atom(fr, gtoks)
        if srt is not None:
            gnode = fr.root
            for t in srt:
                if gnode is None or t not in fr.options(gnode):
                    gnode = None
                    break
                gnode = fr.child(gnode, t)
        gold_in = gnode is not None and fr.is_leaf(gnode)
        cands = []
        for n in pool:
            if gold_in and n is gnode:
                continue
            cands.append((n, n.toks, fr.render(n), False, True, n.neg or n.toks[0] in CMP))
        if gold_in:
            cands.append((gnode, gtoks, fr.render(gnode), True, True, hard[k]))
        else:
            cands.append((None, gtoks, 'gold:' + ' '.join(V.name(t) for t in gtoks), True, False, hard[k]))
        n_reach = 0
        n_eval = 0
        gold_reach = None
        tids = set()
        tids_reach = set()
        rel_eval = collections.Counter()
        rel_reach = collections.Counter()
        gold_rel = None
        errors = collections.Counter()
        n_productive = 0
        for n, toks, text, is_gold, in_enum, mark_a in cands:
            if args.productive and not is_gold and (n_productive >= args.productive or n_eval >= args.max_eval):
                continue
            ta, err = body_table(fr0, task, case, dk, bk, toks)
            if err:
                errors[err[:60]] += 1
            r = row_for(k, tp, ta, toks, text, is_gold, in_enum, mark_a)
            r['err'] = err
            rel = rel_of(V, toks)
            r['rel'] = rel
            r['tid'] = table_id(ta, kept) if ta is not None else None
            if is_gold:
                gold_rel = rel
            else:
                rel_eval[rel] += 1
                if r['reachable']:
                    rel_reach[rel] += 1
            if r['tid'] is not None:
                tids.add(r['tid'])
                if r['reachable']:
                    tids_reach.add(r['tid'])
            if is_gold:
                gold_reach = r['reachable']
                # same table through the chain of gold's own steps
                tw = P_tables[k + 1][0]
                checks['gold_chain_equal' if tables_equal(ta, tw) else 'gold_chain_differs'] += 1
                if r['reachable'] is not True:
                    checks['gold_not_reachable'] += 1
            r['productive'] = productive(r) if ta is not None else False
            if args.productive:
                r['toks'] = [int(t) for t in toks]
            if r['productive'] and not is_gold:
                n_productive += 1
            out.write(json.dumps(r) + '\n')
            n_eval += 1
            if r['reachable']:
                n_reach += 1
        ncand_eval = n_eval - 1  # excluding gold when counting the share
        non_gold_reach = n_reach - (1 if gold_reach else 0)
        share = non_gold_reach / ncand_eval if ncand_eval else None
        root_mask = fr.mask(fr.root)
        step = dict(task=task, case=case, point=point, step=k, legal=round(n_legal, 1) if not exact else n_legal,
                    legal_exact=exact, legal_rse=rse, sample=len(pool), evaluated=n_eval,
                    reachable_in_sample=n_reach, reachable_share_nongold=share,
                    reachable_est=(share * n_legal if share is not None else None),
                    reachable_nongold_in_sample=non_gold_reach,
                    distinct_tables=len(tids), distinct_tables_reachable=len(tids_reach),
                    relations_legal=len(rel_legal), relations_evaluated=len(rel_eval),
                    relations_with_reachable=len(rel_reach), relations_with_reachable_incl_gold=len(set(rel_reach) | ({gold_rel} if gold_reach else set())),
                    per_relation={rel: dict(legal=round(rel_legal[rel], 1), evaluated=rel_eval[rel], reachable_in_sample=rel_reach[rel],
                                            reachable_est=(round(rel_legal[rel] * rel_reach[rel] / rel_eval[rel], 1) if rel_eval[rel] else None))
                                  for rel in sorted(set(rel_legal) | set(rel_eval))},
                    gold_reachable=gold_reach, gold_in_enum=gold_in, gold_hard=hard[k],
                    unexpanded_controls=[V.name(j) for j in root_mask if j in (3, 4, OR, 9, 10)],
                    size_p=size(view(tp, kept)) if tp else None, p_error=perr, errors=dict(errors),
                    nodes=fr.created, seconds=round(time.time() - t_step, 2))
        steps_out.write(json.dumps(step) + '\n')
        step_rows.append(step)

    # neutrality of the probe: the table after the probe holds as many rows as the decoder counts without it
    for k in range(natoms + 1):
        d = states[k][0].fork()
        try:
            cnt = d.counts()
            counted = sorted(c for a in cnt for c in a.values if c is not None) if cnt else None
        except BaseException as e:  # noqa  (engine panics included)
            if isinstance(e, (KeyboardInterrupt, SystemExit)):
                raise
            counted = None
        tp = P_tables[k][0]
        if counted is not None and tp is not None:
            have = sorted(len(e[2]) for e in tp['entries'])
            checks['probe_neutral' if have == counted else 'probe_not_neutral'] += 1
            if have != counted:
                checks['probe_diff_k%d' % k] += 1

    res = dict(task=task, case=case, point=point, kind=spec.get('kind'), atoms=natoms, kept=len(kept),
               seconds=round(time.time() - t_point, 2), checks=dict(checks), gold_labels=gold_labels)
    if mut_out is not None:
        mutant_check(env, spec, args, mut_out, rec, fr0, states, atom_toks, hard, V, ids, model, paths, point, kept, gfin, gview, task, case, sess)
    return res


def mutant_check(env, spec, args, mut_out, rec, fr0, states, atom_toks, hard, V, ids, model, paths, point, kept, gfin, gview, task, case, sess):
    """Stored one-edit mutants that delete or substitute one atom of gold's body: the edited prefix against the stored label."""
    meta = {}
    wanted = {}
    for line in open(DATA + 'feat-exp/sample/meta.jsonl'):
        m = json.loads(line)
        if m['task'] == task and m['case'] == case and m['point'] == point:
            wanted[m['pair_id']] = m
    stored = {}
    csv.field_size_limit(10 ** 9)
    with gzip.open(DATA + 'feat-exp/study/results/values.csv.gz', 'rt') as f:
        rd = csv.reader(f)
        hd = next(rd)
        ip, il = hd.index('pair_id'), hd.index('t__label')
        for row in rd:
            if row[ip] in wanted:
                stored[row[ip]] = row[il]
    L = len(point)
    for r in corpus_records(task, case, point):
        pk = {k: r[k] for k in ('task', 'case', 'point', 'clause', 'K', 'operation')} | {'edits': r['identity']['edits']}
        pid = hashlib.sha256(json.dumps(pk, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        if pid not in wanted:
            continue
        m = wanted[pid]
        row = dict(pair_id=pid, operation=m['operation'], K=m['K'], stored=stored.get(pid, m.get('label')), meta_label=m.get('label'))
        if m['K'] != 1 or m['operation'] not in ('delete', 'substitute') or len(r['identity']['edits']) != 1:
            row['skipped'] = 'not a one-atom delete or substitute'
            mut_out.write(json.dumps(row) + '\n')
            continue
        at = r['identity']['edits'][0]['at']
        j = at[L]
        row['edit_atom'] = j
        mp = arclog.StudyProgram.from_sexp(r['mutant_sexp'], env.settings)
        mids, mmodel, mpaths = mp.decode_stream()
        mby = atoms_of(mpaths, mids, mmodel, point)
        if j not in mby:
            row['skipped'] = 'no mutant atom at edit position (last atom deleted)'
            mut_out.write(json.dumps(row) + '\n')
            continue
        mtoks = [mids[i] for i in mby[j] if mmodel[i] == 1]
        row['edited_atom_hard'] = hard_tokens(mtoks)
        row['later_hard'] = any(hard[min(j, len(hard) - 1):])
        if j >= len(states) - 1:
            row['skipped'] = 'edit beyond gold atoms'
            mut_out.write(json.dumps(row) + '\n')
            continue
        dk, bk = states[j]
        ta, err = body_table(fr0, task, case, dk, bk, mtoks)
        row['err'] = err
        row['atom'] = ' '.join(V.name(t) for t in mtoks)
        row['rel'] = rel_of(V, mtoks)
        if ta is not None:
            tp = body_table(fr0, task, case, dk, bk, [])[0]
            av = view(ta, kept)
            row['reachable'], _ = reach(gfin, gview, ta, av, ta['labels'])
            row['reachable_p'], _ = reach(gfin, gview, ta, av, tp['labels'] if tp else [])
            row['size_p'] = size(view(tp, kept)) if tp else None
            row['size_pa'] = size(av)
            row['tid'] = table_id(ta, kept)
            row.update(column_facts(tp, ta, av))
        mut_out.write(json.dumps(row) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--points', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--only', help='comma-separated indexes into the points list')
    ap.add_argument('--budget', type=int, default=1500, help='new nodes an exact walk may build per step')
    ap.add_argument('--probes', type=int, default=300, help='random descents per step when the exact walk is cut')
    ap.add_argument('--max-eval', type=int, default=200, help='candidates evaluated per step, besides gold')
    ap.add_argument('--step-seconds', type=float, default=40.0)
    ap.add_argument('--deadline', type=float, default=30.0)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--mutants', action='store_true', help='also check stored one-edit mutants against the label')
    ap.add_argument('--productive', type=int, default=0,
                    help='evaluate sampled atoms, in random order, until this many productive ones are found per step '
                         '(or --max-eval evaluations); every evaluated atom is still written')
    args = ap.parse_args()
    pts = json.load(open(args.points))
    if args.only:
        pts = [pts[int(x)] for x in args.only.split(',')]
    env = Env(args.deadline, args.seed)
    with open(args.out, 'w') as out, open(args.out + '.steps.jsonl', 'w') as steps, open(args.out + '.points.jsonl', 'w') as pout:
        mut = open(args.out + '.mutants.jsonl', 'w') if args.mutants else None
        for spec in pts:
            try:
                res = measure_point(env, spec, args, out, steps, mut)
            except BaseException as e:  # report the point and go on
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
                res = dict(task=spec['task'], case=spec['case'], point=spec['point'], error='%s: %s' % (type(e).__name__, e))
            pout.write(json.dumps(res) + '\n')
            for f in (out, steps, pout) + ((mut,) if mut else ()):
                f.flush()
            print(json.dumps({k: v for k, v in res.items() if k != 'gold_labels'}), flush=True)
        if mut:
            mut.close()


if __name__ == '__main__':
    main()
