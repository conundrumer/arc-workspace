//! `lib-compare`: the comparison of the lib with the Souffle lib. It
//! compares each solver with its expanded form, so each lib name that has a
//! definition with that definition inside every solver that uses it, and
//! each lib relation and component with its Souffle version on small
//! generated inputs, each in its eight D4 images and under one color
//! permutation, as `docs/engine/verification.md#lib-comparison` gives.
//!
//! Its arguments: the directory of the lib snapshot, the corpus directory,
//! the directory of the expanded corpus, and the directory of the task
//! files. The command writes each element's inputs under `inputs/` of the
//! snapshot's directory, and reads the Souffle rows of each from the
//! record `scripts/souffle_parity.py lib` writes beside them, under the
//! element's name. It starts no Souffle run, and runs from the root of the
//! tree.
//!
//! The modules: [`inputs`], the generation of each element's inputs file;
//! [`records`], the Souffle record of an inputs file; [`sources`], the
//! digest of the Souffle sources a record was made from; [`evaluation`],
//! the engine's rows of an element and their comparison with the record
//! and with their images; [`components`], the evaluation of a component
//! over the key groups of its inputs; and [`solvers`], the comparison of
//! each solver with its expanded form.

mod components;
mod evaluation;
mod inputs;
mod records;
mod solvers;
mod sources;

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use self::evaluation::{differences, image_differences};
use self::inputs::{elements, emptied_inputs, inputs_path, write_json, Element};
use self::records::{read_record, Record};
use self::solvers::compare_solvers;
use self::sources::sources_digest;

const USAGE: &str = "usage: arclog-cli lib-compare <lib-snapshot-dir> <corpus-dir> <expanded-corpus-dir> <tasks-dir>";

/// The call that writes the Souffle records of the inputs files.
const SOUFFLE_CALL: &str = "uv run python scripts/souffle_parity.py lib";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    let [snapshot, corpus, expanded, tasks] = args else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let snapshot = PathBuf::from(snapshot);
    if let Err(error) = std::fs::create_dir_all(snapshot.join("inputs")) {
        eprintln!("{} cannot be made: {error}", snapshot.join("inputs").display());
        return ExitCode::from(2);
    }
    silence_panics();
    let mut report = Report::default();
    let sources = sources_digest();
    for element in elements() {
        report.element(&snapshot, &element, &sources);
    }
    let solvers = compare_solvers(Path::new(corpus), Path::new(expanded), Path::new(tasks));
    match solvers {
        Ok((differ, not_compared)) => {
            report.solvers = differ;
            report.not_compared.extend(not_compared);
        }
        Err(message) => {
            eprintln!("{message}");
            return ExitCode::from(2);
        }
    }
    report.print()
}

/// What the command found, by the part of the comparison that found it.
#[derive(Default)]
struct Report {
    /// Each element compared and found the same, by name.
    compared: Vec<String>,
    /// Each line on an element whose rows differ.
    differ: Vec<String>,
    /// Each line on an element or a solver not compared, with its reason.
    not_compared: Vec<String>,
    /// Each line on a solver whose two forms differ.
    solvers: Vec<String>,
}

