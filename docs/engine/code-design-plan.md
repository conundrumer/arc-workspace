# Engine code design

The first stage of building the engine: the interfaces and shared parts of [Reader and checker](reader.md), as Rust that compiles, so that the later stages build against fixed signatures and can run in parallel.

## Output

- A Cargo workspace at `engine/`, with the crates of [Crates](overview.md#crates).
- The public types, traits and function signatures that the parts below need, each with a doc comment that states its contract in its own words and quotes no document. Where the item's rule is the language's or a principle's, the doc comment cites a section of `docs/arclog/` or of the handbook that gives it, by its path from the root of the tree and its anchor, such as `docs/arclog/rigid.md#the-pose`, and states no part of that rule. Bodies are `todo!()`.
- No design document is required. Where an interface needs a reason that its doc comment cannot hold, a module comment gives it.

## Parts

- **Terms.** The term id, and its interpretations: number, the constants, Box as four signed bytes, Ident, constructed terms. The intern table and the task session that owns it and the result cache.
- **Relations.** The row, the relation and its parts, as [Factorized bodies](synthesis.md#factorized-bodies) gives, and the index.
- **Syntax.** The node kinds of an arclog and an arcdata file; the trivia, source places and label names kept beside a node; the path an edit names a node by; the node as an immutable value with its canonical hash; the edit.
- **Solver.** The `Solver` tree, and `cases()` returning case programs on demand.
- **Registry.** The format of the tracked lib file under `engine/lib/`, and the type it loads into at compile time.
- **Resolver.** Name resolution of a case program, and the dependency graph it gives.
- **Checker.** A check's input (a node and its scope), its result, the diagnostic type that the lint and the evaluator share, and the check cache's key. The interface admits a prefix form of each check, which [Synthesis](synthesis.md) builds; this stage builds none.
- **Harness.** The test harness that runs a check over every pair of `gen/`, which each later stage's end check uses.

## Rules

- Equivariance holds by construction, as [equivariance.md](equivariance.md) gives: a term type that the comparison typing rule of [Checker](reader.md#checker) keeps from `<` implements no public order, and no lib interface makes a free choice.
- The interfaces implement the docs and reopen none of their decisions. Where a doc leaves an interface open, or a doc line is wrong, report it to the coordinator and edit no engine doc.
- Each crate dependency gives its reason in `Cargo.toml`.
- Each name and doc comment uses a conventional or precise term, qualified where the bare term would be ambiguous, such as `canonical_hash` for the hash of a canonical form. A term the arclog docs or the handbook define, such as site, label or case, keeps its defined sense. No name is invented jargon.

## Done

- `cargo build`, `cargo test` and `cargo doc` pass with no warning.
- Each item of [Reader and checker](reader.md) maps to an interface, and a review checks that map.
- The later stages of step 1 can each own a set of files with no shared edits: representations; reader and writer; registry and resolver; `cases()`; programs as values; checker.
