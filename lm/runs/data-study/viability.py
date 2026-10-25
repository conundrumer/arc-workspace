"""Count how many tables after the branch of a rollout export's continuations are nonviable, gold against sampled.

    work/lm/.venv/bin/python lm/runs/data-study/viability.py index <export> [--out FILE]
    work/lm/.venv/bin/python lm/runs/data-study/viability.py restate <export> [--out FILE] [--points N] [--seed S]

<export> is a rollout export (lm/export_rollouts.py) with its labels.jsonl. A branch point is a (task, corpus case,
prefix_tokens) of the labels; its members are its gold continuation and its sampled ones. A member's tables after
the branch are the relation tables with `token` >= prefix_tokens, numbered by position from 0 (export table
`prefix_tables`). As in lm/encoder.py's `parse_table`, an export table gives one Table per assignment: here an
entry's assignment is its rank among the entries of its table at its example, in entry order (`restate` checks that
the ranks agree with the DET values of assigned.parquet). A table that faults or whose projection search stopped
gives one Table.

Each Table takes the first class that fits, in this order:
- faulted: the table faults, or an entry of it is an example's fault (`value_flags`);
- unseen: every entry is of a kind other than Rows or Count (undefined, stopped, no entries), or is a Count entry
  without the rows of each projection, or the projection search stopped;
- empty everywhere: 0 rows in every train example (a task-wide table: in its task-wide entry);
- empty somewhere: 0 rows in at least one train example but not in every one;
- restatement (`restate` only, position 0 only): at every train example, its set of rows equals the set of rows of
  a Table of the prefix (an evidence table or a table with a smaller token) of the same branch point, or the
  projection of that set onto some of its columns, each column of the Table taken to a distinct column of the same
  type; a Table with a Count entry is not tested;
- viable: none of the above.

`index` reads index.parquet, tables.parquet and the projection files and writes the counts of the first four classes
by member kind (gold, sampled), overall and at positions 0 and 1, and the share of members with no table after the
branch. `restate` reads the values of each Table at position 0 and of the prefix's Tables (once per branch point,
from its gold case) and writes the restatement and viable shares at position 0; with --points N it takes N branch
points drawn uniformly (seed S). --out (default lm/runs/data-study/viability.out) gets the mode's section, and a
section of the other mode already in the file is kept.
"""
import argparse, itertools, json, random, sys, time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
POINT_RELATION, POINT_EVIDENCE = 0, 2
ROWS, COUNT, FAULT = 0, 1, 4
UNSEEN_KINDS = {2, 3, 5}
STOPPED = 1
TRAIN, TASK = 1, 0
CLASSES = ["faulted", "unseen", "empty everywhere", "empty somewhere"]
MAX_MAPPINGS = 5000   # column mappings tried per pair of Tables


def cell_width(t):
    return 4 if t == "Box" else 1


def read_labels(export):
    labs = [json.loads(l) for l in open(Path(export) / "labels.jsonl") if l.strip()]
    for lab in labs:
        lab["point"] = (lab["task"], lab["corpus_case"], int(lab["prefix_tokens"]))
        lab["kind"] = "gold" if lab["rollout"] == "gold" else "sampled"
    return labs


def projection_lookup(export):
    """{(case, table): [projection id]} and {(case, projection, entry): (defined, rows, offset)}."""
    p = pd.read_parquet(Path(export) / "projections.parquet").reset_index(drop=True)
    p["projection"] = p.groupby(["task", "case"]).cumcount()
    of_table = defaultdict(list)
    for r in p.itertuples():
        of_table[(r.case, int(r.table))].append((int(r.projection), list(r.columns), int(r.width)))
    pr = pd.read_parquet(Path(export) / "projection_rows.parquet")
    at = {(r.case, int(r.projection), int(r.entry)): (int(r.defined), int(r.rows), int(r.offset)) for r in pr.itertuples()}
    return of_table, at