impl Report {
    /// Writes the inputs of `element` and adds what its comparisons give,
    /// against a record made from the sources of the digest `sources`.
    fn element(&mut self, snapshot: &Path, element: &Element<'_>, sources: &Result<String, String>) {
        let name = element.name();
        let inputs = element.inputs();
        let path = inputs_path(snapshot, name, "");
        if let Err(message) = write_json(&path, &inputs) {
            self.not_compared.push(format!("{name}: {message}"));
            return;
        }
        let record = read_record(snapshot, name, &inputs, sources);
        let emptied = match &record {
            Record::Undeclared(ports) => ports.clone(),
            _ => Vec::new(),
        };
        let souffle_inputs = (!emptied.is_empty()).then(|| emptied_inputs(&inputs, &emptied));
        if let Some(souffle_inputs) = &souffle_inputs {
            if let Err(message) = write_json(&inputs_path(snapshot, name, ".souffle"), souffle_inputs) {
                self.not_compared.push(format!("{name}: {message}"));
                return;
            }
        }
        let subject = match element.subject() {
            Ok(subject) => subject,
            Err(message) => {
                self.not_compared.push(format!("{name}: {message}"));
                return;
            }
        };
        let rows = match subject.evaluated(&inputs) {
            Ok(rows) => rows,
            Err(message) => {
                self.not_compared.push(format!("{name}: the engine's run stops: {message}"));
                return;
            }
        };
        let mut lines = Vec::new();
        let against_souffle = match record {
            Record::Rows(souffle) => match souffle_inputs.as_ref().map_or(Ok(rows.clone()), |emptied| subject.evaluated(emptied)) {
                Ok(engine) => {
                    lines.extend(differences(&subject, "Souffle", &engine, &souffle));
                    true
                }
                Err(message) => {
                    self.not_compared.push(format!("{name}: against Souffle: the engine's run on the inputs of the Souffle form stops: {message}"));
                    false
                }
            },
            Record::NoSouffleForm => {
                self.not_compared.push(format!("{name}: against Souffle: the Souffle lib has no form of it"));
                false
            }
            Record::Failed(failure) => {
                self.not_compared.push(format!("{name}: against Souffle: the Souffle run fails: {failure}"));
                false
            }
            Record::Missing => {
                self.not_compared.push(format!("{name}: against Souffle: no record of these inputs; `{SOUFFLE_CALL}` writes it"));
                false
            }
            Record::Stale => {
                self.not_compared.push(format!(
                    "{name}: against Souffle: its record was made from other Souffle sources than the present ones; `{SOUFFLE_CALL}` writes it again"
                ));
                false
            }
            Record::NoSources(fault) => {
                self.not_compared.push(format!("{name}: against Souffle: {fault}"));
                false
            }
            Record::Undeclared(ports) => {
                self.not_compared.push(format!(
                    "{name}: against Souffle: its Souffle form declares no input {}, and no record of the inputs with those left empty; `{SOUFFLE_CALL}` writes it",
                    ports.join(", ")
                ));
                false
            }
        };
        lines.extend(image_differences(&subject, &inputs, &rows));
        if !lines.is_empty() {
            self.differ.extend(lines);
            self.differ.push(format!("{name}: its inputs are {}", path.display()));
        } else if against_souffle {
            self.compared.push(name.to_string());
        } else {
            self.compared.push(format!("{name} (its images alone)"));
        }
    }

    /// Prints the report, and gives success where nothing differs.
    fn print(&self) -> ExitCode {
        for line in self.differ.iter().chain(&self.solvers) {
            println!("{line}");
        }
        for line in &self.not_compared {
            println!("not compared: {line}");
        }
        println!("compared: {}", self.compared.join(", "));
        println!(
            "{} elements compared the same, {} lines on elements that differ, {} solvers whose two forms differ, {} elements and solvers not compared",
            self.compared.len(),
            self.differ.len(),
            self.solvers.len(),
            self.not_compared.len()
        );
        if self.differ.is_empty() && self.solvers.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
    }
}

std::thread_local! {
    /// The place of the last panic on this thread.
    static PANIC: std::cell::RefCell<String> = const { std::cell::RefCell::new(String::new()) };
}

/// Keeps a panic's place for [`last_panic`] in place of printing it, since
/// each form the engine does not yet evaluate panics.
fn silence_panics() {
    std::panic::set_hook(Box::new(|info| {
        let place = info.location().map_or("an unknown place".to_owned(), |l| format!("{}:{}", l.file(), l.line()));
        PANIC.with(|p| *p.borrow_mut() = place);
    }));
}

fn last_panic() -> String {
    PANIC.with(|p| p.borrow().clone())
}
