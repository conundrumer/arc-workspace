"""Replay of gold programs for the next form read: one engine replay of each task, and the state before each form as a set of found forms.

A program is stepped once on the engine, with the test output removed, in the canonical topological order of its form DAG (the smallest content key among the ready forms). The tables of a form depend on its ancestors alone, so one replay gives every form's tables. The state before a target form f, for a seed s, is the set S of found forms that is the `cut` of f for s: the forms before f in ProgramDag.random_order(s, non_descendants(f) | {f}), as features_dagc_points.py defines it. The state is built from the tables of the forms of S, in any order: it is a function of the set S.

  (a form's table rows are added to the state with a salt that comes from the form's content key and the table's place in the form, so that no number comes from the order of the replay)

Text of a task: the base gold of points-base.json for held and dev tasks, and the first pair of corpus-v3mix for fit tasks (features_dagc_lib.base_gold, fit_gold). The source record read other revisions of the text; about half of the lines differ.

  gold_tables_env.sh 1 next_form_rows.py --out DIR [--split held|dev|fit] [--shard K/N] [--only TASK ...] [--limit N] [--seconds S]

Output in DIR, flushed by task; a rerun skips a task that has a task row:
  form-rows-<split>-<K>.jsonl    one row per form: task, key (the head), form (the content key), line_id, kind, comp, reads (the owner of each derived relation as a form key and its place), slots, tables
  state-rows-<split>-<K>.jsonl   one row per target form and seed: scope (the keys of S, in the cut's order), scope_id, state
  task-rows-<split>-<K>.jsonl    one row per task: static facts, the state of the empty set, counts, seconds
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

import numpy as np
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shape_facts as F  # noqa: E402

import live  # noqa: E402
import pool_rows as PR  # noqa: E402
from live import M, S, arclog  # noqa: E402
import features_dag_order as DO  # noqa: E402
import features_dagc_lib as L  # noqa: E402

SEEDS = (0, 1)
ROW_CAP = 20000
POINT = 'Position'
COLOR = 'Color'


def texts(split):
    """{task: (source, gold lines)}"""
    if split == 'held':
        base = L.base_gold()
        return {t: ('base gold', base[t]) for t in L.held_tasks()}
    if split == 'dev':
        base = L.base_gold()
        return {t: ('base gold', base[t]) for t in L.dev_tasks()}
    return {t: ('corpus-v3mix', lines) for t, lines in L.fit_gold().items()}


def grids(task):
    d = json.load(open(S.TASKS + task + '.json'))
    return [(np.array(p['input'], dtype=np.int16), np.array(p['output'], dtype=np.int16)) for p in d['train']], [np.array(p['input'], dtype=np.int16) for p in d['test']]


def bg_of(g):
    v, n = np.unique(g, return_counts=True)
    return int(v[n.argmax()])


EIGHT = np.ones((3, 3), dtype=int)


def shape_key(pts):
    r0 = min(p[0] for p in pts)
    c0 = min(p[1] for p in pts)
    return tuple(sorted((r - r0, c - c0) for r, c in pts))


def has_sub(big, small):
    """Whether small occurs as a subgrid of big."""
    H, W = big.shape
    h, w = small.shape
    if h > H or w > W:
        return False
    for r in range(H - h + 1):
        for c in range(W - w + 1):
            if big[r, c] == small[0, 0] and np.array_equal(big[r:r + h, c:c + w], small):
                return True
    return False


def period_of(g):
    """The smallest period of the grid along an axis, at most half of it; 0 with none."""
    best = 0
    for a in (g, g.T):
        n = a.shape[0]
        for p in range(1, n // 2 + 1):
            if np.array_equal(a[p:], a[:-p]):
                best = p if not best else min(best, p)
                break
    return best


class Need:
    """Per train example: the cells a program must get right past a copy of the input, and which of them the found tables cover."""

    def __init__(self, train):
        self.ex = []
        for inp, out in train:
            same = inp.shape == out.shape
            changed = (out != inp) if same else np.ones(out.shape, dtype=bool)
            bg = bg_of(inp)
            fg = inp != bg
            lab, n = ndi.label(~fg)
            border = set(lab[0, :].tolist()) | set(lab[-1, :].tolist()) | set(lab[:, 0].tolist()) | set(lab[:, -1].tolist())
            enclosed = ~fg & ~np.isin(lab, list(border))
            obj, nobj = ndi.label(fg, structure=EIGHT)
            shapes = set()
            bbs = set()
            for sl in ndi.find_objects(obj):
                bbs.add((sl[0].stop - sl[0].start, sl[1].stop - sl[1].start))
            if nobj <= 60:
                for i in range(1, nobj + 1):
                    rr, cc = np.nonzero(obj == i)
                    shapes.add(shape_key(list(zip(rr.tolist(), cc.tolist()))))
            adj = ndi.binary_dilation(fg, iterations=1) & ~fg
            rc = np.zeros(inp.shape, dtype=bool)
            rc[fg.any(1), :] = True
            rc[:, fg.any(0)] = True
            self.ex.append(dict(inp=inp, out=out, same=same, changed=changed, bg=bg, incol=set(np.unique(inp).tolist()), fg=fg, enclosed=enclosed, adj=adj, rc=rc, shapes=shapes, bbs=bbs, nobj=nobj))
        self.reset()

    def reset(self):
        """The state of the empty set of found forms."""
        self.fixed_colors = set()
        for e in self.ex:
            e.update(cc=np.zeros(e['out'].shape, dtype=bool), pc=np.zeros(e['out'].shape, dtype=bool), masks=[], found=set(), sig=np.zeros(e['out'].shape, dtype=np.uint64))

    def static(self):
        d = {}
        sz = [(e['inp'].shape, e['out'].shape) for e in self.ex]
        if all(a == b for a, b in sz):
            d['resize'] = 'same'
        elif len({b for _, b in sz}) == 1 and len({a for a, _ in sz}) > 1:
            d['resize'] = 'fixed out'
        elif all(b[0] % a[0] == 0 and b[1] % a[1] == 0 for a, b in sz):
            d['resize'] = 'int up'
        elif all(a[0] % b[0] == 0 and a[1] % b[1] == 0 for a, b in sz):
            d['resize'] = 'int down'
        elif all(b[0] * b[1] > a[0] * a[1] for a, b in sz):
            d['resize'] = 'larger'
        elif all(b[0] * b[1] < a[0] * a[1] for a, b in sz):
            d['resize'] = 'smaller'
        else:
            d['resize'] = 'mixed'
        d['crop'] = all(has_sub(e['inp'], e['out']) for e in self.ex) if d['resize'] != 'same' else False
        d['embed'] = all(has_sub(e['out'], e['inp']) for e in self.ex) if d['resize'] != 'same' else False
        sym = lambda g: bool(np.array_equal(g, g[::-1]) or np.array_equal(g, g[:, ::-1]))  # noqa: E731
        ins = all(sym(e['inp']) for e in self.ex)
        outs = all(sym(e['out']) for e in self.ex)
        d['sym'] = 'gained' if outs and not ins else 'both' if outs else 'none'
        d['period'] = all(period_of(e['out']) for e in self.ex)
        d['period_in'] = all(period_of(e['inp']) for e in self.ex)
        cm = {}
        ok = d['resize'] == 'same'
        if ok:
            for e in self.ex:
                for a, b in zip(e['inp'].ravel().tolist(), e['out'].ravel().tolist()):
                    if cm.setdefault(a, b) != b:
                        ok = False
                        break
                if not ok:
                    break
        d['colormap'] = ok
        d['newcol'] = 'none' if all(set(np.unique(e['out']).tolist()) <= e['incol'] for e in self.ex) else 'some'
        d['nobj'] = int(np.median([e['nobj'] for e in self.ex]))
        d['ncol'] = int(np.median([len(e['incol']) for e in self.ex]))
        d['outbox'] = all(e['out'].shape in e['bbs'] for e in self.ex)
        return d

    def explained(self):
        """Per example, the mask of cells that the found tables predict right, leaving that example out.

        A cell's signature is its input color, where input and output have one shape, and what each found table says of that cell: whether the cell is in the table, and the table's color there.
        A map from signature to the most common output color is read on the other train examples, and applied to this example."""
        ks, ys, es = [], [], []
        for i, e in enumerate(self.ex):
            k = e['sig'].copy()
            if e['same']:
                k = k ^ (e['inp'].astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15) + np.uint64(1))
            ks.append(k.ravel())
            ys.append(e['out'].ravel())
            es.append(np.full(e['out'].size, i))
        k, y, ex = np.concatenate(ks), np.concatenate(ys).astype(np.int64), np.concatenate(es)
        _, inv = np.unique(k, return_inverse=True)
        c = np.zeros((inv.max() + 1, 10), dtype=np.int32)
        np.add.at(c, (inv, y), 1)
        out = []
        for i, e in enumerate(self.ex):
            at = ex == i
            ce = np.zeros_like(c)
            np.add.at(ce, (inv[at], y[at]), 1)
            o = c - ce
            pred = o.argmax(1)
            good = (o.sum(1) > 0)[inv[at]] & (pred[inv[at]] == y[at])
            out.append(good.reshape(e['out'].shape))
        return out

    def apply(self, adds):
        """Adds the rows of one table: adds is the dict that table_summary returns. The state after a set of tables is the same in any order of the calls."""
        for kind, i, arr in adds['items']:
            if kind == 'x':
                self.add(i, arr, adds['pos_at'], adds['col_at'], adds['salt'])
            else:
                self.fixed_colors.update(arr)

    def add(self, i, arr, pos_at, col_at, salt):
        """arr: rows of one table at train example i. pos_at, col_at: the offset of each Position and Color column."""
        e = self.ex[i]
        H, W = e['out'].shape
        for k in col_at:
            e['found'].update(np.unique(arr[:, k]).tolist())
        for a in pos_at:
            r, b, c, x = arr[:, a], arr[:, a + 1], arr[:, a + 2], arr[:, a + 3]
            ok = (r >= 0) & (c >= 0) & (r < H) & (c < W) & (r + b + 1 == H) & (c + x + 1 == W)
            if not ok.any():
                continue
            rr, cc = r[ok], c[ok]
            e['pc'][rr, cc] = True
            m = np.zeros((H, W), dtype=bool)
            m[rr, cc] = True
            e['masks'].append(m)
            val = np.zeros((H, W), dtype=np.int64)
            val[m] = 1
            for k in col_at:
                np.maximum.at(val, (rr, cc), arr[ok, k] + 2)
            e['sig'] = e['sig'] ^ (val.astype(np.uint64) * salt)
            for k in col_at:
                hit = e['out'][rr, cc] == arr[ok, k]
                e['cc'][rr[hit], cc[hit]] = True

    def facts(self):
        changed, uncov, unpos, colors, srcs, new, add, rem, rec, geom, ncc, area, bbox = [], [], [], [], [], [], [], [], [], [], [], [], []
        adjs, encl, onobj, rcs, copy, jac, colfound = [], [], [], [], [], [], []
        good = self.explained()
        xleft, xgeom, xncc, xcol, xnew, xall, xadj, xencl, xonobj = [], [], [], [], [], [], [], [], []
        for e, g in zip(self.ex, good):
            x = e['changed'] & ~g
            nx = int(x.sum())
            xleft.append(nx)
            xall.append(int((~g).sum()))
            H, W = e['out'].shape
            pts = list(zip(*[a.tolist() for a in np.nonzero(x)])) if nx else []
            xgeom.append(F.geom_shape(pts, H, W))
            xncc.append(len(F.components(pts)) if pts else 0)
            cs = sorted(set(e['out'][x].tolist()))
            xcol.append(cs)
            xnew.append(sum(1 for c in cs if c not in e['incol']))
            if e['same'] and nx:
                xadj.append(round(float((x & e['adj']).sum()) / nx, 3))
                xencl.append(round(float((x & e['enclosed']).sum()) / nx, 3))
                xonobj.append(round(float((x & e['fg']).sum()) / nx, 3))
        for e in self.ex:
            u = e['changed'] & ~e['cc']
            p = e['changed'] & ~e['pc']
            H, W = e['out'].shape
            nu = int(u.sum())
            changed.append(int(e['changed'].sum()))
            uncov.append(nu)
            unpos.append(int(p.sum()))
            area.append(H * W)
            pts = list(zip(*[x.tolist() for x in np.nonzero(u)])) if nu else []
            cs = sorted(set(e['out'][u].tolist()))
            colors.append(cs)
            new.append(sum(1 for c in cs if c not in e['incol']))
            if e['same']:
                s = e['inp'][u]
                o = e['out'][u]
                srcs.append(sorted(set(s.tolist())))
                add.append(int((s == e['bg']).sum()))
                rem.append(int(((o == e['bg']) & (s != e['bg'])).sum()))
                rec.append(int(((o != e['bg']) & (s != e['bg'])).sum()))
                if nu:
                    adjs.append(round(float((u & e['adj']).sum()) / nu, 3))
                    encl.append(round(float((u & e['enclosed']).sum()) / nu, 3))
                    onobj.append(round(float((u & e['fg']).sum()) / nu, 3))
                    rcs.append(round(float((u & e['rc']).sum()) / nu, 3))
            else:
                srcs.append([])
                add.append(0)
                rem.append(0)
                rec.append(0)
            geom.append(F.geom_shape(pts, H, W))
            comps = F.components(pts) if pts else []
            ncc.append(len(comps))
            if comps and len(comps) <= 60:
                copy.append(round(sum(1 for x in comps if shape_key(x) in e['shapes']) / len(comps), 3))
            if pts:
                rs = [x[0] for x in pts]
                cs2 = [x[1] for x in pts]
                bbox.append([max(rs) - min(rs) + 1, max(cs2) - min(cs2) + 1])
            else:
                bbox.append([0, 0])
            if nu and e['masks']:
                best = 0.0
                for m in e['masks']:
                    i = int((m & u).sum())
                    if i:
                        best = max(best, i / int((m | u).sum()))
                jac.append(round(best, 3))
            elif nu:
                jac.append(0.0)
            if cs:
                colfound.append(round(sum(1 for c in cs if c in e['found'] or c in self.fixed_colors) / len(cs), 3))
        return dict(changed=changed, uncov=uncov, unpos=unpos, area=area, colors=colors, srcs=srcs, new=new, add=add, rem=rem, rec=rec, geom=geom, ncc=ncc, bbox=bbox,
                    same=all(e['same'] for e in self.ex), adj=adjs, encl=encl, onobj=onobj, rc=rcs, copy=copy, jac=jac, colfound=colfound,
                    xleft=xleft, xall=xall, xgeom=xgeom, xncc=xncc, xcol=xcol, xnew=xnew, xadj=xadj, xencl=xencl, xonobj=xonobj)


def table_summary(tb, salt_key, n_train):
    """Column types, frames, row counts, and the row shapes on train examples. Returns the summary and the dict of rows that Need.apply adds (None for a table with no Position or Color column). The salt is a table's own odd number, the same on every example, so that a table means one thing in a signature; it comes from salt_key."""
    types = [str(t) for t in tb['types']]
    frames = list(tb.get('frames') or [])
    widths = [4 if t in M.WIDE else 1 for t in types]
    offs = [0]
    for w in widths:
        offs.append(offs[-1] + w)
    xr = S.rows_with_models(tb, ROW_CAP)
    per = {}
    for ex, rows, n, asg, model, _ in xr:
        per.setdefault(tuple(ex), []).append((rows, n, len(asg)))
    pos_at = [offs[i] for i, t in enumerate(types) if t == POINT]
    col_at = [offs[i] for i, t in enumerate(types) if t == COLOR]
    nrows, geom, rel = [], [], []
    train = sorted(k for k in per if k[0] == 1) or sorted(per)
    # The Position column with the most distinct values on train examples.
    best, bestn = None, -1
    for a in pos_at:
        v = set()
        for k in train:
            for r in per[k][0][0]:
                v.add((k, tuple(r[a:a + 4])))
        if len(v) > bestn:
            best, bestn = a, len(v)
    wide_cols = [(offs[i], offs[i + 1]) for i in range(len(types))]
    for k in train:
        rows, n, _ = per[k][0]  # the first DET assignment or model of the example
        nrows.append(n)
        tup = [tuple(tuple(r[a:b]) if b - a > 1 else r[a] for a, b in wide_cols) for r in rows]
        rel.append(F.rel_shape(tup, types))
        if best is not None and rows:
            pts = {(r[best], r[best + 2]) for r in rows}
            r0 = rows[0]
            H, W = r0[best] + r0[best + 1] + 1, r0[best + 2] + r0[best + 3] + 1
            geom.append(F.geom_shape(pts, H, W))
        elif best is not None:
            geom.append('empty')
    adds = None
    if pos_at or col_at:
        adds = dict(pos_at=pos_at, col_at=col_at, salt=np.uint64(int(hashlib.sha256(salt_key.encode()).hexdigest()[:15], 16) * 2 + 1), items=[])
        for k in sorted(per):
            for rows, _, _ in per[k]:
                if not rows:
                    continue
                if k[0] == 1 and k[1] < n_train:
                    adds['items'].append(('x', k[1], np.array(rows, dtype=np.int64)))
                elif k[0] == 0:
                    adds['items'].append(('c', 0, {r[a] for r in rows for a in col_at}))
    nas = max((x[2] for v in per.values() for x in v), default=0)
    nent = max((len(v) for v in per.values()), default=0)
    return dict(labels=[str(x) for x in tb['labels']], types=types, frames=frames, nrows=nrows, geom=geom, rel=rel, ngeom=F.modal(geom), nrel=F.modal(rel), ndet=nas, nmodels=nent), adds


