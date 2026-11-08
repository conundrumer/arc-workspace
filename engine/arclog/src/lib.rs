//! The core crate of the arclog engine: the interfaces and shared parts of
//! step 1 of the engine's build order, Reader and checker, of step 2,
//! Evaluator and lib, of step 3, Cases and judge, for one case, and of
//! step 5, Synthesis.
//!
//! The crate is unrelated to the Python package `engine` under
//! `src/engine/`.
//!
//! # Files by the stage that writes their bodies
//!
//! Each public item here has its final signature. Each later stage writes
//! the bodies of its own files, and edits no file of another stage.
//!
//! ## Step 1
//!
//! - representations: [`hash`], [`terms`], [`session`], [`relations`]
//! - reader and writer: [`layout`], [`read`], [`write`](mod@write),
//!   [`harness`], and the example `round_trip`
//! - registry and resolver: [`registry`], [`resolver`], the files of
//!   `engine/lib/`, the example `resolve`, and the test `registry_file`;
//!   the derivation of a macro's modes applies [`safety`]
//! - `cases()`: [`solver`], and the example `cases`
//! - programs as values: [`program`] and its submodules
//! - checker: [`types`], [`diagnostic`], [`check`] and its submodules,
//!   [`safety`], which its safety check applies, the
//!   example `lint`, and the tests under `engine/arclog/tests/integration/` that feed a
//!   check a file that breaks it, such as the comparison typing rule's and the pose
//!   rule's
//!
//! A stage adds a submodule only under a module of its own. No stage edits
//! this file or a `Cargo.toml`: the standard library serves each body of
//! step 1, its threads included, and a stage that needs a module at the top
//! of the crate or a crate dependency reports it to the coordinator.
//!
//! ## Step 2
//!
//! Each change of step 2 writes the bodies of its own files, and edits a
//! file of another change only at the lines its ticket's Scope gives. The
//! files of each change:
//!
//! - the driver and the joins: [`eval`] (its `mod.rs`),
//!   [`eval::ir`], [`eval::plan`], [`eval::join`], [`eval::examples`],
//!   [`eval::output`], [`task`], and the subcommand `compare` of
//!   `arclog-cli`
//! - the filters: [`eval::filters`]
//! - the result cache: [`eval::cache`], and the bodies of
//!   [`session`]
//! - the algebra: [`algebra`] and its submodules
//! - the lib comparison: the subcommand `lib-compare` of
//!   `arclog-cli`
//! - instances: [`eval::instance`]
//! - `RIGID_DET`: [`eval::rigid`]
//! - the constructions: one file of `arclog-constructions` each, as that
//!   crate's module comment gives
//! - `Unfold`: [`eval::unfold`]
//! - parallelism and determinism: [`eval::pool`], the values of
//!   [`eval::Caps::CORPUS`], and the subcommands `determinism` and
//!   `speed` of `arclog-cli`
//!
//! No change of step 2 edits this file. A change that needs a crate this
//! step's `Cargo.toml` files do not give adds it to its own crate's
//! `Cargo.toml`, with its reason, and to `engine/Cargo.lock`.
//!
//! ## Step 3
//!
//! Each change of step 3 writes the bodies of its own files, and edits a
//! file of another change only at the lines its ticket's Scope gives. The
//! files of each change:
//!
//! - the judge's comparison: [`judge`], [`judge::candidates`],
//!   [`judge::solves`], and [`task::JudgedTask`] in [`task`]
//! - the constraint module: `constraints`
//! - the lazy product that the constraint module and `Unfold` step
//!   through: `product`
//! - the options of a pick: `eval::picks`
//! - the models of a case: `eval::models`
//! - the judged run: `judge::run`, and the subcommand `compare` of
//!   `arclog-cli`
//!
//! ## Step 5
//!
//! - the token stream: [`stream`] and its submodules
//! - the decoder and its token mask: [`decode`] and its submodules
//!
//! A module whose functions take arguments holds
//! `#![allow(unused_variables, dead_code)]` until its stage writes the bodies, since a
//! `todo!()` body reads none of its arguments.

pub mod algebra;
pub mod check;
pub mod clock;
pub mod study;
pub mod mutation;
pub mod constraints;
pub mod decode;
pub mod diagnostic;
pub mod eval;
pub mod safety;
pub mod harness;
pub mod hash;
pub mod heap;
pub mod judge;
pub mod layout;
mod product;
pub mod program;
pub mod read;
pub mod registry;
pub mod relations;
pub mod resolver;
pub mod session;
pub mod solver;
pub mod stats;
pub mod stream;
pub mod task;
pub mod terms;
pub mod trace;
pub mod types;
pub mod write;

pub mod study_clause;
