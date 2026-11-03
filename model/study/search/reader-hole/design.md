# Reader with a hole, before the hole's table exists: design

Terms.

- A hole is the atoms of a clause that read one form X whose table doesn't exist yet: every atom on X and on its methods.
- A reader with a hole (alias: sketch) is a clause with one hole. Its side atoms are its other atoms, its side forms are the forms they read, and its side rows are the rows of the side atoms joined.
- Goal rows are rows that the reader's own head must give. Only OUT has them before any form exists: the train outputs.
- A form is in scope when a 600 s run didn't cover it, the run covered every form it reads (it is ready), and it has a reader whose only uncovered read is that form.
- A bare key join is a hole atom whose key site holds only bare labels, so every key label joins a label that a side atom makes.
- Key by copy: the INIT's key clause is the side atoms that make the key labels, with those labels as its key.

Other terms are those of `work/measures.md` and `work/results.md`.

## Decision

1. For an INIT, the hole can't nearly determine the hole's table from what a search has. It fixes the INIT's interface, and the INIT's bits sit in its port reads, which the reader doesn't see.
2. Goal rows from OUT reach no form through single holes at 600 s on the 37. So the goal's rows that a search has are side rows.
3. The strongest design that side rows allow is key by copy, below. At 600 s on the 37 its ceiling is about 11 non-DET forms per seed, with every keyed form in scope found and every reader it opens found. That is under the noise bound of 12, so I don't recommend an arm at 600 s.
4. Two cheap reads come before any arm. Read 0 recounts the ceiling at the budget that matters. Read A measures how often key by copy gives gold's table. Each can fail, and each has a bar.

## What the hole constrains

Six probes of existing records, each under 20 s. Scripts are in this folder, and their inputs are the bundle and bundlef jobs of `search-identj-heldout50-2seeds-600s-0729e4943` with `kit/points-eval.json`.

| Probe | What it read | What it showed |
|---|---|---|
| `reach_probe.py` | Chains OUT, R1, ..., Rk along gold's reads, where each Ri's other reads are covered and Rk is ready | 0 forms on the 37 at both seeds, on `bundle` and on `identj`. OUT's reader has 1 uncovered read on 8 or 9 of 37 tasks, 2 on 19 or 20, and 3 or more on 9. On the 13 fold tasks: 1 and 11 forms, on 1 and 2 tasks. |
| `reach_probe2.py` | The same chains with up to H holes per reader | H 2: 243 and 249 forms on 9 tasks, 30 INIT. H 3: 925 and 930 on 29 tasks. Of uncovered forms, 108 and 110 have 0 uncovered reads, 621 and 624 have 1, 439 and 446 have 2. |
| `diamond_probe.py` | Gold text of the 37: of an INIT's reads of earlier forms, the share its reader also reads | 45 of 597 reads: key reads 17 of 126, port reads 28 of 471. The reader's side set is a median of 1 form. Mean share per form .12, median 0. |
| `scope_probe.py` | Forms in scope at 600 s | INIT 16 and 19, RULE 27 and 27, DET 7 and 9. Of the INITs, 10 and 9 have a hole atom with a key site. |
| `opened_probe.py` | The readers that a find of an in-scope INIT makes ready at once | On the 37: 16 and 19 INITs on 14 and 16 tasks open 24 and 26 readers (RULE 13 and 14, INIT 8 and 9, DET 3 and 3). None is a form that OUT reads. On the 13: 9 and 9 INITs open 12 and 9. |
| `sketch_count.py`, `right_sketch_probe.py` | Readers by swap in the 600 s banks: kept forms that read a pool INIT method at a bare key join | A median of 89 per task (quartiles 58 and 152), 4,032 on the 37 at seed 0. In-scope INITs with a bare key join: 5 and 4 on the 37, 0 and 1 on the 13. A bank reader with the right side atoms, labels ignored: 1 of 5 and 0 of 4, and 0 on the 13. |

What follows from them:

1. Goal rows don't reach. A chain of single holes from OUT needs every form on it to have one uncovered read. Every chain on the 37 meets a form with two or more, so the goal rows of OUT stop there. On easy tasks the chain sometimes holds: 11 forms on 2 of the 13.
2. Where the saving sits, goal rows are furthest away. On the 117 INIT edges at 25 bits or more (`edge-rows.jsonl.zst` of `features-search-holding-reader-with-hole-design`), the 79 at depth 4 or more save 3.43 bits a form, and the 38 at depth 2 or 3 save .66.
3. The reader doesn't see the INIT's inputs. 79% of an INIT's reads are port reads, and the reader reads the same form at 28 of 471 of them. Port reads hold 29.2 of the 39.8 bits of the median INIT that a body rewrite leaves over 25 bits ("INIT forms that a body rewrite leaves over 25 bits").
4. So the hole fixes the INIT's interface, and nothing past it:
    - the output port and its column types, from the hole's sites;
    - the component, softly: 3.76 bits to 2.28 at depth 4 or more ("Backward from OUT: what a form reads");
    - the head columns, softly: 5.77 to 3.15;
    - the key's values, where the key join is bare: under the side rows, the INIT needs a row at each key the reader joins.
5. Only the key is a value that the side rows determine. It is about 9 bits of a keyed INIT: the keyed coin .55, key labels .43, and a key read at a median of about 8 bits ("Why INIT rarely reads Ident"; "INIT forms that a body rewrite leaves over 25 bits").

## How the search pays for the reader

There are three costs, and the design pays each as follows.

1. The reader's draw. A reader by swap comes from a try that the search makes anyway: a clause that reads a pool INIT at a bare key join. The swap makes that INIT's atoms the hole. It costs no proposal. The probe puts that store at a median of 89 per task, and finds the right reader in it 1 time in 9.
2. The hold. One reader per INIT slot, drawn uniformly from the store, so the right one comes with chance 1/M. The copy is one more option at the key pick, with weight w. It never replaces the prior, so a wrong reader costs a key the share w, and doesn't refuse the right key.
3. The fill. Each INIT kept under a reader gives one more try: the reader with its hole swapped to the new INIT.

A split of proposals among M readers costs log2 M in proposals, and a bit saved on an INIT buys .12 to .26 log2 proposals ("Search that holds a reader with a hole", `design.md`). That is why no tilt in the design is a split: the copy is an option at a pick, priced in bits.

## The design: key by copy

1. Store. In `try_clause`, on a `new` or `equal` outcome, each atom set on a pool INIT method with a bare key join gives a reader by swap. The store keys it by an order-free key: the side atoms as a set, with labels renamed by the graph of sites they share, and the hole's sites as (method, column type) pairs. A count of draws stays with it. The cap is 2,000 per task.
2. Slot. In `next_slot`, an INIT slot takes a reader from the store with chance q. Its side forms join the slot's `fids`, with their ancestors, under `MAX_SCOPE_FORMS`. The slot key holds the reader key, so a slot with a reader isn't the slot without one.
3. Key pick. In `Run.init`, where the slot has a reader and the keyed coin comes up, the key body is the copy with chance w, and `key_body` as now with chance 1 - w. The copy steps the side atoms that make the key labels, closed over the labels they share, through the decoder as `Run.cands` steps a token list, with those labels as `^`. The decoder needs `^` in some written order, and any valid order serves. The keys and their types come from the side atoms' types.
4. Fill. A kept INIT under a reader gives one try of the reader with its hole atoms named for the new INIT, in the slot's scope plus the new form. That try is a normal `try_clause`, so its cover event, keep rule and OUT test are those of any try.
5. Renewal. `.sketches` stands beside the bank, as the prior design gives it, so a renewal keeps the store.

Rules:

- DAG facts only. The reader key, the pick and the copy read no atom index, no first or last atom and no binder mark. The `^` marks of the copy are written facts, and no fact reads them.
- Ident. The copy reads the same side atoms as the reader, so a key label of type Ident has the side form as its source, and the reader's join on it stays inside one source. The member digest of a key value is the side table's. `ARCLOG_IDENT_SOURCE=value` refuses anything else, as now.
- Cover is by the merge key. Key by copy gives gold's INIT table when gold's key rows equal the copy's on every train example and the component and ports are gold's, because an INIT's tables are a function of its key rows and port rows. The copy needn't match gold's text.

Interface tilts are left out. A tilt on the component or the head columns toward a reader's hole replaces the prior on every slot with a reader, so at M = 89 it loses: the right reader adds 2^1.48 / 89 of the chance on 1 slot in 89, and every wrong reader takes chance from X's component.