def entries(export, cases):
    """The index rows of the cases' relation and evidence tables, each with its assignment rank `asg` and example key
    `ex` (-1 for a task-wide entry)."""
    cols = ["case", "table", "example_kind", "example_index", "kind", "rows", "offset", "entry", "point", "token"]
    ix = pd.read_parquet(Path(export) / "index.parquet", columns=cols)
    ix = ix[ix["case"].isin(cases) & ix["point"].isin([POINT_RELATION, POINT_EVIDENCE])].sort_values(["case", "table", "entry"])
    ix["ex"] = np.where(ix["example_kind"] == TASK, -1, ix["example_index"].astype(np.int64))
    ix["asg"] = ix.groupby(["case", "table", "example_kind", "ex"]).cumcount()
    return ix


def classify(ix, tables, proj_of, proj_at):
    """One row per Table (case, table, asg): its class among CLASSES, or None, and whether it has a Count entry."""
    count_seen = []
    for r in ix.itertuples():
        if r.kind != COUNT:
            count_seen.append(True)
            continue
        ps = proj_of.get((r.case, int(r.table)), [])
        count_seen.append(bool(ps) and all(proj_at.get((r.case, j, int(r.entry)), (0,))[0] for j, _, _ in ps))
    ix = ix.assign(seen=np.where(ix["kind"].isin([ROWS, COUNT]), np.array(count_seen), False),
                   fault=ix["kind"] == FAULT)
    ix["train_rows"] = np.where(ix["seen"] & ix["example_kind"].isin([TRAIN, TASK]), ix["rows"], 0)
    per_ex = ix[ix["example_kind"].isin([TRAIN, TASK])].groupby(["case", "table", "asg", "ex"])["train_rows"].sum()
    per_ex = per_ex.groupby(["case", "table", "asg"]).agg(zero=lambda s: int((s == 0).sum()), n="size")
    g = ix.groupby(["case", "table", "asg"]).agg(fault=("fault", "any"), seen=("seen", "any"),
                                                 count=("kind", lambda s: bool((s == COUNT).any())))
    g = g.join(per_ex).reset_index()
    g = g.merge(tables[["case", "table", "tfault", "stopped"]], on=["case", "table"], how="left")
    whole = g["tfault"] | g["stopped"]
    g = pd.concat([g[~whole], g[whole].drop_duplicates(["case", "table"])])   # one Table for such a table
    cls = np.select([g["tfault"] | g["fault"], g["stopped"] | ~g["seen"], g["zero"] == g["n"], g["zero"] > 0],
                    CLASSES, default="")
    g["cls"] = cls
    return g


def pct(a, b):
    return f"{100 * a / b:5.1f}%" if b else "    -"


