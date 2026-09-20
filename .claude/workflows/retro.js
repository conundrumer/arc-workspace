export const meta = {
  name: 'retro',
  description: 'Rule on what console sessions called out beyond their own tasks: read, check, review, fix, resolve, clean up, verify, sweep.',
  phases: [
    { title: 'Read', detail: 'one agent turns the window into issues' },

    { title: 'Sweep', detail: 'one agent sweeps the parameter values of every solver the window names, beside the check and review stages; then one agent writes a review line into each solver a parameter stays open in', model: 'sonnet' },
    { title: 'Check', detail: 'one agent per group of issues: closed, dropped, or open with candidate fixes' },
    { title: 'Review', detail: 'one agent asks the two questions over every open issue and takes a default', model: 'fable' },
    { title: 'Fix', detail: 'each code target in a worktree of its own, merged into the repo one merge at a time, the prose targets in units of at most five that a Codex session fixes then prunes, every other target in parallel' },
    { title: 'Resolve', detail: 'one agent per solver that took a review line in this run, which acts on the line and writes its report' },
    { title: 'Consistency', detail: 'one agent groups the acted-on review lines by the rule that decides each; then one agent per group reads its solvers side by side and reports where they read that rule differently; then, for a divergence no rule of the docs explains, one agent per solver brings that solver to the group\'s form, and the divergence goes into the run\'s result' },
    { title: 'Cleanup', detail: 'one agent per solver the run wrote, which runs Simplify then Prune over it' },
    { title: 'Verify', detail: 'one agent per unit, which starts as soon as that unit\'s own fix lands, one agent on sonnet for the checks over the whole tree, then one round over the other files those findings name' },
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
// says to pass them. Each stage runs a handbook agent under a role from
// prompts/roles/, and its brief is built in the briefs region below. The
// sweep, the sweep lines, the checks, and each prose unit of the fix stage
// take no role: each runs one command and returns what that command printed.
// This script carries the order, the fan-out, the return schemas, and the
// briefs.
//
// An agent writes the diff of each file it changed to a file under
// `.scratch/retro/diffs/`, and reports the path. A diff never travels through
// a return value, so a later brief names the path and the agent that takes
// that brief reads it.
//
// The prose units of the fix stage run on Codex: the agent of such a unit runs
// `scripts/retro_codex.py`, which hands the unit's brief to one `codex exec`
// session and prints that session's final message. Codex makes the edits.
//
// Each unit of the fix stage is a chain of its own: the verify pass of a unit
// starts as soon as that unit's fix lands, beside the fix of another unit. The
// checks are a barrier after every unit, since they test the combined tree.
//
// A code unit takes a git worktree of the repo at HEAD, so the code units run
// beside each other rather than one at a time. Its fix and its verify pass both
// work in that worktree. `scripts/retro_merge.py` then takes the worktree's
// whole change into the repo and removes the worktree. Two applies on one tree
// can race, so the merges run one at a time, in the order the units reach them.
// A unit whose change the repo refuses runs again on the repo itself, after
// every other merge, one such unit at a time.
//
// args:
//   { roles }          required in every run: the `roles` of `uv run python scripts/context.py
//                      workflow retro`. The script reads no file, so the caller passes the text.
//                      READ_ROLES and FIX_ROLES name the roles each run needs; a missing one
//                      returns an error.
//   {}                 full run; returns every call with its default, for, and against.
//   { dry: true }      full run that stops before Fix and returns the fixes it would make.
//   { fixes: [...] }   second run after the user's rulings: Fix, Resolve, Consistency, Apply, Cleanup,
//                      and Verify, over the given fixes.
//                      Each fix: { id, kind, target, edit, tasks }: a call's id with one entry
//                      per target, as the dry run returned them under `dry`, and the issue's
//                      task ids, which a fix over a principle writes a review line into.
//                      The fixes are ruled: the prune step keeps their substance.
//   { resolve: [...] } Resolve over the given task ids, whatever review lines their headers hold.
//                      It reaches Consistency, the Apply step of that stage, and Cleanup after it, then
//                      the checks under Verify, and no other stage. The returned object carries the
//                      Apply results under `applied`.
//   { sweep: [...] }   in a resolve run alone: the solver stems the run sweeps first. A name that
//                      is not a task id is dropped. The sweep writes its review lines, then Resolve
//                      takes those solvers beside the ones args.resolve names, which may be an
//                      empty list. The returned object carries the sweep and the sweep lines.
//   { worktrees: false }
//                      runs the code units of the fix stage one at a time on the repo itself, for a
//                      tree where a worktree cannot work. Absent or `true`, each code unit takes a
//                      worktree of its own and its change is merged back.
//   { codex: ... }     how the prose units of the fix stage run. The default is a Codex session
//                      under Codex's own model and effort. `false` runs them on a handbook agent
//                      instead; `{ model, effort }` passes those two to Codex. A unit whose Codex
//                      session returns nothing falls back to the handbook agent on its own.

// ---------------------------------------------------------------- schemas

// The return schemas, one per stage. Each description is an `mctx` literal,
// so the check reads its words where they stand.

// The call's discretion level: how much room the default took beyond what the
// grounds determine. A level-4 fix is not made in the first run.
const TIER = { type: 'integer', minimum: 1, maximum: 4 }

const FIX_REF = {
  type: 'object',
  properties: {
    kind: { type: 'string', enum: ['prose', 'code', 'entry', 'solver'] },
    target: { type: 'string', description: mctx`the file the fix edits, repo-relative; for an entry, docs/wf-solver/proposals/<name>.md; for a solver, programs/solvers/<task_id>.dl` },
    edit: { type: 'string', description: mctx`the smallest edit that closes the issue in this file, stated as your role's Procedure requires` },
  },
  required: ['kind', 'target', 'edit'],
}

const FIX_CANDIDATE = {
  type: 'object',
  properties: {
    ...FIX_REF.properties,
    for: { type: 'string' },
    against: { type: 'string' },
    illustration: { type: 'string', description: mctx`the illustration your role's Procedure requires of a level-3 fix to Principles` },
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
          id: { type: 'string', description: mctx`I1, I2, and so on, in count-descending order` },
          group: { type: 'string', description: mctx`the file or the tool the issue is about, as your role's Procedure defines a group` },
          issue: { type: 'string', description: mctx`the issue in one plain sentence, stated as your role's Procedure requires` },
          count: { type: 'integer' },
          tasks: { type: 'array', items: { type: 'string' } },
          quote: { type: 'string', description: mctx`one callout, verbatim` },
        },
        required: ['id', 'group', 'issue', 'count', 'tasks', 'quote'],
      },
    },
    borderline_drops: {
      type: 'array',
      description: mctx`the borderline drops, each as your role's Report gives them`,
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
          closed_by: { type: 'string', description: mctx`closed: the commit or the current text that closes it` },
          tier: { ...TIER, description: mctx`dropped: the drop's discretion level, as your role's Procedure states it` },
          basis: { type: 'string', description: mctx`dropped: the principle, norm, or fact the drop rests on` },
          for: { type: 'string', description: mctx`dropped: what argues for the drop, stated as your role's Procedure requires` },
          against: { type: 'string', description: mctx`dropped: what argues against the drop, stated the same way; empty when nothing does` },
          changed_work: { type: 'boolean', description: mctx`open: whether the issue changed what a session did, or was only noted` },
          changed_how: { type: 'string', description: mctx`open: one sentence on what it caused` },
          fixes: { type: 'array', items: FIX_CANDIDATE, description: mctx`open: the candidate fixes, in the order your role's Procedure gives; dropped: the declined fix` },
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
          default: { type: 'string', enum: ['fix', 'replace', 'drop'], description: mctx`the outcome that holds unless the user rules otherwise` },
          tier: { ...TIER, description: mctx`the call's discretion level, as your role's Procedure states it` },
          reason: { type: 'string', description: mctx`the answer to the two questions, in one or two sentences` },
          basis: { type: 'string', description: mctx`the principle, the norm, or the fact the call rests on` },
          for: { type: 'string', description: mctx`what argues for the default, stated as your role's Procedure requires` },
          against: { type: 'string', description: mctx`what argues against the default, stated the same way; empty when nothing does` },
          options: {
            type: 'array',
            description: mctx`a fix to Principles: each reading of the rule as an option, the default first`,
            items: {
              type: 'object',
              properties: {
                choice: { type: 'string', description: mctx`the reading's one-word label` },
                wording: { type: 'string', description: mctx`the text the file carries under this reading` },
                consequence: { type: 'string', description: mctx`what a session that reads this wording does differently` },
                witness: { type: 'string', description: mctx`a task or a solver where this reading and the others part` },
              },
              required: ['choice', 'wording', 'consequence', 'witness'],
            },
          },
          fixes: { type: 'array', items: FIX_REF, description: mctx`the fix the default calls for, one entry per file it edits` },
          covers: { type: 'array', items: { type: 'string' }, description: mctx`replace: the other issue ids this general fix also closes` },
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
    diffs: {
      type: 'array',
      description: mctx`one entry per file this fix changed, the files the brief names and the others alike; empty when it changed nothing`,
      items: {
        type: 'object',
        properties: {
          file: { type: 'string', description: mctx`the repo-relative path of the changed file` },
          path: { type: 'string', description: mctx`the repo-relative path of the diff file written for it, under .scratch/retro/diffs/` },
        },
        required: ['file', 'path'],
      },
    },
    worktree: { type: 'string', description: mctx`the absolute path of the worktree this fix worked in; empty for a fix that worked in the repo` },
    net_words: { type: 'integer', description: mctx`prose: words added minus words removed` },
    verification: { type: 'string', description: mctx`what was run and its result` },
    review_lines: {
      type: 'array',
      description: mctx`the draft solvers this fix wrote a review line into; empty when it wrote none`,
      items: {
        type: 'object',
        properties: {
          task_id: { type: 'string' },
          line: { type: 'string', description: mctx`the review line, verbatim` },
        },
        required: ['task_id', 'line'],
      },
    },
    notes: { type: 'string' },
  },
  required: ['diffs', 'verification', 'review_lines', 'worktree'],
}

