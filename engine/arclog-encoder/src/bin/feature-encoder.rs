//! The feature encoder's commands.
//!
//!   feature-encoder eval SOLVER 'EXPRESSION' [--corpus DIR] [--tasks DIR] [--task-wide]
//!   feature-encoder rows SOLVER 'RELATION' [--corpus DIR] [--tasks DIR] [--task-wide]
//!
//! `eval` prints the forms and the value of a feature expression on the
//! concept case of a solver, `rows` those of a relation term.

use std::path::PathBuf;

use arclog_encoder::run::{cell_text, concept_program, Evaluated, Host, ModelValue, Value};

struct Arguments {
    positional: Vec<String>,
    corpus: PathBuf,
    tasks: PathBuf,
    task_wide: bool,
}

fn arguments() -> Arguments {
    let mut parsed = Arguments { positional: Vec::new(), corpus: PathBuf::from("work/arclog/gen"), tasks: PathBuf::from("data/tasks"), task_wide: false };
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--corpus" => parsed.corpus = args.next().expect("a directory after --corpus").into(),
            "--tasks" => parsed.tasks = args.next().expect("a directory after --tasks").into(),
            "--task-wide" => parsed.task_wide = true,
            _ => parsed.positional.push(arg),
        }
    }
    parsed
}

fn host(arguments: &Arguments, solver: &str) -> Result<Host, String> {
    let program = concept_program(&arguments.corpus, solver)?;
    Host::new(&program, &arguments.tasks.join(format!("{solver}.json")))
}

fn print_value(value: &Value) {
    for form in &value.expanded.forms {
        println!("{form}");
    }
    println!(";; columns {:?} types {:?} task_wide {}", value.row_names, value.types, value.expanded.task_wide);
    if let Some(stop) = &value.stop {
        println!(";; walk stopped: {stop}");
    }
    for at in &value.at {
        if !at.assignment.is_empty() {
            println!(";; assignment {:?}", at.assignment);
        }
        for (example, models) in &at.examples {
            for model in models {
                let name = example.map_or("task".to_string(), |example| format!("e{}", example.index()));
                match model {
                    ModelValue::Rows(rows) => {
                        let shown: Vec<String> = rows.iter().take(12).map(|row| {
                            let cells: Vec<String> = row.iter().zip(&value.types).map(|(id, ty)| cell_text(*id, ty)).collect();
                            format!("({})", cells.join(" "))
                        }).collect();
                        println!("{name}: {} rows {}", rows.len(), shown.join(" "));
                    }
                    ModelValue::Undefined => println!("{name}: undefined"),
                    ModelValue::Stopped(stop) => println!("{name}: stopped {stop}"),
                }
            }
        }
    }
}

fn print(evaluated: &Evaluated) {
    match evaluated {
        Evaluated::Refused(message) => println!("refused: {message}"),
        Evaluated::Fault(message) => println!("fault: {message}"),
        Evaluated::Value(value) => print_value(value),
    }
}

fn main() {
    // The specification takes sources as on, and the engine's default is off.
    if std::env::var_os("ARCLOG_IDENT_SOURCE").is_none() {
        unsafe { std::env::set_var("ARCLOG_IDENT_SOURCE", "type") };
    }
    let arguments = arguments();
    let command = arguments.positional.first().map(String::as_str).unwrap_or_default();
    let result = match (command, &arguments.positional[1.min(arguments.positional.len())..]) {
        ("eval", [solver, text]) => host(&arguments, solver).map(|host| print(&host.feature(text))),
        ("rows", [solver, text]) => host(&arguments, solver).map(|host| print(&host.relation(text, arguments.task_wide))),
        ("worked", []) => {
            let (passed, failed) = arclog_encoder::worked::run(&arguments.corpus, &arguments.tasks);
            println!("{passed} cases pass, {failed} fail");
            Ok(())
        }
        _ => Err("usage: feature-encoder eval|rows SOLVER 'TERM' [--corpus DIR] [--tasks DIR] [--task-wide]".to_string()),
    };
    if let Err(message) = result {
        eprintln!("{message}");
        std::process::exit(1);
    }
}
