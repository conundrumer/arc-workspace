# Scope loss, class C: where the proposal's chance of the gold clause falls short under the recorded scope

Reader: the agent that builds and runs this read. This file stands alone.

`REC` below is `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22`. `RUN` is `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943`. `OLD` is `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad`. `KIT` is `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943`.

## Question

Round 1 ran on the 37 held tasks, arms `bundle_s0` and `bundle_s1` (seeds 0 and 1000), 600 s. For the gold forms whose reads the scope held with the form's kind and whose clause was not drawn, and for the frontier's one-read forms past their expected tries: where does the proposal's chance of the gold clause, under the exact recorded scope, fall short of what the form's bits say? Does the shortfall sit in a few named places, or is it spread?

The answer is one message: forms counted, the median gap in bits, and where the gap sits. If the gap is spread, the message is one line and stops there.

## Rules

- Each Bash call is one command under `timeout 30`. A command that runs longer goes back to the director with its exact command and an ETA from a measured rate. Do not run it.
- No background commands. Do not poll a task's output.
- At most 4 processes on this Mac, each through `/Users/davidlu/code/arc-workspace/scripts/run_heavy.py`. Memory is tight.
- Write only in `REC`. Do not commit.
- Do not read `feat-exp/private/`, `feat-exp/case-cache*/`, `feat-exp/out/`, `feat-exp/stream/`, `*.building`, `judgetool/dataset-contexts/`, `dataset-export-receipts/`, `operator/private`, or any `inform-key/` folder.
- Use the recorded scopes. Do not replay the pick or make a new scope.
- The measure and its parts must not depend on lexical order or on binder marks (`*`, `^`). A place is named by DAG facts (decision type, relation class, construct), never by atom position.

## Forms that enter

| source | record | rule | count |
|---|---|---|---|
| C | `RUN/scope-loss/forms.tsv` | `class == 'C'` and `arm` in `bundle_s0`, `bundle_s1` | 25 and 27 |
| frontier proposal | `RUN/frontier/ready.tsv` | `nreads == '1'` and `bk_primary == 'proposal'`; arm is `bundle_s` + `seed` | 18 and 18 |

The frontier forms are 35 C forms and 1 more: `bundle_s0 5961cc34 g20`, class K (its read was held only in visits of another kind). The union is 53 forms (26 and 27). Key: `(arm, task, g)`. Keep `source` as `C`, `frontier` or `both`.

`g` is the index of the form in gold's non-OUT lines of `KIT/points-eval.json` (sha256 prefix `af855438`), the same index that both records use.

An option `--arms refit_s0,refit_s1` adds the C forms of the refit arms (33 and 29) for a second read. The verdict uses the bundle arms only.

### Outcome by form, from the probe (bundle arms, before the fixes below)

| status | forms |
|---|---|
| mapped, table check passes | 36 |
| a read relation is not in the scope | 5 |
| ports not mapped (the fix for proposer relations below takes about 5 of these 8) | 8 |
| the equal table is an INIT relation with no known name (the fix below takes it) | 1 |
| no held-with-kind opening whose scope the bank holds | 2 |

The frontier K form was not in the probe. Expect about 43 measured forms, about 40 of them with dag bits (4 of the 52 C forms have no dag bits).

"A read relation is not in the scope" is a finding, not a fault. Class C is defined by covers at form level: a node covers gold form `q` when its table equals any one relation of `q`. An INIT form makes several relations, and the clause may read one that no scope form holds (examples: `142ca369 g2` reads `&r1.exposed`, `dbff022c g18` reads `&r33.enclosed`). For such a form the clause cannot be drawn from that scope. Report these forms as their own named place, with no bits.

## Definitions

### The opening and its scope

