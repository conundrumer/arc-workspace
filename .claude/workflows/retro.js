export const meta = {
  name: 'retro',
  description: 'Rule on what console sessions called out beyond their own tasks: read, check, review, fix, resolve, clean up, verify, sweep.',
  phases: [
    { title: 'Read', detail: 'one agent turns the window into issues' },
    { title: 'Sweep', detail: 'one agent sweeps the parameter values of every solver the window names, beside the check and review stages; then one agent writes a review line into each solver a parameter stays open in', model: 'sonnet' },
    { title: 'Check', detail: 'one agent per group of issues: closed, dropped, or open with candidate fixes' },
    { title: 'Review', detail: 'one agent asks the two questions over every open issue and takes a default', model: 'fable' },
    { title: 'Fix', detail: 'code targets one at a time, every prose target in one agent that fixes then prunes, every other target in parallel' },
    { title: 'Resolve', detail: 'one agent per solver that took a review line in this run, which acts on the line and writes its report' },
    { title: 'Consistency', detail: 'one agent groups the acted-on review lines by the rule that decides each; then one agent per group reads its solvers side by side and reports where they read that rule differently' },
    { title: 'Cleanup', detail: 'one agent per solver the run wrote, which runs Simplify then Prune over it' },
    { title: 'Verify', detail: 'one agent per changed target, one agent for the prose targets together, one agent for the checks, then one round over the other files those findings name', model: 'sonnet' },
  ],
}

// Each stage runs a handbook agent under a role from .claude/roles/: the
// agent the role's first line names, `handbook` with no such line. Each role
// carries its stage's procedure, and a task opens with the role text, then
// the brief. The checks step runs a general-purpose
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
//   { fixes: [...] }   second run after the user's rulings: Fix, Resolve, Consistency, Cleanup, and
//                      Verify, over the given fixes.
//                      Each fix: { id, kind, target, edit, tasks }: a call's id with one entry
//                      per target, as the first run returned them under calls[].fixes, and the
//                      issue's task ids, which a fix over a principle writes a review line into.
//                      The fixes are ruled: the prune step keeps their substance.
//   { resolve: [...] } Resolve over the given task ids, whatever review lines their headers hold.
//                      It reaches Consistency and Cleanup after it, and no other stage.
//   { sweep: [...] }   in a resolve run alone: the solver stems the run sweeps first. The sweep
//                      writes its review lines, then Resolve takes those solvers beside the ones
//                      args.resolve names, which may be an empty list. The returned object carries
//                      the sweep and the sweep lines.

// The call's discretion level: how much room the default took beyond what the
// grounds determine. A level-4 fix is not made in the first run.
const TIER = {
  type: 'integer',
  minimum: 1,
  maximum: 4,
  description: '1: a ground states it outright, or it fixes a bug; 2: a ground determines it through a reading of the user\'s intent or of an existing convention, and that reading admits no other; 3: the grounds permit more than one option, and the default is defensible from them; 4: no ground bears on it',
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
    illustration: { type: 'string', description: 'a fix to docs/wf-solver/principles.md at level 3: for each cited task, the case sets under each reading and a witness input where the readings differ' },
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
                choice: { type: 'string', description: 'the reading\'s one-word label' },
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
    review_lines: {
      type: 'array',
      description: 'the draft solvers this fix wrote a review line into; empty when it wrote none',
      items: {
        type: 'object',
        properties: {
          task_id: { type: 'string' },
          line: { type: 'string', description: 'the review line, verbatim' },
        },
        required: ['task_id', 'line'],
      },
    },
    notes: { type: 'string' },
  },
  required: ['diff', 'verification', 'review_lines'],
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
            description: 'the parameters the sweep leaves open: the line carries one of the clauses the brief lists',
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

const RESOLVE_SCHEMA = {
  type: 'object',
  properties: {
    acted: { type: 'array', items: { type: 'string' }, description: 'the review lines acted on, verbatim' },
    left: { type: 'array', items: { type: 'string' }, description: 'the review lines left in the header, verbatim, each with what is left to do' },
    report: { type: 'string', description: 'the repo-relative path of the report written' },
    diff: { type: 'string', description: 'the unified diff of the change to the solver, verbatim; empty when it changed nothing' },
    verification: { type: 'string', description: 'what was run and its result: the solver, the lint, and the audit' },
  },
  required: ['acted', 'left', 'report', 'diff', 'verification'],
}

