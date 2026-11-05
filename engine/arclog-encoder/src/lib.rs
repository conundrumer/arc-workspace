//! The feature library: the encoder from a state's tables to features that
//! `work/feature-spec/feature-spec.md` defines.
//!
//! - [`expression`]: a feature expression as a term of the grammar.
//! - [`schema`]: the columns of a table of a checked program.
//! - [`expand`]: the expansion of a ground expression into arclog forms.
//! - [`library`]: the reader of the feature library, and the expansion of a
//!   call of one of its macros.
//! - `pool`: the expansion of a `pool`.
//! - [`enumerate`]: the feature expressions at a size.
//! - [`encoder`]: the value of each ground expression at a size, on tables of a
//!   state.
//! - [`vectors`]: the vector entries, their names and their numbers.
//! - [`law`]: the check of the transformation law on stored rows.
//! - [`closed`]: the values of the closed roots on grids alone, which the
//!   evaluation reads.
//! - [`run`]: the check and the evaluation of those forms, through the
//!   engine's evaluator.
pub mod closed;
pub mod encoder;
pub mod enumerate;
pub mod expand;
pub mod expression;
pub mod law;
pub mod library;
pub mod pool;
pub mod program_relations;
pub mod run;
pub mod schema;
pub mod vectors;
pub mod worked;
