"""Need per candidate: one row per table of each gold form, with how far that table goes toward what the output needs.

  gold_tables_env.sh candidate_rows.py --out DIR --split fit|held [--shard K/N] [--only TASK ...] [--limit N]

The replay is the one of next_form_rows.py, with the test output removed. A table's facts read only its own rows and the train outputs. Facts of the hole come later, in candidate_model.py.

On train examples, per example, then the mean:
  pos_rec   of the changed cells, the share that a Position column of the table holds, best column
  pos_prec  of that column's cells, the share that are changed cells
  pc_rec    of the changed cells, the share that a Position and Color pair of columns gets right, best pair
  pc_prec   of that pair's rows, the share whose color is the output's
  col_cov   of the colors of the changed cells, the share a Color column of the table holds
  x_gain    of the changed cells, the share that the table takes from unexplained to explained, one train example left out, against the input alone

With --distract K, a task's row also holds the tables of K other fit tasks' programs run on this task's grids, up to 12 forms each, in DIR/candidate-rows-distract-<split>-<K>.jsonl.

Output: DIR/candidate-rows-<split>-<K>.jsonl, one row per task, flushed. A rerun skips finished tasks. It prints a rate and an ETA.
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-backward-from-out-content-heldout37'  # the data folder
sys.path.insert(0, HERE)
import next_form_rows as R  # noqa: E402
from next_form_rows import M, PR, S, arclog, live  # noqa: E402


def mean(xs):
    return round(float(np.mean(xs)), 3) if xs else None


def table_need(tb, train):
    """The facts of one parsed table."""
    types = [str(t) for t in tb['types']]
    widths = [4 if t in M.WIDE else 1 for t in types]
    offs = [0]
    for w in widths:
        offs.append(offs[-1] + w)
    pos_at = [offs[i] for i, t in enumerate(types) if t == R.POINT]
    col_at = [offs[i] for i, t in enumerate(types) if t == R.COLOR]
    per = {}
    for ex, rows, n, asg, model, _ in S.rows_with_models(tb, R.ROW_CAP):
        per.setdefault(tuple(ex), rows)
    pr, pp, cr, cp, cc = [], [], [], [], []
    need = R.Need(train)
    need.new_salt()
    for i, (inp, out) in enumerate(train):
        rows = per.get((1, i))
        same = inp.shape == out.shape
        changed = (out != inp) if same else np.ones(out.shape, dtype=bool)
        H, W = out.shape
        nch = int(changed.sum())
        if rows is None or not len(rows):
            pr.append(0.0)
            pp.append(0.0)
            cr.append(0.0)
            cp.append(0.0)
            cc.append(0.0)
            continue
        arr = np.array(rows, dtype=np.int64)
        need.add(i, arr, pos_at, col_at)
        br = bp = bc = bq = 0.0
        for a in pos_at:
            r, b, c, x = arr[:, a], arr[:, a + 1], arr[:, a + 2], arr[:, a + 3]
            ok = (r >= 0) & (c >= 0) & (r < H) & (c < W) & (r + b + 1 == H) & (c + x + 1 == W)
            if not ok.any():
                continue
            m = np.zeros((H, W), dtype=bool)
            m[r[ok], c[ok]] = True
            hit = int((m & changed).sum())
            rec = hit / nch if nch else 0.0
            pre = hit / int(m.sum())
            if (rec, pre) > (br, bp):
                br, bp = rec, pre
            for k in col_at:
                right = out[r[ok], c[ok]] == arr[ok, k]
                g = np.zeros((H, W), dtype=bool)
                g[r[ok][right], c[ok][right]] = True
                rc = int((g & changed).sum()) / nch if nch else 0.0
                qc = float(right.mean())
                if (rc, qc) > (bc, bq):
                    bc, bq = rc, qc
        pr.append(br)
        pp.append(bp)
        cr.append(bc)
        cp.append(bq)
        want = set(out[changed].tolist())
        have = {int(v) for k in col_at for v in arr[:, k].tolist()}
        cc.append(len(want & have) / len(want) if want else 0.0)
    base = R.Need(train)
    left0 = sum(int((e['changed'] & ~g).sum()) for e, g in zip(base.ex, base.explained()))
    left1 = sum(int((e['changed'] & ~g).sum()) for e, g in zip(need.ex, need.explained()))
    tot = sum(int(e['changed'].sum()) for e in need.ex) or 1
    return dict(types=types, labels=[str(x) for x in tb['labels']], pos_rec=mean(pr), pos_prec=mean(pp), pc_rec=mean(cr), pc_prec=mean(cp), col_cov=mean(cc), x_gain=round((left0 - left1) / tot, 3))


def distractors(task, pool, k=2):
    """The texts of k other fit tasks, by a hash of the two names. Their tables on this task's grids stand for tables a search holds that gold doesn't read."""
    others = sorted((t for t in pool if t != task), key=lambda t: hashlib.sha1((task + t).encode()).hexdigest())
    return others[:k]


def foreign(task, text, train, cap=12):
    """Tables of another task's program on this task's grids, up to cap forms, as far as the program runs here."""
    try:
        return one(task, text, train, cap)[0]
    except Exception:  # noqa: BLE001
        return []


def one(task, text, train, cap=None):
    lines = [x for x in text.splitlines() if x.strip()]
    sess, st = PR.session_of(task, 1024)
    gp = arclog.StudyProgram.from_sexp(text, st)
    ids, model, paths = gp.decode_stream()
    dec = sess.decoder()
    V = dec.vocabulary
    forms = PR.forms_of(V, ids, model, paths)
    before = None
    out = []
    ms = []
    for f in sorted(forms):
        idx, decl, reads = forms[f]
        first = ids[idx[0]]
        if first == live.OUT_TOK or V.name(first) == 'OUT' or (cap is not None and f >= cap):
            break
        new = []
        try:
            for i in idx:
                if model[i]:
                    new += [t for t in dec.step(ids[i])[0] if V.kind(t) == 'relation']
                    if before is None:
                        before = arclog.step_tables(dec, 'live', 'live', True, None)
            before = arclog.step_tables(dec, 'live', 'live', True, before)
        except Exception:  # noqa: BLE001
            if cap is None:
                raise
            break
        slot_ord = {M.slot_no(V.name(t)): i for i, t in enumerate(new)}
        for s, j in PR.relation_tables(before):
            try:
                tb = S.parse_table(PR.OneTable(before, j))
            except M.Fail:
                continue
            t0 = time.perf_counter()
            d = table_need(tb, train)
            ms.append(round((time.perf_counter() - t0) * 1000, 2))
            d['form'] = f
            d['kind'] = lines[f].split()[0].lstrip('(') if f < len(lines) else None
            d['ord'] = slot_ord.get(s)
            out.append(d)
    return out, ms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--split', default='fit')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--distract', type=int, default=0)
    a = ap.parse_args()
    fit_text = R.texts('fit') if a.distract else {}
    pool = sorted(fit_text)
    os.makedirs(a.out, exist_ok=True)
    k, n = map(int, a.shard.split('/'))
    tx = R.texts(a.split)
    names = sorted(tx)
    if a.only:
        names = [t for t in names if t in a.only]
    names = names[k::n]
    path = '%s/candidate-rows-%s-%d.jsonl' % (a.out, a.split, k)
    if a.distract:
        path = '%s/candidate-rows-distract-%s-%d.jsonl' % (a.out, a.split, k)
    done = set()
    if os.path.exists(path):
        with open(path) as f:
            done = {json.loads(x)['task'] for x in f}
    names = [t for t in names if t not in done]
    if a.limit:
        names = names[:a.limit]
    t0 = time.time()
    with open(path, 'a') as fo:
        for i, t in enumerate(names):
            try:
                g = R.grids(t)[0]
                tables, ms = one(t, tx[t][1], g)
                extra = []
                if a.distract:
                    for o in distractors(t, pool, a.distract):
                        extra += foreign(t, fit_text[o][1], g)
                fo.write(json.dumps(dict(task=t, tables=tables, ms=ms, distract=extra), separators=(',', ':')) + '\n')
            except Exception as e:  # noqa: BLE001
                fo.write(json.dumps(dict(task=t, tables=[], ms=[], fault='%s: %s' % (type(e).__name__, str(e)[:200])), separators=(',', ':')) + '\n')
            fo.flush()
            rate = (i + 1) / (time.time() - t0)
            if (i + 1) % 20 == 0 or i + 1 == len(names):
                print('%d/%d tasks, %.1f tasks/s, eta %.0f s' % (i + 1, len(names), rate, (len(names) - i - 1) / rate), flush=True)


if __name__ == '__main__':
    main()