- Openings and their rows come from `OLD/scope-loss/cache/<arm>__<task>.json`: `ops[i]` (fields `slot_tries`, `lost`, `kind`) and, per gold form, `golds[k].rows` (fields `i`, `held`, `hk`).
- The opening of a form: among rows with `hk` true and `ops[i]['lost'] == 0`, the one with the most `slot_tries`, ties to the lowest `i`. For the K form: rows with `held` true and `lost == 0`, by the same rule, and the row field `kind_match` is false. No such row: status `no replayable scope`.
- The recorded scope: `OLD/r1-forms/cache/<arm>__<task>.json` has `openings` and `visits`. Opening `i` is the `i`-th opening with picks, by time. Its matched visit is the first visit with `resume` false and `o.time <= v.time <` the next opening's time (any opening). The scope is that visit's `fids`, sorted by `(forms[f].depth, f)` of the bank, as `superdag_search.next_slot` sorts them; the texts are `forms[f].text`. Assert `v.kind` equals the gold kind for a C form.
- The bank: `RUN/out/<arm>/<task>/work/<task>.out.jsonl.bank`, loaded with `search_node_score_parity.load_bank` (in `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools/`). It needs no engine.

### The target: gold's clause in the scope's names

The search draws over the scope's own form texts (names `&fK`). Gold's clause reads gold names (`&rX`, `&rX.sub`). The target is gold's clause with each read relation replaced by a scope relation with an equal table, and its ports renamed to that relation's columns. `REC/probe/p4.py` does this and is the base for the code; the fixes below are not in it.

