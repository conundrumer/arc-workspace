//! The feature library: the encoder from a state's tables to features that
//! `docs/feature-spec/feature-spec.md` defines.
//!
//! - [`expression`]: a feature expression as a term of the grammar.
//! - [`schema`]: the columns of a table of a checked program.
//! - [`expand`]: the expansion of a ground expression into arclog forms.
//! - [`library`]: the reader of the feature library, and the expansion of a
//!   call of one of its macros.
//! - [`enumerate`]: the feature expressions at a size.
//! - [`encoder`]: the value of each ground expression at a size, on tables of a
//!   state.
//! - [`generate`], [`gen_parts`], [`gen_constants`]: the shapes over a table up to a size, by parts,
//!   in one pass per table.
//! - [`table_vector`]: a table's `TableVector`, and the base tables'.
//! - [`query_vector`]: a query's `QueryVector`.
//! - [`candidate_lists`]: the stable roots that Candidate recognition reads.
//! - [`table_stream`]: a task's tables, read from a tables command's framed stream of typed column
//!   arrays or from a tables file's JSON.
//! - [`vectors`]: the vector entries that name no column.
//! - [`law`]: the check of the transformation law on stored rows.
//! - [`closed`]: the values of the closed roots on grids alone, which the
//!   evaluation reads.
//! - [`run`]: the check and the evaluation of those forms, through the
//!   engine's evaluator.
//! - [`native`]: the operators over materialized rows, a faster evaluation of
//!   what those forms compute.
//! - [`boxes`]: the rows of `inside`, as the boxes they come from, written out where an
//!   operator needs the rows themselves.
//! - [`joined`]: the rows of a `join`, as the tables they come from and the equalities between
//!   their columns, written out where an operator needs the rows themselves.
pub mod atom_lists;
pub mod body_features;
pub mod bounds;
pub mod boxes;
pub mod candidate_lists;
pub mod catalog;
mod catalog_boxes;
mod catalog_cells;
pub mod catalog_facts;
pub mod catalog_lists;
mod catalog_orient;
mod catalog_pairs;
pub mod catalog_run;
pub mod catalog_vector;
pub mod cell_sets;
pub mod closed;
pub mod encoder;
pub mod enumerate;
pub mod expand;
pub mod expression;
pub mod gen_constants;
pub mod gen_parts;
pub mod generate;
pub mod grid_walks;
pub mod joined;
pub mod law;
pub mod library;
pub mod native;
pub mod occurrence;
pub mod program_relations;
pub mod query_vector;
pub mod refine;
pub mod refine_parts;
pub mod run;
pub mod schema;
pub mod shapes_refresh;
pub mod state_features;
pub mod stored;
pub mod table_stream;
pub mod table_vector;
pub mod vectors;
pub mod worked;
pub mod zio;
