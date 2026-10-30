"""Measure the detectors of detectors.py on lists of the gold continuation against its mutants
(work/lm/data-study/mutants.py), beside the same measurement on the lists of the gold against the LM's samples.

    work/lm/.venv/bin/python work/lm/data-study/detectors_mut.py [--mut-export DIR] [--mut-parquet FILE]
        [--counts DIR] [--export DIR] [--parquet FILE] [--data DIR] [--out FILE] [--all-tasks]
        [--ready-parquet FILE --ready-export DIR]

--mut-parquet (default work/lm/data-study/detectors-mut.parquet) is `detectors.py compute` of the mutant export
--mut-export (default work/lm/rollouts-mut/export); --parquet (default work/lm/data-study/detectors.parquet) is that of
--export (default work/lm/rollouts-s2/export); --counts (default work/lm/rollouts-mut/counts) holds mutants.py's
counts. Each parquet is read with the marks of its export joined (`detectors.read_marked`), so the filter
f_independent takes the marks file as it is now. The split is that of --data's cases.npz, as in `detectors.py measure`.

Each score is measured as `detectors.py measure` measures it (encoder.value_draw_metrics at position 0, label
`solving`, variants "graded" and "all"), on three sets of held-out lists: "LM", the rollouts-s2 lists; "mutant",
the mutant lists; "mutant, rows differ", the mutant lists less the mutants whose first table after the branch is
faulted, unseen, empty in every train example, or has the same rows as the gold's. A graded signal's sign, the
median that fills its missing values, and every fit marked "trained on LM" come from the rollouts-s2 lists of the
training tasks (gold against LM). "5-fold on the set" fits the logistic on the lists of four fifths of the
held-out tasks of the set and measures it on the rest, the folds drawn by task as in `detectors.py measure`.

With --ready-parquet and --ready-export (the parquet and the export of the set `ready` of allpoints.py), each
variant also gives the rows under READY_LABEL (`ready_block`): the positives of a branch point are the gold and the
ready members of that point (the ready clauses of reorder.py), the pairs are each positive against each negative,
each positive's pairs weighted 1/(the positives), and a negative whose first table has the rows_hash of a positive
of its point is left out.

A member's first table after the branch is classed, in this order: none (no Table at position 0); faulted (some
Table of it faults); unseen (some Table unseen); empty (every Table empty in every train example); same rows (the
sorted `rows_hash` of its Tables equal the gold's); differs.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[0]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse, contextlib, io, json, random, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = MAIN_ROOT
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pinned   # noqa: E402
pinned.use()   # the pinned model/ modules (pinned.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import detectors as D   # noqa: E402
import encoder as E   # noqa: E402
import value_eval as VE   # noqa: E402

FEATS = D.SCORED


def prepare(df):
    df = D.with_factors(df.copy())
    df["n_types"] = df["types"].map(lambda t: len(t.split(",")) if t else 0).astype(float)
    for c in D.DETECTORS:
        df[c] = df[c].astype(float) if c in df else np.nan   # a parquet older than the detector lacks it
    return df


def fit_logistic(x, y, steps=300, seed=0):
    """detectors.fit_logistic, the same numbers by fewer operations: the standardized matrix made once, and each step's
    gradient and Adam update written out as autograd and torch.optim.Adam (on the CPU, its defaults) compute them."""
    import torch, torch.nn as nn
    F = nn.functional
    x, y = torch.tensor(x, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)
    mu, sd = x.mean(0), x.std(0).clamp_min(1e-6)
    xs = (x - mu) / sd
    torch.manual_seed(seed)
    lin = nn.Linear(x.shape[1], 1)
    w, b = lin.weight.detach().clone(), lin.bias.detach().clone()
    moments = [(w, torch.zeros_like(w), torch.zeros_like(w)), (b, torch.zeros_like(b), torch.zeros_like(b))]
    lr, beta1, beta2, eps = 0.05, 0.9, 0.999, 1e-8
    with torch.no_grad():
        for t in range(1, steps + 1):
            z = F.linear(xs, w, b).squeeze(-1)
            g = ((z.sigmoid() - y) / y.numel()).unsqueeze(-1)   # the gradient of the mean loss at z
            for p, grad, m, v in ((w, g.t().mm(xs), *moments[0][1:]), (b, g.sum(0), *moments[1][1:])):
                m.lerp_(grad, 1 - beta1)
                v.mul_(beta2).addcmul_(grad, grad, value=1 - beta2)
                p.addcdiv_(m, (v.sqrt() / (1 - beta2 ** t) ** 0.5).add_(eps), value=-(lr / (1 - beta1 ** t)))
        loss = F.binary_cross_entropy_with_logits(z, y)   # at the last step, before its update
    def predict(z):
        with torch.no_grad():
            return F.linear((torch.tensor(z, dtype=torch.float32) - mu) / sd, w, b).squeeze(-1).numpy()
    return predict, float(loss.item()), np.where(sd.numpy() > 1e-6, w.numpy().ravel(), np.nan)


def fit_apply(tr, tr_members, te, cols):
    """fit_logistic on the listed Tables of `tr_members` (frame tr) over `cols`, applied to every Table of te; a
    missing value takes the training mean. A column with no value at the training Tables is left out."""
    ti = D.tr_idx_pos(tr, D.listed(tr, tr_members))
    cols = [c for c in cols if tr[c].iloc[ti].notna().any()]
    X = tr[cols].to_numpy(float)
    mu = np.nanmean(X[ti], 0)
    mu = np.where(np.isnan(mu), 0.0, mu)
    fill = lambda A: np.where(np.isnan(A), mu, A)
    pred, _, _ = fit_logistic(fill(X[ti]), tr["solving"].to_numpy(float)[ti])
    return pd.Series(pred(fill(X if te is tr else te[cols].to_numpy(float))), index=te.index)


def fit_apply_trivial(tr, tr_members, te):
    """fit_logistic of value_eval.features on the listed Tables of `tr_members` (frame tr), applied to te's Tables at
    position 0, which the lists read; missing at the other Tables."""
    if te.empty:
        return pd.Series(dtype=float, index=te.index)
    ti = D.tr_idx_pos(tr, D.listed(tr, tr_members))
    TFtr = np.array([VE.features(D.Stub(r), r) for r in tr[D.STUB_COLUMNS].iloc[ti].to_dict("records")], float)
    p0 = np.flatnonzero(te["position"].to_numpy() == 0)
    # zeros at the other Tables keep the product over every Table, so its values at position 0 are as computed over all
    TFte = np.zeros((len(te), TFtr.shape[1]))
    TFte[p0] = [VE.features(D.Stub(r), r) for r in te[D.STUB_COLUMNS].iloc[p0].to_dict("records")]
    pred, _, _ = fit_logistic(TFtr, tr["solving"].to_numpy(float)[ti])
    out = np.full(len(te), np.nan, np.float32)
    out[p0] = pred(TFte)[p0]
    return pd.Series(out, index=te.index)


def scored_lists(members, score):
    """{group: [(solving, member score, case)]} of the members that have a listed Table, as D.metrics forms them."""
    by = {}
    for m, z in zip(members, D.member_scores(members, score)):
        sel = D.listed_at(m)
        if sel:
            by.setdefault(m["group"], []).append((bool(m["records"][sel[0]]["solving"]), float(np.mean(z[sel])),
                                                  m["case"]))
    return by


def ranked_groups(df):
    """The branch points (groups) of frame df whose list at position 0 is ranked: it holds a solving and a
    non-solving listed member."""
    ms = D.members_of(df[df["position"] == 0])
    by = {}
    for m in ms:
        sel = D.listed_at(m)
        if sel:
            by.setdefault(m["group"], set()).add(bool(m["records"][sel[0]]["solving"]))
    return {g for g, v in by.items() if len(v) == 2}


def in_groups(df, groups):
    key = list(zip(df["task"], df["corpus_case"], df["prefix_tokens"].astype(int)))
    return df[np.array([k in groups for k in key], bool)]


def list_acc(members, score):
    """Pairwise ranking accuracy with each ranked list weighted equally, not each pair."""
    accs = []
    for xs in scored_lists(members, score).values():
        pos = [x[1] for x in xs if x[0]]; neg = [x[1] for x in xs if not x[0]]
        if pos and neg:
            d = np.subtract.outer(pos, neg)
            accs.append(float((d > 0).sum() + 0.5 * (d == 0).sum()) / d.size)
    return float(np.mean(accs)) if accs else None


def dropped_pairs(te, cls):
    """{class: pairs} of the pairs of te's ranked lists (variant graded, position 0) that hold a member whose class
    is not `differs`, by that member's class (a gold's pair against a dropped mutant counts under the mutant's)."""
    ms = D.members_of(te[te["position"] == 0])
    for m, c in zip(ms, te.loc[[m["rows"][0] for m in ms], "case"].tolist()):
        m["case"] = c
    out = Counter()
    by = {}
    for m in ms:
        sel = D.listed_at(m)
        if sel:
            by.setdefault(m["group"], []).append((bool(m["records"][sel[0]]["solving"]), m["case"]))
    for xs in by.values():
        for yp, cp in xs:
            if not yp:
                continue
            for yn, cn in xs:
                if yn:
                    continue
                bad = [c for c in (cp, cn) if not c.endswith("__gold") and cls.get(c, "none") != "differs"]
                if bad:
                    out["solving mutant" if bad[0] == cp else cls.get(bad[0], "none")] += 1
    return out


