export const meta = {
  name: 'retro',
  description: 'Rule on what console sessions called out beyond their own tasks: read, check, review, fix, verify, sweep.',
  phases: [
    { title: 'Read', detail: 'one agent turns the window into issues' },
    { title: 'Sweep', detail: 'one agent sweeps the parameter values of every solver the window names, beside the check and review stages; then one agent writes a review line into each solver a parameter stays open in', model: 'sonnet' },
    { title: 'Check', detail: 'one agent per group of issues: closed, dropped, or open with candidate fixes' },
    { title: 'Review', detail: 'one agent asks the two questions over every open issue and takes a default', model: 'fable' },
    { title: 'Fix', detail: 'code targets one at a time, every prose target in one agent that fixes then prunes, every other target in parallel' },
    { title: 'Verify', detail: 'one agent per changed target, one agent for the prose targets together, one agent for the checks, then one round over the other files those findings name', model: 'sonnet' },
  ],
}

// Most stages run the handbook-principles agent under a role from
// .claude/roles/; each role carries its stage's procedure, and a task opens
// with the role text, then the brief. The checks step runs a general-purpose
// agent, and its task text carries the commands. This script carries the
// order, the fan-out, the return schemas, and each instance's task.
//
// args:
//   { roles: {...} }   required in every run: the text of each role the run reaches, by role
//                      name — { 'retro-read': '<the text of .claude/roles/retro-read.md>' }.
//                      The script reads no file, so the caller passes the text. READ_ROLES and
//                      FIX_ROLES name what each run needs; a missing one returns an error.
//   {}                 full run; returns every call with its default, for, and against.
//   { dry: true }      full run that stops before Fix and returns the fixes it would make.
//   { fixes: [...] }   second run after the user's rulings: Fix and Verify, over the given fixes.
//                      Each fix: { id, kind, target, edit, tasks }: a call's id with one entry
//                      per target, as the first run returned them under calls[].fixes, and the
//                      issue's task ids, which a fix over a principle writes a review line into.
//                      The fixes are ruled: the prune step keeps their substance.

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
          basis: { type: 'string', description: 'dropped: the principle, norm, or fact the drop rests on' },
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
          basis: { type: 'string', description: 'the principle, the norm, or the fact the call rests on' },
          for: { type: 'string', description: 'what argues for the default, each reason its own sentence' },
          against: { type: 'string', description: 'what argues against the default, each reason its own sentence; empty when nothing does' },
          options: {
            type: 'array',
            description: 'a fix to docs/wf-solver/principles.md: the readings the call chose between, the chosen one first',
            items: {
              type: 'object',
              properties: {
                choice: { type: 'string', enum: ['keep', 'amend', 'leave'], description: 'keep: the change as the default proposes it; amend: the existing text rewritten in place; leave: the existing text as it stands' },
                wording: { type: 'string', description: 'the text the file carries under this reading' },
                consequence: { type: 'string', description: 'what a session that reads this wording does differently' },
                witness: { type: 'string', description: 'a task or a solver where this reading and the others part' },
              },
              required: ['choice', 'wording', 'consequence', 'witness'],
            },
          },
          fixes: { type: 'array', items: FIX_REF, description: 'the fix the default calls for, one entry per file it edits' },
          covers: { type: 'array', items: { type: 'string' }, description: 'replace: the other issue ids this general fix also closes' },
        },
        required: ['id', 'default', 'tier', 'reason', 'basis', 'for', 'against'],
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
          other_file: { type: 'string', description: 'the repo-relative path of the file the fix belongs in, when the finding was left for another file; empty otherwise' },
        },
        required: ['kind', 'finding', 'fixed', 'other_file'],
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

const SWEEP_SCHEMA = {
  type: 'object',
  properties: {
    sweeps: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          stem: { type: 'string' },
          params: {
            type: 'array',
            description: 'the parameters the sweep leaves open: the line carries one of the four clauses the brief lists',
            items: {
              type: 'object',
              properties: {
                param: { type: 'string' },
                reported: { type: 'string', description: 'what the sweep reported for it, verbatim' },
              },
              required: ['param', 'reported'],
            },
          },
        },
        required: ['stem', 'params'],
      },
    },
  },
  required: ['sweeps'],
}

const SWEEP_LINES_SCHEMA = {
  type: 'object',
  properties: {
    solvers: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          task_id: { type: 'string' },
          lines: { type: 'array', items: { type: 'string' }, description: 'the review lines written, verbatim; empty when every line already stood' },
          lint_ok: { type: 'boolean', description: 'whether the lint\'s `header` category reports nothing after the change' },
        },
        required: ['task_id', 'lines', 'lint_ok'],
      },
    },
  },
  required: ['solvers'],
}

