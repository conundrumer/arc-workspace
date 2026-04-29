# Variants and alts

Two ways the canonical form of a task isn't the only valid one.

- **Variants** — sibling tasks at increasing levels of rule-consistency.
- **Alts** — alternative valid outputs within a task.

## Variants (A / B / C)

The suffix denotes a fixed level of increasing rule-consistency over canonical:

- **A** — Removes incidental noise. Rule preserved.
- **B** — Removes overly complicated rules. Symptom: multiple people disagree over the rule, or the complexity isn't justified for what the task suggests.
- **C** — Removes rule exceptions. Symptom: the solver has code dedicated to handling just one example.

A variant patch is a diff against the next-lower variant present (else canonical). Tasks may include any subset of levels.

## Alts (rule / tiebreak)

An alt is an alternative valid output for a single example. ARC scoring is pass@2, so each example carries at most one alt; the solver passes if its output matches base or alt.

- **rule** — a different rule interpretation yields a different output. The solver should commit to one consistent reading.
- **tiebreak** — one rule, multiple valid outputs. Typically arises when the rule is symmetric or order-independent.

Alts are declared via the `@branch` patch verb and stored on the example as a singleton `alt` field.