def evaluate(tr, te, name, quick=False, extra=(), per_task=False, ready=False):
    """{score name: metrics} of every score on the held-out lists of frame te, trained on tr's lists; with `quick`,
    only the scores of the loop (`-(sum of filters)`, trivial features, the column count and the logistic trained on
    LM, the logistic 5-fold on the set) and the single detectors of `extra`. With `per_task` (variant graded lists),
    also `logistic, 5-fold on the set, per task` and `logistic, 5-fold on the set, equal factor width, per task`:
    `task_weighted` of the 5-fold logistic's folds. With `ready` (te from `with_ready`), every score is measured by
    `ready_metrics`, the trivial features as in the variant all, and there are no rows of equal width or per task."""
    keep_all = name == "all"
    metric = ready_metrics if ready else D.metrics
    p0tr, p0te = tr[tr["position"] == 0], te[te["position"] == 0]
    trm = D.members_of(p0tr, keep_all)
    tem = D.members_of(p0te, keep_all)
    for m, c in zip(tem, te.loc[[m["rows"][0] for m in tem], "case"].tolist()):
        m["case"] = c
    tr_idx = D.listed(tr, trm)
    res = {}
    for f in [] if quick else D.FILTERS:
        res["-" + f] = metric(tem, -te[f])
    res["-(sum of filters)"] = metric(tem, -te[D.FILTERS].sum(axis=1))
    for g in list(extra) if quick else D.GRADED + D.ADDED:
        known = tr.loc[tr_idx, g]
        med = float(np.nanmedian(known)) if known.notna().any() else 0.0
        trs = D.metrics(trm, tr[g].fillna(med))["pair_acc"]
        sign = -1.0 if trs is not None and trs < 0.5 else 1.0
        res[("-" if sign < 0 else "+") + g] = metric(tem, sign * te[g].fillna(med))
    if name == "graded" and not ready:
        trs_m = D.members_of(tr, keep_all=False, stubs=True)
        trs_m = [m for m in trs_m if m["group"] in {x["group"] for x in trm}]
        tes_m = D.members_of(te, keep_all=False, stubs=True)
        with contextlib.redirect_stdout(io.StringIO()):
            sc = VE.logistic(trs_m, tes_m, 1, 300, 0, "solving")
        res["trivial features"] = E.value_draw_metrics(tes_m, [sc], 1, label="solving")
    else:
        res["trivial features"] = metric(tem, fit_apply_trivial(tr, trm, te))
    res["column count, trained on LM"] = metric(tem, fit_apply(tr, trm, te, ["n_columns"]))
    lsc = fit_apply(tr, trm, te, FEATS)
    res["logistic, trained on LM"] = dict(metric(tem, lsc), pair_acc_lists=None if ready else list_acc(tem, lsc))
    # 5-fold cross-validation by task over te's lists
    tasks = sorted({m["task"] for m in tem})
    random.Random(0).shuffle(tasks)
    folds = [set(tasks[k::5]) for k in range(5)]
    accs = defaultdict(list)
    fold_scores = []   # (the fold's members, the 5-fold logistic's score) per fold
    for fold in folds:
        a = [m for m in tem if m["task"] not in fold]
        b = [m for m in tem if m["task"] in fold]
        if not D.listed(te, a) or not b:
            continue
        for key, cols in (("logistic, 5-fold on the set", FEATS), ("column count, 5-fold on the set", ["n_columns"]))[:1 if quick else 2]:
            sc = fit_apply(te, a, te, cols)
            if key == "logistic, 5-fold on the set":
                fold_scores.append((b, sc))
            r = dict(metric(b, sc), pair_acc_lists=None if ready else list_acc(b, sc))
            for k in ("pair_acc", "auc", "pair_acc_lists"):
                if r[k] is not None:
                    accs[(key, k)].append(r[k])
    if name == "graded" and not ready:
        res.update(equal_width(te, tem, res, lsc, fit_apply(tr, trm, te, ["n_columns"]), fold_scores))
        if per_task:
            res["logistic, 5-fold on the set, per task"] = task_weighted(te, fold_scores)
            res["logistic, 5-fold on the set, equal factor width, per task"] = task_weighted(te, fold_scores, "n_columns")
    for key in ("logistic, 5-fold on the set", "column count, 5-fold on the set")[:1 if quick else 2]:
        res[key] = dict(pair_acc=float(np.mean(accs[(key, "pair_acc")])) if accs[(key, "pair_acc")] else None,
                        auc=float(np.mean(accs[(key, "auc")])) if accs[(key, "auc")] else None,
                        pairs=None, ranked_lists=None, lists=None,
                        pair_acc_lists=float(np.mean(accs[(key, "pair_acc_lists")])) if accs[(key, "pair_acc_lists")] else None,
                        folds=accs[(key, "pair_acc")])
    return res


