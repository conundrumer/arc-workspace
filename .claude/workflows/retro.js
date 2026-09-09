export const meta = {
  name: 'retro',
  description: 'Rule on what console sessions called out beyond their own tasks: read, check, review, fix.',
  phases: [
    { title: 'Read', detail: 'one agent turns the window into issues' },
    { title: 'Check', detail: 'one agent per group of issues: closed, dropped, or open with candidate fixes' },
    { title: 'Review', detail: 'one agent asks the two questions over every open issue and takes a default' },
    { title: 'Fix', detail: 'one agent per file makes the fixes the defaults call for, then a second pass by kind' },
  ],
}

// The agents are the retro-* definitions under .claude/agents/; each carries
// its stage's procedure. This script carries the order, the fan-out, the
// return schemas, and each instance's task.
//
// args:
//   {}                 full run; returns every call with its default, for, and against.
//   { dry: true }      full run that stops before Fix and returns the fixes it would make.
//   { fixes: [...] }   second run after the user's rulings: Fix only, over the given fixes.
//                      Each fix: { id, kind, target, edit }: a call's id with its fix, as the
//                      first run returned them under calls[].

const FIX_REF = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: ['prose', 'code', 'entry'] },
    target: { type: 'string', description: 'the file the fix edits, repo-relative; for an entry, docs/wf-solver/proposals/<name>.md' },
    edit: { type: 'string', description: 'the smallest edit that closes the issue, stated so an agent can make it without the issue in hand' },
  },
  required: ['kind', 'target', 'edit'],
}

const FIX_CANDIDATE = {
  type: 'object',
  properties: {
    ...FIX_REF.properties,
    for: { type: 'string' },
    against: { type: 'string' },
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
          reason: { type: 'string', description: 'the answer to the two questions, in one or two sentences' },
          for: { type: 'string', description: 'what argues for the default, each reason its own sentence' },
          against: { type: 'string', description: 'what argues against the default, each reason its own sentence; empty when nothing does' },
          fix: FIX_REF,
          covers: { type: 'array', items: { type: 'string' }, description: 'replace: the other issue ids this general fix also closes' },
        },
        required: ['id', 'default', 'reason', 'for', 'against'],
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

// ---------------------------------------------------------------- tasks

const readTask = () => 'Read the retro window and return the issues.'

const checkTask = (group, issues) => `Check these issues, all about ${group}.\n\n${JSON.stringify(issues, null, 2)}`

const reviewTask = (open) => `Review these open issues and their candidate fixes.\n\n${JSON.stringify(open, null, 2)}`

const fixTask = (target, fixes) => `Make these fixes in ${target}.\n\n${JSON.stringify(fixes, null, 2)}`

const pruneTask = (target, diff) => `Prune the text this diff added or changed in ${target}.\n\n${diff}`

const testCutTask = (target, diff) => `This diff changed ${target} and its tests.\n\n${diff}`

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

async function fixStage(fixes) {
  const byTarget = byKey(fixes, f => f.target)
  const made = await parallel([...byTarget].map(([target, fs]) => async () => {
    const edit = await agent(fixTask(target, fs), { label: `fix:${target}`, phase: 'Fix', schema: EDIT_SCHEMA, agentType: 'retro-fix' })
    if (!edit) return null
    const kind = fs.some(f => f.kind === 'code') ? 'code' : fs.every(f => f.kind === 'entry') ? 'entry' : 'prose'
    let second = null
    if (kind === 'prose') second = await agent(pruneTask(target, edit.diff), { label: `prune:${target}`, phase: 'Fix', schema: EDIT_SCHEMA, agentType: 'retro-prune' })
    if (kind === 'code') second = await agent(testCutTask(target, edit.diff), { label: `test-cut:${target}`, phase: 'Fix', schema: EDIT_SCHEMA, agentType: 'retro-test-cut' })
    return { target, kind, ids: fs.map(f => f.id), edit, second }
  }))
  return made.filter(Boolean)
}

if (args && args.fixes) {
  phase('Fix')
  const made = await fixStage(args.fixes)
  return { fixes: made.filter(m => m.kind !== 'entry'), entries: made.filter(m => m.kind === 'entry') }
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
// every call carries the fix a ruling for it would make; for a drop, the declined one
const ref = f => f && { kind: f.kind, target: f.target, edit: f.edit }
const calls = checks.filter(r => r.status === 'dropped')
  .map(r => ({ id: r.id, default: 'drop', for: r.for, against: r.against, fix: ref(r.fixes?.[0]) }))
log(`${closed.length} closed, ${calls.length} dropped, ${open.length} open`)

phase('Review')
if (open.length) {
  const review = await agent(reviewTask(open), { label: 'review', phase: 'Review', schema: REVIEW_SCHEMA, agentType: 'retro-review' })
  for (const r of review ? review.results : []) {
    const o = open.find(o => o.id === r.id)
    calls.push({ id: r.id, default: r.default, for: r.for, against: r.against, covers: r.covers,
                 fix: ref(r.fix) || (r.default !== 'replace' ? ref(o?.fixes?.[0]) : undefined), changed_work: o?.changed_work })
  }
}
const stands = calls.filter(c => (c.default === 'fix' || c.default === 'replace') && c.fix)
// one agent per general fix: fixes that several replaced issues point at collapse to one
const fixes = [...byKey(stands, c => `${c.fix.target}\n${c.fix.edit}`)].map(([, cs]) => ({ ...cs[0].fix, id: cs.map(c => c.id).join(',') }))
const tally = { issues: issues.length, closed: closed.length }
for (const c of calls) tally[c.default] = (tally[c.default] || 0) + 1
log(`${fixes.length} fixes to make`)

phase('Fix')
const dry = args && args.dry
const made = fixes.length && !dry ? await fixStage(fixes) : []

return {
  tally,
  dry: dry ? fixes : undefined,
  closed,
  calls: calls.map(withIssue),
  fixes: made.filter(m => m.kind !== 'entry'),
  entries: made.filter(m => m.kind === 'entry'),
  borderline_drops: read.borderline_drops,
}
