export const meta = {
  name: 'analyze-create',
  description: 'Run Analyze, then Create, on each task in args, one chain per task.',
  phases: [
    { title: 'Analyze', detail: 'one analyze agent per task' },
    { title: 'Create', detail: 'one create agent per task, after its Analyze' },
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
// A run takes `tasks` in `args`: the task ids, as `bash scripts/queue.sh`
// prints them. Each task's `.scratch/<task_id>/` must not exist at the start.
// With `analyzeOnly: true`, a task's chain ends after Analyze.

if (!args || !Array.isArray(args.tasks) || !args.tasks.length) {
  return { error: 'args needs { tasks: [<task_id>, ...] }' }
}

// ---------------------------------------------------------------- briefs

const analyzeBrief = (id) => mctx`
- Task: ${id}.
`

const createBrief = (id) => mctx`
- Task: ${id}.
- If \`concept.md\`, \`analyze.md\`, or \`witnesses.json\` is missing under \`.scratch/${id}/\`, reply \`missing: <file>\` and stop.
`

// ---------------------------------------------------------------- run

const results = await pipeline(
  args.tasks,
  (_, id) => agent(analyzeBrief(id), {
    label: `analyze:${id}`,
    phase: 'Analyze',
    agentType: 'analyze',
  }),
  (analyze, id) => {
    if (!analyze) {
      log(`${id}: Analyze returned nothing, so Create does not run`)
      return { task: id, analyze: null, create: null }
    }
    if (args.analyzeOnly) return { task: id, analyze, create: null }
    return agent(createBrief(id), {
      label: `create:${id}`,
      phase: 'Create',
      agentType: 'create',
    }).then((create) => ({ task: id, analyze, create }))
  },
)

const chains = args.tasks.map((id, i) => results[i] ?? { task: id, analyze: null, create: null })
const done = args.analyzeOnly
  ? chains.filter((c) => c.analyze)
  : chains.filter((c) => c.create && !c.create.startsWith('missing:'))
log(`${done.length}/${args.tasks.length} tasks reached a ${args.analyzeOnly ? 'Analyze' : 'Create'} report`)
return {
  chains,
  incomplete: chains.filter((c) => !done.includes(c)).map((c) => c.task),
}