def task_weighted(te, fold_scores, key=None):
    """The pair accuracy with each task weighted equally, over the folds `fold_scores` ([(the fold's members, the
    score fit without them)]): each task's pair accuracy over its pairs in its fold (with `key`, over only the pairs
    whose two members' position-0 Tables have the same value of the column `key`, `detectors.same_key_pairs`), then
    the mean over the tasks that have such pairs. {"pair_acc", "tasks": the count of those tasks}."""
    accs = []
    for b, sc in fold_scores:
        by = defaultdict(list)
        for m in b:
            by[m["task"]].append(m)
        for ms in by.values():
            if key is None:
                acc = D.metrics(ms, sc)["pair_acc"]
            else:
                right, n = same_key_pairs(te, sc, ms, key)
                acc = right / n if n else None
            if acc is not None:
                accs.append(acc)
    return dict(pair_acc=float(np.mean(accs)) if accs else None, tasks=len(accs))


def same_key_pairs(df, score, members, key):
    """detectors.same_key_pairs, each member's mean by numpy and not by a pandas Series: the same numbers."""
    by = {}
    rows = [m["rows"] for m in members]
    if not rows:
        return 0.0, 0
    at = np.concatenate(rows)
    sv = np.split(score.to_numpy(np.float64)[score.index.get_indexer(at)], np.cumsum([len(r) for r in rows])[:-1])
    kv = np.split(df[key].to_numpy()[df.index.get_indexer(at)], np.cumsum([len(r) for r in rows])[:-1])
    for m, z, kz in zip(members, sv, kv):
        sel = D.listed_at(m)
        if sel:
            mean = float(z[sel[0]]) if len(sel) == 1 else float(np.mean(z[sel]))
            by.setdefault(m["group"], []).append((m["solving"], mean, kz[sel[0]]))
    right, n = 0.0, 0
    for xs in by.values():
        for a in xs:
            for b in xs:
                if a[0] and not b[0] and a[2] == b[2]:
                    n += 1
                    right += (a[1] > b[1]) + 0.5 * (a[1] == b[1])
    return right, n


