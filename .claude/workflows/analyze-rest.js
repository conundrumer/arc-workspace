export const meta = {
  name: 'analyze-rest',
  description: 'Run the Analyze pass on each task in args, one analyze agent per task.',
  phases: [
    { title: 'Analyze', detail: 'one analyze agent per task' },
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
// A run takes `tasks` in `args`: the task ids to analyze. A script has no
// shell, so the caller picks them, from the output of
// `bash scripts/queue.sh --order name --all --json`: the tasks with no
// `programs/reports/<task_id>/analyze.md` and no claim file at
// `work/task/<task_id>/claim`. The workflow does not claim tasks, so two runs
// at the same time must not share a task.
// A pass changes no git state, so each new file stands untracked.
//
// Before a run, in a fresh checkout (such as a cloud session):
// - `git submodule update --init` fills `data/upstream/`. With it empty,
//   `scripts/queue.sh` lists no task.
// - `uv run python scripts/context.py --write` generates `.claude/agents/`,
//   which git ignores. Without it, `agentType: 'analyze'` fails with "agent
//   type 'analyze' not found". A session reads that directory at its start, so
//   a session that started before the files existed must be restarted to see
//   them. The session-start hook writes them only for the entry points
//   `cli`, `claude-desktop` and `sdk-cli`.

if (!args || !Array.isArray(args.tasks) || !args.tasks.length) {
  return { error: 'args needs { tasks: [<task_id>, ...] }' }
}

// ---------------------------------------------------------------- briefs

const analyzeBrief = (id) => mctx`
- Task: ${id}.
`

// ---------------------------------------------------------------- run

const replies = await parallel(args.tasks.map((id) => () => agent(analyzeBrief(id), {
  label: `analyze:${id}`,
  phase: 'Analyze',
  agentType: 'analyze',
})))

const chains = args.tasks.map((id, i) => ({ task: id, analyze: replies[i] ?? null }))
log(`${chains.filter((c) => c.analyze).length}/${args.tasks.length} tasks reached an Analyze report`)
return {
  chains,
  incomplete: chains.filter((c) => !c.analyze).map((c) => c.task),
}
