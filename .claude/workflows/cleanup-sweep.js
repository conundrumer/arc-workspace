export const meta = {
  name: 'cleanup-sweep',
  description: mctx`Rewrite the inline workarounds the lint names, one cleanup-role agent per solver.`,
  phases: [
    { title: 'Cleanup', detail: 'one agent under the cleanup role per solver, over the lines the lint names' },
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
// A run takes its `roles` in `args`, as `.claude/skills/session/SKILL.md`
// says to pass them, beside `items`: [{ stem, findings: ['<lint finding
// line>', ...] }], one per solver, from `uv run python scripts/run_dl.py
// lint`, the `negated-value` and `negated-use` lines grouped by solver.

const REPORT = {
  type: 'object',
  properties: {
    stem: { type: 'string' },
    changed: { type: 'boolean', description: mctx`whether the file differs from before the pass` },
    run: { type: 'string', enum: ['pass', 'fail'], description: mctx`the solver run after the pass` },
    kept: {
      type: 'array', items: { type: 'string' },
      description: mctx`each finding left as written, with the reason`,
    },
    notes: { type: 'string', description: mctx`what the report section of the role asks for` },
  },
  required: ['stem', 'changed', 'run', 'kept', 'notes'],
}

if (!args || !args.roles || !Array.isArray(args.items)) {
  return { error: 'args needs { roles, items: [{ stem, findings }] }' }
}

// A role's first line may name its agent. The spawn takes the agent from
// that line and the prompt from the rest.
const AGENT_LINE = /^Agent: (\S+)\n+/
const agentMatch = args.roles.cleanup.trim().match(AGENT_LINE)
const agentType = agentMatch ? agentMatch[1] : 'handbook'
const role = args.roles.cleanup.trim().replace(AGENT_LINE, '')

// ---------------------------------------------------------------- briefs

// The brief this sweep sends its agent. It is an `mctx` literal, so the check
// reads its words as the format where they stand.

const brief = (item) => {
  const solver = `programs/solvers/${item.stem}.dl`
  const findings = item.findings.join('\n')
  return mctx`
- Files: ${solver}.
- Regions: the lines the findings below name.
- Each finding states a direct form; write it.
    - A \`negated-value\` finding's comparison becomes the negated primitive.
    - A \`negated-use\` finding's wrapper relation goes, and the use that negated it negates the primitive.
- Then run Simplify and Prune over those regions.
- Every finding is rewritten. A finding you leave as written is reported under \`kept\`, with the reason.
- Findings:

~~~
${findings}
~~~
`
}


phase('Cleanup')
const reports = await pipeline(args.items, (item) =>
  agent(`${role}\n\nYour brief:\n\n${brief(item)}`, {
    label: `cleanup:${item.stem}`,
    phase: 'Cleanup',
    agentType,
    schema: REPORT,
  }))

const done = reports.filter(Boolean)
log(`${done.length}/${args.items.length} solvers reported`)
return {
  reports: done,
  failed: done.filter((r) => r.run === 'fail').map((r) => r.stem),
  kept: done.flatMap((r) => r.kept.map((k) => `${r.stem}: ${k}`)),
  missing: args.items.map((i) => i.stem).filter((s) => !done.some((r) => r.stem === s)),
}
