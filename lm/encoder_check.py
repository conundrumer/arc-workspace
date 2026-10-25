"""Checks that the feature encoder keeps its symmetries, on a random table that holds every column type and on
real tables of the dev export, cut to a few dozen rows each.

- The real tables: by default, a fixture of the evidence tables of 00576224 $Lookup, the case of the smallest
  evidence, followed by the smallest tables of the export that, together, hold every column type the export
  holds. The fixture is cached beside the tables cache and rebuilt when the export, the task files or the
  loader change. Its tables come from several cases, so they keep no column-level provenance, and the masks take
  the table-level sources. With --full, the first 8 tables of 00576224 $Lookup, from the whole export.

- D4: each of the eight elements acts on the cells (a Box's margins move to their edges' images, an orientation
  constant to the constant of its image under the engine's action); each pooled vector must move by the
  element's permutation of positions, and the crossing output must not change.
- Colors, examples and Idents: a permutation of the values, with each value's identifier moving with the value to
  its image, must leave the pooled vectors unchanged, since the identifiers are drawn independently, so that a
  fresh draw is such a permutation. The change when the identifiers stay with the old values is printed beside
  it, to show that the values reach the vectors.
- Row order: a shuffle of the rows must leave the pooled vectors unchanged.
- Joint evidence: a change to one ex_output cell must change ex_input's pooled vectors, since the two evidence
  tables are encoded as one block of rows.
- Batching: programs encoded together, their tables padded into shared batches, must give what each gives alone.
- Orientation features: no two constants of one column type may share their features.
- Loader faults: a table's fault reads as a fault only where it holds a string, whatever dtype the column reads as.
- Masked loss heads: with the same fields masked, in a program step and in a prior step, under each D4 element
  each Box's per-edge margin logits must move to the edges' images, each orientation field's candidate scores must
  move to the candidates' images, and the Number logits, the pointer logits and every field's loss must not change.
- Wider orientation candidates: a C4 column that holds D4 reflections must give masked_loss a finite loss, each
  reflection's field scored over D4's candidates with its value as the target, and each rotation's over C4's.
- Field labels: on a small task, each ex_output Color field must be computed where its value occurs in the same
  example's input or in another train example's output, and sole elsewhere; the test input does not count.
- Provenance: on a small export of two cases written to a temporary directory, `parse_tables` must give the flows,
  keys and depths to the Tables, a key column and a column of constants must be inferrable and a column that flows
  from ex_input computed, ex_output's Color must be free where the output relation's Color column flows from
  ex_input alone and dependent where it flows from a DET, and in a program step a hidden source column must keep
  the column that flows from it visible, each of the two hidden in some draws; an unseen table must keep its
  columns, so that its flows and the flows that read it name columns it holds; and `parse_tables` must refuse an
  export whose flow names a column past its table's columns.
- Masks: in a program step, no table with hidden fields may have a source table with hidden fields (no hidden
  field a source column with hidden fields, where the tables hold the column-level provenance), and each
  hidden dependent ex_output field must keep a visible occurrence of its value in another train example's output;
  an output step does so too; a program step hides computed fields only, an output step computed ex_output fields
  only, and a prior step inferrable fields only.
- Loss parts: the masked loss must equal its program part plus the prior weight times its prior part.
- Autocast: under bf16 autocast, with the encoder in float32, every attention input must be bf16, each equivariant
  matrix must be cast once per call of `prepare`, and the masked loss and its gradients must be finite; on the CPU,
  and on CUDA where the machine has it.
- Checkpointing: the masked loss's gradients must be the same with and without it, with every batch checkpointed and
  with CHECKPOINT_MIN between the batches' sizes, where exactly the batches of at least CHECKPOINT_MIN keys must be
  checkpointed; the bytes the Blocks save for the backward pass are printed per level.
- Checkpointing over many levels: with every batch checkpointed, on two programs of the fixture's evidence tables
  and 30 small tables each, the bytes that a checkpointed Block call keeps per level must not grow with the evidence
  rows beyond the places of the key mask and of the evidence keys' index, and the gradients must be those without
  checkpointing.
- Split backward: `train.run_batch` with the masked loss, whose backward runs before the clean pass, must give the
  gradients of one backward of the summed loss, on a stand-in language model.
- Identifiers: the vectors drawn and the pooled vectors must be bitwise those of a reference copy of the
  identifiers that draws per value.
- Grouping: programs encoded one per call must give what one call gives, where each program's identifiers come
  from its own generator.
- Relation identifiers: `train.table_relations` must draw and give bitwise what `train.encode` gives.
- Equality modes: the D4, permutation and batching checks under `--enc-equality random` and, with --flex, `flex` (on
  small tables and D4's generators, as flex_attention runs eagerly on the CPU); with --flex, flex must give what codes
  gives where the codes are orthonormal; random must score an equal pair at the learned weight.

The equality term's weights, which start at 0, are drawn at random, so that every check sees the term.

    work/lm/.venv/bin/python lm/encoder_check.py [--full] [--flex] [tables dir]

The checks of the flex equality mode run only with --flex.
"""
import copy, json, math, os, pickle, sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).parent))
import encoder as E

FULL = "--full" in sys.argv[1:]
FLEX = "--flex" in sys.argv[1:]
ARGS = [x for x in sys.argv[1:] if x not in ("--full", "--flex")]
TABLES = ARGS[0] if ARGS else "work/tables/dev"
CACHE = "lm/data-dev/tables.pkl"
FIXTURE = "lm/data-dev/encoder-check-fixture.pkl"
TOL = 1e-4
torch.manual_seed(0)
torch.set_default_dtype(torch.float64)   # so that the tolerance measures the encoder, not float32 rounding

orient = [tuple(x) for x in json.load(open(f"{TABLES}/orientations.json"))]
name_of = dict(orient)
code_of = {n: c for c, n in orient}
meaning_code = {E.meaning(n): c for c, n in orient}

in_names = [f":{i}" for i in range(64)] + ["ex_input", "ex_output"]
in_index = {n: i for i, n in enumerate(in_names)}
embed = nn.Embedding(len(in_names), 48)
enc = E.FeatureEncoder(embed, in_index, id_dim=16, orientations=orient, K=4, layers=2, c=32, heads=4)
enc.eval()
with torch.no_grad():   # the equality term's weights, which start at 0, drawn so that the checks see the term
    eq_gen = torch.Generator().manual_seed(13)
    for blk in enc.blocks:
        blk.eq.copy_(torch.randn(blk.eq.shape, generator=eq_gen))


def transform(table, g):
    """The table with the D4 element g applied to its cells."""
    t = copy.copy(table)
    cells = table.cells.copy()
    o = 0
    for ty in table.types:
        w = E.width(ty)
        if ty == "Box":
            for f in range(4):
                cells[:, o + g[f]] = table.cells[:, o + f]
        elif ty in E.ORIENTATION_TYPES:
            cells[:, o] = [meaning_code[E.meaning_under(E.meaning(name_of[int(x)]), g)] for x in table.cells[:, o]]
        o += w
    t.cells = cells
    return t


def relabel(table, ty, perm, example_rows=False):
    """The table with each value v of the columns of type ty replaced by perm[v]."""
    t = copy.copy(table)
    cells = table.cells.copy()
    o = 0
    for c in table.types:
        if c == ty:
            cells[:, o] = [perm[int(v)] for v in table.cells[:, o]]
        o += E.width(c)
    t.cells = cells
    if example_rows:
        t.example = np.array([perm[int(v)] if v >= 0 else v for v in table.example], np.int16)
    return t


def shuffle(table, rng):
    t = copy.copy(table)
    p = rng.permutation(table.n)
    for f in E.ROW_FIELDS:
        setattr(t, f, getattr(table, f)[p])
    return t


def run(tables, ids_from=None, perm=None, kind=None, seed=1):
    """Pooled vectors and crossing output. With ids_from, the identifiers of kind `kind` are those of ids_from,
    each at its value's image under perm, and the rest the same."""
    gen = torch.Generator().manual_seed(seed)
    ids = E.Identifiers(enc.c, enc.code_dim, gen, "cpu", torch.float64)
    if ids_from is not None:
        for (k, v), vec in ids_from.vecs.items():
            ids.put(k, perm[v] if k in kind and v in perm else v, vec)
    with torch.no_grad():
        enc.prepare()
        rel = [enc.relation_vector(t, None) for t in tables]
        s = enc.encode_programs([(tables, rel, ids)], gen)[0]
        cross = enc.cross_out(s)
        enc.release()
    return s, cross, ids