HEAD = re.compile(r'\((\S+)\s+(&\S+)\s*(\(|[^\s()]+)?')


def cut_keys(prog, key, seed):
    """The forms before key in the seed's order of the non-descendants of key and key: the scope of features_dagc_points.py."""
    order = prog.random_order(seed, prog.non_descendants(key) | {key})
    return order[:order.index(key)]


def one(task, source, gold_lines, need_grids, out):
    """Replays one task. out: lists 'form', 'state', 'task' of the rows to write."""
    t_start = time.perf_counter()
    train, test = need_grids
    prog = DO.ProgramDag(gold_lines)
    line_id = {DO.parse(x)[1]: i for i, x in enumerate(gold_lines) if not x.startswith('(OUT')}
    keys = prog.canonical_order([k for k in prog.lines if k != 'OUT'])
    lines = [prog.lines[k] for k in keys] + ([prog.lines['OUT']] if 'OUT' in prog.lines else [])
    text = '\n'.join(lines)
    sess, st = PR.session_of(task, 1024)
    gp = arclog.StudyProgram.from_sexp(text, st)
    ids, model, paths = gp.decode_stream()
    dec = sess.decoder()
    V = dec.vocabulary
    forms = PR.forms_of(V, ids, model, paths)
    need = Need(train)
    owner = {}  # relation token -> (form key, place in the form's declared relations)
    adds = {}   # form key -> rows to add to a state, one dict per table of the form
    rec = {}    # form key -> its form row
    before = None
    fault = None
    for f in sorted(forms):
        idx, decl, reads = forms[f]
        first = ids[idx[0]]
        if first == live.OUT_TOK or V.name(first) == 'OUT':
            break
        line = lines[f] if f < len(lines) else ''
        key = keys[f]
        m = HEAD.match(line)
        kind, third = (m.group(1), m.group(3)) if m else (V.name(first), None)
        comp = third if third and third != '(' else None
        toks = [ids[i] for i in idx if model[i]]
        ru = []
        for tok, cols in S.atom_uses(V, toks):
            k = V.kind(tok)
            nm = V.name(tok)
            own = owner.get(tok) if k == 'relation' else None
            ru.append([nm, k, own[0] if own else None, own[1] if own else None, {V.name(c) if isinstance(c, int) else str(c): how for c, how in cols.items()}])
        row = dict(task=task, key=key, form=prog.content[key], line_id=line_id.get(key), kind=kind, source=source, text=line, comp=comp, reads=ru, nid=len(idx))
        t0 = time.perf_counter()
        tables = []
        adds[key] = []
        try:
            new = []
            for i in idx:
                if model[i]:
                    new += [t for t in dec.step(ids[i])[0] if V.kind(t) == 'relation']
                    if before is None:
                        before = arclog.step_tables(dec, 'live', 'live', True, None)
            before = arclog.step_tables(dec, 'live', 'live', True, before)
            for i, t in enumerate(new):
                owner[t] = (key, i)
            t_step = time.perf_counter() - t0
            t1 = time.perf_counter()
            slot_ord = {M.slot_no(V.name(t)): i for i, t in enumerate(new)}
            row['slots'] = [M.slot_no(V.name(t)) for t in new]
            for n, (s_, j) in enumerate(PR.relation_tables(before)):
                try:
                    tb = S.parse_table(PR.OneTable(before, j))
                except M.Fail as e:
                    h = getattr(e, 'header', None)
                    tables.append(dict(ord=slot_ord.get(s_), fail=str(e)[:120], types=(h or {}).get('types')))
                    continue
                d, ad = table_summary(tb, '%s|%d|%s' % (prog.content[key], n, slot_ord.get(s_)), len(need.ex))
                d['ord'] = slot_ord.get(s_)
                tables.append(d)
                if ad is not None:
                    adds[key].append(ad)
            row['t_table'] = round(time.perf_counter() - t1, 6)
            row['t_step'] = round(t_step, 6)
        except Exception as e:  # noqa: BLE001
            fault = '%s: %s' % (type(e).__name__, str(e)[:200])
            row['fault'] = fault
        row['tables'] = tables
        out['form'].append(row)
        rec[key] = row
        if fault:
            break
    # states: the cut of each target, for each seed
    skipped = 0
    for key, row in rec.items():
        if row['kind'] not in L.KINDS or row.get('fault'):
            continue
        for seed in SEEDS:
            scope = cut_keys(prog, key, seed)
            if any(k not in rec or rec[k].get('fault') for k in scope):
                skipped += 1
                continue
            need.reset()
            for k in scope:
                for ad in adds[k]:
                    need.apply(ad)
            t0 = time.perf_counter()
            state = need.facts()
            out['state'].append(dict(task=task, key=key, form=row['form'], kind=row['kind'], seed=seed, scope=scope, scope_id=DO.short(''.join(sorted(prog.content[k] for k in scope)), 16), state=state, t_need=round(time.perf_counter() - t0, 6)))
    need.reset()
    start = need.facts()
    out['task'].append(dict(task=task, source=source, forms=len(rec), lines=len(lines), fault=fault, states_skipped=skipped, seconds=round(time.perf_counter() - t_start, 3), static=need.static(), start=start))
    return len(rec)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', required=True)
    ap.add_argument('--split', default='fit')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--seconds', type=float)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    k, n = map(int, a.shard.split('/'))
    tx = texts(a.split)
    names = sorted(tx)
    if a.only:
        names = [t for t in names if t in a.only]
    names = names[k::n]
    path = {x: '%s/%s-rows-%s-%d.jsonl' % (a.out, x, a.split, k) for x in ('form', 'state', 'task')}
    done = set()
    if os.path.exists(path['task']):
        with open(path['task']) as f:
            done = {json.loads(x)['task'] for x in f}
    names = [t for t in names if t not in done]
    if a.limit:
        names = names[:a.limit]
    t0 = time.time()
    forms = 0
    with open(path['form'], 'a') as fo, open(path['state'], 'a') as fs, open(path['task'], 'a') as ft:
        for i, t in enumerate(names):
            if a.seconds and time.time() - t0 > a.seconds:
                print('stopped: budget spent', flush=True)
                break
            out = dict(form=[], state=[], task=[])
            try:
                forms += one(t, tx[t][0], tx[t][1], grids(t), out)
            except Exception as e:  # noqa: BLE001
                out = dict(form=[], state=[], task=[dict(task=t, source=tx[t][0], forms=0, fault='%s: %s' % (type(e).__name__, str(e)[:300]))])
            for x, f in (('form', fo), ('state', fs), ('task', ft)):
                for r in out[x]:
                    f.write(json.dumps(r, separators=(',', ':')) + '\n')
                f.flush()
            el = time.time() - t0
            rate = (i + 1) / el
            if (i + 1) % 10 == 0 or i + 1 == len(names) or a.limit:
                print('%d/%d tasks, %d forms, %.2f tasks/s, eta %.0f s' % (i + 1, len(names), forms, rate, (len(names) - i - 1) / rate), flush=True)


if __name__ == '__main__':
    main()