WIDTHS = (("factor width", "n_columns"), ("own width", "n_types"))
EQUAL_WIDTH = ["column count, trained on LM", "logistic, trained on LM", "logistic, 5-fold on the set"]


def equal_width(te, tem, res, lsc, csc, fold_scores):
    """{`<score>, equal <width>`: {pair_acc, pairs}} for the scores of EQUAL_WIDTH, over only the pairs whose
    solving and non-solving members' first tables have the same column count: the surviving factors' total width
    (`n_columns`, as `detectors.with_factors` gives it) or the Table's own count of column types (`n_types`). The
    5-fold row pools the pairs of every fold."""
    out = {}
    for wname, key in WIDTHS:
        for name, sc in (("column count, trained on LM", csc), ("logistic, trained on LM", lsc)):
            right, n = same_key_pairs(te, sc, tem, key)
            out[f"{name}, equal {wname}"] = dict(pair_acc=right / n if n else None, auc=None, pairs=n)
        right = n = 0
        for b, sc in fold_scores:
            r_, n_ = same_key_pairs(te, sc, b, key)
            right += r_; n += n_
        out[f"logistic, 5-fold on the set, equal {wname}"] = dict(pair_acc=right / n if n else None, auc=None, pairs=n)
    return out


def feature_rows(tr, te, feats):
    """{feature: {...}} for each feature of `feats` on the held-out lists of frame te (variant graded lists), trained on
    tr's lists: `own`, its pair accuracy alone, its sign learned on tr's lists as `evaluate` learns it, and `own_eq`,
    the same over only the pairs of equal surviving factors' width (`equal_width`); `without` and `without_eq`, the
    5-fold logistic on every detector less that feature, its pair accuracy as the mean over the folds and over the
    pairs of equal width pooled over the folds."""
    p0tr, p0te = tr[tr["position"] == 0], te[te["position"] == 0]
    trm, tem = D.members_of(p0tr), D.members_of(p0te)
    tr_idx = D.listed(tr, trm)
    tasks = sorted({m["task"] for m in tem})
    random.Random(0).shuffle(tasks)
    folds = [set(tasks[k::5]) for k in range(5)]
    out = {}
    for g in feats:
        known = tr.loc[tr_idx, g]
        med = float(np.nanmedian(known)) if known.notna().any() else 0.0
        trs = D.metrics(trm, tr[g].fillna(med))["pair_acc"]
        sign = -1.0 if trs is not None and trs < 0.5 else 1.0
        sc = sign * te[g].fillna(med)
        r, n = same_key_pairs(te, sc, tem, "n_columns")
        row = dict(sign=sign, own=D.metrics(tem, sc)["pair_acc"], own_eq=r / n if n else None)
        cols = [c for c in FEATS if c != g]
        accs, right, n = [], 0.0, 0
        for fold in folds:
            a = [m for m in tem if m["task"] not in fold]
            b = [m for m in tem if m["task"] in fold]
            if not D.listed(te, a) or not b:
                continue
            sc = fit_apply(te, a, te, cols)
            acc = D.metrics(b, sc)["pair_acc"]
            if acc is not None:
                accs.append(acc)
            r_, n_ = same_key_pairs(te, sc, b, "n_columns")
            right += r_; n += n_
        row.update(without=float(np.mean(accs)) if accs else None, without_eq=right / n if n else None)
        out[g] = row
    return out


def frames(s2, mut, data, all_tasks=False):
    """The frames of the measurement from the rollouts-s2 and the mutant parquets and the split of `data`: the LM
    lists' Tables of the training tasks and of the held-out tasks, the mutant lists' Tables of the held-out tasks,
    those less the mutants whose first table does not differ from the gold's, and `classes` of the mutant frame.
    With `all_tasks`, every task of the mutant parquet counts as held out for the mutant lists, less the tasks whose
    LM lists train the fits (the training tasks of the split that the LM parquet holds)."""
    held, train = D.split_of(data)
    if all_tasks:
        held = set(mut["task"]) - set(s2.loc[s2["task"].isin(train), "task"])
    s2, mut = prepare(s2), prepare(mut)
    mut = mut[mut["task"].isin(held)]
    tr, lm = s2[s2["task"].isin(train)], s2[s2["task"].isin(held)]
    cls = classes(mut)
    drop = {c for c in cls if not c.endswith("__gold") and cls[c] != "differs"}
    return tr, lm, mut, mut[~mut["case"].isin(drop)], cls


