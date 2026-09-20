# Classification rubric
- You are labeling pairs from a coding-agent transcript corpus.
- Each row carries three fields.
    - `preceding_assistant_message`: what the agent said just before the user's comment, often a review, report, or callouts list. It may be trimmed in the middle, marked `...[trimmed]...`.
    - `user_comment`: the user's next message.
    - `following_user_messages`: up to 5 later user messages in the same session, in order, as context.
- Label each row on two axes.

* comment: when editing this doc
    - The kind descriptions match `CALLOUT_RATES` in `tools/console/solver_console/prompts.py` verbatim. A change to one invalidates the store; [Callout rate recalibration](README.md) says what a change costs.

## Origin
- `FROM_REPORT`: the comment engages something the preceding assistant message itself raised. It answers a question it asked, rules on an option it listed, quotes or paraphrases one of its items, picks among its alternatives, vetoes something it proposed, or tells it to proceed with a specific named thing from it.
- `USER_ORIGINATED`: the comment raises something the preceding message did not, such as a new alternative model, a naming objection, a simplification probe, a recalled prior solver or task, an observation about the code or data the message never mentioned, or a process or tooling demand out of nowhere.
- `MIXED`: genuinely both, engaging a raised item and introducing a new concern, or not determinable from the pair, the preceding message being too thin or the comment too elliptical to place.
- Judge from the pair alone.
- A comment that reacts to the fact that work happened, such as "commit it" or "that's wrong", without touching any specific item the message raised, is `USER_ORIGINATED` only where it introduces new substance. Where it rules on the work the message just described, it is `FROM_REPORT`.

## Raised-item pickup
- Look at the preceding assistant message and find every **discrete item** it raised: a judgment call it could not settle, a call it made that only the user can ratify, an open question, a proposal, a caveat, a listed alternative, a numbered callout.
    - A discrete item is something the user could separately engage or ignore.
- Classify each such item into exactly one kind, using the descriptions below.
- **Match an item on the description, not on the label.** An item that fits no description goes in `other`.
- `lib_candidates`: a solver-local form proposed for programs/lib.dl or docs/wf-solver/proposals/, with its entry and survey result
- `doc_issues`: a docs/wf-solver rule that is missing, wrong, or misleading
- `simplification`: redundancy or awkward reading in the shipped solver, such as a relation with one consumer or a line that misleads
- `naming_vocab`: a name with shared scope — a lib comp, a type, doc wording, a proposals entry; a name local to one solver is not this kind
- `correctness_risk`: a defect, or an implicit assumption the solver leans on, such as a property every input happens to satisfy
- `lint_tooling`: an improvement or a defense of the linter, run budgets, timing, or index tooling; a broken tool is P0, not this kind
- `alt_models`: a peer model ruled out: by the data, or as having no divergence witness against a case the solver has
- `unwitnessed_edges`: a divergence between models that no pair in the task exhibits, stated with the constructed witness that would separate them
- `hedges`: a trailing qualification on a settled call, not a discrete open item
- `other`: a discrete item that matches none of the descriptions above
- One rule follows from the descriptions and is easy to get wrong.
    - `naming_vocab` requires shared scope. A quibble about a name that lives only inside one solver file is **not** `naming_vocab`. It is `other`, or `simplification` where the point is that the name misleads the reader of that solver.
* comment
    - A second rule stood here, on `alt_models` requiring the rival to have been dispatched. It is out of the rubric and out of the labels the store holds.
- Emit two lists.
    - `raised_kinds`: the kinds the message raised, one entry per discrete item. A kind repeats where the message raised two items of that kind, and the list is empty where it raised no discrete item.
    - `picked_kinds`: the sublist of `raised_kinds` the user engaged, in `user_comment` or in `following_user_messages`. Engaged means ruled on, argued with, asked about, approved by name, or acted on. Silence is not engagement.
- Everything in `raised_kinds` and not in `picked_kinds` counts as silently ignored.
- Fill `raised_kinds` for every row, `USER_ORIGINATED` ones included. For those, `picked_kinds` stays empty unless the user did touch one of the raised items.

## Output
- Write ONE JSON array to the output path given in your prompt, one object per input row, in the same order.
    ```json
    {"id": "...", "origin": "FROM_REPORT|USER_ORIGINATED|MIXED",
     "raised_kinds": [], "picked_kinds": [], "note": "short phrase of evidence"}
    ```
- `note` is one short phrase naming the evidence, such as "rules on option 2 of the review's list" or "raises slab-anchor perf the review never mentioned". Keep it under 12 words.
- Write no prose outside the JSON file.