const MERGE_SCHEMA = {
  type: 'object',
  properties: {
    applied: { type: 'boolean', description: mctx`whether the worktree's change went into the repo` },
    files: { type: 'array', items: { type: 'string' }, description: mctx`the repo-relative paths the change covers` },
    conflict: { type: 'string', description: mctx`what git reported when it refused the change; empty when it applied` },
  },
  required: ['applied', 'files', 'conflict'],
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
          finding: { type: 'string', description: mctx`what is wrong, in one or two sentences` },
          fixed: { type: 'string', description: mctx`what the fix for it was, or why it was left` },
          other_file: { type: 'string', description: mctx`the repo-relative path of the file the fix belongs in, when the finding was left for another file; empty otherwise` },
        },
        required: ['kind', 'finding', 'fixed', 'other_file'],
      },
    },
    diff_path: { type: 'string', description: mctx`the repo-relative path of the diff file written for this pass's own changes; empty when it changed nothing` },
    changed: { type: 'boolean', description: mctx`whether this pass changed a file` },
  },
  required: ['findings', 'diff_path', 'changed'],
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
          summary: { type: 'string', description: mctx`the summary line, verbatim` },
          failures: { type: 'string', description: mctx`every failure in full; empty when the check passed` },
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
            description: mctx`the parameters the sweep leaves open`,
            items: {
              type: 'object',
              properties: {
                param: { type: 'string' },
                reported: { type: 'string', description: mctx`what the sweep reported for it, verbatim` },
                line: { type: 'string', description: mctx`the review line to write for it, verbatim` },
              },
              required: ['param', 'reported', 'line'],
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
          lines: { type: 'array', items: { type: 'string' }, description: mctx`the review lines written, verbatim; empty when every line already stood` },
          lint_ok: { type: 'boolean', description: mctx`whether the lint's \`header\` category reports nothing after the change` },
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
    acted: { type: 'array', items: { type: 'string' }, description: mctx`the review lines acted on, verbatim` },
    left: { type: 'array', items: { type: 'string' }, description: mctx`the review lines left in the header, verbatim, each with what is left to do` },
    report: { type: 'string', description: mctx`the repo-relative path of the report written` },
    diff_path: { type: 'string', description: mctx`the repo-relative path of the diff file written for the change to the solver; empty when it changed nothing` },
    changed: { type: 'boolean', description: mctx`whether the solver changed` },
    verification: { type: 'string', description: mctx`what was run and its result: the solver, the lint, and the audit` },
  },
  required: ['acted', 'left', 'report', 'diff_path', 'changed', 'verification'],
}