// ---------------------------------------------------------------- tasks

const readTask = () => 'Read the retro window and return the issues.'

const checkTask = (group, issues) => `Check these issues, all about ${group}.\n\n${JSON.stringify(issues, null, 2)}`

const reviewTask = (open) => `Review these open issues and their candidate fixes.\n\n${JSON.stringify(open, null, 2)}`

// Each fix agent writes its diff to a path taken from the target path, so a
// later brief names that path.
const diffPath = (target) => `.scratch/retro/diffs/${target.split('/').join('__')}.diff`

// One entry per file: the file, the fixes it takes, and where its diff goes.
const fixEntries = (groups) => JSON.stringify(
  groups.map(g => ({ target: g.target, diff_path: diffPath(g.target), fixes: g.fixes })), null, 2)

const fixTask = (groups) => [
  groups.length > 1
    ? `Make these fixes. Each entry names one file, the fixes that file takes, and the path its diff goes to.`
    : `Make these fixes in ${groups[0].target}.`,
  '',
  fixEntries(groups),
  '',
  'Write the diff of your changes to each file, verbatim, to that file\'s `diff_path`. Create the directory first.',
].join('\n')

// The reader the pruned text serves, by where the text lives.
const readerFor = (target) =>
  target === 'docs/wf-solver/backlog.md' ? 'the user'
    : target.startsWith('.claude/roles/') ? 'the handbook agent that carries this file as its role, with the docs in its system prompt'
      : 'a future solver session that reads the file through `uv run python scripts/context.py` to write a Souffle solver'

const fixAndPruneTask = (groups, ruled) => [
  fixTask(groups),
  '',
  'Work in two steps: the fix, under the fix role, then the prune, under the prune role, over the diff your fix made.',
  'The reader of each file, for the prune step:',
  '',
  ...groups.map(g => `    ${g.target}: ${readerFor(g.target)}`),
  '',
  ...(ruled ? ['The user ruled for these fixes. The prune keeps the rule each edit states.', ''] : []),
  'The prune step takes the edits above as the edits the diff was meant to make.',
  'Leave each `diff_path` holding the diff as the prune step left it.',
  'Report both steps. The `diff` field carries the fix diff, then the pruned diff. The `notes` field carries one line per cut, and the meaning before and after of each rule the diff touches.',
].join('\n')

const verifyTask = (made) => [
  `Verify the changes to ${made.target}.`,
  '',
  ...made.groups.map(g => [
    `${g.target} — the edits its changes were meant to make:`,
    JSON.stringify(g.fixes.map(f => f.edit), null, 2),
    `Its diff is under ${diffPath(g.target)}.`,
    '',
  ].join('\n')),
  `The fix diff:\n${made.edit.diff}`,
  ...(made.chain && made.chain.length
    ? ['', 'The other code targets of this run changed the same tree. Their diffs are under these paths:', ...made.chain.map(p => `    ${p}`)]
    : []),
].join('\n')

const checksTask = () => [
  'Run these three checks over the current tree, in this order:',
  '',
  '    1. `uv run pytest -q`',
  '    2. `uv run python scripts/context.py > /dev/null; echo exit=$?`',
  '    3. the whole corpus, in chunks',
  '',
  'Run each one to completion. A failure in an earlier check does not stop a later one.',
  'For the third check, list the stems with `ls programs/solvers/*.dl | xargs -n1 basename | sed \'s/\\.dl$//\'`, then split that list into chunks of 100 stems. Run each chunk as `uv run python scripts/run_dl.py run <the chunk\'s stems>`, one Bash call per chunk, in the foreground, with the Bash tool\'s `timeout` set to 600000. Run the chunks one after another. Sum the chunks\' summary lines into one `N/M` count, and collect every failing solver with its failure text.',
  'Report each command: whether it passed, its summary line verbatim, and every failure in full.',
  'For the whole-corpus run, report its summary line and the solvers that failed.',
  'Report a failure as a failure. Do not attribute it to other work, and do not report it as passing.',
  'Change no file. Never run a git command that changes state: no `stash`, `checkout`, `reset`, `rm`, or `commit`.',
].join('\n')

