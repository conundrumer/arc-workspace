# Change notes
- The statements on carrying a change to the code or the documents from who writes it to its commit, that more than one entry point inlines or links.

## Changes
- Have an editor write each change to the code or the documents.
- A change is one editor's edit, and each edit that fixes what its review or its checks found.
- A change passes when the claims of each code editor that worked on it hold, and, where it changes the documents, when its doc review leaves no finding that you keep and `uv run python -m controlled_markdown check` passes in its worktree.
- Where you are the operator, have a triage agent do the judging and the deciding the next lines give.
- Judge each finding of a change's review against the change's worktree and [The ladder](prompts/agents/notes/decisions.md#the-ladder): keep it only where it is so, acting on it serves a rung, and no decision already made rules it out. Record each finding you drop, with its reason, in your reply.
- Send the findings you keep from a change's review, and the findings of its checks, to the editor that made the change, and that editor's fixes to the reviewer that reviewed it, each with SendMessage. Launch a fresh reviewer only for a change's first review.
- Where the editor leaves a kept finding for a decision, decide the question it raises, from the reason the editor gives, as [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) gives, and send the editor the decision.
- Where the `controlled_markdown` check reports a `quotes` call that a change to the documents broke, send that finding to a code editor in place of the doc editor: launch one in the change's worktree, with §D5 of `~/.claude/plans/typed-crunching-teapot.md` as its spec section, each call the check reports as an item, and the files of those calls as the files it may edit.
- Where you did not launch the editor, return the findings you keep and your decisions in your reply in place of sending them to it.
- In each message that sends a reviewer fixes, give what has been settled about the change since its brief, and each request the user added to the change since its brief.
- Before you launch the first editor of a change, add a worktree for it on a branch of its own, with `git worktree add -b <branch> <path>`, at a path outside the main tree.
- Give that worktree in the brief of each agent that works on the change.
- Run the changes you launch at the same time, each in its own worktree.
- Where a kept finding of a change raises a decision that goes to the user, leave that change uncommitted, and give its branch and worktree with that decision in your reply. The session that gets the user's ruling, or carries out that decision's default, commits the change.
- Commit a change only once it passes, in these steps:
    1. Commit it on its branch, new files included, in its worktree.
    2. Rebase its branch onto `master`. Where the rebase conflicts, abort it, remove the worktree, and run the change again in a new worktree.
    3. In the main tree, fast-forward `master` to the branch with `git merge --ff-only <branch>`.
        - Where git refuses the fast-forward, stop there: leave `master`, the branch and its worktree as they are, and give the branch and git's message in your reply.
    4. Run `uv run python scripts/context.py --write` in the main tree.
    5. Remove the worktree with `git worktree remove <path>`.

## worktree
- The message that launches you gives the worktree of the change you work on. Run each command in it, and take each path in the repo from it.
- A later message may add a request to the change, in the form your brief gives one, and that request is part of what the change is to do.