def random_table(rng, n=12):
    types = ["Box", "Number", "Color", "Ident", "Example", "Dir", "DiagDir", "Dir8", "Axis", "DiagAxis", "Axis4",
             "D4", "C4", "Sym", "Sense", "Box"]
    domain = {"Dir": ["DIR_T", "DIR_B", "DIR_L", "DIR_R"], "DiagDir": ["DIAG_TL", "DIAG_TR", "DIAG_BL", "DIAG_BR"],
              "Axis": ["AXIS_V", "AXIS_H"], "DiagAxis": ["DAXIS_DG", "DAXIS_AD"], "D4": list(E.ELEMENTS),
              "C4": ["D4_ID", "D4_CW", "D4_HT", "D4_CC"], "Sym": list(E.SUBGROUPS), "Sense": list(E.SENSES)}
    domain["Dir8"] = domain["Dir"] + domain["DiagDir"]
    domain["Axis4"] = domain["Axis"] + domain["DiagAxis"]
    cols = []
    for ty in types:
        if ty == "Box":
            cols.append(rng.integers(0, 6, (n, 4)))
        elif ty == "Number":
            cols.append(rng.integers(0, 4, (n, 1)))
        elif ty == "Color":
            cols.append(rng.integers(0, 10, (n, 1)))
        elif ty == "Ident":
            cols.append(rng.integers(100, 104, (n, 1)))
        elif ty == "Example":
            cols.append(rng.integers(0, 4, (n, 1)))
        else:
            cols.append(np.array([[code_of[rng.choice(domain[ty])]] for _ in range(n)]))
    present = np.ones((n, len(types)), bool)
    present[: n // 3, 1:4] = False   # some rows as projection rows, without some columns
    marker = np.zeros(n, bool)
    marker[-1] = True                # an unseen entry's marker row: no columns
    present[-1] = False
    return E.Table(step=1, relation=7, evidence=False, unseen=None, largest=n, export_table=None,
                   entry=rng.integers(0, 3, n).astype(np.int32),
                   positions=list(range(len(types))), types=types,
                   cells=np.concatenate(cols, 1).astype(np.int32), present=present,
                   example=rng.integers(-1, 4, n).astype(np.int16), example_kind=rng.integers(0, 3, n).astype(np.int8),
                   assignment=rng.integers(0, 3, (n, 2)).astype(np.int32), model=np.zeros(n, np.int32),
                   part=np.zeros(n, np.int32), marker=marker, unseen_entries={"a check": int(marker.sum())})


def cut(table, n, rng):
    t = copy.copy(table)
    if table.n > n:
        p = np.sort(rng.choice(table.n, n, replace=False))
        for f in E.ROW_FIELDS:
            setattr(t, f, getattr(table, f)[p])
    return t


PROVENANCE = ("depth", "keys", "flows", "output_position", "output_color", "color_dependent")


def fixture():
    """The evidence tables of `case`, then, for each column type the export holds, the smallest table with rows
    that holds it, where no table already chosen does."""
    stamp = E.table_stamp(TABLES)
    if os.path.exists(FIXTURE):
        f = pickle.load(open(FIXTURE, "rb"))
        if f.get("stamp") == stamp:
            return f["tables"]
    tables, _, _ = E.load_tables(TABLES, CACHE)
    chosen = tables[case][:2]
    assert all(t.evidence for t in chosen)
    no_provenance = lambda t: E.Table(**{k: v for k, v in t.__dict__.items() if k not in PROVENANCE})
    body = sorted((t.n, k, i) for k, ts in tables.items() for i, t in enumerate(ts)
                  if not t.evidence and t.unseen is None and t.n)
    for ty in sorted({E.type_name(ty) for ts in tables.values() for t in ts for ty in t.types}):
        if any(ty in map(E.type_name, t.types) for t in chosen):
            continue
        n, k, i = next(x for x in body if ty in map(E.type_name, tables[x[1]][x[2]].types))
        chosen.append(no_provenance(tables[k][i]))
    chosen[1] = no_provenance(chosen[1])
    pickle.dump({"stamp": stamp, "tables": chosen}, open(FIXTURE, "wb"))
    return chosen


rng = np.random.default_rng(0)
case = ("00576224", "$Lookup")
if FULL:
    tables, _, _ = E.load_tables(TABLES, CACHE)
    source, source_title = tables[case][:8], f"{case[0]} {case[1]}, first 8 tables"
else:
    source = fixture()
    source_title = f"fixture, {case[0]} {case[1]} evidence and the smallest tables of each column type"
real = [cut(t, 40, rng) for t in source]
unseen = E.Table(step=2, relation=9, evidence=False, unseen="a check", largest=0, export_table=None, positions=[], types=[],
                 cells=np.zeros((0, 0), np.int32), present=np.zeros((0, 0), bool), example=np.zeros(0, np.int16),
                 example_kind=np.zeros(0, np.int8), assignment=np.zeros((0, 0), np.int32), model=np.zeros(0, np.int32),
                 entry=np.zeros(0, np.int32), part=np.zeros(0, np.int32), marker=np.zeros(0, bool), unseen_entries={})
suites = {"random table, every column type and a marker row, an unseen table, then a second random table":
              [random_table(rng), unseen, random_table(rng)],
          f"{source_title} (types {sorted({ty for t in real for ty in t.types})}), 40 rows each": real}

def orientation_images(g):
    """The code of each orientation constant's image under g."""
    return {c: meaning_code[E.meaning_under(E.meaning(n), g)] for c, n in orient}


def symmetry(title, tabs, elements=E.ELEMENTS):
    """The D4, row order and value permutation checks of `enc` on tabs. Under the "random" equality term, an
    orientation constant's sign code moves with the constant to its image, as the identifiers do in the permutation
    checks."""
    print(f"== {title}")
    s0, c0, ids0 = run(tabs)
    scale = s0.abs().max().item()
    print(f"pooled vectors {tuple(s0.shape)}, max |entry| {scale:.3f}; crossing {tuple(c0.shape)}, max |entry| {c0.abs().max().item():.3f}")
    worst_s, worst_c, worst_same = 0.0, 0.0, float("inf")
    for name, g in elements.items():
        tg = [transform(t, g) for t in tabs]
        if enc.equality == "random":
            s1, c1, _ = run(tg, ids0, orientation_images(g), ("sign orientation",))
        else:
            s1, c1, _ = run(tg)
        perm = E.position_permutation(g)
        moved = torch.empty_like(s0)
        moved[:, :, perm] = s0                       # position p of the original goes to perm[p]
        es, ec = (s1 - moved).abs().max().item(), (c1 - c0).abs().max().item()
        worst_s, worst_c = max(worst_s, es), max(worst_c, ec)
        if name != "D4_ID":
            worst_same = min(worst_same, (s1 - s0).abs().max().item())
        print(f"  {name}: |pooled(g.T) - g.pooled(T)| {es:.2e}   |cross(g.T) - cross(T)| {ec:.2e}")
    print(f"  D4 equivariance {'PASS' if worst_s < TOL and worst_c < TOL else 'FAIL'} (worst {worst_s:.1e}, {worst_c:.1e}); "
          f"for scale, the least |pooled(g.T) - pooled(T)| over g != id is {worst_same:.2e}")
    s1, c1, _ = run([shuffle(t, rng) for t in tabs], ids0, {}, ())
    print(f"  row order: |pooled| change {(s1 - s0).abs().max().item():.2e}")
    for kind, ty, perm, ex_rows in (
            ("color", "Color", dict(enumerate(rng.permutation(10).tolist())), False),
            ("example", "Example", {0: 1, 1: 0}, True),   # the first two train pairs swapped
            ("ident", "Ident", None, False)):
        if perm is None:
            vals = sorted({int(v) for t in tabs for i, x in enumerate(t.types) if x == "Ident"
                           for v in t.cells[:, sum(E.width(y) for y in t.types[:i])]})
            perm = dict(zip(vals, (rng.permutation(len(vals)) + 5000).tolist()))
        if not any(ty in t.types for t in tabs) and not ex_rows:
            continue
        perm_full = {**{v: v for v in range(-1, 20)}, **perm}
        moved_tabs = [relabel(t, ty, perm_full, ex_rows) for t in tabs]
        codes = ("example", "sign example") if kind == "example" else (kind, f"{kind} code", f"sign {kind}")
        s1, c1, _ = run(moved_tabs, ids0, perm_full, codes)
        s2, _, _ = run(moved_tabs, ids0, {}, ())
        e = (s1 - s0).abs().max().item()
        print(f"  {ty} permutation, identifiers move with the values: |pooled| change {e:.2e} {'PASS' if e < TOL else 'FAIL'}; "
              f"identifiers stay with the old values (so the values are seen): {(s2 - s0).abs().max().item():.2e}")


for title, tabs in suites.items():
    symmetry(title, tabs)

def run_masked(tables, masks, seed=1):
    gen = torch.Generator().manual_seed(seed)
    ids = E.Identifiers(enc.c, enc.code_dim, gen, "cpu", torch.float64)
    with torch.no_grad():
        enc.prepare()
        rel = [enc.relation_vector(t, None) for t in tables]
        _, records = enc.encode_programs([(tables, rel, ids)], gen, [masks], detail=True)
        enc.release()
    return records


def same(a, b):
    """The largest difference of two output arrays that hold -inf at the same places, or inf."""
    fa, fb = torch.isfinite(a), torch.isfinite(b)
    return (a[fa] - b[fb]).abs().max().item() if torch.equal(fa, fb) and fa.any() else (0.0 if torch.equal(fa, fb) else float("inf"))


def image_index(names, g):
    """For each candidate constant, the index of its image under g."""
    by_meaning = {E.meaning(n): k for k, n in enumerate(names)}
    return [by_meaning[E.meaning_under(E.meaning(n), g)] for n in names]


print("== masked loss heads under D4, the same fields masked (frac 0.3), in a program step and in a prior step")
for (title, tabs), kind in [(x, k) for x in suites.items() for k in ("program", "prior")]:
    masks = enc.draw_masks(tabs, 0.3, 10 ** 6, torch.Generator().manual_seed(3), kind)
    r0 = run_masked(tabs, masks)
    heads = sorted({h for _, _, r in r0 for h in r["out"]})
    worst = {"loss": 0.0, **{h: 0.0 for h in heads}}
    for name, g in E.ELEMENTS.items():
        r1 = run_masked([transform(t, g) for t in tabs], masks)
        for (_, _, a), (_, _, b) in zip(r0, r1):
            worst["loss"] = max(worst["loss"], (a["loss"] - b["loss"]).abs().max().item())
            for h, (_, oa) in a["out"].items():
                ob = b["out"][h][1]
                if h == "box":
                    ob = ob[:, list(g)]          # edge e of the original against edge g(e) of the image
                elif h.startswith("orientation"):
                    ob = ob[:, image_index(enc.candidate_features(h.split()[-1])[0], g)]
                worst[h] = max(worst[h], same(oa, ob))
    fields = sum(len(r["label"]) for _, _, r in r0)
    ok = all(v < TOL for v in worst.values())
    print(f"  {title[:40]}..., {kind} step: {fields} masked fields; worst change "
          + ", ".join(f"{h} {v:.1e}" for h, v in worst.items()) + f" {'PASS' if ok else 'FAIL'}")

print("== chance loss of the masked heads: each field's chance_loss against its formula (a pointer: -log(targets / "
      "(candidates + 1)); a Box or Position: ln 320), and the loss of every head with all-zero weights, whose scores "
      "are all equal, against chance_loss")
formula = {"Box": math.log(320), "Position": math.log(320), "Number": math.log(1088)}
saved = {k: v.detach().clone() for k, v in enc.heads.state_dict().items()}


def chance_formula(tab, mask, rows_cols, k):
    """The formula's chance loss of the k-th masked field (in np.nonzero order), or None for an orientation type."""
    r, i = rows_cols[0][k], rows_cols[1][k]
    ty = tab.types[i]
    if ty in E.POINTER_TYPES:
        off = int(np.cumsum([0] + [E.width(t) for t in tab.types])[i])
        cand = tab.present[:, i] & ~mask[:, i] & ~tab.marker
        same_value = cand & (tab.cells[:, off] == tab.cells[r, off])
        return math.log((cand.sum() + 1) / max(int(same_value.sum()), 1))
    return formula.get(ty)


seen, worst, zero_worst, bad = {}, 0.0, 0.0, []
for title, tabs in suites.items():
    masks = enc.draw_masks(tabs, 0.3, 10 ** 6, torch.Generator().manual_seed(3), "program")
    for zeroed in (False, True):
        if zeroed:
            enc.heads.load_state_dict({k: torch.zeros_like(v) for k, v in saved.items()})
        try:
            recs = run_masked(tabs, masks)
        finally:
            enc.heads.load_state_dict(saved)
        for _, t, r in recs:
            ch, loss = r["chance_loss"], r["loss"]
            if zeroed:
                zero_worst = max(zero_worst, (loss - ch).abs().max().item())
                continue
            for k, lab in enumerate(r["label"]):
                f = chance_formula(tabs[t], masks[t], np.nonzero(masks[t]), k)
                if f is None:
                    continue
                kind = "pointer" if tabs[t].types[np.nonzero(masks[t])[1][k]] in E.POINTER_TYPES else lab.split("/")[-1]
                seen[kind] = seen.get(kind, 0) + 1
                worst = max(worst, abs(ch[k].item() - f))
ok = worst < 1e-9 and zero_worst < 1e-9 and {"pointer", "Box"} <= set(seen)
print(f"  fields checked against the formula {seen}; worst |chance_loss - formula| {worst:.1e}; with zeroed heads, worst "
      f"|loss - chance_loss| {zero_worst:.1e} {'PASS' if ok else 'FAIL'}")

print("== field labels of ex_output Color: by where each value occurs, on a small task")
small = E.evidence_tables({"train": [{"input": [[1]], "output": [[1, 2, 3]]}, {"input": [[4]], "output": [[2]]}],
                           "test": [{"input": [[3]]}]})
labels, dependent = E.output_labels(small[0], small[1])
want = [E.COMPUTED, E.COMPUTED, E.SOLE, E.COMPUTED], [False, True, False, True]
ok = labels.tolist() == want[0] and dependent.tolist() == want[1]
print(f"  labels {[E.FIELD_LABELS[x] for x in labels]}, dependent {dependent.tolist()} (in the input, in another "
      f"output, nowhere else but the test input, in another output) {'PASS' if ok else 'FAIL'}")

print("== provenance: a small export with flows, keys and depths through parse_tables; the labels, ex_output's Color "
      "free and dependent, and a hidden source column in a program step (200 draws, frac 1)")


def provenance_export(d, bad=False):
    """A small export in `d` and its task file: two cases of one task. Table 2 (Color, Number, Color) has the key
    [1], a Color copied from ex_input and a constant; table 3, the output relation (Box, Color), flows from ex_input
    and, in $Free, from table 2's Color, and in $Dep, from table 4's DET value, which flows from ex_output. $Unseen is
    $Dep with table 4 faulted, so that it is unseen and its flows and those that read it name its columns. With
    `bad`, a flow of table 2 names a column past its three."""
    import pandas as pd
    task = {"train": [{"input": [[1]], "output": [[3]]}, {"input": [[2]], "output": [[3]]}], "test": [{"input": [[1]]}]}
    (d / "tasks").mkdir(); json.dump(task, open(d / "tasks/t.json", "w"))
    grid = dict(point=2, relation=-1, column_types=["Example", "Box", "Color"], width=6, det_relations=[], det_widths=[],
                depth=0, keys=[[0, 1]], output_position=-1, output_color=-1)
    rel = lambda r, types, w, **k: dict(point=0, relation=r, column_types=types, width=w,
                                        **{"det_relations": [], "det_widths": [], "keys": [], "output_position": -1,
                                           "output_color": -1, **k})
    t2 = rel(0, ["Color", "Number", "Color"], 3, depth=1, keys=[[1]])
    t3 = rel(1, ["Box", "Color"], 5, depth=2, output_position=0, output_color=1)
    t4 = rel(2, ["Color"], 1, depth=1)
    t3_dep = {**t3, "det_relations": ["slot 2"], "det_widths": [1]}
    cases = {"$Free": [grid, grid, t2, t3], "$Dep": [grid, grid, t2, t3_dep, t4],
             "$Unseen": [grid, grid, t2, t3_dep, {**t4, "fault": "a check"}]}
    rows = {2: lambda e: [[1 + e, 0, 5], [2, 1, 5]], 3: lambda e: [[0, 0, 0, 0, 3]], 4: lambda e: [[3]]}
    flow = lambda tab, col, kind, st, sc, det=-1: dict(table=tab, column=col, kind=kind, source_table=st,
                                                       source_relation="", source_column=sc, det=det, atom="")
    flows = {"$Free": [flow(2, 0, 0, 0, 2), flow(2, 1, 1, 0, 1), flow(2, 2, 2, -1, -1), flow(3, 0, 0, 0, 1),
                       flow(3, 1, 0, 2, 0)],
             "$Dep": [flow(2, 0, 0, 0, 2), flow(2, 1, 1, 0, 1), flow(2, 2, 2, -1, -1), flow(3, 0, 0, 0, 1),
                      flow(3, 1, 0, 4, 0, 0), flow(4, 0, 1, 1, 2)]}
    flows["$Unseen"] = flows["$Dep"]
    if bad:
        flows["$Free"].append(flow(2, 3, 0, 0, 2))
    tables, index, flow_rows = [], [], []
    (d / "values/t").mkdir(parents=True)
    for case, tabs in cases.items():
        values, entry = [], 0
        for i, t in enumerate(tabs):
            tables.append(dict(task="t", case=case, concept=False, table=i, token=i, projections=0, **{"fault": None, **t}))
            if t["point"] != 0:
                continue
            for e in range(2):
                r = rows[i](e)
                index.append(dict(task="t", case=case, table=i, entry=entry, kind=0, rows=len(r),
                                  offset=len(values), example_kind=1, example_index=e, model=0))
                values += [x for row in r for x in row]; entry += 1
        np.array(values, np.int32).tofile(d / f"values/t/{case}.i32")
        flow_rows += [dict(task="t", case=case, concept=False, **f) for f in flows[case]]
    pd.DataFrame(tables).to_parquet(d / "tables.parquet")
    pd.DataFrame(index).to_parquet(d / "index.parquet")
    pd.DataFrame(flow_rows).to_parquet(d / "flows.parquet")
    pd.DataFrame(columns=["task", "case", "entry", "det", "rows", "offset"]).to_parquet(d / "assigned.parquet")
    pd.DataFrame(columns=["task", "case", "table", "columns", "width"]).to_parquet(d / "projections.parquet")
    pd.DataFrame(columns=["task", "case", "projection", "entry", "defined", "rows", "offset"]).to_parquet(
        d / "projection_rows.parquet")


import tempfile
with tempfile.TemporaryDirectory() as tmp:
    provenance_export(Path(tmp))
    ptabs, pfaults, pstats = E.parse_tables(tmp, Path(tmp) / "tasks")
free, dep = ptabs[("t", "$Free")], ptabs[("t", "$Dep")]
bad = [] if not pfaults and pstats["provenance"].startswith("column") else [("faults or stats", pfaults, pstats)]
labels = [E.FIELD_LABELS[x] for x in E.field_labels(free)[2][0]]
if labels != ["computed", "inferrable", "inferrable"]:
    bad.append(("table 2 labels", labels))
if [t.depth for t in free[2:]] != [1, 2] or free[2].keys != [[1]] or (free[3].output_position, free[3].output_color) != (0, 1):
    bad.append(("depths, keys or output columns", [t.depth for t in free[2:]], free[2].keys))
deps = {}
for name, tabs in (("$Free", free), ("$Dep", dep)):
    lab, d_ = E.output_labels(tabs[0], tabs[1])
    deps[name] = (tabs[1].color_dependent, [E.FIELD_LABELS[x] for x in lab], d_.tolist())
if deps != {"$Free": (False, ["computed", "computed"], [False, False]),
            "$Dep": (True, ["computed", "computed"], [True, True])}:
    bad.append(("ex_output Color", deps))
g, both, alone = torch.Generator().manual_seed(23), 0, {"table 4": 0, "table 3 Color": 0}
for _ in range(200):
    ms = enc.draw_masks(dep, 1.0, 10 ** 6, g, "program")
    src, out_ = bool(ms[4][:, 0].any()), bool(ms[3][:, 1].any())
    both += src and out_
    alone["table 4"] += src and not out_; alone["table 3 Color"] += out_ and not src
if both or not all(alone.values()):
    bad.append(("coordination", both, alone))
unseen_t = ptabs[("t", "$Unseen")]
try:
    for kind in E.STEP_KINDS:
        enc.draw_masks(unseen_t, 1.0, 10 ** 6, g, kind)
    unseen_ok = (unseen_t[4].unseen is not None and unseen_t[4].types == ["Color"] and unseen_t[1].color_dependent
                 and E.column_sources(unseen_t)[3][1] == {(4, 0)})
except IndexError as x:
    unseen_ok = f"IndexError {x}"
if unseen_ok is not True:
    bad.append(("an unseen table's columns", unseen_ok))
with tempfile.TemporaryDirectory() as tmp:
    provenance_export(Path(tmp), bad=True)
    try:
        E.parse_tables(tmp, Path(tmp) / "tasks")
        refused = "no fault"
    except E.DataFault as x:
        refused = str(x)
if "flow [2, 3, 0, 0, 2, -1]" not in refused:
    bad.append(("a flow past the columns", refused))
print(f"  table 2 labels {labels}; ex_output Color (color_dependent, labels, dependent) {deps}; hidden in 200 "
      f"program steps: the source column and the column that flows from it together {both}, each alone {alone}; "
      f"an unseen source table keeps its columns for the flows: {unseen_ok}; a flow past its table's columns: "
      f"{refused!r}; "
      f"{'PASS' if not bad else 'FAIL ' + str(bad)}")

print("== masks: the sources stay visible in a program and an output step, and each step kind hides its label alone "
      "(200 draws per kind, frac 0.5)")
mask_progs = {"fixture": real, "small task": small, "random tables": suites[next(iter(suites))]}
bad, seen = [], {}
for kind in E.STEP_KINDS:
    g = torch.Generator().manual_seed(21)
    for name, tabs in mask_progs.items():
        labs, srcs, cols = E.field_labels(tabs), E.table_sources(tabs), E.provenance(tabs) and E.column_sources(tabs)
        for _ in range(200):
            ms = enc.draw_masks(tabs, 0.5, 10 ** 6, g, kind)
            held = {j for j, m in enumerate(ms) if m is not None and m.any()}
            for j in held:
                lab = labs[j][ms[j]]
                key = (kind, E.FIELD_LABELS[lab[0]], "evidence" if tabs[j].evidence else "derived")
                seen[key] = seen.get(key, 0) + int(ms[j].sum())
                if (lab != (E.INFERRABLE if kind == "prior" else E.COMPUTED)).any():
                    bad.append((kind, name, j, "label"))
                if kind == "output" and tabs[j].relation != "ex_output":
                    bad.append((kind, name, j, "a table other than ex_output"))
                if kind == "program" and not cols and srcs[j] & held:
                    bad.append((kind, name, j, "a source table holds hidden fields"))
                hidden = {(k, c) for k in held for c in np.flatnonzero(ms[k].any(0)).tolist()}
                if kind == "program" and cols and any(cols[j][c] & hidden for c in np.flatnonzero(ms[j].any(0))):
                    bad.append((kind, name, j, "a source column holds hidden fields"))
                if kind in ("program", "output") and tabs[j].relation == "ex_output":
                    col, t = tabs[j].types.index("Color"), tabs[j]
                    ex, color = t.cells[:, 0], t.cells[:, E.EVIDENCE_COLOR]
                    dep = E.output_labels(E.evidence_input(tabs), t)[1]
                    for r in np.flatnonzero(ms[j][:, col] & dep):
                        seen[f"{kind}: hidden dependent"] = seen.get(f"{kind}: hidden dependent", 0) + 1
                        if not (~ms[j][:, col] & (color == color[r]) & (ex != ex[r])).any():
                            bad.append((kind, name, j, "a dependent field's occurrences all hidden"))
ok = not bad and all(seen.get(f"{k}: hidden dependent", 0) > 0 for k in ("program", "output")) and all(
    seen.get(k, 0) > 0 for k in [("program", "computed", "evidence"), ("program", "computed", "derived"),
                                 ("output", "computed", "evidence"),
                                 ("prior", "inferrable", "evidence"), ("prior", "inferrable", "derived")])
print(f"  hidden fields by step kind, label and table kind: {dict(sorted((str(k), v) for k, v in seen.items()))}; "
      f"violations {bad[:3]} {'PASS' if ok else 'FAIL'}")

print("== loss parts: the masked loss against the program part plus the prior weight times the prior part")
with torch.no_grad():
    loss, recs = enc.masked_loss([(real, [None] * len(real))] * 3,   # a program, an output and a prior step
                                 torch.Generator().manual_seed(4), 0.3, 10 ** 6, torch.Generator().manual_seed(5),
                                 prior_weight=0.7)
part = {k: torch.cat([r["loss"] for _, _, r in recs if r["part"] == k]) for k in ("program", "prior")}
e = abs(loss.item() - (part["program"].mean().item() + 0.7 * part["prior"].mean().item()))
print(f"  loss {loss.item():.6f}, program part {part['program'].mean().item():.6f} over {len(part['program'])} fields, "
      f"prior part {part['prior'].mean().item():.6f} over {len(part['prior'])} fields; |difference| {e:.1e} "
      f"{'PASS' if e < 1e-9 else 'FAIL'}")

print("== a C4 column that holds D4 reflections: masked_loss on its masked fields, each scored over the candidates "
      "of the type that holds its value")
c4_names = ["D4_TB", "D4_CW", "D4_LR", "D4_ID"]
c4 = E.Table(step=1, relation=7, evidence=False, unseen=None, largest=4, export_table=None, entry=np.zeros(4, np.int32),
             positions=[0, 1], types=["Ident", "C4"],
             cells=np.array([[100 + i, code_of[n]] for i, n in enumerate(c4_names)], np.int32),
             present=np.ones((4, 2), bool), example=np.full(4, -1, np.int16), example_kind=np.zeros(4, np.int8),
             assignment=np.zeros((4, 0), np.int32), model=np.zeros(4, np.int32), part=np.zeros(4, np.int32),
             marker=np.zeros(4, bool), unseen_entries={})
c4_mask = np.zeros((4, 2), bool)
c4_mask[:, 1] = True
enc.draw_masks = lambda tables, *a, **k: [c4_mask]   # every C4 field masked
try:
    with torch.no_grad():
        loss, recs = enc.masked_loss([([c4], [None])], torch.Generator().manual_seed(4), detail=True, kind="program")
finally:
    del enc.draw_masks
rec = recs[0][2]
want = {"orientation C4 as D4": ("D4", [0, 2]), "orientation C4": ("C4", [1, 3])}
bad = []
for h, (ty, rows) in want.items():
    idx, scores = rec["out"].get(h, (np.zeros(0, np.int64), None))
    if idx.tolist() != rows:
        bad.append((h, idx.tolist())); continue
    names = E.CANDIDATES[ty]
    tgt = torch.tensor([names.index(c4_names[r]) for r in rows])
    ce = torch.nn.functional.cross_entropy(scores, tgt, reduction="none")
    if (ce - rec["loss"][rows]).abs().max().item() > 1e-9 or scores.shape[1] != len(names):
        bad.append((h, "loss or candidates"))
ok = torch.isfinite(loss).item() and not bad
print(f"  loss {loss.item():.4f}; heads {sorted(rec['out'])}; targets {c4_names}; mismatches {bad} "
      f"{'PASS' if ok else 'FAIL'}")

print("== joint evidence block: one ex_output cell's color changed")
tabs = real
assert tabs[0].relation == "ex_input" and tabs[1].relation == "ex_output"
changed = copy.copy(tabs[1])
changed.cells = tabs[1].cells.copy()
changed.cells[0, 5] = (changed.cells[0, 5] + 1) % 10        # the Color column, after Example (1) and Box (4)
s0, _, _ = run(tabs)
s1, _, _ = run([tabs[0], changed] + tabs[2:])
e = (s1[0] - s0[0]).abs().max().item()
print(f"  |ex_input pooled change| {e:.2e} {'PASS' if e > 1e-6 else 'FAIL'} (ex_output's own: {(s1[1] - s0[1]).abs().max().item():.2e})")

print("== batching: four programs encoded in one call, their tables of one level built together and run in shared "
      "batches, against each alone")
# the last two programs have the same table sizes and evidence sizes, so their tables share buckets
progs = list(suites.values()) + [[cut(t, 13, rng) for t in source] for _ in range(2)]
with torch.no_grad():
    enc.prepare()
    work = lambda seed: [(t, [enc.relation_vector(x, None) for x in t],
                          E.Identifiers(enc.c, enc.code_dim, torch.Generator().manual_seed(seed), "cpu", torch.float64)) for t in progs]
    together = enc.encode_programs(work(5), None)
    alone = [enc.encode_programs([w], None)[0] for w in work(5)]
    enc.release()
e = max((a - b).abs().max().item() for a, b in zip(together, alone))
# a level whose batch holds tables of several programs with different row counts
shared = [t for t in range(1, max(map(len, progs))) if any(
    len(g) > 1 and len({progs[i][t].n for i in g}) > 1
    for g in [[i for i in range(len(progs)) if t < len(progs[i]) and progs[i][t].n]]
    if E.batches([progs[i][t].n for i in g], [0] * len(g)) == [list(range(len(g)))])]
print(f"  |together - alone| {e:.2e}; levels whose one batch holds tables of several programs and row counts: {shared} "
      f"{'PASS' if e < TOL and shared else 'FAIL'}")
print("== batching: the same four programs with BATCH_COST 0, so that a level's tables of different row counts run in "
      "separate batches, each with its own equality layout, narrower than the level's where its tables have fewer "
      "columns of a group; against each alone")
narrower = []   # the batches whose equality layout is a gather of the level's
layout = enc.batch_layout
def counted(*a, **k):
    r = layout(*a, **k)
    if r is not None and r[0] is not None:
        narrower.append(r)
    return r
enc.batch_layout, cost = counted, E.BATCH_COST
E.BATCH_COST = 0
try:
    with torch.no_grad():
        enc.prepare()
        together = enc.encode_programs(work(5), None)
        alone = [enc.encode_programs([w], None)[0] for w in work(5)]
        enc.release()
finally:
    del enc.batch_layout
    E.BATCH_COST = cost
e = max((a - b).abs().max().item() for a, b in zip(together, alone))
print(f"  |together - alone| {e:.2e}; batches with a narrower layout: {len(narrower)} "
      f"{'PASS' if e < TOL and narrower else 'FAIL'}")
print("== batching: two programs of one table each, 300 and 290 rows, together (one batch, padded to 304 rows) against "
      "each alone (padded to 304 and 296 rows)")
big = [[random_table(rng, 300)], [random_table(rng, 290)]]
assert E.batches([300, 290], [0, 0]) == [[0, 1]]
with torch.no_grad():
    enc.prepare()
    work = [(t, [enc.relation_vector(x, None) for x in t],
             E.Identifiers(enc.c, enc.code_dim, torch.Generator().manual_seed(6), "cpu", torch.float64)) for t in big]
    together = enc.encode_programs(work, None)
    alone = [enc.encode_programs([w], None)[0] for w in work]
    enc.release()
e = max((a - b).abs().max().item() for a, b in zip(together, alone))
print(f"  |together - alone| {e:.2e} {'PASS' if e < TOL else 'FAIL'}")
print("== orientation features: distinct within each column type (Dir8 and Axis4 span two encoding ranges)")
feats = {n: E.orientation_features(n) for _, n in orient}
family = lambda code: {0: 0, 1: 0, 2: 1, 3: 1}.get(code >> 8, code >> 8)
same = [(a, b) for i, (ca, a) in enumerate(orient) for cb, b in orient[i + 1:]
        if family(ca) == family(cb) and all(np.array_equal(x, y) for x, y in zip(feats[a], feats[b]))]
print(f"  pairs of constants with equal features: {same or 'none'} {'PASS' if not same else 'FAIL'}")

print("== the loader's fault test: a tables frame whose fault column reads as the str dtype, one string and nulls")
import pandas as pd
frame = pd.DataFrame({"fault": pd.array([None, "a fault", None], dtype="str"), "projections": [0, 0, 0],
                      "column_types": [["Color"]] * 3, "det_relations": [[]] * 3, "det_widths": [[]] * 3, "token": [1, 2, 3],
                      "relation": [1, 2, 3], "table": [0, 1, 2], "width": [1, 1, 1]})
parsed = [x for t in frame.to_dict("records") for x in E.parse_table(t, [], np.zeros(0, np.int32), {}, {}, {}, {}, 1)]
faulted = [t.unseen for t in parsed if t.unseen is not None]
print(f"  fault dtype {frame['fault'].dtype}; unseen tables {faulted} {'PASS' if faulted == ['the table faults'] else 'FAIL'}")

print("== the loader's split by assignment: a table of one DET whose four entries, of 3 rows each, hold two assignments, "
      "under a table cap of 8 rows")
row = {"fault": None, "projections": 0, "column_types": ["Color"], "det_relations": ["slot 5"], "det_widths": [1],
       "token": 4, "relation": 6, "table": 0, "width": 1}
ents = [{"entry": e, "kind": 0, "rows": 3, "offset": 3 * e, "example_kind": 1, "example_index": e % 2, "model": 0}
        for e in range(4)]
asg = {e: [{"det": 0, "offset": 12 + e // 2, "rows": 1}] for e in range(4)}   # entries 0 and 1 read one DET value, 2 and 3 another
split = E.parse_table(row, ents, np.r_[np.arange(12) % 10, 3, 4].astype(np.int32), asg, {}, {}, {}, 2)
over = E.mark_over_rows({("t", "c"): split}, 8)
ok = (len(split) == 2 and all(t.step == 5 and t.relation == 6 for t in split)
      and [sorted(set(t.entry.tolist())) for t in split] == [[0, 1], [2, 3]]
      and all(len(np.unique(t.assignment, axis=0)) == 1 for t in split) and E.table_groups(split) == [0, 0]
      and sum(t.n for t in split) > 8 and not over and all(t.unseen is None and t.n <= 8 for t in split))
print(f"  {len(split)} tables at step {[t.step for t in split]}, relation {[t.relation for t in split]}, entries "
      f"{[sorted(set(t.entry.tolist())) for t in split]}, rows {[t.n for t in split]} (sum {sum(t.n for t in split)}), "
      f"over the cap {len(over)} {'PASS' if ok else 'FAIL'}")

print("== bf16 autocast, the encoder in float32: every attention input is bf16, and each equivariant matrix is cast once "
      "per call of prepare, not at each use")


def autocast_check(device):
    """Encodes the real tables under bf16 autocast on `device`, with gradients on: gives the dtypes of q, k and v at
    each attention call, the storages of the bf16 equivariant matrices saved for the backward pass (one per save),
    the count of equivariant maps, and whether the pooled vectors are finite."""
    e32 = copy.deepcopy(enc).float().to(device)
    calls, saved = [], []
    sdpa = E.F.scaled_dot_product_attention
    e32.prepare()
    shapes = {tuple(m.shape) for m in e32.prepared()}
    n_maps = len({m.data_ptr() for m in e32.prepared()})
    e32.release()
    shapes |= {s[::-1] for s in shapes}

    def spy(q, k, v, **kw):
        calls.append((q.dtype, k.dtype, v.dtype))
        return sdpa(q, k, v, **kw)

    def pack(t):
        if t.dtype == torch.bfloat16 and tuple(t.shape) in shapes:
            saved.append(t.untyped_storage().data_ptr())
        return t

    E.F.scaled_dot_product_attention = spy
    try:
        gen = torch.Generator().manual_seed(1)
        with torch.autocast(device, dtype=torch.bfloat16), torch.autograd.graph.saved_tensors_hooks(pack, lambda t: t):
            e32.prepare()
            ids = E.Identifiers(e32.c, e32.code_dim, gen, device, torch.float32)
            s = e32.encode_programs([(real, [e32.relation_vector(t, None) for t in real], ids)], gen)[0]
            e32.release()
    finally:
        E.F.scaled_dot_product_attention = sdpa
    return calls, saved, n_maps, bool(torch.isfinite(s).all())


def autocast_masked(device):
    """The masked loss of the real tables under bf16 autocast on `device`, as pretrain.py --autocast runs it, and
    whether it and every gradient are finite."""
    e32 = copy.deepcopy(enc).float().to(device)
    with torch.autocast(device, dtype=torch.bfloat16):
        loss, _ = e32.masked_loss([(real, [None] * len(real))], torch.Generator().manual_seed(1), 0.3, 10 ** 6,
                                  torch.Generator().manual_seed(2))
    loss.backward()
    grads = [p.grad for p in e32.parameters() if p.grad is not None]
    return loss.item(), bool(grads) and all(torch.isfinite(g).all() for g in grads)


for device in ("cpu", "cuda"):
    if device == "cuda" and not torch.cuda.is_available():
        print("  cuda: SKIP (no CUDA on this machine)")
        continue
    calls, saved, n_maps, finite = autocast_check(device)
    ok_dtype = bool(calls) and all(d == (torch.bfloat16,) * 3 for d in calls)
    ok_cast = len(set(saved)) <= n_maps < len(saved)
    print(f"  {device}: {len(calls)} attention calls, input dtypes {sorted({str(x) for d in calls for x in d})}; "
          f"{len(saved)} saves of a bf16 matrix from {len(set(saved))} storages ({n_maps} matrices that prepare builds); "
          f"pooled finite {finite} {'PASS' if ok_dtype and ok_cast and finite else 'FAIL'}")
    loss, grads_finite = autocast_masked(device)
    ok = math.isfinite(loss) and grads_finite
    print(f"  {device}: masked loss under autocast {loss:.4f}, gradients finite {grads_finite} {'PASS' if ok else 'FAIL'}")

print("== checkpointing: the masked loss's gradients with and without --enc-checkpoint, and the bytes the Blocks save "
      "for the backward pass at each level")


def grads_and_saved(ckpt, minimum=0):
    """The gradients of the masked loss over both suites as one batch of programs, the bytes of the new storages
    that the Block calls save for the backward pass, per level, and the keys B (N + P + E) of each Block call of the
    forward pass and of each that the checkpoint takes, with CHECKPOINT_MIN at `minimum`."""
    enc.checkpoint, ckpt_min = ckpt, E.CHECKPOINT_MIN
    E.CHECKPOINT_MIN = minimum
    level, saved, seen, calls, taken = [None], {}, set(), [], []
    block_forward, ckpt_fn = E.Block.forward, E.checkpoint

    def ckpt_spy(fn, x, ctx, *rest, **kw):
        taken.append(x.shape[0] * ctx.mask.shape[-1])
        return ckpt_fn(fn, x, ctx, *rest, **kw)

    def spy(self, x, ctx, *rest):
        level[0] = ctx.level
        if torch.is_grad_enabled() and not backward[0]:
            calls.append(x.shape[0] * ctx.mask.shape[-1])
        try:
            return block_forward(self, x, ctx, *rest)
        finally:
            level[0] = None

    def pack(t):
        ptr = t.untyped_storage().data_ptr()
        if level[0] is not None and ptr not in seen:
            seen.add(ptr)
            saved[level[0]] = saved.get(level[0], 0) + t.untyped_storage().nbytes()
        return t

    backward = [False]
    E.Block.forward, E.checkpoint = spy, ckpt_spy
    try:
        enc.zero_grad()
        with torch.autograd.graph.saved_tensors_hooks(pack, lambda t: t):
            loss, _ = enc.masked_loss([(t, [None] * len(t)) for t in suites.values()], torch.Generator().manual_seed(8),
                                      0.3, 10 ** 6, torch.Generator().manual_seed(9))
        backward[0] = True
        loss.backward()
    finally:
        E.Block.forward, E.checkpoint, E.CHECKPOINT_MIN = block_forward, ckpt_fn, ckpt_min
        enc.checkpoint = False
    return {n: p.grad.clone() for n, p in enc.named_parameters() if p.grad is not None}, saved, calls, taken


g0, b0, calls, _ = grads_and_saved(False)
g1, b1, _, taken = grads_and_saved(True)
e = max((g0[n] - g1[n]).abs().max().item() for n in g0)
print(f"  {len(g0)} parameter gradients, |with - without| {e:.2e}, {len(taken)} of {len(calls)} Block calls "
      f"checkpointed {'PASS' if g0.keys() == g1.keys() and e < 1e-12 and len(taken) == len(calls) else 'FAIL'}")
# CHECKPOINT_MIN between the calls' sizes: the calls under it run without the checkpoint, the rest with it
mid = sorted(set(calls))[len(set(calls)) // 2]
g2, _, _, taken2 = grads_and_saved(True, mid)
e = max((g0[n] - g2[n]).abs().max().item() for n in g0)
ok = sorted(taken2) == sorted(k for k in calls if k >= mid) and 0 < len(taken2) < len(calls)
print(f"  CHECKPOINT_MIN {mid}: {len(taken2)} of {len(calls)} Block calls checkpointed, those of at least "
      f"{mid} keys; |with - without| {e:.2e} {'PASS' if ok and g0.keys() == g2.keys() and e < 1e-12 else 'FAIL'}")
print("  KB saved by the Blocks per level, without: " + ", ".join(f"{k}: {v / 1e3:.0f}" for k, v in sorted(b0.items()))
      + "; with: " + (", ".join(f"{k}: {v / 1e3:.0f}" for k, v in sorted(b1.items())) or "none")
      + f" {'PASS' if sum(b1.values()) < sum(b0.values()) / 10 else 'FAIL'}")
enc.zero_grad()

print("== checkpointing over many levels: the bytes a checkpointed Block call keeps for the backward pass, per level, "
      "with the fixture's evidence and with it cut to 6 rows per table, and the gradients against no checkpointing")
ev_big = real[:2]
ev_small = [cut(t, 6, np.random.default_rng(3)) for t in ev_big]
body = cut(next(t for t in real[2:] if t.n and not t.evidence), 4, np.random.default_rng(4))
LEVELS = 30
kv_width = [0]   # a row's evidence keys and values at one layer, H (w + wv)


def kept_per_level(evidence, ckpt=True):
    """The gradients of the masked loss of two programs of the evidence tables then LEVELS copies of `body`, and the
    bytes of the new storages, per level, that the Block calls save and that the checkpoint keeps of their inputs."""
    progs = [list(evidence) + [body] * LEVELS for _ in range(2)]
    enc.checkpoint, ckpt_min = ckpt, E.CHECKPOINT_MIN
    E.CHECKPOINT_MIN = 0   # every batch checkpointed, though the fixture's are small
    level, kept, seen = [None], {}, set()
    block_forward, ckpt_fn = E.Block.forward, E.checkpoint

    def count(t):
        ptr = t.untyped_storage().data_ptr()
        if level[0] is not None and ptr not in seen:
            seen.add(ptr)
            kept[level[0]] = kept.get(level[0], 0) + t.untyped_storage().nbytes()

    def walk(o):
        if torch.is_tensor(o):
            count(o)
        elif isinstance(o, (list, tuple)):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            for x in o.values():
                walk(x)
        elif hasattr(o, "__dict__") and not isinstance(o, nn.Module):
            for x in vars(o).values():
                walk(x)

    def spy(self, x, ctx, l, mats):
        level[0] = ctx.level
        kv_width[0] = self.heads * (mats["W"] + mats["Wv"])
        try:
            return block_forward(self, x, ctx, l, mats)
        finally:
            level[0] = None

    def ckpt_spy(fn, x, ctx, *rest, **kw):   # the inputs, which the checkpoint keeps to run the call again
        level[0] = ctx.level
        walk((x, ctx))
        level[0] = None
        return ckpt_fn(fn, x, ctx, *rest, **kw)

    E.Block.forward, E.checkpoint = spy, ckpt_spy
    try:
        enc.zero_grad()
        with torch.autograd.graph.saved_tensors_hooks(lambda t: (count(t), t)[1], lambda t: t):
            loss, _ = enc.masked_loss([(t, [None] * len(t)) for t in progs], torch.Generator().manual_seed(8), 0.3,
                                      10 ** 6, torch.Generator().manual_seed(9))
        loss.backward()
    finally:
        E.Block.forward, E.checkpoint, E.CHECKPOINT_MIN = block_forward, ckpt_fn, ckpt_min
        enc.checkpoint = False
    return {n: p.grad.clone() for n, p in enc.named_parameters() if p.grad is not None}, kept


g_big, k_big = kept_per_level(ev_big)
_, k_small = kept_per_level(ev_small)
g_plain, _ = kept_per_level(ev_big, ckpt=False)
e = max((g_plain[n] - g_big[n]).abs().max().item() for n in g_plain)
print(f"  {len(g_plain)} parameter gradients over {LEVELS + 2} levels, |with - without| {e:.2e} "
      f"{'PASS' if g_plain.keys() == g_big.keys() and e < 1e-12 else 'FAIL'}")
# from level 3 on, past the levels that first see the shared tensors (the evidence block, and the evidence keys and
# values that the first table after it reads), a level's bytes may differ only by the evidence places of the key mask
# and of the evidence keys' index: at most 8 bytes per place in each, of each program's table
d_rows = sum(t.n for t in ev_big) - sum(t.n for t in ev_small)
bound = 2 * 2 * 8 * d_rows
late = [k for k in k_big if k >= 3]
diff = max(abs(k_big[k] - k_small.get(k, 0)) for k in late)
copy_bytes = 2 * d_rows * len(enc.blocks) * kv_width[0] * 8
print(f"  KB kept per level from level 3, fixture evidence ({sum(t.n for t in ev_big)} rows per program): "
      f"mean {np.mean([k_big[k] for k in late]) / 1e3:.1f}; cut ({sum(t.n for t in ev_small)} rows): "
      f"mean {np.mean([k_small[k] for k in late]) / 1e3:.1f}; largest difference {diff} bytes, bound {bound} "
      f"(a per-level copy of those rows' keys and values would add about {copy_bytes / 1e3:.0f} KB) "
      f"{'PASS' if late and diff <= bound else 'FAIL'}")
enc.zero_grad()

print("== train.py's run_batch with --aux-masked: the gradients when the masked loss's backward runs apart, before "
      "the clean pass, against one backward of the summed loss (a stand-in language model, two dev cases)")
import train as T

cases, _, names, kinds, mask_table = T.load("lm/data-dev")
lm_tables, _, _ = E.load_tables(TABLES, CACHE)
in_names_, out_names_, in_index_, out_index_ = T.vocabularies(names, kinds)
lm_cases = [c for c in cases if (c["task"], c["case"]) in lm_tables][:2]
for c in lm_cases:
    c["tables"] = [cut(t, 30, rng) for t in lm_tables[(c["task"], c["case"])]]


class StandIn(nn.Module):
    """A language model's interface over a causal running mean of the inputs, so that the feature vectors reach
    every later target."""
    def __init__(self, hidden=48, id_dim=16):
        super().__init__()
        self.embed = nn.Embedding(len(in_names_), hidden)
        self.id_in = nn.Linear(id_dim, hidden, bias=False)
        self.mix = nn.Linear(hidden, hidden)
        self.head = nn.Linear(hidden, len(out_names_), bias=False)
        self.query, self.key = nn.Linear(hidden, id_dim, bias=False), nn.Linear(hidden, id_dim, bias=False)

    def forward(self, tokens, ids, mask, feats=None, feat_mask=None):
        x = self.embed(tokens) + self.id_in(ids)
        if feats is not None:
            x = torch.where(feat_mask[..., None], feats.to(x.dtype), x)
        h = torch.tanh(self.mix(torch.cumsum(x, 1) / torch.arange(1, x.shape[1] + 1)[:, None]))
        return self.head(h), self.query(h), self.key(h)


torch.manual_seed(2)
lm = StandIn()
lm.encoder = E.FeatureEncoder(lm.embed, in_index_, 16, orient, K=4, layers=1, c=16, heads=2,
                              examples=E.max_example(lm_tables) + 1)
lm.rel_token = {int(n[2:]): i for i, n in enumerate(names) if n.startswith("&r") and n[2:].isdigit()}
lm_args = (in_index_, out_index_, 16, 48, T.Masks(mask_table, names, kinds, out_index_))
group, W_AUX = list(range(len(lm_cases))), 0.5


def lm_grads(split_backward):
    lm.zero_grad()
    lm.mask_gen = torch.Generator().manual_seed(3)
    if split_backward:
        aux = dict(weight=W_AUX, frac=0.3, cap=64, kind="alternate", prior_weight=1.0, step=0)
        loss, _ = T.run_batch(lm, lm_cases, group, lm_args, "cpu", gen=torch.Generator().manual_seed(1), K=4,
                              enc_gen=torch.Generator().manual_seed(2), aux=aux)
    else:
        lm_loss, _ = T.run_batch(lm, lm_cases, group, lm_args, "cpu", gen=torch.Generator().manual_seed(1), K=4,
                                 enc_gen=torch.Generator().manual_seed(2))
        g = torch.Generator().manual_seed(1)
        encs = [T.encode(lm_cases[i], *lm_args, gen=g, K=4, rel_token=lm.rel_token) for i in group]
        masked, _ = lm.encoder.masked_loss([(e[5][0], e[5][2]) for e in encs], lm.mask_gen, 0.3, 64, lm.mask_gen)
        loss = lm_loss + W_AUX * masked
    loss.backward()
    return loss.item(), {n: p.grad.clone() for n, p in lm.named_parameters() if p.grad is not None}


l0, g0 = lm_grads(False)
l1, g1 = lm_grads(True)
e = max((g0[n] - g1[n]).abs().max().item() for n in g0)
ok = g0.keys() == g1.keys() and e < 1e-12 and abs(l0 - l1) < 1e-12 and any(n.startswith("encoder.") for n in g0)
print(f"  loss {l0:.6f} against {l1:.6f}; {len(g0)} parameter gradients, |split - joint| {e:.2e} {'PASS' if ok else 'FAIL'}")

print("== identifiers: the vectors drawn and the pooled vectors, bitwise, against a reference copy of the identifiers "
      "that draws per value and stacks the vectors (one seed)")


class ReferenceIdentifiers:
    """The identifiers as first written: a vector per (kind, key), drawn on first use, stacked at each lookup."""
    def __init__(self, c, code_dim, gen, device, dtype=None):
        self.c, self.code_dim, self.gen, self.device, self.vecs = c, code_dim, gen, device, {}
        self.dtype = dtype or torch.get_default_dtype()

    def get(self, kind, keys, dim=None):
        dim = dim or self.c
        new = [k for k in keys if (kind, k) not in self.vecs]
        if new:
            v = torch.randn(len(new), dim, generator=self.gen)
            if kind.endswith("code"):
                v = v / v.norm(dim=1, keepdim=True)
            v = v.to(self.dtype)
            for k, x in zip(new, v):
                self.vecs[(kind, k)] = x
        if not keys:
            return torch.zeros(0, dim, dtype=self.dtype)
        return torch.stack([self.vecs[(kind, k)] for k in keys])

    def host(self, kind, values, dim=None, unique=None):
        u, inv = np.unique(values, return_inverse=True)
        return self.get(kind, u.tolist(), dim)[torch.from_numpy(inv.reshape(-1))]


def encoded(make_ids, tabs):
    gen = torch.Generator().manual_seed(11)
    ids = make_ids(enc.c, enc.code_dim, gen, "cpu", torch.float64)
    with torch.no_grad():
        enc.prepare()
        s = enc.encode_programs([(tabs, [enc.relation_vector(t, None) for t in tabs], ids)], gen)[0]
        enc.release()
    return s, ids.vecs


for title, tabs in suites.items():
    s_ref, v_ref = encoded(ReferenceIdentifiers, tabs)
    s_new, v_new = encoded(E.Identifiers, tabs)
    ok = v_ref.keys() == v_new.keys() and all(torch.equal(v_ref[k], v_new[k]) for k in v_ref) and torch.equal(s_ref, s_new)
    print(f"  {title[:40]}...: {len(v_ref)} identifiers, the same keys and bitwise the same vectors, and the same "
          f"pooled vectors: {'PASS' if ok else 'FAIL'}")

print("== --enc-group: programs encoded one per call against all in one call, each program's identifiers drawn from "
      "its own generator, so that the draws do not depend on the grouping")


class PerProgramIdentifiers(E.Identifiers):
    """Identifiers whose generator is seeded by the order of their creation, which is the programs' order."""
    made = [0]

    def __init__(self, c, code_dim, gen, device, dtype=None):
        super().__init__(c, code_dim, torch.Generator().manual_seed(100 + self.made[0]), device, dtype)
        self.made[0] += 1


def grouped(group, fn):
    PerProgramIdentifiers.made[0] = 0
    enc.group, lm.encoder.group = group, group
    real_ids, E.Identifiers = E.Identifiers, PerProgramIdentifiers
    try:
        return fn()
    finally:
        E.Identifiers = real_ids
        enc.group, lm.encoder.group = 0, 0


progs = [(t, [None] * len(t)) for t in list(suites.values()) + [[cut(t, 13, rng) for t in source] for _ in range(2)]]
with torch.no_grad():
    f0 = grouped(0, lambda: enc(progs))
    f1 = grouped(1, lambda: enc(progs))
e = max((a - b).abs().max().item() for a, b in zip(f0, f1))
print(f"  the encoder's output vectors, {len(progs)} programs: |grouped - one call| {e:.2e} {'PASS' if e < TOL else 'FAIL'}")
l0, g0 = grouped(0, lambda: lm_grads(True))
l1, g1 = grouped(1, lambda: lm_grads(True))
e = max((g0[n] - g1[n]).abs().max().item() for n in g0)
ok = g0.keys() == g1.keys() and e < 1e-10 and abs(l0 - l1) < 1e-10
print(f"  run_batch with --aux-masked: loss {l0:.6f} against {l1:.6f}; |grouped - one call| of {len(g0)} gradients "
      f"{e:.2e} {'PASS' if ok else 'FAIL'}")

print("== pretrain.py's relation identifiers: train.table_relations against encode's last item, every dev case with "
      "tables, one generator through them all")
all_cases = [c for c in cases if (c["task"], c["case"]) in lm_tables and all(c is not x for x in lm_cases)]
for c in all_cases:
    c["tables"] = lm_tables[(c["task"], c["case"])]
full_args = (in_index_, out_index_, 64, 10 ** 7, T.Masks(mask_table, names, kinds, out_index_))
ga, gb = torch.Generator().manual_seed(12), torch.Generator().manual_seed(12)
ok, n_rel = True, 0
for c in all_cases:
    e = T.encode(c, *full_args, gen=ga, K=4, rel_token=lm.rel_token)[5]
    tabs, rel = T.table_relations(c, 64, 10 ** 7, gb, 4, lm.rel_token)
    ok &= len(tabs) == len(e[0]) and all(x is y for x, y in zip(tabs, e[0])) and len(rel) == len(e[2])
    ok &= all((x is None and y is None) or (x is not None and y is not None and torch.equal(x, y)) for x, y in zip(rel, e[2]))
    n_rel += sum(x is not None for x in rel)
ok &= torch.equal(torch.randn(4, generator=ga), torch.randn(4, generator=gb))
print(f"  {len(all_cases)} cases, {n_rel} relation identifiers bitwise the same, and the generators after: "
      f"{'PASS' if ok and n_rel else 'FAIL'}")

print("== equality modes: the symmetry and batching checks under --enc-equality random"
      + (" and flex (flex_attention runs eagerly on the CPU, slowly, so flex takes small tables and D4's two generators)"
         if FLEX else ""))
import warnings
warnings.filterwarnings("ignore", message=".*flex_attention.*")
base_enc = enc
small = {"the fixture's evidence tables, 40 rows each, then a random table of every column type":
         real[:2] + [suites[next(iter(suites))][0]]}
generators = {k: E.ELEMENTS[k] for k in ("D4_ID", "D4_CW", "D4_LR")}
for mode in ("random", "flex") if FLEX else ("random",):
    enc = copy.deepcopy(base_enc)
    enc.equality = mode
    for title, tabs in (suites if mode == "random" else small).items():
        symmetry(f"{mode}: {title}", tabs, E.ELEMENTS if mode == "random" else generators)
    bprogs = list(suites.values()) if mode == "random" else list(small.values())
    bprogs = bprogs + [[cut(t, 13, rng) for t in source[:3]] for _ in range(2)]   # these two share their buckets
    with torch.no_grad():
        enc.prepare()
        work = lambda seed: [(t, [enc.relation_vector(x, None) for x in t],
                              E.Identifiers(enc.c, enc.code_dim, torch.Generator().manual_seed(seed), "cpu", torch.float64)) for t in bprogs]
        together = enc.encode_programs(work(5), None)
        alone = [enc.encode_programs([w], None)[0] for w in work(5)]
        enc.release()
    e = max((a - b).abs().max().item() for a, b in zip(together, alone))
    print(f"  {mode}: batching, {len(bprogs)} programs, |together - alone| {e:.2e} {'PASS' if e < TOL else 'FAIL'}")
enc = base_enc

if FLEX:
    print("== flex against codes on the fixture, 40 rows each: the same pooled vectors, where the codes of Numbers and "
          "Idents are orthonormal (one place per value), so that the codes' scores are those of equality")


    def pooled_with(mode, tabs):
        e = copy.deepcopy(base_enc)
        e.equality, e.code_dim = mode, 256
        gen = torch.Generator().manual_seed(21)
        ids = E.Identifiers(e.c, e.code_dim, gen, "cpu", torch.float64)
        for kind, ty in (("number code", "Number"), ("ident code", "Ident")):
            vals = sorted({int(v) for t in tabs for i, x in enumerate(t.types) if x == ty
                           for v in t.cells[:, sum(E.width(y) for y in t.types[:i])]})
            assert len(vals) <= e.code_dim
            for k, v in enumerate(vals):
                ids.put(kind, v, torch.eye(e.code_dim)[k])
        with torch.no_grad():
            e.prepare()
            s = e.encode_programs([(tabs, [e.relation_vector(t, None) for t in tabs], ids)], gen)[0]
            e.release()
        return s


    s_codes, s_flex = pooled_with("codes", real), pooled_with("flex", real)
    e = (s_codes - s_flex).abs().max().item()
    print(f"  |flex - codes| {e:.2e} {'PASS' if e < 1e-5 else 'FAIL'} (max |pooled| {s_codes.abs().max().item():.2f})")

print("== random: the score of a pair of rows, one column, against the column's learned weight, over 66 values")
blk = base_enc.blocks[0]
ids = E.Identifiers(base_enc.c, base_enc.code_dim, torch.Generator().manual_seed(22), "cpu", torch.float64)
vals = np.array([3, 3] + list(range(4, 68)))
codes = ids.lookup("sign number", vals, E.RANDOM_CODE_WIDTH)[None, :, None]           # [1, n, 1, 32]
pos = torch.tensor([[5]])
with torch.no_grad():
    k_ = E.equality_keys(blk.eq[None], pos, torch.zeros(len(vals), dtype=torch.long), codes[0], 1 / E.RANDOM_CODE_WIDTH)
    score = torch.einsum("nd,mhd->hnm", codes[0].flatten(1), k_[:, 0])                  # [H, n, n]
    w = blk.eq[:, 5, 5]
equal = (score[:, 0, 1] - w).abs().max().item()
diag = (score.diagonal(dim1=1, dim2=2) - w[:, None]).abs().max().item()
off = ~torch.eye(len(vals) - 2, dtype=torch.bool)
unequal = (score[:, 2:, 2:] / w[:, None, None])[:, off]
# exactly the weight in exact arithmetic; in floating point, a sum of 32 products, to rounding
ok = max(equal, diag) <= 1e-12 * w.abs().max().item()
print(f"  equal values: |score - weight| {max(equal, diag):.1e} {'PASS' if ok else 'FAIL'}; "
      f"unequal values: score / weight has rms {unequal.pow(2).mean().sqrt().item():.3f} (1/sqrt(32) = {32 ** -0.5:.3f})")