const CLEANUP_SCHEMA = {
  type: 'object',
  properties: {
    changed: { type: 'string', description: 'what changed, or `no change` with the reason' },
    run: { type: 'string', description: 'the run result after the pass, and any failure or finding the first run already had' },
    concerns: { type: 'array', items: { type: 'string' }, description: 'what looks wrong in the hypothesis and needs the caller\'s ruling' },
  },
  required: ['changed', 'run', 'concerns'],
}

const GROUP_SCHEMA = {
  type: 'object',
  properties: {
    assignments: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          task_id: { type: 'string' },
          line: { type: 'string', description: 'the review line, verbatim' },
          group: { type: 'string', description: 'a short kebab-case id for the rule the line falls under; lines one rule decides share it' },
          rule: { type: 'string', description: 'the rule that decides the line, as doc and section' },
        },
        required: ['task_id', 'line', 'group', 'rule'],
      },
    },
  },
  required: ['assignments'],
}

const CONSISTENCY_SCHEMA = {
  type: 'object',
  properties: {
    misgrouped: {
      type: 'array',
      description: 'the lines of the group that its rule does not decide',
      items: {
        type: 'object',
        properties: {
          task_id: { type: 'string' },
          line: { type: 'string' },
          rule: { type: 'string', description: 'the rule that decides the line, as doc and section' },
        },
        required: ['task_id', 'line', 'rule'],
      },
    },
    divergences: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          point: { type: 'string', description: 'the point the solvers\' review lines share' },
          solvers: { type: 'array', items: { type: 'string' }, description: 'the task ids the entry holds between' },
          principled: { type: 'boolean', description: 'whether the tasks differ in a way a rule of the docs names' },
          rule: { type: 'string', description: 'the doc section of the rule the entry rests on' },
          reading: { type: 'string', description: 'the reading the docs should force; `consistent` for a group with no divergence' },
          wording: { type: 'string', description: 'the passage that leaves that reading open; empty when the divergence is principled' },
          form: { type: 'string', description: 'the form the solvers should agree on' },
          ground: { type: 'string', description: 'what the judgment rests on: the passage read, by doc and section' },
        },
        required: ['point', 'solvers', 'principled', 'rule', 'reading', 'wording', 'form', 'ground'],
      },
    },
  },
  required: ['divergences', 'misgrouped'],
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

// The files a fix diff changed beside the brief's targets: a code fix writes a
// test with its change, so that test file is in scope too.
const diffFiles = (made) => [...new Set(
  [...(made.edit.diff || '').matchAll(/^\+\+\+ b\/(\S+)/gm)].map(m => m[1])
)].filter(p => !made.targets.includes(p))

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
  ...(diffFiles(made).length
    ? ['', 'The fix diff also changed these files. They are in scope beside the target: fix what you find in them.', ...diffFiles(made).map(p => `    ${p}`)]
    : []),
  ...(made.chain && made.chain.length
    ? ['', 'The other code targets of this run changed the same tree. Their diffs are under these paths:', ...made.chain.map(p => `    ${p}`)]
    : []),
].join('\n')

const checksTask = () => [
  'Run these checks over the current tree, in this order:',
  '',
  '    1. `uv run pytest -q`',
  '    2. `uv run python scripts/context.py > /dev/null; echo exit=$?`',
  '    3. the whole corpus, in chunks',
  '',
  'Run each one to completion. A failure in an earlier check does not stop a later one.',
  'For the corpus check, list the stems with `ls programs/solvers/*.dl | xargs -n1 basename | sed \'s/\\.dl$//\'`, then split that list into chunks of 100 stems. Run each chunk as `uv run python scripts/run_dl.py run <the chunk\'s stems>`, one Bash call per chunk, in the foreground, with the Bash tool\'s `timeout` set to 600000. Run the chunks one after another. Sum the chunks\' summary lines into one `N/M` count, and collect every failing solver with its failure text.',
  'Report each command: whether it passed, its summary line verbatim, and every failure in full.',
  'For the whole-corpus run, report its summary line and the solvers that failed.',
  'Report a failure as a failure. Do not attribute it to other work, and do not report it as passing.',
  'Change no file. Never run a git command that changes state.',
].join('\n')

