"""Classify a table by its schema (column types, candidate keys) and its cardinality against the grids, the objects
and the examples.

    work/lm/.venv/bin/python work/lm/data-study/classify.py measure [--out FILE] [--data DIR]

`classify` is the classifier; `measure` writes work/lm/data-study/classes.out (default --out) from the detector
caches of rollouts-s2, rollouts-mut and rollouts-foreign, their detector parquets, and the corpus export
work/tables/full-9a98b493/tables.parquet.

A key below is a candidate key with its Example columns left out (rows are taken one train example at a time, so an
Example column never tells two rows apart). The keys of a Table are the export's candidate keys, mapped to the
Table's columns; where the export gives none and the rows are known, the minimal column sets whose values are unique
in the rows at every train example; where neither is known, the set of every column (a superkey). The classes, each
a rule on a key and the rows at every train example (a Table takes every class that some key gives):

- raster_in, raster_out: the key is one Box column whose values at every train example are the cells of the input
  grid (of the output grid), one row per cell;
- cells: the key is one Box column whose values are cells of the input or the output grid at every train example
  with rows, but not one row per cell of either (a class added from the data: a selection of cells);
- boxes: the key is one Box column, and some value is not a cell (a class added from the data: a set of boxes or
  offsets);
- entity: the key is one Ident column;
- relationship: the key holds two or more Ident columns, or the rows are closed under the swap of two columns of one
  type (detectors.canonical);
- box_relationship: the key holds two or more Box columns and no Ident (a class added from the data: pairs of cells
  or boxes);
- membership: the key holds an Ident column and a Box column (a class added from the data: an object and its cells);
- box_param: the key is one Box column and one or more value columns (a class added from the data: a cell or box
  under a direction, a color or a number);
- entity_param: the key is one Ident column and one or more value columns (a class added from the data);
- map: the key is one or more value columns (Color, Number, Unit, an orientation type), and the columns outside the
  key and the Example columns are value columns, one or more;
- lookup: the key is one or more value columns, and some column outside the key is a Box or an Ident (a class added
  from the data: a value that picks out a box or an object);
- per_example: the key is empty (the key of Example alone), or one row at every train example;
- set: the only key is every column, and no column is an Ident;
- empty: no row at any train example (a class added from the data; no other rule is applied);
- no_rows: in `classify_cache`, a Table that is faulted or unseen or whose rows come from projections (no other rule
  is applied);
- unclassified: none of the above.

Without rows (`rows` None) the cardinality rules are not applied: raster_in, raster_out, cells and boxes fold into
`box_key` (the key is one Box column), the swap test of relationship and the one-row test of per_example are left
out, and empty is not given.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[0]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse, itertools, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = MAIN_ROOT
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pinned   # noqa: E402
pinned.use()   # the pinned model/ modules (pinned.py)
sys.path.insert(0, str(Path(__file__).resolve().parent))

ORIENT = {"Dir", "DiagDir", "Dir8", "Axis", "DiagAxis", "Axis4", "D4", "C4", "Sym", "Sense", "Pose"}
VALUE = {"Color", "Number", "Unit"} | ORIENT
ADDED = ["box_relationship", "membership", "box_param", "entity_param", "lookup"]
CLASSES = ["raster_in", "raster_out", "cells", "boxes", "entity", "relationship", "map", "per_example", "set"] + ADDED + [
    "empty", "no_rows", "unclassified"]
SCHEMA_CLASSES = ["box_key", "entity", "relationship", "map", "per_example", "set"] + ADDED + ["unclassified"]
MAX_KEY_COLUMNS = 12   # above this many columns, derived keys are searched up to KEY_SIZE columns
KEY_SIZE = 4
SET_ROWS = 20000


def type_name(t):
    return "Pose" if t.startswith("Pose") else t


def width(t):
    return 4 if t == "Box" else 1


def spans(types):
    o, out = 0, []
    for t in types:
        out.append((o, o + width(t)))
        o += width(t)
    return out


def cell_set(h, w):
    r, c = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    return set(map(tuple, np.stack([r, h - 1 - r, c, w - 1 - c], -1).reshape(-1, 4).tolist()))


def derived_keys(types, rows):
    """The minimal sets of non-Example columns whose values are unique in the rows at every train example."""
    cols = [j for j, t in enumerate(types) if t != "Example"]
    import detectors as D
    sp = spans(types)
    ids = []
    for r in rows:
        if not len(r):
            continue
        per = []
        for j in cols:
            _, inv = D.unique_axis0(r[:, sp[j][0]:sp[j][1]], return_inverse=True)
            per.append(inv.reshape(-1).astype(np.int64))
        ids.append((len(r), per))
    def unique(sub):
        for n, per in ids:
            if n <= 1:
                continue
            if not sub:
                return False
            z = np.zeros(n, np.int64)
            for k in sub:
                z = z * (int(per[k].max()) + 1) + per[k]
            if len(np.unique(z)) < n:
                return False
        return True
    found = []
    top = len(cols) if len(cols) <= MAX_KEY_COLUMNS else KEY_SIZE
    for size in range(0, top + 1):
        for sub in itertools.combinations(range(len(cols)), size):
            if any(set(f) <= set(sub) for f in found):
                continue
            if unique(sub):
                found.append(sub)
    if not found:
        found.append(tuple(range(len(cols))))
    return [[cols[k] for k in sub] for sub in found]


def symmetric(types, rows):
    """Whether the rows at every train example are closed under the swap of two columns of one type, with some row
    differing between the two (detectors.canonical's test)."""
    import detectors as D
    if max(len(r) for r in rows) > SET_ROWS:
        return False
    k = D.keyed_rows(rows)
    return D.canonical(list(types), rows, k) is not k


def classify(types, keys=None, rows=None, grids=None):
    """The classes of a table (a set of CLASSES, or of SCHEMA_CLASSES where rows is None) and the keys used.

    types: the column types; keys: candidate keys as lists of column indexes (None or [] where unknown); rows: one
    int array [n, row width] per train example, as detectors.train_rows gives them, or None; grids: one pair
    (input, output) of 2-D arrays per train example, needed where rows is given."""
    types = [type_name(t) for t in types]
    non_ex = [j for j, t in enumerate(types) if t != "Example"]
    has_rows = rows is not None
    if has_rows and not any(len(r) for r in rows):
        return {"empty"}, []
    if keys:
        ks = [sorted(j for j in k if types[j] != "Example") for k in keys]
    elif has_rows:
        ks = derived_keys(types, rows)
    else:
        ks = [non_ex]
    ks = [list(k) for k in dict.fromkeys(tuple(k) for k in ks)]
    out = set()
    sp = spans(types)
    for k in ks:
        kt = [types[j] for j in k]
        rest = [j for j in non_ex if j not in k]
        if len(k) == 1 and kt[0] == "Box":
            if not has_rows:
                out.add("box_key")
            else:
                b = sp[k[0]]
                vals = [set(map(tuple, r[:, b[0]:b[1]].tolist())) for r in rows]
                ins = [cell_set(*np.asarray(g[0]).shape) for g in grids]
                outs = [cell_set(*np.asarray(g[1]).shape) for g in grids]
                if all(v == c for v, c in zip(vals, ins)):
                    out.add("raster_in")
                elif all(v == c for v, c in zip(vals, outs)):
                    out.add("raster_out")
                elif all(not v or v <= a or v <= o for v, a, o in zip(vals, ins, outs)):
                    out.add("cells")
                else:
                    out.add("boxes")
        if len(k) == 1 and kt[0] == "Ident":
            out.add("entity")
        if kt.count("Ident") >= 2:
            out.add("relationship")
        nb, ni, nv = kt.count("Box"), kt.count("Ident"), sum(t in VALUE for t in kt)
        if nb >= 2 and not ni:
            out.add("box_relationship")
        if nb and ni:
            out.add("membership")
        if nb == 1 and not ni and nv and nv == len(kt) - 1:
            out.add("box_param")
        if ni == 1 and not nb and nv and nv == len(kt) - 1:
            out.add("entity_param")
        if k and nv == len(kt) and rest and all(types[j] in VALUE for j in rest):
            out.add("map")
        if k and nv == len(kt) and any(types[j] in ("Box", "Ident") for j in rest):
            out.add("lookup")
        if not k:
            out.add("per_example")
        if len(ks) == 1 and set(k) == set(non_ex) and non_ex and "Ident" not in types:
            out.add("set")
    if has_rows:
        if all(len(r) == 1 for r in rows):
            out.add("per_example")
        if "relationship" not in out and len(non_ex) >= 2 and symmetric(types, rows):
            out.add("relationship")
    if not out:
        out.add("unclassified")
    return out, ks


def shape_of(types, ks):
    """The schema shape: the multiset of column types and the key structure (each key's multiset of types, and
    whether the table has an Example column)."""
    types = [type_name(t) for t in types]
    cols = tuple(sorted(types))
    key = tuple(sorted(tuple(sorted(types[j] for j in k)) for k in ks))
    return cols, key


def show_shape(s):
    cols, key = s
    c = Counter(cols)
    cs = " ".join(f"{t}x{n}" if n > 1 else t for t, n in sorted(c.items()))
    ks = " | ".join("{" + ",".join(k) + "}" for k in key) if key else "none"
    return f"({cs}) key {ks}"


# ------------------------------------------------------------------ measure

EXPORTS = {"rollouts-s2": "detectors.parquet", "rollouts-mut": "detectors-mut.parquet",
           "rollouts-foreign": "detectors-foreign.parquet"}


def table_keys(t):
    """The export's candidate keys of cached Table t, in the Table's column indexes; None where the export gives
    none or a key column is not among the Table's columns."""
    if not t["keys"]:
        return None
    pos = list(t["positions"])
    out = []
    for k in t["keys"]:
        if all(p in pos for p in k):
            out.append([pos.index(p) for p in k])
    return out or None


def classify_cache(name):
    """[{task, case, index, member kind, classes, keys, shape, relation, names}] per Table at position 0 of the
    cache of work/lm/<name>/export, with the classes from the rows and from the schema alone."""
    import pickle
    path = ROOT / "work/lm/detector-cache" / f"{name}.pkl"
    with open(path, "rb") as f:
        tasks = pickle.load(f)["tasks"]
    out = []
    for task in sorted(tasks):
        snap = tasks[task]
        grids = [(p["input"], p["output"]) for p in snap["pairs"]]
        for r in snap["rows"]:
            if r["det"] is None:
                continue
            t = snap["tables"][r["det"]]
            keys = table_keys(t)
            rows = t["rows"] if t["unseen"] is None else None
            scls, sks = classify(t["types"], keys, None, None)
            cls, ks = classify(t["types"], keys, rows, grids) if rows is not None else ({"no_rows"}, sks)
            out.append(dict(task=task, case=r["case"], index=r["index"], gold=r["gold"], solving=r["solving"],
                            classes=cls, schema_classes=scls, keys=ks, declared=keys is not None,
                            seen=rows is not None, shape=shape_of(t["types"], ks), relation=t["relation"],
                            corpus_case=r["corpus_case"], types=list(t["types"]), names=t["names"]))
    return out


def shares(recs, field, classes):
    n = len(recs)
    cnt = Counter(c for r in recs for c in r[field])
    return {c: cnt[c] / n if n else 0.0 for c in classes}


def multiplicity(recs, field, skip=("unclassified",)):
    m = Counter(min(len([c for c in r[field] if c not in skip]), 3) for r in recs)
    n = len(recs)
    return {k: m[k] / n if n else 0.0 for k in range(4)}


def pairs_of(recs, field):
    p = Counter()
    for r in recs:
        for a, b in itertools.combinations(sorted(r[field]), 2):
            p[(a, b)] += 1
    return p


def coverage(cnt):
    tot = sum(cnt.values())
    acc, out, marks = 0, {}, [0.5, 0.9, 0.99]
    for k, (_, n) in enumerate(cnt.most_common(), 1):
        acc += n
        while marks and acc >= marks[0] * tot:
            out[marks.pop(0)] = k
    return out


def fmt_shares(d):
    return ", ".join(f"{k} {v:.1%}" for k, v in d.items() if v > 0)


def fmt_mult(d):
    return ", ".join(f"{k if k < 3 else '3+'}: {v:.1%}" for k, v in d.items())


def class_block(title, recs, field, classes):
    lines = [f"### {title} ({len(recs)} Tables)", "",
             f"- class shares: {fmt_shares(shares(recs, field, classes))}",
             f"- classes matched (unclassified counts 0): {fmt_mult(multiplicity(recs, field))}",
             "- most frequent class pairs: " + ", ".join(
                 f"{a}+{b} {n / max(len(recs), 1):.1%}" for (a, b), n in pairs_of(recs, field).most_common(6)), ""]
    return lines


def tail_block(recs, field, k_top=10, k_tail=10, seed=0):
    import random
    cnt = Counter(r["shape"] for r in recs)
    cov = coverage(cnt)
    by = defaultdict(list)
    for r in recs:
        by[r["shape"]].append(r)
    lines = [f"- distinct shapes: {len(cnt)} over {len(recs)} Tables; singletons {sum(1 for v in cnt.values() if v == 1)}; "
             f"shapes to cover 50% {cov.get(0.5)}, 90% {cov.get(0.9)}, 99% {cov.get(0.99)}", "",
             "Most frequent shapes (count, classes of their Tables):", ""]
    for s, n in cnt.most_common(k_top):
        cl = Counter(" ".join(sorted(r[field])) for r in by[s])
        lines.append(f"- {n}: {show_shape(s)}: " + "; ".join(f"{c} {m}" for c, m in cl.most_common(3)))
    tail = [s for s, n in cnt.items() if n == 1]
    random.Random(seed).shuffle(tail)
    lines += ["", "Tail shapes (one Table each, drawn at random):", ""]
    for s in tail[:k_tail]:
        r = by[s][0]
        cols = ", ".join(f"{n}:{t}" for n, t in zip(r.get("names") or [f"c{i}" for i in range(len(r["types"]))],
                                                   [type_name(t) for t in r["types"]]))
        lines.append(f"- {show_shape(s)}: {' '.join(sorted(r[field]))}; task {r['task']}, case {r['corpus_case']!r}, "
                     f"relation {r['relation']}, columns {cols}")
    return lines + [""]


def corpus_records():
    import pandas as pd
    df = pd.read_parquet(ROOT / "work/tables/full-9a98b493/tables.parquet",
                         columns=["task", "case", "relation", "column_types", "column_names", "keys", "fact"])
    memo, out = {}, []
    for task, case, rel, ty, nm, keys, fact in zip(df["task"], df["case"], df["relation"], df["column_types"],
                                                    df["column_names"], df["keys"], df["fact"]):
        ty = [type_name(t) for t in ty]
        ks = [list(map(int, k)) for k in keys] if len(keys) else None
        mk = (tuple(ty), None if ks is None else tuple(map(tuple, ks)))
        if mk not in memo:
            cls, kk = classify(ty, ks, None, None)
            memo[mk] = (cls, kk, shape_of(ty, kk))
        cls, kk, sh = memo[mk]
        out.append(dict(task=task, corpus_case=case, relation=int(rel), types=ty, names=list(nm), schema_classes=cls,
                        declared=ks is not None, shape=sh, fact=fact))
    return out


def ranking(recs_by, data, labels=("detectors", "classes", "detectors + classes")):
    """loop.py's headline rows with the one-hot of the classes in place of the detectors, and with the detectors and
    the one-hot together, on the LM, mutant and foreign lists, variants graded and viable."""
    import pandas as pd
    import detectors as D
    import detectors_mut as DM
    held, train = D.split_of(data)
    onehot = [f"cls_{c}" for c in CLASSES]
    frames = {}
    for name, pq in EXPORTS.items():
        df = pd.read_parquet(ROOT / "work/lm/data-study" / pq)
        oh = pd.DataFrame([dict(case=r["case"], index=r["index"], **{f"cls_{c}": float(c in r["classes"])
                                                                     for c in CLASSES}) for r in recs_by[name]])
        frames[name] = df.merge(oh, on=["case", "index"], how="left")
    orig_det, orig_feats = list(D.DETECTORS), list(DM.FEATS)
    out = {}
    try:
        sets = {"detectors": orig_det, "classes": onehot, "detectors + classes": orig_det + onehot}
        for label in labels:
            cols = sets[label]
            D.DETECTORS[:] = cols
            DM.FEATS = cols
            for variant in ("graded", "viable"):
                s2, mut, fr = frames["rollouts-s2"], frames["rollouts-mut"], frames["rollouts-foreign"]
                if variant == "viable":
                    s2, _ = D.viable(s2[s2["task"].isin(held | train)])
                    mut, _ = D.viable(mut[mut["task"].isin(held)])
                    fr, _ = D.viable(fr[fr["task"].isin(held)])
                lm = D.headline(s2, held, train)
                tr, _, m, m_r, _ = DM.frames(s2, mut, data)
                _, _, f, f_r, _ = DM.frames(s2, fr, data)
                res = {"LM": (lm["logistic, fit on LM"], lm["logistic, 5-fold"])}
                for nm, df in (("mutant", m), ("mutant r.d.", m_r), ("foreign", f), ("foreign r.d.", f_r)):
                    e = DM.evaluate(tr, df, "graded", quick=True)
                    res[nm] = (e["logistic, trained on LM"], e["logistic, 5-fold on the set"])
                out[(label, variant)] = res
    finally:
        D.DETECTORS[:] = orig_det
        DM.FEATS = orig_feats
    return out


def measure(out_path, data):
    import pandas as pd
    import detectors as D
    recs_by = {name: classify_cache(name) for name in EXPORTS}
    flt = {}
    for name, pq in EXPORTS.items():
        df = pd.read_parquet(ROOT / "work/lm/data-study" / pq, columns=["case", "index"] + D.FILTERS)
        flt.update({(name, c, int(i)): not any(bool(x) for x in v if x == x)
                    for c, i, *v in zip(df["case"], df["index"], *(df[f] for f in D.FILTERS))})
    for name, recs in recs_by.items():
        for r in recs:
            r["clean"] = flt.get((name, r["case"], int(r["index"])), False)
    allrecs = [r for recs in recs_by.values() for r in recs]
    corpus = corpus_records()
    lines = ["# Classes of tables by schema", "",
             "The classifier is `classify` in work/lm/data-study/classify.py; its docstring defines the classes and "
             "the keys. A Table is one DET assignment of an export table. A first table is a Table at position 0 "
             "after the branch. \"Matched\" counts the classes a Table takes, unclassified counted as 0.", ""]
    lines += ["## Classes of first tables, from the rows", ""]
    for name, recs in recs_by.items():
        lines += class_block(name, recs, "classes", CLASSES)
    lines += class_block("the three exports pooled", allrecs, "classes", CLASSES)
    seen = [r for r in allrecs if r["seen"]]
    rows_v = [r for r in seen if "empty" not in r["classes"]]
    lines += class_block("the three exports pooled, Tables with rows at some train example", rows_v, "classes",
                         CLASSES)
    lines += ["## Classes from the schema alone", "",
              "The rules applied without rows: the key's types only (box_key, entity, relationship by Idents, map, "
              "per_example by an empty key, set). Where the export gives no key, the key is every column.", ""]
    lines += class_block("first tables of the three exports, schema alone", allrecs, "schema_classes", SCHEMA_CLASSES)
    lines += class_block("every table of the corpus export full-9a98b493", corpus, "schema_classes", SCHEMA_CLASSES)
    decl = [r for r in corpus if r["declared"]]
    lines += class_block("corpus tables whose export gives a candidate key", decl, "schema_classes", SCHEMA_CLASSES)
    # agreement of the schema-alone view with the rows view, on first tables with rows
    fold = lambda cs: {"box_key" if c in ("raster_in", "raster_out", "cells", "boxes") else c for c in cs}
    agree = sum(fold(r["classes"]) - {"unclassified"} == r["schema_classes"] - {"unclassified"} for r in rows_v)
    lines += [f"- On the {len(rows_v)} first tables with rows, the schema-alone classes equal the rows-based ones "
              f"(raster_in, raster_out, cells and boxes folded into box_key) for {agree / max(len(rows_v), 1):.1%}; "
              f"the export gives a candidate key for {sum(r['declared'] for r in allrecs) / len(allrecs):.1%} of "
              f"first tables and {len(decl) / len(corpus):.1%} of corpus tables.", ""]
    lines += ["## The long tail of schema shapes", "",
              "A shape is the multiset of the column types and the key structure (the multiset of types of each "
              "key used, Example columns left out of the keys).", "", "### First tables of the three exports", ""]
    lines += tail_block(allrecs, "classes")
    lines += ["### Every table of the corpus export (keys: declared, else every column)", ""]
    lines += tail_block(corpus, "schema_classes")
    lines += ["## Gold against non-gold", ""]
    s2 = recs_by["rollouts-s2"]
    groups = [("gold (rollouts-s2)", [r for r in s2 if r["gold"]]), ("LM", [r for r in s2 if not r["gold"]]),
              ("mutant", [r for r in recs_by["rollouts-mut"] if not r["gold"]]),
              ("foreign (crossover)", [r for r in recs_by["rollouts-foreign"] if not r["gold"]])]
    for clean in (False, True):
        lines += [f"### {'non-degenerate first tables (detectors.FILTERS all 0)' if clean else 'every first table'}", "",
                  "| set | Tables | " + " | ".join(CLASSES) + " | matched 0/1/2/3+ |",
                  "|---|---|" + "---|" * len(CLASSES) + "---|"]
        for nm, rs in groups:
            rs = [r for r in rs if r["clean"]] if clean else rs
            sh, mu = shares(rs, "classes", CLASSES), multiplicity(rs, "classes")
            lines.append(f"| {nm} | {len(rs)} | " + " | ".join(f"{sh[c]:.0%}" for c in CLASSES) + " | " +
                         "/".join(f"{mu[k]:.0%}" for k in range(4)) + " |")
        lines.append("")
    lines += ["## Whether a class predicts anything", "",
              "loop.py's logistic rows (fit_logistic on the listed Tables at position 0, missing values at the training "
              "mean): trained on the LM lists of the training tasks and measured on the held-out lists of each set "
              "(\"fit\"), and 5-fold by task (\"5f\"; on every task for LM, on the held-out tasks of the set for the "
              "others). Features: the detectors (the existing headline row), the one-hot of the classes (`cls_*`), and "
              "both. Each cell is pairwise ranking accuracy / AUC; r.d. is \"rows differ\".", ""]
    res = ranking(recs_by, data)
    sets = ["LM", "mutant", "mutant r.d.", "foreign", "foreign r.d."]
    for variant in ("graded", "viable"):
        lines += [f"### variant {variant}", "", "| features | " + " | ".join(f"{s} fit | {s} 5f" for s in sets) + " |",
                  "|---|" + "---|---|" * len(sets)]
        for label in ("detectors", "classes", "detectors + classes"):
            r = res[(label, variant)]
            cell = lambda m: f"{D.show(m.get('pair_acc'))} / {D.show(m.get('auc'))}"
            lines.append(f"| {label} | " + " | ".join(f"{cell(r[s][0])} | {cell(r[s][1])}" for s in sets) + " |")
        lines.append("")
    orig = {"raster_in", "raster_out", "entity", "relationship", "map", "per_example", "set"}
    lm_r, mut_r = res[("detectors", "graded")]["LM"][0], res[("detectors + classes", "graded")]["LM"][0]
    q = ["## Qualifications", "",
         f"- The export gives a candidate key for {sum(r['declared'] for r in allrecs)} of {len(allrecs)} first "
         "tables, so the keys of the rows view are derived from the train rows. A derived key holds of those rows "
         "only: a Table of few rows has keys that a larger instance would break, and a Table with several derived "
         f"keys takes the classes of each. Of the {len(rows_v)} first tables with rows, "
         f"{sum(len(r['keys']) > 1 for r in rows_v) / len(rows_v):.0%} have two or more derived keys; "
         f"{sum(len(r['classes']) > 1 for r in rows_v if len(r['keys']) == 1) / max(sum(len(r['keys']) == 1 for r in rows_v), 1):.0%} "
         "of those with one key match two or more classes, against "
         f"{sum(len(r['classes']) > 1 for r in rows_v if len(r['keys']) > 1) / max(sum(len(r['keys']) > 1 for r in rows_v), 1):.0%} "
         "of those with several.",
         f"- With the brief's classes only (raster, entity, relationship, map, per_example, set), "
         f"{sum(not (r['classes'] & orig) for r in rows_v) / len(rows_v):.0%} of the first tables with rows are "
         "unclassified; the classes cells, boxes, box_relationship, membership, box_param, entity_param, lookup and "
         "empty were added for the shapes that recurred among them, and with them no first table is unclassified. "
         "set overlaps box_param and box_relationship by construction where the only key is every column.",
         "- The corpus rows apply only the schema rules (see the section on the schema alone): raster, cells and "
         "boxes fold into box_key, and the swap test, the one-row test and empty are not applied. Where the corpus "
         "export gives no key (most tables), the key is every column, which makes set and the key-of-every-column "
         "readings of box_param, box_relationship and membership; those shares say what the column types allow, not "
         "what the rows are.",
         f"- The gold continuations appear in each export: the pooled counts hold the gold first tables of a held-out "
         f"branch point up to three times. The gold row of the gold-against-non-gold tables is rollouts-s2's "
         f"({sum(r['gold'] for r in s2)} Tables, training and held-out tasks).",
         "- Each class is a 0/1 feature of a Table at position 0; a member's score is the mean over its listed "
         f"Tables. On the LM lists, adding the one-hot to the detectors lowers the fit row ({D.show(lm_r['pair_acc'])} "
         f"to {D.show(mut_r['pair_acc'])}); the viable foreign rows rest on about 90 pairs, and their 5-fold folds on "
         "11 to 26 pairs each (detectors-foreign.out).",
         "- The detectors row reproduces loop.py's and detectors-foreign.out's headline numbers.", ""]
    lines[4:4] = q
    Path(out_path).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return recs_by, corpus


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["measure"])
    ap.add_argument("--out", default=str(ROOT / "work/lm/data-study/classes.out"))
    ap.add_argument("--data", default=str(ROOT / "work/lm/data-full-4663b88a"))
    a = ap.parse_args()
    measure(a.out, a.data)


if __name__ == "__main__":
    main()