const CLEANUP_SCHEMA = {
  type: 'object',
  properties: {
    changed: { type: 'string', description: mctx`what changed, or \`no change\` with the reason` },
    run: { type: 'string', description: mctx`the run result after the pass, and the failure or finding your role's Procedure says to report as already there` },
    carried: { type: 'array', items: { type: 'string' }, description: mctx`a file the brief did not name that a carry reached, and what changed in it` },
  },
  required: ['changed', 'run', 'carried'],
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
          line: { type: 'string', description: mctx`the review line, verbatim` },
          group: { type: 'string', description: mctx`the group id for the rule the line falls under, in the form your role's Procedure gives` },
          rule: { type: 'string', description: mctx`the rule that decides the line, as doc and section` },
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
      description: mctx`the lines of the group that its rule does not decide`,
      items: {
        type: 'object',
        properties: {
          task_id: { type: 'string' },
          line: { type: 'string' },
          rule: { type: 'string', description: mctx`the rule that decides the line, as doc and section` },
        },
        required: ['task_id', 'line', 'rule'],
      },
    },
    divergences: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          point: { type: 'string', description: mctx`the point the solvers' review lines share` },
          solvers: { type: 'array', items: { type: 'string' }, description: mctx`the task ids the entry holds between` },
          principled: { type: 'boolean', description: mctx`whether the tasks differ in a way a rule of the docs names` },
          rule: { type: 'string', description: mctx`the doc section of the rule the entry rests on` },
          reading: { type: 'string', description: mctx`the reading the docs should force; \`consistent\` for a group with no divergence` },
          wording: { type: 'string', description: mctx`the passage that leaves that reading open; empty when the divergence is principled` },
          form: { type: 'string', description: mctx`the form the solvers should agree on` },
          ground: { type: 'string', description: mctx`what the judgment rests on: the passage read, by doc and section` },
        },
        required: ['point', 'solvers', 'principled', 'rule', 'reading', 'wording', 'form', 'ground'],
      },
    },
  },
  required: ['divergences', 'misgrouped'],
}


// ---------------------------------------------------------------- tasks

// A path under the diff directory, taken from the text it belongs to, so the
// name holds no separator of its own.
const DIFF_DIR = '.scratch/retro/diffs'
const slug = (text) => text.split('/').join('__').replace(/[^A-Za-z0-9._-]+/g, '-')

// Each fix agent writes its diff to a path taken from the target path, so a
// later brief names that path.
const diffPath = (target) => `${DIFF_DIR}/${slug(target)}.diff`
// A prose target takes a second pass, and its prune step leaves its own diff.
const prunePath = (target) => `${DIFF_DIR}/${slug(target)}__prune.diff`
// A verify pass fixes what it finds, so it leaves a diff of its own.
const verifyPath = (label) => `${DIFF_DIR}/${slug(label)}__verify.diff`
// A resolve pass writes the solver, so it leaves a diff of its own.
const resolvePath = (taskId) => `${DIFF_DIR}/${slug(taskId)}__resolve.diff`
// An apply pass writes the solver beside the resolve pass, so its diff takes a
// path of its own.
const applyPath = (taskId) => `${DIFF_DIR}/${slug(taskId)}__apply.diff`

// The console lists every `.md` under a task's report directory as a stage
// report, so a resolve report stands beside the task's session reports.
const REPORT_DIR = 'tools/console/state/reports'

const solverTarget = (taskId) => `programs/solvers/${taskId}.dl`

// One entry per file: the file, the fixes it takes, and where its diff goes.
// A prose file takes a second path, for the diff of the prune step over it.
const fixEntries = (groups, pruned) => JSON.stringify(
  groups.map(g => ({
    target: g.target,
    diff_path: diffPath(g.target),
    ...(pruned ? { prune_path: prunePath(g.target) } : {}),
    fixes: g.fixes,
  })), null, 2)

// The reader the pruned text serves, by where the text lives.
const readerFor = (target) =>
  target === 'docs/wf-solver/backlog.md' ? 'the user'
    : target.startsWith('prompts/roles/') ? 'the handbook agent that carries this file as its role, with the docs in its system prompt'
      : 'a future solver session that reads the file through `uv run python scripts/context.py` to write a Souffle solver'

// The diff of each file a fix changed beside the brief's targets: a code fix
// writes a test with its change, so that test file is in scope too.
const otherDiffs = (made) => (made.edit.diffs || []).filter(d => d.file && !made.targets.includes(d.file))
const diffFiles = (made) => [...new Set(otherDiffs(made).map(d => d.file))]

// The seed key of a review line: its kind, its head, and the start of its
// point. A line of another form is no review line, and takes no key.
const seedKey = (line) => {
  const m = /^\/\/\s*review\s+(\w+):\s*(.*?)\s+—\s+(.*)$/.exec(line)
  return m ? `${m[1]}|${m[2]}|${m[3].slice(0, 40)}` : null
}

// ---------------------------------------------------------------- briefs

// The brief each stage sends its agent. Each is an `mctx` literal, so the
// check reads its words as the format where they stand. A hole in a literal
// is a name, and the value it takes is computed above it. A fence inside a
// literal takes tildes, since the literal's own delimiter is a backtick.

const ONE_CALL = mctx`- Run it as one Bash call, in the foreground, with the Bash tool's \`timeout\` set to 600000.`
const NO_GIT = mctx`- Never run a git command that changes state.`
const NO_WRITES = mctx`- Change no file. Never run a git command that changes state.`
const RUN_THE_CHECKS = mctx`- Run the solver, the lint, and the audit.`

// The second role of a prose unit, between the two role texts.
const FIX_AND_PRUNE_STEP = mctx`- The second step, over the diff your fix made:`

const readTask = () => mctx`- Read the retro window and return the issues.`

const checkTask = (group, issues) => {
  const list = JSON.stringify(issues, null, 2)
  return mctx`
- Check these issues, all about ${group}.

~~~json
${list}
~~~
`
}

const reviewTask = (open) => {
  const list = JSON.stringify(open, null, 2)
  return mctx`
- Review these open issues and their candidate fixes.

~~~json
${list}
~~~
`
}

