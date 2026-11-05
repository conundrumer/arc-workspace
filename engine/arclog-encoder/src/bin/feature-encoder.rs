//! The feature encoder's commands.
//!
//!   feature-encoder eval SOLVER 'EXPRESSION' [--corpus DIR] [--tasks DIR] [--task-wide]
//!   feature-encoder rows SOLVER 'RELATION' [--corpus DIR] [--tasks DIR] [--task-wide]
//!   feature-encoder worked [--corpus DIR] [--tasks DIR]
//!   feature-encoder encode SOLVER TABLE... [--size D] [--out FILE] [--work-cap N] [--limit N] [--max-inputs N] [--program-relations]
//!   feature-encoder names [--size D] [--limit N] [--max-inputs N] [--program-relations] [--out FILE]
//!   feature-encoder vector SOLVER TABLE [--size D] [--names FILE] [--limit N] [--max-inputs N] [--program-relations] [--out FILE]
//!   feature-encoder grid-values GRIDS_JSON (--scene | --rule) [--size D] [--max-inputs N] [--work-cap N] --out FILE
//!   feature-encoder count SOLVER TABLE... [--size D] [--max-inputs N] [--program-relations]
//!   feature-encoder law TASKS_FILE [--size D] [--rate R] [--max-inputs N] [--tables K] [--thin R] [--seconds S] [--tasks-count N] [--shard I/N] [--control] [--program-compare] [--out FILE]
//!
//! `eval` prints the forms and the value of a feature expression on the
//! concept case of a solver, and `rows` those of a relation term. `worked`
//! checks the worked expansions of the specification. `encode` writes one JSON
//! line for each ground expression up to a size, small sizes first; on a restart
//! with the same `--out` it skips the expressions the file holds. `names` writes
//! the vector entries at a size, and `vector` their numbers on a table. `count`
//! prints the terms at each size, by operator, with no evaluation. `grid-values`
//! writes the value of each closed root at each grid of a file: a list of grids
//! for Scene recognition, of pairs of grids for Rule recognition. A line holds the
//! root, its size and its values; on a restart it skips the roots the file holds. `law` compares
//! a sample of features on a sample of tables with their images under the group,
//! writing a line per table and element, and on a restart skips those the file
//! holds. With `--program-compare` it compares each table's stored rows with the
//! table as its program computes it.

use std::collections::HashSet;
use std::io::{BufRead, Write};
use std::ops::ControlFlow;
use std::path::PathBuf;
use std::time::Instant;

use arclog_encoder::encoder::{encode, json_string, value_json, Counts, Law, Options, Outcome};
use arclog_encoder::run::{cell_text, concept_program, Evaluated, Host, ModelValue, Value};
use arclog_encoder::vectors::{entries, vectors, TABLE_HOLE};

struct Arguments {
    positional: Vec<String>,
    corpus: PathBuf,
    tasks: PathBuf,
    task_wide: bool,
    size: usize,
    out: Option<PathBuf>,
    work_cap: u64,
    limit: Option<u64>,
    max_inputs: Option<usize>,
    program_relations: bool,
    rate: u32,
    tables_per_task: usize,
    tasks_count: usize,
    shard: (usize, usize),
    control: bool,
    names: Option<PathBuf>,
    thin: u32,
    seconds: f64,
    program_compare: bool,
    rule: bool,
}

