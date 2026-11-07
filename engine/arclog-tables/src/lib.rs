//! The tables of a decode's steps and their flat columns: the code that only
//! the tables export and its tools run.
//!
//! - [`tables`]: the tables of a decoder's last step, and the evidence tables
//!   of a task.
//! - [`flows`]: the sources of each column of a table, over the dependency
//!   graph of a checked program.
//! - [`identity`]: the identity of each table, column and flow atom of a
//!   case, free of the names and the order that the program's author chose.
//! - [`structure`]: the bodies that the evaluator joins for each table and the
//!   symmetries of the tables and bodies, under those identities.
//! - [`extents`]: the extent of the made frame of each `Box` value of a table,
//!   from a second evaluation of the bodies that give its rows.
//! - [`columns`]: the tables of one case program as flat columns, the layout
//!   that the Python package and its export read.
//! - [`summary`]: the TableHash, the example keys and the TableVector of a
//!   table at each of its assignments, which the export by assignment of
//!   [`columns`] writes. The features are those of `arclog-features`.
//! - [`corpus`]: the walk of a solver of a corpus that records the tables of
//!   its cases.
//!
//! The crate reads a decoder and a checked program through the read-only
//! accessors of `arclog`, the core crate, and the core crate calls nothing
//! here: no crate that the streams export is built from depends on this one,
//! so the compiler refuses a call from the streams path into this code. The
//! reuse key of the streams export rests on that, as `model/export.py` gives it.

pub mod columns;
pub mod corpus;
pub mod extents;
pub mod flows;
pub mod identity;
pub mod shape_rows;
pub mod split;
pub mod structure;
pub mod summary;
pub mod tables;
pub mod study_filters;
pub mod study_features;
