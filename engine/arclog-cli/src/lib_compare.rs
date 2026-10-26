//! `lib-compare`: the comparison of the lib with the Souffle lib. It
//! compares each lib relation and component with its Souffle version on
//! small generated inputs, as `docs/engine/verification.md#lib-comparison`
//! gives.
//!
//! Its arguments: the directory of the lib snapshot, then the names of the
//! elements to compare, every element where it is given none. The command
//! writes each element's inputs under `inputs/` of the snapshot's
//! directory, and reads the Souffle rows of each from the record
//! `scripts/souffle_parity.py lib` writes beside them, under the element's
//! name. It starts no Souffle run, and runs from the root of the tree. It
//! reads the record of each element first, and evaluates no element while a
//! record of an element is missing, stale or without the emptied inputs it
//! needs: it lists those elements, with the call that writes their records,
//! and exits with 2. Then it evaluates the elements on the threads of
//! [`corpus_threads`], and prints their lines in the order of the elements.
//!
//! The comparison with the Souffle record covers the rows inside the
//! domain of the Souffle form, and lists the rest as not compared. A
//! difference at a free choice of the Souffle lib that
//! `docs/engine/equivariance.md#free-choices` records is a fault of the
//! Souffle lib, which the command lists apart, and which gives no failure
//! of the command.
//!
//! The modules: [`inputs`], the generation of each element's inputs file;
//! [`records`], the Souffle record of an inputs file; [`sources`], the
//! digest of the Souffle sources a record was made from; [`evaluation`],
//! the engine's rows of an element and their comparison with the record;
//! [`coverage`], what of the engine's rows the comparison with the record
//! covers; [`free_choices`], the free choices of the Souffle lib the
//! comparison gives as its faults; and [`components`], the evaluation of a
//! component over the key groups of its inputs.

mod components;
mod coverage;
pub(crate) mod evaluation;
mod free_choices;
mod inputs;
mod records;
mod sources;

use std::path::{Path, PathBuf};
use std::process::ExitCode;

use arclog::harness::{corpus_threads, require_optimized_build, run_on_workers};

use self::coverage::{covered, left_out_lines, Souffle};
use self::evaluation::{fork_line, walk_differences};
use self::free_choices::{split, SECTION};
use self::inputs::{elements, inputs_path, write_json, Element};
use self::records::{read_record, Record, SouffleInputs};
use self::sources::sources_digest;

const USAGE: &str = "usage: arclog-cli lib-compare <lib-snapshot-dir> [<element> ...]";

/// The call that writes the Souffle records of the inputs files.
const SOUFFLE_CALL: &str = "uv run python scripts/souffle_parity.py lib";

/// The subcommand on `args`, the arguments after its name.
pub fn run(args: &[String]) -> ExitCode {
    if let Err(code) = require_optimized_build() {
        return code;
    }
    let Some((snapshot, names)) = args.split_first() else {
        eprintln!("{USAGE}");
        return ExitCode::from(2);
    };
    let snapshot = PathBuf::from(snapshot);
    if let Some(unknown) = names.iter().find(|name| !elements().iter().any(|e| e.name() == name.as_str())) {
        eprintln!("{unknown} is no lib element");
        return ExitCode::from(2);
    }
    let selected: Vec<Element<'static>> = elements().into_iter().filter(|e| names.is_empty() || names.iter().any(|name| name == e.name())).collect();
    if let Err(error) = std::fs::create_dir_all(snapshot.join("inputs")) {
        eprintln!("{} cannot be made: {error}", snapshot.join("inputs").display());
        return ExitCode::from(2);
    }
    silence_panics();
    let sources = sources_digest();
    let plans: Vec<Plan> = selected.iter().map(|element| prepare(&snapshot, element, &sources)).collect();
    let needing: Vec<&str> = selected.iter().zip(&plans).filter(|(_, plan)| matches!(plan, Plan::Needs(_))).map(|(element, _)| element.name()).collect();
    if !needing.is_empty() {
        for plan in &plans {
            if let Plan::Needs(line) = plan {
                println!("not compared: {line}");
            }
        }
        println!("{SOUFFLE_CALL} {}", needing.join(" "));
        return ExitCode::from(2);
    }
    let ready: Vec<&Ready> = plans.iter().filter_map(|plan| if let Plan::Compare(ready) = plan { Some(ready) } else { None }).collect();
    let mut parts = run_on_workers(&ready, corpus_threads().min(ready.len().max(1)), |ready| ready.compare(&snapshot)).into_iter();
    let mut report = Report::default();
    for plan in plans {
        match plan {
            Plan::Compare(_) => report.append(parts.next().expect("a part for each element compared")),
            Plan::Skip(line) | Plan::Needs(line) => report.not_compared.push(line),
        }
    }
    report.print()
}

/// What the records phase gives for an element.
enum Plan<'e> {
    /// The element has a record whose rows the engine's are compared with.
    Compare(Ready<'e>),
    /// The element is not compared, with the line that says why, and the
    /// engine does not run on it.
    Skip(String),
    /// The element's record is missing, stale or lacks the emptied inputs
    /// it needs, with the line that says so: `SOUFFLE_CALL` writes it.
    Needs(String),
}

/// An element with a record to compare with.
struct Ready<'e> {
    element: &'e Element<'e>,
    /// The inputs the record was made from.
    inputs: SouffleInputs,
    record: Souffle,
}