fn arguments() -> Arguments {
    let mut parsed = Arguments { positional: Vec::new(), corpus: PathBuf::from("work/arclog/gen"), tasks: PathBuf::from("data/tasks"), task_wide: false, size: 0, out: None, work_cap: 1 << 20, limit: None, max_inputs: None, program_relations: false, rate: 20_000, tables_per_task: 3, tasks_count: 60, shard: (0, 1), control: false, names: None, thin: 1_000_000, seconds: 30.0, program_compare: false, rule: false };
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--corpus" => parsed.corpus = args.next().expect("a directory after --corpus").into(),
            "--tasks" => parsed.tasks = args.next().expect("a directory after --tasks").into(),
            "--task-wide" => parsed.task_wide = true,
            "--size" => parsed.size = args.next().and_then(|text| text.parse().ok()).expect("a number after --size"),
            "--out" => parsed.out = Some(args.next().expect("a file after --out").into()),
            "--work-cap" => parsed.work_cap = args.next().and_then(|text| text.parse().ok()).expect("a number after --work-cap"),
            "--limit" => parsed.limit = Some(args.next().and_then(|text| text.parse().ok()).expect("a number after --limit")),
            "--max-inputs" => parsed.max_inputs = Some(args.next().and_then(|text| text.parse().ok()).expect("a number after --max-inputs")),
            "--program-relations" => parsed.program_relations = true,
            "--rate" => parsed.rate = args.next().and_then(|text| text.parse().ok()).expect("a count per million after --rate"),
            "--control" => parsed.control = true,
            "--program-compare" => parsed.program_compare = true,
            "--rule" => parsed.rule = true,
            "--scene" => parsed.rule = false,
            "--thin" => parsed.thin = args.next().and_then(|text| text.parse().ok()).expect("a count per million after --thin"),
            "--seconds" => parsed.seconds = args.next().and_then(|text| text.parse().ok()).expect("a number after --seconds"),
            "--names" => parsed.names = Some(args.next().expect("a file after --names").into()),
            "--tables" => parsed.tables_per_task = args.next().and_then(|text| text.parse().ok()).expect("a number after --tables"),
            "--tasks-count" => parsed.tasks_count = args.next().and_then(|text| text.parse().ok()).expect("a number after --tasks-count"),
            "--shard" => {
                let text = args.next().expect("I/N after --shard");
                let (at, of) = text.split_once('/').expect("I/N after --shard");
                parsed.shard = (at.parse().expect("a number"), of.parse().expect("a number"));
            }
            _ => parsed.positional.push(arg),
        }
    }
    parsed
}

fn host(arguments: &Arguments, solver: &str) -> Result<Host, String> {
    let program = concept_program(&arguments.corpus, solver)?;
    Host::new(&program, &arguments.tasks.join(format!("{solver}.json")))
}

/// The expressions that a file of an earlier run holds.
fn finished(path: &PathBuf) -> HashSet<String> {
    let Ok(file) = std::fs::File::open(path) else { return HashSet::new() };
    let mut held = HashSet::new();
    for line in std::io::BufReader::new(file).lines().map_while(Result::ok) {
        if let Some(rest) = line.strip_prefix("{\"expression\":") {
            if let Some(end) = rest.find(",\"size\":") {
                held.insert(rest[..end].to_string());
            }
        }
    }
    held
}

fn run_encode(arguments: &Arguments, solver: &str, tables: &[String]) -> Result<(), String> {
    let host = host(arguments, solver)?;
    let options = Options { size: arguments.size, tables: tables.to_vec(), program_relations: arguments.program_relations, work_cap: arguments.work_cap, max_inputs: arguments.max_inputs };
    let skip = arguments.out.as_ref().map(finished).unwrap_or_default();
    let mut out: Box<dyn Write> = match &arguments.out {
        Some(path) => Box::new(std::io::BufWriter::new(std::fs::OpenOptions::new().create(true).append(true).open(path).map_err(|error| error.to_string())?)),
        None => Box::new(std::io::BufWriter::new(std::io::stdout())),
    };
    let start = Instant::now();
    let mut counts = Counts::default();
    let mut last = Instant::now();
    encode(&host, &options, &mut |record| {
        counts.visited += 1;
        let key = json_string(&record.expression);
        if !skip.contains(&key) {
            let head = format!("{{\"expression\":{key},\"size\":{},\"task_wide\":{}", record.size, record.task_wide);
            let line = match &record.outcome {
                Outcome::Refused => {
                    counts.refused += 1;
                    None
                }
                Outcome::Alias(name) => {
                    counts.aliases += 1;
                    Some(format!("{head},\"alias_of\":{}}}", json_string(name)))
                }
                Outcome::Fault(message) => {
                    counts.faults += 1;
                    Some(format!("{head},\"fault\":{}}}", json_string(message)))
                }
                Outcome::Value(value, law) => {
                    counts.values += 1;
                    let law = if *law == Law::Invariant { "invariant" } else { "equivariant" };
                    Some(format!("{head},\"law\":\"{law}\",\"columns\":{},\"at\":{}}}", json_list(&value.row_names), value_json(value)))
                }
            };
            if let Some(line) = line {
                let _ = writeln!(out, "{line}");
            }
        }
        if last.elapsed().as_secs() >= 5 {
            last = Instant::now();
            let _ = out.flush();
            let rate = counts.visited as f64 / start.elapsed().as_secs_f64();
            eprintln!("size {} {:.0}/s visited {} values {} aliases {} refused {} faults {}", record.size, rate, counts.visited, counts.values, counts.aliases, counts.refused, counts.faults);
        }
        if arguments.limit.is_some_and(|limit| counts.visited >= limit) { ControlFlow::Break(()) } else { ControlFlow::Continue(()) }
    });
    let _ = out.flush();
    eprintln!("done in {:.1}s: visited {} values {} aliases {} refused {} faults {}", start.elapsed().as_secs_f64(), counts.visited, counts.values, counts.aliases, counts.refused, counts.faults);
    Ok(())
}

