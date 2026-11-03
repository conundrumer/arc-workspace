# Proposer mask and admission count

Two settings for the joint kit (`search-joint-r1-kit-0729e4943`). Each setting is off when it is unset, and then the kit does what it did before.

## Settings

| Setting | Effect |
|---|---|
| `PROPOSER_MASK=1` | A DET clause is not offered a proposer that has no live value on the task. |
| `ADMISSION_COUNT=1` | `Run.form` counts each DET that DET admission refuses, as `admission:DET <reason> <where>`. It changes no draw. |
| `ADMISSION_RETEST=1` | With `ADMISSION_COUNT=1`: for a DET that reads fewer forms than the scope holds, it also steps the DET over the forms it reads alone. The count name then ends in `closure admits` or `closure refused: <reason>`. |
| `ALL_COUNTS=1` | `kaggle_worker.py` prints one `all counts` line at the end: every numeric count of the pool's Run, with the `search.` and `sr:` keys. It changes nothing else. |

### What `PROPOSER_MASK=1` does

1. `live.dead_proposers(session, task)` steps DET, one proposer and END on a fork of an empty decoder, for each proposer that the decoder admits after DET. This is the step that `Run.proposed` makes. A refusal that names `DetAdmission` marks the proposer dead. The answer is kept for the task and the session settings, so the probe runs once for each task in a process (0.011 s on c4d067a0).
2. `kaggle_worker.py` calls it right after the session is made, and prints `proposer mask: <n> dead proposers in <s> s: <names>`. A Run that finds no answer makes it at its first DET proposal.
3. `Run.proposed(pg, f, 'DET')` takes the dead proposers out of the names that it offers. It keeps the other proposers in their order and with their prior counts, so their relative weights do not change. The search tree has fewer options at that choice. A RULE clause (`Run.rule`) still gets all proposers.
4. `search.fingerprint()` adds `PROPOSER_MASK` when the setting is on, because the ranks of a saved path name other options under the mask. A saved search state of one setting does not load under the other.
5. `Run.c` counts `mask:DET proposals` (the DET proposals made under the mask) and `mask:DET proposers removed` (the dead proposers that those proposals did not offer). The worker log shows them as `sr:mask:...`.

The probe reads no form, no atom order and no atom index. It runs on the empty program, so it does not depend on how the scope's forms are written or ordered.

A proposer is masked for a DET clause only. Gold has no case where the mask would remove a proposer that gold needs (see Gold guard).

### What `ADMISSION_COUNT=1` does

When a DET clause is refused with `DetAdmission`, `Run.form` adds 1 to `admission:DET <reason> <where>` before it adds to the `form:` count. `<where>` is one of:

- `proposer`: the DET reads no form.
- `reads no form`: the body reads no relation of the scope.
- `no DET outside its reads`: every DET form of the scope is in the DET's read-closure.
- `DETs outside its reads`: some DET form of the scope is outside it.

The key `admission:...` is not in `REJECTS`, so it ends no search path. The worker prints it as `sr:admission:...`. `admission-count.patch` holds this part alone.

## Apply

From the kit's top folder:

```
patch -p1 < proposer-mask.patch
```

The patch changes `model/study/sampler/live.py`, `search.py` and `kaggle_worker.py`. `admission-count.patch` changes `live.py` only, and applies to the unpatched kit. It does not apply on top of `proposer-mask.patch`. Both patches pass `patch -p1 --dry-run` on the kit.

A job sets the setting in its environment, like the other settings of a job line, for example `PROPOSER_MASK=1 ADMISSION_COUNT=1 ... ./run3600.sh <task> <name> models-tk 600`.

## Gold guard

Question: does a gold DET name a proposer that the empty-program probe marks dead on that task? Such a form would be impossible under the mask.

`gold_guard.py` runs the probe on every task in `points-eval.json`, `points-round50.json`, `points-n600.json` and `points-cheapest.json` that has a gold form which names a proposer (141 tasks, all with a task file). It runs on the Mac engine. Output: `out/gold_guard.out`, one JSON line for each task.

- Gold DET forms that name a dead proposer: **0.** The gold DETs that name a proposer have the shape `(DET &x Proposer)`. No gold line has a `(SET`.
- Two gold RULE forms name a dead proposer: `(RULE &r1 DominantColor)` on 7ec998c9 (`points-n600.json`) and `(RULE &r24 DominantColor)` on c35c1b4c (`points-eval.json`). The mask does not act on a RULE clause, so these stay possible.
- On aa4ec2a5, gold names AnyOutNewColor and DominantColor in DETs. The probe finds both live there.

So the mask uses the empty-program verdict alone. If a later gold has a DET that names a proposer that the probe marks dead, rerun `gold_guard.py`:

```
PYTHONPATH=<arclog path> ARCLOG_IDENT_SOURCE=value <python> gold_guard.py <kit> [task ...]
```

## Check