const sweepTask = (stems) => [
  'Sweep the parameter values of these solvers:',
  '',
  ...stems.map(s => `    ${s}`),
  '',
  'Run `mkdir -p .scratch/retro/sweep` first. Then take one stem at a time.',
  'A stem whose `.scratch/retro/sweep/<stem>.txt` exists is already swept: read that file for its sweep output.',
  'A stem whose file is missing is swept now: run `uv run python scripts/run_dl.py sweep <stem> > .scratch/retro/sweep/<stem>.txt 2>&1`, then read that file. A sweep takes minutes, so run it as its own Bash call, in the foreground, with the Bash tool\'s `timeout` set to 600000.',
  'A sweep line leaves its parameter open when it carries one of these four clauses:',
  '',
  '    `test refutes [...] — a determination from train alone could pick it`',
  '    `differ from stored in kind, so the pairs do not fix this parameter`',
  '    `fit and are smaller than stored`',
  '    `the cases admit different values`',
  '',
  'A line whose extra values only `reproduce the stored outputs on test too` leaves nothing open.',
  'A line cut by the time budget, and a line that names a partial scope, leave nothing open on that ground alone.',
  'Report per stem the parameters whose line carries one of those four clauses, each with that line verbatim. A stem with no such parameter reports an empty list.',
  'Change no file outside `.scratch/retro/sweep/`. Never run a git command that changes state: no `stash`, `checkout`, `reset`, `rm`, or `commit`.',
].join('\n')

