"""One row per gold form in gold's order: the targets of the next form, and the state before it.

The state is the task's grids plus gold's earlier forms with their tables, stepped on the engine with the test output removed. It is an upper bound on what a search has found.

Text of a stem:
  held stems (the 37) and dev stems (the other 62 of the 99): census-bands-cheapest/texts.json, the lines each census row reads.
  fit stems: gold-v3-cover-forms-a036da074/corpus-view, first pair.

  gold_tables_env.sh next_form_rows.py --out DIR [--split held|dev|fit] [--shard K/N] [--only TASK ...] [--limit N]

Output: DIR/form-rows-<split>-<K>.jsonl and DIR/task-rows-<split>-<K>.jsonl, flushed per task. A rerun skips a task with a task row.
"""
import argparse
import gzip
import json
import os
import re
import sys
import time

import numpy as np
from scipy import ndimage as ndi

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-backward-from-out-content-heldout37'  # the data folder
sys.path.insert(0, HERE)
import shape_facts as F  # noqa: E402

import live  # noqa: E402
import pool_rows as PR  # noqa: E402
from live import M, S, arclog  # noqa: E402

D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
CENSUS = D + 'census/census-bands-cheapest/'
VIEW = D + 'gold/gold-v3-cover-forms-a036da074/corpus-view/'
HELD = open(D + 'sampler/sampler-worker/held/tasks.txt').read().split()
EVAL = open(D + 'features-worker/arm/eval-tasks.txt').read().split()
ROW_CAP = 20000
POINT = 'Position'
COLOR = 'Color'


def texts(split):
    if split in ('held', 'dev'):
        st = json.load(open(CENSUS + 'texts.json'))['stems']
        names = HELD if split == 'held' else [t for t in EVAL if t not in HELD]
        out = {}
        for t in names:
            lines = st[t]['lines']
            if not any(x.startswith('(OUT') for x in lines) and st[t].get('out'):
                lines = lines + [st[t]['out']]
            out[t] = ('census:' + st[t]['source'], '\n'.join(lines))
        return out
    out = {}
    ev = set(EVAL)
    for e in sorted(os.scandir(VIEW), key=lambda e: e.name):
        if e.name not in ev:
            with gzip.open(e.path + '/pairs.jsonl.gz', 'rt') as f:
                out[e.name] = ('cover-view', json.loads(f.readline())['gold_sexp'])
    return out


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
        self.fixed_colors = set()
        self.salt = np.uint64(1)
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
            self.ex.append(dict(inp=inp, out=out, same=same, changed=changed, cc=np.zeros(out.shape, dtype=bool), pc=np.zeros(out.shape, dtype=bool), bg=bg, incol=set(np.unique(inp).tolist()),
                                fg=fg, enclosed=enclosed, adj=adj, rc=rc, shapes=shapes, bbs=bbs, nobj=nobj, masks=[], found=set(), sig=np.zeros(out.shape, dtype=np.uint64)))
        self.rng = np.random.default_rng(1)

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

    def add(self, i, arr, pos_at, col_at):
        """arr: rows of one table at train example i. pos_at, col_at: the offset of each Position and Color column."""
        e = self.ex[i]
        H, W = e['out'].shape
        salt = self.salt
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

    def add_fixed(self, vals):
        self.fixed_colors.update(vals)

    def new_salt(self):
        """A table's own odd number, the same on every example, so that a table means one thing in a signature."""
        self.salt = np.uint64(int(self.rng.integers(1, 2 ** 62)) * 2 + 1)

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


def table_summary(tb, need):
    """Column types, frames, row counts, and the row shapes on train examples. Adds the table's rows to need."""
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
    if need is not None and (pos_at or col_at):
        need.new_salt()
        for k in sorted(per):
            for rows, _, _ in per[k]:
                if not rows:
                    continue
                if k[0] == 1 and k[1] < len(need.ex):
                    need.add(k[1], np.array(rows, dtype=np.int64), pos_at, col_at)
                elif k[0] == 0:
                    need.add_fixed({r[a] for r in rows for a in col_at})
    nas = max((x[2] for v in per.values() for x in v), default=0)
    nent = max((len(v) for v in per.values()), default=0)
    return dict(labels=[str(x) for x in tb['labels']], types=types, frames=frames, nrows=nrows, geom=geom, rel=rel, ngeom=F.modal(geom), nrel=F.modal(rel), ndet=nas, nmodels=nent)


HEAD = re.compile(r'\((\S+)\s+(&\S+)\s*(\(|[^\s()]+)?')