def index_mode(export):
    labs = read_labels(export)
    t = pd.read_parquet(Path(export) / "tables.parquet", columns=["case", "table", "token", "point", "fault", "projections"])
    held = set(t["case"])
    kept = [l for l in labs if l["prefix_tables"] is not None and l["case"] in held]
    left = [l for l in labs if l not in kept]
    t["tfault"] = t["fault"].notna()
    t["stopped"] = t["projections"] == STOPPED
    pre = {l["case"]: (int(l["prefix_tokens"]), int(l["prefix_tables"])) for l in kept}
    t = t[t["case"].isin(pre) & (t["point"] == POINT_RELATION)]
    t["prefix_tokens"] = t["case"].map(lambda c: pre[c][0])
    t["prefix_tables"] = t["case"].map(lambda c: pre[c][1])
    after = t[t["token"] >= t["prefix_tokens"]].copy()
    assert (after["table"] >= after["prefix_tables"]).all() and \
        (t[t["token"] < t["prefix_tokens"]]["table"] < t[t["token"] < t["prefix_tokens"]]["prefix_tables"]).all()
    after["position"] = after["table"] - after["prefix_tables"]
    proj_of, proj_at = projection_lookup(export)
    ix = entries(export, set(after["case"]))
    ix = ix.merge(after[["case", "table"]], on=["case", "table"])
    g = classify(ix, after, proj_of, proj_at)
    g = g.merge(after[["case", "table", "position"]], on=["case", "table"])
    kind = {l["case"]: l["kind"] for l in kept}
    g["member"] = g["case"].map(kind)
    lines = ["## index", ""]
    points = {l["point"] for l in kept}
    lines.append(f"labels: {len(labs)}; kept {len(kept)} members of {len(points)} branch points "
                 f"({sum(l['kind'] == 'gold' for l in kept)} gold, {sum(l['kind'] == 'sampled' for l in kept)} sampled)")
    for l in left:
        lines.append(f"left out: {l['case']} ({l['kind']}): the export holds no tables of it; fault: {l['fault']}")
    lines.append("")
    for m in ("gold", "sampled"):
        ms = [l for l in kept if l["kind"] == m]
        x = g[g["member"] == m]
        n_after = after[after["case"].map(kind) == m].groupby("case").size()
        lines.append(f"### {m}: {len(ms)} members, {int(n_after.sum())} export tables after the branch, {len(x)} Tables")
        none = sum(n_after.get(l["case"], 0) == 0 for l in ms)
        faulty_none = sum(n_after.get(l["case"], 0) == 0 and l["fault"] is not None for l in ms)
        lines.append(f"members with no table after the branch: {none} ({pct(none, len(ms))}), "
                     f"{faulty_none} of them with a fault line")
        lines.append(f"export tables after the branch per member: mean {n_after.reindex([l['case'] for l in ms], fill_value=0).mean():.1f}")
        lines.append("rows \"/m\": each member weighs 1, shared among its Tables; the count is of members")
        head = "where".ljust(12) + "Tables".rjust(8) + "".join(c.rjust(18) for c in CLASSES) + "  rest".rjust(8)
        lines.append(head)
        for name, sel in (("all", x), ("position 0", x[x["position"] == 0]), ("position 1", x[x["position"] == 1])):
            row = name.ljust(12) + str(len(sel)).rjust(8)
            row += "".join(pct(int((sel["cls"] == c).sum()), len(sel)).rjust(18) for c in CLASSES)
            row += pct(int((sel["cls"] == "").sum()), len(sel)).rjust(8)
            lines.append(row)
            # each member weighs 1, shared among its Tables there
            w = 1 / sel.groupby("case")["cls"].transform("size")
            row = (name + " /m").ljust(12) + str(sel["case"].nunique()).rjust(8)
            row += "".join(pct(float(w[sel["cls"] == c].sum()), float(w.sum())).rjust(18) for c in CLASSES)
            row += pct(float(w[sel["cls"] == ""].sum()), float(w.sum())).rjust(8)
            lines.append(row)
        p0 = x[x["position"] == 0]
        with_p0 = p0["case"].nunique()
        lines.append(f"members with a table at position 0: {with_p0}; Tables there per member: "
                     f"mean {len(p0) / max(with_p0, 1):.2f}, most {p0.groupby('case').size().max() if with_p0 else 0}")
        by = p0.groupby("case")["cls"]
        for c in CLASSES[:3]:
            every = int(by.apply(lambda s: (s == c).all()).sum())
            some = int(by.apply(lambda s: (s == c).any()).sum())
            lines.append(f"  position 0 {c}: every Table {every} ({pct(every, len(ms))} of members), "
                         f"some Table {some} ({pct(some, len(ms))})")
        excl = int(by.apply(lambda s: s.isin(CLASSES[:3]).all()).sum())
        lines.append(f"  position 0 every Table faulted, unseen or empty everywhere: {excl} ({pct(excl, len(ms))} of members)")
        lines.append("")
    return lines


# ------------------------------------------------------------------ restate

def table_rows(values, t, ents, proj_of, proj_at):
    """{asg: {ex: frozenset of row tuples}} over the train examples (or the task-wide entry) of a seen table, or None
    for an assignment with a Count entry or an unseen entry."""
    w = int(t["width"])
    out, bad = defaultdict(lambda: defaultdict(set)), set()
    for e in ents.itertuples():
        if e.example_kind not in (TRAIN, TASK):
            continue
        if e.kind != ROWS:
            bad.add(e.asg)
            continue
        n, off = int(e.rows), int(e.offset)
        a = np.asarray(values[off:off + n * w]).reshape(n, w)
        out[e.asg][e.ex] |= set(map(tuple, a.tolist()))
    return {k: {ex: frozenset(s) for ex, s in v.items()} for k, v in out.items() if k not in bad}


def spans(types):
    o, res = 0, []
    for ty in types:
        res.append((o, o + cell_width(ty)))
        o += cell_width(ty)
    return res