const sweepTask = (stems) => [
  'Sweep the parameter values of these solvers:',
  '',
  ...stems.map(s => `    ${s}`),
  '',
  'Run `mkdir -p .scratch/retro/sweep` first. Then take one stem at a time.',
  'A stem whose `.scratch/retro/sweep/<stem>.txt` exists is already swept: read that file for its sweep output.',
  'A stem whose file is missing is swept now: run `uv run python scripts/run_dl.py sweep <stem> > .scratch/retro/sweep/<stem>.txt 2>&1`, then read that file. A sweep takes minutes, so run it as its own Bash call, in the foreground, with the Bash tool\'s `timeout` set to 600000.',
  'A sweep line leaves its parameter open when it carries one of these clauses:',
  '',
  '    `test refutes [...] — a determination from train alone could pick it`',
  '    `differ from stored in kind, so the pairs do not fix this parameter`',
  '    `fit and are smaller than stored`',
  '    `the cases admit different values`',
  '',
  'A line whose extra values only `reproduce the stored outputs on test too` leaves nothing open.',
  'A line cut by the time budget, and a line that names a partial scope, leave nothing open on that ground alone.',
  'Report per stem the parameters whose line carries one of those clauses, each with that line verbatim. A stem with no such parameter reports an empty list.',
  'Change no file outside `.scratch/retro/sweep/`. Never run a git command that changes state.',
].join('\n')

// The console lists every `.md` under a task's report directory as a stage
// report, so a resolve report stands beside the task's session reports.
const REPORT_DIR = 'tools/console/state/reports'

const solverTarget = (taskId) => `programs/solvers/${taskId}.dl`

const resolveTask = (taskId) => [
  `Act on the review lines in programs/solvers/${taskId}.dl.`,
  '',
  'Every review line in the solver\'s header names a point to act on, except a line whose kind marks it as waiting on the user; `cite` is such a kind today. Work each line per the procedure\'s operations, as they apply to it.',
  'Remove each line you finished. Leave a line you did not finish; when the solver carries no `// draft` line, return it to draft first: `uv run python -c "import sys; sys.path.insert(0, \'tools/console\'); from solver_console import solvers; solvers.mark_draft(\'<task_id>\'); solvers.withdraw_citations(\'<task_id>\')"`. A review line whose kind waits on the user is not yours: leave it as it is.',
  'Run the solver, the lint, and the audit.',
  `Write your report, in the form the Review operation gives, to ${REPORT_DIR}/${taskId}/retro.md. Create the directory first. The run, lint, and audit output go in your returned verification, not in the report.`,
  'Never run a git command that changes state.',
].join('\n')

const cleanupTask = (taskId, source) => [
  `Run Simplify, then Prune, over the whole of programs/solvers/${taskId}.dl.`,
  source,
  'Scratch goes under `.scratch/<task_id>/`.',
].join('\n')

// The seed key of a review line: its kind, its head, and the start of its point.
const seedKey = (line) => {
  const m = /^\/\/\s*review\s+(\w+):\s*(.*?)\s+—\s+(.*)$/.exec(line)
  return m ? `${m[1]}|${m[2]}|${m[3].slice(0, 40)}` : line.slice(0, 60)
}

const groupTask = (lines) => [
  'Group these review lines. Each entry names the solver the line stood in, the line, and a seed key from its text.',
  '',
  JSON.stringify(lines, null, 2),
].join('\n')

