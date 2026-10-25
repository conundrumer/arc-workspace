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
  the column that flows from it visible, each of the two hidden in some draws with `mask_remote`; a column whose
  only source is another derived table, or whose flows name no table, must be remote, and never hidden without `mask_remote`; an unseen table must keep its
  columns, so that its flows and the flows that read it name columns it holds; and `parse_tables` must refuse an
  export whose flow names a column past its table's columns.
- The loader's checks of an export, on small exports of one case: `load_tables` must refuse to build an export
  whose checks.txt reports a violation, or gives no count line, and build it with `allow_violations`, and build one
  whose counts are all 0, or that has no checks.txt, which it must print; with `strict`, it must refuse an export
  with a copy flow from a column of another type, and one with a copy flow whose values are not the source's, from
  the build and from the cache, and without `strict` count each; a pickle without the totals must print that it is
  unchecked. `parse_tables` must count an Undefined entry, and refuse where the loader's count of unseen entries
  differs from the export's; `entry_runs` must read a Rows entry's run and refuse an Undefined entry, naming the
  case, the table and the entry.
- Masks: in a program step, no table with hidden fields may have a source table with hidden fields (no hidden
  field a source column with hidden fields, where the tables hold the column-level provenance), and each
  hidden dependent ex_output field must keep a visible occurrence of its value in another train example's output;
  without `mask_remote`, each hidden field of a derived column that has sources must keep one visible source in its
  own table or in a grid table, and no remote field is hidden; an output step does so too; a program step hides computed fields only, an output step computed ex_output fields
  only, and a prior step inferrable fields only.
- Remote groups: on a fixture whose derived table copies two columns from an earlier derived table, under
  `mask_remote` "groups" each hidden remote field's key group must be hidden with it, so that the group's other
  row, which holds the same value, is no pointer candidate, while a row of another group that holds the value stays
  visible in some draws, and a group of two rows must be hidden as often as a group of one; the field hidden alone
  in some draws with `mask_remote`; a remote column whose flows name no table, or whose source table is unseen,
  never hidden; a group never hidden past `cap`; the preflight must count the hidden remote fields and refuse a
  program where no pointer-type remote field with a row target would be hidden. Without groups, the masks must be
  bitwise those of a reference copy of the rule, and the masked loss bitwise the same with the reference copy's
  masks and with the attention probe on, which must give shares in [0, 1]. The pretrain log's remote entries must
  sum to the remote labels of `by_type`, a pointer type's target kinds to its fields, and `by_depth` must leave the
  remote fields out. Each remote pointer field's target kind must be the one a direct test of the visible rows gives,
  a row of another entry with the same key a cross-entry target; `group_chance_loss` must equal `chance_loss` where
  every group holds one field; and the matched recency reference must be given over at most the probed fields.
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
- Source rows and pointer equality: with `--enc-source-rows`, a program without source rows must give bitwise what it
  gives without the flag; on two dev programs whose derived tables have source tables, the D4, row order, permutation,
  batching and checkpointing checks must hold, and the source rows must change the vectors; on a two-table lookup
  export, equal Idents across the tables must score the source equality weight, and a source table over the table
  cap must give no keys. With `--enc-ptr-equality` too, the masked heads' D4 check must hold, and, with `--learn`, a
  hidden Color pointer must learn, from a same-row copy of its value and from the lookup's source rows, where its run without the
  flags stays at its chance level.
