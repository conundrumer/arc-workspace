export const meta = {
  name: 'analyze-rest',
  description: 'Run the Analyze pass on each queue task that has no Analyze report and no claim.',
  phases: [
    { title: 'Select', detail: 'one agent lists the tasks that need Analyze' },
    { title: 'Analyze', detail: 'one analyze agent per selected task' },
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
// A run takes an optional `args.limit`: the most tasks to analyze, taken in
// queue order. A pass changes no git state, so each new file stands untracked.
//
// Before a run, in a fresh checkout (such as a cloud session):
// - `git submodule update --init` fills `data/upstream/`. With it empty,
//   `scripts/queue.sh` lists no task, and the select agent returns an empty list.
// - `uv run python scripts/context.py --write` generates `.claude/agents/`,
//   which git ignores. Without it, `agentType: 'analyze'` fails with "agent
//   type 'analyze' not found". A session reads that directory at its start, so
//   a session that started before the files existed must be restarted to see
//   them. The session-start hook writes them only for the entry points
//   `cli`, `claude-desktop` and `sdk-cli`.
// - A script has no shell, so the select agent runs `scripts/queue.sh`.
// - The workflow does not claim tasks. It leaves out a task that has a claim
//   file, and two runs at the same time can pick the same task.

const SELECTED = {
  type: 'object',
  properties: { tasks: { type: 'array', items: { type: 'string' } } },
  required: ['tasks'],
}

// ---------------------------------------------------------------- briefs

const selectBrief = () => mctx`
- Run \`bash scripts/queue.sh --order name --all --json\`.
- Leave out each task that has a claim file at \`work/task/<task_id>/claim\`.
- Of the tasks that remain, leave out each that has \`programs/reports/<task_id>/analyze.md\`.
- Reply with the task ids that remain, in queue order.
`

const analyzeBrief = (id) => mctx`
- Task: ${id}.
`

// ---------------------------------------------------------------- run

phase('Select')
const selected = await agent(selectBrief(), {
  label: 'select',
  phase: 'Select',
  schema: SELECTED,
  effort: 'low',
})
if (!selected) return { error: 'the select agent returned nothing' }

const limit = args && Number.isInteger(args.limit) ? args.limit : null
const tasks = limit === null ? selected.tasks : selected.tasks.slice(0, limit)
log(`${tasks.length} of ${selected.tasks.length} tasks need Analyze`)

const replies = await parallel(tasks.map((id) => () => agent(analyzeBrief(id), {
  label: `analyze:${id}`,
  phase: 'Analyze',
  agentType: 'analyze',
})))

const chains = tasks.map((id, i) => ({ task: id, analyze: replies[i] ?? null }))
log(`${chains.filter((c) => c.analyze).length}/${tasks.length} tasks reached an Analyze report`)
return {
  chains,
  incomplete: chains.filter((c) => !c.analyze).map((c) => c.task),
  notRun: selected.tasks.slice(tasks.length),
}
