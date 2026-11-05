//! The feature library: the encoder from a state's tables to features that
//! `work/feature-spec/feature-spec.md` defines.
//!
//! - [`expression`]: a feature expression as a term of the grammar.
//! - [`schema`]: the columns of a table of a checked program.
//! - [`expand`]: the expansion of a ground expression into arclog forms.
//! - [`library`]: the reader of the feature library, and the expansion of a
//!   call of one of its macros.
//! - `pool`: the expansion of a `pool`.
//! - [`run`]: the check and the evaluation of those forms, through the
//!   engine's evaluator.
pub mod expand;
pub mod expression;
pub mod library;
pub(crate) mod pool;
pub mod program_relations;
pub mod run;
pub mod schema;
pub mod worked;
