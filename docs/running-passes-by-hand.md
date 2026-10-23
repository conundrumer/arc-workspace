# Running Analyze and Create by hand

One Analyze pass and one Create pass, each on its own task, with no operator. These steps skip `set-aside`, which suits a task that has no earlier report, solver or witness file of its pass.

## Choose the tasks

The queue is the output of `bash scripts/queue.sh --order name --all --json`. Leave out each task that has a claim file at `work/task/<task_id>/claim`.

- Analyze takes the first queue task that has no `programs/reports/<task_id>/analyze.md`.
- Create takes the first queue task that has `programs/reports/<task_id>/analyze.md` and no `programs/solvers/<task_id>.dl`.

## Run the passes

1. Claim each task: `uv run python scripts/operate.py claim <task_id>`. Launch a pass only where this exits 0.
2. Launch the `analyze` agent on its task and the `create` agent on its task, in the background and at the same time. The brief of each is `Task: <task_id>`.
3. Wait for both replies. A pass changes no git state, so its new files stand untracked until `git add` and `git commit` keep them.