fn json_list(items: &[String]) -> String {
    format!("[{}]", items.iter().map(|item| json_string(item)).collect::<Vec<_>>().join(","))
}

fn run_names(arguments: &Arguments) -> Result<(), String> {
    let found = entries(&[TABLE_HOLE.to_string()], arguments.size, arguments.program_relations, arguments.max_inputs, arguments.limit.map(|limit| limit as usize));
    let mut out: Box<dyn Write> = match &arguments.out {
        Some(path) => Box::new(std::io::BufWriter::new(std::fs::File::create(path).map_err(|error| error.to_string())?)),
        None => Box::new(std::io::BufWriter::new(std::io::stdout())),
    };
    for entry in &found {
        let _ = writeln!(out, "{}", entry.expression);
    }
    eprintln!("{} entries", found.len());
    Ok(())
}

fn run_vector(arguments: &Arguments, solver: &str, table: &str) -> Result<(), String> {
    let holes = vec![TABLE_HOLE.to_string()];
    let host = host(arguments, solver)?;
    host.set_work_cap(arguments.work_cap);
    let found = match &arguments.names {
        Some(path) => {
            let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
            let mut found = Vec::new();
            for line in text.lines().filter(|line| !line.trim().is_empty()) {
                let feature = host.with_reader(|reader| reader.feature_text(line))?;
                found.extend(arclog_encoder::vectors::entry_of(feature));
            }
            found
        }
        None => entries(&holes, arguments.size, arguments.program_relations, arguments.max_inputs, arguments.limit.map(|limit| limit as usize)),
    };
    let vectors = vectors(&host, &found, &[(TABLE_HOLE.to_string(), table.to_string())]);
    let mut out: Box<dyn Write> = match &arguments.out {
        Some(path) => Box::new(std::io::BufWriter::new(std::fs::File::create(path).map_err(|error| error.to_string())?)),
        None => Box::new(std::io::BufWriter::new(std::io::stdout())),
    };
    for (at, vector) in vectors.iter().enumerate() {
        for (name, number) in &vector.numbers {
            let _ = writeln!(out, "{at}\t{number}\t{name}");
        }
    }
    eprintln!("{} assignments, {} numbers each", vectors.len(), vectors.first().map_or(0, |vector| vector.numbers.len()));
    Ok(())
}

