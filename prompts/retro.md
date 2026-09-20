# Retro briefs
- The brief each stage of the retro workflow sends its agent, one section per stage.

* comment
    - A section carries the name `retro.js` asks for, and the workflow fills its `{{variables}}` with the run's values.
    - A value that is a list is built by the script and arrives as one text value.
    - The sections under Partials are the runs of lines that more than one brief uses.

## read
- Read the retro window and return the issues.

## check
- Check these issues, all about {{group}}.
```json
{{issues}}
```

## review
- Review these open issues and their candidate fixes.
```json
{{open}}
```

## fix
- {{lead}}
```json
{{entries}}
```
- Write the diff of your changes to each file named above, verbatim, to that file's `diff_path`. Create the directory first.
- A file you changed that is not named above takes a diff of its own under `{{diff_dir}}/`, at a path you pick.
- Report one `diffs` entry per file you changed, the files named above and the others alike: the file, and the path its diff went to.

## fix-and-prune
* inline: #fix
- Work in two steps: the fix, under the fix role, then the prune, under the prune role, over the diff your fix made.
- The reader of each file, for the prune step:
```
{{readers}}
```
- {{ruled}}
- The prune step takes the edits above as the edits the diff was meant to make.
- Each file named above takes two diffs: the fix step writes its own diff to that file's `diff_path`, and the prune step writes the diff of its own pass to that file's `prune_path`.
- Run the verification command once over all the fix edits together, and once over all the prune edits together. It does not run per file.
- Report both steps. The `diffs` field carries one entry per file the run changed, each `path` that file's `prune_path`, since the prune step left the final state. The `notes` field carries one line per cut, and the meaning before and after of each rule the diff touches.

## verify
- Verify the changes to {{target}}.
```
{{groups}}
```
- {{others}}
- {{chain}}
- Write the diff of your own changes, verbatim, to {{verify_path}}, and report that path. A pass that changed nothing writes no file and reports an empty path.
- {{worktree_note}}

## merge
- Take the change in the worktree at {{worktree}} into the repo.
```
uv run python scripts/retro_merge.py {{command_arg}}
```
* inline: #one-call
- It prints `{"applied": ..., "files": [...], "conflict": ...}`. Return that object as your structured output, field for field, changing nothing in it.
- When the command fails, or prints nothing, return `applied` false, an empty `files`, and what went wrong in `conflict`.
- Run no other command. Change no file yourself, and never run a git command of your own.

## checks
- Run the checks over the current tree: the suite, the handbook build, and every solver of the corpus.
```
uv run python scripts/retro_checks.py
```
* inline: #one-call
- It prints `{"checks": [...]}`. Return that `checks` array, each entry as it stands.
- Report a failure as a failure. Do not attribute it to other work, and do not report it as passing.
* inline: #no-writes

## sweep
- Sweep the parameter values of these solvers.
```
mkdir -p .scratch/retro/sweep && uv run python scripts/run_dl.py sweep --open {{stems}}
```
* inline: #one-call
- A stem whose cached sweep is missing, or was made from other solver code, sweeps again, and that takes minutes.
- It prints `{"sweeps": [...], "skipped": [...]}`. Return that `sweeps` array, each entry as it stands.
- Change no file outside `.scratch/retro/sweep/`. Never run a git command that changes state.

## sweep-lines
- Write the sweep review lines into these solvers.
```
uv run python scripts/run_dl.py sweep --mark {{stems}}
```
* inline: #one-call
- It prints `{"solvers": [...], "skipped": [...]}`. Return that `solvers` array, each entry as it stands.
- Change no other file. Never run a git command that changes state.

## resolve
- Act on the review lines in programs/solvers/{{task_id}}.dl.
- Every review line in the solver's header names a point to act on, except a line whose kind marks it as waiting on the user; `cite` is such a kind today. Work each line per the procedure's operations, as they apply to it.
- Remove each line you finished. Leave a line you did not finish; when the solver carries no `// draft` line, return it to draft first: `uv run python -c "import sys; sys.path.insert(0, 'tools/console'); from solver_console import solvers; solvers.mark_draft('<task_id>'); solvers.withdraw_citations('<task_id>')"`. A review line whose kind waits on the user is not yours: leave it as it is.
* inline: #run-the-checks
- Write the diff of your change to the solver, verbatim, to {{diff_path}}, and report that path. A run that changed nothing writes no file and reports an empty path.
- Write your report, in the form the Review operation gives, to {{report_path}}. Create the directory first. The run, lint, and audit output go in your returned verification, not in the report.
* inline: #no-git