const fixOne = (target) => mctx`Make these fixes in ${target}.`
const FIX_MANY = mctx`Make these fixes. Each entry names one file, the fixes that file takes, and the path its diff goes to.`
const fixLead = (groups) => groups.length > 1 ? FIX_MANY : fixOne(groups[0].target)

const fixTask = (groups, pruned = false) => {
  const lead = fixLead(groups)
  const entries = fixEntries(groups, pruned)
  const dir = DIFF_DIR
  return mctx`
- ${lead}

~~~json
${entries}
~~~

- Write the diff of your changes to each file named above, verbatim, to that file's \`diff_path\`. Create the directory first.
- A file you changed that is not named above takes a diff of its own under \`${dir}/\`, at a path you pick.
- Report one \`diffs\` entry per file you changed, the files named above and the others alike: the file, and the path its diff went to.
`
}

const RULED = mctx`- The user ruled for these fixes. The prune keeps the rule each edit states.`
const UNRULED = mctx`- The user ruled on none of these fixes.`

const fixAndPruneTask = (groups, ruled) => {
  const fix = fixTask(groups, true)
  const readers = groups.map(g => `${g.target}: ${readerFor(g.target)}`).join('\n')
  const rulingLine = ruled ? RULED : UNRULED
  return mctx`
${fix}
- Work in two steps: the fix, under the fix role, then the prune, under the prune role, over the diff your fix made.
- The reader of each file, for the prune step:

~~~
${readers}
~~~

${rulingLine}
- The prune step takes the edits above as the edits the diff was meant to make.
- Each file named above takes two diffs: the fix step writes its own diff to that file's \`diff_path\`, and the prune step writes the diff of its own pass to that file's \`prune_path\`.
- Run the verification command once over all the fix edits together, and once over all the prune edits together. It does not run per file.
- Report both steps. The \`diffs\` field carries one entry per file the run changed, each \`path\` that file's \`prune_path\`, since the prune step left the final state. The \`notes\` field carries one line per cut, and the meaning before and after of each rule the diff touches.
`
}

// A code unit works in a worktree of its own, so its brief says where it is,
// how a command runs there, and how its change gets back.
const worktreeNote = () => mctx`
- You are in a git worktree of the repo, checked out at HEAD. It is a full tree of its own, and every path above is relative to its root.
- Work inside that tree and nowhere else: every read, every edit, and every command.
- Run each \`uv run\` command from the root of that tree. The first one builds that tree's own environment.
- A file you create is new to git, and a diff of the tracked files leaves it out. For each file you create, append the output of \`git diff --no-index -- /dev/null <file>\` to that file's diff.
- Report the absolute path of the worktree in \`worktree\`.
`

// The verify pass of a code unit works in the worktree its fix worked in, so
// the change it reads and the change it makes stay in one tree.
const worktreeVerifyNote = (worktree) => mctx`
- The fix worked in a git worktree of the repo, at ${worktree}. Every path above is relative to that tree's root.
- Work inside that tree and nowhere else: every read, every edit, and every command.
- Run each \`uv run\` command from ${worktree}.
`

const proseDiffs = (fix, prune) => mctx`- Its fix diff is under ${fix}, and the diff of the prune over that fix is under ${prune}.`
const codeDiff = (diff) => mctx`- Its diff is under ${diff}.`

const verifyGroup = (made, g) => {
  const target = g.target
  const edits = JSON.stringify(g.fixes.map(f => f.edit), null, 2)
  const where = made.kind === 'prose'
    ? proseDiffs(diffPath(g.target), prunePath(g.target))
    : codeDiff(diffPath(g.target))
  return mctx`
- ${target} — the edits its changes were meant to make:

~~~json
${edits}
~~~

${where}
`
}

const verifyOthers = (files) => mctx`
- The fix also changed these files. They are in scope beside the target: fix what you find in them. Each entry names the file, then the diff of its change.

~~~
${files}
~~~
`
const NO_OTHERS = mctx`- The fix changed no file beside the target.`

const verifyChain = (paths) => mctx`
- The other code targets of this run changed the same tree. Their diffs are under these paths:

~~~
${paths}
~~~
`
const NO_CHAIN = mctx`- No other code target of this run changed the same tree.`

const verifyTask = (made) => {
  const target = made.target
  const groups = made.groups.map(g => verifyGroup(made, g)).join('\n\n')
  const others = otherDiffs(made).length
    ? verifyOthers(otherDiffs(made).map(d => `${d.file} — ${d.path}`).join('\n'))
    : NO_OTHERS
  const chain = made.chain && made.chain.length
    ? verifyChain(made.chain.join('\n'))
    : NO_CHAIN
  const where = verifyPath(made.label)
  const worktree = made.worktree ? '\n\n' + worktreeVerifyNote(made.worktree) : ''
  return mctx`
- Verify the changes to ${target}.

${groups}

${others}
${chain}
- Write the diff of your own changes, verbatim, to ${where}, and report that path. A pass that changed nothing writes no file and reports an empty path.
` + worktree
}

const mergeTask = (worktree) => {
  const arg = shq(worktree)
  return mctx`
- Take the change in the worktree at ${worktree} into the repo.

~~~
uv run python scripts/retro_merge.py ${arg}
~~~

${ONE_CALL}
- It prints \`{"applied": ..., "files": [...], "conflict": ...}\`. Return that object as your structured output, field for field, changing nothing in it.
- When the command fails, or prints nothing, return \`applied\` false, an empty \`files\`, and what went wrong in \`conflict\`.
- Run no other command. Change no file yourself, and never run a git command of your own.
`
}

const checksTask = () => mctx`
- Run the checks over the current tree: the suite, the handbook build, and every solver of the corpus.

~~~
uv run python scripts/retro_checks.py
~~~

${ONE_CALL}
- It prints \`{"checks": [...]}\`. Return that \`checks\` array, each entry as it stands.
- Report a failure as a failure. Do not attribute it to other work, and do not report it as passing.
${NO_WRITES}
`