Engine: the Mac build (`<python>` is `.../runtime-kaggle-py313/venv/bin/python`, `EXTRA_PATH` is `.../ident-impl/macsite`, `ARCLOG_IDENT_SOURCE=value`). `run_direct.sh KIT OUTDIR TASK SECONDS SEED` runs one direct worker with the joint arm's settings (SEARCH_SCOPE_RULE=scope/joint.py, models-tk, `P_DAG=1`, `ORDER_FREE=tie,key`, seed 0).

### Check 1: setting unset

A direct worker of 14 s on c4d067a0, the unpatched kit against the patched kit with `PROPOSER_MASK` unset (`out/base14`, `out/unset14`; result in `out/check1_unset14.txt`):

- The `.picks` lines are equal: 7 picks, at the same draw counts (0, 75, 103, 178, 186, 194, 204) and with the same nodes.
- The visits are equal for the first 6 of 7. The last visit is the one that the 14 s end cuts: 85 tries against 86.
- The workers end at a wall-clock time. The unpatched worker ended at 289 draws, the patched worker at 290.

### Mask on, 14 s

c4d067a0, 14 s, seed 0, with `ADMISSION_COUNT=1 ALL_COUNTS=1` (`out/off14`, `out/mask14`; result in `out/compare14_mask.txt`):

| | mask off | mask on |
|---|---|---|
| dead proposers found | | 11 (AnyOutNewColor ChangedColor DimDiff DominantColor OutNewColor Period RarestColor SepThickness SepTileCount SepTileDim VanishedColor) in 0.011 s |
| `search.dead:form:DET refused: DetAdmission` | 8 | 0 |
| `sr:admission:DET NoLiveAssignment proposer` | 8 | 0 |
| draws | 283 | 291 |
| picks | 7 | 7, equal to the 7 of mask off |

### Check 2: 120 s, two tasks

The four runs take about 2 min 10 s each, one at a time, so about 9 min in all. Run each command in its own call. `R` is this folder, `PY` and `EXTRA_PATH` are as above.

```
R=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/proposer-mask
PY=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python
EXTRA_PATH=/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/ident-impl/macsite

ADMISSION_COUNT=1 ALL_COUNTS=1 PY=$PY EXTRA_PATH=$EXTRA_PATH /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need now bash $R/run_direct.sh $R/kit-patched $R/out/off120_c4d067a0 c4d067a0 120 0
ADMISSION_COUNT=1 ALL_COUNTS=1 PROPOSER_MASK=1 PY=$PY EXTRA_PATH=$EXTRA_PATH /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need now bash $R/run_direct.sh $R/kit-patched $R/out/on120_c4d067a0 c4d067a0 120 0
ADMISSION_COUNT=1 ALL_COUNTS=1 PY=$PY EXTRA_PATH=$EXTRA_PATH /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need now bash $R/run_direct.sh $R/kit-patched $R/out/off120_dd6b8c4b dd6b8c4b 120 0
ADMISSION_COUNT=1 ALL_COUNTS=1 PROPOSER_MASK=1 PY=$PY EXTRA_PATH=$EXTRA_PATH /Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need now bash $R/run_direct.sh $R/kit-patched $R/out/on120_dd6b8c4b dd6b8c4b 120 0
```

Then, for each task:

```
python3 $R/compare.py c4d067a0 $R/out/off120_c4d067a0 $R/out/on120_c4d067a0 > $R/out/compare120_c4d067a0.txt
python3 $R/compare.py dd6b8c4b $R/out/off120_dd6b8c4b $R/out/on120_dd6b8c4b > $R/out/compare120_dd6b8c4b.txt
```

`compare.py` prints the DET admission count, the mask counts, the draws and whether the picks are equal. The clauses drawn differ between the arms, so a pick that reads a drawn clause can differ too.

## Files

- `proposer-mask.patch`: the mask, the admission count, `ALL_COUNTS`, and the fingerprint line.
- `admission-count.patch`: the admission count alone, against the unpatched kit.
- `kit-patched/`: a copy of the kit with `proposer-mask.patch` applied. `run_direct.sh` runs it.
- `gold_guard.py`, `out/gold_guard.out`: the gold guard.
- `run_direct.sh`, `compare.py`, `check1.py`: the check scripts.
- `make_admission_only.py`, `admission-only/`: the make of `admission-count.patch`.
- `out/`: the outputs of the runs.

## Check 2 result

120 s, seed 0, mask off against on:

| Task | DET admission refusals, off | DET admission refusals, on | Dead proposer options removed |
| --- | --- | --- | --- |
| dd6b8c4b | 23, all `NoLiveAssignment` of a proposer | 0 | 770 over 77 DET proposals |
| c4d067a0 | 0 (no DET visit in that run) | 0 | 605 over 55 DET proposals |

The first scope picks are equal. Later picks differ, because the masked run spends no draws on dead proposers, so the draw counts and the clauses drawn shift.

