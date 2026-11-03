# Relation pick, per-key models: state of the record

The held reads are done: 5 final models and 5 controls, each once, primary first. `summary.md` has the bars, `table-final-*.md` the class and position tables beside the rank read, `keys-*.tsv` the per-key tables, `learned-final-hyb-noorder.md` the top keys in words, `rows-per-key.md` the rows per key, `tune-table.md` every tune read, `prediction.md` the prediction written before the reads.

Held, saved bits per pick, all 1,959 picks and by class. The rank read's row is its model without content features.

| Model | All | Derived | Lib | Own | Rest |
|---|---|---|---|---|---|
| Rank read | +.30 | +.35 | +.67 | +.05 | +.16 |
| Relation keys | +.36 | +.28 | +.83 | +.13 | +.36 |
| Component keys | +.36 | +.31 | +.84 | +.07 | +.35 |
| Family keys | +.34 | +.39 | +.87 | .00 | +.16 |
| Primary: lib by name, derived by family | +.41 | +.44 | +.88 | +.04 | +.31 |
| The same with reader counts and form order | +.50 | +.58 | +.99 | +.02 | +.35 |

Prediction against the read: primary +.40 read +.41, gold alive +.37 read +.39, with order facts +.48 read +.50, derived +.45 read +.44, lib +.8 read +.88, rest +.25 read +.31, own 0 read +.04: held. Relation keys +.38 read +.36: held. Keys passing at gold picks, 12 lib relations on 12% of picks: 5 on 8.2%, missed. Net passes, 3 or fewer: 6, missed. Control -.03: +.001, missed, as under a drawn label most keys choose no trees.
