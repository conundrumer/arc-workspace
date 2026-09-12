export const meta = {
  name: 'cleanup-sweep',
  description: 'Rewrite the inline workarounds the lint names, one cleanup-role agent per solver.',
  phases: [
    { title: 'Cleanup', detail: 'one handbook agent under the cleanup role per solver, over the lines the lint names' },
  ],
}

// args:
//   role   the text of .claude/roles/cleanup.md; the script reads no file.
//   items  [{ stem, findings: ['<lint finding line>', ...] }], one per solver,
//          from `uv run python scripts/run_dl.py lint`, the `negated-value`
//          and `negated-use` lines grouped by solver.

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

if (!args || typeof args.role !== 'string' || !Array.isArray(args.items)) {
  return { error: 'args needs { role: <cleanup role text>, items: [{ stem, findings }] }' }
}

const brief = (item) => `
Brief

Files: programs/solvers/${item.stem}.dl.
Regions: the lines the findings below name.

Each finding states a direct form; write it. A \`negated-value\` finding's
comparison becomes the negated primitive. A \`negated-use\` finding's wrapper
relation goes, and the use that negated it negates the primitive. Then run
Simplify and Prune over those regions. Every finding is rewritten; a finding
that cannot be rewritten is reported under kept, with the reason.

Findings:
${item.findings.map((f) => `  ${f}`).join('\n')}
`

phase('Cleanup')
const reports = await pipeline(args.items, (item) =>
  agent(`${args.role}\n${brief(item)}`, {
    label: `cleanup:${item.stem}`,
    phase: 'Cleanup',
    agentType: 'handbook',
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