fn run_grid_values(arguments: &Arguments, grids: &str) -> Result<(), String> {
    use arclog_encoder::closed::{closed_values, task_of_inputs, task_of_pairs, ClosedCounts, ClosedRun, OutputLeaf};
    let text = std::fs::read_to_string(grids).map_err(|error| error.to_string())?;
    let (task, output_leaf) = if arguments.rule {
        let pairs: Vec<(Vec<Vec<u8>>, Vec<Vec<u8>>)> = parse_grids(&text, true)?.into_iter().map(|pair| (pair.0, pair.1.expect("a pair"))).collect();
        (task_of_pairs(&pairs)?, OutputLeaf::Required)
    } else {
        let inputs: Vec<Vec<Vec<u8>>> = parse_grids(&text, false)?.into_iter().map(|pair| pair.0).collect();
        (task_of_inputs(&inputs)?, OutputLeaf::None)
    };
    let host = Host::of_task("(OUT (input ^P ^Col))", task)?;
    let run = ClosedRun { size: arguments.size, max_inputs: arguments.max_inputs, output_leaf, work_cap: arguments.work_cap };
    let path = arguments.out.clone().ok_or("`grid-values` writes to --out")?;
    let done: HashSet<String> = std::fs::read_to_string(&path).unwrap_or_default().lines().filter_map(|line| line.split('\t').next().map(str::to_string)).collect();
    let mut out = std::io::BufWriter::new(std::fs::OpenOptions::new().create(true).append(true).open(&path).map_err(|error| error.to_string())?);
    let mut counts = ClosedCounts::default();
    let start = Instant::now();
    let mut last = Instant::now();
    let mut written = 0u64;
    closed_values(&host, &run, &done, &mut counts, &mut |expression, size, values| {
        let _ = writeln!(out, "{expression}\t{size}\t{}", values.join(" "));
        written += 1;
        if last.elapsed().as_secs() >= 10 {
            last = Instant::now();
            let _ = out.flush();
            eprintln!("{written} roots written; {:.0}/s", written as f64 / start.elapsed().as_secs_f64());
        }
        ControlFlow::Continue(())
    });
    let _ = out.flush();
    eprintln!("done in {:.1}s: {counts:?}", start.elapsed().as_secs_f64());
    Ok(())
}

/// The grids of `text`, a JSON list of grids, or of pairs of grids where `pairs`
/// holds: a small reader of nested lists of digits.
fn parse_grids(text: &str, pairs: bool) -> Result<Vec<(Vec<Vec<u8>>, Option<Vec<Vec<u8>>>)>, String> {
    let value: serde_json::Value = serde_json::from_str(text).map_err(|error| error.to_string())?;
    let grid = |value: &serde_json::Value| -> Result<Vec<Vec<u8>>, String> {
        let rows = value.as_array().ok_or("a grid is a list")?;
        rows.iter().map(|row| row.as_array().ok_or("a row is a list".to_string()).and_then(|row| row.iter().map(|cell| cell.as_u64().map(|cell| cell as u8).ok_or("a cell is a digit".to_string())).collect())).collect()
    };
    let items = value.as_array().ok_or("a list of grids")?;
    items.iter().map(|item| {
        if pairs {
            let pair = item.as_array().ok_or("a pair is a list")?;
            Ok((grid(&pair[0])?, Some(grid(&pair[1])?)))
        } else {
            Ok((grid(item)?, None))
        }
    }).collect()
}

fn run_count(arguments: &Arguments, solver: &str, tables: &[String]) -> Result<(), String> {
    use arclog_encoder::enumerate::{value_kinds, Space, Typed};
    use arclog_encoder::expression::Rel;
    let host = host(arguments, solver)?;
    for task_wide in [false, true] {
        let space = Space { registry: arclog::registry::Registry::get(), tables: &host, task_wide, table_names: tables.to_vec(), program_relations: arguments.program_relations, kinds: value_kinds(), max_inputs: arguments.max_inputs, frames: Vec::new(), thin: None, no_output: false };
        let mut lower: Vec<Vec<Typed>> = Vec::new();
        for size in 0..=arguments.size {
            let start = Instant::now();
            let mut counts: std::collections::BTreeMap<String, u64> = std::collections::BTreeMap::new();
            let mut terms = Vec::new();
            let _ = space.generate(&lower, size, &mut |term| {
                let name = match &term.rel {
                    Rel::Leaf(_) => "leaf".to_string(),
                    Rel::Project(..) => "project".to_string(),
                    Rel::Select(..) => "select".to_string(),
                    Rel::Join(..) => "join".to_string(),
                    Rel::Antijoin(..) => "antijoin".to_string(),
                    Rel::Union(..) => "union".to_string(),
                    Rel::LibJoin(..) => "lib-join".to_string(),
                    Rel::Component(name, bindings, _) => format!("component/{} inputs/{name}", bindings.len()),
                    Rel::Pool { .. } => "pool".to_string(),
                    Rel::Call(..) => "call".to_string(),
                };
                *counts.entry(name).or_default() += 1;
                if size < arguments.size {
                    terms.push(term);
                }
                ControlFlow::Continue(())
            });
            let total: u64 = counts.values().sum();
            println!("task_wide {task_wide} size {size}: {total} terms in {:.1}s", start.elapsed().as_secs_f64());
            for (name, count) in &counts {
                println!("  {count:>10} {name}");
            }
            lower.push(terms);
        }
    }
    Ok(())
}

