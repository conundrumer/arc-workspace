# DET admission and the scope: answers

**Question 1: No.** With no engine change, the decoder's context is the program that admission reads. The binding opens only an empty decoder (`Session.decoder()`), and a decoder gets its forms only by `step`. Each DET form that is stepped runs admission over every DET before it. So a scope whose own DETs fail admission together (the whole pool) cannot be context for any clause. For a scope whose DETs pass together (the policy's scopes), a second decoder over the clause's read-closure can admit the clause. But the step P run shows no try lost to DETs outside the read-closure in such scopes (question 4), so that split costs time and gains no try.

Engine source: `engine/arclog/src/decode/det_admission.rs`, `engine/arclog/src/judge/determination.rs`, `engine/arclog/src/decode/state.rs`, `engine/arclog/src/decode/mod.rs`. Binding: `engine/arclog-bindings/src/decoder.rs`, `session.rs`, `study.rs` (`engine/arclog-py/src/lib.rs` only registers them). Kit: `model/study/sampler/live.py`, `search.py`, `superdag_search.py` in `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/joint/search-joint-r1-kit-0729e4943/`.

## 1. Scope as context, admission over the read-closure

### How the search builds its decoder

1. `Run.scope(forms)` (live.py:739) joins the scope texts, gets the token stream from `StudyProgram.from_sexp(...).decode_stream()`, and steps each model token into a fork of `session.decoder()`. After each form it calls `Run.close`, which calls `step_tables` for the form's relation tables.
2. `Run.scoped` keeps the last scope's decoder. A Search replays its scope once for each run object. A run that the Manager makes again replays it again.
3. `Search.execute` (search.py:678) calls `run.scope`, then `run.form(pg, dec, kind)`, which draws the clause on a fork of that decoder.
4. For a DET, `Run.det` (live.py:912) draws a proposer (`Run.proposed`: DET, proposer, END) or a body (`Run.body`, then `Run.end`, which steps END).
5. `try_clause` (superdag_search.py:439) gives `clause.decoder` and `clause.pg` to `Pool.take` and `Pool.test`. These read the decoder that holds the scope and the clause: its tables, and the OUT candidates over it.

### What the decoder needs from the scope to propose a clause

- **Relations:** the relation slot tokens that the scope declares (`pg.made`, `pg.ndecl`). A slot is the relation's place among the scope's declarations, so a token of one decoder means nothing in a decoder of other forms.
- **Columns and types:** `pg.decl_types` and `pg.decl_slots` from `step_tables` at each form end, and `pg.colmaps` from `column_positions` on the decoder.
- **Tables:** `body_table` and `step_tables` of each body prefix, evaluated over the scope relations that the prefix reads.
- **Checks:** the atom checks of the mask (types, static prune, atom head), over the resolved finished forms.
- **Labels:** the clause's own. The scope gives none.
- **For OUT:** `scope_partners` reads the scope relations' tables.

### What admission reads

`Decoder::next` calls `admit_written_dets` (mod.rs:613) after each END, SET or ONE token where the state closes a DET or a RIGID_DET. Then `det_liveness` reads:

- the checked program of all finished forms with the closed DET (`finished_checked`),
- `written_dets(program)`: every DET of the program, read by the clause or not,
- the domain of each DET at each assignment, and the models of each pick, on the task in the session,
- the assignment cap (256) and the table work cap.

The other walks of a decode read the read-closure only. The rows and tables of a clause in progress use `walked_dets` and `relation_dets` (interface.rs:781, 789). The OUT determination uses `dets_read(case.program, output.node)` (determination.rs:308). Admission is the only walk over all DETs.

### Why the split is no full answer

- **The scope:** stepping a scope DET runs admission over the forms before it. The context decoder can hold no DET set that fails together. `scope/whole.py` already bisects for the largest DET prefix that passes (105 of 290 DET forms in the probe log).
- **The clause:** a split is possible for a scope that passes.
  1. Draw the clause on the full-scope decoder.
  2. Find the scope forms that the clause tokens read, at any depth.
  3. Replay those forms into a new decoder, remap the relation tokens of the clause, step them, and step END there.
  4. Build the Clause from that decoder, with a `pg` and a scope length for the closure. `take` and `test` read slot numbers through `pg`.
  5. Do the same at each `can_end` check of a DET body (live.py:1311, 1402, 1441). Each check steps END on the full-scope decoder, so it runs admission over the full program too.
- **Cost:** `closure_verdict` in the patch below does steps 2 and 3. On the whole-pool bank it took 7 ms for a 4-form closure in a warm session. In the step P run, a try costs 14 to 30 ms (`search.seconds` / `search.runs`: 94 s / 6,244 to 359 s / 11,940). A scope replay with tables costs 37 to 73 ms (`sr:scope_seconds` / `search:new scope`). So the split adds one closure replay per distinct read set and a token replay per DET end check. That is a large part of a try, for 0 tries gained in the step P scopes.