const consistencyTask = (group, rule, members) => [
  `Compare these solvers, the group \`${group}\`, under the rule ${rule}. Each entry names one solver, its report, and the review lines the Resolve stage acted on in it under that rule.`,
  `Scratch goes under \`.scratch/retro/consistency/${group}/\`.`,
  '',
  JSON.stringify(members.map(r => ({
    task_id: r.task_id,
    solver: r.target,
    report: `${REPORT_DIR}/${r.task_id}/retro.md`,
    acted: r.acted,
  })), null, 2),
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
// has its role before its first action. The texts come from args. A role's
// first line may name its agent. The spawn takes the agent from that line
// and the prompt from the rest.
const AGENT_LINE = /^Agent: (\S+)\n+/
const ROLES = (args && args.roles) || {}
const roleFile = (name) => {
  const text = ROLES[name]
  if (typeof text !== 'string' || !text.trim()) throw new Error(`args.roles[${JSON.stringify(name)}] is missing: pass the text of .claude/roles/${name}.md`)
  return text.trim()
}
const roleOf = (name) => roleFile(name).replace(AGENT_LINE, '')
const agentOf = (name) => {
  const m = roleFile(name).match(AGENT_LINE)
  return { agentType: m ? m[1] : 'handbook' }
}
const asRole = (name, task) => `${roleOf(name)}\n\n---\n\nYour brief:\n\n${task}`
// A prose target takes the fix role, then the prune role over its own diff.
const asFixAndPrune = (task) =>
  `${roleOf('retro-fix')}\n\n---\n\nThe second step, over the diff your fix made:\n\n${roleOf('retro-prune')}\n\n---\n\nYour brief:\n\n${task}`

// The roles a run reaches, by the run it is.
const READ_ROLES = ['retro-read', 'retro-check', 'retro-review']
const FIX_ROLES = ['retro-fix', 'solver', 'retro-prune', 'retro-verify', 'retro-group', 'retro-consistency', 'cleanup']
// The sweep lines stage runs in a full run, and in a resolve run given stems to sweep.
const SWEEP_ROLES = ['retro-sweep']
const RESOLVE_ROLES = ['solver', 'retro-group', 'retro-consistency', 'cleanup']
const rolesNeeded = () => args && args.resolve ? [...RESOLVE_ROLES, ...(args.sweep ? SWEEP_ROLES : [])]
  : args && args.fixes ? FIX_ROLES
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
    const edit = await agent(prompt, { label: `fix:${u.target}`, phase: 'Fix', schema: EDIT_SCHEMA, ...agentOf(u.kind === 'prose' ? 'retro-fix' : fixRole(u.kind)) })
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
    const v = await agent(asRole('retro-verify', verifyTask(m)), { label: `verify:${m.target}`, phase: 'Verify', schema: VERIFY_SCHEMA, ...agentOf('retro-verify') })
    return v && { target: m.target, targets: [...m.targets, ...diffFiles(m)], ...v }
  }))).filter(Boolean)
  const checks = runChecks
    ? await agent(checksTask(), { label: 'checks', phase: 'Verify', schema: CHECKS_SCHEMA, model: 'sonnet', effort: 'low' })
    : null
  const failed = checks ? checks.checks.filter(c => !c.passed) : []
  log(`${findings.reduce((n, f) => n + f.findings.length, 0)} verify findings; ${runChecks ? `${failed.length} failing checks` : 'checks skipped'}`)
  return { findings, checks: checks ? checks.checks : [] }
}

// The items one agent takes, in order.
const chunks = (items, size) => {
  const out = []
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size))
  return out
}

// The label one agent of a chunked stage carries.
const chunkLabel = (name, i, n) => (n > 1 ? `${name}:${i + 1}/${n}` : name)

// The window names the solvers the sessions wrote. The stems go in chunks of
// at most 25, one agent per chunk, so a parameter value the pairs leave open is
// reported beside the calls.
async function sweepStage(stems) {
  if (!stems.length) return null
  const parts = chunks(stems, 25)
  const done = (await parallel(parts.map((part, i) => () =>
    agent(sweepTask(part), { label: chunkLabel('sweep', i, parts.length), phase: 'Sweep', schema: SWEEP_SCHEMA, model: 'sonnet', effort: 'low' })
  ))).filter(Boolean)
  if (!done.length) return null
  const sweeps = done.flatMap(d => d.sweeps)
  log(`${sweeps.filter(s => s.params.length).length} of ${sweeps.length} swept solvers hold a parameter the pairs leave open`)
  return sweeps
}

// A solver the sweep leaves a parameter open in returns to draft and takes one
// review line per open parameter. The solvers go in chunks of at most 20, one
// agent per chunk.
async function sweepLinesStage(sweeps) {
  const open = (sweeps || []).filter(s => s.params && s.params.length)
  if (!open.length) return null
  const parts = chunks(open, 20)
  const done = (await parallel(parts.map((part, i) => () =>
    agent(asRole('retro-sweep', sweepLinesTask(part)), { label: chunkLabel('sweep-lines', i, parts.length), phase: 'Sweep', schema: SWEEP_LINES_SCHEMA, ...agentOf('retro-sweep') })
  ))).filter(Boolean)
  if (!done.length) return null
  const solvers = done.flatMap(d => d.solvers)
  log(`${solvers.reduce((n, s) => n + s.lines.length, 0)} review lines over ${solvers.length} solvers`)
  return solvers
}