/// The train tasks of `path` that the law check samples, by a hash of each id.
fn sampled_tasks(path: &str, count: usize) -> Result<Vec<String>, String> {
    let text = std::fs::read_to_string(path).map_err(|error| error.to_string())?;
    let mut tasks: Vec<(String, String)> = text.split_whitespace().filter(|task| *task != "981571dc").map(|task| (arclog::hash::digest_text(&format!("law-sample/{task}")), task.to_string())).collect();
    tasks.sort();
    Ok(tasks.into_iter().take(count).map(|(_, task)| task).collect())
}

fn elements_of(task: &str) -> Vec<arclog_encoder::law::Element> {
    use arclog_encoder::law::Element;
    // A color permutation by a hash of the task, so a run is the same each time.
    let digest = arclog::hash::digest_text(&format!("law-colors/{task}"));
    let mut colors: Vec<u8> = (0..10).collect();
    for (at, byte) in digest.bytes().take(9).enumerate() {
        let other = at + usize::from(byte) % (10 - at);
        colors.swap(at, other);
    }
    let mut permuted = [0u8; 10];
    permuted.copy_from_slice(&colors);
    let identity = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
    let _ = identity;
    // A quarter turn and a reflection generate D4.
    vec![Element::new("D4_CW", permuted), Element::new("D4_LR", permuted)]
}

