# Change notes
- The statements on carrying a change to the code or the documents from who writes it to its commit, that more than one entry point inlines or links.

## Changes

### Carrying a change
- Have an editor write each change to the code or the documents.
- A change is one editor's edit, and each edit that fixes what its review or its checks found.
- A change passes when each code editor that worked on it reports done or blocked, when no item its editors report done needs an item they report unfinished, and, where it changes the documents, the `///` and `//!` comments of [lib.dl](programs/lib.dl) and of the modules under [lib](programs/lib) among them, when a reply of the doc reviewer that follows the last edit of those changes says no finding stands and `uv run python -m controlled_markdown check` passes in its worktree.
- Send the findings of a change's checks to the editor that made the change, with SendMessage. A change's reviewer sends its findings to the change's editors, and each editor sends its fixes to that reviewer: relay none of them. Launch a fresh reviewer only for a change's first review.
- Where the `controlled_markdown` check reports a `quotes` call that a change to the documents broke, send that finding to a code editor in place of the doc editor: launch one in the change's worktree, with each call the check reports as an item, to repair as [Prose in code](src/controlled_markdown/writing.md#prose-in-code) gives, and the files of those calls as the files it may edit.
- Where a doc reviewer's reply gives a finding outside its `Held back` heading, launch an editor in the change's worktree, and send its agent id to that reviewer with SendMessage. For a finding on a line of the document set or on one of those comments, launch a doc editor, with an Intent that says what that line's readers need to know, taken from the items of the change's briefs. For a finding on prose in code, launch a code editor, with the correction of the finding's line as its item and the finding's file as the file it may edit.
- Launch the first editor of a change with the Agent tool's `isolation: "worktree"`, and take the change's worktree from the Agent tool's completion notification for that editor.
    - The harness removes that worktree, with its untracked files, when that editor ends a turn with no change to a tracked file. Launch the editor that continues such a change as a new first editor, and send no editor to a worktree you add yourself.
        * comment: A code editor whose first worktree was removed after a turn with no edit had no worktree to continue in, and its notes under `.scratch/` were gone: ticket `1791209231-worktree-cleanup-operator-1`. The operator then sent that editor to a worktree it added with `git worktree add`, and the permission classifier refused the editor's edits to [src](src) and [scripts](scripts) there: ticket `1791209668-classifier-refusal-operator-1`.
- Give that worktree, by its path, in the brief of each later agent that works on the change.
- Run the changes you launch at the same time.

### Findings an editor leaves
- Judge each finding a change's editor leaves with a reason against the change's worktree, that reason, and [The ladder](prompts/agents/notes/decisions.md#the-ladder): keep it only where it is so, acting on it serves a rung, and no decision already made rules it out. Record each finding you drop, with its reason, in your reply, and send the editor each you drop, as dropped, and each you keep that needs no decision, as kept, each with your reason.
- Where the editor leaves a finding, or an item unfinished, for a decision, decide the question it raises, from the reason the editor gives, as [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) gives, and send the editor the decision.

### Merging a change
- Where a kept finding of a change raises a decision that goes to the user, leave that change unmerged, and give its branch and worktree with that decision in your reply. The session that gets the user's ruling, or carries out that decision's default, merges the change.
- Before you merge a change, read the diff of each accepted gate output its briefs list, and send each difference there that those briefs do not ask for to the change's editor as a finding of its checks.
- Merge a change only once it passes, with `uv run python scripts/merge_change.py <worktree> -m <message>`, and commit in no other way.
- Where that script exits with status 1, leave the worktree as it is. Where it reports that the rebase conflicts, run the change again with a new first editor, and give the old worktree and its branch in your reply. Where it reports a failed check, send what it reports to the change's editor as a finding of its checks. Otherwise, give the worktree and the script's message in your reply.
    - Where the failed check is the gate, give in that finding, for each `DIFF` line that the change's briefs ask for, the accepted output under `tests/gate/accepted/` to update.

## worktree
- The worktree of the change you work on is the one the message that launches you gives, or, where it gives none, your working directory at start. Run each command in it, and take each path in the repo from it, apart from a path under `tickets/`, which you take from the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints.
- A later message may add a request to the change, in the form your brief gives one, and that request is part of what the change is to do.

## worktree-isolation
- The harness may refuse a compound Bash command that it cannot verify runs git only inside the worktree, such as one that writes a file through a heredoc, runs `printf` with a computed format, or runs git inside a command substitution. Write such a file with the Write or Edit tool, run such a git call as a simple command in a Bash call of its own, and run the rest of the command in a Bash call of its own.
    * comment: The refusal message reaches an agent only after the refused call. Without this line, code editor `a16cb9e50afdd6691` had five such commands refused and retried each split: ticket `1791218737-a16cb9e50afdd6691-transcript-review-3`. With only the heredoc and `printf` forms named, doc editor `a0c48e5b4d30194d1` had a command with git inside a command substitution refused and split it: ticket `1791220161-a0c48e5b4d30194d1-transcript-review-1`. The forms after "such as" stay because a reader cannot tell from the condition alone which commands the harness cannot verify.

## budget
- Do each step your documents give, and finish the work, even where it runs past the budget a `Budget: N minutes` line of your brief or a later message gives.

## gate
- `uv run python scripts/gate.py --outputs-only <out-dir> [cmd ...]` is the gate: it runs the gate commands it is given on the fixed inputs under `tests/gate/` that `gate.py --help` lists, and compares their outputs with the accepted ones.
- Run it only to write the accepted gate outputs your brief lists and those a finding of your checks gives to update, with the commands whose outputs those are as `cmd` and a new directory under `.scratch/` in the worktree as `<out-dir>`.
- Copy each of those outputs from `<out-dir>/gate/new/` to its accepted file under `tests/gate/accepted/`, and run no `gate.py --accept`.