def classes(df):
    """{case: class of its first table after the branch} for every case of df, and {case: gold case of its group}."""
    p0 = df[df["position"] == 0]
    by = p0.groupby("case")
    faulted, unseen = by["faulted"].any().to_dict(), by["unseen"].any().to_dict()
    empty = p0["f_empty"].fillna(0).astype(bool).groupby(p0["case"]).all().to_dict()
    hashes = defaultdict(list)
    for case, h in zip(p0["case"].tolist(), p0["rows_hash"].tolist()):
        hashes[case].append(h)
    key = {}
    for case, hs in hashes.items():
        if faulted[case]:
            key[case] = "faulted"
        elif unseen[case]:
            key[case] = "unseen"
        elif empty[case]:
            key[case] = "empty"
        else:
            # a missing rows_hash is None, or NaN where the parquet holds the column as floats
            key[case] = None if any(h is None or (isinstance(h, float) and np.isnan(h)) for h in hs) else tuple(sorted(hs))
    out = {}
    for case in df["case"].unique():
        k = key.get(case, "none")
        if case.endswith("__gold"):
            out[case] = k if isinstance(k, str) else "seen"
        elif isinstance(k, str):
            out[case] = k
        else:
            out[case] = "same rows" if k is not None and k == key.get(case.rsplit("__", 1)[0] + "__gold") else "differs"
    return out


# ------------------------------------------------------------------ the ready clauses as positives

READY_LABEL = "positives: the gold and the ready clauses of its branch point"
READY_ROWS = ["-(sum of filters)", "trivial features", "column count, trained on LM", "logistic, trained on LM",
              "logistic, 5-fold on the set"]


def point_of(case):
    return case.rsplit("__", 1)[0]


def ready_metrics(members, score):
    """The pair accuracy and AUC of `score` where a list may hold several positives (its solving members): each pair is
    a positive against a negative of its list, and each positive's pairs weigh 1/(the list's positives), so a list
    weighs as much as with one positive. The AUC is the mean over the lists of encoder.auc. Gives, as
    `detectors.metrics` does, pair_acc, auc, lists, ranked_lists and pairs (unweighted), and `positives`, the
    positives of the ranked lists."""
    right = n = 0.0
    pairs = ranked = positives = 0
    aucs = []
    lists = scored_lists(members, score)
    for xs in lists.values():
        y = np.array([x[0] for x in xs]); sc = np.array([x[1] for x in xs], np.float32)
        a = E.auc(sc, y)
        if a is not None:
            aucs.append(a)
        if y.any() and not y.all():
            d = sc[y][:, None] - sc[~y][None, :]
            right += float((d > 0).sum() + 0.5 * (d == 0).sum()) / int(y.sum())
            n += int((~y).sum())
            pairs += d.size; ranked += 1; positives += int(y.sum())
    return dict(pair_acc=right / n if n else None, auc=float(np.mean(aucs)) if aucs else None, lists=len(lists),
                ranked_lists=ranked, pairs=pairs, positives=positives, pair_acc_sampled=None, auc_sampled=None)


def ready_frame(df, export):
    """The frame of the ready set (`detectors.read_marked` of its parquet and export): its gold rows, and the rows
    of each ready member (a line of the export's samples.jsonl whose end is "ready") as a positive: `solving` true,
    `member` "ready" and the case `<branch point>__ready<k>`, k its rollout. A ready member is positive by its end,
    whatever its label."""
    from rollout_labels import case_name
    names = {}
    for line in open(Path(export) / "samples.jsonl"):
        s = json.loads(line) if line.strip() else {}
        if s.get("end") == "ready":
            c = case_name(s["task"], s["case"], s["branch"], s["rollout"])
            names[c] = f"{point_of(c)}__ready{s['rollout']}"
    df = df[df["case"].isin(names) | df["gold"].astype(bool)].copy()
    ready = df["case"].isin(names)
    df.loc[ready, "solving"] = True
    df["member"] = df["member"].astype(object)
    df.loc[ready, "member"] = "ready"
    df["case"] = df["case"].map(lambda c: names.get(c, c))
    return df


def first_keys(df):
    """{case: the sorted rows_hash of its Tables at position 0}, None where one of them has none."""
    p0 = df[df["position"] == 0]
    hashes = defaultdict(list)
    for case, h in zip(p0["case"].tolist(), p0["rows_hash"].tolist()):
        hashes[case].append(h)
    return {case: None if any(h is None or (isinstance(h, float) and np.isnan(h)) for h in hs) else tuple(sorted(hs))
            for case, hs in hashes.items()}


