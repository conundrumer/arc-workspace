# Ident sources: design

An Ident column has one source. A join of two Ident columns is legal only at the same source. The checker refuses every other join, every union of two sources, and every comparison of two sources, so `Decoder.admits` does not admit those tokens and the sampler cannot draw them. An Ident's value holds the id of the node that made it, and is the same in every process.

Paths are relative to the worktree, except paths that start with `work/`, which are relative to the main checkout. Line numbers are at commit cbb82f51d.

## Definitions
- **Maker**: a form that makes Ident values. Today: an `INIT` on `Connectivity` (output `component`), `Enclosure` (`enclosed`) or `Quotient` (`class`), and a `DET` on the proposer `PanelCombine`. These are the only `Ident` columns in `engine/lib/registry.sexpr` (lines 182, 270, 426, 763). No fact and no plain lib relation has one.
- **Source**: the type's name for a maker. One form and one output port. Within one program, the form's name identifies it.
- **Handle**: the `u32` that a row holds for an Ident. It stays in one process.
- **Cell**: the `i32` that a table export gives for an Ident.

## Today's behaviour
- **Type.** `ValueType::Ident` is one unit variant: `engine/arclog/src/types/lattice.rs:23`. Two Ident columns have equal types, so `meet` (`lattice.rs:54`) gives `Ident` and `join` (`lattice.rs:67`) gives `Ident`.
- **No rule refuses a cross-source join.** The only analysis of Ident places is `engine/arclog/src/check/types/own_idents.rs`. It finds an assembly's own Idents and refuses nothing. `docs/arclog/rigid.md:42` says so.
- **Checked on a program.** `engine/target/release/check_one` (build of Oct 27) on the two programs in the folder `tiny/` beside this file:
    - `tiny/cross`: `(&obj.component *P *Id) (&obj2.component (:P *Q) (:Id Id))`, and the same read under `NOT`. No `Check(Types)` line. Only `Check(Spelling)` lines.
    - `tiny/clash`, the control, an Ident label at a Color site: `Check(Types) the label here stands at sites of the types Ident and Color, whose meet is empty`.
- **Value.** An Ident is an index in the session's intern table: `engine/arclog/src/terms.rs:204-208`. The table keys it by the set of members, with the members' type: `terms.rs:296-300`, `terms.rs:637-657`. So equal cell sets from two makers have one Ident in one session, and a cross-source join means "these two sets are equal". The number depends on the order of interning.
- **Where Idents are interned.**
    - `engine/arclog-constructions/src/connectivity.rs:318-330` (`identified`, which `component`, `enclosed` and `class` use).
    - `engine/arclog/src/eval/proposers/native.rs:457` (`PanelCombine`).
    - `engine/arclog/src/terms.rs:519` (an Ident read from a file). `encode_param_value` reaches it from `eval/driver.rs:164`, `eval/rigid.rs:492` and `eval/init_form.rs:480`.
- **Sampler.** The label pick reads the decoder: `model/study/sampler/sample2_col.py:1148` lists every label in scope, and `sample2_col.py:1094-1129` asks `Decoder.admits`. `live.py:96` sets `S.ADMITS`. The path in the engine:
    1. `engine/arclog/src/decode/mod.rs:255` `admits`, `decode/mod.rs:290` `mask_over`.
    2. `decode/mod.rs:313` `fixed_label_conflicts` drops labels with an empty meet. `decode/mod.rs:314` `native_classes` shares verdicts.
    3. `decode/mod.rs:340` `next` runs the prefix checks.
    4. `engine/arclog/src/check/types/form_check.rs:33-39` is the type check on a prefix.
- **Join coin.** The relation pick reads type strings in Python: `joinable` at `sample2_col.py:1562-1598` calls `compat` at `sample2_col.py:548`. `FAMILIES` (`sample2_col.py:370`) holds no Ident, so `compat('Ident', 'Ident')` is true for any two Ident columns. With `must_join`, `sample2_col.py:2175-2176` zeroes the relations outside `joinable`.

## The type
- `ValueType::Ident` takes a field:
    ```rust
    Ident(IdentSource)

    enum IdentSource {
        /// A declared column with no maker yet, an Ident read from a file, and every Ident with the flag off.
        Open,
        /// The one source of the column.
        Form(SourceId),
    }

    /// A hash of the form's name, its canonical form, and the output port. 16 bytes, Copy.
    struct SourceId(StableHash);
    ```
