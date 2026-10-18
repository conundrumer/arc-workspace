//! The core crate of the arclog engine: the interfaces and shared parts of
//! step 1 of the engine's build order, Reader and checker.
//!
//! The crate is unrelated to the Python package `engine` under
//! `src/engine/`.
//!
//! # Files by the stage that writes their bodies
//!
//! Each public item here has its final signature, and each body is
//! `todo!()`. Each later stage of step 1 writes the bodies of its own files,
//! and edits no file of another stage:
//!
//! - representations: [`hash`], [`terms`], [`session`], [`relations`]
//! - reader and writer: [`layout`], [`read`], [`write`](mod@write),
//!   [`harness`], and the example `round_trip`
//! - registry and resolver: [`registry`], [`resolver`], the files of
//!   `engine/lib/`, the example `resolve`, and the test `registry_file`
//! - `cases()`: [`solver`], and the example `cases`
//! - programs as values: [`program`] and its submodules
//! - checker: [`types`], [`diagnostic`], [`check`] and its submodules, the
//!   example `lint`, and the tests under `engine/arclog/tests/` that feed a
//!   check a file that breaks it, such as the order rule's and the pose
//!   rule's
//!
//! A stage adds a submodule only under a module of its own. No stage edits
//! this file or a `Cargo.toml`: the standard library serves each body of
//! step 1, its threads included, and a stage that needs a module at the top
//! of the crate or a crate dependency reports it to the coordinator.
//!
//! A module whose functions take arguments holds
//! `#![allow(unused_variables, dead_code)]` until its stage writes the bodies, since a
//! `todo!()` body reads none of its arguments.

pub mod check;
pub mod diagnostic;
pub mod grounding;
pub mod harness;
pub mod hash;
pub mod layout;
pub mod program;
pub mod read;
pub mod registry;
pub mod relations;
pub mod resolver;
pub mod session;
pub mod solver;
pub mod terms;
pub mod types;
pub mod write;
