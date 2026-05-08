# Principles

A solver is a model of a task. The body encodes the task's structure; the Consts hold its parameters. Three principles shape that model: fidelity to the task, invariance under its variations, and coverage over modeling forms.

## Fidelity

The model is faithful to the concept of the task — the actual task, not an implementation artifact of how the data is encoded. The failure mode: the body carrying structure that doesn't belong to the task (a dictionary that orders its keys, an iteration that numbers cells, an arithmetic step that conceals a relational operation).

**Relational form.** ARC concepts are relations between cells, regions, and properties. Encoding as relations keeps the model faithful to the concept. Dictionaries or imperative loops carry structure the concept didn't have. Ordered iteration should only be used when the task has ordered structure.

**ARC reality.** Same at the level of values. ARC concepts work in colors, directions, axes. Projecting these into bools, ints, or other derived types pulls the model away from what the task actually is. Arithmetic enters as fallback when no clean relational form exists; it doesn't carry conceptual weight.

## Invariance

The body is symmetric under variations of the task that don't change its essential structure — rotations, mirrorings, recolorings. The Consts capture each variation as a value the body parameterizes over. The failure mode: tying the body to one specific variant when the task is symmetric across the family.

**Color.** Colors in ARC have no intrinsic structure beyond identity. If the task has structure over colors — an ordering, a mapping, a partition — that structure lives in Consts. Body comparisons by enum ordinal or fixed-order iteration over C0..C9 invent structure that isn't in the task.

**Orientation.** A task may privilege a specific direction, axis, or transformation; absent that, no choice is privileged. The 4-distance Position encodes this — no corner serves as origin. The primitive types Dir, Axis, DiagDir, DiagAxis, and D4 express orientation choices as values, so a sibling task with different orientation swaps a Consts value rather than restructuring the body.

## Coverage

A task can be modeled multiple ways — each model claims the task is an instance of some task family. Modeling the same task under several families gives coverage over its plausible identities. ARC training tasks are intended to teach core knowledge priors in pure form; coverage surfaces which prior the task could be teaching.

Generalization happens at the family level. All tasks in a family share a body; the data that distinguishes a task within its family lives in Consts. The body parameterizes; Consts fills in.

Models are typically mixes of two kinds of content:

- *Data*: facts a program can derive from the train pairs. Flattens composition — represents a relationship as data with the structural decomposition hidden. The relationship can be at any level (cell mappings, shape symmetries, intermediate states).
- *Ops*: composed primitives. The rule literally *is* composition. Makes the structure that's there visible.

At any choice node, a choice can lean toward data (flatten) or toward ops (expose). Different op compositions of the same task are also distinct models — coverage extends within op-leaning territory.

Useful coverage gives one model per plausible family. The prior becomes visible from each plausible angle.
