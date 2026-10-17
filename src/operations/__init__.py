"""The operator's procedures, as functions from the state to the next step:
the next call the operator agent makes, which `scripts/operate.py` prints.

The modules keep these rules:

- No procedure reads a file, a transcript or the clock: `scripts/operate.py`
  reads the state into a `state.State`, and each procedure reads only that.
  `task_work`, the work a pipeline sets aside, is no procedure: it is the
  one module that touches files, and a step the procedures print runs it.
- Whether a step the command gives is in flight, done or failed is as
  `scripts/operate.py --help journal` gives it (`journal`).
- Each agent a step launches has a description of the form
  `roles.description` gives, so the state reads back which procedure, and
  which ticket, task or batch, each launch of any operator of the session
  serves.
- A step that needs a judgment, or the meaning of prose an agent wrote,
  goes to an agent launched for it, or reads the fixed form that agent
  writes; where neither places it, the step is undecided
  (`steps.Undecided`), and goes to a ticket analyst launched on it
  (`decisions`). Where a reply or a message of an agent is in no form the
  command reads, the step first asks that agent once to send it again in
  that form (`handled.ask_again`), and is undecided only where the answer is
  still in no such form.
- The coordinator gets from the command only what the coordinator alone
  can act on: the items for the user (`triage`), and its own lines in no
  form the command reads, which go back to it (`steps.unread_line`), since
  only their writer knows what they meant.

Modules: `state` (what the command reads), `roles` (the agents launched
and their descriptions), `directives` (the coordinator's lines), `tracker`
(the reads of a ticket's log), `log_commands` (the calls that write
it), `worktrees` (the worktree of a change), `steps` (the calls printed
and their keys), `command_words` (the words of a Bash command, and the
call of the command), `filing` (the files the command writes for a printed
call), `printing` (the text that prints a step), `handled` (whether an
operator already made or handled a step), `final_reply` (the operator's
final reply and its carrier), `constants` (the values the command shares
with the scripts an agent runs), `briefs` (the briefs the launches give),
`journal` (the step journal), `messages` (the messages to agents at work),
`brief_reading` (the
reading of a brief's or a message's text back),
`triage` (ticket analysts on open tickets, and the labeled items of their
replies for the coordinator), `decisions` (ticket analysts on undecided
steps), `drafts` (the review of draft changes), `taking` (the release of tickets and the take of open changes), `changes`
(a change the operator holds, from its take to its merge), `change_agents` (the agents of a change),
`item_check` (the launch of a change's item checker), `change_fragments`
(the doc editor of a change's `mctx` fragments), `change_overrun` (a
change past its cost budget), `change_budget` (the cost budget of a change),
`doc_review` (the review of a change's documents), `merging` (the merge and
what follows it), `alerts` (the alerts and the other agents' messages),
`reports` (the fixed forms of the replies the command reads), `passes` (the
solver pipelines), `runs` (the pipelines a run script starts),
`task_work` (the work a pipeline sets aside), `batches` (After a batch,
and the reviews, the gate, the process assessment and the cost audit,
which no batch holds),
`order` (the order of the procedures' steps, and the batch of launches
of one output), `plan` (the operator's next step and the block),
`standing` (the step that ends the operator and the lines of what stands
at its end),
and `monitor` (the monitor's steps: the alerts on the watched agents' runs).
`ticketing.exits` gives what takes a ticket out of each status."""
