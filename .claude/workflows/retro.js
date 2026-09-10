export const meta = {
  name: 'retro',
  description: 'Rule on what console sessions called out beyond their own tasks: read, check, review, fix, verify.',
  phases: [
    { title: 'Read', detail: 'one agent turns the window into issues' },
    { title: 'Check', detail: 'one agent per group of issues: closed, dropped, or open with candidate fixes' },
    { title: 'Review', detail: 'one agent asks the two questions over every open issue and takes a default' },
    { title: 'Fix', detail: 'code targets one at a time, every other target in parallel, then a prune pass over each prose target' },
    { title: 'Verify', detail: 'one agent per changed target, then one agent runs the checks' },
  ],
}

// Most stages run a named agent from .claude/agents/; each carries its stage's
// procedure. The checks step runs a general-purpose agent, and its task text
// carries the commands. This script carries the order, the fan-out, the return
// schemas, and each instance's task.
//
// args:
//   {}                 full run; returns every call with its default, for, and against.
//   { dry: true }      full run that stops before Fix and returns the fixes it would make.
//   { fixes: [...] }   second run after the user's rulings: Fix and Verify, over the given fixes.
//                      Each fix: { id, kind, target, edit }: a call's id with one entry per
//                      target, as the first run returned them under calls[].fixes. The fixes
//                      are ruled: the prune pass keeps their substance.

// The judgment a call took. A tier-4 fix is not made in the first run.
const TIER = {
  type: 'integer',
  minimum: 1,
  maximum: 4,
  description: '1: no judgment, a principle states it, it is a bug, or it corrects a wrong fact; 2: a straightforward reading of the user\'s intent or an existing norm; 3: a defensible judgment close to the norms; 4: insufficient basis to settle',
}

const FIX_REF = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: ['prose', 'code', 'entry', 'solver'] },
    target: { type: 'string', description: 'the one file the fix edits, repo-relative; for an entry, docs/wf-solver/proposals/<name>.md; for a solver, programs/solvers/<task_id>.dl' },
    edit: { type: 'string', description: 'the smallest edit that closes the issue in this file, stated so an agent that has this file alone can make it without the issue in hand' },
  },
  required: ['kind', 'target', 'edit'],
}

const FIX_CANDIDATE = {
  type: 'object',
  properties: {
    ...FIX_REF.properties,
    for: { type: 'string' },
    against: { type: 'string' },
    illustration: { type: 'string', description: 'a fix to docs/wf-solver/principles.md at tier 3: for each cited task, the case sets under each reading and a witness input where the readings differ' },
  },
  required: [...FIX_REF.required, 'for', 'against'],
}

const ISSUES_SCHEMA = {
  type: 'object',
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string', description: 'I1, I2, ... in count-descending order' },
          group: { type: 'string', description: 'the file or tool the issue is about: a doc file, programs/lib.dl, the runner, the console, the task data' },
          issue: { type: 'string', description: 'one plain sentence: what is wrong or missing in the shared thing, not what a session did' },
          count: { type: 'integer' },
          tasks: { type: 'array', items: { type: 'string' } },
          quote: { type: 'string', description: 'one callout, verbatim' },
        },
        required: ['id', 'group', 'issue', 'count', 'tasks', 'quote'],
      },
    },
    borderline_drops: {
      type: 'array',
      description: 'callouts dropped as task-local where the call was close: task id and the first words',
      items: { type: 'string' },
    },
  },
  required: ['issues', 'borderline_drops'],
}

