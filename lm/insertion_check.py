"""Checks the insertion of the feature vectors into the language model's sequence, on every case of a data
directory that the tables export holds, at a long and a short --max-len: with the vectors removed, the sequence
must be the one encoded without tables; every target must predict the same token, from the position just
before it; the declarations' positions must be the shifted ones; each table's vectors must follow its step;
the steps kept and the targets must be the same with and without tables; and the length must stay within
twice --max-len.

- At 4096, every case keeps all its steps and all its tables.
- At 12, every case loses its steps past the 11th and the tables after them; some cases keep each remaining table,
  and some drop their latest tables past twice --max-len.

    work/lm/.venv/bin/python lm/insertion_check.py [data dir] [tables dir]
"""
import re, sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
import encoder as E
import train as T

DATA = sys.argv[1] if len(sys.argv) > 1 else "lm/data-dev"
TABLES = sys.argv[2] if len(sys.argv) > 2 else "work/tables/dev"
K = 4

train, held, names, kinds, mask_table = T.load(DATA)
tables, _, _ = E.load_tables(TABLES, f"{DATA}/tables.cache")
names_in = {n for n, k in zip(names, kinds) if k not in ("relation", "label")}
in_names = sorted(names_in) + [T.BOS] + [f"{p}_{k}" for p in ("DECL", "REF") for k in T.KINDS]
out_names = sorted(names_in) + [f"REF_{k}" for k in T.KINDS]
in_index = {n: i for i, n in enumerate(in_names)}
out_index = {n: i for i, n in enumerate(out_names)}
rel_token = {int(n[2:]): i for i, n in enumerate(names) if re.fullmatch(r"&r\d+", n)}
masks = T.Masks(mask_table, names, kinds, out_index)

cases = [c for c in train + held if (c["task"], c["case"]) in tables]
rules, cut, n_tables = {}, {}, 0
for c in cases:
    c["tables"] = tables[(c["task"], c["case"])]
    for max_len in (4096, 12):
        a = T.encode(c, in_index, out_index, 64, max_len, masks, torch.Generator().manual_seed(0))
        b = T.encode(c, in_index, out_index, 64, max_len, masks, torch.Generator().manual_seed(0), K=K, rel_token=rel_token)
        kept, feat_pos, rel, rule = b[5]
        feat = np.zeros(b[4], bool)
        if feat_pos:
            feat[np.array(feat_pos).reshape(-1)] = True
        steps = np.flatnonzero(~feat)                 # the position of each step
        assert feat.sum() == K * len(kept) and b[4] <= 2 * max_len
        assert torch.equal(b[0][torch.from_numpy(steps)], a[0]) and torch.equal(b[1][torch.from_numpy(steps)], a[1])
        assert len(a[2]) == len(b[2])
        for ta, tb in zip(a[2], b[2]):
            assert steps[ta.pos + 1] == tb.pos + 1 and ta.cls == tb.cls and ta.ptr == tb.ptr
            assert tb.pos == steps[ta.pos] or feat[tb.pos]   # the step before, or the last vector of a table after it
        for k in T.KINDS:
            assert [steps[p] for p in a[3][k]] == b[3][k]
        for t, f in zip(kept, feat_pos):
            assert f == list(range(f[0], f[0] + K)) and (f[0] - 1 == steps[t.step] or feat[f[0] - 1])
        m = min(len(c["steps"]), max_len - 1)
        cut[max_len] = cut.get(max_len, 0) + (len(kept) < sum(t.step <= m for t in c["tables"]))
        if max_len == 4096:
            n_tables += len(kept)
            for r in rule:
                rules[r] = rules.get(r, 0) + 1
print(f"PASS on {len(cases)} cases, {n_tables} tables at max-len 4096")
print(f"tables by the rule that found their relation's declaration: {rules}")
print(f"cases that drop tables past twice max-len: {cut}")
