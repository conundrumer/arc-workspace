+ budget: 2700
* comment: when editing this doc
    - Readers: the code editor, code reviewer, design reviewer and lib reviewer where their brief gives Codex mode, by the link in each entry point.
    - Acts, each with its section:
        - Giving the work of each checklist item to Codex and handling its replies: [Codex mode](#codex-mode).

# Codex mode
- Keep your agent type, your checklist walk, your hooks and your final reply.
- Do no item's work yourself, and edit no file but your report file.
- Run `uv run python scripts/step.py <agent>` at your start, where your documents give a checklist.
    + xref: scripts/step.py:main
- Where they give none, give Codex, as its one item, the line `Do the work your documents and your brief give.`, and take each later step of this section as for that item.
- Give each item it prints, whole, on stdin to `uv run python scripts/codex_agent.py <agent> <scratch> <brief> <model> <effort>`, with your agent type, scratch directory, brief file, and the model and effort the Codex mode line gives.
    + xref: scripts/codex_agent.py:main
- Run that command in the background, and wait for it as [waiting-on-commands](prompts/agents/notes/commands.md#waiting-on-commands) gives.
- Use the same scratch directory on every call: the command keeps one Codex session there and resumes it for each later item or message.
    + xref: scripts/codex_agent.py:run
- Make each Agent call and SendMessage that Codex asks for where your own documents allow it, including each launch that `uv run python scripts/operate.py review <agent-id>` prints.
    + xref: scripts/operate_review.py:review
- Run that review command yourself in a foreground Bash call, with your agent id, where your checklist calls for it, and pass its output to Codex.
    + xref: scripts/operate_review.py:review
- Give each result and each message that reaches you to Codex as the next input to the same command.
- Where Codex asks for a step command, run it yourself and give its output to Codex; Codex runs no step command.
- Where an item prints a condition and calls to enter or skip a part, give that output to Codex, run the call its judgment gives, and pass the result to Codex.
    + xref: scripts/step.py:main
- Once Codex has done an item, including the work after any calls or messages it requested, run the step command with that item's name.
    + xref: scripts/step.py:main
- Where Codex reports a blocker other than waiting for a call or message above, or the command exits nonzero, stop the checklist at that item with `uv run python scripts/step.py <agent> --stop <item>`, and give your final reply with the work so far, the unfinished item and why, including the error the command printed.
    + xref: scripts/step.py:main, scripts/codex_agent.py:main
- Do no unfinished work yourself.
- Where Codex asks for the final reply, write its report text to your report file and give that reply as your own documents require.
