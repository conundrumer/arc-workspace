# Determination

It builds the derivation of each stored parameter from the observed data, by `DET`, the proposers and `RIGID_DET`. It rests on [rigid](../../docs/arclog/rigid.md) for `RIGID_DET`.

The step of the [build order](overview.md#build-order) that builds it ends when the determined values match the stored `param` records, as [verification.md](verification.md) checks them, for each parameter that no case with an open parameter or a `DEMONSTRATED` form reads. The other parameters are checked in [Every case](cases.md#every-case).

## `DET`

- The `DET` relations are determined in dependency order.
- A `DET` whose body names no proposer and no domain is a determination by the solver's clauses: its rows are its value, and the train pairs filter none of them, as [determination](../../docs/handbook/principles.md#models-and-tasks) gives that kind.
- A `DET` whose body gives several candidates, from a proposer or a domain, is filtered by the train pairs, as [determination](../../docs/handbook/principles.md#models-and-tasks) gives. The engine enumerates the assignments of these `DET` relations lazily, in dependency order. It runs each case that reads them on the train pairs at each assignment, and keeps, per case, the assignments at which that case solves every train pair. A train pair with two candidates is solved where the case solves either of them, as [Solves](cases.md#solves) gives: the stored assignment is one function of the evidence, and the split task is chosen after it, as [Cases](../../docs/handbook/principles.md#cases) gives Fit. `ex_output` holds the pair's given output. The result cache shares the entries that an assignment leaves unchanged.
- A parameter that several cases read takes the values that every such case with an assignment that solves the train pairs admits, as [Parameters across cases](../../docs/handbook/principles.md#parameters-across-cases) gives.
- A case's open values of a parameter are those that [Params](../../docs/handbook/solver-file.md#params) gives: the values under the case of its base that takes the concept case's reading at every `DET_OR_RULE` and `RULE_OR_DET` line.
- A `DET` without `(ONE)` whose value differs across the assignments that solve the train pairs is an undetermined parameter, and the engine reports it as an error. With `(ONE)`, those values are its open values, as [Open values](cases.md#open-values) gives.
- The product of candidates runs under a cap of 1000. The cap is provisional: the largest product of the corpus's determination plans is 100, as [Determination candidates](corpus-survey.md#determination-candidates) gives, but the old tooling's limit was 100 and the solvers whose plans passed it were changed, so the corpus's products show that limit. A domain proposer's candidates are those [Proposers](#proposers) gives. A product past the cap is an alert that names the parameters, as [Bounds](overview.md#requirements) gives.

## Proposers

- A proposer is arclog text in `engine/lib/proposers.arclog`. Name resolution expands it as the body of the `DET` that names it.
- On the derived reading of a `DET_OR_RULE` or `RULE_OR_DET` line, the proposer runs on each input, a pair's or a witness's, alone, with `ex_output` empty. Where it gives no value, each case that takes that reading is undefined on that input, as the `@derive` line of [Params](../../docs/handbook/solver-file.md#params) gives.
- A domain proposer, as [Program](../../docs/arclog/arclog.md#program) gives it, is native: it enumerates the values of its type that the evidence gives, and reads no stored value.
    - An orientation type: every value of the type.
    - Color: the colors of the examples' inputs and of the train outputs.
    - Number: 0 up to the largest extent of an example's grid.
    - Position: the cells of the largest example grid's frame.
    - A pair type: the product of its two domains.
    - Box and Offset have no domain proposer, since no frame bounds them, and a `DET` of one states a body that gives its candidates. 48d8fb45's `win_box`, the one `DET` of `gen/` that names `BoxDomain`, is a fault of its solver.
- Each other proposer whose derivation needs a form that a program bans, such as arithmetic, and that no lib relation gives, is native too, with its columns in the registry.

## `RIGID_DET`

- The engine computes `RIGID_DET` by the method of [Implementation](../../docs/arclog/rigid.md#implementation), with one instance's reading as the frame of each assembly.
- An assembly's instances are those its `instance` clause gives, and a form with none has one instance, as [rigid](../../docs/arclog/rigid.md) gives. The engine infers no instance from a part's columns: a part column the `instance` clause does not name is a column of the part.
- No output observes that choice, as [Invariance](../../docs/handbook/principles.md#invariance) requires: the checker gives each `:Pose` column the type Pose, and refuses every read that would see the frame, as [The `RIGID_DET` frame](equivariance.md#the-rigid_det-frame) gives.

## How each decision can fail

| Decision | Failure | What catches or bounds it |
| --- | --- | --- |
| Determination filtered by the train pairs over a product | many parameters with several candidates | dependency order with shared entries, and a cap that reports the parameters |
| The Pose type | a read that sees no frame and that the rule refuses | `pose_difference` gives every relation between two poses; all 24 clauses of `gen/` that read a pose pass the rule |

## Known gaps

None.