const CHECK_SCHEMA = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          status: { type: 'string', enum: ['closed', 'dropped', 'open'] },
          closed_by: { type: 'string', description: 'closed: the commit or the current text that closes it' },
          tier: { ...TIER, description: `dropped: ${TIER.description}` },
          for: { type: 'string', description: 'dropped: what argues for the drop, each reason its own sentence' },
          against: { type: 'string', description: 'dropped: what argues against the drop, each reason its own sentence; empty when nothing does' },
          changed_work: { type: 'boolean', description: 'open: whether the issue changed what a session did, or was only noted' },
          changed_how: { type: 'string', description: 'open: one sentence on what it caused' },
          fixes: { type: 'array', items: FIX_CANDIDATE, description: 'open: the candidate fixes, the recommended one first; dropped: the declined fix' },
        },
        required: ['id', 'status'],
      },
    },
  },
  required: ['results'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          default: { type: 'string', enum: ['fix', 'replace', 'drop'], description: 'the outcome that holds unless the user rules otherwise' },
          tier: TIER,
          reason: { type: 'string', description: 'the answer to the two questions, in one or two sentences' },
          for: { type: 'string', description: 'what argues for the default, each reason its own sentence' },
          against: { type: 'string', description: 'what argues against the default, each reason its own sentence; empty when nothing does' },
          fixes: { type: 'array', items: FIX_REF, description: 'the fix the default calls for, one entry per file it edits' },
          covers: { type: 'array', items: { type: 'string' }, description: 'replace: the other issue ids this general fix also closes' },
        },
        required: ['id', 'default', 'tier', 'reason', 'for', 'against'],
      },
    },
  },
  required: ['results'],
}

const EDIT_SCHEMA = {
  type: 'object',
  properties: {
    diff: { type: 'string', description: 'the unified diff, verbatim' },
    net_words: { type: 'integer', description: 'prose: words added minus words removed' },
    verification: { type: 'string', description: 'what was run and its result' },
    notes: { type: 'string' },
  },
  required: ['diff', 'verification'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          kind: { type: 'string', enum: ['wrong edit', 'broken rule', 'contradiction', 'test', 'dropped substance'] },
          finding: { type: 'string', description: 'what is wrong, in one or two sentences' },
          fixed: { type: 'string', description: 'what the fix for it was, or why it was left' },
        },
        required: ['kind', 'finding', 'fixed'],
      },
    },
    diff: { type: 'string', description: 'the unified diff of what this pass changed, verbatim; empty when it changed nothing' },
  },
  required: ['findings', 'diff'],
}

const CHECKS_SCHEMA = {
  type: 'object',
  properties: {
    checks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          command: { type: 'string' },
          passed: { type: 'boolean' },
          summary: { type: 'string', description: 'the summary line, verbatim' },
          failures: { type: 'string', description: 'every failure in full; empty when the check passed' },
        },
        required: ['command', 'passed', 'summary', 'failures'],
      },
    },
  },
  required: ['checks'],
}

// ---------------------------------------------------------------- tasks

const readTask = () => 'Read the retro window and return the issues.'

const checkTask = (group, issues) => `Check these issues, all about ${group}.\n\n${JSON.stringify(issues, null, 2)}`

const reviewTask = (open) => `Review these open issues and their candidate fixes.\n\n${JSON.stringify(open, null, 2)}`

const fixTask = (target, fixes) => `Make these fixes in ${target}.\n\n${JSON.stringify(fixes, null, 2)}`

// The reader the pruned text serves, by where the text lives.
const readerFor = (target) =>
  target === 'docs/wf-solver/backlog.md' ? 'the user'
    : target.startsWith('.claude/agents/') ? 'a retro agent that carries this file as its definition'
      : 'a future solver session that reads the file through `uv run python scripts/context.py` to write a Souffle solver'

const pruneTask = (target, diff, ruled, fixes) =>
  `Prune the text this diff added or changed in ${target}. The reader is ${readerFor(target)}.` +
  (ruled ? ' The user ruled for these fixes: remove nothing their edit names, keep their substance, and reword only.' : '') +
  `\n\nThe edits the diff was meant to make:\n${JSON.stringify(fixes.map(f => f.edit), null, 2)}\n\n${diff}`

