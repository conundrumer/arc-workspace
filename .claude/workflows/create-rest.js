export const meta = {
  name: 'create-rest',
  description: 'Run the Create pass on each task in args, one create agent per task.',
  phases: [
    { title: 'Create', detail: 'one create agent per task' },
  ],
}

// The tag that marks a string as prose an agent reads. `uv run python -m
// controlled_markdown check` finds every `mctx` literal in the repo and reads
// it as the format, so the words in one are checked where they stand.
const mctx = (parts, ...values) => {
  const text = parts.reduce((out, part, i) => out + part + (i < values.length ? values[i] : ''), '')
  const lines = text.split('\n')
  while (lines.length && !lines[0].trim()) lines.shift()
  while (lines.length && !lines[lines.length - 1].trim()) lines.pop()
  const pad = Math.min(...lines.filter(l => l.trim()).map(l => l.length - l.trimStart().length), Infinity)
  return lines.map(l => (l.trim() ? l.slice(pad) : '')).join('\n')
}
// A run takes `tasks` in `args`: the task ids to create. A script has no
// shell, so the caller picks them, from the output of
// `bash scripts/queue.sh --order name --all --json`: the tasks with a
// `programs/reports/<task_id>/analyze.md`, no `programs/solvers/<task_id>.dl`
// and no claim file at `work/task/<task_id>/claim`. The workflow does not
// claim tasks, so two runs at the same time must not share a task.
// A pass changes no git state, so each new file stands untracked.
//
// Before a run, in a fresh checkout (such as a cloud session):
// - `git submodule update --init` fills `data/upstream/`. With it empty,
//   `scripts/queue.sh` lists no task.
// - `uv run python scripts/context.py --write` generates `.claude/agents/`,
//   which git ignores. Without it, `agentType: 'create'` fails with "agent
//   type 'create' not found". A session reads that directory at its start, so
//   a session that started before the files existed must be restarted to see
//   them. The session-start hook writes them only for the entry points
//   `cli`, `claude-desktop` and `sdk-cli`.
// - `souffle` and a C++ compiler must be on PATH, because Create runs the
//   solver it writes. `which souffle` finds the binary. No apt package
//   exists on Ubuntu 24.04, and a cloud session's network policy blocks
//   downloads from github.com, while `git clone` of
//   `https://github.com/souffle-lang/souffle.git` at tag 2.5 works. Build it
//   with cmake, with `-DSOUFFLE_USE_CURSES=OFF`, after
//   `apt-get install flex libffi-dev zlib1g-dev libsqlite3-dev libncurses-dev mcpp sqlite3`.
// - `scripts/run_dl.py` calls macOS `xcrun`, which Linux lacks. A script
//   `xcrun` on PATH stands in for it: `xcrun -f clang` exits 1, and
//   `xcrun clang++ <args>` runs `clang++` with the `-Wl,-install_name,*`
//   argument left out. The functor library then builds as `libfunctors.dylib`,
//   and `ln -s libfunctors.dylib programs/libfunctors.so` lets Souffle find it
//   (git ignores both). With these in place `uv run python scripts/run_dl.py
//   <stem>` passes on an existing solver.

if (!args || !Array.isArray(args.tasks) || !args.tasks.length) {
  return { error: 'args needs { tasks: [<task_id>, ...] }' }
}

// ---------------------------------------------------------------- briefs

const createBrief = (id) => mctx`
- Task: ${id}.
`

// ---------------------------------------------------------------- run

const replies = await parallel(args.tasks.map((id) => () => agent(createBrief(id), {
  label: `create:${id}`,
  phase: 'Create',
  agentType: 'create',
  model: 'opus',
})))

const chains = args.tasks.map((id, i) => ({ task: id, create: replies[i] ?? null }))
log(`${chains.filter((c) => c.create).length}/${args.tasks.length} tasks reached a Create report`)
return {
  chains,
  incomplete: chains.filter((c) => !c.create).map((c) => c.task),
}