const sweepTask = (stems) => {
  const list = stems.join(' ')
  return mctx`
- Sweep the parameter values of these solvers.

~~~
mkdir -p .scratch/retro/sweep && uv run python scripts/run_dl.py sweep --open ${list}
~~~

${ONE_CALL}
- A stem whose cached sweep is missing, or was made from other solver code, sweeps again, and that takes minutes.
- It prints \`{"sweeps": [...], "skipped": [...]}\`. Return that \`sweeps\` array, each entry as it stands.
- Change no file outside \`.scratch/retro/sweep/\`. Never run a git command that changes state.
`
}

const sweepLinesTask = (sweeps) => {
  const list = sweeps.map(s => s.stem).join(' ')
  return mctx`
- Write the sweep review lines into these solvers.

~~~
uv run python scripts/run_dl.py sweep --mark ${list}
~~~

${ONE_CALL}
- It prints \`{"solvers": [...], "skipped": [...]}\`. Return that \`solvers\` array, each entry as it stands.
- Change no other file. Never run a git command that changes state.
`
}

const resolveTask = (taskId) => {
  const solver = solverTarget(taskId)
  const where = resolvePath(taskId)
  const report = `${REPORT_DIR}/${taskId}/retro.md`
  return mctx`
- Act on the review lines in ${solver}.
- Every review line in the solver's header names a point to act on, except a line whose kind marks it as waiting on the user; \`cite\` is such a kind today. Work each line per the procedure's operations, as they apply to it.
- Remove each line you finished. Leave a line you did not finish; when the solver carries no \`// draft\` line, return it to draft first: \`uv run python -c "import sys; sys.path.insert(0, 'tools/console'); from solver_console import solvers; solvers.mark_draft('<task_id>'); solvers.withdraw_citations('<task_id>')"\`. A review line whose kind waits on the user is not yours: leave it as it is.
${RUN_THE_CHECKS}
- Write the diff of your change to the solver, verbatim, to ${where}, and report that path. A run that changed nothing writes no file and reports an empty path.
- Write your report, in the form the Review operation gives, to ${report}. Create the directory first. The run, lint, and audit output go in your returned verification, not in the report.
${NO_GIT}
`
}

const cleanupTask = (taskId, source) => {
  const solver = solverTarget(taskId)
  return mctx`
- Run Simplify, then Prune, over the whole of ${solver}.
- ${source}
- Scratch goes under \`.scratch/<task_id>/\`.
`
}

const groupTask = (lines) => {
  const list = JSON.stringify(lines, null, 2)
  return mctx`
- Group these review lines. Each entry names the solver the line stood in, the line, and a seed key from its text.

~~~json
${list}
~~~
`
}

const consistencyTask = (group, rule, members) => {
  const scratch = `.scratch/retro/consistency/${group}/`
  const list = JSON.stringify(members.map(r => ({
    task_id: r.task_id,
    solver: r.target,
    report: `${REPORT_DIR}/${r.task_id}/retro.md`,
    acted: r.acted,
  })), null, 2)
  return mctx`
- Compare these solvers, the group \`${group}\`, under the rule ${rule}. Each entry names one solver, its report, and the review lines the Resolve stage acted on in it under that rule.
- Scratch goes under \`${scratch}\`.

~~~json
${list}
~~~
`
}

// One solver of a divergence the docs' rules do not explain. The solver goes to
// the form its group agreed on, under the reading that decides it.
const applyTask = (taskId, d) => {
  const solver = solverTarget(taskId)
  const divergence = JSON.stringify(
    { point: d.point, reading: d.reading, form: d.form }, null, 2)
  const where = applyPath(taskId)
  const report = `${REPORT_DIR}/${taskId}/retro-consistency.md`
  return mctx`
- Bring ${solver} to the form below, under the reading below.

~~~json
${divergence}
~~~

- The solvers this entry holds between read that point differently. The form above is the form they agree on.
- Change nothing the form does not reach. The model, the parameterization, and the Choice cases stay as they are.
${RUN_THE_CHECKS}
- Write the diff of your change to the solver, verbatim, to ${where}, and report that path. A run that changed nothing writes no file and reports an empty path.
- Write your report, in the form the Review operation gives, to ${report}. Create the directory first. The run, lint, and audit output go in your returned verification, not in the report.
- Report the point you brought the solver to in \`acted\`, as one entry, and what the form leaves unfinished in \`left\`.
${NO_GIT}
`
}

// The agent of a prose unit runs one command, and the brief it hands on is
// built at the call site, since it carries the unit's own two role texts.
const codexTask = (count, targets, command) => mctx`
- Run the brief below through Codex. It covers ${count}: ${targets}.
- Run this as one Bash call, in the foreground, with the Bash tool's \`timeout\` set to 600000. Copy the whole command, the brief between the two \`RETRO_BRIEF\` markers included, verbatim.

~~~
${command}
~~~

- It prints the JSON of the Codex session's final message. Return that JSON as your structured output, field for field, changing nothing in it.
- When the command fails, or prints nothing, return an empty \`diffs\`, an empty \`verification\`, an empty \`review_lines\`, and what went wrong in \`notes\`.
- Run no other command. Make none of the edits yourself, and change no file. Never run a git command that changes state.
`



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
  if (typeof text !== 'string' || !text.trim()) throw new Error(`args.roles[${JSON.stringify(name)}] is missing: pass the output of scripts/context.py workflow retro`)
  return text.trim()
}
const roleOf = (name) => roleFile(name).replace(AGENT_LINE, '')
const agentOf = (name) => {
  const m = roleFile(name).match(AGENT_LINE)
  return { agentType: m ? m[1] : 'handbook' }
}
const asRole = (name, task) => `${roleOf(name)}\n\n---\n\nYour brief:\n\n${task}`
// A prose unit takes the fix role, then the prune role over the diff the fix
// step made.
const asFixAndPrune = (task) =>
  `${roleOf('retro-fix')}\n\n---\n\n${FIX_AND_PRUNE_STEP}\n\n${roleOf('retro-prune')}\n\n---\n\nYour brief:\n\n${task}`

// ---------------------------------------------------------------- codex

// How the prose units run: an object of Codex settings, or `false` for the
// handbook agent.
const CODEX = args && 'codex' in args ? args.codex : {}

// A value as one single-quoted shell word.
const shq = (value) => `'${String(value).split('\'').join('\'\\\'\'')}'`

const codexFlags = () => [
  CODEX && CODEX.model ? ` --model ${shq(CODEX.model)}` : '',
  CODEX && CODEX.effort ? ` --effort ${shq(CODEX.effort)}` : '',
].join('')

