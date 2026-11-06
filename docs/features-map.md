# Features map

Where each thing about features over tables is defined. Where two documents differ, the one higher in "Authoritative" holds, unless a line says otherwise. "First version" and "v1" name the same library.

## Authoritative

- Goal, and what counts as a result: [Goal](../work/goal.md). It is under `work/`, which git ignores.
- The objects of the search and the maps between them: [Structure of the search](feature-spec/structure.md).
- The vectors and their keys, `TableVector`, `AssignmentVector`, `QueryVector`, `State` and `Sample`: [Type contract](sample-build/contract.md).
    - A `TableVector` reads one table at one assignment and the base tables.
    - A comparison with a table the query uses is a `QueryVector` entry.
    - `:min`, `:mean` and `:max` in the contract pool over assignments.
- What a feature is, the feature query language, shapes and coverage: [Feature specification](feature-spec/feature-spec.md). It changes the contract only where its section "What in the sample contract changes" says so.
- Column types, frames and lineage: [Arclog column types](feature-spec/arclog-types.md). The engine's code is the source of truth for it.
- How features leave the engine, and what a model reads of them: [Feature export](feature-spec/export-design.md).
- How features are measured: [Evaluation protocol](feature-spec/evaluation-protocol.md), and each measure's meaning in [Measures](../work/measures.md).
- The arclog language and lib, which features are written in: [arclog](arclog/arclog.md) and [The arclog lib](arclog/lib.md).

## Code

- The encoder and the generated shapes: `engine/arclog-encoder`.
- The named parts: `engine/lib/features.arclog`.
- The scripts that score features: `model/feature_eval`.
- The first version: `model/contracts/features`, described in [its README](../model/contracts/README.md). It is a reference line. It does not define what a feature is.

## Run outputs

- `work/feature-spec/results` and the task lists beside it. Git ignores them. Results older than the generated features do not measure them.

## Records

These state what was planned or measured at the time. They do not define current work.

- [Build directive](feature-spec/directive.md): the order the encoder was first built in.
- [Feature encoder](feature-encoder.md), [Large tables](encoder-large-tables.md) and [Table information](table-information.md): a neural encoder, a route the project left.
- [Sample build spec](sample-build/spec.md), [schema](sample-build/schema.md), [inventory](sample-build/inventory.md) and [training rows](sample-build/training-rows.md).
- [State search spec](state-search/state-search-spec.md), [state features](state-search/state-features.md) and [kit decisions](state-search/kit-decisions.md).
- [Redesign proposal](proposals/redesign-proposal.md).
- [Informative tables experiment](../model/contracts/experiment-informative-tables.md).
