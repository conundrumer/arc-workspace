//! The feature library: the encoder from a state's tables to features that
//! `work/feature-spec/feature-spec.md` defines.
//!
//! - [`expression`]: a feature expression as a term of the grammar.
//! - [`schema`]: the columns of a table of a checked program.
//! - [`expand`]: the expansion of a ground expression into arclog forms.
//! - [`library`]: the reader of the feature library, and the expansion of a
//!   call of one of its macros.
//! - [`enumerate`]: the feature expressions at a size.
//! - [`encoder`]: the value of each ground expression at a size, on tables of a
//!   state.
//! - [`vectors`]: the vector entries, their names and their numbers.
//! - [`law`]: the check of the transformation law on stored rows.
//! - [`closed`]: the values of the closed roots on grids alone, which the
//!   evaluation reads.
//! - [`run`]: the check and the evaluation of those forms, through the
//!   engine's evaluator.
//! - [`native`]: the operators over materialized rows, a faster evaluation of
//!   what those forms compute.
//! - [`optable`]: the operators on each schema, each checked once.
//! - [`walk`]: the bottom-up walk over classes of relations on one task.
//! - [`tablewalk`]: a table's closed roots, keyed by shape.
//! - [`family`]: the relational shapes that read a table and `output`, in one pass
//!   per table.
pub mod catalog;
mod catalog_boxes;
mod catalog_cells;
pub mod catalog_facts;
mod catalog_orient;
mod catalog_pairs;
pub mod catalog_run;
pub mod catalog_vector;
pub mod closed;
pub mod encoder;
pub mod enumerate;
pub mod expand;
pub mod expression;
pub mod gen_constants;
pub mod gen_lists;
pub mod gen_parts;
pub mod generate;
pub mod family;
pub mod law;
pub mod library;
pub mod native;
pub mod optable;
pub mod program_relations;
pub mod run;
pub mod schema;
pub mod tablewalk;
pub mod vectors;
pub mod walk;
pub mod worked;
pub mod zio;
