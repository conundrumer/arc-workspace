//! The core crate of the arclog engine: the interfaces and shared parts of
//! step 1 of the engine's build order, Reader and checker
//! (`work/engine/reader.md`).
//!
//! The crate is the arclog engine of `work/engine/overview.md`, unrelated to
//! the Python package `engine` under `src/engine/`.
//!
//! # Modules by the stage that writes their bodies
//!
//! Each public item here has its final signature, and each body is
//! `todo!()`. Each later stage of step 1 writes the bodies of its own modules,
//! and edits no module of another stage:
//!
//! - representations: [`hash`], [`terms`], [`session`], [`relations`]
//! - reader and writer: [`layout`], [`read`], [`write`](mod@write), [`harness`]
//! - registry and resolver: [`registry`], [`resolver`]
//! - `cases()`: [`solver`]
//! - programs as values: [`program`]
//! - checker: [`types`], [`diagnostic`], [`check`]
//!
//! A module whose functions take arguments holds
//! `#![allow(unused_variables, dead_code)]` until its stage writes the bodies, since a
//! `todo!()` body reads none of its arguments.

pub mod check;
pub mod diagnostic;
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