- Equality modes: the D4, permutation and batching checks under `--enc-equality random` and, with --flex, `flex` (on
  small tables and D4's generators, as flex_attention runs eagerly on the CPU); with --flex, flex must give what codes
  gives where the codes are orthonormal; random must score an equal pair at the learned weight.

The equality term's weights, which start at 0, are drawn at random, so that every check sees the term.

    work/lm/.venv/bin/python lm/encoder_check.py [--full] [--flex] [--learn] [tables dir]

The checks of the flex equality mode run only with --flex, and the two learnability runs of the pointer (200 training
steps each, about 45 s together) only with --learn.
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
LEARN = "--learn" in sys.argv[1:]
ARGS = [x for x in sys.argv[1:] if x not in ("--full", "--flex", "--learn")]
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
    tables, _, _ = E.load_tables(TABLES, CACHE, strict=False)
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
    tables, _, _ = E.load_tables(TABLES, CACHE, strict=False)
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
    """A small export in `d` and its task file: two cases of one task. Table 2 (Color, Number, Color, Color) has the
    key [1], a Color copied from ex_input, a constant and a Color whose flow names no table (source_table -1); table 3, the output relation (Box, Color), flows from ex_input
    and, in $Free, from table 2's Color, and in $Dep, from table 4's DET value, which flows from ex_output. $Unseen is
    $Dep with table 4 faulted, so that it is unseen and its flows and those that read it name its columns. With
    `bad`, a flow of table 2 names a column past its four."""
    import pandas as pd
    task = {"train": [{"input": [[1]], "output": [[3]]}, {"input": [[2]], "output": [[3]]}], "test": [{"input": [[1]]}]}
    (d / "tasks").mkdir(); json.dump(task, open(d / "tasks/t.json", "w"))
    grid = dict(point=2, relation=-1, column_types=["Example", "Box", "Color"], width=6, det_relations=[], det_widths=[],
                depth=0, keys=[[0, 1]], output_position=-1, output_color=-1)
    rel = lambda r, types, w, **k: dict(point=0, relation=r, column_types=types, width=w,
                                        **{"det_relations": [], "det_widths": [], "keys": [], "output_position": -1,
                                           "output_color": -1, **k})
    t2 = rel(0, ["Color", "Number", "Color", "Color"], 4, depth=1, keys=[[1]])
    t3 = rel(1, ["Box", "Color"], 5, depth=2, output_position=0, output_color=1)
    t4 = rel(2, ["Color"], 1, depth=1)
    t3_dep = {**t3, "det_relations": ["slot 2"], "det_widths": [1]}
    cases = {"$Free": [grid, grid, t2, t3], "$Dep": [grid, grid, t2, t3_dep, t4],
             "$Unseen": [grid, grid, t2, t3_dep, {**t4, "fault": "a check"}]}
    rows = {2: lambda e: [[1 + e, 0, 5, 7], [2, 1, 5, 7]], 3: lambda e: [[0, 0, 0, 0, 3]], 4: lambda e: [[3]]}
    flow = lambda tab, col, kind, st, sc, det=-1: dict(table=tab, column=col, kind=kind, source_table=st,
                                                       source_relation="", source_column=sc, det=det, atom="")
    flows = {"$Free": [flow(2, 0, 0, 0, 2), flow(2, 1, 1, 0, 1), flow(2, 2, 2, -1, -1), flow(2, 3, 0, -1, -1),
                       flow(3, 0, 0, 0, 1), flow(3, 1, 0, 2, 0)],
             "$Dep": [flow(2, 0, 0, 0, 2), flow(2, 1, 1, 0, 1), flow(2, 2, 2, -1, -1), flow(2, 3, 0, -1, -1),
                      flow(3, 0, 0, 0, 1), flow(3, 1, 0, 4, 0, 0), flow(4, 0, 1, 1, 2)]}
    flows["$Unseen"] = flows["$Dep"]
    if bad:
        flows["$Free"].append(flow(2, 4, 0, 0, 2))
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
if labels != ["computed", "inferrable", "inferrable", "remote"]:
    bad.append(("table 2 labels (Color 3, whose flow names no table, is remote)", labels))
if [t.depth for t in free[2:]] != [1, 2] or free[2].keys != [[1]] or (free[3].output_position, free[3].output_color) != (0, 1):
    bad.append(("depths, keys or output columns", [t.depth for t in free[2:]], free[2].keys))
deps = {}
for name, tabs in (("$Free", free), ("$Dep", dep)):
    lab, d_ = E.output_labels(tabs[0], tabs[1])
    deps[name] = (tabs[1].color_dependent, [E.FIELD_LABELS[x] for x in lab], d_.tolist())
if deps != {"$Free": (False, ["computed", "computed"], [False, False]),
            "$Dep": (True, ["computed", "computed"], [True, True])}:
    bad.append(("ex_output Color", deps))
remote_labels = {name: [[E.FIELD_LABELS[x] for x in lab[0]] for lab in E.field_labels(tabs)[3:] if lab is not None]
                 for name, tabs in (("$Free", free), ("$Dep", dep))}
if remote_labels != {"$Free": [["computed", "remote"]], "$Dep": [["computed", "remote"], ["computed"]]}:
    bad.append(("remote labels (tables 3 and 4: Box from ex_input, Color from a derived table)", remote_labels))
g, both, alone = torch.Generator().manual_seed(23), 0, {"table 4": 0, "table 3 Color": 0}
for _ in range(200):   # the old rule, --mask-remote: table 3's Color is hidden in some draws
    ms = enc.draw_masks(dep, 1.0, 10 ** 6, g, "program", mask_remote=True)
    src, out_ = bool(ms[4][:, 0].any()), bool(ms[3][:, 1].any())
    both += src and out_
    alone["table 4"] += src and not out_; alone["table 3 Color"] += out_ and not src
if both or not all(alone.values()):
    bad.append(("coordination", both, alone))
remote_default, others_default = 0, 0
for tabs in (free, dep):
    for _ in range(100):   # the default: a column whose only source is a derived table is never hidden
        ms = enc.draw_masks(tabs, 1.0, 10 ** 6, g, "program")
        remote_default += int(ms[3][:, 1].any()) + int(ms[2][:, 3].any())
        others_default += int(ms[3][:, 0].any())
counted = {flag: E.preflight([("dep", dep)], 1.0, 10 ** 6, mask_remote=flag) for flag in (False, True)}
if remote_default or not others_default or counted[False] != counted[True] or counted[False]["remote"] != dep[3].n + dep[2].n:
    bad.append(("remote fields by default", remote_default, others_default, counted))
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
if "flow [2, 4, 0, 0, 2, -1]" not in refused:
    bad.append(("a flow past the columns", refused))
print(f"  table 2 labels {labels}; ex_output Color (color_dependent, labels, dependent) {deps}; hidden in 200 "
      f"program steps with --mask-remote: the source column and the column that flows from it together {both}, "
      f"each alone {alone}; table 3 Color and table 2 column 3 (a flow without a source table), labelled remote, hidden in {remote_default} of 200 program steps by "
      f"default; "
      f"an unseen source table keeps its columns for the flows: {unseen_ok}; a flow past its table's columns: "
      f"{refused!r}; "
      f"{'PASS' if not bad else 'FAIL ' + str(bad)}")

print("== the loader's checks of an export: checks.txt, the unseen counts, the entry reader and the copy flows, on small "
      "exports")


def checked_export(d, variant="clean"):
    """A small export in `d` and its task file: one case, whose table 2 (Color, Number) copies its Color from ex_input
    and table 3 (Color) its Color from table 2's. With `variant` "type", table 3's flow names table 2's Number
    instead; "value", table 3 holds a Color that table 2 does not; "undefined", table 3 has a third entry, of the
    kind Undefined."""
    import pandas as pd
    task = {"train": [{"input": [[1]], "output": [[3]]}, {"input": [[2]], "output": [[3]]}], "test": [{"input": [[1]]}]}
    (d / "tasks").mkdir(); json.dump(task, open(d / "tasks/t.json", "w"))
    grid = dict(point=2, relation=-1, column_types=["Example", "Box", "Color"], width=6)
    tabs = [grid, grid, dict(point=0, relation=0, column_types=["Color", "Number"], width=2),
            dict(point=0, relation=1, column_types=["Color"], width=1)]
    rows = {2: [[1, 5], [2, 6]], 3: [[4 if variant == "value" else 1]]}
    flow = lambda tab, st, sc: dict(task="t", case="$C", concept=False, table=tab, column=0, kind=0, source_table=st,
                                    source_relation="", source_column=sc, det=-1, atom="")
    tables, index, values = [], [], []
    for i, t in enumerate(tabs):
        tables.append(dict(task="t", case="$C", concept=False, table=i, token=i, projections=0, fault=None,
                           det_relations=[], det_widths=[], depth=min(i, 2), keys=[], output_position=-1,
                           output_color=-1, **t))
        for e in range(2 if i in rows else 0):
            index.append(dict(task="t", case="$C", table=i, entry=len(index), kind=0, rows=len(rows[i]),
                              offset=len(values), example_kind=1, example_index=e, model=0))
            values += [x for r in rows[i] for x in r]
    if variant == "undefined":
        index.append(dict(task="t", case="$C", table=3, entry=len(index), kind=2, rows=0, offset=0, example_kind=2,
                          example_index=0, model=0))
    (d / "values/t").mkdir(parents=True)
    np.array(values, np.int32).tofile(d / "values/t/$C.i32")
    pd.DataFrame(tables).to_parquet(d / "tables.parquet")
    pd.DataFrame(index).to_parquet(d / "index.parquet")
    pd.DataFrame([flow(2, 0, 2), flow(3, 2, 1 if variant == "type" else 0)]).to_parquet(d / "flows.parquet")
    pd.DataFrame(columns=["task", "case", "entry", "det", "rows", "offset"]).to_parquet(d / "assigned.parquet")
    pd.DataFrame(columns=["task", "case", "table", "columns", "width"]).to_parquet(d / "projections.parquet")
    pd.DataFrame(columns=["task", "case", "projection", "entry", "defined", "rows", "offset"]).to_parquet(
        d / "projection_rows.parquet")


def checked_load(variant, checks=None, **kw):
    """load_tables on a fresh `checked_export` with `checks` as its checks.txt (none where None), and a fresh cache:
    (the stats or the DataFault's text, what it printed, then the same of a second load, from the cache)."""
    import contextlib, io
    with tempfile.TemporaryDirectory() as tmp:
        checked_export(Path(tmp), variant)
        if checks is not None:
            open(Path(tmp) / "checks.txt", "w").write(checks)
        out = []
        for _ in range(2):
            text = io.StringIO()
            with contextlib.redirect_stdout(text):
                try:
                    got = E.load_tables(tmp, Path(tmp) / "tables.pkl", tasks_dir=Path(tmp) / "tasks", **kw)[2]
                except E.DataFault as x:
                    got = str(x)
            out += [got, text.getvalue()]
        return out


bad, seen = [], {}
violated = "copy types: 3 tables\ncopy types: 3, depths: 0\n"
s, printed, _, _ = checked_load("clean", "copy types: 0, depths: 0\n")
seen["clean, a clean checks.txt"] = s["copy flows"]["checked"] if isinstance(s, dict) else s
if not isinstance(s, dict) or s["copy flows"]["type"] + s["copy flows"]["value"] or s["copy flows"]["checked"] != 2:
    bad.append(("a clean export", s))
s, printed, _, _ = checked_load("clean")
if not isinstance(s, dict) or "carries no checks.txt" not in printed:
    bad.append(("no checks.txt", s, printed))
for checks, want in ((violated, "refused"), ("copy types: 0, depths: 2\n", "refused"), ("copy types: 0\n\n", "built"),
                     ("a line that gives no count\n", "refused"), ("", "refused")):
    s, _, _, _ = checked_load("clean", checks)
    got = "refused" if isinstance(s, str) and "checks.txt reports" in s else "built" if isinstance(s, dict) else s
    seen[f"checks.txt {checks!r}"] = got
    if got != want:
        bad.append(("checks.txt", checks, s))
s, printed, _, _ = checked_load("clean", violated, allow_violations=True)
if not isinstance(s, dict) or "built under allow_violations" not in printed:
    bad.append(("allow_violations", s))
for variant, kind in (("type", "type"), ("value", "value")):
    strict, _, strict_cached, _ = checked_load(variant)
    loose, printed, _, _ = checked_load(variant, strict=False)
    seen[f"{variant}: strict, loose"] = ("refused" if isinstance(strict, str) else "built",
                                         {k: loose["copy flows"][k] for k in ("checked", "type", "value")}
                                         if isinstance(loose, dict) else loose)
    if not (isinstance(strict, str) and "copy flows" in strict and "flow [3, 0, 0, 2" in strict
            and isinstance(strict_cached, str) and "copy flows" in strict_cached and isinstance(loose, dict)
            and loose["copy flows"][kind] == 1 and loose["copy flows"]["cases"] == 1
            and ("1 with" if kind == "type" else "1 columns with") in printed):
        bad.append((variant, strict, strict_cached, loose))
import contextlib, io
text = io.StringIO()
with contextlib.redirect_stdout(text):
    E.copy_flow_rule({"provenance": "a pickle built before the check"}, True, "an old cache")
if "unchecked" not in text.getvalue():
    bad.append(("a pickle without the totals", text.getvalue()))
with tempfile.TemporaryDirectory() as tmp:
    checked_export(Path(tmp), "undefined")
    utabs, _, _ = E.parse_tables(tmp, Path(tmp) / "tasks")
    seen["undefined entry"] = E.unseen_counts(utabs)[1]
    parse_table = E.parse_table   # a loader that loses its count of unseen entries
    E.parse_table = lambda *a, **k: [E.Table(**{**t.__dict__, "unseen_entries": {}}) for t in parse_table(*a, **k)]
    try:
        E.parse_tables(tmp, Path(tmp) / "tasks")
        mismatch = "no fault"
    except E.DataFault as x:
        mismatch = str(x)
    finally:
        E.parse_table = parse_table
if seen["undefined entry"] != {"an entry is undefined": 1} or "the loader's {}" not in mismatch \
        or "{'an entry is undefined': 1}" not in mismatch:
    bad.append(("a count mismatch", seen["undefined entry"], mismatch))
t3 = {"table": 3, "column_types": ["Color"], "width": 1}
runs = [E.entry_runs(t3, {"kind": 0, "entry": 4, "rows": 2, "offset": 8}, {}, {}, "t $C"),
        E.entry_runs(t3, {"kind": 1, "entry": 4, "rows": 2, "offset": 8}, {}, {}, "t $C")]
try:
    E.entry_runs(t3, {"kind": 2, "entry": 4, "rows": 0, "offset": 0}, {}, {}, "t $C")
    refused = "no fault"
except E.DataFault as x:
    refused = str(x)
if runs != [[([0], 1, 2, 8)], "a count with no projections"] or not refused.startswith("t $C table 3 entry 4"):
    bad.append(("the entry reader", runs, refused))
print(f"  {seen}; a count mismatch: {mismatch!r}; an Undefined entry's read: {refused!r} "
      f"{'PASS' if not bad else 'FAIL ' + str(bad)}")

print("== masks: the sources stay visible in a program and an output step, and each step kind hides its label alone "
      "(200 draws per kind, frac 0.5, without and with --mask-remote)")
mask_progs = {"fixture": real, "small task": small, "random tables": suites[next(iter(suites))],
              "provenance $Free": free, "provenance $Dep": dep}
bad, seen = [], {}
for kind, remote in [(k, r) for k in E.STEP_KINDS for r in (False, True)]:
    g = torch.Generator().manual_seed(21)
    for name, tabs in mask_progs.items():
        labs, srcs, cols = E.field_labels(tabs), E.table_sources(tabs), E.provenance(tabs) and E.column_sources(tabs)
        for _ in range(200):
            ms = enc.draw_masks(tabs, 0.5, 10 ** 6, g, kind, mask_remote=remote)
            held = {j for j, m in enumerate(ms) if m is not None and m.any()}
            for j in held:
                lab = labs[j][ms[j]]
                for x in np.unique(lab):
                    key = (kind, E.FIELD_LABELS[x], "evidence" if tabs[j].evidence else "derived")
                    seen[key] = seen.get(key, 0) + int((lab == x).sum())
                if (~np.isin(lab, (E.INFERRABLE,) if kind == "prior" else
                             (E.COMPUTED, E.REMOTE) if remote and kind == "program" else (E.COMPUTED,))).any():
                    bad.append((kind, remote, name, j, "label"))
                if kind == "output" and tabs[j].relation != "ex_output":
                    bad.append((kind, remote, name, j, "a table other than ex_output"))
                if kind == "program" and not cols and srcs[j] & held:
                    bad.append((kind, remote, name, j, "a source table holds hidden fields"))
                hidden = {(k, c) for k in held for c in np.flatnonzero(ms[k].any(0)).tolist()}
                if kind == "program" and cols and any(cols[j][c] & hidden for c in np.flatnonzero(ms[j].any(0))):
                    bad.append((kind, remote, name, j, "a source column holds hidden fields"))
                if kind == "program" and cols and not remote and not tabs[j].evidence:
                    for c in np.flatnonzero(ms[j].any(0)):   # a source in the field's own table or a grid table
                        near = {(i, d) for i, d in cols[j][c] if i == j or tabs[i].evidence}
                        seen["program: hidden derived column with sources"] = seen.get(
                            "program: hidden derived column with sources", 0) + bool(cols[j][c])
                        if cols[j][c] and (not near or near & hidden):
                            bad.append((kind, remote, name, j, "no visible source in its own table or a grid table"))
                if kind in ("program", "output") and tabs[j].relation == "ex_output":
                    col, t = tabs[j].types.index("Color"), tabs[j]
                    ex, color = t.cells[:, 0], t.cells[:, E.EVIDENCE_COLOR]
                    dep_ = E.output_labels(E.evidence_input(tabs), t)[1]
                    for r in np.flatnonzero(ms[j][:, col] & dep_):
                        seen[f"{kind}: hidden dependent"] = seen.get(f"{kind}: hidden dependent", 0) + 1
                        if not (~ms[j][:, col] & (color == color[r]) & (ex != ex[r])).any():
                            bad.append((kind, remote, name, j, "a dependent field's occurrences all hidden"))
                if not remote and (lab == E.REMOTE).any():
                    bad.append((kind, remote, name, j, "a remote field hidden by default"))
ok = not bad and all(seen.get(f"{k}: hidden dependent", 0) > 0 for k in ("program", "output")) and all(
    seen.get(k, 0) > 0 for k in [("program", "computed", "evidence"), ("program", "computed", "derived"),
                                 ("program", "remote", "derived"), "program: hidden derived column with sources",
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
lm_tables, _, _ = E.load_tables(TABLES, CACHE, strict=False)
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

print("== --enc-source-rows: a program without source rows, flag on against flag off, bitwise (the pooled vectors, the "
      "masked loss and its gradients, with every batch checkpointed)")
torch.manual_seed(0)
src_enc = E.FeatureEncoder(embed, in_index, id_dim=16, orientations=orient, K=4, layers=2, c=32, heads=4, source_rows=True)
missing, unexpected = src_enc.load_state_dict(enc.state_dict(), strict=False)
assert not unexpected and all(k.endswith(".src_eq") for k in missing), (missing, unexpected)
src_enc.eval()


def masked_grads(e, progs, ckpt=True, remote=False):
    """The masked loss of `progs` under `e`, and its gradients, every batch checkpointed where `ckpt`."""
    e.checkpoint, ckpt_min = ckpt, E.CHECKPOINT_MIN
    E.CHECKPOINT_MIN = 0
    try:
        e.zero_grad()
        loss, _ = e.masked_loss([(t, [None] * len(t)) for t in progs], torch.Generator().manual_seed(8), 0.3, 10 ** 6,
                                torch.Generator().manual_seed(9), mask_remote=remote)
        loss.backward()
    finally:
        e.checkpoint, E.CHECKPOINT_MIN = False, ckpt_min
    grads = {n: p.grad.clone() for n, p in e.named_parameters() if p.grad is not None}
    e.zero_grad()
    return loss.detach(), grads


def run_with(e, tables):
    """`run` under the encoder e."""
    global enc
    kept, enc = enc, e
    try:
        return run(tables)
    finally:
        enc = kept


no_src = list(suites.values())
s_off = [run_with(base_enc, t)[0] for t in no_src]
s_on = [run_with(src_enc, t)[0] for t in no_src]
l_off, g_off = masked_grads(base_enc, no_src)
l_on, g_on = masked_grads(src_enc, no_src)
ok = (all(torch.equal(a, b) for a, b in zip(s_off, s_on)) and torch.equal(l_off, l_on) and g_off.keys() == g_on.keys()
      and all(torch.equal(g_off[n], g_on[n]) for n in g_off))
print(f"  {len(no_src)} programs without column-level provenance: pooled vectors, loss {l_on.item():.6f} and "
      f"{len(g_on)} gradients bitwise the same {'PASS' if ok else 'FAIL'}")

print("== --enc-source-rows: D4, row order and identifier permutations, batching and checkpointing on two dev programs "
      "whose derived tables have source tables, 30 rows each, the source equality weights drawn at random")
with torch.no_grad():
    for blk in src_enc.blocks:
        blk.src_eq.copy_(torch.randn(blk.src_eq.shape, generator=eq_gen))
cut_rng = np.random.default_rng(7)
src_progs = {k: [cut(t, 30, cut_rng) for t in lm_tables[k]] for k in [case, ("0520fde7", "$Table $Lookup")]}
for k, ts in src_progs.items():
    srcs, pairs = E.source_tables(ts)
    print(f"  {k[0]} {k[1]}: {sum(map(bool, srcs))} of {len(ts)} tables read source rows, of the column types "
          f"{sorted({ts[j].types[c] for p in pairs for col in p for j, c in col})}")
    enc = src_enc
    try:
        symmetry(f"source rows: {k[0]} {k[1]}", ts)
    finally:
        enc = base_enc
some = src_progs[("0520fde7", "$Table $Lookup")]
s_on = run_with(src_enc, some)[0]
with torch.no_grad():
    w_saved = [blk.src_eq.clone() for blk in src_enc.blocks]
    for blk in src_enc.blocks:
        blk.src_eq.zero_()
    s_zero = run_with(src_enc, some)[0]
    for blk, w in zip(src_enc.blocks, w_saved):
        blk.src_eq.copy_(w)
s_off = run_with(base_enc, some)[0]
e_off, e_zero = (s_on - s_off).abs().max().item(), (s_on - s_zero).abs().max().item()
print(f"  the source rows reach the vectors: |on - off| {e_off:.2e}, |on - on with the source equality weights at 0| "
      f"{e_zero:.2e} {'PASS' if e_off > 1e-3 and e_zero > 1e-3 else 'FAIL'}")
plist = list(src_progs.values()) + [[cut(t, 13, rng) for t in some] for _ in range(2)]
for cost in (E.BATCH_COST, 0):
    saved_cost, E.BATCH_COST = E.BATCH_COST, cost
    try:
        with torch.no_grad():
            src_enc.prepare()
            work = lambda seed: [(t, [src_enc.relation_vector(x, None) for x in t],
                                  E.Identifiers(src_enc.c, src_enc.code_dim, torch.Generator().manual_seed(seed), "cpu",
                                                torch.float64)) for t in plist]
            together = src_enc.encode_programs(work(5), None)
            alone = [src_enc.encode_programs([w], None)[0] for w in work(5)]
            src_enc.release()
    finally:
        E.BATCH_COST = saved_cost
    e = max((a - b).abs().max().item() for a, b in zip(together, alone))
    print(f"  batching, BATCH_COST {cost}: {len(plist)} programs, |together - alone| {e:.2e} {'PASS' if e < TOL else 'FAIL'}")
l1, g1 = masked_grads(src_enc, [some], remote=True)   # the source rows serve the remote columns
l0, g0 = masked_grads(src_enc, [some], ckpt=False, remote=True)
e = max((g0[n] - g1[n]).abs().max().item() for n in g0)
ok = g0.keys() == g1.keys() and e < 1e-12 and any(n.endswith("src_eq") for n in g0) and abs(l0 - l1).item() < 1e-12
print(f"  checkpointing: {len(g0)} gradients, the source equality weights' among them, |with - without| {e:.2e} "
      f"{'PASS' if ok else 'FAIL'}")

print("== --enc-source-rows: a two-table lookup export, table B's Ident and Color copied from table A's, keyed by the "
      "Ident")


def lookup_export(d, rng, cases=32, n=16):
    """An export of `cases` cases of one task, in `d`: tables A (Ident, Color) and B (Ident, Color), each with the key
    Ident; B holds A's rows in another order, and its columns flow from A's."""
    import pandas as pd
    task = {"train": [{"input": [[0]], "output": [[0]]}], "test": [{"input": [[0]]}]}
    (d / "tasks").mkdir(); json.dump(task, open(d / "tasks/t.json", "w"))
    grid = dict(point=2, relation=-1, column_types=["Example", "Box", "Color"], width=6, det_relations=[], det_widths=[],
                depth=0, keys=[[0, 1]], output_position=-1, output_color=-1)
    rel = lambda r, depth: dict(point=0, relation=r, column_types=["Ident", "Color"], width=2, det_relations=[],
                                det_widths=[], depth=depth, keys=[[0]], output_position=-1, output_color=-1)
    flow = lambda case, col: dict(task="t", case=case, concept=False, table=3, column=col, kind=0, source_table=2,
                                  source_relation="", source_column=col, det=-1, atom="")
    tables, index, flows = [], [], []
    (d / "values/t").mkdir(parents=True)
    for k in range(cases):
        case, color, order = f"$C{k}", rng.integers(0, 4, n), rng.permutation(n)
        rows, values = {2: [[100 + i, color[i]] for i in range(n)], 3: [[100 + i, color[i]] for i in order]}, []
        for i, t in enumerate([grid, grid, rel(0, 1), rel(1, 2)]):
            tables.append(dict(task="t", case=case, concept=False, table=i, token=i, projections=0, fault=None, **t))
            if i in rows:
                index.append(dict(task="t", case=case, table=i, entry=i, kind=0, rows=n, offset=len(values),
                                  example_kind=1, example_index=0, model=0))
                values += [x for r in rows[i] for x in r]
        np.array(values, np.int32).tofile(d / f"values/t/{case}.i32")
        flows += [flow(case, 0), flow(case, 1)]
    pd.DataFrame(tables).to_parquet(d / "tables.parquet")
    pd.DataFrame(index).to_parquet(d / "index.parquet")
    pd.DataFrame(flows).to_parquet(d / "flows.parquet")
    pd.DataFrame(columns=["task", "case", "entry", "det", "rows", "offset"]).to_parquet(d / "assigned.parquet")
    pd.DataFrame(columns=["task", "case", "table", "columns", "width"]).to_parquet(d / "projections.parquet")
    pd.DataFrame(columns=["task", "case", "projection", "entry", "defined", "rows", "offset"]).to_parquet(
        d / "projection_rows.parquet")


with tempfile.TemporaryDirectory() as tmp:
    lookup_export(Path(tmp), np.random.default_rng(0))
    lk, lk_faults, _ = E.parse_tables(tmp, Path(tmp) / "tasks")
lookups = list(lk.values())
A_, B_ = lookups[0][2], lookups[0][3]
srcs, pairs = E.source_tables(lookups[0])
ok_src = not lk_faults and srcs == [[], [], [], [2]] and pairs[3] == [[(2, 0)], [(2, 1)]]
# the equality part of B's scores against A's rows at the first layer, with the Ident pair's weight at 5 and the rest 0
with torch.no_grad():
    for blk in src_enc.blocks:
        blk.src_eq.zero_(); blk.src_eq[:, 0, 0] = 5.0 / E.SOURCE_EQ_GAIN
spied, attend_fn = [], E.attend
E.attend = lambda q, k, v, mask, flex=None: (spied.append((q, k, mask)), attend_fn(q, k, v, mask, flex))[1]
try:
    run_with(src_enc, lookups[0])
finally:
    E.attend = attend_fn
q, k, mask = spied[-len(src_enc.blocks)]   # B's level, the first layer
W0 = src_enc.c // src_enc.blocks[0].heads * E.NPOS
eq_s = q[0, :B_.n, :, W0:].transpose(0, 1) @ k[0, -A_.n:, :, W0:].permute(1, 2, 0)          # [H, B rows, A rows]
match = torch.from_numpy(B_.cells[:, :1] == A_.cells[:, 0][None])
e_match = (eq_s[:, match] - 5.0).abs().max().item()
off = eq_s[:, ~match].abs().max().item()
ok = ok_src and e_match < 1e-9 and off < 5.0 and bool(mask[0, 0, 0, -A_.n:].all())
print(f"  B's source tables {srcs[3]}, its columns' pairs {pairs[3]}; at the first layer, B's scores against A's rows "
      f"in the equality channels, Ident weight 5: equal Idents |score - 5| {e_match:.1e}, unequal Idents at most "
      f"{off:.2f} (random codes); A's {A_.n} rows unmasked keys {'PASS' if ok else 'FAIL'}")
capped = {("t", "c"): [copy.copy(t) for t in lookups[0][:3]]}
over = E.mark_over_rows(capped, A_.n - 1)
capped = capped[("t", "c")] + [B_]
s_capped_on, s_capped_off = run_with(src_enc, capped)[0], run_with(base_enc, capped)[0]
ok = E.source_tables(capped)[0][3] == [] and len(over) == 1 and torch.equal(s_capped_on, s_capped_off)
print(f"  table A over --enc-max-rows: B has no source rows, and flag on gives bitwise what flag off gives "
      f"{'PASS' if ok else 'FAIL'}")

print("== --enc-source-rows --enc-ptr-equality: the masked loss heads under D4, the same fields masked (frac 0.3), in a "
      "program step, on the two dev programs; the pointer logits and every field's loss must not change")
torch.manual_seed(0)
ptr_enc = E.FeatureEncoder(embed, in_index, id_dim=16, orientations=orient, K=4, layers=2, c=32, heads=4,
                           source_rows=True, ptr_equality=True)
ptr_enc.load_state_dict(src_enc.state_dict(), strict=False)
ptr_enc.eval()
with torch.no_grad():
    for blk in ptr_enc.blocks:
        blk.src_eq.copy_(torch.randn(blk.src_eq.shape, generator=eq_gen))
    ptr_enc.heads.ptr_eq.copy_(torch.randn(ptr_enc.heads.ptr_eq.shape, generator=eq_gen) / E.POINTER_EQ_GAIN)
    ptr_enc.heads.ptr_src.copy_(torch.randn(ptr_enc.heads.ptr_src.shape, generator=eq_gen) / E.POINTER_EQ_GAIN)
for k, tabs in src_progs.items():
    masks = ptr_enc.draw_masks(tabs, 0.3, 10 ** 6, torch.Generator().manual_seed(3), "program")
    enc = ptr_enc
    try:
        r0 = run_masked(tabs, masks)
        worst, fields = {"loss": 0.0, "pointer": 0.0}, sum(len(r["label"]) for _, _, r in r0)
        for name, g in E.ELEMENTS.items():
            r1 = run_masked([transform(t, g) for t in tabs], masks)
            for (_, _, a), (_, _, b) in zip(r0, r1):
                worst["loss"] = max(worst["loss"], (a["loss"] - b["loss"]).abs().max().item())
                if "pointer" in a["out"]:
                    pa, pb = a["out"]["pointer"][1], b["out"]["pointer"][1]
                    fa = torch.isfinite(pa)
                    worst["pointer"] = max(worst["pointer"], (pa[fa] - pb[fa]).abs().max().item()
                                           if torch.equal(fa, torch.isfinite(pb)) else float("inf"))
    finally:
        enc = base_enc
    pointers = sum(len(r["out"]["pointer"][0]) for _, _, r in r0 if "pointer" in r["out"])
    print(f"  {k[0]} {k[1]}: {fields} masked fields, {pointers} pointers; worst change loss {worst['loss']:.1e}, "
          f"pointer {worst['pointer']:.1e} {'PASS' if pointers and max(worst.values()) < TOL else 'FAIL'}")

print("== --enc-ptr-equality and --enc-source-rows: learnability of a hidden Color pointer, 200 steps of AdamW (lr 1e-3, "
      "warmup 20, clip 1.0) at c 32 in float32, four programs a step, 30% of the Color fields hidden; the mean pointer "
      "loss / its chance level (ratio) over each 50 steps. A run with the flags passes where its last 50 steps' ratio "
      "is under 0.3, and the run without them where it is over 0.8")


def same_row_table(rng, n=16):
    """A table (Ident, Color, Color) whose second Color column copies the first."""
    color = rng.integers(0, 4, n)
    return E.Table(step=1, relation=7, evidence=False, unseen=None, largest=n, export_table=None,
                   entry=np.zeros(n, np.int32), positions=[0, 1, 2], types=["Ident", "Color", "Color"],
                   cells=np.stack([100 + np.arange(n), color, color], 1).astype(np.int32),
                   present=np.ones((n, 3), bool), example=np.full(n, -1, np.int16), example_kind=np.zeros(n, np.int8),
                   assignment=np.zeros((n, 0), np.int32), model=np.zeros(n, np.int32), part=np.zeros(n, np.int32),
                   marker=np.zeros(n, bool), unseen_entries={})


def learn(draw, hidden, flags, steps=200):
    """The pointer curve of an encoder with `flags`, trained on the programs `draw(rng)` gives, with 30% of the
    Color fields of the table `hidden` hidden."""
    torch.set_default_dtype(torch.float32)
    try:
        torch.manual_seed(0)
        e = E.FeatureEncoder(nn.Embedding(len(in_names), 48), in_index, id_dim=16, orientations=orient, K=4, layers=2,
                             c=32, heads=4, **flags)
        params = [p for p in e.parameters() if p.requires_grad]
        opt = torch.optim.AdamW(params, lr=1e-3, weight_decay=0.0)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda i: min(1.0, (i + 1) / 20))
        r_, hist, curve = np.random.default_rng(1), [], []
        for step in range(steps):
            drawn = draw(r_)
            masks = []
            for ts in drawn:
                m = [None if not t.n else np.zeros((t.n, len(t.types)), bool) for t in ts]
                m[hidden][:, 1] = r_.random(ts[hidden].n) < 0.3
                m[hidden][0, 1] = True
                masks.append(m)
            gen = torch.Generator().manual_seed(step)
            e.prepare()
            try:
                work = [(ts, [e.relation_vector(t, None) for t in ts], E.Identifiers(e.c, e.code_dim, gen, "cpu"))
                        for ts in drawn]
                _, recs = e.encode_programs(work, gen, masks)
            finally:
                e.release()
            loss = torch.cat([r["loss"] for _, _, r in recs])
            opt.zero_grad(); loss.mean().backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step(); sched.step()
            hist.append((loss.mean().item(), torch.cat([r["chance_loss"] for _, _, r in recs]).mean().item()))
            if step % 50 == 49:
                curve.append(tuple(np.mean(hist[-50:], 0)))
        return curve
    finally:
        torch.set_default_dtype(torch.float64)


cases_ = {"a same-row cue: one table (Ident, Color, a copy of Color), the first Color hidden":
              (lambda r: [[same_row_table(r)] for _ in range(4)], 0, dict(ptr_equality=True), {}),
          "the lookup export, B's Color hidden":
              (lambda r: [lookups[i] for i in r.choice(len(lookups), 4, replace=False)], 3,
               dict(source_rows=True, ptr_equality=True), {})}
for title, (draw, hidden, on, off) in cases_.items() if LEARN else []:
    print(f"  {title}")
    for flags, want in ((on, lambda x: x < 0.3), (off, lambda x: x > 0.8)):
        curve = learn(draw, hidden, flags)
        ratio = curve[-1][0] / curve[-1][1]
        print(f"    {' '.join('--enc-' + k.replace('_', '-') for k in flags) or 'no flags'}: "
              + ", ".join(f"steps {50 * i + 1}-{50 * i + 50} {l:.3f}/{c:.3f} ({l / c:.2f})" for i, (l, c) in enumerate(curve))
              + f" {'PASS' if want(ratio) else 'FAIL'}")
if not LEARN:
    print("  skipped: run with --learn")

print("== --mask-remote-groups: on a fixture whose derived table B (Ident, Number, Color) copies its Ident and Color "
      "from table A, the key group of a hidden remote field is hidden with it (300 program steps, frac 0.5)")


def group_fixture(shift=0):
    """ex_input and ex_output of the provenance export's $Free, then A (Ident, Color; key Ident, both columns from
    ex_input's Color) and B (Ident, Number, Color), whose Ident and Color are copied from A and whose Number is
    computed from ex_input's Position; per example's entry, B's rows (1, 5, 3), (1, 6, 3), (2, 7, 3), (3, 8, 4): the
    rows of Ident 1 are one key group of the Color column, and both hold Color 3, which the row of Ident 2 holds too.
    The second example's entry adds `shift` to each Ident, so that with a shift no row of one entry agrees with a
    row of the other on the Ident."""
    def table(i, types, rows, keys, flows):
        n = 2 * len(rows)
        second = [[x + shift if k == 0 else x for k, x in enumerate(row)] for row in rows]
        return E.Table(step=i, relation=i, evidence=False, unseen=None, largest=len(rows), export_table=i,
                       positions=list(range(len(types))), types=types, cells=np.array(rows + second, np.int32),
                       present=np.ones((n, len(types)), bool), example=np.repeat([0, 1], len(rows)).astype(np.int16),
                       example_kind=np.ones(n, np.int8), assignment=np.full((n, 0), -1, np.int32),
                       model=np.zeros(n, np.int32), entry=np.repeat([0, 1], len(rows)).astype(np.int32),
                       part=np.zeros(n, np.int32), marker=np.zeros(n, bool), unseen_entries={}, det_relations=[],
                       depth=i - 1, keys=keys, output_position=-1, output_color=-1,
                       flows=np.array([f + [-1] for f in flows], np.int32))
    a = table(2, ["Ident", "Color"], [[1, 3], [2, 3], [3, 4]], [[0]], [[0, 1, 0, 2], [1, 0, 0, 2]])
    b = table(3, ["Ident", "Number", "Color"], [[1, 5, 3], [1, 6, 3], [2, 7, 3], [3, 8, 4]], [],
              [[0, 0, 2, 0], [1, 1, 0, 1], [2, 0, 2, 1]])
    return [free[0], free[1], a, b]


grp = group_fixture()
bad, seen = [], {"r0 hidden": 0, "r0 hidden, r2 visible": 0, "leak under --mask-remote": 0, "B Ident hidden": 0}
g = torch.Generator().manual_seed(31)
for _ in range(300):
    for remote in (True, "groups"):
        ms = enc.draw_masks(grp, 0.5, 10 ** 6, g, "program", mask_remote=remote)
        col = ms[3][:, 2]
        for e in (0, 4):   # the first row of each entry
            if remote is True:
                seen["leak under --mask-remote"] += bool(col[e] != col[e + 1])
                continue
            if col[e] != col[e + 1]:
                bad.append(("a key group's Color hidden apart", col.tolist()))
            seen["r0 hidden"] += bool(col[e]); seen["r0 hidden, r2 visible"] += bool(col[e] and not col[e + 2])
        if remote == "groups":
            seen["B Ident hidden"] += bool(ms[3][:, 0].any())
            if ms[3][:, 2].any() and ms[2][:, 1].any():
                bad.append(("B's Color and its source A's Color hidden together",))
labels = [E.FIELD_LABELS[x] for x in E.column_labels(grp, 3)]
groups_of = E.key_groups(grp, 3, 2).tolist()
if labels != ["remote", "computed", "remote"] or len(set(groups_of)) != 6 or groups_of[0] != groups_of[1]:
    bad.append(("labels or key groups", labels, groups_of))
if not all(seen.values()):
    bad.append(("draws", seen))
# a remote column whose flows name no table (table 2 column 3 of $Free) and one whose source table is unseen
# (table 3 column 1 of $Unseen) are never hidden; one whose source is seen (table 3 column 1 of $Dep) is
never = {"$Free table 2 column 3": 0, "$Unseen table 3 column 1": 0, "$Dep table 3 column 1": 0}
for _ in range(200):
    never["$Free table 2 column 3"] += bool(enc.draw_masks(free, 1.0, 10 ** 6, g, "program", "groups")[2][:, 3].any())
    never["$Unseen table 3 column 1"] += bool(enc.draw_masks(unseen_t, 1.0, 10 ** 6, g, "program", "groups")[3][:, 1].any())
    never["$Dep table 3 column 1"] += bool(enc.draw_masks(dep, 1.0, 10 ** 6, g, "program", "groups")[3][:, 1].any())
if never["$Free table 2 column 3"] or never["$Unseen table 3 column 1"] or not never["$Dep table 3 column 1"]:
    bad.append(("columns without a seen source pair", never))
# a group counts toward --mask-cap: at cap 1, the two rows of Ident 1 are never hidden, the row of Ident 3 is
capped = [0, 0]
for _ in range(200):
    col = enc.draw_masks(grp, 1.0, 1, g, "program", "groups")[3][:, 2]
    capped[0] += bool(col[[0, 1, 4, 5]].any()); capped[1] += bool(col[[3, 7]].any())
if capped[0] or not capped[1]:
    bad.append(("the cap", capped))
print(f"  B labels {labels}, Color key groups {groups_of}; {seen}; never hidden or hidden {never}; at cap 1, the group "
      f"of two rows hidden in {capped[0]} and the row of Ident 3 in {capped[1]} of 200 draws "
      f"{'PASS' if not bad else 'FAIL ' + str(bad)}")

print("== --mask-remote-groups preflight: the fixture's hidden remote fields by type, and a refusal where no remote "
      "field would be hidden ($Unseen)")
grp2 = group_fixture(10)
counted = E.preflight([("groups", grp2)] * 8, 0.5, 10 ** 6, mask_remote="groups")   # eight draws
try:
    E.preflight([("unseen", unseen_t)], 1.0, 10 ** 6, mask_remote="groups")
    refused = "no fault"
except E.DataFault as x:
    refused = str(x)
try:   # the fixture without the shift: every row target of B's Ident is a row of the other entry
    E.preflight([("groups", grp)], 1.0, 10 ** 6, mask_remote="groups", seed=3)
    refused_cross = "no fault"
except E.DataFault as x:
    refused_cross = str(x)
ok = (sum(x[0] - x[1] - x[2] for x in counted["hidden remote"].values()) > 0 and "hide no remote field" in refused
      and "another entry" in refused_cross)
print(f"  shifted fixture {counted['hidden remote']}; $Unseen: {refused!r}; unshifted fixture at frac 1: "
      f"{refused_cross[:90]!r} {'PASS' if ok else 'FAIL'}")


def reference_masks(tables, frac, cap, gen, kind, mask_remote=False):
    """A reference copy of `draw_masks` with `mask_remote` False or True."""
    want = E.INFERRABLE if kind == "prior" else E.COMPUTED
    out = []
    for t, lab in zip(tables, E.field_labels(tables)):
        if not t.n or not len(t.types):
            out.append(None); continue
        m = (torch.rand(t.n, len(t.types), generator=gen).numpy() < frac) & t.present & ~t.marker[:, None]
        m &= (lab == want) | ((lab == E.REMOTE) & (mask_remote and kind == "program"))
        if kind == "output" and t.relation != "ex_output":
            m[:] = False
        r, i = np.nonzero(m)
        if len(r) > cap:
            drop = torch.randperm(len(r), generator=gen).numpy()[cap:]
            m[r[drop], i[drop]] = False
        out.append(m)
    if kind == "program" and E.provenance(tables):
        sources, held, blocked = E.column_sources(tables), set(), set()
        pairs = [(j, c) for j, m in enumerate(out) if m is not None for c in np.flatnonzero(m.any(0)).tolist()]
        for p in torch.randperm(len(pairs), generator=gen).tolist():
            j, c = pairs[p]
            if sources[j][c] & held or (j, c) in blocked:
                out[j][:, c] = False
            else:
                held.add((j, c)); blocked |= sources[j][c]
    elif kind == "program":
        sources, held = E.table_sources(tables), set()
        for j in torch.randperm(len(tables), generator=gen).tolist():
            if out[j] is None or not out[j].any():
                continue
            if sources[j] & held or any(j in sources[k] for k in held):
                out[j][:] = False
            else:
                held.add(j)
    if kind in ("program", "output"):
        for j, t in enumerate(tables):
            if t.relation == "ex_output" and out[j] is not None:
                E.keep_occurrence(t, out[j], E.output_labels(E.evidence_input(tables), t)[1])
    return out


print("== without --mask-remote-groups: the masks bitwise those of a reference copy of the rule (20 draws per step "
      "kind, frac 0.3, cap 64, with and without --mask-remote), and the masked loss bitwise the same with the reference "
      "masks and with the attention probe on")
ref_progs = {**mask_progs, "groups fixture": grp, **{f"dev {k[0]} {k[1]}": v for k, v in src_progs.items()}}
diff, n_masks = [], 0
for remote in (False, True):
    g1, g2 = torch.Generator().manual_seed(41), torch.Generator().manual_seed(41)
    for kind in E.STEP_KINDS:
        for name, tabs in ref_progs.items():
            for _ in range(20):
                a_, b_ = enc.draw_masks(tabs, 0.3, 64, g1, kind, remote), reference_masks(tabs, 0.3, 64, g2, kind, remote)
                n_masks += 1
                if not all((x is None and y is None) or (x is not None and y is not None and np.array_equal(x, y))
                           for x, y in zip(a_, b_)):
                    diff.append((remote, kind, name))
progs_ = [(t, [None] * len(t)) for t in [real, grp, *src_progs.values()]]
loss_diff = []
with torch.no_grad():
    for remote in (False, True, "groups"):
        run_loss = lambda probe: enc.masked_loss(progs_, torch.Generator().manual_seed(4), 0.3, 64,
                                                 torch.Generator().manual_seed(5), mask_remote=remote, probe=probe)
        l0, r0 = run_loss(False)
        l1, r1 = run_loss(True)
        if not (torch.equal(l0, l1) and all(torch.equal(x[2]["loss"], y[2]["loss"]) for x, y in zip(r0, r1))):
            loss_diff.append((remote, "probe"))
        if remote != "groups":
            enc.draw_masks = lambda tables, frac, cap, gen, kind, mask_remote=False: reference_masks(
                tables, frac, cap, gen, kind, mask_remote)
            try:
                l2, r2 = run_loss(False)
            finally:
                del enc.draw_masks
            if not (torch.equal(l0, l2) and all(torch.equal(x[2]["loss"], y[2]["loss"]) for x, y in zip(r0, r2))):
                loss_diff.append((remote, "reference masks"))
        if remote == "groups":
            shares = [(r["parent_attention"], r["parent_chance"], r["parent_recent"]) for _, t, r in r1
                      if "parent_attention" in r]
            on = [(pa[~np.isnan(pc)], pc[~np.isnan(pc)], pr[~np.isnan(pr).any(1)]) for pa, pc, pr in shares]
            n_probed = sum(len(c) for _, c, _ in on)
            n_recent = sum(len(x) for _, _, x in on)
            if not n_probed or not n_recent or not all(
                    ((0 <= a) & (a <= 1)).all() and ((0 < c) & (c <= 1)).all() and ((0 <= x) & (x <= 1)).all()
                    for a, c, x in on):
                loss_diff.append(("groups", "probe shares", n_probed))
print(f"  {n_masks} mask draws, differing {diff[:3]}; masked loss differences {loss_diff}; probed remote fields "
      f"{n_probed}, with a recency reference {n_recent} {'PASS' if not diff and not loss_diff else 'FAIL'}")

print("== --mask-remote-groups: one draw per key group, so a group's chance to be hidden does not grow with its size "
      "(2,000 program steps of the groups fixture, frac 0.3: B's Color groups of 2 rows and of 1 row)")
g = torch.Generator().manual_seed(51)
hits, apart = {2: [0, 0], 1: [0, 0]}, 0
for _ in range(2000):
    col = enc.draw_masks(grp, 0.3, 10 ** 6, g, "program", "groups")[3][:, 2]
    for e in (0, 4):
        apart += bool(col[e] != col[e + 1])
        hits[2][0] += bool(col[e]); hits[2][1] += 1
        for r in (e + 2, e + 3):
            hits[1][0] += bool(col[r]); hits[1][1] += 1
p_ = {k: h / n for k, (h, n) in hits.items()}
ok = not apart and 0.8 < p_[2] / p_[1] < 1.25 and p_[1] > 0.05
print(f"  hiding probability of a group of 2 rows {p_[2]:.3f}, of 1 row {p_[1]:.3f} (one draw per field would give the "
      f"first about 1.7 times the second); a group's rows hidden apart {apart} {'PASS' if ok else 'FAIL'}")

print("== --mask-remote-groups: the pretrain log's remote split sums to its totals (the groups fixture and the dev "
      "programs, a program step each)")
import pretrain as P
with torch.no_grad():
    _, recs = enc.masked_loss([(t, [None] * len(t)) for t in [grp, *src_progs.values()]],
                              torch.Generator().manual_seed(6), 0.5, 10 ** 6, torch.Generator().manual_seed(7),
                              kind="program", mask_remote="groups")
log = P.losses(P.summarize(recs), 1.0)
bad = []
remote_labels = {k: v for k, v in log["by_type"]["program"].items() if k.startswith("remote/")}
by_type_fields = sum(v["fields"] for v in remote_labels.values())
split = [(b, ty, v) for b, tys in log["by_source_rows"].items() for ty, v in tys.items()]
if sum(v["fields"] for _, _, v in split) != log["remote"]["fields"] or log["remote"]["fields"] != by_type_fields:
    bad.append(("fields", log["remote"]["fields"], by_type_fields))
for ty in {ty for _, ty, _ in split}:
    l_split = sum(v["loss"] * v["fields"] for _, t_, v in split if t_ == ty)
    l_type = remote_labels["remote/" + ty]["loss"] * remote_labels["remote/" + ty]["fields"]
    if abs(l_split - l_type) > 1e-6 * max(1.0, abs(l_type)):
        bad.append(("loss", ty, l_split, l_type))
for b, ty, v in split:
    kinds_ = [v[k] for k in P.TARGETS.values() if k in v]
    if ty in E.POINTER_TYPES and (sum(x["fields"] for x in kinds_) != v["fields"] or abs(
            sum(x["loss"] * x["fields"] for x in kinds_) - v["loss"] * v["fields"]) > 1e-6 * max(1.0, v["loss"] * v["fields"])):
        bad.append(("target kinds", b, ty))
    if ty not in E.POINTER_TYPES and kinds_:
        bad.append(("a target kind of a type that is not a pointer", b, ty))
    if not 1 <= v["groups"] <= v["fields"]:
        bad.append(("groups", b, ty, v["groups"], v["fields"]))
depth_fields = sum(int(r["loss"].numel()) - int((r["source_rows"] >= 0).sum()) for _, t, r in recs
                   if P.depth_bucket(r.get("depth")) and "source_rows" in r)
depth_fields += sum(int(r["loss"].numel()) for _, t, r in recs if P.depth_bucket(r.get("depth")) and "source_rows" not in r)
if sum(v["fields"] for v in log.get("by_depth", {}).values()) != depth_fields:
    bad.append(("by_depth without the remote fields", log.get("by_depth"), depth_fields))
n_pointer_kinds = sum(1 for _, ty, v in split if ty in E.POINTER_TYPES for k in P.TARGETS.values() if k in v)
if not n_pointer_kinds or not split:
    bad.append(("nothing split", split))
print(f"  remote fields {log['remote']['fields']} in {log['remote']['groups']} groups over {len(split)} (bucket, type) "
      f"entries, {sorted(remote_labels)}; {n_pointer_kinds} pointer target-kind entries "
      f"{'PASS' if not bad else 'FAIL ' + str(bad)}")

print("== --mask-remote-groups: the target kinds of remote pointer fields, the group chance loss and the matched "
      "recency reference (200 program steps of the groups fixture, with and without the shift of the second entry's "
      "Idents)")
bad, kinds_seen = [], {}
g = torch.Generator().manual_seed(61)
for name, tabs in (("unshifted", grp), ("shifted", grp2)):
    for _ in range(200):
        ms = enc.draw_masks(tabs, 0.5, 10 ** 6, g, "program", "groups")
        m, t = ms[3], tabs[3]
        rf, (rr, ii) = E.remote_fields(tabs, 3, m), np.nonzero(m)
        for f, (r, c) in enumerate(zip(rr, ii)):
            if rf["remote_target"][f] < 0:
                continue
            v = t.cells[:, c]   # B's columns are one place wide
            vis = t.present[:, c] & ~m[:, c]
            row = (vis & (v == v[r])).any()
            cross = (vis & (v == v[r]) & (t.entry != t.entry[r]) & (E.key_groups(tabs, 3, c, False) ==
                                                                       E.key_groups(tabs, 3, c, False)[r])).any()
            want = 0 if not row else 2 if cross else 1
            kinds_seen[(name, int(want))] = kinds_seen.get((name, int(want)), 0) + 1
            if rf["remote_target"][f] != want:
                bad.append((name, r, c, rf["remote_target"][f], want))
if not kinds_seen.get(("unshifted", 2)) or not kinds_seen.get(("shifted", 1)) or kinds_seen.get(("shifted", 2)):
    bad.append(("kinds", kinds_seen))
# group_chance_loss is the per-field chance where every group holds one field, and the two row kinds add to the rows
with torch.no_grad():
    _, recs = enc.masked_loss([(t, [None] * len(t)) for t in [grp, grp2, *src_progs.values()]],
                              torch.Generator().manual_seed(6), 0.5, 10 ** 6, torch.Generator().manual_seed(7),
                              kind="program", mask_remote="groups", probe=True)
log = P.losses(P.summarize(recs), 1.0)
entries = [v for tys in log["by_source_rows"].values() for v in tys.values()]
entries += [v[k] for v in list(entries) for k in P.TARGETS.values() if k in v] + [log["remote"]]
singles = [v for v in entries if v["groups"] == v["fields"]]
if not singles or any(abs(v["group_chance_loss"] - v["chance_loss"]) > 1e-9 for v in singles):
    bad.append(("group chance where groups are single fields", [(v["group_chance_loss"], v["chance_loss"]) for v in singles]))
if any("group_chance_loss" not in v for v in entries):
    bad.append(("group_chance_loss missing",))
rows_direct = sum(int((r["remote_target"] >= 1).sum()) for _, _, r in recs if "remote_target" in r)
rows_log = sum(v.get(k, {}).get("fields", 0) for tys in log["by_source_rows"].values() for v in tys.values()
               for k in ("row_target", "row_target_cross_entry"))
if rows_direct != rows_log or not rows_log:
    bad.append(("row targets", rows_direct, rows_log))
pa = log.get("parent_attention", {})
if not pa.get("matched_fields") or not pa["matched_fields"] <= pa["fields"] or not all(
        0 <= x <= 1 for x in [pa["matched_parent"], pa["matched_recent"]] + pa["matched_parent_layers"]
        + pa["matched_recent_layers"]):
    bad.append(("matched recency reference", pa))
print(f"  target kinds (fixture, kind) {dict(sorted(kinds_seen.items()))}; entries whose groups are single fields "
      f"{len(singles)}; row targets {rows_log} of the log against {rows_direct} of the records; matched fields "
      f"{pa.get('matched_fields')} of {pa.get('fields')} {'PASS' if not bad else 'FAIL ' + str(bad)}")
