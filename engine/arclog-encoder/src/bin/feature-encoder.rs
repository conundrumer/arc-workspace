//! The feature encoder's commands.
//!
//!   feature-encoder eval SOLVER 'EXPRESSION' [--corpus DIR] [--tasks DIR] [--task-wide]
//!   feature-encoder rows SOLVER 'RELATION' [--corpus DIR] [--tasks DIR] [--task-wide]
//!   feature-encoder worked [--corpus DIR] [--tasks DIR]
//!   feature-encoder encode SOLVER TABLE... [--size D] [--out FILE] [--work-cap N] [--limit N] [--max-inputs N] [--program-relations]
//!   feature-encoder names [--size D] [--limit N] [--max-inputs N] [--program-relations] [--out FILE]
//!   feature-encoder vector SOLVER TABLE [--size D] --out FILE
//!   feature-encoder base-vectors SOLVER [--size D] --out FILE
//!   feature-encoder query-vectors SOLVER [--size D] --out FILE
//!   feature-encoder candidate-lists OUT_DIR (TASK | TABLES_FILE)... --size D [--names DERANGEMENTS] [--threads N]
//!   feature-encoder term-counts PATTERN TABLES_FILE [--size D]
//!   feature-encoder grid-values GRIDS_JSON (--scene | --rule) [--size D] [--max-inputs N] [--work-cap N] --out FILE
//!   feature-encoder count SOLVER TABLE... [--size D] [--max-inputs N] [--program-relations]
//!   feature-encoder stored-eval REQUESTS_JSONL --out FILE
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
use arclog_encoder::vectors::{entries, TABLE_HOLE};

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
    threads: usize,
    max_columns: Option<usize>,
    passes: usize,
    /// Whether the top size holds relational operators alone.
    relational: bool,
}

fn arguments() -> Arguments {
    let mut parsed = Arguments { positional: Vec::new(), corpus: PathBuf::from("work/arclog/gen"), tasks: PathBuf::from("data/tasks"), task_wide: false, size: 0, out: None, work_cap: 1 << 20, limit: None, max_inputs: None, program_relations: false, rate: 20_000, tables_per_task: 3, tasks_count: 60, shard: (0, 1), control: false, names: None, thin: 1_000_000, seconds: 30.0, program_compare: false, rule: false, threads: 1, max_columns: None, passes: 1, relational: false };
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
            "--relational" => parsed.relational = true,
            "--passes" => parsed.passes = args.next().and_then(|text| text.parse().ok()).expect("a number after --passes"),
            "--max-columns" => parsed.max_columns = args.next().and_then(|text| text.parse().ok()),
            "--threads" => parsed.threads = args.next().and_then(|text| text.parse().ok()).expect("a number after --threads"),
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
        Some(path) => arclog_encoder::zio::writer(path, true)?,
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
        Some(path) => arclog_encoder::zio::writer(path, false)?,
        None => Box::new(std::io::BufWriter::new(std::io::stdout())),
    };
    for entry in &found {
        let _ = writeln!(out, "{}", entry.expression);
    }
    eprintln!("{} entries", found.len());
    Ok(())
}