fn run_law(arguments: &Arguments, tasks_file: &str) -> Result<(), String> {
    use arclog_encoder::law::{compare_table, compare_with_program, Sample, Tally};
    let tasks = sampled_tasks(tasks_file, arguments.tasks_count)?;
    let path = arguments.out.clone().ok_or("`law` writes to --out")?;
    let done: HashSet<String> = std::fs::read_to_string(&path).unwrap_or_default().lines().filter_map(|line| {
        let start = line.find("\"key\":\"")? + 7;
        let end = line[start..].find('"')? + start;
        Some(line[start..end].to_string())
    }).collect();
    let mut out = std::io::BufWriter::new(std::fs::OpenOptions::new().create(true).append(true).open(&path).map_err(|error| error.to_string())?);
    let control = arguments.control.then(|| arclog_encoder::law::Element::new("D4_TB", [1, 0, 2, 3, 4, 5, 6, 7, 8, 9]));
    let sample = Sample { size: arguments.size, rate_per_million: arguments.rate, thin_per_million: arguments.thin, seconds: arguments.seconds, max_inputs: arguments.max_inputs, work_cap: arguments.work_cap, control };
    let start = Instant::now();
    let total = tasks.iter().enumerate().filter(|(at, _)| at % arguments.shard.1 == arguments.shard.0).count();
    let mut finished_tasks = 0usize;
    for (at, solver) in tasks.iter().enumerate() {
        if at % arguments.shard.1 != arguments.shard.0 {
            continue;
        }
        let state = (|| -> Result<Host, String> {
            let program = concept_program(&arguments.corpus, solver)?;
            Host::new(&program, &arguments.tasks.join(format!("{solver}.json")))
        })();
        let state = match state {
            Ok(state) => state,
            Err(message) => {
                let _ = writeln!(out, "{{\"key\":\"{solver}\",\"skipped\":{}}}", json_string(&message));
                let _ = out.flush();
                continue;
            }
        };
        let mut names = state.table_names();
        names.sort_by_key(|name| arclog::hash::digest_text(&format!("law-table/{solver}/{name}")));
        let mut tables = Vec::new();
        let mut left_out = Vec::new();
        for name in &names {
            if tables.len() >= arguments.tables_per_task {
                break;
            }
            match state.stored_rows(solver, name) {
                Ok(rows) => tables.push(rows),
                Err(message) => left_out.push(format!("{name}: {message}")),
            }
        }
        for table in &tables {
            if arguments.program_compare {
                let key = format!("{solver}/{}/program", table.table);
                if done.contains(&key) {
                    continue;
                }
                let mut tally = Tally::default();
                let began = Instant::now();
                let result = compare_with_program(table, &state, &sample, &mut tally, &mut |_| {});
                let differences: Vec<String> = tally.differences.iter().take(40).map(|difference| format!("{{\"expression\":{},\"law\":\"{:?}\",\"detail\":{}}}", json_string(&difference.expression), difference.law, json_string(&difference.detail))).collect();
                let fault = result.err().map_or("null".to_string(), |message| json_string(&message));
                let _ = writeln!(out, "{{\"key\":\"{key}\",\"seconds\":{:.1},\"compared\":{},\"invariant\":{},\"equivariant\":{},\"both_refused\":{},\"both_fault\":{},\"stopped\":{},\"out_of_time\":{},\"difference_count\":{},\"fault\":{fault},\"differences\":[{}]}}", began.elapsed().as_secs_f64(), tally.compared, tally.invariant, tally.equivariant, tally.both_refused, tally.both_fault, tally.stopped, tally.out_of_time, tally.differences.len(), differences.join(","));
                let _ = out.flush();
                continue;
            }
            for element in elements_of(solver) {
                let key = format!("{solver}/{}/{}", table.table, element.name);
                if done.contains(&key) {
                    continue;
                }
                let mut tally = Tally::default();
                let mut last = Instant::now();
                let began = Instant::now();
                let result = compare_table(table, &state.task, &element, &sample, &mut tally, &mut |tally| {
                    if last.elapsed().as_secs() >= 20 {
                        last = Instant::now();
                        eprintln!("{} {} compared {} differences {} ({:.0}s)", solver, table.table, tally.compared, tally.differences.len(), began.elapsed().as_secs_f64());
                    }
                });
                let differences: Vec<String> = tally.differences.iter().take(40).map(|difference| format!("{{\"expression\":{},\"law\":\"{:?}\",\"detail\":{}}}", json_string(&difference.expression), difference.law, json_string(&difference.detail))).collect();
                let fault = result.err().map_or("null".to_string(), |message| json_string(&message));
                let _ = writeln!(out, "{{\"key\":\"{key}\",\"seconds\":{:.1},\"compared\":{},\"invariant\":{},\"equivariant\":{},\"both_refused\":{},\"both_fault\":{},\"stopped\":{},\"out_of_time\":{},\"difference_count\":{},\"fault\":{fault},\"differences\":[{}]}}", began.elapsed().as_secs_f64(), tally.compared, tally.invariant, tally.equivariant, tally.both_refused, tally.both_fault, tally.stopped, tally.out_of_time, tally.differences.len(), differences.join(","));
                let _ = out.flush();
            }
        }
        if !left_out.is_empty() {
            let _ = writeln!(out, "{{\"key\":\"{solver}/left-out\",\"left_out\":{}}}", json_list(&left_out));
            let _ = out.flush();
        }
        finished_tasks += 1;
        let elapsed = start.elapsed().as_secs_f64();
        eprintln!("{finished_tasks}/{total} tasks; {:.2} tasks/min; ETA {:.0}s; last {solver}", finished_tasks as f64 / elapsed * 60.0, elapsed / finished_tasks as f64 * (total - finished_tasks) as f64);
    }
    Ok(())
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
        ("encode", [solver, tables @ ..]) if !tables.is_empty() => run_encode(&arguments, solver, tables),
        ("names", []) => run_names(&arguments),
        ("vector", [solver, table]) => run_vector(&arguments, solver, table),
        ("count", [solver, tables @ ..]) if !tables.is_empty() => run_count(&arguments, solver, tables),
        ("grid-values", [grids]) => run_grid_values(&arguments, grids),
        ("law", [tasks_file]) => run_law(&arguments, tasks_file),
        _ => Err("usage: feature-encoder eval|rows|worked|encode|names|vector ...; the file's first lines give each form".to_string()),
    };
    if let Err(message) = result {
        eprintln!("{message}");
        std::process::exit(1);
    }
}