const sweepLinesTask = (sweeps) => [
  'Mark these solvers. Each entry names one solver and the parameters its sweep leaves open, each with the sweep\'s line for it.',
  '',
  JSON.stringify(sweeps.map(s => ({ task_id: s.stem, params: s.params })), null, 2),
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

const fixRole = (kind) => (kind === 'solver' ? 'solver' : 'retro-fix')

// A stage's task under its role: the role text, then the brief, so the agent
// has its role before its first action. The texts come from args. A retro
// stage rules on the theory as well as the code, so the agent is the handbook
// variant that carries principles.md unabridged.
const HANDBOOK = { agentType: 'handbook-principles' }
const ROLES = (args && args.roles) || {}
const roleOf = (name) => {
  const text = ROLES[name]
  if (typeof text !== 'string' || !text.trim()) throw new Error(`args.roles[${JSON.stringify(name)}] is missing: pass the text of .claude/roles/${name}.md`)
  return text.trim()
}
const asRole = (name, task) => `${roleOf(name)}\n\n---\n\nYour brief:\n\n${task}`
// A prose target takes the fix role, then the prune role over its own diff.
const asFixAndPrune = (task) =>
  `${roleOf('retro-fix')}\n\n---\n\nThe second step, over the diff your fix made:\n\n${roleOf('retro-prune')}\n\n---\n\nYour brief:\n\n${task}`

// The roles a run reaches, by the run it is.
const READ_ROLES = ['retro-read', 'retro-check', 'retro-review']
const FIX_ROLES = ['retro-fix', 'solver', 'retro-prune', 'retro-verify']
// The sweep lines stage runs in a full run alone.
const SWEEP_ROLES = ['retro-sweep']
const rolesNeeded = () => args && args.fixes ? FIX_ROLES
  : args && args.dry ? READ_ROLES
    : [...READ_ROLES, ...FIX_ROLES, ...SWEEP_ROLES]

// A unit of fix work: the files one agent takes, with the fixes of each.
const unit = (groups, kind) => ({
  groups,
  kind,
  target: groups.map(g => g.target).join(', '),
  targets: groups.map(g => g.target),
  fixes: groups.flatMap(g => g.fixes),
})

async function fixStage(fixes, ruled = false) {
  const targets = [...byKey(fixes, f => f.target)].map(([target, fs]) => ({ target, fixes: fs, kind: kindOf(fs) }))
  const code = targets.filter(t => t.kind === 'code').map(t => unit([t], 'code'))
  const prose = targets.filter(t => t.kind === 'prose')
  // Every prose target of a round goes to one agent, so the round pays the
  // per-agent cost once.
  const rest = [
    ...(prose.length ? [unit(prose, 'prose')] : []),
    ...targets.filter(t => t.kind !== 'code' && t.kind !== 'prose').map(t => unit([t], t.kind)),
  ]

  const makeFix = async (u) => {
    const prompt = u.kind === 'prose'
      ? asFixAndPrune(fixAndPruneTask(u.groups, ruled))
      : asRole(fixRole(u.kind), fixTask(u.groups))
    const edit = await agent(prompt, { label: `fix:${u.target}`, phase: 'Fix', schema: EDIT_SCHEMA, ...HANDBOOK })
    if (!edit) return null
    return { target: u.target, targets: u.targets, groups: u.groups, kind: u.kind, ids: u.fixes.map(f => f.id), fixes: u.fixes, edit, chain: null }
  }

  // Every code target edits the same tree and the same suite, so they go one at
  // a time, each starting from the tree the previous one left. Each verify pass
  // judges the tests of the whole chain, so it takes the paths of the other
  // code diffs.
  const codeChain = async () => {
    const made = []
    for (const u of code) {
      const m = await makeFix(u)
      if (m) made.push(m)
    }
    if (made.length > 1) {
      for (const m of made) m.chain = made.filter(o => o !== m).map(o => diffPath(o.target))
    }
    return made
  }

  const otherTargets = async () => parallel(rest.map(u => () => makeFix(u)))

  const [others, coded] = await parallel([otherTargets, codeChain])
  return [...(others || []), ...(coded || [])].filter(Boolean)
}

async function verifyStage(made, runChecks = true) {
  const findings = (await parallel(made.map(m => async () => {
    const v = await agent(asRole('retro-verify', verifyTask(m)), { label: `verify:${m.target}`, phase: 'Verify', schema: VERIFY_SCHEMA, ...HANDBOOK })
    return v && { target: m.target, targets: m.targets, ...v }
  }))).filter(Boolean)
  const checks = runChecks
    ? await agent(checksTask(), { label: 'checks', phase: 'Verify', schema: CHECKS_SCHEMA, model: 'sonnet', effort: 'low' })
    : null
  const failed = checks ? checks.checks.filter(c => !c.passed) : []
  log(`${findings.reduce((n, f) => n + f.findings.length, 0)} verify findings; ${runChecks ? `${failed.length} failing checks` : 'checks skipped, no code target changed'}`)
  return { findings, checks: checks ? checks.checks : [] }
}

// The window names the solvers the sessions wrote. One agent sweeps each of
// them, so a parameter value the pairs leave open is reported beside the calls.
async function sweepStage(stems) {
  if (!stems.length) return null
  const sweep = await agent(sweepTask(stems), { label: 'sweep', phase: 'Sweep', schema: SWEEP_SCHEMA, model: 'sonnet', effort: 'low' })
  if (!sweep) return null
  log(`${sweep.sweeps.filter(s => s.params.length).length} of ${sweep.sweeps.length} swept solvers hold a parameter the pairs leave open`)
  return sweep.sweeps
}

// A solver the sweep leaves a parameter open in returns to draft and takes one
// review line per open parameter.
async function sweepLinesStage(sweeps) {
  const open = (sweeps || []).filter(s => s.params && s.params.length)
  if (!open.length) return null
  const lines = await agent(asRole('retro-sweep', sweepLinesTask(open)), { label: 'sweep-lines', phase: 'Sweep', schema: SWEEP_LINES_SCHEMA, ...HANDBOOK })
  if (!lines) return null
  log(`${lines.solvers.reduce((n, s) => n + s.lines.length, 0)} review lines over ${lines.solvers.length} solvers`)
  return lines.solvers
}

// The kind a target takes, by where it sits.
const kindForTarget = (target) =>
  target.startsWith('docs/wf-solver/proposals/') ? 'entry'
    : target.startsWith('programs/solvers/') ? 'solver'
      : target.endsWith('.md') ? 'prose'
        : 'code'

// A verify pass fixes what it finds in its own target and leaves a finding
// that needs another file, naming that file. Each such finding becomes a fix on
// that file, and the fixes that changed something are verified like the first
// round. It starts no round of its own.
async function followupStage(verify) {
  const fixes = (verify ? verify.findings : []).flatMap(v =>
    v.findings.map(f => ({ f, target: (f.other_file || '').trim() }))
      .filter(({ target }, i, xs) => target && !(v.targets || [v.target]).includes(target) && xs.findIndex(x => x.target === target) === i)
      .map(({ f, target }) => ({
        id: `verify:${v.target}`,
        kind: kindForTarget(target),
        target,
        edit: `A verify pass over ${v.target} found this and left it: ${f.finding} ${f.fixed || ''}`.trim(),
      })))
  if (!fixes.length) return null
  log(`${fixes.length} follow-up fixes from the verify findings`)
  phase('Fix')
  const made = await fixStage(fixes, true)
  phase('Verify')
  // A fix that returned an empty diff changed nothing, so it takes no verify
  // pass. The checks run only over a code change.
  const changed = made.filter(m => (m.edit.diff || '').trim())
  const codeChanged = changed.some(m => m.kind === 'code')
  log(`${changed.length} of ${made.length} follow-up fixes changed a file`)
  return { fixes: made, verify: changed.length ? await verifyStage(changed, codeChanged) : null }
}

const missing = rolesNeeded().filter(name => typeof ROLES[name] !== 'string' || !ROLES[name].trim())
if (missing.length) return { error: `args.roles is missing ${missing.join(', ')}. Pass each role's text from .claude/roles/<name>.md under args.roles.` }

if (args && args.fixes) {
  phase('Fix')
  const made = await fixStage(args.fixes, true)
  phase('Verify')
  const verify = await verifyStage(made)
  const followups = await followupStage(verify)
  return { fixes: made.filter(m => m.kind !== 'entry'), entries: made.filter(m => m.kind === 'entry'), verify, followups }
}

phase('Read')
const read = await agent(asRole('retro-read', readTask()), { label: 'read', phase: 'Read', schema: ISSUES_SCHEMA, ...HANDBOOK })
if (!read) return { error: 'read agent returned nothing' }
const issues = read.issues
// The sweep runs beside the check and review stages, and is awaited before any fix.
const sweeping = (args && args.dry) ? null : sweepStage([...new Set(issues.flatMap(i => i.tasks || []))])
log(`${issues.length} issues from the window; ${read.borderline_drops.length} borderline drops`)
if (!issues.length) return { tally: { issues: 0 }, borderline_drops: read.borderline_drops }

phase('Check')
const groups = byKey(issues, i => i.group)
const checks = (await parallel([...groups].map(([group, gi]) => () =>
  agent(asRole('retro-check', checkTask(group, gi)), { label: `check:${group}`, phase: 'Check', schema: CHECK_SCHEMA, ...HANDBOOK })
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
  .map(r => ({ id: r.id, default: 'drop', tier: r.tier, basis: r.basis, for: r.for, against: r.against,
               changed_how: r.changed_how, fixes: refs([r.fixes?.[0]]) }))
log(`${closed.length} closed, ${calls.length} dropped, ${open.length} open`)

phase('Review')
if (open.length) {
  // A review the fable safeguard refuses returns nothing, and opus reruns it.
  const reviewOpts = { label: 'review', phase: 'Review', schema: REVIEW_SCHEMA, ...HANDBOOK }
  const review = await agent(asRole('retro-review', reviewTask(open)), { ...reviewOpts, model: 'fable' })
    || await agent(asRole('retro-review', reviewTask(open)), { ...reviewOpts, model: 'opus' })
  for (const r of review ? review.results : []) {
    const o = open.find(o => o.id === r.id)
    const fixes = r.fixes?.length ? refs(r.fixes) : (r.default === 'replace' ? [] : refs([o?.fixes?.[0]]))
    calls.push({ id: r.id, default: r.default, tier: r.tier, reason: r.reason, basis: r.basis,
                 for: r.for, against: r.against, options: r.options,
                 covers: r.covers, fixes, changed_work: o?.changed_work, changed_how: o?.changed_how })
  }
}
// a tier-4 call is presented and not made
const stands = calls.filter(c => (c.default === 'fix' || c.default === 'replace') && c.fixes.length && c.tier !== 4)
// one agent per general fix: fixes that several replaced issues point at collapse to one
// A fix carries its issue's tasks: a fix over a principle writes a review line into each of their draft solvers.
const fixes = [...byKey(stands.flatMap(c => c.fixes.map(f => ({ ...f, id: c.id, tasks: issueById.get(c.id)?.tasks || [] }))), f => `${f.target}\n${f.edit}`)]
  .map(([, fs]) => ({ ...fs[0], id: fs.map(f => f.id).join(','), tasks: [...new Set(fs.flatMap(f => f.tasks))] }))
const tally = { issues: issues.length, closed: closed.length }
for (const c of calls) tally[c.default] = (tally[c.default] || 0) + 1
log(`${fixes.length} fixes to make`)

phase('Fix')
const dry = args && args.dry
// The sweep overlaps the reading stages only: the fix and verify stages run solvers under a CPU limit.
const sweep = sweeping ? await sweeping : null
const sweepLines = sweep ? await sweepLinesStage(sweep) : null
const made = fixes.length && !dry ? await fixStage(fixes) : []

phase('Verify')
const verify = made.length ? await verifyStage(made) : null
const followups = verify ? await followupStage(verify) : null


return {
  tally,
  dry: dry ? fixes : undefined,
  closed,
  calls: calls.map(withIssue),
  fixes: made.filter(m => m.kind !== 'entry'),
  entries: made.filter(m => m.kind === 'entry'),
  verify,
  followups,
  sweep,
  sweep_lines: sweepLines,
  borderline_drops: read.borderline_drops,
}