// What the docs settle is settled in this run: a draft that took a review line
// here acts on it here. One agent per solver, as the solver fixes of the fix
// stage run.
async function resolveStage(taskIds) {
  const stems = [...new Set(taskIds.map(s => (s || '').trim()))].filter(Boolean)
  if (!stems.length) return null
  const done = (await parallel(stems.map(id => async () => {
    const r = await agent(asRole('solver', resolveTask(id)), { label: `resolve:${id}`, phase: 'Resolve', schema: RESOLVE_SCHEMA, ...agentOf('solver') })
    return r && { task_id: id, target: solverTarget(id), ...r }
  }))).filter(Boolean)
  log(`${done.reduce((n, r) => n + r.acted.length, 0)} review lines acted on over ${done.length} solvers; ${done.reduce((n, r) => n + r.left.length, 0)} left`)
  return done
}

// The Resolve stage takes each solver on its own. One agent then groups the
// lines it acted on by the rule that decides each, and one agent per group
// reads that group's solvers side by side, so a point two of them read
// differently is reported as a divergence. A group of one solver runs no
// agent, and a line the group's rule does not decide comes back as misgrouped.
async function consistencyStage(resolved) {
  const acted = (resolved || []).filter(r => r && (r.acted || []).length)
  if (acted.length < 2) return null
  const lines = acted.flatMap(r => r.acted.map(line => ({ task_id: r.task_id, line, seed: seedKey(line) })))
  const g = await agent(asRole('retro-group', groupTask(lines)), { label: 'group', phase: 'Consistency', schema: GROUP_SCHEMA, ...agentOf('retro-group') })
  if (!g) return null
  const groups = [...byKey(g.assignments, a => a.group)].map(([id, as]) => ({ id, rule: as[0].rule, lines: as }))
  const runs = groups.filter(gr => new Set(gr.lines.map(a => a.task_id)).size >= 2)
  log(`${groups.length} groups over ${lines.length} lines; ${runs.length} hold two or more solvers`)
  const byId = new Map(acted.map(r => [r.task_id, r]))
  const results = (await parallel(runs.map((gr, i) => async () => {
    const ids = [...new Set(gr.lines.map(a => a.task_id))]
    const members = ids.map(t => ({ ...byId.get(t), acted: gr.lines.filter(a => a.task_id === t).map(a => a.line) }))
    const r = await agent(asRole('retro-consistency', consistencyTask(gr.id, gr.rule, members)), { label: chunkLabel('consistency', i, runs.length), phase: 'Consistency', schema: CONSISTENCY_SCHEMA, ...agentOf('retro-consistency') })
    return r && { group: gr.id, ...r }
  }))).filter(Boolean)
  const divergences = results.flatMap(r => r.divergences.map(d => ({ group: r.group, ...d })))
  const misgrouped = results.flatMap(r => (r.misgrouped || []).map(m => ({ group: r.group, ...m })))
  log(`${divergences.filter(d => !d.principled).length} unprincipled of ${divergences.length} consistency entries over ${results.length} groups; ${misgrouped.length} misgrouped lines`)
  return { groups, divergences, misgrouped }
}

// The solvers a run wrote: a solver fix that changed the file, and a resolve
// that changed the file. Each owes the cleanup pass of the procedure.
const cleanupItems = (made, resolved) => {
  const items = new Map()
  for (const m of made || []) {
    if (m.kind !== 'solver' || !(m.edit.diff || '').trim()) continue
    for (const t of m.targets) items.set(t.replace(/^programs\/solvers\/|\.dl$/g, ''), `A solver fix of this run wrote it; its diff is under ${diffPath(t)}.`)
  }
  for (const r of resolved || []) {
    if (!(r.diff || '').trim()) continue
    items.set(r.task_id, `The Resolve stage of this run wrote it; its report is at ${r.report}.`)
  }
  return [...items].map(([task_id, source]) => ({ task_id, source }))
}

// One agent per solver the run wrote.
async function cleanupStage(items) {
  if (!items.length) return null
  const done = (await parallel(items.map(({ task_id, source }) => async () => {
    const r = await agent(asRole('cleanup', cleanupTask(task_id, source)), { label: `cleanup:${task_id}`, phase: 'Cleanup', schema: CLEANUP_SCHEMA, ...agentOf('cleanup') })
    return r && { task_id, target: solverTarget(task_id), ...r }
  }))).filter(Boolean)
  log(`${done.filter(r => !/^no change/i.test(r.changed)).length} of ${done.length} solvers changed in cleanup; ${done.reduce((n, r) => n + r.concerns.length, 0)} concerns`)
  return done
}