## 2. The engine change

**A fact for the user.** In `Decoder::det_liveness` (det_admission.rs:58), admission walks every DET of the program (`written_dets(program)`, `held_dets(program)`). The change: walk the DETs that the closed DET reads at any depth.

1. Take the closed form's node as root: `derived_at(program, &NodePath::top(last))` (interface.rs:766). For a RIGID_DET, take each relation that the form derives. Today the root is `written.last()`, the last DET in dependency order, which names only the form of a stop.
2. Set `written = dets_read(program, root)` (determination.rs:221). This includes the root.
3. Set `dets` to the non-pick DETs of `written`, and `picks` to the picks of `written`.

With this change, admission walks the same DETs as the walks of `walked_dets`, `relation_dets` and the determination. The cap stays 256.

**What else reads the full program at that point:**

- `finished_checked`: the static check of the whole program. It must stay.
- `independent_parts` and `verdict_past_cap`: these read `written`. The closed DET reads every DET of its closure, so the closure is always one part, and the joint walk decides. The part rule then has no effect on admission.
- `cached_det_prefix`: keyed by the closed form, in a cache that `State::finish_form` clears at each finished form. Its key stays correct.
- `held_dets(full program)` in `check/held_det.rs` and `study/render_choices.rs`: admission does not use these, so the change leaves them as they are.

**What the change breaks or moves:**

- **The refusal moves to the OUT test.** Some programs pass that are refused today. In such a program a DET D is live over its closure, but the part that D shares with a sibling is past the cap or has no live leaf. Each pass of D's END then admits D. An OUT that reads both D and that sibling walks that part at the determination, and gets `CaseOutcome::Stopped` at the cap or `Unsolved`. The search loses the early prune for such pairs, and the cap still holds for every OUT.
- **No joint liveness.** A program's DETs have a live assignment together only along each OUT's closure. No code that I read needs more.
- **Order.** Today a scope DET's verdict depends on which DETs come before it in the scope. With the change, the verdict depends on the DET's closure alone, so a pool DET passes in any scope that holds its closure.
- **Tests.** The DET admission tests in `engine/arclog/tests/integration/decode_interface.rs` (lines 210 to 345) each use one DET, or a DET with the forms it reads. None needs an unread DET to be walked.
- **Docs.** The doc comment of `Refusal::DetAdmission` ("The written DETs have no complete live assignment") and the comments of `verdict_past_cap` must be changed.

**Context, not program:** a decoder that takes forms as context only needs a new constructor, a state that holds context forms, and an admission filter. It gives the same scope setup as the change above. But the clause's own admission would still walk the context siblings in its part unless the closure rule also applies. So the read-closure change is the smaller one.

## 3. When admission runs, and why the whole-pool scope was refused

**During a scope setup:** at the END of each scope DET form, and at SET or ONE of a DET in its marks stage. The program is every form before it, with that DET. The memo of each part's walk is in the session (`ProbeMemo`, keyed by `part_key`, for an acyclic program).

**During a clause:** only when the clause is a DET or a RIGID_DET. Admission runs at each `can_end` check, which is `forced(END)` on an atom try (a refusal counts `try:unsafe`, `or:unsafe` or `all:unsafe`). It also runs at the END in `Run.end` (a refusal counts `form:DET refused: ...`). A RULE or INIT clause runs no admission.

**Why the whole-pool scope was refused: a part past the cap.** The probe is `whole_probe.py`, run on the bank `scratchpad/whole/probe-work/whole/135a2760.out.jsonl.bank`, in 2.2 s. Its output:

1. The bank has 2,143 forms and 290 DETs, in scope order (depth, then form id). The replay is refused at form 443, DET `&f209`, with `DetAdmission(Bound(Assignments { cap: 256 }))`.
2. `&f209` with its ancestors is 4 forms and 3 DETs. That program passes.
3. `&f209`'s part among the DETs before it has 15 DETs, 12 of them outside `&f209`'s read-closure. The part has five proposer roots: `&f28` AxisDomain, `&f29` SharedColor, `&f31` UnchangedColor, `&f34` TileCount and `&f36` ColorDomain. It also has 10 depth-2 DETs, and 9 of those read `&f36`. The 15 DETs with their ancestors are 17 forms and one part. That program is refused with `Bound(Assignments { cap: 256 })`. In one part, that refusal comes from the joint walk, so the part has more than 256 leaves.
4. The forms before `&f209` without that part, with `&f209`'s closure, are 350 forms and 112 DETs. That program passes.

