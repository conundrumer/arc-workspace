# Classification rubric

You are labeling pairs from a coding-agent transcript corpus. Each row has:
- `preceding_assistant_message` — what the agent said just before the user's comment (often a review, report, or callouts list; may be trimmed in the middle, marked `...[trimmed]...`)
- `user_comment` — the user's next message
- `following_user_messages` — up to 5 later user messages in the same session, in order (context only)

Label each row on two axes.

## 1. origin

- `FROM_REPORT` — the comment engages something the preceding assistant message itself raised: answers a question it asked, rules on an option it listed, quotes or paraphrases one of its items, picks among its alternatives, vetoes something it proposed, or tells it to proceed with a specific named thing from it.
- `USER_ORIGINATED` — the comment raises something the preceding message did not: a new alternative model, a naming objection, a simplification probe, a recalled prior solver or task, an observation about the code or data the message never mentioned, a process or tooling demand out of nowhere.
- `MIXED` — genuinely both (engages a raised item AND introduces a new concern), or not determinable from the pair (preceding message too thin, comment too elliptical to place).

Judge from the pair alone. A comment that merely reacts to the fact that work happened ("commit it", "that's wrong") without touching any specific item the message raised is USER_ORIGINATED only if it introduces new substance; if it rules on the work the message just described, it is FROM_REPORT.

## 2. raised-item pickup

Look at the preceding assistant message. Find every **discrete item** it raised: a judgment call it could not settle, a call it made that only the user can ratify, an open question, a proposal, a caveat, a listed alternative, a numbered callout. A discrete item is something the user could separately engage or ignore.

Classify each such item into exactly one kind, using the descriptions below. **Match an item on the description, not on the label.** An item that fits no description goes in `other`.

- `lib_candidates` — a solver-local form proposed for programs/lib.dl or docs/wf-solver/proposals/, with the protocol's recommendation
- `doc_gaps` — a docs/wf-solver rule that is missing, wrong, or misleading, with the edit it needs
- `simplification` — redundancy or awkward reading in the shipped solver, such as a relation with one consumer or a line that misleads
- `naming_vocab` — a name with shared scope — a lib comp, a type, doc wording, a proposals entry; a name local to one solver is not this kind
- `correctness_risk` — a defect, or an implicit assumption the solver leans on, such as a property every input happens to satisfy
- `lint_tooling` — an improvement or a defense of the linter, run budgets, timing, or index tooling; a broken tool is P0, not this kind
- `alt_models` — a rival model dispatched: killed by data, an alt impl with the same outputs, or dropped as not worth building
- `unwitnessed_edges` — a divergence between models that no pair in the task exhibits, stated with the constructed witness that would separate them
- `hedges` — a trailing qualification on a settled call, not a discrete open item
- `other` — a discrete item that matches none of the descriptions above

Two rules that follow from the descriptions and are easy to get wrong:

1. `naming_vocab` requires shared scope. A quibble about a name that lives only inside one solver file is **not** `naming_vocab` — it is `other` (or `simplification`, when the point is that the name misleads the reader of that solver).
2. `alt_models` requires the rival to have been **dispatched** in the message — killed by the data, shown to give the same outputs, or dropped as not worth building. A rival merely mentioned as still open, or floated without a disposition, is `other`.

Emit:
- `raised_kinds` — list of kinds the message raised, one entry per discrete item (repeat a kind if the message raised two items of that kind); empty list if it raised no discrete items
- `picked_kinds` — the sublist of `raised_kinds` the user engaged, in `user_comment` or in `following_user_messages`. "Engaged" means ruled on, argued with, asked about, approved by name, or acted on. Silence is not engagement.

Everything in `raised_kinds` not in `picked_kinds` counts as silently ignored. Fill `raised_kinds` for every row, including `USER_ORIGINATED` ones; for those, `picked_kinds` stays empty unless the user did touch one of the raised items.

## Output

Write ONE JSON array to the output path given in your prompt. One object per input row, same order:

```json
{"id": "...", "origin": "FROM_REPORT|USER_ORIGINATED|MIXED",
 "raised_kinds": [], "picked_kinds": [], "note": "short phrase of evidence"}
```

`note` is one short phrase naming the evidence, e.g. "rules on option 2 of the review's list" or "raises slab-anchor perf the review never mentioned". Keep it under 12 words. No prose outside the JSON file.