def with_ready(te, rd):
    """The frame te (a set's lists, `prepare`d) with the ready members of rd (`ready_frame`, `prepare`d, of the same
    variant) at te's branch points added as positives, less each negative whose first table has the rows_hash of a
    positive of its branch point. Gives the frame, on a new index, and the counts: the ready members added, their
    branch points, the negatives left out, and those of them whose rows are a ready member's and not the gold's."""
    points = set(te["case"].map(point_of))
    add = rd[~rd["gold"].astype(bool) & rd["case"].map(point_of).isin(points)]
    both = pd.concat([te, add], ignore_index=True)
    keys = first_keys(both)
    solving = both.groupby("case")["solving"].first().astype(bool)
    pos, gold = defaultdict(set), {}
    for c, k in keys.items():
        if solving[c] and k is not None:
            pos[point_of(c)].add(k)
        if c.endswith("__gold"):
            gold[point_of(c)] = k
    out = {c for c, k in keys.items() if not solving[c] and k is not None and k in pos[point_of(c)]}
    cases = set(add["case"])
    counts = {"ready": len(cases), "points": len({point_of(c) for c in cases}), "left out": len(out),
              "ready rows": sum(keys[c] != gold.get(point_of(c)) for c in out)}
    return both[~both["case"].isin(out)].reset_index(drop=True), counts


def ready_block(tr, sets, rd, name="graded", width=8):
    """The lines of the scores of READY_ROWS on each set of `sets` ([(set name, frame)]) with the ready members of
    rd added (`with_ready`), measured by `ready_metrics`, under READY_LABEL."""
    res, counts = {}, {}
    for s, df in sets:
        te, counts[s] = with_ready(df, rd)
        res[s] = evaluate(tr, te, name, quick=True, ready=True)
    names = [s for s, _ in sets]
    out = [READY_LABEL,
           f"{'score':<26}" + "".join(f"{s.replace(', rows differ', ' r.d.'):>{2 * width}}" for s in names),
           f"{'':<26}" + f"{'pairs':>{width}}{'AUC':>{width}}" * len(names)]
    for k in READY_ROWS:
        out.append(f"{k.replace(', trained on LM', ', fit on LM').replace(' on the set', ''):<26}" + "".join(
            f"{D.show(res[s][k]['pair_acc']):>{width}}{D.show(res[s][k]['auc']):>{width}}" for s in names))
    lr = "logistic, trained on LM"
    out.append(f"{'ranked lists, pairs':<26}" + "".join(
        f"{res[s][lr]['ranked_lists']:>{width}}{res[s][lr]['pairs']:>{width}}" for s in names))
    out.append(f"{'positives, ready added':<26}" + "".join(
        f"{res[s][lr]['positives']:>{width}}{counts[s]['ready']:>{width}}" for s in names))
    out.append(f"{'points with ready':<26}" + "".join(f"{counts[s]['points']:>{2 * width}}" for s in names))
    out.append(f"{'left out, of a ready':<26}" + "".join(
        f"{counts[s]['left out']:>{width}}{counts[s]['ready rows']:>{width}}" for s in names))
    return out


def ready_frames(parquet, export):
    """The ready set's frame, `ready_frame` of `detectors.read_marked`; None where `parquet` is None."""
    return None if parquet is None else ready_frame(D.read_marked(parquet, export), export)


def ready_variant(rd, held, variant):
    """The ready frame of the held tasks, `prepare`d, in the variant `viable` (`detectors.viable`: a ready member
    whose first table is degenerate drops like any member) or not."""
    rd = rd[rd["task"].isin(held)]
    if variant == "viable":
        rd = D.viable(rd)[0]
    return prepare(rd)