So siblings that share a root DET join one part, and the leaves of that part multiply past 256. No part with no live leaf is needed to explain the refusal. A part with no live leaf among several parts would give the same label (`verdict_past_cap` gives `Bound(Assignments)` for it when the product of the parts' leaves is past the cap). Step 3 rules that case out here, because the part alone is refused.

## 4. Step P refusals outside the read-closure

Run: `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-ident-type-6tasks-600s-e8c1b7882/out/`, last `all counts` line of each task log.

| arm | tasks | `search.dead:form:DET refused: DetAdmission` | reason in `sr:` keys | `search.runs` | seconds of those deaths |
|---|---|---|---|---|---|
| off | 5 (dd6b8c4b has no such key) | 854 | NoLiveAssignment 853 | 55,212 | 4.7 |
| type | 6 | 747 | NoLiveAssignment 742 | 51,068 | 4.8 |

The `sr:` keys show no other reason. No `Bound(Assignments)` appears.

**Lost to DETs outside the read-closure: 0 of 854 and 0 of 747.** The records give the reason but not the DET. These facts give the DET:

1. A body DET's END is checked by `can_end` at its last atom, an OR or an ALL before `Run.end` steps it (live.py:1311, 1402, 1441). The check runs the same admission on the same state. A body DET that admission refuses therefore ends as `try:unsafe`, `or:unsafe` or `all:unsafe`. `search.dead:try:unsafe` is 0 to 11 for each task.
2. `Run.proposed` (live.py:901) steps the proposer and END with no such check. So `form:DET refused: DetAdmission` comes from proposer DETs.
3. A proposer DET reads no form. Its read-closure is the DET alone, and it is its own part.
4. The scope replay admitted the scope's DETs, so each scope part is live. If the DET's own part has no live leaf, the verdict is `NoLiveAssignment` (or the `Bound` label when the product of the parts' leaves is past 256). Otherwise the verdict passes. So the verdict depends on the DET alone.
5. The probe `proposer_probe.py` steps DET, proposer, END on an empty program. On each of the six tasks, it finds 8 to 11 proposers with `DetAdmission(NoLiveAssignment)`. AnyOutNewColor, DimDiff, OutNewColor, Period, SepThickness, SepTileCount and SepTileDim are refused on all six tasks. The test `det_admission_refuses_an_empty_proposer_domain_and_allows_its_empty_set_value` gives this behavior for UnchangedColor.

These tries are lost to proposers that have no live value on the task, which is 1.5% of the runs in each arm. A proposer's verdict on the empty program is the same for every scope. The check of all 42 proposers took 0.01 to 0.04 s for each task.

### The counted log line

**The patch:** `admission_count.patch`, against the kit's `live.py`. The patched copy is `patched/live.py`. It changes no draw and no pick.

- `Run.form` takes the body tokens of a refused DET before it puts `pg` back. If the refusal is `DetAdmission`, it adds 1 to `admission:DET <reason> <where>`. This count comes before the `form:` count, which ends the search path. The `admission:` key is not in `REJECTS`.
- `<where>` is one of these:
  - `proposer`: the DET reads no form.
  - `reads no form`: a body that reads no relation of the scope.
  - `no DET outside its reads`: every DET form of the scope is in the DET's read-closure.
  - `DETs outside its reads`: some DET form of the scope is outside it.
- With `ADMISSION_RETEST=1`, the last case gets `, closure admits` or `, closure refused: <reason>`, from `Run.closure_verdict`. That function replays the read-closure into a new decoder of the session, remaps the relation tokens, and steps the DET. `admission:retest seconds` counts its time. **`closure admits` is the count of tries lost to DETs outside the read-closure.** A `Grammar` reason is a replay that did not take a token.
- The worker prints the counts as `sr:admission:...` in its `all counts` lines.
- **Check:** `retest_check.py` gives the patch the scope of the forms before `&f209` and `&f209`'s body tokens. With that scope, `&f209` is refused with `Bound(Assignments)`. The count name is `admission:DET Bound DETs outside its reads, closure admits`, and the retest took 7 ms.
- **Assumption:** `Run.body` keeps the stepped model tokens in `pg.toks`, and a token that the engine emitted is passed over where the drawn tokens hold it. A `Grammar` count shows a replay where this assumption fails.

## Files

All are in `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/admission/`:

- `answers.md`: this file.
- `whole_probe.py`: the probe of question 3.
- `proposer_probe.py`: the probe of question 4.
- `proposer_probe.out`: the output of `proposer_probe.py`.
- `admission_count.patch`: the counted log line.
- `patched/live.py`: the kit's `live.py` with that patch.
- `retest_check.py`: the check of that patch.

**Caveat:** the probes ran on the Mac engine in `scratchpad/ident-impl/macsite`. With that build, four proposers on c4d067a0 give `Bound(TableWork)`. The repo's `det_liveness` maps a `TableWork` stop of the walk to a pass, so that build may differ from the repo source there. The step P logs show no `TableWork` refusal.