fn run_grid_values(arguments: &Arguments, grids: &str) -> Result<(), String> {
    use arclog_encoder::closed::{closed_values, task_of_inputs, task_of_pairs, ClosedCounts, ClosedRun, OutputLeaf};
    let text = arclog_encoder::zio::read_text(grids).map_err(|error| error.to_string())?;
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
    let done: HashSet<String> = arclog_encoder::zio::read_text(&path).unwrap_or_default().lines().filter_map(|line| line.split('\t').next().map(str::to_string)).collect();
    let mut out = arclog_encoder::zio::writer(&path, true)?;
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

/// The task of the grids in `text`, for a test that reads pairs where `rule` holds.
fn grids_task(text: &str, rule: bool) -> Result<arclog::task::Task, String> {
    use arclog_encoder::closed::{task_of_inputs, task_of_pairs};
    if rule {
        let pairs: Vec<(Vec<Vec<u8>>, Vec<Vec<u8>>)> = parse_grids(text, true)?.into_iter().map(|pair| (pair.0, pair.1.expect("a pair"))).collect();
        task_of_pairs(&pairs)
    } else {
        let inputs: Vec<Vec<Vec<u8>>> = parse_grids(text, false)?.into_iter().map(|pair| pair.0).collect();
        task_of_inputs(&inputs)
    }
}

fn scratch_host() -> Result<Host, String> {
    let task = arclog_encoder::closed::task_of_inputs(&[vec![vec![0u8]]])?;
    Host::of_task("(OUT (input ^P ^Col))", task)
}

/// The catalog's values on each requested table, with the time of its pass.
fn run_catalog_values(arguments: &Arguments, requests: &str) -> Result<(), String> {
    let path = arguments.out.clone().ok_or("`catalog-values` writes to --out")?;
    let mut out = arclog_encoder::zio::writer(&path, false)?;
    let (passes, spent) = arclog_encoder::catalog_run::values_of(requests, &arguments.tasks, &mut out)?;
    out.flush().map_err(|error| error.to_string())?;
    eprintln!("{passes} passes, {:.2} us per table at a pair", spent.as_secs_f64() * 1e6 / passes.max(1) as f64);
    Ok(())
}

/// The value of relation terms on a stored table, through the engine. Each request
/// is a line with `task`, `types`, `rows` by `train/i`, and `terms`, whose table is
/// `&t`, with columns `T0`, `T1`. Each result line gives a term's size, why the
/// checker refuses it, and at each example its count of rows and its first cell.
/// A shape's numbers at each example, as a vector's file writes them: `[greatest, second]`, where a
/// fraction is `[top, bottom]`, null where a bound stopped it, and 0 at its default.
fn slot_json(slot: &arclog_encoder::generate::Slot) -> serde_json::Value {
    use arclog_encoder::generate::{Number, SLOT_DEFAULT, SLOT_NO_VALUE};
    let number = |value: Number| if value.bottom <= 1 { serde_json::json!(value.top) } else { serde_json::json!([value.top, value.bottom]) };
    match slot.state {
        SLOT_DEFAULT => serde_json::json!(0),
        SLOT_NO_VALUE => serde_json::Value::Null,
        _ => serde_json::json!([number(slot.greatest), number(slot.second)]),
    }
}

/// Writes a vector's entries, one line per shape.
fn write_vector(out: &mut dyn Write, key: &serde_json::Value, vector: &arclog_encoder::table_vector::TableVector, names: &std::collections::HashMap<u64, String>) -> Result<(), String> {
    writeln!(out, "{}", serde_json::json!({"table": key, "entries": vector.shapes.len(), "examples": vector.examples, "train": vector.train, "table_rows_mean": vector.table_rows.0, "table_rows_max": vector.table_rows.1})).map_err(|error| error.to_string())?;
    for shape in 0..vector.shapes.len() {
        let at: Vec<serde_json::Value> = vector.at(shape).iter().map(slot_json).collect();
        writeln!(out, "{}", serde_json::json!({"shape": names.get(&vector.shapes[shape]), "reads": vector.meta[shape].0, "size": vector.meta[shape].1, "at": at})).map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn names_of(store: &arclog_encoder::generate::NameStore) -> std::collections::HashMap<u64, String> {
    store.all().into_iter().map(|(hash, name)| (hash as u64, name)).collect()
}

/// A table's vector at each of its assignments, and its `AssignmentVector`, to a file, since the
/// values at a test input read that input.
fn run_vector(arguments: &Arguments, solver: &str, table: &str) -> Result<(), String> {
    use arclog_encoder::generate::{Generators, Walker};
    use arclog_encoder::table_vector::{assignment_vector, table_vector, Grids};
    let path = arguments.out.clone().ok_or("`vector` writes to --out")?;
    let host = host(arguments, solver)?;
    let (_, grids) = Grids::of_file(&arguments.tasks, solver, None)?;
    let tables = arclog_encoder::run::stored_tables(&host, table)?;
    let families = Generators::default();
    let mut out = arclog_encoder::zio::writer(&path, false)?;
    let examples = grids.inputs.len();
    let mut vectors = Vec::with_capacity(tables.at.len());
    for (_, stored) in &tables.at {
        let family = families.get(stored, arguments.size.max(1));
        let mut walker = Walker::new(&family);
        vectors.push((stored.content(), table_vector(&mut walker, stored, &grids, examples, false)));
    }
    let names = names_of(&families.names);
    for ((assignment, _), (_, vector)) in tables.at.iter().zip(&vectors) {
        write_vector(&mut out, &serde_json::json!({"name": table, "assignment": format!("{assignment:?}")}), vector, &names)?;
    }
    let refs: Vec<(u128, &arclog_encoder::table_vector::TableVector)> = vectors.iter().map(|(hash, vector)| (*hash, vector)).collect();
    let pooled = assignment_vector(&refs, tables.capped);
    writeln!(out, "{}", serde_json::json!({"assignment_vector": table, "count": pooled.count, "capped": pooled.capped, "distinct": pooled.distinct, "differ": pooled.differ, "entries": pooled.shapes.len()})).map_err(|error| error.to_string())?;
    if pooled.count > 1 {
        for (at, shape) in pooled.shapes.iter().enumerate() {
            let held = &pooled.pools[at * pooled.examples..(at + 1) * pooled.examples];
            writeln!(out, "{}", serde_json::json!({"shape": names.get(shape), "pools": held})).map_err(|error| error.to_string())?;
        }
    }
    out.flush().map_err(|error| error.to_string())?;
    eprintln!("{} assignments, {} shapes over them", pooled.count, pooled.shapes.len());
    Ok(())
}

/// Each query's `QueryVector`, one JSON line per query, to a file.
fn run_query_vectors(arguments: &Arguments, solver: &str) -> Result<(), String> {
    use arclog_encoder::generate::Generators;
    use arclog_encoder::table_vector::Grids;
    let path = arguments.out.clone().ok_or("`query-vectors` writes to --out")?;
    let host = host(arguments, solver)?;
    let (_, grids) = Grids::of_file(&arguments.tasks, solver, None)?;
    let families = Generators::default();
    let vectors = arclog_encoder::query_vector::query_vectors(&host, &grids, &families, arguments.size)?;
    let mut out = arclog_encoder::zio::writer(&path, false)?;
    for vector in &vectors {
        let line = serde_json::json!({"query": vector.identity, "names": vector.names, "values": vector.values, "use_names": vector.use_names, "per_use": vector.per_use, "column_origin": vector.column_origin});
        writeln!(out, "{line}").map_err(|error| error.to_string())?;
    }
    out.flush().map_err(|error| error.to_string())?;
    eprintln!("{} queries", vectors.len());
    Ok(())
}

/// The base tables' vectors, to a file.
fn run_base_vectors(arguments: &Arguments, solver: &str) -> Result<(), String> {
    use arclog_encoder::generate::Generators;
    use arclog_encoder::table_vector::{base_vectors, Grids};
    let path = arguments.out.clone().ok_or("`base-vectors` writes to --out")?;
    let (_, grids) = Grids::of_file(&arguments.tasks, solver, None)?;
    let families = Generators::default();
    let base = base_vectors(&grids, &families, arguments.size.max(1));
    let mut out = arclog_encoder::zio::writer(&path, false)?;
    let names = names_of(&families.names);
    write_vector(&mut out, &serde_json::json!({"base": "input"}), &base.input, &names)?;
    write_vector(&mut out, &serde_json::json!({"base": "ex_output"}), &base.ex_output, &names)?;
    out.flush().map_err(|error| error.to_string())
}

/// Each table's stable roots, one file per task, with a task's tables read from a command that
/// prints them or from a file. `GENERATE_TABLES_CMD` holds that command, to which the task's name
/// is added. What it prints holds test rows, so it reaches this process by a pipe alone, and
/// neither its output nor its errors are printed or kept. `--names` gives a derangement per task,
/// and then each pair reads another pair's output.
fn run_candidate_lists(arguments: &Arguments, out: &str, sources: &[String]) -> Result<(), String> {
    use arclog_encoder::candidate_lists::lists_task;
    use arclog_encoder::generate::{Generators, NameStore};
    std::fs::create_dir_all(out).map_err(|error| error.to_string())?;
    let mut families = Generators::default();
    families.names = NameStore::to_file(&format!("{out}/names.tsv.zst"))?;
    let derangements: Option<std::collections::BTreeMap<String, Option<Vec<usize>>>> = match &arguments.names {
        Some(path) => Some(serde_json::from_str(&arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?),
        None => None,
    };
    let command: Option<Vec<String>> = std::env::var("GENERATE_TABLES_CMD").ok().map(|text| text.split_whitespace().map(str::to_string).collect());
    let d = arguments.size.max(1);
    let next = std::sync::atomic::AtomicUsize::new(0);
    let finished = std::sync::atomic::AtomicUsize::new(0);
    let totals = std::sync::Mutex::new((0u64, 0f64));
    let begun = Instant::now();
    std::thread::scope(|scope| {
        for _ in 0..arguments.threads.max(1) {
            scope.spawn(|| loop {
                let at = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let Some(source) = sources.get(at) else { break };
                let stem = arclog_encoder::zio::stem(source);
                let target = format!("{out}/{stem}.lists.zst");
                if std::path::Path::new(&target).exists() {
                    continue;
                }
                let order: Option<&[usize]> = match &derangements {
                    None => None,
                    Some(held) => match held.get(&stem).and_then(Option::as_ref) {
                        Some(order) => Some(order.as_slice()),
                        // A task whose train outputs are all equal leaves the null.
                        None => continue,
                    },
                };
                let text = match &command {
                    Some(parts) => {
                        let run = std::process::Command::new(&parts[0]).args(&parts[1..]).arg(&stem).stderr(std::process::Stdio::null()).output();
                        match run {
                            Ok(run) if run.status.success() => String::from_utf8(run.stdout).map_err(|error| error.to_string()),
                            Ok(run) => Err(format!("the tables command ended with {}", run.status)),
                            Err(error) => Err(error.to_string()),
                        }
                    }
                    None => arclog_encoder::zio::read_text(source),
                };
                let text = match text {
                    Ok(text) => text,
                    Err(message) => {
                        eprintln!("{stem}: {message}");
                        continue;
                    }
                };
                let result = lists_task(&text, &arguments.tasks, &families, order, d);
                drop(text);
                match result {
                    Ok(found) => {
                        if arclog_encoder::zio::write_bytes(&target, &found.bytes).is_err() {
                            eprintln!("{stem}: the lists do not write");
                        }
                        families.names.flush();
                        let mut held = totals.lock().expect("no panic");
                        held.0 += found.walks;
                        held.1 += found.seconds;
                        let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                        let rate = done as f64 / begun.elapsed().as_secs_f64();
                        eprintln!("{done}/{} {}: {} walks, {:.0} ms per walk so far, {} shapes; ETA {:.0}s", sources.len(), found.task, found.walks, held.1 * 1e3 / held.0.max(1) as f64, found.shapes, (sources.len() - done) as f64 / rate);
                    }
                    Err(message) => eprintln!("{stem}: {message}"),
                }
            });
        }
    });
    families.names.flush();
    Ok(())
}

/// The rows at each train pair of each generated term whose text holds a pattern, on each gold
/// table of a kept tables file, for a check against the expression a term stands for.
fn run_term_counts(arguments: &Arguments, pattern: &str, file: &str) -> Result<(), String> {
    use arclog_encoder::generate::{leaves_at, Generators, Walker};
    use arclog_encoder::stored::Stored;
    use arclog_encoder::table_vector::Grids;
    let data: serde_json::Value = serde_json::from_str(&arclog_encoder::zio::read_text(file)?).map_err(|error| error.to_string())?;
    let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
    let train = data["train"].as_u64().ok_or("a file's train")? as usize;
    let (_, grids) = Grids::of_file(&arguments.tasks, &task_name, None)?;
    let families = Generators::default();
    let empty = Vec::new();
    for item in data["items"].as_array().unwrap_or(&empty) {
        let Some(stored) = Stored::of_json(&item["gold"], train, 0, usize::MAX) else { continue };
        if stored.types.len() > 8 {
            continue;
        }
        let family = families.get(&stored, arguments.size.max(1));
        let mut walker = Walker::new(&family);
        let example_of: Vec<usize> = (0..train).collect();
        let rows: Vec<_> = stored.rows.iter().map(|models| models.first().cloned()).collect();
        let leaves = leaves_at(&rows, &example_of, &grids.inputs, &grids.outputs, &grids.constants);
        for (text, counts) in walker.term_counts(&leaves, train, pattern) {
            println!("{}\t{}\t{}\t{}", item["table"].as_str().unwrap_or(""), serde_json::json!(item["gold"]["types"]), text, serde_json::json!(counts));
        }
    }
    Ok(())
}

fn run_stored_eval(arguments: &Arguments, requests: &str) -> Result<(), String> {
    use arclog_encoder::expression::Reader;
    use arclog_encoder::run::StoredRows;
    use arclog_encoder::schema::{type_of_name, TableColumn};
    use arclog_encoder::stored::cell_bits;
    let path = arguments.out.clone().ok_or("`stored-eval` writes to --out")?;
    let mut out = arclog_encoder::zio::writer(&path, false)?;
    let registry = arclog::registry::Registry::get();
    let reader = Reader { registry, library: arclog_encoder::library::library(), program_relations: &arclog_encoder::program_relations::is_program_relation };
    let text = arclog_encoder::zio::read_text(requests).map_err(|error| error.to_string())?;
    for (at, line) in text.lines().enumerate() {
        let request: serde_json::Value = serde_json::from_str(line).map_err(|error| error.to_string())?;
        let task_name = request["task"].as_str().ok_or("a request's task")?;
        let task = arclog::task::read_task(&arguments.tasks.join(format!("{task_name}.json"))).map_err(|error| format!("{error:?}"))?;
        let types: Vec<arclog::types::ValueType> = request["types"].as_array().ok_or("a request's types")?.iter().map(|name| type_of_name(name.as_str().unwrap_or(""))).collect::<Option<_>>().ok_or("a type with no name")?;
        let mut rows = Vec::new();
        for pair in 0..task.train.len() {
            let held = request["rows"].get(format!("train/{pair}")).and_then(serde_json::Value::as_array).cloned().unwrap_or_default();
            let mut table: Vec<Vec<arclog::terms::TermId>> = Vec::with_capacity(held.len());
            for row in &held {
                let row = row.as_array().ok_or("a row")?;
                let cells: Option<Vec<arclog::terms::TermId>> = row.iter().zip(&types).map(|(cell, ty)| cell_bits(cell, ty).map(arclog::terms::TermId::from_encoding)).collect();
                table.push(cells.ok_or("a cell")?);
            }
            rows.push((Some(arclog::terms::Example::at(pair as u16)), table));
        }
        for extra in 0..task.test.len() {
            rows.push((Some(arclog::terms::Example::at((task.train.len() + extra) as u16)), Vec::new()));
        }
        let columns: Vec<TableColumn> = types.iter().enumerate().map(|(place, ty)| TableColumn { name: format!("T{place}"), path: vec![format!("T{place}")], ty: Some(ty.clone()) }).collect();
        let stored = StoredRows { table: "&t".to_string(), stored_name: format!("stored-eval/{at}"), columns, types: types.clone(), per_input: true, has_example: false, rows };
        let train = task.train.len();
        let host = Host::stored(task, &stored)?;
        for term in request["terms"].as_array().ok_or("a request's terms")? {
            let written = term.as_str().ok_or("a term")?;
            let outcome = reader.rel_text(written).and_then(|rel| {
                let size = rel.size();
                host.evaluate_terms(&[&rel], false).pop().expect("one term").map(|values| (size, values))
            });
            let record = match outcome {
                Err(message) => serde_json::json!({"line": at, "term": written, "refused": message.chars().take(240).collect::<String>()}),
                Ok((size, values)) => {
                    let mut counts = Vec::new();
                    let mut firsts = Vec::new();
                    for relation in values.examples.iter().take(train) {
                        match relation {
                            None => {
                                counts.push(serde_json::Value::Null);
                                firsts.push(serde_json::Value::Null);
                            }
                            Some(relation) => {
                                counts.push(serde_json::json!(relation.len()));
                                let mut first = None;
                                arclog::eval::join::each_row(relation, &mut |row| {
                                    if first.is_none() {
                                        first = row.first().map(|cell| arclog::terms::Term::decode_number(*cell));
                                    }
                                });
                                firsts.push(serde_json::json!(first));
                            }
                        }
                    }
                    serde_json::json!({"line": at, "term": written, "size": size, "counts": counts, "firsts": firsts})
                }
            };
            writeln!(out, "{record}").map_err(|error| error.to_string())?;
        }
        out.flush().map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn run_count(arguments: &Arguments, solver: &str, tables: &[String]) -> Result<(), String> {
    use arclog_encoder::enumerate::{Space, Typed};
    use arclog_encoder::expression::Rel;
    let host = host(arguments, solver)?;
    for task_wide in [false, true] {
        let space = Space { registry: arclog::registry::Registry::get(), tables: &host, task_wide, table_names: tables.to_vec(), program_relations: arguments.program_relations, max_inputs: arguments.max_inputs, thin: None, no_output: false, quick: false, max_bound_columns: None };
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
                    Rel::Semijoin(..) => "semijoin".to_string(),
                    Rel::All(..) => "all".to_string(),
                    Rel::Union(..) => "union".to_string(),
                    Rel::LibJoin(..) => "lib-join".to_string(),
                    Rel::Component(name, bindings, _) => format!("component/{} inputs/{name}", bindings.len()),
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
    let text = arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?;
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
    let done: HashSet<String> = arclog_encoder::zio::read_text(&path).unwrap_or_default().lines().filter_map(|line| {
        let start = line.find("\"key\":\"")? + 7;
        let end = line[start..].find('"')? + start;
        Some(line[start..end].to_string())
    }).collect();
    let mut out = arclog_encoder::zio::writer(&path, true)?;
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
        ("base-vectors", [solver]) => run_base_vectors(&arguments, solver),
        ("query-vectors", [solver]) => run_query_vectors(&arguments, solver),
        ("candidate-lists", [out, sources @ ..]) if !sources.is_empty() => run_candidate_lists(&arguments, out, sources),
        ("term-counts", [pattern, file]) => run_term_counts(&arguments, pattern, file),
        ("count", [solver, tables @ ..]) if !tables.is_empty() => run_count(&arguments, solver, tables),
        ("grid-values", [grids]) => run_grid_values(&arguments, grids),
        ("law", [tasks_file]) => run_law(&arguments, tasks_file),
        ("stored-eval", [requests]) => run_stored_eval(&arguments, requests),
        ("catalog-values", [requests]) => run_catalog_values(&arguments, requests),
        _ => Err("usage: feature-encoder eval|rows|worked|encode|names|vector ...; the file's first lines give each form".to_string()),
    };
    if let Err(message) = result {
        eprintln!("{message}");
        std::process::exit(1);
    }
}