## group
- Group these review lines. Each entry names the solver the line stood in, the line, and a seed key from its text.
```json
{{lines}}
```

## consistency
- Compare these solvers, the group `{{group}}`, under the rule {{rule}}. Each entry names one solver, its report, and the review lines the Resolve stage acted on in it under that rule.
- Scratch goes under `{{scratch}}`.
```json
{{members}}
```

## apply
- Bring programs/solvers/{{task_id}}.dl to the form below, under the reading below.
```json
{{divergence}}
```
- The solvers this entry holds between read that point differently. The form above is the form they agree on.
- Change nothing the form does not reach. The model, the parameterization, and the Choice cases stay as they are.
* inline: #run-the-checks
- Write the diff of your change to the solver, verbatim, to {{diff_path}}, and report that path. A run that changed nothing writes no file and reports an empty path.
- Write your report, in the form the Review operation gives, to {{report_path}}. Create the directory first. The run, lint, and audit output go in your returned verification, not in the report.
- Report the point you brought the solver to in `acted`, as one entry, and what the form leaves unfinished in `left`.
* inline: #no-git

## cleanup
- Run Simplify, then Prune, over the whole of programs/solvers/{{task_id}}.dl.
- {{source}}
- Scratch goes under `.scratch/<task_id>/`.

## codex
- Run the brief below through Codex. It covers {{count}}: {{targets}}.
- Run this as one Bash call, in the foreground, with the Bash tool's `timeout` set to 600000. Copy the whole command, the brief between the two `RETRO_BRIEF` markers included, verbatim.
```
{{command}}
```
- It prints the JSON of the Codex session's final message. Return that JSON as your structured output, field for field, changing nothing in it.
- When the command fails, or prints nothing, return an empty `diffs`, an empty `verification`, an empty `review_lines`, and what went wrong in `notes`.
- Run no other command. Make none of the edits yourself, and change no file. Never run a git command that changes state.

## Partials

### one-call
- Run it as one Bash call, in the foreground, with the Bash tool's `timeout` set to 600000.

### no-git
- Never run a git command that changes state.

### no-writes
- Change no file. Never run a git command that changes state.

### run-the-checks
- Run the solver, the lint, and the audit.

### verify-group
- {{target}} — the edits its changes were meant to make:
```json
{{edits}}
```
- {{diffs}}

### verify-prose-diffs
- Its fix diff is under {{fix_path}}, and the diff of the prune over that fix is under {{prune_path}}.

### verify-code-diff
- Its diff is under {{diff_path}}.

### verify-others
- The fix also changed these files. They are in scope beside the target: fix what you find in them. Each entry names the file, then the diff of its change.
```
{{files}}
```

### verify-no-others
- The fix changed no file beside the target.

### verify-chain
- The other code targets of this run changed the same tree. Their diffs are under these paths:
```
{{paths}}
```

### verify-no-chain
- No other code target of this run changed the same tree.

### fix-and-prune-step
- The second step, over the diff your fix made:

### worktree
- You are in a git worktree of the repo, checked out at HEAD. It is a full tree of its own, and every path above is relative to its root.
- Work inside that tree and nowhere else: every read, every edit, and every command.
- Run each `uv run` command from the root of that tree. The first one builds that tree's own environment.
- A file you create is new to git, and a diff of the tracked files leaves it out. For each file you create, append the output of `git diff --no-index -- /dev/null <file>` to that file's diff.
- Report the absolute path of the worktree in `worktree`.

### worktree-verify
- The fix worked in a git worktree of the repo, at {{worktree}}. Every path above is relative to that tree's root.
- Work inside that tree and nowhere else: every read, every edit, and every command.
- Run each `uv run` command from {{worktree}}.
