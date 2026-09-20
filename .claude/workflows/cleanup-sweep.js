export const meta = {
  name: 'cleanup-sweep',
  description: 'Rewrite the inline workarounds the lint names, one cleanup-role agent per solver.',
  phases: [
    { title: 'Cleanup', detail: 'one agent under the cleanup role per solver, over the lines the lint names' },
  ],
}

// A run takes its `roles` in `args`, as `.claude/skills/session/SKILL.md`
// says to pass them, beside `items`: [{ stem, findings: ['<lint finding
// line>', ...] }], one per solver, from `uv run python scripts/run_dl.py
// lint`, the `negated-value` and `negated-use` lines grouped by solver.

const REPORT = {
  type: 'object',
  properties: {
    stem: { type: 'string' },
    changed: { type: 'boolean', description: 'whether the file differs from before the pass' },
    run: { type: 'string', enum: ['pass', 'fail'], description: 'the solver run after the pass' },
    kept: {
      type: 'array', items: { type: 'string' },
      description: 'each finding left as written, with the reason',
    },
    notes: { type: 'string', description: 'what the report section of the role asks for' },
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

// The brief this sweep sends its agent. Everything from the marker above to
// the marker below is the prose this script holds: `scripts/context.py
// workflow` slices the region and prints it, so a reader outside the script
// reads the brief without running it.

const brief = (item) => `- Files: programs/solvers/${item.stem}.dl.
- Regions: the lines the findings below name.
- Each finding states a direct form; write it.
    - A \`negated-value\` finding's comparison becomes the negated primitive.
    - A \`negated-use\` finding's wrapper relation goes, and the use that negated it negates the primitive.
- Then run Simplify and Prune over those regions.
- Every finding is rewritten. A finding you leave as written is reported under \`kept\`, with the reason.
- Findings:

\`\`\`
${item.findings.join('\n')}
\`\`\``

// ------------------------------------------------------------- briefs end

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
