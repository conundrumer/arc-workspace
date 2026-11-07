//! The arclog engine's binary for the dev loop and the refine passes, with
//! no Python in the path.
//!
//! The first argument names a subcommand, and each subcommand stands in a
//! file of its own, which reads the arguments after its name.

mod arguments;
mod check_diff;
mod compare;
mod concept_case;
mod count_determinism;
mod decode;
mod determine;
mod determinism;
mod empty_gold;
mod lib_compare;
mod renaming;
mod row_counts;
mod row_parity;
mod select;
mod souffle_rows;
mod speed;
mod stream;
mod tables;
mod test_pairs;

use arclog::algebra::tables::OrientationTables;
use std::process::ExitCode;

/// Each subcommand, by the name the first argument gives it.
const SUBCOMMANDS: [(&str, fn(&[String]) -> ExitCode); 14] = [
    ("check-diff", check_diff::run),
    ("compare", compare::run),
    ("count-determinism", count_determinism::run),
    ("decode", decode::run),
    ("determine", determine::run),
    ("empty-gold", empty_gold::run),
    ("lib-compare", lib_compare::run),
    ("determinism", determinism::run),
    ("speed", speed::run),
    ("row-counts", row_counts::run),
    ("row-parity", row_parity::run),
    ("stream", stream::run),
    ("tables", tables::run),
    ("test-pairs", test_pairs::run),
];

fn main() -> ExitCode {
    // Reads and checks the orientation tables: a table that is not
    // D4-invariant stops the engine here, before any subcommand runs.
    OrientationTables::get();
    let args: Vec<String> = std::env::args().skip(1).collect();
    let run = args.first().and_then(|name| SUBCOMMANDS.iter().find(|(n, _)| n == name)).map(|(_, run)| run);
    match run {
        Some(run) => run(&args[1..]),
        None => {
            let names: Vec<&str> = SUBCOMMANDS.iter().map(|(name, _)| *name).collect();
            eprintln!("usage: arclog-cli <{}> [<argument> ...]", names.join("|"));
            ExitCode::from(2)
        }
    }
}