// What one Codex session reads: what it is running under, then the fix role,
// the prune role, and the unit's brief.
const codexBrief = (u, ruled) => [
  'You are running under a workflow, not a conversation. Your final message is the JSON the output schema gives and nothing else. Never run a git command that changes state.',
  '',
  asFixAndPrune(fixAndPruneTask(u.groups, ruled)),
].join('\n')

// The agent of a prose unit runs one command. The script it runs writes the
// brief and the schema, makes AGENTS.md current, and hands the brief to one
// Codex session. Codex makes the edits, writes the diffs, and runs the
// verification.
const codexCall = (u, ruled) => codexTask(
  `${u.targets.length} file${u.targets.length === 1 ? '' : 's'}`,
  u.targets.join(', '),
  [
    `uv run python scripts/retro_codex.py --label ${shq(u.label)} --schema ${shq(JSON.stringify(EDIT_SCHEMA))}${codexFlags()} <<'RETRO_BRIEF'`,
    codexBrief(u, ruled),
    'RETRO_BRIEF',
  ].join('\n'))

// A Codex session that left no final message comes back with nothing to
// verify, and its unit falls back to the handbook agent.
const codexReturned = (edit) => !!edit && !!(edit.verification || '').trim()

// The roles a run reaches, by the run it is.
const READ_ROLES = ['retro-read', 'retro-check', 'retro-review']
const FIX_ROLES = ['retro-fix', 'solver', 'retro-prune', 'retro-verify', 'retro-group', 'retro-consistency', 'cleanup']
const RESOLVE_ROLES = ['solver', 'retro-fix', 'retro-group', 'retro-consistency', 'cleanup']
const rolesNeeded = () => args && args.resolve ? RESOLVE_ROLES
  : args && args.fixes ? FIX_ROLES
    : args && args.dry ? READ_ROLES
      : [...READ_ROLES, ...FIX_ROLES]

// A unit of fix work: the files one agent takes, with the fixes of each. The
// label names the unit wherever a file is written for it.
const unit = (groups, kind, label) => {
  const target = groups.map(g => g.target).join(', ')
  return {
    groups,
    kind,
    target,
    label: label || `fix:${target}`,
    targets: groups.map(g => g.target),
    fixes: groups.flatMap(g => g.fixes),
  }
}

// A prose unit runs under one Bash timeout, which bounds how many files it
// can fix and prune.
const PROSE_UNIT = 5

// Whether a code unit takes a worktree of its own.
const WORKTREES = !(args && args.worktrees === false)

// Each unit is a chain: the fix, then the verify pass over what that fix left,
// then, for a unit in a worktree, the merge of that worktree into the repo. A
// unit's chain runs beside the chains of the other units. The return carries
// the units that landed and the findings of their verify passes. The phase of
// every agent here is set per call, since the chains overlap.
async function fixStage(fixes, ruled = false) {
  const targets = [...byKey(fixes, f => f.target)].map(([target, fs]) => ({ target, fixes: fs, kind: kindOf(fs) }))
  const code = targets.filter(t => t.kind === 'code').map(t => unit([t], 'code'))
  const proseUnits = chunks(targets.filter(t => t.kind === 'prose'), PROSE_UNIT)
  const rest = [
    ...proseUnits.map((part, i) => unit(part, 'prose', chunkLabel('fix:prose', i, proseUnits.length))),
    ...targets.filter(t => t.kind !== 'code' && t.kind !== 'prose').map(t => unit([t], t.kind)),
  ]

  // What one unit leaves behind: the unit itself, and the report of the agent
  // that fixed it.
  const fixed = (u, edit) => ({ target: u.target, targets: u.targets, groups: u.groups, kind: u.kind, label: u.label, ids: u.fixes.map(f => f.id), fixes: u.fixes, edit, worktree: (edit.worktree || '').trim(), chain: null })

  // `isolate` gives the agent a worktree of the repo to work in, and tells it
  // that it is in one.
  const makeFix = async (u, isolate = false) => {
    if (u.kind === 'prose' && CODEX) {
      const edit = await agent(codexCall(u, ruled), { label: u.label, phase: 'Fix', schema: EDIT_SCHEMA, model: 'sonnet', effort: 'low' })
      if (codexReturned(edit)) return fixed(u, edit)
      log(`${u.label}: the codex session returned nothing; the unit runs on a handbook agent instead`)
    }
    const prompt = u.kind === 'prose'
      ? asFixAndPrune(fixAndPruneTask(u.groups, ruled))
      : asRole(fixRole(u.kind), fixTask(u.groups) + (isolate ? worktreeNote() : ''))
    const edit = await agent(prompt, { label: u.label, phase: 'Fix', schema: EDIT_SCHEMA, ...(isolate ? { isolation: 'worktree' } : {}), ...agentOf(u.kind === 'prose' ? 'retro-fix' : fixRole(u.kind)) })
    return edit ? fixed(u, edit) : null
  }

  // The verify pass of one unit, over the diffs that unit's own fix left. A fix
  // that changed nothing leaves nothing to read.
  const verifyUnit = async (m) => {
    if (!(m.edit.diffs || []).length) return null
    const v = await agent(asRole('retro-verify', verifyTask(m)), { label: `verify:${m.label.replace(/^fix:/, '')}`, phase: 'Verify', schema: VERIFY_SCHEMA, ...agentOf('retro-verify') })
    return v && { target: m.target, targets: [...m.targets, ...diffFiles(m)], ...v }
  }

  // Two applies on one tree can race, so each merge waits for the one before
  // it. The units reach this gate in the order they finish.
  let gate = Promise.resolve()
  const merged = (run) => {
    const next = gate.then(run, run)
    gate = next.then(() => {}, () => {})
    return next
  }

  // A unit whose change the repo refuses runs again on the repo itself.
  const back = []

  const mergeUnit = async (s, u) => {
    if (!s.made.worktree) {
      log(`${u.label}: the fix named no worktree; it runs again on the repo`)
      back.push(u)
      return { made: null, finding: null }
    }
    const label = `merge:${u.label.replace(/^fix:/, '')}`
    const merge = await merged(() => agent(mergeTask(s.made.worktree), { label, phase: 'Fix', schema: MERGE_SCHEMA, model: 'sonnet', effort: 'low' }))
    if (merge && merge.applied) return { ...s, merge }
    log(`${u.label}: the repo refused the worktree's change; its fix runs again on the repo. ${(merge && merge.conflict) || 'the merge returned nothing'}`)
    back.push(u)
    return { made: null, finding: null }
  }

  // The stages of one chain. A stage of a unit whose fix returned nothing
  // passes that on.
  const fixStep = (isolate) => async (u) => ({ made: await makeFix(u, isolate) })
  const verifyStep = async (s) => (s.made ? { ...s, finding: await verifyUnit(s.made) } : s)
  const mergeStep = async (s, u) => (s.made ? mergeUnit(s, u) : s)

  // Units of one serial run edit the same tree and the same suite, so they go
  // one at a time, each starting from the tree the previous one left. Each
  // verify pass judges the tests of the whole run, so it takes the paths of the
  // other diffs of that run.
  const serial = async (units) => {
    const made = []
    for (const u of units) {
      const m = await makeFix(u)
      if (m) made.push(m)
    }
    if (made.length > 1) {
      for (const m of made) m.chain = made.filter(o => o !== m).map(o => diffPath(o.target))
    }
    return parallel(made.map(m => async () => ({ made: m, finding: await verifyUnit(m) })))
  }

  const codeRun = async () => (code.length
    ? (WORKTREES ? pipeline(code, fixStep(true), verifyStep, mergeStep) : serial(code))
    : [])
  const restRun = async () => (rest.length ? pipeline(rest, fixStep(false), verifyStep) : [])

  const [others, coded] = await parallel([restRun, codeRun])
  // The fallbacks start once every merge is done, and go one at a time.
  if (back.length) log(`${back.length} of ${code.length} code units fall back to the repo`)
  const fellBack = back.length ? await serial(back) : []
  const done = [...(others || []), ...(coded || []), ...fellBack].filter(s => s && s.made)
  const findings = done.map(s => s.finding).filter(Boolean)
  log(`${findings.reduce((n, f) => n + f.findings.length, 0)} verify findings over ${findings.length} units`)
  return { made: done.map(s => s.made), findings }
}

