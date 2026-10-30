//! The walk of a solver of a corpus that records the tables of its case
//! programs: for each case whose stream the decoder takes, the tables of each
//! step of its replay with the index of the step's token. The replay, the
//! read of the solver and its task, and the session of the run are those of
//! [`arclog::decode::corpus`].

use std::path::Path;

use arclog::decode::corpus::replay_solver;
use arclog::eval::instance::Constructions;
use arclog::stream::DecodeSettings;

use crate::tables::{record_step, Points, Table};

/// The tables of one case of a solver, each with the index in the stream of
/// the token whose step gives it, or the fault that gives none.
#[derive(Debug)]
pub struct CaseTables {
    /// The case as [`case_spelled`](arclog::stream::corpus::case_spelled) writes its name.
    pub case: String,
    /// Whether the case is the solver's concept case.
    pub concept: bool,
    /// The tables in the order of the stream, or why the stream gives none.
    pub tables: Result<Vec<(usize, Table)>, String>,
}

/// The tables of each wanted case of a solver, with the count of train
/// pairs of its task, which names an example.
#[derive(Debug)]
pub struct SolverTables {
    pub train: usize,
    pub cases: Vec<CaseTables>,
}

/// The tables, at `points`, of each case of the solver `id` of `corpus` on
/// its task in `tasks`, the concept case or, with `all`, every case, in the
/// order of the cases, with the lib's constructions `constructions`, under
/// `settings`; or the
/// fault that stops the solver. A case that holds a `DEMONSTRATED` form is
/// left out. The replay computes no token mask.
pub fn solver_tables(corpus: &Path, tasks: &Path, id: &str, all: bool, points: Points, constructions: &Constructions, settings: &DecodeSettings) -> Result<SolverTables, String> {
    let replayed = replay_solver(corpus, tasks, id, all, constructions, settings, false, &|tables: &mut Vec<(usize, Table)>, decoder, stepped| {
        record_step(tables, decoder, stepped.index, points);
    })?;
    let cases = replayed.cases.into_iter().map(|case| CaseTables { case: case.case, concept: case.concept, tables: case.outcome }).collect();
    Ok(SolverTables { train: replayed.train, cases })
}