def one(task, source, text, need_grids, fo, ft):
    t_start = time.perf_counter()
    train, test = need_grids
    lines = [x for x in text.splitlines() if x.strip()]
    sess, st = PR.session_of(task, 1024)
    gp = arclog.StudyProgram.from_sexp(text, st)
    ids, model, paths = gp.decode_stream()
    dec = sess.decoder()
    V = dec.vocabulary
    forms = PR.forms_of(V, ids, model, paths)
    need = Need(train)
    owner = {}
    before = None
    nf = 0
    fault = None
    for f in sorted(forms):
        idx, decl, reads = forms[f]
        first = ids[idx[0]]
        if first == live.OUT_TOK or V.name(first) == 'OUT':
            break
        line = lines[f] if f < len(lines) else ''
        m = HEAD.match(line)
        kind, name, third = (m.group(1), m.group(2), m.group(3)) if m else (V.name(first), None, None)
        comp = third if third and third != '(' else None
        t0 = time.perf_counter()
        state = need.facts()
        if f == 0:
            state['static'] = need.static()
        t_need = time.perf_counter() - t0
        toks = [ids[i] for i in idx if model[i]]
        ru = []
        for tok, cols in S.atom_uses(V, toks):
            k = V.kind(tok)
            nm = V.name(tok)
            own = owner.get(tok) if k == 'relation' else None
            ru.append([nm, k, own[0] if own else None, own[1] if own else None, {V.name(c) if isinstance(c, int) else str(c): how for c, how in cols.items()}])
        row = dict(task=task, form=f, kind=kind, source=source, text=line, comp=comp, reads=ru, nid=len(idx), state=state, t_need=round(t_need, 6))
        t0 = time.perf_counter()
        tables = []
        try:
            new = []
            for i in idx:
                if model[i]:
                    new += [t for t in dec.step(ids[i])[0] if V.kind(t) == 'relation']
                    if before is None:
                        before = arclog.step_tables(dec, 'live', 'live', True, None)
            before = arclog.step_tables(dec, 'live', 'live', True, before)
            for i, t in enumerate(new):
                owner[t] = (f, i)
            t_step = time.perf_counter() - t0
            t1 = time.perf_counter()
            slot_ord = {M.slot_no(V.name(t)): i for i, t in enumerate(new)}
            for s, j in PR.relation_tables(before):
                try:
                    tb = S.parse_table(PR.OneTable(before, j))
                except M.Fail as e:
                    h = getattr(e, 'header', None)
                    tables.append(dict(ord=slot_ord.get(s), fail=str(e)[:120], types=(h or {}).get('types')))
                    continue
                d = table_summary(tb, need)
                d['ord'] = slot_ord.get(s)
                tables.append(d)
            row['t_table'] = round(time.perf_counter() - t1, 6)
            row['t_step'] = round(t_step, 6)
        except Exception as e:  # noqa: BLE001
            fault = '%s: %s' % (type(e).__name__, str(e)[:200])
            row['fault'] = fault
        row['tables'] = tables
        fo.write(json.dumps(row, separators=(',', ':')) + '\n')
        nf += 1
        if fault:
            break
    final = need.facts()
    ft.write(json.dumps(dict(task=task, source=source, forms=nf, lines=len(lines), fault=fault, seconds=round(time.perf_counter() - t_start, 3), final=final), separators=(',', ':')) + '\n')
    fo.flush()
    ft.flush()
    return nf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--split', default='fit')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    k, n = map(int, a.shard.split('/'))
    tx = texts(a.split)
    names = sorted(tx)
    if a.only:
        names = [t for t in names if t in a.only]
    names = names[k::n]
    pt = '%s/task-rows-%s-%d.jsonl' % (a.out, a.split, k)
    done = set()
    if os.path.exists(pt):
        with open(pt) as f:
            done = {json.loads(x)['task'] for x in f}
    names = [t for t in names if t not in done]
    if a.limit:
        names = names[:a.limit]
    t0 = time.time()
    forms = 0
    with open('%s/form-rows-%s-%d.jsonl' % (a.out, a.split, k), 'a') as fo, open(pt, 'a') as ft:
        for i, t in enumerate(names):
            try:
                forms += one(t, tx[t][0], tx[t][1], grids(t), fo, ft)
            except Exception as e:  # noqa: BLE001
                ft.write(json.dumps(dict(task=t, source=tx[t][0], forms=0, fault='%s: %s' % (type(e).__name__, str(e)[:300])), separators=(',', ':')) + '\n')
                ft.flush()
            el = time.time() - t0
            rate = (i + 1) / el
            if (i + 1) % 10 == 0 or i + 1 == len(names):
                print('%d/%d tasks, %d forms, %.1f tasks/s, eta %.0f s' % (i + 1, len(names), forms, rate, (len(names) - i - 1) / rate), flush=True)


if __name__ == '__main__':
    main()
