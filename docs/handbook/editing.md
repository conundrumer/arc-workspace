+ budget: 24200

# Editing the agent-facing documents
- The handbook, the console's messages to a worker, the documents that say what each agent reads, and what the tools print to a session.

## What a file holds
+ rules on lines
- A file holds what the reader of its entry point needs for the work it does there, and nothing more.
- Add or keep a line only where its reader needs it: where the reader could not infer what it says, assuming it can infer whatever you could infer from its context, or would misread its context without it.
- A line is a restatement for a reader when another line of that reader's context says or implies what it says. An elaboration is detail, a reason or a consequence beyond what the reader needs, an example, or a list of kinds where a general term exists.
    - A line that has to be edited only because its list needs another item holds a list of kinds, and the general term goes in its place.
- Write or keep a line, or words in a line, that is to stop a reader's failure, or that is a restatement or an elaboration for each of its readers, only where an observed failure required it: one that no tool, hook or existing line could prevent at less cost, its upkeep counted, and that has recurred, as a cited record shows, would show in no run's output, or lost work or left an output wrong.
    - An observed failure is a reader's failure without that text, at a session, a task and pass, or a run. An argued reason or a predicted failure is not one.
    - A restatement or an elaboration is required only by a failure its reader made with the text it restates or elaborates in its context.
    - Where a line's `comment` quotes and cites the user's words or rulings, what they ask needs no observed failure, and a line meets them where it meets what they ask, in any words.
    - The words that a line's `comment` quotes and cites to a line of [Principles](docs/handbook/principles.md) need no observed failure, and the other words of that line stay under the test above.
