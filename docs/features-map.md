# Features map

Where each thing about features over tables is defined. One document defines each thing, and the others link to it. "First version" and "v1" name the same library.

## Terms

* comment: The user's words, session 12a37de8, 2026-11-06: "Always use conventional terms".
* comment: The user's words, session 12a37de8, 2026-11-06: "Always qualify or conventional terms . No more single loose words. Row is confusing".
- Reports and documents on features use conventional terms, and qualify each term that a bare word could misread: table row, feature vector, ARC example, constraint model, learned model. A name from code or from the first version appears only where it names that code. [Terms](sample-build/contract.md#terms) defines them, and [Measures](../work/measures.md) gives each measure's conventional term, with the project's word as its alias.

## Authoritative

- Goal, and what counts as a result: [Goal](../work/goal.md). It is under `work/`, which git ignores.
- The objects of the search and the maps between them: [Structure of the search](feature-spec/structure.md).
- The terms, the levels of a feature's value, the vectors and their keys, `State` and `Sample`: [Type contract](sample-build/contract.md).
- What a feature is, the feature query language, shapes and coverage: [Feature specification](feature-spec/feature-spec.md).
- Column types, frames and lineage: [Arclog column types](feature-spec/arclog-types.md). The engine's code is the source of truth for it.
- How features leave the engine, and what a learned model reads of them: [Feature export](feature-spec/export-design.md).
- How features are measured: [Evaluation protocol](feature-spec/evaluation-protocol.md), and each measure's meaning in [Measures](../work/measures.md).
- The live search is the pool search, `model/study/sampler/superdag_search.py`, which `model/study/search/dev161/dev_run.py` runs. [Search handoff](../work/search-handoff.md) lists its decision steps and the state of the work.
- The writer, its writing points and the blocks of its vector: [Writer spec](../work/lm/data-study/sampler/sampler-worker/proposer-inventory/writer-spec.md).
- The rules by which the feature encoder refuses a term, and their arclog reading: [Feature grammar refusal rules](feature-spec/grammar-rules.md).
- The columns of the writer's training instances, and the search's draws as negative examples: [Training instances](sample-build/training-instances.md).
- The split of tasks: [Split design](sample-build/split.md).
- The arclog language and lib, which features are written in: [arclog](arclog/arclog.md) and [The arclog lib](arclog/lib.md).

## Code

- The encoder and the generated shapes: `engine/arclog-encoder`.
- The budget of cells that stops a term in a walk, and the charge against it: [The budget of a term](feature-spec/feature-spec.md#the-budget-of-a-term). The code is `Walker::walk_of` in `engine/arclog-encoder/src/generate.rs`.
- The named parts: `engine/lib/features.arclog`.
- The scripts that score features: `model/feature_eval`.
- The trainer those scripts run: `engine/block-boost`.
- The first version: `model/contracts/features`, described in [its README](../model/contracts/README.md). It is a baseline, and a feature vector must give what it tells a learned model. It does not define what a feature is.
- The neural encoder beside a language model, a route the project left: [Feature encoder](feature-encoder.md) is the design that `model/encoder.py` implements. Its tables are parameterized tables at one assignment.

## Run outputs

- `work/feature-spec/results` and the task lists beside it. Git ignores them. Results older than the generated features do not measure them.
