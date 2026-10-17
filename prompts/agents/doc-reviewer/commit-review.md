+ budget: 1842
* comment: when editing this doc
    - The doc reviewer receives this document from the step command at the start of its run, before it reviews.
    - Acts, each with its section:
        - Reviewing a merged commit or a standing doc review, and filing its findings: [A review of a commit](#a-review-of-a-commit).

# A review of a commit
- In a review of a commit of `master` that the coordinator merged, the change is that commit's diff, and the commit before it is the commit that `contexts --diff` and `context --diff` take.
- A standing doc review is recorded by the tag your brief gives, which `git tag -f <tag> <hash>`, with the commit's hash your brief gives, sets.
- A standing doc review has no change. In its place, read the context `uv run python scripts/context.py context --at <hash> <reader> [args]` prints, from its entry point to its end, with each section that reader reaches by links, by the steps [Reviewing a change](docs/handbook/editing.md#reviewing-a-change) gives for reading a context, other than the steps that read the listing `contexts --diff` prints. The reader reaches the target of each link of that context, and of each section it reaches, where that link leads it there by the rule [Reviewing a change](docs/handbook/editing.md#reviewing-a-change) gives on when a link leads the reader to its target. Read each such section once, as `git show <hash>:<path>` prints its file.
- When you file the findings of a review of a commit or of a standing doc review, file each as a `bug` ticket on `commit <hash>`, with the hash of the commit it reviews, other than one that a ticket outside `tickets/closed/` records.