def show(x):
    return "    -" if x is None else f"{x:.3f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mut-export", default=str(ROOT / "work/lm/rollouts-mut/export"))
    ap.add_argument("--mut-parquet", default=str(ROOT / "work/lm/data-study/detectors-mut.parquet"))
    ap.add_argument("--counts", default=str(ROOT / "work/lm/rollouts-mut/counts"))
    ap.add_argument("--export", default=str(ROOT / "work/lm/rollouts-s2/export"))
    ap.add_argument("--parquet", default=str(ROOT / "work/lm/data-study/detectors.parquet"))
    ap.add_argument("--data", default=str(ROOT / "work/lm/data-full-4663b88a"))
    ap.add_argument("--out", default=str(ROOT / "work/lm/data-study/detectors-mut.out"))
    ap.add_argument("--all-tasks", action="store_true", help="every task of the mutant set is held out (an all-boundaries set), less the tasks whose LM lists train the fits")
    ap.add_argument("--ready-parquet", help="the parquet of the ready set: adds the rows whose positives are the gold and the ready clauses")
    ap.add_argument("--ready-export", help="the export of the ready set")
    a = ap.parse_args()
    tr, lm, mut, mut_r, cls = frames(D.read_marked(a.parquet, a.export), D.read_marked(a.mut_parquet, a.mut_export),
                                     a.data, a.all_tasks)

    # counts
    counts = {}
    for p in sorted(Path(a.counts).glob("*.json")):
        counts[p.stem] = json.loads(p.read_text())
    points = [c for t in counts.values() for c in t.values()]
    tot = Counter()
    for c in points:
        for k, v in c.items():
            if k != "skipped":
                tot[k] += v
    skipped = Counter(c["skipped"] for c in points if "skipped" in c)
    lines_ = [json.loads(l) for l in open(Path(a.mut_export) / "samples.jsonl") if l.strip()][1:]
    labels = {l["case"]: l for l in (json.loads(x) for x in open(Path(a.mut_export) / "labels.jsonl") if x.strip())}
    muts = [s for s in lines_ if s["rollout"] != "gold"]
    from rollout_labels import case_name
    names = {case_name(s["task"], s["case"], s["branch"], s["rollout"]): s for s in muts}
    rule_muts = [s for s in muts if s["rules"]]
    consistent = [n for n, s in names.items() if s["rules"] == ["Consistent"]]
    solving = [n for n in names if E.value_solving(labels[n])]
    faulted_lines = [n for n in names if labels[n]["fault"] is not None]
    by_class = Counter(cls.get(n, "none") for n in names)

    out = ["# Detectors on gold against mutant", "",
           "A mutant is the gold continuation's next clause after the branch with one model-written token replaced "
           "by another that the mask admits and the LM's head could write (an out token, or an identifier the stream "
           "has declared), where the gold's remaining tokens of the clause stay admissible and the clause ends where "
           "the gold's does; its stream stops at that clause's end (work/lm/data-study/mutants.py).",
           f"Mutant export {a.mut_export}; LM lists from {a.parquet}; split by {a.data}. Every list is one branch "
           "point of a held-out task" + (" (with --all-tasks: every task of the set less the LM's training tasks)" if a.all_tasks else "") + ": the gold continuation and its mutants (\"mutant\"), or the gold and the LM's "
           "sampled continuations (\"LM\").", ""]
    qual_at = len(out)
    out += ["## Counts", "",
            f"- branch points of held-out tasks: {len(points)}; skipped, no complete clause after the prefix: "
            f"{skipped.get('no complete clause after the prefix', 0)}; skipped for time: {skipped.get('time', 0)}",
            f"- candidates: {tot['candidates']}; completable {tot['completable']}, a gold token inadmissible "
            f"{tot['inadmissible']}, the clause ending elsewhere {tot['elsewhere']}, fault {tot['fault']}",
            f"- completable candidates per branch point with a clause: median "
            f"{np.median([c['completable'] for c in points if 'skipped' not in c]):.0f}, "
            f"min {min(c['completable'] for c in points if 'skipped' not in c)}, "
            f"max {max(c['completable'] for c in points if 'skipped' not in c)}; branch points with none: "
            f"{sum(c['completable'] == 0 for c in points if 'skipped' not in c)}",
            f"- mutants written: {len(muts)} ({tot['mutants']} drawn), at {len({(s['task'], s['case'], s['branch']) for s in muts})} branch points; "
            f"in a RULE clause {len(rule_muts)}, of which the engine judges {len(consistent)} consistent; "
            f"`solving` {len(solving)}; with a fault line in the export's report {len(faulted_lines)}",
            "- mutants by their first table after the branch: " +
            ", ".join(f"{k} {v}" for k, v in sorted(by_class.items(), key=lambda kv: -kv[1])),
            f"- gold continuations by their first table after the branch: " +
            ", ".join(f"{k} {v}" for k, v in sorted(Counter(cls[c] for c in cls if c.endswith('__gold')).items(),
                                                     key=lambda kv: -kv[1])),
            ""]
    by_kind = Counter()
    for s in muts:
        m = s["mutation"]
        kind = "identifier" if m["to_name"].startswith("&") or m["to_name"][:1] == "L" and m["to_name"][1:].isdigit() else "out token"
        by_kind[kind] += 1
    out.insert(len(out) - 1, "- mutants whose substituted token is an identifier: "
               f"{by_kind['identifier']}; an out token: {by_kind['out token']}")

    results = {}
    for vname in ("graded", "all"):
        results[vname] = {s: evaluate(tr, df, vname) for s, df in (("LM", lm), ("mutant", mut), ("mutant, rows differ", mut_r))}
    sets = ("LM", "mutant", "mutant, rows differ")
    rd = ready_frames(a.ready_parquet, a.ready_export)
    held = set(mut["task"])
    for vname in ("graded", "all"):
        R = results[vname]
        out.append(f"## Held-out lists, variant {vname}")
        out.append("pairwise ranking accuracy and AUC on each set of lists; `shift` is the mutant pairwise ranking "
                   "accuracy less the LM one")
        sizes = {s: R[s]["-f_empty"] for s in sets}
        out.append("lists, ranked lists and pairs: " + "; ".join(
            f"{s} {sizes[s]['lists']}, {sizes[s]['ranked_lists']}, {sizes[s]['pairs']}" for s in sets))
        out.append(f"{'score':<34}" + "".join(f"{s[:20]:>22}" for s in sets) + f"{'shift':>8}")
        out.append(f"{'':<34}" + "".join(f"{'pairs':>11}{'AUC':>11}" for _ in sets))
        for k in R["LM"]:
            row = f"{k:<34}" + "".join(f"{show(R[s][k]['pair_acc']):>11}{show(R[s][k]['auc']):>11}" for s in sets)
            a_, b_ = R["LM"][k]["pair_acc"], R["mutant"][k]["pair_acc"]
            out.append(row + (f"{b_ - a_:>+8.3f}" if a_ is not None and b_ is not None else ""))
        if rd is not None:
            out += ready_block(tr, [("mutant", mut), ("mutant, rows differ", mut_r)], ready_variant(rd, held, vname),
                               vname, width=11)
        out.append("")
    # the three largest shifts among single detectors, variant graded
    R = results["graded"]
    single = [k for k in R["LM"] if k.lstrip("+-") in D.DETECTORS]
    shifts = sorted(((R["mutant"][k]["pair_acc"] - R["LM"][k]["pair_acc"], k) for k in single
                     if R["mutant"][k]["pair_acc"] is not None and R["LM"][k]["pair_acc"] is not None),
                    key=lambda x: -abs(x[0]))
    g = results["graded"]
    lg = lambda s, k: show(g[s][k]["pair_acc"])
    lr, l5 = "logistic, trained on LM", "logistic, 5-fold on the set"
    drop = dropped_pairs(mut, cls)
    covered = ranked_groups(mut)
    n_mt = len({t for t, _, _ in covered})
    matched = evaluate(tr, in_groups(lm, covered), "graded", quick=True)[lr]
    qual = ["## Qualifications", "",
            f"- The pairs are gold against mutant at one branch point: both continuations share the prefix and the "
            f"clause's shape, and differ by one token and what the engine emits after it. A mutant is a negative by "
            f"construction, except where the engine judges its RULE consistent and the label marks it solving "
            f"({len(solving)} mutants); its later clauses do not exist, which is why only the first table is compared.",
            f"- Near misses are dense: of {tot['candidates']} admissible substitutions the head could write, "
            f"{tot['completable']} ({tot['completable'] / max(tot['candidates'], 1):.0%}) keep the rest of the gold's clause "
            f"admissible and end where it ends. Most dropped candidates make a later gold token inadmissible.",
            f"- {by_class.get('same rows', 0)} of {len(muts)} mutants give a first table with the gold's rows (a "
            f"substitution the table does not see, such as a commuted or redundant term, or an Ident of the case), "
            f"and {by_class.get('empty', 0) + by_class.get('unseen', 0) + by_class.get('faulted', 0) + by_class.get('none', 0)} "
            f"give one that is empty in every example, unseen, faulted or absent. A detector ties on the first and "
            f"the variant graded drops the second. The \"mutant, rows differ\" set keeps only the mutants whose first "
            f"table differs from the gold's: it drops the same-rows ones and also the unseen, empty and solving ones "
            f"that still had a live Table in the variant graded ({sum(drop.values())} of {g['mutant'][lr]['pairs']} "
            f"pairs: " + ", ".join(f"{v} {k}" for k, v in sorted(drop.items(), key=lambda kv: -kv[1])) + ").",
            f"- The logistic on every detector: held out on the LM lists {lg('LM', lr)} "
            f"(detectors.out's 0.802); trained on LM and applied to the mutant lists {lg('mutant', lr)}, "
            f"rows differ {lg('mutant, rows differ', lr)}; in 5-fold on the mutant lists "
            f"{lg('mutant', l5)}, rows differ {lg('mutant, rows differ', l5)}. "
            f"The 5-fold fits on about {round(n_mt * 4 / 5)} tasks and scores {round(n_mt / 5)}; its per-fold accuracy on "
            f"the mutant lists ranges from {min(g['mutant'][l5]['folds']):.2f} to {max(g['mutant'][l5]['folds']):.2f}.",
            f"- The LM number and the mutant number are not on the same branch points: the LM number is "
            f"{g['LM'][lr]['pairs']} pairs over {g['LM'][lr]['ranked_lists']} ranked lists, the mutant number "
            f"{g['mutant'][lr]['pairs']} pairs over {g['mutant'][lr]['ranked_lists']} ranked lists from {n_mt} tasks. "
            f"At those branch points the LM lists have {matched['ranked_lists']} ranked lists and {matched['pairs']} "
            f"pairs, and the same logistic scores {show(matched['pair_acc'])} on them, so the matched drop is "
            f"{show(None if None in (matched['pair_acc'], g['mutant'][lr]['pair_acc']) else matched['pair_acc'] - g['mutant'][lr]['pair_acc'])}. Weighting lists equally instead of pairs gives "
            f"{show(g['mutant'][lr]['pair_acc_lists'])} and {show(g['mutant, rows differ'][lr]['pair_acc_lists'])} for "
            f"the fit on LM, and {show(g['mutant'][l5]['pair_acc_lists'])} and "
            f"{show(g['mutant, rows differ'][l5]['pair_acc_lists'])} for the 5-fold.",
            "- The largest shifts of a single detector from the LM lists to the mutant lists (variant graded): " +
            ", ".join(f"{k} {d:+.3f} ({show(R['LM'][k]['pair_acc']).strip()} to {show(R['mutant'][k]['pair_acc']).strip()})"
                      for d, k in shifts[:3]) + ".",
            "- A graded signal's sign is the one that ranks better on the LM lists of the training tasks; on the mutant "
            "lists a score below 0.5 means the sign learned on the LM lists points the wrong way.",
            "- The mutant lists have up to as many mutants as `--per-point` per branch point, so a list has more pairs "
            "than an LM list, and a branch point with many near misses weighs no more than one with few.",
            "- `rows_hash` compares Ident cells by value, and an Ident is equal only within one case, so a mutant whose "
            "first table holds Ident columns can count as differing from the gold's where its rows are the same.", ""]
    out[qual_at:qual_at] = qual
    Path(a.out).write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