- Choose an edit in this order of preference: a deletion; no change, where a tool or another line already covers it; a change to existing words; and new words only where none of those is enough.
- Fix a finding by changing the line that caused it, and add no exception to a rule for a small inconsistency.
- Where a rule holds a condition, an exception or a case stacked on it for each failure it was to stop, where several rules one reader loads act on the same act, or where a rule names one instance of a kind its reason covers, put in their place one general rule that covers their cases, and where none covers them, make each clause that earns its place a rule of its own in the section whose subject it is.
- When the premise of a line is wrong, change the line that states that premise.
- A line kept against a rule of [Editing the agent-facing documents](docs/handbook/editing.md), or put back after a cut, has a `comment`, as [Directives](src/controlled_markdown/writing.md#directives) gives it, that says why it stays, taken from the one who asked for the change or from a ticket or a transcript you read, and cites the ticket, the transcript, the user's instruction file or the Principles line that records it.
    - On kept words that need an observed failure, the comment states that failure: the reader that failed, where, and what it did without that text. That failure is a case the line covers, and any words that cover that case meet it.
    - On words whose source is the user's words or rulings, or a line of Principles, the comment quotes the words that source gave, with the user's session and time, or the path and section of the user's instruction file that holds them, the ruling, or the Principles line.
- Where words you write or keep in your edit need an observed failure and have no ticket or transcript that records one, search the tickets and the project's session transcripts for one. Where you find one, rewrite the comment to cite it, and where you find none, cut those words.
    - The tickets are under `tickets/` in the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints, and in no other worktree.
    - `python3 ~/.claude/skills/retrieve/transcripts.py --help` lists the subcommands that read the transcripts, and each takes a session as its id or its `.jsonl` path.
    - The session transcripts are the `.jsonl` files directly in `~/.claude/projects/-Users-davidlu-code-arc-workspace/` and in `~/.claude-console/projects/-Users-davidlu-code-arc-workspace/`, and a session's subagent transcripts are the `.jsonl` files at any depth under `<session id>/subagents/` in the same directory, each of which a subcommand takes as a session of its own.

## Where each text is
- The handbook's documents: [Handbook](prompts/handbook.md) includes them in order, and holds no text of its own.
- The operations: [Procedure](docs/handbook/procedure.md).
- The theory of tasks, models and encodings: [Principles](docs/handbook/principles.md) and [Encoding](docs/handbook/encoding.md).
- The lib's sections: the `//!` and `///` comments of [lib.dl](programs/lib.dl) and of the modules under [lib](programs/lib).
- What each Claude Code session on the repo and each agent launched in such a session reads, and no codex session reads: [arc-workspace](CLAUDE.md).
- What the coordinator, the session the user talks with, reads: [Coordinator](prompts/agents/notes/coordinator.md), rendered to `.claude/coordinator.md`, and, where the user starts it with [claude.py](scripts/claude.py), [User session](prompts/user-session.md), as its appended system prompt.
    - Its context: `context coordinator` where the user starts it with `claude`, and `context user-session` where the user starts it with [claude.py](scripts/claude.py), then the user's messages.
    - The coordinator also reads each document or section outside its `context` output that a link of those documents leads to, where the link's condition holds.
- What a session at a terminal reads, and the passes it runs: [Session](.claude/skills/session/SKILL.md), then [Solver session](prompts/session.md).
    - [Session](.claude/skills/session/SKILL.md) is deprecated, and has no `comment` directive.
    - Its context: `context session`, then the output of each command the text gives.
- What a codex session on the repo reads: [Codex on arc-workspace](prompts/codex.md).
    - Its context: `context codex`, then the user's message.
    - A codex session also reads, as its developer instructions, the main tree's `docs/codex-style.md` with its HTML comments left out, which the `.codex/config.toml` of the worktree it runs in gives it.
- What each agent reads: the prompt of its name under [agents](prompts/agents).
    - Its context: `context agent <name>`.
    - An agent also reads each document or section a link of its prompt leads to, where the link's condition holds, and `context agent <name>` prints none of those.
    - The `analyze` agent reads [Analyze after the concept](prompts/agents/analyze-next.md) after it writes the concept.
- The statements more than one entry point inlines or links: the documents under [notes](prompts/agents/notes), one per subject.
- What each of the agents' processes must achieve: [Process notes](prompts/agents/notes/process.md).
- The console messages, deprecated with the console: [Console messages](prompts/console.md).
    - A worker's context: the appendix, the message the stage opens with, then each message a condition sends, under that condition: `context console <stage>`.
    - A survey session's context: the appendix, its role, then the `survey` message: `context survey`.
    - The system reminders the console prefixes to a message: [workers.py](tools/console/solver_console/workers.py).
    - The committer's brief: `commit_brief` in [config.py](tools/console/solver_console/config.py).
- The roles, deprecated: [roles](prompts/roles), one document per role. A role's `agent` attribute says which agent runs it, and a role with none runs as `handbook`.
    - Its context: `context role <name>`.
    - A role's brief comes from the script or the session that spawns it, and the `context role` output gives that file's path.
- The `deletions` report: [Deletion report](prompts/run_dl.md).
- Each text a program puts in an agent's context: its `mctx` fragments, as [Prose in code](src/controlled_markdown/writing.md#prose-in-code) gives them.
- What the callout-rate classifier reads, deprecated with the console: [Classification rubric](tools/console/recal/RUBRIC.md).
- The classifier, deprecated with the console: [Callout rate recalibration](tools/console/recal/README.md).
- The workflow briefs and the schema descriptions, deprecated: the scripts under [workflows](.claude/workflows).
    - A workflow agent that runs a role reads `context workflow <name>`, and an agent with no role reads its brief alone.
    - `readerFor` in [retro.js](.claude/workflows/retro.js) gives the reader of each document a retro fix touches.
- `uv run python scripts/context.py --write` generates files git does not track, and `uv run python scripts/context.py --help` lists them.

## What goes where
- A document or a section that more than one entry point includes, inlines or links says nothing that holds for one of them and not another, and no default that a line of one of them overrides.
- An entry point inlines each operation it runs, in order, under a heading of its name.
    - A session's entry point inlines [Every pass](docs/handbook/procedure.md#every-pass) as well.
- The prompt of each agent whose `tools` include `Bash`, other than one whose documents give it no call but a command and the calls that command prints, has `TaskStop` in its `tools` too, and inlines each line of [commands](prompts/agents/notes/commands.md#commands).
- An entry point's `+ lib:` attribute says how it reads the lib.
    - A reader whose `+ lib:` is `index` reads a declaration's interface when it needs one.
- A document mentions a file under [src](src) only where its reader runs or reads the file.
- State a fact or a rule once, in the document and the section whose subject it is.
    - A rule on an act that one step of a reader applies stands in that reader's context at that step: inlined there from the section that states it, or stated there where that step is its subject.
    - A rule on an act that several steps of a reader apply stands once in that reader's context, in the section whose subject is that act or at the first of those steps, and each other step links it there.
    - Link every other fact or rule from each other place that needs it.
- An agent's `description`, in the front matter of its prompt, says what the agent reads and what work it is for, as much as a launcher needs to pick the agent, and what its reply gives, where a launcher acts on that. It may give what the work is on, such as the task its brief gives, and gives nothing else of the brief's form, which [Launching notes](prompts/agents/notes/launching.md) states.
- A line that links a section relies on that section's heading alone.
- No document restricts, replaces or redirects an operation another document states.
- Progressive disclosure and staged disclosure manage an agent's context: an agent does better work when its context holds only what its current work needs, and these rules keep the rest out of its context until the agent reaches the work that needs it, so that its context does not overload.
    * comment: The user's words, session 7fd429fb, 2026-10-12T16:37:24Z to 16:39:46Z: "Is this general principle documented anywhere? Stagedisc and progdisc", "File", and "It should be clear this is for making agents do a better job by context management and avoiding overload".
    - Progressive disclosure: text that only part of an entry point's work needs, where splitting it off removes more from what the reader loads than the pointer to it adds, stands in a file the reader does not hold until it meets that part, and reaches the reader there: a tool's output there gives at most a clause and points to that file, or a stated condition that refers to that part tells the reader to load that file, or a section of it that a link gives. A section of a file the reader already holds is not split off.
        * comment: The user's words, session 7fd429fb, 2026-10-12T16:40:13Z: "So the files should actually be separate and deferred loaded not just sequential or sectioned".
    - Staged disclosure: where part of an entry point's work depends on the output of an earlier part, the text that only the later part needs stands in a file the reader loads once it has done the earlier part, and the earlier text gives that point as the condition to load it. A later section of a file the reader already holds does not meet this rule.
        * comment: The user's words, session 7fd429fb, 2026-10-12T16:40:13Z: "So the files should actually be separate and deferred loaded not just sequential or sectioned".
- Write no document line for a form that only a check with a `guard` decorator guards against.
- A document the handbook includes links only to a document an entry point in `HANDBOOK_ENTRIES` in [__main__.py](src/controlled_markdown/__main__.py) includes, or to a file outside the document set.
- A document rendered on its own is an entry point, and its lead says what the render leaves out when a link in the render leads there.
- A render leaves out the lines that have an attribute its entry point excludes. Outside an entry point's lead, no heading of the render is left with nothing under it, and no line of it refers to a section the render leaves out.
    - `deferred` marks a section of a pass no entry point runs yet.
    - The session render includes them, and so does `uv run python scripts/context.py section`.

## Writing a file
+ line review
- In an edit, follow the form the file's other lines show.
- Before you edit or review a file that holds a directive other than `comment`, or that an `include` or `inline` directive of another file gives, read [Templating a document](src/controlled_markdown/templating.md).
- A file that has editing notes opens with them, under a `* comment: when editing this doc` line. Read them before you edit the file.
- A line uses precise and conventional words, each term in the meaning the documents give it, and no contrastive structure unless the alternative must be addressed. The conventional word for a thing is the term practitioners of its discipline use for it, where one exists.
    - A line uses each word in its literal sense: `name` as a verb is for giving a thing a name, and nowhere else.
        * comment: The user's words, in the Global Style of the user's `~/.claude/CLAUDE.md`: "Use words only in their literal sense, e.g. the usages of "names" "carries" "holds" "reads" must be literal."
- Write that a thing always holds or never holds only where you know it does. Where a check is what the claim rests on, state the claim over the instances the check covered, such as the task's inputs.
    - Such a claim most often uses `never`, `every`, `no` or `nothing`.
        * comment: The user's words, session `6dfaef3b`, 2026-10-02T04:45:16Z: "don't write that something always or never holds unless you know it does. [the common words to watch out for]".
- Write a statement in the imperative mood where it tells its reader to do something or sets a rule on an act its reader does, and every other statement in the indicative mood.
- A reference to a document or a section is a link, as [Links](src/controlled_markdown/writing.md#links) gives it.
- A bare path stands in code that compares it, and nowhere else.
- A document tells no agent to write a file named `report.md`.
    * comment: The user's words, session `631a6654`, 2026-09-23T22:50:48Z: "nothing shall be named report.md", after the harness blocked a write to that name.

## Checking
- `uv run python -m controlled_markdown check` reports each line that breaks a rule, with the rule's message.
- `fmt` in place of `check` rewrites a file in canonical form.
- The document set is the paths under `[tool.controlled_markdown]` in [pyproject.toml](pyproject.toml).
- [Writing a document](src/controlled_markdown/writing.md) states a rule where the message is not enough, or where the file shows no instance of the construct you need.

## Reviewing a change
- A reader's context is everything it receives, from its entry point to the last message, in the order it arrives.
- `uv run python scripts/context.py contexts` lists the readers, and `uv run python scripts/context.py context <reader> [args]` prints one reader's context, with the argument the listing gives for that reader.
- The `context` output leaves out [arc-workspace](CLAUDE.md), each `comment` directive with the lines under it, and the system reminders [workers.py](tools/console/solver_console/workers.py) prefixes to a console message.
- The reader of a comment is the editor of its file, whose context is the `context agent doc-editor` output, then that file with its comments, and, for a comment in [arc-workspace](CLAUDE.md), which is read raw, each reader of that file as well.
- Review a change by reading each context that contains the changed lines, or whose reader reaches by links a section that contains them, from its entry point to the end, as the reader of that context.
    - `uv run python scripts/context.py contexts --diff <commit>`, with `git merge-base HEAD master` as the commit, lists each reader whose context the change alters or leads by links to a changed section, and under each reader, each such section outside its context, then each link on the way to such a section.
    - A reader of the change is a reader that listing gives, other than one it marks `(removed)`, whose context the change alters or that reaches a section listed under it.
    - Read the `context` output for each reader of the change, with each other text [Where each text is](#where-each-text-is) gives that reader as reading, and judge each line as a reader that has only that context.
    - A line `<target> via <source>` of that listing gives a link: a line of `<source>` links to `<target>`, and `<source>` is `context` where the link stands in the reader's context.
    - A link leads the reader to its target where its line has the reader read that target, under the condition that line gives, and not where its line gives that target as a document to edit, describe or mention.
    - A reader reaches a section only where a path of the links listed for it, each of which leads the reader to its target, runs from `context` to that section. Read each section a reader reaches as part of that reader's context, at the line of that context that has the first link of such a path.
    - Follow the reader through each operation its context gives, in order. At each operation, ask what the reader is focused on, what it holds, where each output it makes goes (a file, its report, or its reply), and whether the context gives what the operation needs.
    - Where one pass takes another pass's output, check that the form the first pass's context gives that output is the form the second pass's context reads.
    - A finding needs a decision where its possible fixes differ in what a reader is told or may do.
    - Report each line that gives an agent a power it did not have, such as deleting, overwriting, renaming, reverting, or deciding what the user decides, and each line that moves a step between the user, the session at a terminal, and an agent. Report each such line as an item of its own, to the one who asked for the change.
    - Start from the assumption that defects are there, and trace each one to the line that caused it, or to the premise that is wrong.
    - Treat a finding as one instance of a kind, and search every context for the other instances of that kind.
    - After each fix, read the contexts the fix touches again for contradictions.
- Report nothing on a decision the one who asked for the change gives as already settled, other than a line the change adds that is a restatement or an elaboration for one of its readers: report each such line to the one who asked for the change, with the line of that reader's context that it restates or elaborates. A meaning that carrying out that decision drops for a reader, other than one the decision states, is a finding.

### What stays and its whole unit
- Judge each part the change adds to a context, keeps there or moves within it, and, where no change is under review, each part of the context, by the rules of [What a file holds](#what-a-file-holds) and [What goes where](#what-goes-where). Report each part that reaches its reader before the reader meets the part of its work that needs it, and each section that holds parts that different operations need, so that no condition loads one part without the other. The handbook and the lib, in the context of a reader that loads them up front, are neither.
    * comment: Request 6-402, transcript `7fd429fb-e3be-4173-9b0e-df52f507d6a2` at 17:57:14Z: the doc reviews of the agents' documents, with the line above in their context, reported no part of a context that only some of its reader's operations need, such as the rules of draft revision, held steps and the process assessment in the ticket analyst's context.
- Read each section and each rule the change touches whole, for a rule grown by stacked conditions, exceptions or cases that [What a file holds](#what-a-file-holds) has you restructure.
    - A line far longer than the lines around it is a sign of such growth: judge its rule and its section, and where they have grown so, ask in your finding for their restructure.
- For each line the change cuts or moves in a document, or drops from a render, check that every reader whose context contained that line, or who reached it by links, still gets what it said, and report each reader that loses a meaning.
- Run `uv run python scripts/context.py context --diff <commit> <reader> [args]` for each reader of the change that `contexts --diff` lists, with the commit it took. Read the diffs it prints, apart from that of a section the reader does not reach, for the lines that reader lost, and judge each line it gained against the operations that reader's context gives it.
    - Report each gained line that does not fit those operations. Where the change's intent puts that line on that reader, report it to the one who asked for the change.
        * comment: On 2026-10-04, in session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a`, the doc-reviewer `a628be02072210fa7` read the whole context of [Operator](prompts/agents/operator.md), judged the foreground command rule it gained against the change's scope, "the agents that run commands", and did not report that the rule does not fit an agent that launches agents. On 2026-10-05, the operator `a37be74e20c8008ae` polled up to 10 minutes on a backgrounded merge.

### How the kept text reads
+ line review
- Judge no line that a finding of [What stays and its whole unit](docs/handbook/editing.md#what-stays-and-its-whole-unit) asks to cut or restructure.
- Check each line against every rule that [Writing a file](#writing-a-file) and [Writing a document](src/controlled_markdown/writing.md) give a line, and, where [Writing a file](#writing-a-file) has you read [Templating a document](src/controlled_markdown/templating.md), every rule that document gives a line.
- List every term the change introduces, headings and labels included, wherever you write the review, apart from its findings, and report as a finding each that breaks the rule on conventional words in [Writing a file](#writing-a-file).
    * comment: On 2026-10-04, the doc-reviewer runs `ab58e2331176baa7c` and `a8875999997fee88e` of session `dc433af1-cf87-408d-ab9d-9a1ede6b1b2a` applied the rule on conventional words to other lines of a diff that added the section name `pass-issues`, and their findings did not report that name.
- Find each line of the document set or of prose in code, outside the change, whose premise the change makes false, read it in each of its readers' contexts, and report each that no longer stands.