/// Writes the inputs files of `element` and reads its record, made from the
/// sources of the digest `sources`.
fn prepare<'e>(snapshot: &Path, element: &'e Element<'e>, sources: &Result<String, String>) -> Plan<'e> {
    let name = element.name();
    let given = element.inputs();
    if let Err(message) = write_json(&inputs_path(snapshot, name, ""), &given) {
        return Plan::Skip(format!("{name}: {message}"));
    }
    let (record, inputs) = read_record(snapshot, element, &given, sources);
    if let SouffleInputs::Emptied(emptied) = &inputs {
        if let Err(message) = write_json(&inputs_path(snapshot, name, ".souffle"), emptied) {
            return Plan::Skip(format!("{name}: {message}"));
        }
    }
    match record {
        Record::Rows(record) => Plan::Compare(Ready { element, inputs, record }),
        Record::NoSouffleForm => Plan::Skip(format!("{name}: against Souffle: the Souffle lib has no form of it")),
        Record::Failed(failure) => Plan::Skip(format!("{name}: against Souffle: the Souffle run fails: {failure}")),
        Record::Unreadable => Plan::Skip(format!("{name}: against Souffle: its record of these inputs and sources holds rows that do not read")),
        Record::NoSources(fault) => Plan::Skip(format!("{name}: against Souffle: {fault}")),
        Record::Missing => Plan::Needs(format!("{name}: against Souffle: no record of these inputs; `{SOUFFLE_CALL}` writes it")),
        Record::Stale => {
            Plan::Needs(format!("{name}: against Souffle: its record was made from other Souffle sources than the present ones; `{SOUFFLE_CALL}` writes it again"))
        }
        Record::Undeclared(ports) => Plan::Needs(format!(
            "{name}: against Souffle: its Souffle form declares no input {}, and no record of the inputs with those left empty; `{SOUFFLE_CALL}` writes it",
            ports.join(", ")
        )),
    }
}

/// What the command found, by the part of the comparison that found it.
#[derive(Default)]
struct Report {
    /// Each element compared and found the same, by name.
    compared: Vec<String>,
    /// Each line on an element whose rows differ.
    differ: Vec<String>,
    /// Each line on an element not compared, with its reason.
    not_compared: Vec<String>,
    /// Each line on a difference from the Souffle record at a free choice
    /// of the Souffle lib that [`SECTION`] records as its fault.
    souffle_faults: Vec<String>,
    /// Each line on inputs whose walks give more than one set of outputs,
    /// with the outputs of each walk.
    forks: Vec<String>,
}

impl Ready<'_> {
    /// What the comparison of the element with its record gives. The
    /// engine runs on the inputs the record was made from.
    fn compare(&self, snapshot: &Path) -> Report {
        let mut report = Report::default();
        let name = self.element.name();
        let path = inputs_path(snapshot, name, "");
        let souffle_path = inputs_path(snapshot, name, ".souffle");
        let subject = match self.element.subject() {
            Ok(subject) => subject,
            Err(message) => {
                report.not_compared.push(format!("{name}: {message}"));
                return report;
            }
        };
        let engine = match self.inputs.engine_walks(&subject) {
            Ok(engine) => engine,
            Err(message) => {
                report.not_compared.push(match self.inputs {
                    SouffleInputs::Given(_) => format!("{name}: the engine's run stops: {message}"),
                    SouffleInputs::Emptied(_) => format!("{name}: against Souffle: the engine's run on the inputs of the Souffle form stops: {message}"),
                });
                return report;
            }
        };
        let emptied = matches!(self.inputs, SouffleInputs::Emptied(_));
        if engine.len() > 1 {
            report.forks.push(fork_line(&subject, if emptied { &souffle_path } else { &path }, &engine));
        }
        let mut covered_walks = Vec::new();
        for walk in &engine {
            let (compared, outside) = covered(&subject, self.inputs.inputs(), walk, &self.record);
            covered_walks.push(compared);
            if let Some(line) = outside.filter(|line| !report.not_compared.contains(line)) {
                report.not_compared.push(line);
            }
        }
        report.not_compared.extend(left_out_lines(&subject, &self.record));
        let (plain, chosen) = split(&subject, &covered_walks);
        let mut lines = walk_differences(&subject, "Souffle", &plain);
        if emptied && !lines.is_empty() {
            lines.push(format!("{name}: its inputs against Souffle are {}", souffle_path.display()));
        }
        report.souffle_faults.extend(
            walk_differences(&subject, "Souffle", &chosen).into_iter().map(|line| format!("{line}; the free choice of its Souffle form that {SECTION} records")),
        );
        if lines.is_empty() {
            report.compared.push(name.to_string());
        } else {
            report.differ.extend(lines);
            report.differ.push(format!("{name}: its inputs are {}", path.display()));
        }
        report
    }
}

impl Report {
    /// Adds the lines of `part` after the lines of this report.
    fn append(&mut self, part: Report) {
        self.compared.extend(part.compared);
        self.differ.extend(part.differ);
        self.not_compared.extend(part.not_compared);
        self.souffle_faults.extend(part.souffle_faults);
        self.forks.extend(part.forks);
    }

    /// Prints the report, and gives success where nothing differs.
    fn print(&self) -> ExitCode {
        for line in &self.differ {
            println!("{line}");
        }
        for line in &self.forks {
            println!("fork: {line}");
        }
        for line in &self.souffle_faults {
            println!("a fault of the Souffle lib: {line}");
        }
        for line in &self.not_compared {
            println!("not compared: {line}");
        }
        println!("compared: {}", self.compared.join(", "));
        println!(
            "{} elements compared the same, {} lines on elements that differ, {} inputs that fork, {} lines on faults of the Souffle lib, {} lines on what is not compared",
            self.compared.len(),
            self.differ.len(),
            self.forks.len(),
            self.souffle_faults.len(),
            self.not_compared.len()
        );
        if self.differ.is_empty() { ExitCode::SUCCESS } else { ExitCode::FAILURE }
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
