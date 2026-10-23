# Outliers

What reading and rerunning the slowest solvers of [Runs](corpus-survey.md#runs) showed. No script computes these lines.

## Causes of the outliers

Each outlier of the table of [Runs](corpus-survey.md#runs) was read and, where a fix was tried, rerun with the fix, and every fix kept the output, by an md5 of the sorted `.output` files. None is a cost of its task's intended concept. The class column judges by principle: a form that does more work than another is a fault only where a principle rules it out, since the principled form is right whatever it costs, as [Performance](../../docs/handbook/encoding.md#performance) gives.

| clause | cause | class | measured fix |
| --- | --- | --- | --- |
| a57f2f04 `parse.copy` | each row is derived on 32 paths of about 30 functor calls each: `diag_dirs` takes each corner once per axis order, 2×; `box_extent` inlines `axis_of`, whose 2 rows give one extent, 4× over two calls; `Parse` is keyed by the whole `Choice`, though the copy varies with no `PanelExtent`, 2×; and on one input 57600 rows hold 900 distinct contents, since the cases' relations hold the same rows there | the key: solver, by the rule that a comp is keyed by the `Choice` fields it varies with; the axis order: the principled form, which states the corner on either axis with no axis literal; `box_extent`: lib; the rest: Souffle (no shared subexpressions, no sharing across cases) | one axis order and `box_extent` without the hidden direction: 2.76 s to 0.36 s on call 21 |
| a57f2f04 `parse.scan_order.before` | `Order.first` by subsumption over the `before` pairs, O(m²) per key against O(m) for a minimum; 512 keys hold 24 distinct contents, since the scan is keyed by the whole `Choice` | `first` by pairs: lib; the key: solver, by the same rule | two minimum aggregates in place of `LexOrder`: 2440832 rows to none, 3.4 s to 0.03 s |
| abbfd121 `parse.shade_reach.edge` | a `Propagation` keyed by source color copies the colorless `map_link` edges once per color, 3×, and its closure chains past the output claim's text | solver, by fidelity: the closure states a hypothesis that the output claim does not | a direct read of `map_link`: 504k rows less, the same output |
| abbfd121 Wallpaper internals | `wp._reach` and `wp._pair`, 1708260 rows each, test every candidate on every pair of a period class, where a test per class decides it | lib | a test per class: `_pair` gone, `_reach` 256k, the program 2.0 s to 0.73 s |
| a32d8b75 `parse.cover` | each of 15600 rows enumerates about 660 field cells and filters on an equal computed `diag_dist`: about 20M probes | Souffle (no index on a computed key) | a relation of the computed key, 10560 rows: 2.94 s to 0.014 s |
| 20a9e565 `mirror_defect` | a universal by defect negation that enumerates every P after the defect row is derived: about 3.7M probes for 1240 defects | Souffle (no early exit on an existential) | none clean; a rewrite changed 6 rows |
| a395ee82 `determine.covered` | a cell's place in its block is computed per pair of cells, the join is on a computed key, and the axis and `box_extent` factors of `parse.copy` | Souffle (no hoisting, no index on a computed key); the axis order: the principled form; `box_extent`: lib | a relation of the places, 11371 rows: 1.11 s to 0.065 s |

- Past the fixes, the largest rows are those of the orbit as cell pairs, abbfd121's `wp.action` 256038 and `map_link` 166485, and the rows that cases whose relations hold the same rows on an input give once each.

## Timings alone

- `run_dl.py run` makes its Souffle calls in parallel, so the times of [Runs](corpus-survey.md#runs) include contention: a57f2f04 took 47 s of user time over 18 s of wall time. Each call rerun alone, under a load average of 11 to 17, gives a57f2f04's slowest call 6.35 s of wall time, its largest `parse.copy` 4.93 s, and abbfd121's slowest call 2.25 s of program and about 1.3 s of Souffle's frontend.
