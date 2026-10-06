# Preference notes
- The goals and the preferences the user has stated on the project and on how its agents work.

## The user's preferences
- Each statement gives a goal or a preference the user stated, in the user's sense, and the quote under it gives the user's words.

### Goals
- The agents do their best work efficiently before the solvers are brought to their best form.
    > agents must do their best work the most efficiently before we can make solvers in their best form
- Token efficiency comes first and time second, and speed is bought with no contention and no excess coordination between agents. A split of work across agents that saves about 30 minutes for about 150k tokens is worth it.
    > priority 1 is efficiency , priority 2 is fast, but don't sacrifice efficiency for it like contention and excess coordination
    > 30 min saved for 150k tokens is worth it
- The process, the code and the semantics are kept in their best state, and the code is maintainable.
    > ensure everything is in its best state. process code semantics etc
    > we also want to make the code maintainable
- Good software practice is applied without the user asking for it.
    > it is strange i have to keep asking for good SWE practice over and over again
    > ok do it now. DRY it all up
- The process does not take long, and takes no more of the user's CPU than it needs. Agents notice slowness themselves, with no overfitting and no excess tooling.
    > remember the goal is to have make the process not take too long
- Performance does not regress, and time is checked as output is.
    > proactively ensure perf doesnt regress
- The lib is in its best form, a full rewrite allowed: the authoritative vocabulary of the priors ARC tasks compose, with perfect interfaces and fast implementations.
    > my next goal is to make the lib in its best form. open to totally rewriting it.
    > you already know we should use everything at our disposal to make the interfaces Perfect and the impl Fast
- The tooling may come to serve generators, or another frontend language, as well as Souffle solvers, and its divisions follow what varies.
    > maybe we'll extend to generators and not just solvres. or maybe we'll use a diff language as frontend

### Fixes
- A fix is general, not fitted to the last incident, and adds no tooling the problem does not need.
    > you're overfitting
    > this seems like overengineering
    * comment: With the lines of [Decision notes](prompts/agents/notes/decisions.md) "Make no option the default that fits only the instance that raised the decision." and "Prefer the general option, the one that settles the other instances of the question too, and where tooling can enforce the rule, the tooling change." in its context, an assignee added a hook that parsed every agent's Bash call to deny a harmless pattern, on the evidence of one solver read that cost one extra command: ticket 2-153, on ticket 3-4.
- A failure's cause is fixed, not only the state the failure left.
    > i dont want oyu to only fix the state, they are symptoms and i want to fix the cause
    > should have root-caused all these issues
- A recommendation rests on evidence of a need. What is worth anticipating is a practice that prevents a bad situation of the kind that prompted past changes, not a mechanical gap in the tooling.
    > there's no evidence for a need for "not covered", and that's "dumb" stuff.
- A miss is not answered by a rule that records it: instructions are kept few, since a model follows a limited number of them, and none restates another document.
    > you know how models have a limit of the number of instructions they can follow?
    > dont give yourself too many rules, and don't restate
- A design is thought through for how it can fail before it is implemented, and the agent that implements it is told to do so.
    > i realize we should rly think thru these things
    > just tell the implementing agent to ultrathink it through before implementing
- Simple mechanisms are preferred. Agents are watched as the user watches them, by reading what they do, with no classifier.
    > i'm preferring simple ways of doing things like thats why we're using the file system as tickets DB and md files for the ticket data
    > i dont want overengineering like using classifiers, and it doesn't need to be that granular
- Machine load is fixed through the cost of the work, never by a cap on agents or on commands.
    > the cap will be moot once the gate is not grossly inefficient
    > no agent cap that's not the issue here
- Where an agent departs from a rule, the agent is asked why before its document or the tool changes, and its answer is the evidence.
    > we should ask sonnet op why it started waiting in fg
- A claim that an agent wasted work is checked against its procedure before the agent is blamed.
    > so ... just let the agent not listen to the procedure and be wasteful?
- A review of the tool reads a pass's transcript call by call, in the agent's position, since a review of outputs misses design bugs.
    > it seems after all our efforts, we still have bugs. design bugs more like. no review from agent's POV
    > you need to think from the pov of solver agents. this means, you have to put yourself in their position.
- A solver pass that ran under a wrong rule is run again once the rule is fixed, not patched.
    > i want these passes to run with no problems
- A fix that removes an outdated rule for efficiency is approved in general.
    > approve efficiency things fixing outdated rules in general

### Tools
- The tooling keeps no backwards compatibility with old forms: solvers are consistent and in their best form.
    > wait no. solvers should be consistent and be in their best form
    > pros of perfect bakcwards compatibiltiy does not outweigh the ocns
- The tooling has no inefficiency such as text processing in a hot path.
    > the tooling shouldn't have inefficiencies like this.
- A regression check does not substantially slow the work it guards, and a merge's gate takes under a minute.
    > would like it to be <1min
    > gates shouldn't be so expensive in the first place
- No output or measurement that a file already holds is computed again, the "before" side of a comparison included.
    > no i mean, running the "before" results of the diff
