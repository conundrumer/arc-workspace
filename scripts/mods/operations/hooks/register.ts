// description: Runs the session's operations loop, started by `/ops`: it makes each call `scripts/operate.py call ops` gives, and records it with `operate.py made`, and beside it the monitor loop, by `scripts/monitor.py call ops-monitor`.
//
// One operations loop runs per session, and the monitor loop runs while it runs. `operate.py --help` gives the form of a step and of a recorded call. A step the loop
// cannot make, and a failure of the loop, stop it and reach the coordinator's model as a user-role row and the
// person as a toast, so that a stopped loop does not read as an idle one. A hot reload of this module, or the
// session's end, ends the loop with it, and `/ops` starts it again.

const NAME = 'operations'
const LOOP = 'ops'
const MONITOR = 'ops-monitor'
const COORDINATOR = 'main'
const OPERATE = ['uv', 'run', 'python', 'scripts/operate.py']
const WATCH = ['uv', 'run', 'python', 'scripts/monitor.py']
// `operate.py call` blocks for up to 210 s before it gives a wait.
const CALL_TIMEOUT_MS = 240_000
// How long the loop sleeps after a step that gives nothing to call.
const WAIT_MS = 15_000
const AGENT_ID = /agentId: (\w+)/

let running = false

// The scripts read the session from `CLAUDE_CODE_SESSION_ID`, which the host's own environment may give for another
// session, as where this session runs under another one's command.
const sessionEnv = async ($) => ({ CLAUDE_CODE_SESSION_ID: await $.session.id() })

async function run($, argv, timeoutMs = 30_000) {
  const r = await $.process.run(argv, { timeoutMs, env: await sessionEnv($) })
  if (r.exitCode !== 0) throw new Error(`${argv.join(' ')} exited ${r.exitCode}: ${r.stderr}`)
  return r.stdout
}

const operate = ($, args, timeoutMs) => run($, [...OPERATE, ...args], timeoutMs)

async function tell($, text) {
  await $.session.append({ message: { type: 'user', content: [{ type: 'text', text }] } })
  $.ui.toast(`${NAME}: ${text.split('\n')[0]}`)
}

// The call `step` of the loop `id` gives, made, as the record `operate.py made` takes. A message to the
// coordinator, which the loops run in the coordinator's own session, reaches its model as a user-role row from the
// operations loop, and the operations loop alone from the monitor loop, which reads the monitor's record.
async function make($, id, step) {
  switch (step.kind) {
    case 'launch': {
      const input = {
        description: step.description,
        subagent_type: step.subagentType,
        prompt: step.prompt,
        run_in_background: true,
        ...(step.worktree ? { isolation: 'worktree' } : {}),
        ...(step.model ? { model: step.model } : {}),
      }
      const r = await $.tool.call({ tool: 'Agent', ...input })
      if (r.deny !== undefined) throw new Error(`the launch ${step.key} was denied: ${r.deny}`)
      const id = AGENT_ID.exec(r.text ?? '')?.[1]
      if (id === undefined) throw new Error(`the launch ${step.key} gave no agent id: ${r.text}`)
      return { tool: 'Agent', input, result: JSON.stringify({ agentId: id }), error: false }
    }
    case 'send': {
      const input = { to: step.to, message: step.message }
      if (step.to === COORDINATOR) {
        if (id === LOOP) await tell($, step.message)
        return { tool: 'SendMessage', input, result: 'kept in the record', error: false }
      }
      const r = await $.tool.call({ tool: 'SendMessage', ...input })
      return { tool: 'SendMessage', input, result: r.text ?? r.deny ?? null, error: r.deny !== undefined || r.isError === true }
    }
    case 'bash': {
      const r = await $.process.run(['bash', '-c', step.command], { timeoutMs: 600_000, env: await sessionEnv($) })
      return { tool: 'Bash', input: { command: step.command }, result: r.stdout + r.stderr, error: r.exitCode !== 0 }
    }
    default:
      throw new Error(`a step of kind ${step.kind} has no call: ${JSON.stringify(step)}`)
  }
}

// The loop `id`, whose steps `command` gives, until its step is a final reply, whose text it returns, or, where
// `whileRunning`, until the operations loop ends.
async function loop($, id, command, whileRunning) {
  while (!whileRunning || running) {
    const step = JSON.parse(await run($, command, CALL_TIMEOUT_MS))
    if (step.kind === 'wait') {
      await $.clock.sleep(WAIT_MS)
      continue
    }
    if (step.kind === 'reply') return step.text
    const made = await make($, id, step)
    await operate($, ['made', id, JSON.stringify({ ...made, key: step.key })])
  }
}

const failed = ($, id) => (err) => tell($, `The ${id} loop stopped on a failure: ${err?.stack ?? err}`)

// The operations loop, with the monitor loop beside it. Its final reply ends with the monitor's part for the
// coordinator, read once the monitor loop has stopped, so that no later read of the monitor's is left out.
async function operations($) {
  const monitor = loop($, MONITOR, [...WATCH, 'call', MONITOR], true).catch(failed($, MONITOR))
  let reply
  try {
    reply = await loop($, LOOP, [...OPERATE, 'call', LOOP], false)
  } finally {
    running = false
    await monitor
  }
  const part = (await run($, [...WATCH, 'unfinished', MONITOR], CALL_TIMEOUT_MS)).trim()
  await tell($, `The operations loop ended:\n${reply}${part ? `\n\n${part}` : ''}`)
}

export function register(on) {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'ops',
      description: 'Starts the operations loop for this session, or gives it a line.',
      argumentHint: '[line]',
      immediate: true,
    })
    return next(e)
  })
  on('command.run', { command: 'ops' }, async ($, e) => {
    // `/ops <line>` gives the loop a line of the coordinator's, as `operate.py tell` takes it.
    if (e.args.trim() !== '') {
      await operate($, ['tell', LOOP, e.args.trim()])
      return { text: `The operations loop has the line: ${e.args.trim()}` }
    }
    if (running) return { text: 'The operations loop already runs.' }
    running = true
    void operations($).catch(failed($, LOOP))
    return { text: 'The operations loop started.' }
  })
}
