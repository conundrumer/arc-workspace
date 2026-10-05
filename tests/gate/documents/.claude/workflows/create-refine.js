export const meta = {
  name: 'create-refine',
  description: 'Deprecated. Run Create, then Refine, on each task in args, one chain per task.',
  phases: [
    { title: 'Create', detail: 'one create agent per task' },
    { title: 'Refine', detail: 'one refine agent per task, after its Create' },
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
// prints them. Each task's `.scratch/<task_id>/` holds the Analyze files, and
// no solver of the task exists at the start.

if (!args || !Array.isArray(args.tasks) || !args.tasks.length) {
  return { error: 'args needs { tasks: [<task_id>, ...] }' }
}

// ---------------------------------------------------------------- briefs

// With `marker` in `args`, each brief asks the agent to write the marker its
// agent file gives, which shows whether the run loaded the current file.
const markerLine = (id, pass) => args.marker ? mctx`
- Before anything else, write the marker line your agent file gives, or \`none\`, to \`.scratch/${id}/marker-${pass}\`.
` : ''

const createBrief = (id) => mctx`
- Task: ${id}.
- If \`concept.md\`, \`analyze.md\`, or \`witnesses.json\` is missing under \`.scratch/${id}/\`, reply \`missing: <file>\` and stop.
${markerLine(id, 'create')}
`

const refineBrief = (id) => mctx`
- Task: ${id}.
${markerLine(id, 'refine')}
`

// ---------------------------------------------------------------- run

const results = await pipeline(
  args.tasks,
  (_, id) => agent(createBrief(id), {
    label: `create:${id}`,
    phase: 'Create',
    agentType: 'create',
  }),
  (create, id) => {
    if (!create || create.startsWith('missing:')) {
      log(`${id}: Create gave ${create ?? 'nothing'}, so Refine does not run`)
      return { task: id, create, refine: null }
    }
    return agent(refineBrief(id), {
      label: `refine:${id}`,
      phase: 'Refine',
      agentType: 'refine',
    }).then((refine) => ({ task: id, create, refine }))
  },
)

const chains = args.tasks.map((id, i) => results[i] ?? { task: id, create: null, refine: null })
const done = chains.filter((c) => c.refine)
log(`${done.length}/${args.tasks.length} tasks reached a Refine report`)
return {
  chains,
  incomplete: chains.filter((c) => !done.includes(c)).map((c) => c.task),
}
