# Writing

How to write and edit documents and code. For code, prose includes docstrings, comments, printed messages, and similar.

Writing has two sides. Reader-side is what lands in the doc — calibrate to what the reader knows and needs. Writer-side is context for writing (your understanding, your reasoning, explanations from chat) — it stays out of the doc. Default reader is you.

## Process

1. Finish the primary task — code or doc work — before revising.
2. Say `<revision>`.
3. Check prose for issues.
4. Revise within your thinking.
5. Repeat until no issues.
6. Edit.
7. Read the result cold for gaps like undefined terms and incomplete specs. Flag if present.
8. If updating, review the result for inconsistencies, contradictions, tensions, and redundancies with related docs and code. Flag if present.
9. Say what was reviewed.
10. Say `</revision>`.

This runs per turn, not per edit or per session. Chat that produced the draft optimizes for user agreement on the framing; the result has to stand alone.

Checks run at both phrase and concept levels. Phrase-level catches Issues that surface in wording; concept-level catches structural problems (fit, contradictions, altitude).

## Issues

Counterproductive compulsive tendencies.

### Overfitting

Writing needs to be general enough to cover cases beyond the one that triggers probing and doc revision. The compulsion: writing overly strong instructions, as if overcompensating for a specific mistake that just happened.

### Leakage

A new reader has neither the prior version nor the session that produced the current one. Writing that hangs on either of those referents is noise at best, distorting at worst. Compulsions include:

- **Edit-deltas** — phrasing about what was changed, e.g. "does not X" against removed content. Presumes a prior version.
- **State-comparisons** — words like "stay", "still", "unchanged" that presume a reference state.
- **Session anchors** — content from the session, e.g. vocab from chat or terms from other docs.

### Fabrication

Specifics make writing feel concrete, so when actual data is thin, plausible-looking material fills in automatically. The compulsion: invented imperatives, made-up examples, claims not actually observed.

Inventing is warranted when the concept is genuinely abstract and the reader needs a concrete instance to grasp it. The compulsion: inventing for surface concreteness when the concept is already grounded.

### Verbosity

Padding doesn't add signal; it dilutes it. The compulsion: redundant phrasing and rhetorical inflation. A specific shape: contrast structures like "not X, but Y" used when no real alternative is being ruled out.

- BAD: "It isn't a new wellness trend there; it's baked into how people eat."
- GOOD: "Fermented foods are dietary staples there, so probiotics feel like an extension of existing habits."
