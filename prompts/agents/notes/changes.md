# Change notes
- The statements on carrying a change to the code or the documents from its worktree to a commit, that more than one entry point inlines or links.

## Changes
- A change is one editor's edit, and each edit that fixes what its review or its claims check found.
- A change to the code passes when its code editor's claims hold. A change to the documents passes when its doc review leaves no finding that you keep.
- Where you are the operator, have a triage agent do the judging and the deciding the next lines give.
- Judge each finding of a change's review against the change's worktree and [The ladder](prompts/agents/notes/decisions.md#the-ladder): keep it only where it is so, acting on it serves a rung, and no decision already made rules it out. Record each finding you drop, with its reason, in your reply.
- Send the findings you keep from a change's review, and the findings of its claims check, to the editor that made the change, and that editor's fixes to the reviewer that reviewed it, each with SendMessage. Launch a fresh reviewer only for a change's first review.
- Where the editor leaves a kept finding for a decision, decide the question it raises, from the reason the editor gives, as [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) gives, and send the editor the decision.
- Where you did not launch the editor, return the findings you keep and your decisions in your reply in place of sending them to it.
- In each message that sends a reviewer fixes, give what has been settled about the change since its brief, such as a power the user approved or a premise you checked.
    * comment: A doc reviewer re-reported in each of three rounds the powers the user had approved, and three times reported a gate output that the worktree does not produce.
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