const verifyTask = (made) =>
  `Verify the changes to ${made.target}.\n\n` +
  `The edits they were meant to make:\n${JSON.stringify(made.fixes.map(f => f.edit), null, 2)}\n\n` +
  `The fix diff:\n${made.edit.diff}` +
  (made.chain ? `\n\nThe combined diff of every code target in this run:\n${made.chain}` : '') +
  (made.second ? `\n\nThe second pass diff:\n${made.second.diff}` : '')

const checksTask = () => [
  'Run these three checks over the current tree, in this order:',
  '',
  '    1. `uv run pytest -q`',
  '    2. `uv run python scripts/context.py > /dev/null; echo exit=$?`',
  '    3. `uv run python scripts/run_dl.py`',
  '',
  'Run each one to completion. A failure in an earlier check does not stop a later one.',
  'Give each command a timeout long enough for the corpus run. When a command takes longer than the tool allows, run it in the background and wait for it to finish.',
  'Report each command: whether it passed, its summary line verbatim, and every failure in full.',
  'Report a failure as a failure. Do not attribute it to other work, and do not report it as passing.',
  'Change no file. Never run a git command that changes state: no `stash`, `checkout`, `reset`, `rm`, or `commit`.',
].join('\n')

// ---------------------------------------------------------------- stages

const byKey = (items, key) => {
  const m = new Map()
  for (const it of items) {
    const k = key(it)
    if (!m.has(k)) m.set(k, [])
    m.get(k).push(it)
  }
  return m
}

// A target takes one kind. A code fix decides the target, since its tests move with it.
const kindOf = (fixes) =>
  fixes.some(f => f.kind === 'code') ? 'code'
    : fixes.every(f => f.kind === 'solver') ? 'solver'
      : fixes.every(f => f.kind === 'entry') ? 'entry'
        : 'prose'

const fixAgent = (kind) => (kind === 'solver' ? 'solver' : 'retro-fix')

async function fixStage(fixes, ruled = false) {
  const targets = [...byKey(fixes, f => f.target)].map(([target, fs]) => ({ target, fixes: fs, kind: kindOf(fs) }))
  const code = targets.filter(t => t.kind === 'code')
  const rest = targets.filter(t => t.kind !== 'code')

  const makeFix = async (t) => {
    const edit = await agent(fixTask(t.target, t.fixes), { label: `fix:${t.target}`, phase: 'Fix', schema: EDIT_SCHEMA, agentType: fixAgent(t.kind) })
    if (!edit) return null
    return { target: t.target, kind: t.kind, ids: t.fixes.map(f => f.id), fixes: t.fixes, edit, chain: null, second: null }
  }

  // Every code target edits the same tree and the same suite, so they go one at
  // a time, each starting from the tree the previous one left. Their combined
  // diff goes to each of their verify passes, which judges the tests in it.
  const codeChain = async () => {
    const made = []
    for (const t of code) {
      const m = await makeFix(t)
      if (m) made.push(m)
    }
    if (made.length > 1) {
      const diff = made.map(m => m.edit.diff).join('\n')
      for (const m of made) m.chain = diff
    }
    return made
  }

  const otherTargets = async () => parallel(rest.map(t => async () => {
    const m = await makeFix(t)
    if (!m) return null
    if (m.kind === 'prose') m.second = await agent(pruneTask(m.target, m.edit.diff, ruled, m.fixes), { label: `prune:${m.target}`, phase: 'Fix', schema: EDIT_SCHEMA, agentType: 'retro-prune' })
    return m
  }))

  const [others, coded] = await parallel([otherTargets, codeChain])
  return [...(others || []), ...(coded || [])].filter(Boolean)
}

async function verifyStage(made) {
  const findings = (await parallel(made.map(m => async () => {
    const v = await agent(verifyTask(m), { label: `verify:${m.target}`, phase: 'Verify', schema: VERIFY_SCHEMA, agentType: 'retro-verify' })
    return v && { target: m.target, ...v }
  }))).filter(Boolean)
  const checks = await agent(checksTask(), { label: 'checks', phase: 'Verify', schema: CHECKS_SCHEMA })
  const failed = checks ? checks.checks.filter(c => !c.passed) : []
  log(`${findings.reduce((n, f) => n + f.findings.length, 0)} verify findings; ${failed.length} failing checks`)
  return { findings, checks: checks ? checks.checks : [] }
}

