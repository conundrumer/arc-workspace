//! `empty-gold <corpus-dir> <tasks-dir> <task_id> ...`: prints, for each
//! task, one line of the JSON that `arclog::study::empty_gold::empty_gold`
//! gives, under the default request work cap, as the gold publisher's native call does.

use std::path::Path;
use std::process::ExitCode;

pub(crate) fn run(args: &[String]) -> ExitCode {
    let [corpus, tasks, ids @ ..] = args else {
        eprintln!("usage: arclog-cli empty-gold <corpus-dir> <tasks-dir> <task_id> ...");
        return ExitCode::from(2);
    };
    let constructions = match arclog_constructions::shared() {
        Ok(constructions) => constructions,
        Err(fault) => {
            eprintln!("{fault}");
            return ExitCode::FAILURE;
        }
    };
    let mut status = ExitCode::SUCCESS;
    for id in ids {
        match arclog::study::empty_gold::empty_gold(Path::new(corpus), Path::new(tasks), id, None, constructions) {
            Ok(value) => println!("{value}"),
            Err(fault) => {
                eprintln!("{id}: {fault}");
                status = ExitCode::FAILURE;
            }
        }
    }
    status
}