- A witness entry may reassign any parameter, a grid-valued one with its anchor included, unless a good reason constrains it.
    > unless there's a good reason to constrain, we should allow specifying a stamp grid and anchor
- The tooling serves the agents, and a choice on its design is not the user's. The user reads no code other than solver code, and no tool output.
    > I should not need to decide
    > the only code i read is solver code
    > no, the tool is for agents. i mean, consequence wrt goals
- The solver console, retro, the `.claude/workflows` scripts, the role prompts and the `/session` skill are deprecated: each is noted as deprecated, is not removed, and does not get in the way.
    > console is being deprecated, just dont let it get in the way
    > just note that retro is deprecated don't actualyl rmeove
- Project content and ephemeral project state are kept apart in git.
    > i dont want to mix project contents w ephemeral project state
- A migration never loses an existing persistent working file.
    > let's make sure we done lose the existing persistent work files
- Nothing is recorded that nothing reads afterwards, and no state is kept in a second copy.
    > dont want pointless bookkeeping
    > it is harmful to give yourself busy work by not keeping things DRY
- Git permissions given to agents are scoped.
    > i shouldn't give all git permissions always. it should be scoped
- A change to the user's global Claude configuration is a project of its own: it is verified first, and made by an agent on `~/code/claude-config` where it needs no judgment.
    > send it as an agent separate f rom this project, it's a different project scope
    > claude-config changes needs verification. if no judgment needed send agent to fix

### Documents
- The documents are written first to serve the agents that read them, and new agent-facing text is checked to serve each agent it reaches before a pass runs on it.
    > the priority is that the docs should best serve the agents
    > i forgot we need to ensure new text serves agents.
- Load-bearing text admits no misreading, a rewrite adds no verbosity, and a rule for something intuitive takes few words.
    > i dont want verbosity either! we need to grade severity of looseness and triage
    > why is it taking so many words to describe something intuitive
- An edit of text is checked for a change of meaning it was not meant to make.
    > i mean, i wanted to check if we changed the meaning
- The documents are structured so that changes to them run in parallel, as changes to code do.
    > ideally the docs are structured such that it can run in parallel like code
- The documents make evident which agent takes a kind of work, so that the user never names it, and lead each agent to what it needs, so that agents do not explore the same ground again.
    > i shouldnt have to state it
    > improve docstrings/docs to help w nav
- An agent whose body is a document gets no instructions on how to follow that document.
    > that doesn't feel right. why should it get instructions on how to follow a doc?
- A test of agents' reading is not primed: its prompt gives the text under test and no gloss of its terms.
    > you primed them
- [arc-workspace](CLAUDE.md) holds only what every session needs.
    > concerned about claude.md getting bloated with commands
- [Case inclusion: the decision history](docs/wf-solver/case-rule-history.md) holds only what helps decide case inclusion and related questions from the user's rulings.
    > the purpose of hte doc is to help decide on case inclusion and related based on my decisions
- The user writes no text: an agent makes each rewording, and ensures the meaning of the new text and of the text it touches.
    > i don't write text. make this update happen and ensure the semantics are correct and anything it touches

### Agents
- Work that can run in parallel on disjoint files is split and run at once, with no agents tripping over each other.
    > if parallelizable make it so
    > i dont want to burn tokens on agents tripping over each other
- The agents' processes are efficient, and a brief costs no run its work does not need.
    > i dont understand you but i am once again asking you ensure processes are efficient
- An agent stopped by the usage limit is resumed by a message, not launched again.
    > Resume I mean. Usage limit was hit
- The Create and Refine passes read the full lib interface up front by a conscious decision.
    > it was a conscious decision to load  the full lib interface up front
- A session the user launches with the handbook appended is intentional, and its cost is not waste.
    > i intentionally launched a handbook session bc i wanted to talk about things that rely on the handbook being in context.

### Names
- An existing name is no precedent: a term is not kept because a document or the lib uses it.
    > we don't have to keep it that way. choose the best term
    > i do not agree w many of the existing names, dont weigh as precdence
- A name may be abstract where it is precise, with a qualifier where needed, within the domain, and a mathematical word imprecise for the thing is vetoed.
    > dynamical systems is too far. i want abstractions within the domain. veto orbit
    > veto all math words that are imprecise for the thing
- Abbreviations follow the software convention, judicious and consistent.
    > we sohuldn't entirelt ban abbrvs. just need to be judicious and consistent
- A label is chosen for its use in deciding how to act on what it labels.
    > it should be useful for acting upon
- "Task" may name a work item as well as an ARC task.
    > i am open to task, dont care ab out that overload

### The lib
- Convenience, a site count included, is never a reason to keep a relation in the lib.
    > convenience is not a reason
- ADTs are not used freely as another way to write a disjunction.
    > historically, without the ADT restriction, they've been freely used and I felt it increased program complexity, like it's another way to do a disjunction
- Boilerplate is counted in atoms, not lines.
    > also prefer counting atoms not lines.
- The lib need not be written in Souffle, and custom functors and other implementations are allowed.
    > we can also write custom functors and whatever. the lib doesn't have to be written in souffle