def restates(x_types, x_rows, y_types, y_rows):
    """Whether x's rows at every example equal y's projected onto distinct columns of the same types."""
    if set(x_rows) != set(y_rows):
        return False
    xs, ys = spans(x_types), spans(y_types)
    cands = []
    for i, ti in enumerate(x_types):
        c = []
        for j, tj in enumerate(y_types):
            if ti != tj:
                continue
            if all({r[xs[i][0]:xs[i][1]] for r in x_rows[ex]} == {r[ys[j][0]:ys[j][1]] for r in y_rows[ex]} for ex in x_rows):
                c.append(j)
        if not c:
            return False
        cands.append(c)
    for k, m in enumerate(itertools.product(*cands)):
        if k >= MAX_MAPPINGS:
            return False
        if len(set(m)) < len(m):
            continue
        if all(x_rows[ex] == {tuple(v for j in m for v in r[ys[j][0]:ys[j][1]]) for r in y_rows[ex]} for ex in x_rows):
            return True
    return False


def det_runs(export, cases):
    """{(case, entry): [(det, rows, offset)]} of assigned.parquet."""
    a = pd.read_parquet(Path(export) / "assigned.parquet", columns=["case", "entry", "det", "rows", "offset"])
    a = a[a["case"].isin(cases)]
    by = defaultdict(list)
    for r in a.itertuples():
        by[(r.case, int(r.entry))].append((int(r.det), int(r.rows), int(r.offset)))
    return by