| File | Function | Change |
|---|---|---|
| `superdag_search.py` | `try_clause` | Offer readers by swap to the store on `new` and `equal` |
| | `Slot`, `next_slot`, `visit` | A slot holds a reader key, and its side forms join `fids`; `s.run.sketch` is set |
| | `try_clause` after a kept INIT | The fill try |
| | `after_bank`, `read_slots`, `install` | `.sketches` beside the bank; `SEARCH_HOLD_KEY=q,w`, unset means no patch |
| `live.py` | `Run.init`, `key_body` | The copy as a key option with weight w |
| `search.py` | `Manager.get`, `Disk` key | The reader key in the search key, so a frontier with a copy isn't reused without one |
| `hold_key.py`, new | store, order-free key, copy tokens | As above |

## Cost estimate

Measured rates:

| Rate | Value | Source |
|---|---|---|
| Proposals per CPU s | 14.20 at age 0 to 60 s, 9.74 at 480 s and up | `search-out-tries-probe-8tasks-600s-c87cf482a/probe-read.txt` |
| CPU ms per try | 93.6 young, 150.1 at 480 s and up | `search-evict-heldout37-2seeds-600s-c87cf482a/rate-age2-read.md`, arm `evict` |
| Forms in a scope; OUT tries per form | 6.2 to 14.6; 6.4 to 18.7, from age 0 to 480 s | `probe-read.txt`, as `work/results.md` states it |
| Proposals, CPU s, kept forms per 600 s task | 4,522; 509; 1,722 (medians) | Source C of `features-search-holding-reader-with-hole-design/design.md` |
| Kept INIT share of kept forms | .295 | `kept:` counters of `bundle_s0` logs, a ratio |
| INIT share of visits | .31 | `search:visits:` counters of the same logs, a ratio |
| Seconds of take per kept node | .079 `identj`, .103 bundle | `search-identj-heldout50-2seeds-600s-0729e4943/read.txt` |
| Parse of a clause for readers by swap | .003 ms CPU per form | This folder, 5,950 forms of 2 banks, Mac |
| A sandwich of goal rows and side rows | .29 ms at 200 rows, 2.7 ms at 2,000, 9.8 ms at 8,000 rows per example, 4 examples | `bench_sandwich.py`, Mac; for the OUT variant only |

Per 600 s task, at q = .5 and w = .5:

| Part | Estimate | From |
|---|---|---|
| Store | 4,522 tries x .003 ms, about 14 ms | Parse rate |
| Fills | .295 x 1,722 x .5, about 254 tries, x 93.6 to 150.1 ms: 24 to 38 CPU s, 4.7% to 7.5% of 509 | Kept share, ms per try |
| Scope growth | A median of 1 side form on half the INIT slots, .31 x .5 of visits, at +7% to +16% of a scope's forms: about +1% to +2.5% of CPU | Side set size, scope size, visit share |
| Key mass | Every other keyed INIT draw in a slot with a reader loses the share w: .42 bits over all INIT slots at q w = .25 | q and w |

In all, 6% to 10% of CPU goes to the design, so every other form loses .09 to .15 log2 proposals.

Gain on a keyed in-scope INIT X with a bare key join. In a slot with a reader, the right reader comes with chance 1/M, and a right copy saves Δ bits with chance s, the share that Read A measures. Averaged over INIT slots, X's key chance changes by the factor

F = (1 - q w) + q w s 2^Δ / M.

At q = .5, w = .5, Δ = 9 and M = 89, F = .75 + 1.44 s: 1.47 at s = .5, and 2.19 at s = 1. The ceiling counts 4.5 such INITs a seed on the 37 and the readers they open, 1.5 each by `opened_probe.py`, so about 11 non-DET forms per seed if every one is found. Proposals scaled by F in full, the generous end, give 1 to 2.5 forms at a base find chance of .14 to .6 over the run. Those chances come from `blocked-read.json`: at 25 bits or more, 5 covered of 35 ready or covered; under 25 bits, 133 of 219.

F turns on M. With a pick that holds the right reader in a top 4, F = .75 + 32 s. No record ranks readers by swap, and the store holds the right one 1 time in 9, so the design has no pick.

## The reads before an arm

Read 0 is a ceiling, and Read A is a share.

### Read 0: the ceiling at the budget that matters