// The checks test the combined tree, so they are a barrier after every unit.
async function checksStage() {
  const done = await agent(checksTask(), { label: 'checks', phase: 'Verify', schema: CHECKS_SCHEMA, model: 'sonnet', effort: 'low' })
  const checks = done ? done.checks : []
  log(`${checks.filter(c => !c.passed).length} failing checks`)
  return checks
}

// The items one agent takes, in order.
const chunks = (items, size) => {
  const out = []
  for (let i = 0; i < items.length; i += size) out.push(items.slice(i, i + size))
  return out
}

// The label one agent of a chunked stage carries.
const chunkLabel = (name, i, n) => (n > 1 ? `${name}:${i + 1}/${n}` : name)

// The window names the solvers the sessions wrote. A name that is not a task
// id names no solver, and is dropped. The stems go in chunks of at most 25, one
// agent per chunk, so a parameter value the pairs leave open is reported beside
// the calls.
async function sweepStage(stems) {
  const ids = [...new Set((stems || []).map(s => (s || '').trim()).filter(s => /^[0-9a-f]{8}$/.test(s)))]
  if (!ids.length) return null
  const parts = chunks(ids, 25)
  const done = (await parallel(parts.map((part, i) => () =>
    agent(sweepTask(part), { label: chunkLabel('sweep', i, parts.length), phase: 'Sweep', schema: SWEEP_SCHEMA, model: 'sonnet', effort: 'low' })
  ))).filter(Boolean)
  if (!done.length) return null
  const sweeps = done.flatMap(d => d.sweeps)
  log(`${sweeps.filter(s => s.params.length).length} of ${sweeps.length} swept solvers hold a parameter the pairs leave open`)
  return sweeps
}

