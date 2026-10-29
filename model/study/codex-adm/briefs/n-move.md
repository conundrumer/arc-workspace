You are the n-move owner in the LM data study. Read the plan first: model/study/plan.md, most of all Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study, the study's directory. Git ignores it, so its code has no history and its threads cannot get worktrees. M is your worktree of the repository, /Users/davidlu/code/arc-workspace/.claude/worktrees/study-move, on the branch study-move from master.

## Goal

The study's live code and documents tracked in the repository under M/lm/study/, while every data file stays in S. After the move, each study thread works in a worktree of its own made with scripts/change_worktree.py, and its changes land on master through scripts/merge_change.py. The running pipeline must work the same from the repository as it does from S today.

## Design direction

- Keep the study's directory layout under model/study/ (ast/run/, ast/run/mech/, ast/run/mech2/, judge3/, judgetool/, judge2/render2/, codex-adm/ and so on), so imports between the study's modules keep their shape.
- Code and data are separate. Today many modules find data next to themselves (`HERE / 'labels.sqlite3'`, `STUDY / 'ast/run/corpus-v11'`). After the move, data paths come from one data root, which is S found through the main worktree (`engine.checkout.main_worktree`), so that the same code works from the main tree and from any worktree. A path that names code stays relative to the module.
- The live code is what the current pipeline runs and imports: the corpus runner and the checks it uses, the labeler (mech) and its steps, mech2, judge3, judgetool, judge2/render2 as judge3 and judgetool import it, the codex-adm scripts (send.sh, newthread.sh, ends.py) with codex-adm's state files and log as data, health.sh, fault_status_diff.py, and the documents plan.md, duplicates.md and codex-adm/briefs/. Find the rest by following imports from those entry points. Diagnostic directories, old tracks and generated outputs stay in S untracked.
- reasons/ is outside the move: the user handles it.

## How it must go

- Other threads keep editing S while you work. Copy from S, and before you hand over, copy again every file of the moved set that changed in S after your first copy, with the same path changes.
- Check what can be checked without load: every moved module compiles and imports, and a read-only entry point (such as a --help) runs from M.
- The merge checks of scripts/merge_change.py apply to tracked .py files (uv run python -m controlled_markdown check reads code citations and paths). Make the moved code pass them.
- Do not commit. When the move is ready, end your turn with COORDINATOR: and the list of moved files, the data root, and what you checked; I run the merge.

## Rules

- Message owners with model/study/codex-adm/send.sh <owner> <request id> <text>, request ids from 7720000 upward. The owners are in S/codex-adm/owners.txt.
- Start your final answer with COORDINATOR: when you need the coordinator: a command your sandbox blocks (such as scripts/run_heavy.py), or a decision outside your area.
- Run no tests.
- When you stop, write your open items to S/codex-adm/handover-n-move.md.