1. Replay gold's non-OUT lines and the scope texts, each with `superdag.Run` and `run.collect = []`, on `superdag.session_of(task)`. For each relation slot `s` of each collected table: `parse_table(OneTable(ct, j))` (skip a table that raises: a table past the work cap, as `superdag.gold_keys` skips it), `table_key(tb)[0]` (the merge key), `tb['labels']`, and column signatures `(str(type), hash of the column's values by example)` as `superdag.table_key` computes them per column (`col_sigs` in `p4.py`). The relation's name: `pg.names['&r%d' % s]` gives `&rH` or `&rH.j`; `pg.written['&rH']` gives the text head (`&fK` for scope forms). Key each relation by `(text head, j or None)`.
2. Gold refs of form `g`: the names in its text, its own head left out, in text order. Their slots: the relation tokens (vocabulary names `&r<digits>`) of `or_q.gold_rest(sess, lines[:g], lines[g], kind)`, in order. The two lists have the same length on all 52 probe forms; if not, status `refs and tokens differ`.
3. For each distinct gold ref, the scope candidates are the scope relations with the same merge key. No candidate: status `read relation not in the scope`. Try candidates in this order, and take the first that maps: (a) an INIT relation with the same `j` whose form has gold's text up to names; (b) a head relation (`j` None); (c) an INIT relation whose sub-name is known; then ties in scope order. A candidate maps when:
   - the labels are equal (no rename), or
   - `port_map` gives a one-to-one map of gold labels to scope labels by column signature, ties taken in column order. Labels must be plain: no `''` and no repeats.
   - **Fix, proposer relations.** A scope relation of one column whose label is `''` and whose form is `(DET &fK P)` with no body takes as its label the port name that readers of any `(DET &x P)` form use, in the task's gold lines and the job's bank texts. Use it only where all such readers use one name.
   - **Fix, INIT sub-names.** The name `&fK.sub` of INIT relation `j` comes from a map `(component, j) -> sub` learned by step 2's alignment over every form of the gold lines and of the scope (the component is the third word of the INIT form's text).
   - A port whose value is a record (a list of ports) stays as it is. Where the labels differ and the atom has a record port, the candidate does not map.
4. Rename in the parsed tree (`form_orders.parse`): each atom whose first symbol is the gold ref gets the new name and the mapped port names (`rename` in `p4.py`). Then `or_q.sorted_fields(text, sess, scope)` puts ports in the column order of the scope relations.
5. Table check (gate): replay `scope + [target]`; the sorted merge keys of the target's relations must equal those of gold form `g`. A fail is status `table differs`. The probe had no fail on 36 forms.

Where a ref does not map, status `unmapped` with the reasons in `how`.

### The bits

All walks use `or_q.walk(sampler, task, case, point, scope, target, sess, task_json, kind)` of `KIT/model/study/sampler/or_q.py`: gold's clause forced through `search.SearchRun` (the class the visit's search uses) with each choice on gold's side, each order's bits from the first try of each choice as the search counts a path, and `total` = -log2 of the sum of the chances over the valid atom orders. `parts` holds the chance-weighted mean of each named decision over the orders, with `orders: entropy credit` making the parts sum to `total`. `atoms` and `detail` give each atom's mean bits and its phases (`cur`). A walk is valid where `bad` is empty, `dead` is None and `left` is 0.

- **S**: the target over the recorded scope, the gold kind.
- **R**: gold's form over gold's own ancestors, by the dag-bits method on this kit. Take `sub` = the lines of `g`'s ancestors and `g`, in their order. `canon, _ = or_q.canonical_lines(sub, sess)`; scope `or_q.canonical_scope(canon, k)` and target `canon[k]`, with `k` the index of `g` in `sub`.
- **DB**: "the form's bits", from `gold-v3-dag-bits` as the frontier read took them: `OLD/frontier/bits.json`, `[bits, status, dir]` per task and form. Use statuses `exact`, `one` and `bound` (a bound is an upper bound). A form with no DB has S and R and enters the S - R tables only.

R is needed because DB holds a total per form and no parts. R uses the run's code, priors and settings; DB used `models-base` and the dag kit's code. On the 15 probe forms with all three, R - DB was within 3.2 bits, and within 1 bit on 9 of them.

### The places

Each form's gap is `S.total - DB.bits`. It splits into ten scope places, each `S_k - R_k`, and one place `R.total - DB.bits`. The places sum to the gap.

Split of `parts` into places. An atom part has the name `<ctx> atom: <phase>`, where ctx is the place in the form (`top`, `br1`, `key`, `port`, ...). The phase is one of `relation`, `relation (op)`, `column`, `column stop`, `value: label`, `value: other`, `join mix`. An atom reads a scope form if its relation is a name `&f...` or `&r...`. For a NOT atom, its inner atom's relation counts. Split each atom-phase total from `parts` between read atoms and the other atoms by the shares in `detail[k]['cur']`, where `atoms[k][1]` is the atom's text. Where no atom row has that phase, the whole total goes to the other atoms, and the row is counted in a check.

| place | parts |
|---|---|
| relation pick: read | phase `relation` at read atoms |
| relation pick: builtin | phase `relation` at other atoms |
| op pick | phase `relation (op)` (NOT, comparisons, `=`) and `br:else-NOT pick` |
| argument fill: read | phases `column`, `column stop`, `value: label`, `value: other` at read atoms |
| argument fill: other | the same phases at other atoms |
| join coin | phase `join mix` |
| stop | `top:stop`, `br:stop`, `br:go on` (any ctx prefix) |
| proposer | `proposer`, `proposer or atoms` |
| OR and ALL | `or:*`, `br:*` (other than stop and go on), `top:no OR`, `top:no ALL`, `all:guard stops`, `key: which labels an OR exports` |
| INIT structure | `component`, `keyed`, `key: count of labels`, `key: which labels`, `port: *`, `outside: *`, `head: *`, `long body`, `key partly read`, `rigid: *` |
| order sum | `orders: entropy credit` |
| priors and code | `R.total - DB.bits` |

A part name that fits no row goes to `other`. Expect 0; report the count and the bits.

The kind is not a place: a C form's opening drew the form's kind. The K form is the exception, and its row says so.

Besides the ten-place split, write the sum of each raw part name over forms (S, R, S - R). This lets a reader see a finer split.

## The rule, fixed before the numbers

Use measured forms: status `mapped`, S and R valid, and DB present.

1. Per place k: `M_k` = the sum over forms of the form's gap at k.
2. Positive mass `P = sum_k max(M_k, 0)`. Share `s_k = max(M_k, 0) / P`.
3. The top 3 places are the 3 with the largest share on all forms. `T3` is the sum of their shares.
4. Bootstrap over tasks: draw 2,000 resamples of the tasks, with `numpy.random.default_rng(0)`. A task brings all its forms of both seeds. Recompute `T3` for the same 3 places in each resample.
5. **A few named places** if the 2.5% point of `T3` is 0.60 or more. Otherwise, **spread**.
6. If the median gap (`S.total - DB.bits` over measured forms) is under 1 bit, the verdict is **no gap**. The rest of the rule does not apply.

The forms whose read relation is not in the scope are their own place, with no bits. The message gives their count beside the measured forms.

Note: the probe printed S and R totals for 15 forms, and parts for 3 of them, before this rule was written. The rule does not use those numbers.

## Scripts and outputs (all in `REC`)

- `env.sh`, in the form of `features-tower-read-heldout37-ramp22/tw_env.sh`. Python `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python -u`. `sys.path` first: `KIT/model/study/sampler`, then the engine `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path`. The environment of the run's job lines: `P_DAG=1 ORDER_FREE=tie,key ARCLOG_IDENT_SOURCE=value ONE_REPAIR=30 CHOOSE_LIFT=0 RAYON_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1`, with `STEER_COVER` and `KEY_IDENT` unset. Priors: `live.Sampler(KIT + '/models-tk')` with the default steers, as `kaggle_worker.py` makes it. It runs the script through `run_heavy.py --cpus 1 --need soon`.
- `job.py [--budget S] [--shard I/N] [--arms ...] [--all-slots]`. Streams one JSON line per form to `forms.jsonl` (`forms-<arm>.jsonl` with `--arms`) as soon as the form is done, and skips the keys that are done. Shard by `zlib.crc32(task.encode()) % N`, so that a task stays in one shard. With `--budget`, it stops after the form in progress once S seconds pass, and prints `done N todo M`. It exits 75 when RSS passes 3 GiB after a form (rerun it). A form that raises gets a row with status `error` and the message, so a rerun does not loop on it.
- Row fields: `arm`, `seed`, `task`, `g`, `kind`, `source`, `nreads`, `opening`, `n_hk`, `slot_tries`, `kind_match`, `scope_fids`, `scope_n`, `how`, `status`, `target`, `table_check`, `S` and `R` (each: `total`, `parts`, `atoms`, `detail`, `orders`, `bad`, `dead`, `left`, `fell_back`), `DB` (`bits`, `status`), `cpu`, `wall`, `rss_gib`.
- `read.py`: reads the rows and writes `places.tsv` (one row per form and place: S_k, R_k, gap), `parts.tsv` (raw part sums), `summary.json`, and `results.md`. `results.md` holds the tables below and the message.
- `manifest.json`: the pins (kit path, sha256 of `or_q.py`, `live.py`, `search.py`, `superdag.py`, `superdag_search.py`, `form_orders.py`; models-tk `live_priors.pkl` sha256, which the kit manifest gives as `7dafa0ce...`; the engine `.so` path and sha256; points-eval sha; `sampler_paths.REPO`, which must be `KIT`; the settings), the command and the rule.

### Engine

The run's engine wheel is commit `e8c1b7882`. The Mac build `runtime-0a7d32160` differs from it only in `engine/lib/study-meanings.json` (`git diff --stat 0a7d32160 e8c1b7882`, outside `work/`, `model/`, `prompts/`, `docs/`, `programs/` and `data/`). State this in the manifest.

## Tables in `results.md`

1. Forms: entered, by source and arm; by status.
2. Per form: arm, task, g, kind, source, scope_n, slot_tries, S, R, DB and its status, S - R, S - DB, and the largest place.
3. Places: for each place, the sum of gaps, the share with its bootstrap interval, the median gap per form, and the number of forms where it is the largest place. Then T3 with its interval, and the verdict.
4. The same table on S - R only (the ten scope places), with the forms that have no DB included.
5. The forms whose read relation is not in the scope: arm, task, g, the relation gold reads, and the relations of that gold form that the scope does hold.

### The message

One of these:

- `N forms counted (M measured, X with a read relation absent from the scope, Y not measured); median gap G bits over the dag bits; spread: the top 3 places hold T3 of the gap [lo, hi].`
- `N forms counted (...); median gap G bits over the dag bits; it sits in A (a bits a form, s%), B (...), C (...): T3 [lo, hi] of the gap.` Then one line on R - DB (priors and code) when that place is in the top 3.
- `N forms counted (...); median gap G bits: no gap.`

## Checks (in `summary.json` and in a section of `results.md`)

1. Table check: every mapped form passes. A fail is a fault in the mapping: report it and do not count the form.
2. Walks: S and R valid on every mapped form. Report the others with `bad` or `dead`.
3. Kind: the matched visit's kind is the gold kind on every C form.
4. Sums: on each walk, the places sum to `total` within 0.05 bits. The scope places use `parts`, so this checks that the place table covers all part names.
5. Read and other split: count the atom phases that had no atom row and went to the other atoms.
6. R against DB: median, interquartile range and largest absolute value of `R.total - DB.bits`, split by DB status. Name the forms beyond 3 bits. This is not a gate.
7. Order free: for 3 forms with an exact order sum and 2 or more orders, walk S on a target text whose body atoms are in reverse order. Its `total` must equal S within 0.01.
8. Determinism: rerun 2 forms. The totals must be equal.
9. Exact or estimate: count the walks where `orders.exact` is false (more than 256 orders; the total is an estimate, with `se_bits`).

## Cost

Items: 53 forms, each with a bank load, two replays, a table check, and two order sums.

Measured in the probe (`REC/probe/p4.jsonl` and `p4-map.jsonl`, one process):

- Load, mapping and table check: 0.2 to 7 s a form, median 0.6 s (52 forms in about 65 s).
- The S and R walks on 15 forms: median 0.1 s, largest 26.7 s (`dd6b8c4b g14`, 120 orders). `f560132c g10` (seed 0) did not end within 28 s.
- Not measured: `canonical_lines` for R. It runs over the form's ancestors only, and the probe's R with no canonical step took under 1 s on most forms.
- `or_q.walk` stops a clause's order sum at 300 s, so one form costs at most about 10 minutes (S and R).

ETA: about 50 forms at 2 to 5 s each, and 2 to 4 heavy forms at 1 to 10 minutes each. On 2 shards: likely 10 to 15 minutes, at most about 40 minutes. Commands (each is slow, so hand them to the director):

```
bash REC/env.sh job.py --shard 0/2
bash REC/env.sh job.py --shard 1/2
```

Smoke test first, under 30 s: `timeout 30 bash REC/env.sh job.py --budget 15` on the first forms. Check the rows against `probe/p4.jsonl`: the S totals of the forms that both hold must be equal. R can differ, since the probe's R has no `canonical_lines` step.

`read.py` takes seconds.

Optional, after the main read:

- `--all-slots` walks S on every distinct held-with-kind scope of each form, at about 8 scopes a form. It gives a per-form median over scopes, which shows whether the scope with the most tries is typical. ETA: about 8 times the S half of the main run.
- `--arms refit_s0,refit_s1` adds 62 forms, at about the same rate a form.

## Limits

- The walk's sessions are fresh (`live_try.session_of`, 2 GiB byte bound). The search's session was warm and had 0.9 of 2,888 MiB. Table work counts only what a session has not cached, so the bits can differ from the visit's own path bits. S and R have the same treatment.
- The chance is the proposal's chance of gold's clause, path by path. The visit's best-first search, its patience and its seconds are not in it.
- One opening a form (the one with the most slot tries). `--all-slots` covers the rest.
- The scope relation for a gold read is the first that maps, by the order above. Equal tables give equal clause tables; their column orders can differ, and the bits go with the column order.
- A record port maps only where the labels are equal.
