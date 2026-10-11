"""The operator's procedures, as functions from the state to the next step:
the next call the operator agent makes, which `scripts/operate.py` prints.

The modules keep these rules:

- No procedure reads a file, a transcript or the clock: `scripts/operate.py`
  reads the state into a `state.State`, and each procedure reads only that.
  `task_work`, the work a pipeline sets aside, is no procedure: it is the
  one module that touches files, and a step the procedures print runs it.
- A step changes the state that the next read of it gives, so a procedure
  finds that a step is done from the state alone, and never from a record
  of its own. The record of a call the operator made is the call in the
  transcripts of the session's operators.
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
(a ticket's log and the calls that write it), `steps` (the calls printed
and their keys), `command_words` (the words of a Bash command, and the
call of the command), `filing` (the files the command writes for a printed
call), `printing` (the text that prints a step), `handled` (whether an
operator already made or handled a step), `final_reply` (the operator's
final reply and its carrier), `constants` (the values the command shares
with the scripts an agent runs), `briefs` (the briefs the launches give),
`triage` (ticket analysts on open tickets, and the labeled items of their
replies for the coordinator), `decisions` (ticket analysts on undecided
steps), `drafts` (the review of draft changes), `changes` (a change from
its take to its merge), `change_budget` (the cost budget of a change),
`merging` (the merge and what follows it), `alerts` (the alerts and the
other agents' messages), `reports` (the fixed forms of the replies the
command reads), `passes` (the solver pipelines),
`task_work` (the work a pipeline sets aside), `batches` (After a batch),
`plan` (the order of the procedures, the block and the final reply),
and `monitor` (the monitor's steps: the alerts on the watched agents' runs)."""