if (args && args.fixes) {
  phase('Fix')
  const made = await fixStage(args.fixes, true)
  phase('Verify')
  const verify = await verifyStage(made)
  return { fixes: made.filter(m => m.kind !== 'entry'), entries: made.filter(m => m.kind === 'entry'), verify }
}

phase('Read')
const read = await agent(readTask(), { label: 'read', phase: 'Read', schema: ISSUES_SCHEMA, agentType: 'retro-read' })
if (!read) return { error: 'read agent returned nothing' }
const issues = read.issues
log(`${issues.length} issues from the window; ${read.borderline_drops.length} borderline drops`)
if (!issues.length) return { tally: { issues: 0 }, borderline_drops: read.borderline_drops }

phase('Check')
const groups = byKey(issues, i => i.group)
const checks = (await parallel([...groups].map(([group, gi]) => () =>
  agent(checkTask(group, gi), { label: `check:${group}`, phase: 'Check', schema: CHECK_SCHEMA, agentType: 'retro-check' })
))).filter(Boolean).flatMap(r => r.results)
const issueById = new Map(issues.map(i => [i.id, i]))
const withIssue = r => ({ ...r, issue: issueById.get(r.id)?.issue, tasks: issueById.get(r.id)?.tasks, count: issueById.get(r.id)?.count })
const closed = checks.filter(r => r.status === 'closed').map(withIssue)
const open = checks.filter(r => r.status === 'open').map(withIssue)
// every call carries the fix a ruling for it would make, one entry per file it
// edits; for a drop, the declined one
const ref = f => f && { kind: f.kind, target: f.target, edit: f.edit, illustration: f.illustration }
const refs = fs => (fs || []).map(ref).filter(Boolean)
const calls = checks.filter(r => r.status === 'dropped')
  .map(r => ({ id: r.id, default: 'drop', tier: r.tier, for: r.for, against: r.against, fixes: refs([r.fixes?.[0]]) }))
log(`${closed.length} closed, ${calls.length} dropped, ${open.length} open`)

phase('Review')
if (open.length) {
  const review = await agent(reviewTask(open), { label: 'review', phase: 'Review', schema: REVIEW_SCHEMA, agentType: 'retro-review' })
  for (const r of review ? review.results : []) {
    const o = open.find(o => o.id === r.id)
    const fixes = r.fixes?.length ? refs(r.fixes) : (r.default === 'replace' ? [] : refs([o?.fixes?.[0]]))
    calls.push({ id: r.id, default: r.default, tier: r.tier, for: r.for, against: r.against, covers: r.covers,
                 fixes, changed_work: o?.changed_work })
  }
}
// a tier-4 call is presented and not made
const stands = calls.filter(c => (c.default === 'fix' || c.default === 'replace') && c.fixes.length && c.tier !== 4)
// one agent per general fix: fixes that several replaced issues point at collapse to one
const fixes = [...byKey(stands.flatMap(c => c.fixes.map(f => ({ ...f, id: c.id }))), f => `${f.target}\n${f.edit}`)]
  .map(([, fs]) => ({ ...fs[0], id: fs.map(f => f.id).join(',') }))
const tally = { issues: issues.length, closed: closed.length }
for (const c of calls) tally[c.default] = (tally[c.default] || 0) + 1
log(`${fixes.length} fixes to make`)

phase('Fix')
const dry = args && args.dry
const made = fixes.length && !dry ? await fixStage(fixes) : []

phase('Verify')
const verify = made.length ? await verifyStage(made) : null

return {
  tally,
  dry: dry ? fixes : undefined,
  closed,
  calls: calls.map(withIssue),
  fixes: made.filter(m => m.kind !== 'entry'),
  entries: made.filter(m => m.kind === 'entry'),
  verify,
  borderline_drops: read.borderline_drops,
}
