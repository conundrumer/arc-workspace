# Ident block read: design

## Question
At each gold Ident-only form of the 37 held tasks and the 22 ramp tasks, this read compares two rates of the form's head shape:

- the proposal's rate: the chance that the bundle's proposal draws a form of that head shape at the form's scope;
- gold's rate: the share of corpus gold forms with that head shape, among corpus forms whose scopes have the same DAG facts.

The read reports bits lost per form and the count of forms where the proposal's rate is under a tenth of gold's. It reports by shape, with the 37 and the ramp apart. Its verdict says which of two things blocks the Ident forms: the proposal's Ident conditioning, or compounding over chain depth.

## Record
- Record folder `R` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-ident-block-read-heldout37-ramp22/`. Write only there.
- When the read is done, copy `R` to `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-ident-block-read-heldout37-ramp22/`, because scratchpads don't survive a restart. If your brief doesn't allow that write, hand the `cp -R` command back.
- The deliverable is `R/results.md`: the tables of [Read](#read) and the verdict.

## Pins
Every script checks these pins at start and exits on a mismatch. `R/manifest.json` records them.

| Pin | Value |
|---|---|
| Sampler code | `KIT=/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943`, folder `$KIT/model/study/sampler`. sha256 of `live.py sample2_col.py search.py superdag.py superdag_search.py live_try.py or_q.py`, concatenated in that order, starts `6db5589ab189` |
| Engine | `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path`, `arclog/arclog.abi3.so` sha256 `b41ccf9c0567b923f04771d7b5e479172d94f30fa09e4a9b181713ec19e043a3`. Its engine tree equals the kit wheel's e8c1b7882 except `engine/lib/study-meanings.json`, and it reads `ARCLOG_IDENT_SOURCE` |
| Python | `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python -u`. Scripts put the sampler folder and the engine path first on `sys.path` themselves. Don't use `-I` |
| Models, the 37 | `$KIT/models-tk`: `live_priors.pkl` 7dafa0ce1e975027, `relR4_o.pkl` 3015d409597fff42, `choice5_o.pkl` 04a895269d26541e, `tilt_v1.json` ca858276d4713e92 |
| Models, the ramp | `$KIT/models-tkf`: `live_priors.pkl` 00eb0d40b2b52859 (the 22 ramp tasks left out), the same three steer files |
| Settings | `P_DAG=1 ORDER_FREE=tie,key ARCLOG_IDENT_SOURCE=value RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`. `STEER_COVER` unset. Every other variable at the kit's default |
| Held gold | `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/live-gold-r1/points-eval.json`, sha256 starts `af855438abe27a5b`. Never read `view-final` at run time |
| Ident-only list | `gold-ident-only-refit.json` beside it, sha256 starts `08ec1bc4d836c650`. Index `g` is the g-th non-empty line that doesn't start with `(OUT` |
| Task sets | `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held/tasks.txt` (37) and `held/ramp-fold.txt` (22) |
| Task JSON | held: `$KIT/data/tasks/<task>.json`; corpus: `/Users/davidlu/code/arc-workspace/data/tasks/<task>.json`. Test outputs removed, `World.Open`, `DecodeSettings(**live_try.SETTINGS)`, as `live_try.session_of` does |
| Corpus gold | `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-view-final-2149/<stem>/pairs.jsonl.gz`, the first row's `gold_sexp`: a copy of `gold-v3-combined-cut/view-final` as of 21:49 on Nov 1, 1,110 stems. Stems: all, less `features-worker/arm/eval-tasks.txt` (99, which hold the 37), less the 22 ramp tasks: 989. `R/corpus-pin.json` records the stem count and the sha256 of the sorted lines `stem<TAB>sha256(gold_sexp)` |

- The models are those of `kernel-bundle-ec15d12f0` (`work/synth-kaggle/kernel-freeze-tiekey-ec15d12f0/manifest.json`), the kit the refit and Ident reads ran "against the bundle". The `Bundle:` line of `work/facts.md` names the older Kaggle set (priors 49759a522172b459, `relR4_o` c527e533408a5269, `choice5_o` 9603712a5cf35684, `tilt_v1` 730b7596c1b841cc). Name this in `results.md`.
- The ramp's `relR4_o.pkl` has the ramp tasks in its train rows, so the ramp read is held out for the priors only. Name this in `results.md`.
- The priors were fit on `view-final` before 21:49. The corpus copy can differ from the fit text on stems regolded since. Name this as a limit.

## Definitions

### Forms, reads, ancestors
- A program's forms are its non-empty lines that don't start with `(OUT`. A form's kind is its first word: `RULE`, `DET`, `INIT`, `RIGID_DET`; any other word is `OTHER`. Its head is its second word.
- A form reads each name `&x` in its text, with `.port` cut off, that is the head of another form of the program.
- The scope of form g is the set of g's ancestors by reads. The pool's scope has the same build: picked nodes and their ancestors.
- A valid order of a scope is a random topological order, drawn from a seeded `random.Random`. No script passes gold's text order to the proposal.

### Column types
- A replay of a program gives each form's tables: `D.Run(pri, session, 0, deadline, task, live.Limits())` with `run.collect = []`, then `run.scope(forms)`; `run.collect[g]` is form g's `step_tables` result. `search_node_score_gold_ident.py` does the same. `import superdag as D` from the kit.
- A table's column types are `[str(t) for t in D.OneTable(ct, j).tables['column_types'][0]]` for each `(_, j)` in `D.relation_tables(ct)`. Types come flat: a key's fields are columns of their own.
- A form holds Ident where some table has a column type that contains `Ident`. A form is Ident-only where it has a table and every table has such a column. This is the rule of the pinned list.

### Head shape
A form's head shape is `(kind, I, K)`.

- `I`: over the form's tables, the least count of columns whose type contains `Ident`, capped at 3: `0`, `1`, `2`, `3+`. A form with no table has `I = none`.
- `K`, for `INIT` only: `nokey` where the text has no `(key (` clause. Else `nk` is the count of distinct `^` labels in the key clause, and `K` is `key-ident` where one of the first `nk` column types of the first table contains `Ident`, else `key-plain`. For other kinds `K` is `-`.
- The `^` marks serve only to count the key's columns, which is a fact of the key as a set. The first `nk` columns of a keyed output are the key's columns in any written order.
- One function `shape_of(kind, text, ct)` gives the shape on both sides. It takes gold's text with `run.collect[g]`, or a drawn `Clause` as `(kind, clause.text, clause.tables)`.

### Ident links
- `link(f)` is 0 where form f holds no Ident. Else it is 1 plus the largest `link` over the Ident-holding forms that f reads, and 0 where it reads none. So a maker, such as `Connectivity`, `Enclosure`, `Quotient` or `PanelCombine`, has link 1.
- This is the link of "Gold shapes missing from the pools" in `work/results.md`.

### DAG facts of a scope
Each fact reads the scope as a set, with its read edges and its tables' column types. No fact reads text order, atom order, a place in a body or a binder mark.

| Fact | Values |
|---|---|
| `nscope` | number of scope forms: `0`, `1-2`, `3-5`, `6-11`, `12+` |
| `ident_in` | number of scope forms that hold Ident: `0`, `1`, `2-3`, `4+` |
| `ident_sink` | a sink of the scope holds Ident (a sink is a scope form that no other scope form reads): `0`, `1` |
| `link_in` | the largest `link` in the scope: `0`, `1`, `2`, `3-4`, `5+` |

- Cell `C1` = (`nscope`, `ident_in`, `ident_sink`). Cell `C2` = `C1` plus `link_in`.
- Backoff: where a cell has fewer than 40 corpus forms, the read uses the next level: `C2`, `C1`, (`ident_in`, `ident_sink`), (`ident_in > 0`, `ident_sink`), kind alone. Each row records its level.
- The primary read uses `C1`. `C2` and kind alone are extra columns.

## Rates

### Gold's rate
- One replay per corpus program gives every form's shape and facts.
- `p_gold(s | C)` = (count of corpus forms in cell C with shape s + 0.5) / (count of corpus forms in C + 0.5 V), with V the number of shapes seen in the corpus. This rate includes the kind.

### The proposal's rate
The rate is exact for the kind and sampled within the kind. An exact rate within the kind isn't feasible. The shape depends on the whole clause: each label of a RULE body, and an INIT's component, key body and port heads. The drawer also redraws inside a draw (`try:empty`, `atom cannot close`), so the chance of a shape is a sum over clauses with no product form. `or_q` gives the exact chance of one clause, not of a set of clauses.

- Kind: `P_kind(k | scope)` = (kinds[k] + 1) / (the sum over admitted kinds), as `superdag.Pool.kind` computes it, with `kinds = {k: sum(c.get(k, 0) for c in pri['kinds1'].values())}`. A kind is admitted where `dec.admits([live.KIND_TOK[k]])[0]` holds, and `dec, pg = sampler.run.scope(order)`. A gold kind outside `KIND_TOK` gets `P_kind = 0`, and the row says so.
- Within the kind: draws `sampler.clause(session, seed, time.monotonic() + 20, task_json, order, kind)` with gold's kind, on `live.Sampler(models)` with the default steers. A draw that returns `None` counts as a try with no shape. `h` is the count of draws with gold's within-kind shape `(I, K)`, and `n` is the count of tries. `r̂` = (h + 0.5) / (n + 1).
- `p_prop(s | scope)` = `P_kind` × `r̂`.
- Each batch of 32 draws gets a new valid order of the scope, seeded by `(task, g, batch)`. So the rate is an average over valid orders. Draw seed i of form g is `int(sha1(f'{task} {g} {i}').hexdigest()[:12], 16)`.
- With the defaults of `superdag_search.py` (`SEARCH_READ_SCOPE`, `SEARCH_NEW_TABLE`, `SEARCH_FREE_STOP` and the prefix score off), the search's chance of a clause is the chance of the `Sampler.clause` draw. This read measures that chance and not the search's order. "Why INIT rarely reads Ident" measured the order apart.

### Stopping rule, per form
1. Draw in batches of 32.
2. After each batch, take the Jeffreys 95% interval of r: Beta(h + .5, n − h + .5), quantiles .025 and .975 (`scipy.stats.beta`). Multiply both ends by `P_kind`.
3. Stop where the interval's top is under `0.1 × p_gold` (resolved: under a tenth), where its bottom is over `0.1 × p_gold` (resolved: not under), at n = 256, or at 120 CPU s for the form (unresolved).

### Per form
- Bits lost `L = log2 p_gold(s | C1) − log2 p_prop(s | scope)`. It splits as `L_kind = log2 p_gold(k | C1) − log2 P_kind` and `L_within = L − L_kind`.
- The flag is `under`, `not under` or `unresolved`, by the stopping rule. The point flag is `p_prop < 0.1 × p_gold`.
- Side counts on the same draws:
    - `shapes`: the counts of every within-kind shape drawn.
    - `reads_ident`: draws whose text reads a scope form that holds Ident. A drawn `Clause.text` names scope forms by their written heads.
    - `key_ident`: INIT draws with `K = key-ident`.

## Measured cost on one task
These are probes in `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-ident-block-read-design/` (`probe_draw.py`, `probe_types.py`), on 135a2760 under the pins. They aren't part of the read.

- A replay of the 37 forms of gold took 2.3 s. The column types matched the pinned list on forms 29 to 34.
- RULE draws at the 30-form scope of form 30: 30 draws in 16.5 s, 2.5 s of which replayed the scope. That is .47 s a draw.
- INIT draws at the 31-form scope of form 31: 67 draws in 14.1 s, .21 s a draw. The peak RSS was .98 GB.
- So a form costs from about 10 s (resolved at 32 draws) to 120 s (the cap). Scopes vary, so the smoke step measures the rate again and prints it.

## Forms read
- Pass 1, per task:
    - Up to 12 Ident-only forms. Group them by stratum (kind, link bin `1`, `2`, `3-4`, `5+`), shuffle each stratum with a seed, and take forms from the strata in turn.
    - Up to 3 plain control forms: forms that have a table, hold no Ident, and have a kind in `KIND_TOK`, chosen with a seed.
    - That makes about 290 Ident-only forms on the 37 and all 41 on the ramp, with about 110 plain forms.
- Pass 2: the other Ident-only forms, about 200, all on the 37.
- The read weights each task's done Ident-only forms by (its Ident-only forms) / (its done forms), so pass 1 alone gives estimates of the totals. Tables give the raw counts beside the weighted ones.
- Optional pass 3, the in-sample control: 60 corpus Ident-only forms, with stems and forms seeded and stratified by kind and link bin, drawn on `models-tk`. Run it only if the verdict reads A or mixed.

## Files
All scripts are in `R`. Each script streams. It appends one JSON line per unit as soon as the unit exists, flushes, prints `[done/total, rate, ETA]` every unit, and skips the units the output already holds on a rerun.

| File | Does |
|---|---|
| `ib_lib.py` | Pins and the pin check, paths, task sets, gold loaders, `parse` (kind, head, reads), `ancestors`, `valid_order(scope, rng)`, `replay(task_json, forms, models)`, `tables_of(ct)`, `shape_of`, `links`, `facts(scope, reads, holds, links)`, `cell(facts, level)`, `jeffreys(h, n)` |
| `ib_env.sh` | `ib_env.sh CPUS SCRIPT ARGS`: checks the pins, exports the settings and `PY`, unsets `STEER_COVER`, and runs `/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus CPUS --need soon` on `$PY -u R/SCRIPT ARGS` for a `.py` script, or on `bash R/SCRIPT ARGS` for a `.sh` script. `ib_env.sh check` prints the pins and exits 1 on a mismatch |
| `ib_corpus_all.sh N` | Starts N shard loops at once and waits for them. Loop k runs `$PY -u R/ib_corpus.py --shard k/N` again until `R/corpus/rows-kofN.jsonl` holds the line `{"rec": "shard_done"}` |
| `ib_held_all.sh PASS P` | Runs `$PY -u R/ib_held.py --task T --pass PASS` for each task, P at a time, through `xargs -P P`. The tasks are the 37 and the 22 for passes 1 and 2, and the stems that `ib_held.py --list-pass3` prints for pass 3 |
| `ib_corpus.py --shard K/N [--limit M]` | Writes the corpus pin, then replays each corpus stem of the shard (stems by index mod N). Appends to `R/corpus/rows-KofN.jsonl`, one line per form: `stem, g, kind, shape, facts, link, holds, ident_only, nscope`, and one `{"rec": "task", "stem", "forms", "replayed", "error"}` line per stem. A replay error keeps the forms that replayed. The process exits after a stem when its RSS passes 3 GiB, and the driver loop starts it again |
| `ib_held.py --task T --pass 1\|2\|3 [--forms g,g] [--max-draws N] [--out DIR]` | One task per process. Models: `models-tk` for the 37 and pass 3, `models-tkf` for the ramp. The Run that gives `P_kind` is `sampler.run`, which the first `sampler.clause` call makes. Replays gold (held: `points-eval.json`; pass 3: the corpus copy), checks the replay against the pinned Ident-only list, picks the pass's forms, and runs [The proposal's rate](#the-proposals-rate) for each form not done. Appends to `R/held/T.jsonl` one line per form: `task, set (37, ramp, corpus), pass, role (ident, plain), g, kind, shape, facts, link, nscope, p_kind, admitted, n, h, flag, cpu, orders, shapes, reads_ident, key_ident, drops` |
| `ib_check.py` | The checks of [Checks](#checks), on one task or a few tasks, each under 30 s |
| `ib_read.py` | Reads `R/corpus/*.jsonl` and `R/held/*.jsonl` and writes `R/tables.json` and `R/results.md` |

## Checks
- **C1, Ident-only list**: on each held task, the replay's Ident-only forms equal the pinned list. `ib_held.py` checks this on every task and stops the task on a mismatch. The smoke check runs it on 135a2760.
- **C2, the shape at its scope**: for 4 Ident-only forms and 2 plain forms of 135a2760, replay (the scope in a valid order, then form g) and take `shape_of` on the last collected table set. It equals the shape from the full-program replay.
- **C3, the draw side**: for 5 drawn clauses at one scope, replay (scope, then `clause.text`) and take `shape_of`. It equals `shape_of` on `clause.tables`. This shows that `Clause.tables` holds the clause's own tables.
- **C4, DAG invariance of facts**: on 20 corpus stems, replay the program in gold's order and in one other valid order, as whole programs. Shapes, facts and links agree on every form.
- **C5, seed and order stability**: on 2 forms of 135a2760, two runs of 64 draws, each with its own seed base and orders, give rates whose Jeffreys intervals overlap.
- **Data check, after the runs**: corpus stems replayed against stems listed, forms per kind, cells under 40 forms, held forms done by pass against the lists. `ib_read.py` prints these first.

## Controls
- **Plain forms**: the plain control forms of the same tasks, read with the same rates. A loss particular to Ident shows in the Ident-only rows and not in the plain rows.
- **Noise floor**: for each done Ident-only form, replay the stopping rule 1,000 times with binomial draws at `r = min(1, p_gold / P_kind)`, a proposal that matches gold's cell. The share flagged `under` is the false-flag rate. Report its count beside the real count.
- **Response**: for each kind, merge the held rows (Ident and plain) into three scope classes: no Ident in scope, Ident in scope but not at a sink, Ident at a sink. Give gold's within-kind share of `I ≥ 1` and the proposal's mean within-kind share of `I ≥ 1`. Compare the rise from the first class to the third in log-odds, gold against the proposal. This table reads the proposal's conditioning on Ident directly.
- **Pass 3** (optional): the same rows on corpus forms, in sample for the priors. A loss that stays in sample is a property of the proposal's form, not of holding tasks out.

## Read
`ib_read.py` writes these tables to `R/results.md`, with the 37 and the ramp apart. The table rows are shapes, then all Ident-only forms, then the plain control.

**Table 1, by shape** (the deliverable): `shape | forms (done, total) | median p_gold | median p_prop | mean L | median L | mean L_kind | under (resolved) | unresolved | under, weighted to all forms | noise-floor under`.

**Table 2, by link** (Ident-only forms): `link bin | forms | median L | mean L | share under | median L, INIT keyed | median L, RULE`. Below it, the OLS slope of L on `link` (capped at 8), with a 95% interval from 1,000 bootstrap draws over tasks.

**Table 3, response**: as in [Controls](#controls).

**Table 4, against the 4% figure**:
- The phrase "INIT per-instance read" is in no record found. The nearest figures, both in `work/results.md`:
    - 4.2%: in an Ident scope, INIT reads an Ident form on 4.2% of search tries, against gold's 31.6% ("In an Ident scope, INIT reads an Ident form on 4.2% of tries"; in "Why INIT rarely reads Ident", 4.2% on `cover` inside the visit's real length, 28.6% in random draws on `dagb`, gold 55.2% with an Ident form in reach).
    - .04: "INIT reads Ident, keeps Ident" has a pool share over gold share of .04 on the 37.
- Rows:
    1. Over INIT draws at Ident scopes (`ident_in > 0`), the share with `reads_ident`. This is the draw's figure, beside 4.2%, 28.6% and gold's 31.6% and 55.2%.
    2. The median `p_prop / p_gold` of INIT Ident-only forms, keyed and not keyed. This is beside .04.
    3. The share of INIT draws with `key_ident`, beside gold's 36.4% of keys that take an Ident label.

**Table 5, cells**: corpus forms per `C1` cell, the backoff level of each held row, and the `C2` and kind-alone means of L.

## Predictions
Written before any number of this read.

### What each reading predicts
- **A, the proposal's Ident conditioning is the block.**
    - A1: on the 37, 40% or more of Ident-only forms (weighted) are `under`, and the median L is 2 bits or more.
    - A2: on the plain control, 15% or fewer are `under`, and the median L is 1 bit or less.
    - A3: the loss doesn't need depth: the median L at link 1 and 2 is 2 bits or more.
    - A4: in Table 3, the proposal's log-odds rise of `I ≥ 1` from no-Ident scopes to Ident-sink scopes is under half of gold's rise.
- **B, compounding over chain depth is the block.**
    - B1: 15% or fewer of Ident-only forms are `under`, and the median L is 1 bit or less.
    - B2: L is flat in link. The slope is within ±.3 bits a link, and the median L at link 5+ is 1.5 bits or less.
    - B3: the per-form shape loss can't explain the pool's cover by link (10 of 78 form-runs at link 1, 3 of 108 at link 2, 2 of 578 at link 5+ on the 37), so the cost lies in the chain: each link waits on the one before it.
- **C, conditioning that worsens with depth.** The median L at link 1 and 2 is 1 bit or less, and the slope is .5 bits a link or more.
- Any other result is **mixed**. The verdict then names the shapes that hold the `under` forms and their share of all Ident-only forms.

### Rule for the verdict
A reading holds where each of its numbered items holds: A1 to A4 for A, B1 and B2 for B, the one line for C. B3 is how B is read, not a test. `ib_read.py` applies A, B and C in that order to the 37, weighted, and prints the first that holds, with the value of each item. It then prints the ramp's result under the same rule, as a second read. The ramp has 41 forms, so its read is weak.

### Point predictions
- `INIT` keyed on Ident (58 on the 37, 12 on the ramp): median L 4 to 5.5 bits, 70% or more `under`. The earlier draw read gave 1.0 to 1.7% of keys on an Ident label against gold's 36.4%.
- `INIT` not keyed (32 and 11): median L 0 to 1 bit, 15% or fewer `under`.
- `RULE` (400 and 16): median L 1 to 2 bits, 10 to 25% `under`. The earlier read gave 17.2% of RULE tries with an Ident table in Ident scopes.
- All Ident-only forms on the 37: median L 1.5 to 2.5 bits, 20 to 35% `under`. The slope is 0 to +.3 bits a link. Verdict: mixed. Conditioning blocks keyed INIT, which is about 12% of the forms. For the RULE bulk, the shape costs about 1.5 bits a form, so the chains' length is what blocks.
- Plain control: median L .7 bits or less, 10% or fewer `under`.
- `L_kind`: from −.5 to +.7 bits on each shape.
- Table 4: the INIT draw reads an Ident scope form on 25 to 35% of draws at Ident scopes, so the 4.2% belongs to search order and visit end, not to the draw. The median `p_prop / p_gold` of keyed INIT is .03 to .1, close to the .04 of pool against gold.

## Steps and commands
Set `R` and `E=$R/ib_env.sh`. Run each command under `timeout 30`. Hand back each command marked "hand back", with its ETA. The smoke step's measured rate replaces the ETAs given here.

1. Write `ib_lib.py`, `ib_env.sh`, `ib_corpus.py`, `ib_held.py`, `ib_check.py` and `ib_read.py`, and `R/manifest.json` with the pins, this design's path and the predictions.
2. `timeout 30 bash $E check`: 5 s. Every pin matches.
3. `timeout 30 bash $E 1 ib_check.py c1c2 135a2760`: 10 s. C1 and C2 pass.
4. `timeout 30 bash $E 1 ib_check.py c3 135a2760 30`: 15 s. C3 passes.
5. Smoke: `timeout 30 bash $E 1 ib_held.py --task 135a2760 --pass 1 --forms 30,31 --max-draws 32 --out $R/smoke`: 25 s. Rows for both forms. Each row has `n` = 32, a `p_kind`, a flag, the side counts, and a rate in draws a second. A rerun of the same command writes nothing and prints "2 done".
6. `timeout 30 bash $E 1 ib_check.py c5 135a2760 30,31`: 28 s. C5 passes. If one call can't hold both forms, run them one at a time.
7. `timeout 30 bash $E 1 ib_corpus.py --shard 0/1 --limit 8`: about 20 s. It prints s a stem. ETA for 989 stems = that rate × 989 / 4 at 4 processes.
8. `timeout 30 bash $E 1 ib_check.py c4 20`: under 30 s. If it runs over, give it 10 stems.
9. Hand back. Corpus replay, 4 processes, about 1 GB each: `bash $E 4 ib_corpus_all.sh 4`. A restart after the RSS exit goes on where the shard stopped. ETA: about 1,000 to 1,500 CPU s, about 5 to 7 min wall. It can run beside step 10.
10. Hand back. Held pass 1, one process per task, 8 at a time, about 1 GB each: `bash $E 8 ib_held_all.sh 1 8`. ETA: about 440 forms at a mean of about 55 CPU s, so about 6.7 CPU h, about 50 to 60 min wall. The longest task is about 15 forms × 120 s = 30 min.
11. `timeout 30 bash $E 1 ib_read.py`: under 30 s on pass 1 rows. Check the data check lines and the tables. If the corpus rows aren't complete, it stops and says how many stems are left.
12. Hand back. Held pass 2: `bash $E 8 ib_held_all.sh 2 8`. ETA: about 200 forms, about 3 CPU h, about 25 min wall. Run it where the director wants all 495 forms on the 37. Without it, the pass 1 weights give the estimate.
13. Optional, hand back. Pass 3, the in-sample control: `bash $E 8 ib_held_all.sh 3 8`. ETA: about 60 forms, about 1 CPU h, about 8 min wall.
14. `timeout 30 bash $E 1 ib_read.py` again after each pass. Then copy `R` as in [Record](#record).

## Limits to state in results.md
- The read measures the draw distribution (`Sampler.clause`), not the best-first search's order or its visit end.
- The cell rate is a coarse model of gold. A proposal that equals gold's own process still shows L below 0 on average, because that process knows more than the cell. So L at or above 0 is a loss even against a coarse gold model, and the size of L is a lower bound.
- The shape is a necessary part of a cover, not the whole of one. A small L rules out the head shape as the block. It doesn't rule out the body.
- `relR4_o.pkl` holds the ramp in its train rows. The corpus copy is of 21:49, and the priors were fit earlier.