// A solver the sweep leaves a parameter open in takes one review line per open
// parameter, and keeps the draft state it has. The solvers go in chunks of at
// most 20, one agent per chunk.
async function sweepLinesStage(sweeps) {
  const open = (sweeps || []).filter(s => s.params && s.params.length)
  if (!open.length) return null
  const parts = chunks(open, 20)
  const done = (await parallel(parts.map((part, i) => () =>
    agent(sweepLinesTask(part), { label: chunkLabel('sweep-lines', i, parts.length), phase: 'Sweep', schema: SWEEP_LINES_SCHEMA, model: 'sonnet', effort: 'low' })
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
  // A line of another form is a continuation of the line above it, and carries
  // no point of its own, so the group agent never sees it.
  const lines = acted.flatMap(r => r.acted.map(line => ({ task_id: r.task_id, line, seed: seedKey(line) })).filter(l => l.seed))
  if (!lines.length) return null
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

// A divergence no rule of the docs explains is settled here, not by the user.
// Each solver the entry holds between goes to the one form under the one
// reading, one agent per solver. The divergence itself is recorded under
// `record` in the run's result, for the user to read. The solvers of one entry
// run together, and the entries run beside each other.
async function applyStage(consistency) {
  const entries = ((consistency && consistency.divergences) || []).filter(d => d && d.principled === false)
  if (!entries.length) return null
  const done = (await parallel(entries.map(d => async () => {
    const stems = [...new Set((d.solvers || []).map(s => (s || '').trim()).filter(Boolean))]
    const solvers = await parallel(stems.map(id => async () => {
      const r = await agent(asRole('solver', applyTask(id, d)), { label: `apply:${id}`, phase: 'Consistency', schema: RESOLVE_SCHEMA, ...agentOf('solver') })
      return r && { task_id: id, target: solverTarget(id), ...r }
    }))
    return { group: d.group, point: d.point, reading: d.reading, form: d.form,
             record: { point: d.point, rule: d.rule, reading: d.reading, wording: d.wording,
                       form: d.form, ground: d.ground, solvers: d.solvers },
             solvers: (solvers || []).filter(Boolean) }
  }))).filter(Boolean)
  log(`${done.reduce((n, e) => n + e.solvers.filter(s => s.changed).length, 0)} solvers brought to form over ${done.length} unprincipled divergences`)
  return done
}

// The solvers the Apply step wrote, flat.
const appliedSolvers = (applied) => (applied || []).flatMap(e => e.solvers || [])

// The solvers a run wrote: a solver fix that changed the file, a resolve that
// changed the file, and an apply that changed the file. Each owes the cleanup
// pass of the procedure.
const cleanupItems = (made, resolved, applied) => {
  const items = new Map()
  for (const m of made || []) {
    if (m.kind !== 'solver' || !(m.edit.diffs || []).length) continue
    for (const t of m.targets) items.set(t.replace(/^programs\/solvers\/|\.dl$/g, ''), `A solver fix of this run wrote it; its diff is under ${diffPath(t)}.`)
  }
  for (const r of resolved || []) {
    if (!r.changed) continue
    items.set(r.task_id, `The Resolve stage of this run wrote it; its report is at ${r.report}.`)
  }
  for (const r of appliedSolvers(applied)) {
    if (!r.changed) continue
    items.set(r.task_id, `The Apply step of this run brought it to the form its group agreed on; its report is at ${r.report}.`)
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
  log(`${done.filter(r => !/^no change/i.test(r.changed)).length} of ${done.length} solvers changed in cleanup; ${done.reduce((n, r) => n + (r.carried || []).length, 0)} files a carry reached`)
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
// that file, and each such fix is verified in its own chain, as the first round
// runs. This round starts no round of its own.
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
  const { made, findings } = await fixStage(fixes, true)
  phase('Verify')
  // A fix that reported no diff changed nothing. The checks run only over a
  // code change.
  const changed = made.filter(m => (m.edit.diffs || []).length)
  const codeChanged = changed.some(m => m.kind === 'code')
  log(`${changed.length} of ${made.length} follow-up fixes changed a file`)
  return { fixes: made, verify: changed.length ? { findings, checks: codeChanged ? await checksStage() : [] } : null }
}

const missing = rolesNeeded().filter(name => typeof ROLES[name] !== 'string' || !ROLES[name].trim())
if (missing.length) return { error: `args.roles is missing ${missing.join(', ')}. Pass the output of scripts/context.py workflow retro.` }

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
  const applied = await applyStage(consistency)
  phase('Cleanup')
  const cleanup = await cleanupStage(cleanupItems(null, resolved, applied))
  // Resolve and Cleanup both edit solvers, so the checks run over the tree
  // they leave.
  phase('Verify')
  const checks = await checksStage()
  return { tally: null, closed: null, calls: null, fixes: null, entries: null, resolve: resolved,
           consistency, applied, cleanup, verify: { findings: [], checks }, followups: null, sweep, sweep_lines: sweepLines, borderline_drops: null }
}

if (args && args.fixes) {
  phase('Fix')
  // Each unit is verified in its own chain; the checks wait for every unit, and
  // for the stages that write the solvers beside them.
  const { made, findings } = await fixStage(args.fixes, true)
  phase('Resolve')
  const resolved = await resolveStage(resolveStems(made, null))
  phase('Consistency')
  const consistency = await consistencyStage(resolved)
  const applied = await applyStage(consistency)
  phase('Cleanup')
  const cleanup = await cleanupStage(cleanupItems(made, resolved, applied))
  phase('Verify')
  const verify = { findings, checks: await checksStage() }
  const followups = await followupStage(verify)
  return { fixes: made.filter(m => m.kind !== 'entry'), entries: made.filter(m => m.kind === 'entry'), resolve: resolved, consistency, applied, cleanup, verify, followups }
}

phase('Read')
const read = await agent(asRole('retro-read', readTask()), { label: 'read', phase: 'Read', schema: ISSUES_SCHEMA, ...agentOf('retro-read') })
if (!read) return { error: 'read agent returned nothing' }
const issues = read.issues
// The sweep runs beside the check and review stages, and is awaited before any fix.
const sweeping = (args && args.dry) ? null : sweepStage([...new Set(issues.flatMap(i => i.tasks || []))])
log(`${issues.length} issues from the window; ${read.borderline_drops.length} borderline drops`)
if (!issues.length) return { tally: { issues: 0 }, consistency: null, applied: null, borderline_drops: read.borderline_drops }

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
const dry = args && args.dry
// The doc whose fixes wait on the user's ruling, at any level.
const PRINCIPLES = 'docs/handbook/principles.md'
// A level-4 call is presented and not made, and so is a fix to PRINCIPLES. A dry run makes
// nothing, so it lists them with the rest: the rulings filter them like any other fix.
const stands = calls.filter(c => (c.default === 'fix' || c.default === 'replace') && c.fixes.length && (dry || c.tier !== 4))
// one agent per general fix: fixes that several replaced issues point at collapse to one
// A fix carries its issue's tasks: a fix over a principle writes a review line into each of their draft solvers.
const fixes = [...byKey(stands.flatMap(c => c.fixes.filter(f => dry || f.target !== PRINCIPLES).map(f => ({ ...f, id: c.id, tasks: issueById.get(c.id)?.tasks || [] }))), f => `${f.target}\n${f.edit}`)]
  .map(([, fs]) => ({ ...fs[0], id: fs.map(f => f.id).join(','), tasks: [...new Set(fs.flatMap(f => f.tasks))] }))
const tally = { issues: issues.length, closed: closed.length }
for (const c of calls) tally[c.default] = (tally[c.default] || 0) + 1
log(`${fixes.length} fixes to make`)

phase('Fix')
// The sweep overlaps the reading stages only: the fix and verify stages run solvers under a CPU limit.
const sweep = sweeping ? await sweeping : null
const sweepLines = sweep ? await sweepLinesStage(sweep) : null
// Each unit is verified in its own chain; the checks wait for every unit, and
// for the stages that write the solvers beside them.
const { made, findings } = fixes.length && !dry ? await fixStage(fixes) : { made: [], findings: [] }

phase('Resolve')
const resolved = dry ? null : await resolveStage(resolveStems(made, sweepLines))

phase('Consistency')
const consistency = dry ? null : await consistencyStage(resolved)
const applied = dry ? null : await applyStage(consistency)

phase('Cleanup')
const cleanup = dry ? null : await cleanupStage(cleanupItems(made, resolved, applied))

phase('Verify')
const verify = made.length ? { findings, checks: await checksStage() } : null
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
  applied,
  cleanup,
  verify,
  followups,
  sweep,
  sweep_lines: sweepLines,
  borderline_drops: read.borderline_drops,
}
