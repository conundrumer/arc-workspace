# Change notes
- The statements on carrying a change to the code or the documents from its worktree to a commit, that more than one entry point inlines or links.

* comment: When editing this doc, keep a statement here when more than one entry point inlines or links it.

## Changes
- A change is one editor's edit, and each edit that fixes what its review or its claims check found.
- A change to the code passes when its code editor's claims hold. A change to the documents passes when a doc review finds nothing left in it that needs no decision.
- Send the findings of a change's review or claims check to the editor that made the change, and that editor's fixes to the reviewer that reviewed it, each with SendMessage. Launch a fresh reviewer only for a change's first review.
- Before you launch the first editor of a change, add a worktree for it on a branch of its own, with `git worktree add -b <branch> <path>`, at a path outside the main tree.
- Give that worktree in the brief of each agent that works on the change.
- Run the changes you launch at the same time, each in its own worktree.
- Commit a change only once it passes, in these steps:
    1. Commit it on its branch, new files included, in its worktree.
    2. Rebase its branch onto `master`. Where the rebase conflicts, abort it, remove the worktree, and run the change again in a new worktree.
    3. In the main tree, fast-forward `master` to the branch with `git merge --ff-only <branch>`.
    4. Run `uv run python scripts/context.py --write` in the main tree.
    5. Remove the worktree with `git worktree remove <path>`.

## worktree
- The message that launches you gives the worktree of the change you work on. Run each command in it, and take each path in the repo from it.
