# Principles

A solver is a model of a task. The body encodes the task's structure; the Consts hold its parameters. Three principles shape that model: fidelity to the task, invariance under its variations, and coverage over modeling forms.

## Fidelity

The model is faithful to the concept of the task — the actual task, not an implementation artifact of how the data is encoded. The failure mode: the body carrying structure that doesn't belong to the task (a dictionary that orders its keys, an iteration that numbers cells, an arithmetic step that conceals a relational operation).

**Relational form.** ARC concepts are relations between cells, regions, and properties. Encoding as relations keeps the model faithful to the concept. Dictionaries or imperative loops carry structure the concept didn't have. Ordered iteration should only be used when the task has ordered structure.

**ARC reality.** Same at the level of values. ARC concepts work in colors, directions, axes. Projecting these into bools, ints, or other derived types pulls the model away from what the task actually is. Arithmetic enters as fallback when no clean relational form exists. Numbers are one layer of indirection from the concept; arithmetic adds a second.

## Invariance

The body is symmetric under variations of the task that don't change its essential structure — rotations, mirrorings, recolorings. The Consts capture each variation as a value the body parameterizes over. The failure mode: tying the body to one task in the family when the family is symmetric.

**Color.** Colors in ARC have no intrinsic structure beyond identity. If the task has structure over colors — an ordering, a mapping, a partition — that structure lives in Consts. Body comparisons by enum ordinal or fixed-order iteration over C0..C9 invent structure that isn't in the task.

**Orientation.** A task may privilege a specific direction, axis, or transformation; absent that, no choice is privileged. The 4-distance Position encodes this — no corner serves as origin. The primitive types Dir, Axis, DiagDir, DiagAxis, and D4 express orientation choices as values, so a sibling task with different orientation swaps a Consts value rather than restructuring the body.

**Equivariance.** Whether a primitive is safe under orientation parameterization is a property of the primitive: does it commute with D4? A primitive `f(P, ...) → (P_out, ...)` is *equivariant* when `f(apply(D, P)) = apply(D, f(P))` for every D in D4 and every P in its domain. The formula may read a specific Position slot internally — `divide`'s `O = Near / (Sh+G)` works from the near edge — yet the slot choice washes out, because the primitive's constraints force the algebra to be symmetric: flip the input and the output flips with it. `divide` and `divide_by_size` are equivariant.

A primitive is *non-equivariant* when the slot choice is observable — it yields different outputs under different transforms of the same physical cell. The diagnostic is the equality above: inequality on any (D, P) means non-equivariant. A primitive that computes its intile mapping as `T mod period` fails it — for a non-divisible frame extent, `T mod period` and `B mod period` give different mappings for one cell.

Equivariant primitives are safe with the apply-sandwich (`apply(D, P, P') → f(P') → apply(D_inv, ...)`). A non-equivariant primitive needs an explicit anchor parameter (e.g. `anchor: DiagDir`), or should be replaced by an equivariant alternative: 332efdb3 models its period-2 pattern via `divide_by_size` with K=1 G=1 rather than a `T mod period` primitive.

## Coverage

A task can be modeled multiple ways — each model claims the task is an instance of some task family. Modeling the same task under several families gives coverage over its plausible identities. ARC training tasks are intended to teach core knowledge priors in pure form; coverage surfaces which prior the task could be teaching.

Generalization happens at the family level. All tasks in a family share a body; the data that distinguishes a task within its family lives in Consts. The body parameterizes; Consts fills in.

Sibling tasks under family F are other tasks in F. A solver may carry multiple model claims via cases of `Choice`; with multiple claims, sibling-talk specifies which family.

Models are typically mixes of two kinds of content:

- *Data*: facts a program can derive from the train pairs. Flattens composition — represents a relationship as data with the structural decomposition hidden. The relationship can be at any level (cell mappings, shape symmetries, intermediate states).
- *Ops*: composed primitives. The rule literally *is* composition. Makes the structure that's there visible.

At any choice node, a choice can lean toward data (flatten) or toward ops (expose).

**Alt model vs alt impl.** Two candidates are the same model iff (a) same Consts shape — same parameters, field types, relations — and (b) same outputs for every (input × Consts-value) in that shape. Different on either → different models. Output divergence on any single input (current Consts fixed) settles different-model when it fires; Consts-shape divergence catches the case where two candidates coincide on outputs for the current Consts but parameterize into different sibling families. Op compositions split the same way: re-decomposing the same property over the same Consts is an alt impl. Coverage extends within op-leaning territory only when an op composition commits to a different Consts shape.

**Worked examples — alt models.**

- *44f52bb0 `$Direct` vs `$GroupMatch`.* `$Direct` Consts: `syms` (one D4 subset), `sym_out`, `asym_out`. Body: input invariant under every D in `c.syms` → emit `sym_out`; else `asym_out`. `$GroupMatch` Consts: `mapping_sym` (id → sym set members), `mapping_out` (id → grid). Body: a containment check (each group ⊆ input's invariance set); the largest covered group wins; emit that entry's grid. Outputs coincide on every input under this task's Consts. Sibling families diverge — `$Direct`'s siblings are binary symmetry-classification tasks (parameter: which sym set); `$GroupMatch`'s extend to multi-class symmetry-id tasks where ≥3 groups map to distinct outputs (parameter: the full mapping table).

- *34b99a2b `$Lookup` vs `$Xor`.* `$Lookup` Consts: `combine_member` + `combine_out` — a pattern → output color table. Body: set-equality match against each pattern. `$Xor` Consts: `bg` + `out_fill` — two color sentinels. Body: count contributing non-bg cells per output position; emit `out_fill` iff exactly one. Different Consts shapes, different sibling families (pattern-substitution vs per-cell XOR-fold), different priors (lookup vs algebraic combination).

**Worked example — alt impls.**

- *Three alternative bodies for 44f52bb0 `$Direct`.* Orbit walks orbit equivalences via transitive closure; Closed computes the generated group closure explicitly then runs the invariance check over the closure; Patterns enumerates all symmetric grids in Consts and does membership lookup. All three would share `$Direct`'s Consts shape — single sym set + two output grids — and produce identical outputs on every input. Each is an alt impl of `$Direct`; adding any as a Choice case wouldn't extend coverage — same family, same prior, same generalization.

Useful coverage gives one model per plausible family. The prior becomes visible from each plausible angle.