// The drafts a run wrote a review line into: the solvers its fixes name, and the
// solvers its sweep lines marked.
const resolveStems = (made, sweepLines) => [
  ...(made || []).flatMap(m => (m.edit.review_lines || []).map(r => r.task_id)),
  ...(sweepLines || []).filter(s => (s.lines || []).length).map(s => s.task_id),
]

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

// The solvers the caller names, whatever their headers hold. A run given stems
// to sweep sweeps them first, and resolves the solvers its lines marked beside
// the ones the caller names.
if (args && args.resolve) {
  const toSweep = (args.sweep || [])
  let sweep = null
  let sweepLines = null
  if (toSweep.length) {
    phase('Sweep')
    sweep = await sweepStage(toSweep)
    sweepLines = await sweepLinesStage(sweep)
  }
  phase('Resolve')
  const resolved = await resolveStage([...args.resolve, ...resolveStems(null, sweepLines)])
  phase('Consistency')
  const consistency = await consistencyStage(resolved)
  phase('Cleanup')
  const cleanup = await cleanupStage(cleanupItems(null, resolved))
  return { tally: null, closed: null, calls: null, fixes: null, entries: null, resolve: resolved,
           consistency, cleanup, verify: null, followups: null, sweep, sweep_lines: sweepLines, borderline_drops: null }
}

if (args && args.fixes) {
  phase('Fix')
  const made = await fixStage(args.fixes, true)
  phase('Resolve')
  const resolved = await resolveStage(resolveStems(made, null))
  phase('Consistency')
  const consistency = await consistencyStage(resolved)
  phase('Cleanup')
  const cleanup = await cleanupStage(cleanupItems(made, resolved))
  phase('Verify')
  const verify = await verifyStage(made)
  const followups = await followupStage(verify)
  return { fixes: made.filter(m => m.kind !== 'entry'), entries: made.filter(m => m.kind === 'entry'), resolve: resolved, consistency, cleanup, verify, followups }
}

phase('Read')
const read = await agent(asRole('retro-read', readTask()), { label: 'read', phase: 'Read', schema: ISSUES_SCHEMA, ...agentOf('retro-read') })
if (!read) return { error: 'read agent returned nothing' }
const issues = read.issues
// The sweep runs beside the check and review stages, and is awaited before any fix.
const sweeping = (args && args.dry) ? null : sweepStage([...new Set(issues.flatMap(i => i.tasks || []))])
log(`${issues.length} issues from the window; ${read.borderline_drops.length} borderline drops`)
if (!issues.length) return { tally: { issues: 0 }, consistency: null, borderline_drops: read.borderline_drops }

phase('Check')
const groups = byKey(issues, i => i.group)
const checks = (await parallel([...groups].map(([group, gi]) => () =>
  agent(asRole('retro-check', checkTask(group, gi)), { label: `check:${group}`, phase: 'Check', schema: CHECK_SCHEMA, ...agentOf('retro-check') })
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
  const reviewOpts = { label: 'review', phase: 'Review', schema: REVIEW_SCHEMA, ...agentOf('retro-review') }
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
// The doc whose fixes wait on the user's ruling, at any level.
const PRINCIPLES = 'docs/wf-solver/principles.md'
// a level-4 call is presented and not made, and so is a fix to PRINCIPLES
const stands = calls.filter(c => (c.default === 'fix' || c.default === 'replace') && c.fixes.length && c.tier !== 4)
// one agent per general fix: fixes that several replaced issues point at collapse to one
// A fix carries its issue's tasks: a fix over a principle writes a review line into each of their draft solvers.
const fixes = [...byKey(stands.flatMap(c => c.fixes.filter(f => f.target !== PRINCIPLES).map(f => ({ ...f, id: c.id, tasks: issueById.get(c.id)?.tasks || [] }))), f => `${f.target}\n${f.edit}`)]
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

phase('Resolve')
const resolved = dry ? null : await resolveStage(resolveStems(made, sweepLines))

phase('Consistency')
const consistency = dry ? null : await consistencyStage(resolved)

phase('Cleanup')
const cleanup = dry ? null : await cleanupStage(cleanupItems(made, resolved))

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
  resolve: resolved,
  consistency,
  cleanup,
  verify,
  followups,
  sweep,
  sweep_lines: sweepLines,
  borderline_drops: read.borderline_drops,
}