- Lattice, in `lattice.rs`:
    - `parent()`: `Ident(Form(_))` stands under `Ident(Open)`. `meet` and `is_below` then need no change: two different sources have an empty meet.
    - `join()`: one new arm before the parent arm: two `Ident(Form(_))` that differ give `None`. Without it, the parent arm would give `Ident(Open)`.
- The shape follows `ValueType::Pose(AssemblyId)`: `engine/arclog/src/types.rs:21-38`. The name and the canonical form identify the form, so the check cache stays right: `CheckCacheKey` holds the canonical form and the signatures of the forms it reads (`engine/arclog/src/check/mod.rs:368`).
- A tuple variant makes the compiler list each use. The uses:
    - `terms.rs:263`, `:389`, `:412`, `:517`, `:519`
    - `types/lattice.rs:145`
    - `program/arcdata_nodes.rs:84`
    - `study/render_terms.rs:58`
    - `eval/join.rs:976`
    - `eval/rigid.rs:669`
    - `arclog-cli/src/lib_compare/inputs.rs:296`
    - `arclog-cli/src/row_parity.rs:1472`
- **Program text does not change.** The source comes from the form that a read resolves to. No lib relation declares anything: `Fixed(Ident)` at a maker's output means "this form".

### How a source passes through forms
| Place | Source of the column |
| --- | --- |
| Maker's Ident output | The maker. Attach it in `Inference::instance_output` (`check/inference.rs:1418`) and in `port_relation` (`check/inference.rs:1521`). Cache it on `FormInference`, one hash per form. |
| `DET` on `PanelCombine` | That `DET` form. Attach it at `ClauseColumns::Declared` in `clause_column` (`check/inference.rs:1364`). |
| `RULE`, `DET` column | The source of the label at it, by the existing `clause_column` path. |
| Port, key column, column of a type parameter | The binding's type, by the existing `bind` and `project`. |
| Projection | No effect. |
| `CHOOSE` | The label's type, by the existing path at `check/inference.rs:1178-1185`. |
| `RIGID_DET` part or key column | The site's type, by the existing `rigid_output` (`check/inference.rs:1437`). A pose has no Ident. The assembly's own Idents keep their source, and the renaming in `eval/rigid.rs` reads no source. |
| `OR`, `IF`: two branches of one source | That source. |
| `OR`, `IF`: two branches of two sources | Refused. See [Unions](#unions). |
| `OUT` | Never holds an Ident: Position and Color only. |
| Input facts | No Ident column. |
| Ident read from a file (`arcdata`) | `Open`. As today, such a value equals no Ident that a maker made. |

### Rules
- **Join.** One label at two Ident sites of two sources: refused by the existing meet.
- **`NOT`.** A site under `NOT` joins. A label at another source under `NOT` is refused, by the existing walk: `Conjunct::Not(Negated::Atom(_))` reads its sites (`types/label_walk.rs:453`) under `Sites::All`. The reason: with the source in the value, the negated atom never holds a row, so the `NOT` tests nothing. Gold has none of these; 20 of 25 and 10 of 21 kept junk tables are this kind.
- **`=` and `!=`.** `with_constraints` (`label_walk.rs:669-683`) puts the two labels of each constraint in one class, `!=` included, so the meet refuses two sources. No new code. Gold and the pool samples have none.
- **Key.** A keyed maker is one source at all its keys. A join at two different key labels is legal. Gold needs it, for example `b7f8a4d8` `&r25` and `e74e1818` `&r12`. Pose types differ on this, because their keys are part of the type.
- **Type parameter.** Two projections of different sources onto one parameter are refused where the parameter has a bound: `joined_projections` at `check/inference.rs:1625` reads `join`. A parameter with no bound takes its first projection (`check/inference.rs:1642`) and has no such check. Add the check for Ident types in `bound_faults` (`check/inference.rs:326-339`) so that `Quotient`, `Inclusion` and the like follow the one rule. In gold, sampler-worker finds 0 crosses in 160 meetings with 39 traced on one side, and my tracer finds 0. The pool samples have 0.

### Unions
- **How the checker sees branches.** `LabelWalk::conjunct_type` reads each branch of an `OR` (`label_walk.rs:460-471`) and each arm of an `IF` (`label_walk.rs:472-481`). `join_branches` (`label_walk.rs:651`) joins the branch types with `ValueType::join`. With the new `join` arm, two sources give `None`, and `join_branches` gives `LabelFault::NoJoin`.
- **The refusal.** The fault lands on the label in `FormInference::labels`. `refusals` (`form_check.rs:102-119`) makes a refusal at the label's first use. `pose_of_fault` gives `None` for `NoJoin`, so no other rule takes it.
- **How it reaches the walk.**
    1. A later branch stands at a site of an Ident column of source B. The label X, made at source A in the first branch, is a candidate.
    2. `FastFrontier.adm` asks `Decoder.admits` over the labels.
    3. `mask_over` calls `next`, which runs `TypesCheck::check_prefix` on the prefix with X at that site.
    4. `infer_form_where` gives the `NoJoin` refusal at X's first use, in the first branch.
    5. `settled_result` (`check/prefix.rs:564`) keeps a refusal at a node that is not open. The first branch is closed, so the refusal stands.
    6. The token X is not in the mask, so `options` at `sample2_col.py:1161` does not give it.
    - The same path holds for `(= X Z)` with Z of source B: the class of X holds Z, so the branch's type is source B.
    - A join of branches only widens (`form_check.rs:28-32`), so no later token could undo the refusal.
- **What the walk does then.** A later branch that can't name an exported label has three exits, all in place at `sample2_col.py:3025-3032`: it binds the label at a column of the same source; it closes without the label with probability `P_UNNAMED`, which makes the label local to its branch; or it is drawn again up to `BRANCH_TRIES` times. No Python change is needed for this.
- **Two clauses of one relation.** A relation has one clause, and the `column_refusals` path (`check/inference.rs:1323`) reads `join` as well. So a relation of several clauses in one case refuses two sources too. Alts rederive a relation per case, so two sources in two cases are no union.

### Where the draw sees it
- **Label pick**: `Decoder.admits`, with no Python change.
- **Join coin and relation pick**: `joinable` must read the same thing, or `must_join` picks a relation where no label is admitted, and the draw dies as `try:unjoined`.
- **Default.** `joinable` sends a relation with an Ident column to its decoder lookahead while the scope holds an Ident, in place of `compat`. The lookahead at `sample2_col.py:1581-1597` already asks `fr.admitted` for a label, so the column pick and the coin read the mask. The cache key at `sample2_col.py:1582` adds `key` where `tset` holds `Ident`, because the plain type strings don't tell two scopes apart. About 8 lines. Tables keep the plain string `Ident`.
- `col_wanted` keeps `compat`. It gives a soft boost, so a wrong boost costs a redraw and nothing else.
- **Type strings.** `format!("{ty:?}")` would print the source, and exact `"Ident"` compares exist in `arclog-tables/src/study_filters/normal.rs:398,470`, `recovery.rs:78`, `equality.rs:21,107,185`, `model/study/feat_exp/featlib.py:871,943`. So `type_names` at `arclog-tables/src/columns.rs:804`, `study/features.rs:25` and `study/render_correspondence.rs:37` print `Ident` for every `Ident(_)`. Fault messages keep the source.

### Against sampler-worker's definition
- The same at the type level: the source is the form that makes the value. Name and canonical form are one thing in a program.
- **Union in one column**: refused. Same reading as the ruling.
- **Form against form plus method**: the source holds the output port. No component has two Ident outputs, so the two definitions agree on today's registry. A `DET_OR_RULE` line with several proposers has one reading per case, so one form per case.
- **Keyed maker**: one source, as above.
- **`NOT`**: illegal, as above.

## The value
The value is a member digest, and it is the same in every process.

### Why the value holds no source
The value is the member digest alone, and the handle is keyed by the set, as today. Two derivations of one set are equal, and pooled joins across examples match where sets are equal. The source rule stands in the type.
- The type is static, so it can't read table content. Two forms with equal tables stay two sources, and a join of them is refused. The pool merges forms with equal tables, so a draw doesn't meet this.
- Two makers that share one equal set give one value, and a table made from either merges.
- A table hash in the value would need a pass after the key groups, and one handle per evaluation, so a pooled join across examples would stop matching where two tables differ. The pool's merge key can't give that hash, because `table_key` reads the Ident cells.

### Width
- A row holds `TermId(u32)`: `terms.rs:24`, with 367 uses in 46 files. A 128-bit digest doesn't fit. 32 bits of hash alone have about 5% odds of a collision in a session of 20,000 contents (an estimate: 100 makers, 4 examples, 50 classes), and a collision is a false join.
- **So rows keep a handle.** The intern table keeps, per handle, the canonical value. The handle never leaves the process: each export reads the canonical value. Widening `TermId` to 64 bits would double row memory and still not hold 128 bits.

### Member digest
- The digest is a hash of the member set.
- For a set with no Ident member, the intern hash is already canonical (`terms.rs:637-642`, `MemberSet` keeps canonical order). For a set with Ident members, the digest is the sum of each member's hash with each Ident field replaced by that Ident's digest: `set.ident_fields()` at `terms.rs:366` finds them. Children are interned first, so this is bottom-up.
- It needs no table hash, no pass after the groups, and no sort. A pooled join across examples of one maker matches where the sets are equal, as today.
- The canon sort stays where it is used: `IdentNumbering` (`write.rs:171-190`) gives ranks in a written file, `content_order` gives every order.

### What a table export holds
- The cell for a table key is the member digest, cut to 32 bits.
- 32 bits are enough here: one table holds under 1,000 classes, so a collision in a table has odds near 1 in 10,000, and it costs one wrong merge.
- `push_cells` (`arclog-tables/src/columns.rs:820-828`) takes the table's read lock and writes the digest.

### Where the interning changes
- `Content::Set` gains the digest, kept beside `contents` in `InternTable` (`terms.rs:615`).
- `free_unheld` (`terms.rs:670`) keeps the new vector in step.
- `Content::FromFile` stays.
- `Relation::rows_hash` stays: it serves caches in one process.

### Cost
| Item | Cost |
| --- | --- |
| Type check of an atom | One 16-byte compare per Ident site, so O(columns) per atom. One hash per maker form, kept on `FormInference`. |
| Mask | No new path. `fixed_label_conflicts` and `native_classes` read the same `meet`. |
| Member digest, per table | O(1) per class, plus O(members) for a set with Ident members. No sort. Plus 32 bytes per content. |
| Export | One lookup per Ident cell. |

## What it breaks
- **Gold, type.** By the workers' counts: 0 of 25,921 forms join across sources (dataset-worker), and 0 crosses in 2,681 joins, 103 `=` and `!=`, and 160 parameter meetings (sampler-worker). My tracer on the first case of each of 1,105 tasks in `corpus-v3mix`: 0 crosses, 0 under `NOT`, 0 `!=`, 0 parameter crosses.
- **Gold, unions: more than one task.** The ruling refuses every union of two sources. e3721c99 is being removed, and two more tasks hold one:
    - `67e490f4` `&r56` (first case; sampler-worker's `&r70`): `(OR ((&r14.component ... *Id) (&r21 (:Id Id))) ((&r27.component (:P P) (:Id Id)) ...))`. `&r56` is read by `OUT` on `XRel` and `Key` alone. If no case reads its `Id`, a different label in the second branch keeps the rows and exports no `Id`.
    - `e872b94a` `&r11` (first case; sampler-worker's `&r12`): `(OR ((&r3.component (:P *P) (:Id *Id))) ((&r7.component (:P P) (:Id Id))))`, which `&r12` counts as `Cardinality` members. This needs a rewrite or removal.
    - Dataset-worker must settle both before the flag turns on. A program that fails is refused. No explicit conversion exists, and I propose none.
- **Solvers.** `programs/solvers/` holds only `.dl` files (1,147), which have no Ident type. `programs/arclog/` holds 962 `.arclog` solvers, which the checker reads. The same forms fail there; step T5 lists them.
- **`scripts/materialize.py` and patches.** Patches correct task data under `data/`. Task data holds no Ident, so neither changes.
- **Stored banks.** A bank holds form text and `x_rows`. A pool that reads a bank replays the text, so banks keep working. `x_rows` in old records hold session numbers, which were never comparable across sessions.
- **Gold keys.** `gold_keys` (`work/lm/data-study/sampler/search-worker/poolsearch/superdag.py:347`) runs in each session, so nothing stored changes. The keys match as today, because the cell is by content.
- **`table_key`** (`superdag.py:79`, `superdag_search.py:224`). No change. It hashes integers, which Python hashes the same in every process, so with stable cells the merge key is the same in every process. That lifts the reason for the refusal at `superdag_search.py:632-633`, and keys may then carry over a new session. That change is separate.
- **State files.** `.bss` files are written per kit. A kit with a new engine starts new state. Their format does not change.
- **Memo keys.** `det_memo.rs` keys (`decode/det_memo.rs:271,369`) and the result cache read `rows_hash` over handles, in one process, so they stay right. Two makers of equal content now give two handles, so a DET that reads each misses the other's memo entry. Their contents differ, so the entries were rarely shared.
- **Features.** `t_Ident` and the `b4_pt_...` features read the plain type string, which stays. `featlib.Ident` compares values within a table. The cell's size changes from small to any `i32`, so step V2 greps for a numeric use of an Ident cell.
- **Study filters.** `study_filters/equality.rs` works up to a bijection of Idents, and stays right. Comments at `arclog-tables/src/columns.rs:37-41`, `featlib.py:852-858` and `pool_rows.py:41` must change.
- **Kit wheels.** A wheel from before the flag has no flag. Keys from two kits were never compared, and a kit pins one engine, so nothing mixes.

## Junk removed
Script: `junk_share.py` in this folder. Run: search-pool-context-steers-rest31-600s-c87cf482a. Sample: all 31 tasks of each arm, because the script takes 2 s. Kept nodes in records.

| Arm | Kept nodes | With an Ident column | Refused, positive join | Refused, under `NOT` | Share of Ident nodes | Share of all nodes |
| --- | --- | --- | --- | --- | --- | --- |
| context_nocover | 22,215 | 1,769 | 5 | 20 | 1.4% | 0.1% |
| context_cover | 26,932 | 2,402 | 11 | 10 | 0.9% | 0.1% |

- No node inherits a refusal from a clause it reads. No pool form holds a union of two sources or a type-parameter cross.
- By kind, nocover: `Quotient` with `Quotient` 9, `Connectivity` with `Connectivity` 8, `Connectivity` with `Quotient` 2, `Enclosure` with `Quotient` 2, `PanelCombine` with `Quotient` 2, and two of one each. Cover: 10 of the 11 positive nodes are `INIT` bodies that join `Connectivity` and `PanelCombine`.
- **Why the share is small.** A cross-source join on interned Idents gives rows only where two sets are equal, so it is nearly always empty, and an empty table is not kept. `NOT` over another source gives the left table back, which is an equal table, so it is not kept either. The junk is in draws, not in kept nodes.
- **Proposals.** Records hold no text for a draw that left no node, so the share of proposals can't be read. Bounds from the `done` files, as a share of draws: `try:empty` 14,517 of 94,433 and 13,076 of 84,429 (15%), `node:equal` 39,115 and 37,838 (41% and 45%). Cross-source draws are some part of these. Step P gives the number.
- **Predictions**, written at 2026-11-01T22:09:51Z before any reading (`prediction.txt`): 25% of kept Ident tables and 12% of gold programs. Results: 0.9% to 1.4%, and 0%. Both were wrong. I had not known that Idents are interned by content, which makes these joins empty.

## The change in steps
Each step names its check. Tests are banned, so the tiny programs are throwaway files. Type first, value after: the type alone meets the user's request, and it can ship before the value does.

The flag is an environment variable, `ARCLOG_IDENT_SOURCE`, read once as `ARCLOG_STATS` is at `arclog/src/stats.rs:51`. Unset: as today, every Ident is `Open`, and each cell is its session number. `type`: the type rules. `value`: the type rules and the value.

### Type
- **T1. Lattice.** `IdentSource`, `SourceId`, the `parent` and `join` arms, and each use the compiler lists. Check: flag unset, `check_one` on `tiny/cross` prints as today.
- **T2. Attach.** `instance_output`, `port_relation`, `clause_column`, behind the flag. Check: flag `type`, `tiny/cross` prints `Check(Types)` for `&cross` and for `&cross_not`.
- **T3. Unbound parameters.** The Ident check in `bound_faults`. Check: new tiny programs, one `(!= Id Id2)` over two makers, one `Quotient` with `a` and `b` of two makers, one `OR` that exports `Id` from two makers. Each prints a refusal. An `OR` of one maker in two branches prints none.
- **T4. Wire names.** Three sites print `Ident`. Check: `git grep -n '"Ident"' engine/arclog-tables` still reads what it read, and a table's `column_types` shows `Ident` under the flag.
- **T5. Gold.** Run `check_one` on all 962 stems with the flag `type`, and list each stem with a `Check(Types)` line. Expected: the stems of the union forms, and no other. ETA 6 minutes on one process, from 25 stems in 8.6 s. Also the same list through `verdicts` below, because that goes through the decoder.
- **T6. Admits.** Check with a Python session: at a site of `&b.component` `Id`, with an `Id` label of `&a` in scope, `dec.admits` gives false for the label. At a later `OR` branch the same.
- **T7. `joinable`.** The change at [Where the draw sees it](#where-the-draw-sees-it). Check: `search.dead:try:unjoined` per draw does not rise in step P.
- **T8. Docs.** `docs/arclog/arclog.md` (the `Ident` line at 17, and Disjunction), `docs/arclog/rigid.md:42`, `docs/engine/reader.md:30-31`, `docs/engine/equivariance.md:70,129`.
- **P. Pool.** Paired arms on the 6 tasks of `search-pool-context-steers-det6-600s-c87cf482a`, 600 s, flag `type` against unset, with `ADM_STATS=1` (`sample2_col.py:250`). Report the share of label options that the flag removes, draws per second, and table recall. ETA 12 minutes on a pod, after the wheel. My prediction: draws per second within 5%, recall within noise.

### Value
- **V1. Interning.** The digest in `InternTable` and `free_unheld`.
- **V2. Export.** `push_cells`, and a grep for a numeric use of an Ident cell in `model/study`.
- **V3. Gold, rows.** `verdicts` on every solver with the flag `value` against unset. The verdict lines must be equal, or each difference is explained. It is the check for the pooled joins across examples. ETA 30 to 60 minutes on 8 CPUs, an estimate. Hand this one back to run.
- **V4. Two processes.** The check below.
- **V5. Docs and comments.** `terms.rs:204-208,296-300,610-613`, `columns.rs:37-41`, `featlib.py:852-858`, `pool_rows.py:41`, `docs/engine/reader.md:30-31`.

### Check: equal content gives the same Ident in two processes
For 20 stems with a maker, in two processes with the flag `value`:
1. Process A: open a session, replay gold's forms, and write `{form index: sorted cells of each table}` as JSON.
2. Process B: open a session, first run an unrelated clause that interns other sets (for example a `Connectivity` on all cells, then a `Quotient` on colors), then do as A.
3. Compare the two files. They must be byte-equal.

Run once with `RAYON_NUM_THREADS=1` against the default, and once on macOS against a pod. The same check with the flag unset must show differences, or it tests nothing.

## Commands
- `<checkout>/scripts/run_heavy.py --cpus 8 --need soon cargo build --release -p arclog-cli` from `engine/`. ETA 5 to 15 minutes, an estimate. It gives `check_one` and `verdicts`.
- `ARCLOG_IDENT_SOURCE=type target/release/check_one <corpus> <stem>`. Under 1 s.
- `ARCLOG_IDENT_SOURCE=type target/release/verdicts programs/arclog data/tasks`. See V3 for the ETA.
- Wheel for a kit: `scripts/build_study_runtime.py` through `run_heavy.py`, into a new path, as for `kits/engine-c87cf482a/`. A job line sets the flag as it sets `STEER_COVER`.
- `python3 junk_share.py --arm context_nocover`, `python3 junk_share.py --arm context_cover`, `python3 gold_share.py`, in this folder. 2 s each. `ident_sources.py` holds the tracer. It reads `CHOOSE`, `RIGID_DET` and `DEMONSTRATED` forms as giving no source, so it can undercount in gold: 39 such forms, 34 reads.

## Migration
1. The flag stays off in the kits until dataset-worker's corpus has no union of two sources and T5 lists no stem.
2. Then a new kit runs with `ARCLOG_IDENT_SOURCE=type` in its job lines.
3. Then V1 to V4, and a kit with `value`.
4. When both hold, remove the flag and the `Open` default, other than for file-read Idents.

## Open choices
- **Join coin.** Default: decoder lookahead in `joinable`. The other way is a `column_sources` export and a source in `compat`. Take it only if step P shows a slowdown.
- **`Inclusion` and other components that compare a parameter across ports.** Default: the one rule of T3. A `Quotient` with `a` and `b` of two sources is then refused, which gold does not need.
- **The two unions in `67e490f4` and `e872b94a` (needs dataset-worker).** Default: refused, so they need a rewrite or removal.