The four probes `scope_probe.py`, `opened_probe.py`, `sketch_count.py` and `right_sketch_probe.py`, on the banks and `.cover` files of a run at that budget, both seeds. Each runs in under 20 s a run. 3,600 s runs on the 13 and the Kaggle budget are the candidates.

- Prediction: on the 37 at 600 s, as measured: 4.5 keyed INITs with a bare key join a seed, a ceiling of about 11 non-DET forms. At 3,600 s on the 13, at most 3 keyed INITs with a bare key join a seed, since 600 s gives 0 and 1.
- Bar: an arm needs a ceiling of 24 non-DET forms or more, twice the noise bound of 12, on the mean of two seeds. Under 24, key by copy doesn't go to an arm at that budget.

### Read A: does key by copy give gold's table

Offline, gold only: no search and no priors. Gold priors don't enter, so the 22 `train-fill` stems of the held-out ramp count with the 37.

1. Unit: a gold edge (R, X), where X is an INIT and R reads a method of X at a bare key join. All 37 held tasks and the 59 stems of `gold/gold-heldout-ramp-pass1/heldout-ramp.jsonl`.
2. Copy: X' is X with its key clause body replaced by the side atoms of R that make the key labels, closed over the labels they share, with those labels as the key.
3. Replay gold's program with X' in place of X, in the replay of `features-backward-from-out-content-heldout37` (`gold_tables_env.sh`). An edge is a hit when every table of X' equals the table of X under the order-free `table_key` of `superdag_search.py`.
4. Beside it: per train example, the copy's key rows against X's, as equal, a subset, a superset or other.
5. Control: the copy from a reader of another INIT of the same task, with the key labels mapped by type. A control with no type match counts as a miss.
6. Report s on all such edges and at 25 bits or more, by depth band and by reader kind, with a 95% task bootstrap.

- Prediction: s from .25 to .55 on all edges, .2 to .5 at 25 bits or more. The control under .05. Most of the copy's misses are a superset: the side rows hold keys that X has no row for.
- Bar: s at 25 bits or more of .6 or more, with the lower limit over .4, and the control under .1, sends key by copy on. Under .3 closes it. Between the two, it stays a finding with no arm.
- Cost: one gold replay per edge. 115 held INITs are keyed, so the edges number in the low hundreds with the ramp. This is an estimate, as no record times a single gold replay.

The arm follows only if both reads pass: key by copy against the bundle, q = .5 and w = .5, two seeds, 600 s, forms counted on the 37 and on the held-out ramp, under the pass rule of `work/measures.md`.

## What the design can't settle

- A pick for readers. F is set by the rank of the right reader in the store, and no record ranks readers by swap. The store holds the right side atoms for 1 of 9 keyed in-scope INITs, and labels were ignored in that match, so it is an upper bound.
- Find chances. The base chance of a form in scope, and of a reader it opens, comes from end-of-run counts, not from a hazard over the run.
- The INIT's port reads stay drawn. Forms whose port reads cost past about 25 bits stay out of reach whatever the hole fixes.
- OUT's goal rows on easy tasks. On the 13 the chain from OUT reaches 11 forms on 2 tasks at seed 1000. A sandwich of goal rows and side rows costs .3 to 3 ms at the row cap, so that variant is cheap to check. This design doesn't cover it.

## What it assumes

- Cover counts a table by its merge key, so a copy that gives gold's key rows gives gold's INIT tables when the component and ports are gold's.
- Proposals for X scale with F in full. That is the generous end: the fitted INIT slope gives .12 to .26 log2 proposals per bit.
- The in-scope count at run end bounds the forms the design can add, with one step of opening. Later steps of the chain are found at the forward chance, and the opened readers are counted as found.
- The store at 600 s is the bank's kept forms. Tries with an equal table add readers, so M is a lower bound and F an upper bound.
- Δ = 9 bits is the median key cost of INITs that a body rewrite leaves over 25 bits. In-scope INITs may differ.

## Files

Scripts in this folder: `reach_probe.py`, `reach_probe2.py`, `diamond_probe.py`, `scope_probe.py`, `opened_probe.py`, `sketch_count.py` (its loader makes only `superdag.Form` and `superdag.Node`), `right_sketch_probe.py`, `bench_sandwich.py`. Each takes the points file and a run's `out` folder, as its docstring gives.