def restate_mode(export, n_points, seed):
    labs = read_labels(export)
    t = pd.read_parquet(Path(export) / "tables.parquet",
                        columns=["case", "table", "token", "point", "fault", "projections", "column_types", "width", "det_widths"])
    held = set(t["case"])
    kept = [l for l in labs if l["prefix_tables"] is not None and l["case"] in held]
    points = defaultdict(list)
    for l in kept:
        points[l["point"]].append(l)
    keys = sorted(points)
    sampled_note = None
    if n_points and n_points < len(keys):
        keys = sorted(random.Random(seed).sample(keys, n_points))
        sampled_note = f"{n_points} of {len(points)} branch points, drawn uniformly (seed {seed})"
    t["tfault"] = t["fault"].notna()
    t["stopped"] = t["projections"] == STOPPED
    members = [l for k in keys for l in points[k]]
    cases = {l["case"] for l in members}
    tk = {(r.case, int(r.table)): r for r in t[t["case"].isin(cases)].itertuples()}
    proj_of, proj_at = projection_lookup(export)
    # the position-0 table of each member, and the prefix tables of each branch point's gold case
    p0 = {l["case"]: (l["case"], int(l["prefix_tables"])) for l in members
          if (l["case"], int(l["prefix_tables"])) in tk and tk[(l["case"], int(l["prefix_tables"]))].point == POINT_RELATION}
    gold_of = {k: next((l for l in points[k] if l["kind"] == "gold"), None) for k in keys}
    ix = entries(export, cases)
    ix = ix.merge(pd.DataFrame(list(p0.values()), columns=["case", "table"]).assign(p0=True), on=["case", "table"], how="left")
    g0 = classify(ix[ix["p0"] == True].drop(columns="p0"), t[t["case"].isin(cases)], proj_of, proj_at)
    cls0 = defaultdict(list)
    for r in g0.itertuples():
        cls0[(r.case, int(r.table))].append((int(r.asg), r.cls))
    by_case = {c: e for c, e in ix.groupby("case", sort=False)}
    dets = det_runs(export, cases)
    results, asg_bad, asg_n = [], 0, 0
    for k in keys:
        gold = gold_of[k]
        if gold is None:
            continue
        gc, n_pre = gold["case"], int(gold["prefix_tables"])
        gv = np.memmap(Path(export) / "values" / k[0] / f"{gc}.i32", np.int32, mode="r")
        ge = by_case[gc]
        prefix = []
        for tab, ents in ge[ge["table"] < n_pre].groupby("table"):
            r = tk[(gc, int(tab))]
            if r.tfault or r.stopped:
                continue
            types = list(r.column_types)
            for asg, rows in table_rows(gv, r._asdict(), ents, proj_of, proj_at).items():
                if any(rows.values()):
                    prefix.append((types, rows))
        for l in points[k]:
            if l["case"] not in p0:
                continue
            c, tab = p0[l["case"]]
            r = tk[(c, tab)]
            v = gv if c == gc else np.memmap(Path(export) / "values" / k[0] / f"{c}.i32", np.int32, mode="r")
            ents = by_case[c][by_case[c]["table"] == tab]
            # the rank-based assignment against the DET values of each entry
            seen_asg = defaultdict(set)
            for e in ents.itertuples():
                key = tuple((d, np.asarray(v[o:o + n * int(r.det_widths[d])]).tobytes())
                            for d, n, o in sorted(dets.get((c, int(e.entry)), [])))
                seen_asg[e.asg].add(key)
            asg_n += 1
            asg_bad += any(len(s) > 1 for s in seen_asg.values()) or len({frozenset(s) for s in seen_asg.values()}) < len(seen_asg)
            rows_of = table_rows(v, r._asdict(), ents, proj_of, proj_at) if not (r.tfault or r.stopped) else {}
            for asg, cl in cls0[(c, tab)]:
                if cl:
                    results.append((l["kind"], c, cl))
                    continue
                rows = rows_of.get(asg)
                if rows is None:
                    results.append((l["kind"], c, "not tested (Count entry)"))
                    continue
                types = list(r.column_types)
                same = any(restates(types, rows, yt, yr) for yt, yr in prefix)
                results.append((l["kind"], c, "restatement" if same else "viable"))
    lines = ["## restate", ""]
    if sampled_note:
        lines.append(f"sample: {sampled_note}")
    lines.append(f"branch points: {len(keys)}; members with a table at position 0: {len(p0)}")
    lines.append(f"position-0 tables whose rank-based assignments disagree with their DET values: {asg_bad} of {asg_n}")
    lines.append("")
    order = CLASSES + ["restatement", "not tested (Count entry)", "viable"]
    lines.append("member".ljust(10) + "Tables".rjust(8) + "".join(c.rjust(26) for c in order))
    for m in ("gold", "sampled"):
        xs = [cl for kk, _, cl in results if kk == m]
        lines.append(m.ljust(10) + str(len(xs)).rjust(8) + "".join(pct(xs.count(c), len(xs)).rjust(26) for c in order))
    lines.append("rows \"/m\": each member weighs 1, shared among its Tables at position 0; the count is of members")
    for m in ("gold", "sampled"):
        xs = [(c, cl) for kk, c, cl in results if kk == m]
        size = defaultdict(int)
        for c, _ in xs:
            size[c] += 1
        row = (m + " /m").ljust(10) + str(len(size)).rjust(8)
        row += "".join(pct(sum(1 / size[c] for c, cl in xs if cl == o), len(size)).rjust(26) for o in order)
        lines.append(row)
    lines.append("")
    for m in ("gold", "sampled"):
        xs = [cl for kk, _, cl in results if kk == m]
        rest = [x for x in xs if x not in CLASSES]
        lines.append(f"{m}: of the position-0 Tables in none of the first four classes ({len(rest)}), "
                     f"restatements {pct(rest.count('restatement'), len(rest))}")
    lines.append("")
    return lines


def write(out, mode, lines):
    out = Path(out)
    sections = {}
    if out.exists():
        cur = None
        for line in out.read_text().splitlines():
            if line.startswith("## "):
                cur = line[3:]
                sections[cur] = []
            if cur:
                sections[cur].append(line)
    sections[mode] = lines
    out.write_text("\n".join(l for m in ("index", "restate") if m in sections for l in sections[m]).rstrip() + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("mode", choices=["index", "restate"])
    ap.add_argument("export")
    ap.add_argument("--out", default=str(ROOT / "lm/runs/data-study/viability.out"))
    ap.add_argument("--points", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    start = time.time()
    lines = index_mode(a.export) if a.mode == "index" else restate_mode(a.export, a.points, a.seed)
    write(a.out, a.mode, lines)
    print("\n".join(lines))
    print(f"{time.time() - start:.0f} s", file=sys.stderr)


if __name__ == "__main__":
    main()
