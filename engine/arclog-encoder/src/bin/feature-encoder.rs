//! The feature encoder's commands.
//!
//!   feature-encoder eval SOLVER 'EXPRESSION' [--corpus DIR] [--tasks DIR] [--task-wide]
//!   feature-encoder rows SOLVER 'RELATION' [--corpus DIR] [--tasks DIR] [--task-wide]
//!   feature-encoder worked [--corpus DIR] [--tasks DIR]
//!   feature-encoder encode SOLVER TABLE... [--size D] [--out FILE] [--work-cap N] [--limit N] [--max-inputs N] [--program-relations]
//!   feature-encoder names [--size D] [--limit N] [--max-inputs N] [--program-relations] [--out FILE]
//!   feature-encoder vector SOLVER TABLE [--size D] [--wide-size D] [--shapes FILE] --out FILE
//!   feature-encoder shape-check SOLVER... --sample N [--seed S] [--max-tables K] [--size D] [--out FILE]
//!   feature-encoder cap-hits SOLVER... [--size D] [--max-tables K] --out FILE
//!   feature-encoder base-vectors SOLVER [--size D] --out FILE
//!   feature-encoder query-vectors SOLVER [--size D] --out FILE
//!   feature-encoder state-vectors SOLVER [--size D] --out FILE
//!   feature-encoder candidate-lists OUT_DIR (TASK | TABLES_FILE)... --size D [--names DERANGEMENTS] [--threads N] [--wide-only [--wide-size D] | --parents-only | --state-only] [--tables-cmd COMMAND]
//!   feature-encoder all-lists ROOT (TASK | TABLES_FILE)... --size D --tables-cmd COMMAND [--names DERANGEMENTS] [--threads N] [--wide-size D] [--families DIR] [--count-bounds]
//!   feature-encoder term-counts PATTERN TABLES_FILE [--size D]
//!   feature-encoder shapes-refresh ROWS_FILE TASK OUT [--shapes FILE] [--threads N] [--families DIR] [--count-bounds] [--headerless]
//!   feature-encoder engine
//!   feature-encoder term-stats TYPE,TYPE,... [--size D]
//!   feature-encoder family-names TYPE,TYPE,... [--size D]
//!   feature-encoder refine-explain CALL ARITY KEY_BITS
//!   feature-encoder shape-count TABLES_FILE... [--size D]
//!   feature-encoder grid-values GRIDS_JSON (--scene | --rule) [--size D] [--max-inputs N] [--work-cap N] --out FILE
//!   feature-encoder grid-vectors GRIDS_JSON (--scene | --rule) [--size D] --out FILE
//!   feature-encoder count SOLVER TABLE... [--size D] [--max-inputs N] [--program-relations]
//!   feature-encoder stored-eval REQUESTS_JSONL --out FILE
//!   feature-encoder law TASKS_FILE [--size D] [--rate R] [--max-inputs N] [--tables K] [--thin R] [--seconds S] [--tasks-count N] [--shard I/N] [--control] [--program-compare] [--out FILE]
//!
//! `eval` prints the forms and the value of a feature expression on the
//! concept case of a solver, and `rows` those of a relation term. `worked`
//! checks the worked expansions of the specification. `encode` writes one JSON
//! line for each ground expression up to a size, small sizes first; on a restart
//! with the same `--out` it skips the expressions the file holds. `names` writes
//! the vector entries at a size, and `vector` their numbers on a table; with `--shapes` it walks only the
//! terms that the listed shapes need, and writes the listed shapes' lines. `shape-check` draws a list of
//! `--sample` shapes from the full vector of each table of each solver, and for each assignment compares the
//! list walk's slots with the full walk's and gives the CPU seconds of both. `count`
//! prints the terms at each size, by operator, with no evaluation. `grid-values`
//! writes the value of each closed root at each grid of a file: a list of grids
//! for Scene recognition, of pairs of grids for Rule recognition. A line holds the
//! root, its size and its values; on a restart it skips the roots the file holds. `law` compares
//! a sample of features on a sample of tables with their images under the group,
//! writing a line per table and element, and on a restart skips those the file
//! holds. With `--program-compare` it compares each table's stored rows with the
//! table as its program computes it.
//!
//! `--count-bounds` counts the evaluations that a bound stopped, per bound and per term head, and prints
//! the counts to the standard error when the command ends, with a `term` line for each term that a walk
//! charges many cells or spends much time on. `all-lists`, `shapes-refresh` and `cap-hits` take it, and `cap-hits` runs
//! with it always. The progress line of `all-lists` and the summary line of `shapes-refresh` say that the
//! counts were on, and so does the first line of the file that `cap-hits` writes. A `term` line holds the
//! term's text, so a run with the counts keeps the text of its terms, and reads and writes no saved family.
//! The commands that read or print a term's text keep it always: `cap-hits`, `term-counts` and
//! `term-stats`.
//!
//! `engine` prints the encoder's producers, which the header of a rows file must name for `shapes-refresh` to read it. `shapes-refresh`
//! refuses a rows file with no header, unless `--headerless`, which only the store's check set of `scripts/shape_store.py same-values` passes.

#[global_allocator]
static ALLOCATOR: mimalloc::MiMalloc = mimalloc::MiMalloc;

use std::io::{BufRead, Write};
use std::ops::ControlFlow;
use std::path::PathBuf;
use std::time::Instant;

use arclog_encoder::encoder::{encode, json_string, value_json, Counts, Law, Options, Outcome};
use arclog_encoder::lookup::{LookupMap, LookupSet};
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
    wide_size: Option<usize>,
    kinds: Option<Vec<String>>,
    families: Option<PathBuf>,
    wide_only: bool,
    parents_only: bool,
    state_only: bool,
    thin: u32,
    seconds: f64,
    program_compare: bool,
    rule: bool,
    threads: usize,
    max_columns: Option<usize>,
    passes: usize,
    /// Whether the top size holds relational operators alone.
    relational: bool,
    /// A file of shape hashes or shape texts, one per line.
    shapes: Option<PathBuf>,
    sample: usize,
    seed: u64,
    max_tables: usize,
    /// Whether the evaluations that a bound stopped are counted: `--count-bounds`.
    count_bounds: bool,
    /// The command that prints a task's tables, as words: `--tables-cmd`.
    tables_cmd: Option<Vec<String>>,
    /// Whether `shapes-refresh` reads a rows file with no header: `--headerless`.
    headerless: bool,
}

fn arguments() -> Arguments {
    let mut parsed = Arguments { kinds: None, families: None, wide_size: None, wide_only: false, parents_only: false, state_only: false, positional: Vec::new(), corpus: PathBuf::from("programs/arclog"), tasks: PathBuf::from("data/tasks"), task_wide: false, size: 0, out: None, work_cap: 1 << 20, limit: None, max_inputs: None, program_relations: false, rate: 20_000, tables_per_task: 3, tasks_count: 60, shard: (0, 1), control: false, names: None, thin: 1_000_000, seconds: 30.0, program_compare: false, rule: false, threads: 1, max_columns: None, passes: 1, relational: false, shapes: None, sample: 0, seed: 1, max_tables: usize::MAX, count_bounds: false, tables_cmd: None, headerless: false };
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--corpus" => parsed.corpus = args.next().expect("a directory after --corpus").into(),
            "--tasks" => parsed.tasks = args.next().expect("a directory after --tasks").into(),
            "--task-wide" => parsed.task_wide = true,
            "--size" => parsed.size = args.next().and_then(|text| text.parse().ok()).expect("a number after --size"),
            "--wide-size" => parsed.wide_size = Some(args.next().and_then(|text| text.parse().ok()).expect("a number after --wide-size")),
            "--families" => parsed.families = Some(args.next().expect("a directory after --families").into()),
            "--kinds" => parsed.kinds = Some(args.next().expect("kinds after --kinds").split(',').map(str::to_string).collect()),
            "--wide-only" => parsed.wide_only = true,
            "--parents-only" => parsed.parents_only = true,
            "--state-only" => parsed.state_only = true,
            "--out" => parsed.out = Some(args.next().expect("a file after --out").into()),
            "--work-cap" => parsed.work_cap = args.next().and_then(|text| text.parse().ok()).expect("a number after --work-cap"),
            "--limit" => parsed.limit = Some(args.next().and_then(|text| text.parse().ok()).expect("a number after --limit")),
            "--max-inputs" => parsed.max_inputs = Some(args.next().and_then(|text| text.parse().ok()).expect("a number after --max-inputs")),
            "--program-relations" => parsed.program_relations = true,
            "--rate" => parsed.rate = args.next().and_then(|text| text.parse().ok()).expect("a count per million after --rate"),
            "--control" => parsed.control = true,
            "--program-compare" => parsed.program_compare = true,
            "--count-bounds" => parsed.count_bounds = true,
            "--headerless" => parsed.headerless = true,
            "--tables-cmd" => parsed.tables_cmd = Some(args.next().expect("a command after --tables-cmd").split_whitespace().map(str::to_string).collect()),
            "--rule" => parsed.rule = true,
            "--relational" => parsed.relational = true,
            "--shapes" => parsed.shapes = Some(args.next().expect("a file after --shapes").into()),
            "--sample" => parsed.sample = args.next().and_then(|text| text.parse().ok()).expect("a number after --sample"),
            "--seed" => parsed.seed = args.next().and_then(|text| text.parse().ok()).expect("a number after --seed"),
            "--max-tables" => parsed.max_tables = args.next().and_then(|text| text.parse().ok()).expect("a number after --max-tables"),
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
fn finished(path: &PathBuf) -> LookupSet<String> {
    let Ok(file) = std::fs::File::open(path) else { return LookupSet::new() };
    let mut held = LookupSet::new();
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
    let done: LookupSet<String> = arclog_encoder::zio::read_text(&path).unwrap_or_default().lines().filter_map(|line| line.split('\t').next().map(str::to_string)).collect();
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

/// Each generated shape over the base tables at each grid of a file, as `grid-values` writes its roots, with
/// the table each reads before its name: a word for a value, `1` for a default, and `-` for no value. A shape with one
/// word at every grid is left out.
fn run_grid_vectors(arguments: &Arguments, grids: &str) -> Result<(), String> {
    use arclog_encoder::closed::{task_of_inputs, task_of_pairs};
    use arclog_encoder::generate::{Generators, SlotState, Walker, READS_OUTPUT};
    use arclog_encoder::stored::Stored;
    use arclog_encoder::table_vector::{pair_vector, table_vector, Grids, TableVector};
    let text = arclog_encoder::zio::read_text(grids).map_err(|error| error.to_string())?;
    let path = arguments.out.clone().ok_or("`grid-vectors` writes to --out")?;
    let (task, json) = if arguments.rule {
        let pairs: Vec<(Vec<Vec<u8>>, Vec<Vec<u8>>)> = parse_grids(&text, true)?.into_iter().map(|pair| (pair.0, pair.1.expect("a pair"))).collect();
        let train: Vec<serde_json::Value> = pairs.iter().map(|(input, output)| serde_json::json!({"input": input, "output": output})).collect();
        (task_of_pairs(&pairs)?, serde_json::json!({"train": train, "test": []}))
    } else {
        let inputs: Vec<Vec<Vec<u8>>> = parse_grids(&text, false)?.into_iter().map(|pair| pair.0).collect();
        let test: Vec<serde_json::Value> = inputs.iter().map(|input| serde_json::json!({"input": input})).collect();
        (task_of_inputs(&inputs)?, serde_json::json!({"train": [], "test": test}))
    };
    let grids = Grids::of(&task, &json, None);
    let (d, examples) = (arguments.size.max(1), grids.inputs.len());
    let families = Generators::default();
    let input = Stored::of_grids(&grids.inputs);
    let family = families.get(&input, d);
    let mut walker = Walker::new(&family);
    let mut vectors: Vec<(&str, TableVector)> = Vec::new();
    if arguments.rule {
        let output = Stored::of_grids(&grids.outputs);
        vectors.push(("input", table_vector(&mut walker, &input, &grids, examples, true)));
        vectors.push(("output", table_vector(&mut walker, &output, &grids, examples, false)));
        vectors.push(("pair", pair_vector(&grids, &families, d, true)));
    } else {
        vectors.push(("input", table_vector(&mut walker, &input, &grids, examples, false)));
        vectors.push(("pair", pair_vector(&grids, &families, d, false)));
    }
    let names = names_of(&families.names);
    let mut out = arclog_encoder::zio::writer(&path, false)?;
    let mut written = 0u64;
    for (table, vector) in &vectors {
        for shape in 0..vector.shapes.len() {
            if !arguments.rule && vector.meta[shape].0 & READS_OUTPUT != 0 {
                continue;
            }
            let words: Vec<String> = vector.at(shape).iter().map(|slot| match slot.state {
                SlotState::NoValue => "-".to_string(),
                SlotState::Value => format!("{:016x}", slot.digest | 2),
                SlotState::Default => format!("{:016x}", 1),
            }).collect();
            if words.windows(2).all(|two| two[0] == two[1]) {
                continue;
            }
            let name = names.get(&vector.shapes[shape]).map_or("", String::as_str);
            writeln!(out, "{table} {name}\t{}\t{}", vector.meta[shape].1, words.join(" ")).map_err(|error| error.to_string())?;
            written += 1;
        }
    }
    out.flush().map_err(|error| error.to_string())?;
    eprintln!("{written} roots over {examples} grids");
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
    use arclog_encoder::generate::{Number, SlotState};
    let number = |value: Number| if value.bottom <= 1 { serde_json::json!(value.top) } else { serde_json::json!([value.top, value.bottom]) };
    match slot.state {
        SlotState::Default => serde_json::json!(0),
        SlotState::NoValue => serde_json::Value::Null,
        SlotState::Value => serde_json::json!([number(slot.greatest), number(slot.second)]),
    }
}

/// Writes a vector's entries, one line per shape.
fn write_vector(out: &mut dyn Write, key: &serde_json::Value, vector: &arclog_encoder::table_vector::TableVector, names: &LookupMap<u64, String>) -> Result<(), String> {
    writeln!(out, "{}", serde_json::json!({"table": key, "entries": vector.shapes.len(), "examples": vector.examples, "train": vector.train, "table_rows_mean": vector.table_rows.0, "table_rows_max": vector.table_rows.1})).map_err(|error| error.to_string())?;
    for shape in 0..vector.shapes.len() {
        let at: Vec<serde_json::Value> = vector.at(shape).iter().map(slot_json).collect();
        writeln!(out, "{}", serde_json::json!({"shape": names.get(&vector.shapes[shape]), "reads": vector.meta[shape].0, "size": vector.meta[shape].1, "at": at})).map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn names_of(store: &arclog_encoder::generate::NameStore) -> LookupMap<u64, String> {
    store.by_vector_hash()
}

/// The shapes of a file, one per line. A line whose first field, up to a tab, is up to 16 hex digits with or
/// without `0x` gives a hash, as the names file writes them. Any other line is a shape's text.
fn read_shape_list(path: &std::path::Path) -> Result<arclog_encoder::generate::ShapeList, String> {
    Ok(arclog_encoder::generate::ShapeList::new(read_shape_hashes(path)?))
}

/// The hashes of a file's shapes, in the file's order (see [`read_shape_list`]).
fn read_shape_hashes(path: &std::path::Path) -> Result<Vec<u64>, String> {
    use arclog_encoder::generate::ShapeList;
    let text = arclog_encoder::zio::read_text(path)?;
    let mut hashes = Vec::new();
    for line in text.lines() {
        let field = line.split('\t').next().unwrap_or_default().trim();
        if field.is_empty() {
            continue;
        }
        let digits = field.strip_prefix("0x").unwrap_or(field);
        let hash = if digits.len() <= 16 { u64::from_str_radix(digits, 16).ok() } else { None };
        hashes.push(hash.unwrap_or_else(|| ShapeList::hash_of_text(line.trim())));
    }
    Ok(hashes)
}

/// The CPU seconds that this thread has used.
fn thread_cpu_seconds() -> f64 {
    #[repr(C)]
    struct Timespec {
        seconds: i64,
        nanoseconds: i64,
    }
    unsafe extern "C" {
        fn clock_gettime(clock: u32, now: *mut Timespec) -> i32;
    }
    #[cfg(target_os = "macos")]
    const THREAD_CPU: u32 = 16;
    #[cfg(not(target_os = "macos"))]
    const THREAD_CPU: u32 = 3;
    let mut now = Timespec { seconds: 0, nanoseconds: 0 };
    // SAFETY: `now` is a valid timespec for the call to fill.
    unsafe { clock_gettime(THREAD_CPU, &mut now) };
    now.seconds as f64 + now.nanoseconds as f64 * 1e-9
}

/// For each table of each solver and each assignment of it: a list of `--sample` shapes drawn from the shapes of
/// the full vectors over the table's assignments, the list walk against the full walk, and the CPU seconds of
/// each. A line holds counts and seconds, and no value. A slot is the same where its state, greatest, second and
/// digest are, at every example.
fn run_shape_check(arguments: &Arguments, solvers: &[String]) -> Result<(), String> {
    use arclog_encoder::generate::{Generators, ShapeList, Slot, Walker};
    use arclog_encoder::table_vector::{table_vector, table_vector_of_shapes, Grids};
    if arguments.sample == 0 {
        return Err("`shape-check` takes --sample N".to_string());
    }
    let mut out: Box<dyn Write + Send> = match &arguments.out {
        Some(path) => arclog_encoder::zio::writer(path, false)?,
        None => Box::new(std::io::stdout()),
    };
    let same = |a: &Slot, b: &Slot| a.state == b.state && a.digest == b.digest && a.greatest == b.greatest && a.second == b.second;
    let size = arguments.size.max(1);
    for solver in solvers {
        let prepared = host(arguments, solver).and_then(|host| Grids::of_file(&arguments.tasks, solver, None).map(|(_, grids)| (host, grids)));
        let (host, grids) = match prepared {
            Ok(held) => held,
            Err(message) => {
                eprintln!("{solver}: {message}");
                continue;
            }
        };
        let examples = grids.inputs.len();
        let families = Generators::default();
        for (identity, spelled) in host.program_facts().table_names.iter().take(arguments.max_tables) {
            let Ok(tables) = arclog_encoder::run::stored_tables(&host, spelled) else { continue };
            let mut fulls = Vec::with_capacity(tables.at.len());
            for (_, stored) in &tables.at {
                let family = families.get(stored, size);
                arclog_encoder::gen_parts::clear_views();
                let (vector, seconds) = {
                    let mut walker = Walker::new(&family);
                    let begun = thread_cpu_seconds();
                    let vector = table_vector(&mut walker, stored, &grids, examples, false);
                    (vector, thread_cpu_seconds() - begun)
                };
                fulls.push((family, vector, seconds));
            }
            let mut union: Vec<u64> = fulls.iter().flat_map(|(_, vector, _)| vector.shapes.iter().copied()).collect();
            union.sort_unstable();
            union.dedup();
            // A partial shuffle, from a generator that the seed and the table's name fix.
            let mut state = (arguments.seed ^ ShapeList::hash_of_text(&format!("{solver} {identity}"))) | 1;
            for place in 0..arguments.sample.min(union.len()) {
                state ^= state << 13;
                state ^= state >> 7;
                state ^= state << 17;
                let other = place + (state % (union.len() - place) as u64) as usize;
                union.swap(place, other);
            }
            union.truncate(arguments.sample);
            let list = ShapeList::new(union.iter().copied());
            for (at, (family, full, full_seconds)) in fulls.iter().enumerate() {
                let mask = family.shape_mask(&list);
                arclog_encoder::gen_parts::clear_views();
                let mut walker = Walker::new(family);
                let begun = thread_cpu_seconds();
                let got = table_vector_of_shapes(&mut walker, &tables.at[at].1, &grids, examples, false, &mask);
                let list_seconds = thread_cpu_seconds() - begun;
                let (mut listed, mut missing, mut different) = (0usize, 0usize, 0usize);
                for (place, shape) in full.shapes.iter().enumerate() {
                    if !list.contains(*shape) {
                        continue;
                    }
                    listed += 1;
                    match got.shapes.binary_search(shape) {
                        Err(_) => missing += 1,
                        Ok(found) => {
                            let slots_differ = full.at(place).iter().zip(got.at(found)).any(|(a, b)| !same(a, b));
                            if slots_differ || full.meta[place] != got.meta[found] {
                                different += 1;
                            }
                        }
                    }
                }
                let extra = got.shapes.iter().filter(|shape| full.shapes.binary_search(shape).is_err()).count();
                let (walked, roots) = mask.counts();
                let line = serde_json::json!({
                    "task": solver, "table": identity, "assignment": at, "asked": union.len(), "terms": family.counts().0, "walked_terms": walked, "listed_roots": roots,
                    "full_shapes": full.shapes.len(), "listed_in_full": listed, "listed_in_list_walk": got.shapes.len(), "missing": missing, "extra": extra, "different": different,
                    "table_rows_same": full.table_rows == got.table_rows, "full_s": full_seconds, "list_s": list_seconds, "over_full": full.over_budget, "over_list": got.over_budget,
                });
                writeln!(out, "{line}").map_err(|error| error.to_string())?;
            }
            out.flush().map_err(|error| error.to_string())?;
        }
    }
    Ok(())
}

/// A table's vector at each of its assignments, and its `AssignmentVector`, to a file, since the
/// values at a test input read that input. With `--shapes`, the walk covers the terms that the listed shapes need,
/// and the file holds the listed shapes alone.
fn run_vector(arguments: &Arguments, solver: &str, table: &str) -> Result<(), String> {
    use arclog_encoder::generate::{Generators, Walker};
    use arclog_encoder::table_vector::{assignment_vector, table_vector, table_vector_of_shapes, Grids};
    let path = arguments.out.clone().ok_or("`vector` writes to --out")?;
    let list = arguments.shapes.as_ref().map(|path| read_shape_list(path)).transpose()?;
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
        let vector = match &list {
            Some(list) => table_vector_of_shapes(&mut walker, stored, &grids, examples, false, &family.shape_mask(list)),
            None => table_vector(&mut walker, stored, &grids, examples, false),
        };
        vectors.push((stored.content(), vector));
    }
    if list.is_some() {
        eprintln!("{} of {} tables passed the walk's bound on cells", vectors.iter().filter(|(_, vector)| vector.over_budget).count(), vectors.len());
    }
    let names = names_of(&families.names);
    for ((assignment, _), (_, vector)) in tables.at.iter().zip(&vectors) {
        write_vector(&mut out, &serde_json::json!({"name": table, "assignment": format!("{assignment:?}")}), vector, &names)?;
    }
    for (assignment, stored) in &tables.at {
        let Some(wide) = arclog_encoder::table_vector::task_wide_vector(stored, &grids, &families, arguments.wide_size.unwrap_or(arguments.size.max(1)), false) else { continue };
        let names = names_of(&families.names);
        let held: Vec<usize> = (0..wide.shapes.len()).filter(|at| list.as_ref().is_none_or(|list| list.contains(wide.shapes[*at]))).collect();
        writeln!(out, "{}", serde_json::json!({"task_wide": table, "assignment": format!("{assignment:?}"), "entries": held.len()})).map_err(|error| error.to_string())?;
        for at in held {
            let shape = &wide.shapes[at];
            writeln!(out, "{}", serde_json::json!({"shape": names.get(shape), "reads": wide.meta[at].0, "value": slot_json(&wide.slots[at])})).map_err(|error| error.to_string())?;
        }
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

/// Each member's State features, to a file, since the values at a test input read that input.
fn run_state_vectors(arguments: &Arguments, solver: &str) -> Result<(), String> {
    use arclog_encoder::generate::Generators;
    use arclog_encoder::table_vector::Grids;
    let path = arguments.out.clone().ok_or("`state-vectors` writes to --out")?;
    let host = host(arguments, solver)?;
    let (_, grids) = Grids::of_file(&arguments.tasks, solver, None)?;
    let families = Generators::default();
    let members = arclog_encoder::state_features::state_vectors(&host, &grids, &families, arguments.size.max(1))?;
    let names = names_of(&families.names);
    let mut out = arclog_encoder::zio::writer(&path, false)?;
    let pool_lines = |out: &mut dyn Write, key: serde_json::Value, held: &[(u64, f32, f32, f32)]| -> Result<(), String> {
        writeln!(out, "{}", serde_json::json!({"pool": key, "entries": held.len()})).map_err(|error| error.to_string())?;
        for (shape, least, mean, most) in held {
            writeln!(out, "{}", serde_json::json!({"shape": names.get(shape), "least": least, "mean": mean, "most": most})).map_err(|error| error.to_string())?;
        }
        Ok(())
    };
    for member in &members {
        let numbers: serde_json::Map<String, serde_json::Value> = member.numbers.iter().map(|(name, value)| ((*name).to_string(), serde_json::json!(value))).collect();
        writeln!(out, "{}", serde_json::json!({"member": member.name, "assignment": member.assignment, "numbers": numbers})).map_err(|error| error.to_string())?;
        for (other, relation, vector) in &member.edges {
            write_vector(&mut out, &serde_json::json!({"member": member.name, "other": other, "relation": relation}), vector, &names)?;
        }
        for (relation, held) in &member.pools {
            pool_lines(&mut out, serde_json::json!({"member": member.name, "relation": relation}), held)?;
        }
        pool_lines(&mut out, serde_json::json!({"member": member.name, "used_by": true}), &member.used_by)?;
    }
    out.flush().map_err(|error| error.to_string())?;
    eprintln!("{} members", members.len());
    Ok(())
}

/// The base tables' vectors, to a file.
fn run_base_vectors(arguments: &Arguments, solver: &str) -> Result<(), String> {
    use arclog_encoder::generate::Generators;
    use arclog_encoder::table_vector::{base_vectors, pair_vector, Grids};
    let path = arguments.out.clone().ok_or("`base-vectors` writes to --out")?;
    let (_, grids) = Grids::of_file(&arguments.tasks, solver, None)?;
    let families = Generators::default();
    let base = base_vectors(&grids, &families, arguments.size.max(1));
    let pair = pair_vector(&grids, &families, arguments.size.max(1), false);
    let mut out = arclog_encoder::zio::writer(&path, false)?;
    let names = names_of(&families.names);
    write_vector(&mut out, &serde_json::json!({"base": "input"}), &base.input, &names)?;
    write_vector(&mut out, &serde_json::json!({"base": "ex_output"}), &base.ex_output, &names)?;
    write_vector(&mut out, &serde_json::json!({"base": "pair"}), &pair, &names)?;
    out.flush().map_err(|error| error.to_string())
}

/// A task's tables, read as the tables command prints them, which the command's name and the task's stem
/// give. `TABLES_STREAM=1` asks the command for the framed stream. Its output holds test rows, so it reaches
/// this process by a pipe alone, and neither it nor the command's errors are printed or kept.
fn tables_by_command(command: &[String], stem: &str) -> Result<arclog_encoder::table_stream::TablesIn, String> {
    let mut child = std::process::Command::new(&command[0]).args(&command[1..]).arg(stem).env("TABLES_STREAM", "1").stdin(std::process::Stdio::null()).stdout(std::process::Stdio::piped()).stderr(std::process::Stdio::null()).spawn().map_err(|error| error.to_string())?;
    let stdout = child.stdout.take().ok_or("the tables command has no output")?;
    let read = arclog_encoder::table_stream::TablesIn::from_reader(stdout);
    if read.is_err() {
        let _ = child.kill();
    }
    let status = child.wait().map_err(|error| error.to_string())?;
    match read {
        Ok(tables) if status.success() => Ok(tables),
        Ok(_) => Err(format!("the tables command ended with {status}")),
        Err(message) if status.success() => Err(message),
        Err(message) => Err(format!("the tables command ended with {status}: {message}")),
    }
}

/// Each table's stable roots, one file per task, with a task's tables read from a command that
/// prints them or from a file. `--tables-cmd` holds that command, to which the task's name
/// is added. What it prints holds test rows, so it reaches this process by a pipe alone, and
/// neither its output nor its errors are printed or kept. `--names` gives a derangement per task,
/// and then each pair reads another pair's output.
fn run_candidate_lists(arguments: &Arguments, out: &str, sources: &[String]) -> Result<(), String> {
    use arclog_encoder::candidate_lists::{lists_from, ListsOf};
    use arclog_encoder::generate::{Generators, NameStore};
    std::fs::create_dir_all(out).map_err(|error| error.to_string())?;
    let mut families = Generators::default();
    // A run writes a names file of its own, since a stopped run leaves its file with an unfinished end.
    let names_file = format!("{out}/names.tsv.zst");
    let names_file = if std::path::Path::new(&names_file).exists() { format!("{out}/names-{}.tsv.zst", std::process::id()) } else { names_file };
    families.names = NameStore::to_file(&names_file)?;
    let derangements: Option<std::collections::BTreeMap<String, Option<Vec<usize>>>> = match &arguments.names {
        Some(path) => Some(serde_json::from_str(&arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?),
        None => None,
    };
    let command = &arguments.tables_cmd;
    let d = arguments.size.max(1);
    let next =std::sync::atomic::AtomicUsize::new(0);
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
                let tables = match command {
                    Some(parts) => tables_by_command(parts, &stem),
                    None => arclog_encoder::zio::read_text(source).and_then(|text| arclog_encoder::table_stream::TablesIn::from_json(&text)),
                };
                let tables = match tables {
                    Ok(tables) => tables,
                    Err(message) => {
                        eprintln!("{stem}: {message}");
                        continue;
                    }
                };
                let lists_of = if arguments.state_only {
                    ListsOf::State
                } else if arguments.parents_only {
                    ListsOf::Parents
                } else if arguments.wide_only {
                    ListsOf::Wide(arguments.wide_size.unwrap_or(1))
                } else {
                    ListsOf::Tables
                };
                let result = lists_from(&tables, &arguments.tasks, &families, order, d, lists_of, None);
                drop(tables);
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

/// Every kind of list of each task, from one read of its tables: state, wide and per-input, on the true
/// outputs and, by the derangements `--names` gives, on the deranged ones. `--tables-cmd` is required, and holds the
/// command that prints the tables, as for `candidate-lists`. A task's file of each kind is written as it ends, a
/// restart skips the files that exist, and the command runs only for a task that lacks one.
fn run_all_lists(arguments: &Arguments, root: &str, sources: &[String]) -> Result<(), String> {
    use arclog_encoder::candidate_lists::{lists_from, ListsOf};
    use arclog_encoder::generate::{Generators, NameStore};
    let derangements: std::collections::BTreeMap<String, Option<Vec<usize>>> = match &arguments.names {
        Some(path) => serde_json::from_str(&arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?,
        None => Default::default(),
    };
    let command = arguments.tables_cmd.as_ref().ok_or("`all-lists` reads --tables-cmd")?;
    let d = arguments.size.max(1);
    let wide = arguments.wide_size.unwrap_or(1);
    // One family cache per kind. A run writes a names file of its own, since a stopped run leaves its file with an unfinished end.
    let families_of = |folder: &str, term_limit: usize| -> Result<Generators, String> {
        for kind in ["lists", "null"] {
            std::fs::create_dir_all(format!("{root}/{folder}/{kind}")).map_err(|error| error.to_string())?;
        }
        let mut families = Generators::default();
        families.term_limit = term_limit;
        // The `term` lines of the counts print a term's text.
        families.keep_text = arguments.count_bounds;
        if let Some(saved) = &arguments.families {
            let saved = saved.join(format!("{folder}-{d}-{wide}"));
            std::fs::create_dir_all(&saved).map_err(|error| error.to_string())?;
            families.saved = Some(saved);
        }
        families.one_group = folder == "more";
        let names_file = format!("{root}/{folder}/lists/names.tsv.zst");
        let names_file = if std::path::Path::new(&names_file).exists() { format!("{root}/{folder}/lists/names-{}.tsv.zst", std::process::id()) } else { names_file };
        families.names = NameStore::to_file(&names_file)?;
        Ok(families)
    };
    let chosen = |folder: &str| arguments.kinds.as_ref().is_none_or(|kinds| kinds.iter().any(|kind| kind == folder));
    let mut kinds: Vec<(&str, ListsOf, Generators)> = Vec::new();
    for (folder, lists_of, term_limit) in [("state", ListsOf::State, 500_000), ("wide", ListsOf::Wide(wide), 500_000), ("on", ListsOf::Tables, 2_500_000), ("named", ListsOf::Named, 0), ("more", ListsOf::TablesOnly, 2_500_000), ("state_each", ListsOf::StateEach, 500_000)] {
        // These stand only where a run names them.
        if matches!(folder, "more" | "state_each") && arguments.kinds.is_none() {
            continue;
        }
        if chosen(folder) {
            kinds.push((folder, lists_of, families_of(folder, term_limit)?));
        }
    }
    let next = std::sync::atomic::AtomicUsize::new(0);
    let finished = std::sync::atomic::AtomicUsize::new(0);
    let begun = Instant::now();
    let lacks = |stem: &str| -> bool {
        let wanted = |folder: &str, kind: &str| !std::path::Path::new(&format!("{root}/{folder}/{kind}/{stem}.lists.zst")).exists();
        let deranged = derangements.get(stem).and_then(Option::as_ref).is_some();
        kinds.iter().any(|(folder, _, _)| wanted(folder, "lists") || (deranged && wanted(folder, "null")))
    };
    let to_write = sources.iter().filter(|source| lacks(&arclog_encoder::zio::stem(source))).count();
    std::thread::scope(|scope| {
        for _ in 0..arguments.threads.max(1) {
            scope.spawn(|| loop {
                let at = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let Some(source) = sources.get(at) else { break };
                let stem = arclog_encoder::zio::stem(source);
                let order: Option<&[usize]> = derangements.get(&stem).and_then(Option::as_ref).map(Vec::as_slice);
                let target = |folder: &str, kind: &str| format!("{root}/{folder}/{kind}/{stem}.lists.zst");
                let wanted = |folder: &str, kind: &str| !std::path::Path::new(&target(folder, kind)).exists();
                if !lacks(&stem) {
                    continue;
                }
                let started = Instant::now();
                let tables = match tables_by_command(command, &stem) {
                    Ok(tables) => tables,
                    Err(message) => {
                        eprintln!("{stem}: {message}");
                        continue;
                    }
                };
                let tables_seconds = started.elapsed().as_secs_f64();
                let mut walks = 0;
                let mut left_out = 0;
                for (folder, lists_of, families) in &kinds {
                    for (kind, own_order) in [("lists", None), ("null", order)] {
                        if !wanted(folder, kind) || (kind == "null" && own_order.is_none()) {
                            continue;
                        }
                        match lists_from(&tables, &arguments.tasks, families, own_order, d, *lists_of, Some(std::path::Path::new(&target(folder, kind)))) {
                            Ok(found) => {
                                walks += found.walks;
                                left_out = left_out.max(found.left_out);
                                families.names.flush();
                            }
                            Err(message) => eprintln!("{stem}: {folder} {kind}: {message}"),
                        }
                    }
                }
                let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                let rate = done as f64 / begun.elapsed().as_secs_f64();
                let counts = if arclog_encoder::bounds::enabled() { ", bound counts on" } else { "" };
                eprintln!("{done}/{to_write} {stem}: {tables_seconds:.1} s of tables, {walks} walks, {left_out} items left out, {:.0} s; ETA {:.0}s{counts}", started.elapsed().as_secs_f64(), to_write.saturating_sub(done) as f64 / rate);
            });
        }
    });
    for (_, _, families) in &kinds {
        families.names.flush();
    }
    if arclog_encoder::bounds::enabled() {
        eprint!("{}", arclog_encoder::bounds::summary());
    }
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
    // The walk matches the pattern against a term's text.
    let families = Generators::keeping_text();
    let empty = Vec::new();
    for item in data["items"].as_array().unwrap_or(&empty) {
        let Some(stored) = Stored::of_json(&item["gold"], train, 0) else { continue };
        if stored.types.len() > arclog_encoder::generate::MAX_TABLE_COLUMNS {
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

/// The `shapes` records of a task's tables from their stored rows: `shapes-refresh ROWS_FILE TASK OUT [--shapes FILE] [--threads N] [--families DIR]`. ROWS_FILE holds a line `{"hash": HEX, "table": T}` for each table, with `T` as `stored_of`
/// reads it. With `--shapes`, the records hold the listed shapes alone, in the file's order. With `--families`, a family that the run builds is saved under DIR, and a later run of the same binary reads it. It prints a line of counts.
fn run_shapes_refresh(arguments: &Arguments, rows: &str, task: &str, out: &str) -> Result<(), String> {
    let only = match &arguments.shapes {
        Some(path) => Some(read_shape_hashes(path)?),
        None => None,
    };
    let mut families = arclog_encoder::generate::Generators::default();
    // The `term` lines of the counts print a term's text.
    families.keep_text = arguments.count_bounds;
    if let Some(folder) = &arguments.families {
        // A family's file name holds no size, so the folder does. The records hold no root names, so the names stay in memory and a family read from a file adds none.
        let saved = folder.join(format!("shapes-refresh-{}", arclog_encoder::shapes_refresh::SIZE));
        std::fs::create_dir_all(&saved).map_err(|error| format!("{}: {error}", saved.display()))?;
        families.saved = Some(saved);
        families.saved_limit = arclog_encoder::generate::CACHED_TERMS;
    }
    let summary = arclog_encoder::shapes_refresh::run(std::path::Path::new(rows), std::path::Path::new(out), &arguments.tasks, task, only.as_deref(), arguments.threads, &families, arguments.headerless)?;
    let counts = if arclog_encoder::bounds::enabled() { "; bound counts on" } else { "" };
    eprintln!("{summary}{counts}");
    if arclog_encoder::bounds::enabled() {
        eprint!("{}", arclog_encoder::bounds::summary());
    }
    Ok(())
}

/// Each table of each tables file, walked: its active entries, and the distinct shapes over the tables so far,
/// a line per file. A family's roots count once per schema.
fn run_shape_count(arguments: &Arguments, files: &[String]) -> Result<(), String> {
    use arclog_encoder::generate::{leaves_at, Generators, Walker};
    use arclog_encoder::stored::Stored;
    use arclog_encoder::table_vector::Grids;
    use std::collections::BTreeSet;
    let families = Generators::default();
    let empty = Vec::new();
    let mut shapes: BTreeSet<u64> = BTreeSet::new();
    let mut schemas: BTreeSet<String> = BTreeSet::new();
    let (mut roots, mut tables, mut entries, mut values) = (0u64, 0u64, 0u64, 0u64);
    for file in files {
        let data: serde_json::Value = serde_json::from_str(&arclog_encoder::zio::read_text(file)?).map_err(|error| error.to_string())?;
        let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
        let train = data["train"].as_u64().ok_or("a file's train")? as usize;
        let (_, grids) = Grids::of_file(&arguments.tasks, &task_name, None)?;
        let mut seen: BTreeSet<u128> = BTreeSet::new();
        for item in data["items"].as_array().unwrap_or(&empty) {
            let Some(stored) = Stored::of_json(&item["gold"], train, 0) else { continue };
            if stored.types.is_empty() || stored.types.len() > arclog_encoder::generate::MAX_TABLE_COLUMNS || !seen.insert(stored.content()) || stored.rows.iter().take(train).any(|models| models.len() != 1) {
                continue;
            }
            let family = families.get(&stored, arguments.size.max(1));
            if schemas.insert(stored.key.clone()) {
                roots += family.roots as u64;
            }
            let mut walker = Walker::new(&family);
            let example_of: Vec<usize> = (0..train).collect();
            let held: Vec<_> = stored.rows.iter().take(train).map(|models| models.first().cloned()).collect();
            let leaves = leaves_at(&held, &example_of, &grids.inputs, &grids.outputs, &grids.constants);
            let found = walker.walk(&leaves, train, false);
            tables += 1;
            for (hash, at) in found.sorted_roots() {
                let at = at * found.stride;
                let live = found.slots[at..at + found.stride].iter().filter(|slot| slot.state != arclog_encoder::generate::SlotState::Default).count() as u64;
                if live > 0 {
                    entries += 1;
                    values += live;
                    shapes.insert(hash as u64);
                }
            }
        }
        println!("{task_name}\ttables {tables}\tschemas {}\troots over the schemas {roots}\tentries {entries}\tvalues {values}\tdistinct active shapes {}", schemas.len(), shapes.len());
    }
    Ok(())
}

/// The name of each root of a family at the column types `types`.
fn run_family_names(arguments: &Arguments, types: &str) -> Result<(), String> {
    use arclog_encoder::generate::{Generated, NameStore};
    let types: Vec<arclog::types::ValueType> = types.split(',').filter(|name| *name != "grids").map(|name| arclog_encoder::schema::type_of_name(name).ok_or_else(|| format!("no type {name}"))).collect::<Result<_, _>>()?;
    let store = NameStore::default();
    let _family = if types.is_empty() { Generated::of_grids(arguments.size.max(1), &store, false) } else { Generated::of(&types, arguments.size.max(1), &store, false) };
    for (_, name) in store.all() {
        println!("{name}");
    }
    Ok(())
}

/// A family's terms and roots at the column types `types`, by the heads of a term and of its first relation.
fn run_term_stats(arguments: &Arguments, types: &str) -> Result<(), String> {
    use arclog_encoder::generate::{Generated, NameStore};
    use std::collections::BTreeMap;
    let types: Vec<arclog::types::ValueType> = types.split(',').map(|name| arclog_encoder::schema::type_of_name(name).ok_or_else(|| format!("no type {name}"))).collect::<Result<_, _>>()?;
    let family = Generated::of(&types, arguments.size.max(1), &NameStore::default(), true);
    let (count, first) = family.counts();
    println!("terms {} leaves {} roots {} by size {:?}", count - first, first, family.roots, family.by_size);
    for (rule, count) in &family.rejected_by_rule {
        println!("rejected\t{count}\t{rule}");
    }
    let mut by: BTreeMap<(String, String), (u64, u64)> = BTreeMap::new();
    for at in first..count {
        let (text, _, _) = family.term_info(at);
        if text.is_empty() {
            return Err("a family in `term-stats` has no terms' text".to_string());
        }
        let mut words = text.split(' ');
        let head = words.next().unwrap_or("").trim_start_matches('(').to_string();
        let inner = words.next().unwrap_or("").trim_start_matches('(').trim_end_matches(')').to_string();
        let inner = if arclog_encoder::gen_constants::is_part_name(&inner) { "part".to_string() } else { inner };
        let entry = by.entry((head, inner)).or_default();
        entry.0 += 1;
        entry.1 += family.term_roots(at) as u64;
    }
    let mut rows: Vec<_> = by.into_iter().collect();
    rows.sort_by_key(|(_, (terms, _))| std::cmp::Reverse(*terms));
    for ((head, inner), (terms, roots)) in rows.iter().take(60) {
        println!("{terms}\t{roots}\t{head}\t{inner}");
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
    let done: LookupSet<String> = arclog_encoder::zio::read_text(&path).unwrap_or_default().lines().filter_map(|line| {
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

/// The lists of tables that a caller sends by pipe, so no table's rows stand in a file: each line of stdin is what the
/// tables command of `candidate-lists` prints, and each answer on stdout is its length as 8 bytes, then the lists as that
/// command's file holds them. An answer of length 0 is a fault, written to stderr.
fn run_serve_lists(arguments: &Arguments) -> Result<(), String> {
    use arclog_encoder::candidate_lists::{lists_task, ListsOf};
    use arclog_encoder::generate::Generators;
    use std::io::{BufRead, Write};
    let mut families = Generators::default();
    if let Some(saved) = &arguments.families {
        let saved = saved.join(format!("on-{}-serve", arguments.size.max(1)));
        std::fs::create_dir_all(&saved).map_err(|error| error.to_string())?;
        families.saved = Some(saved);
    }
    let stdin = std::io::stdin();
    let mut out = std::io::stdout().lock();
    for line in stdin.lock().lines() {
        let line = line.map_err(|error| error.to_string())?;
        let bytes = match lists_task(&line, &arguments.tasks, &families, None, arguments.size.max(1), ListsOf::Tables) {
            Ok(found) => found.bytes,
            Err(message) => {
                eprintln!("{message}");
                Vec::new()
            }
        };
        out.write_all(&(bytes.len() as u64).to_le_bytes()).map_err(|error| error.to_string())?;
        out.write_all(&bytes).map_err(|error| error.to_string())?;
        out.flush().map_err(|error| error.to_string())?;
    }
    Ok(())
}

/// The lines of a file of an earlier run that a restart reads, or none where the file does not stand.
fn earlier_lines(path: &std::path::Path) -> Vec<serde_json::Value> {
    arclog_encoder::zio::read_text(path).map(|text| text.lines().filter_map(|line| serde_json::from_str(line).ok()).collect()).unwrap_or_default()
}

/// For each table of each solver, one full walk at each assignment, and the terms that a bound stopped, with the bound.
/// A line holds shape texts and bound names, and no value. The run counts the bounds and keeps the text of every term, which it needs to name the shapes.
/// The first line of the file, `{"header": true, "count_bounds": true}`, records that the counts were on.
/// A line `{"task", "table", "start"}` comes before a table's walks and `{"task", "table", "done"}` after them, so that a restart
/// skips the tables that are done and those that a stopped run began and did not finish.
fn run_cap_hits(arguments: &Arguments, solvers: &[String]) -> Result<(), String> {
    use arclog_encoder::generate::{Generators, Walker};
    use arclog_encoder::table_vector::{table_vector, Grids};
    arclog_encoder::bounds::enable();
    let path = arguments.out.clone().ok_or("`cap-hits` writes to --out")?;
    let shapes = arguments.shapes.as_ref().map(|path| read_shape_list(path)).transpose()?;
    let earlier = earlier_lines(&path);
    let started: LookupSet<(String, String)> = earlier.iter().filter(|line| line.get("start").is_some()).map(|line| (line["task"].as_str().unwrap_or("").to_string(), line["table"].as_str().unwrap_or("").to_string())).collect();
    let task_done: LookupSet<String> = earlier.iter().filter(|line| line.get("task_done").is_some()).map(|line| line["task"].as_str().unwrap_or("").to_string()).collect();
    let mut out = arclog_encoder::zio::writer(&path, true)?;
    writeln!(out, "{}", serde_json::json!({"header": true, "count_bounds": true})).map_err(|error| error.to_string())?;
    let size = arguments.size.max(1);
    let walk_bit = arclog_encoder::bounds::bit_of(arclog_encoder::bounds::Bound::Walk);
    for solver in solvers {
        if task_done.contains(solver) {
            continue;
        }
        let prepared = host(arguments, solver).and_then(|host| Grids::of_file(&arguments.tasks, solver, None).map(|(_, grids)| (host, grids)));
        let (host, grids) = match prepared {
            Ok(held) => held,
            Err(message) => {
                writeln!(out, "{}", serde_json::json!({"task": solver, "task_done": true, "error": message})).map_err(|error| error.to_string())?;
                continue;
            }
        };
        let examples = grids.inputs.len();
        let families = Generators::keeping_text();
        let mut skipped = 0usize;
        for (identity, spelled) in host.program_facts().table_names.iter().take(arguments.max_tables) {
            if started.contains(&(solver.clone(), identity.clone())) {
                skipped += 1;
                continue;
            }
            writeln!(out, "{}", serde_json::json!({"task": solver, "table": identity, "start": true})).map_err(|error| error.to_string())?;
            out.flush().map_err(|error| error.to_string())?;
            let Ok(tables) = arclog_encoder::run::stored_tables(&host, spelled) else {
                writeln!(out, "{}", serde_json::json!({"task": solver, "table": identity, "done": 0, "error": "no table"})).map_err(|error| error.to_string())?;
                continue;
            };
            for (at, (_, stored)) in tables.at.iter().enumerate() {
                let family = families.get(stored, size);
                arclog_encoder::gen_parts::clear_views();
                let begun = thread_cpu_seconds();
                let mut walker = Walker::new(&family);
                let vector = table_vector(&mut walker, stored, &grids, examples, false);
                let seconds = thread_cpu_seconds() - begun;
                let (hits, cells) = arclog_encoder::bounds::take_term_hits();
                let shape = |term: u32| family.term_shape(term as usize, &stored.types).unwrap_or_default();
                let listed: Vec<serde_json::Value> = hits.iter().filter(|(_, bits)| bits & !walk_bit != 0).map(|(term, bits)| serde_json::json!([shape(*term), arclog_encoder::bounds::names_of_bits(bits & !walk_bit)])).collect();
                let walk_skipped: Vec<u32> = hits.iter().filter(|(_, bits)| bits & walk_bit != 0).map(|(term, _)| *term).collect();
                let mut top: Vec<(u32, u64)> = cells;
                top.sort_by_key(|(_, count)| std::cmp::Reverse(*count));
                top.truncate(12);
                let top: Vec<serde_json::Value> = top.iter().map(|(term, count)| serde_json::json!([shape(*term), count])).collect();
                let types: Vec<String> = stored.types.iter().map(|ty| format!("{:?}", ty.without_source())).collect();
                // With --shapes: each listed shape that the vector holds, with the examples where it has a value, the examples where a bound stopped it, and the distinct values.
                let mut listed_shapes: Vec<serde_json::Value> = Vec::new();
                if let Some(list) = &shapes {
                    let mut names: Option<LookupMap<u64, String>> = None;
                    for (place, hash) in vector.shapes.iter().enumerate() {
                        if !list.contains(*hash) {
                            continue;
                        }
                        let slots = vector.at(place);
                        let valued = slots.iter().filter(|slot| slot.state == arclog_encoder::generate::SlotState::Value).count();
                        let stopped = slots.iter().filter(|slot| slot.state == arclog_encoder::generate::SlotState::NoValue).count();
                        if valued == 0 && stopped == 0 {
                            continue;
                        }
                        let distinct = slots.iter().filter(|slot| slot.state == arclog_encoder::generate::SlotState::Value).map(|slot| slot.digest).collect::<LookupSet<_>>().len();
                        let names = names.get_or_insert_with(|| names_of(&families.names));
                        listed_shapes.push(serde_json::json!([names.get(hash), valued, stopped, distinct, vector.scope(place)]));
                    }
                }
                let line = serde_json::json!({
                    "task": solver, "table": identity, "assignment": at, "types": types, "keys": stored.keys, "terms": family.counts().0, "seconds": seconds,
                    "over_budget": vector.over_budget, "table_rows_max": vector.table_rows.1, "hits": listed,
                    "walk_skipped": walk_skipped.len(), "first_walk_skip": walk_skipped.first().map(|term| shape(*term)), "cells": top,
                    "listed_shapes": listed_shapes,
                });
                writeln!(out, "{line}").map_err(|error| error.to_string())?;
                out.flush().map_err(|error| error.to_string())?;
            }
            writeln!(out, "{}", serde_json::json!({"task": solver, "table": identity, "done": tables.at.len(), "capped": tables.capped})).map_err(|error| error.to_string())?;
            out.flush().map_err(|error| error.to_string())?;
        }
        writeln!(out, "{}", serde_json::json!({"task": solver, "task_done": true, "skipped_tables": skipped})).map_err(|error| error.to_string())?;
        out.flush().map_err(|error| error.to_string())?;
    }
    // The summary lists, per head, the cells and the seconds of the writes of `inside` cells.
    eprint!("{}", arclog_encoder::bounds::summary());
    Ok(())
}

fn main() {
    let arguments = arguments();
    let command = arguments.positional.first().map(String::as_str).unwrap_or_default();
    if arguments.count_bounds {
        if !matches!(command, "all-lists" | "shapes-refresh" | "cap-hits") {
            eprintln!("`--count-bounds` belongs to `all-lists`, `shapes-refresh` and `cap-hits`");
            std::process::exit(1);
        }
        arclog_encoder::bounds::enable();
    }
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
        ("shape-check", solvers) if !solvers.is_empty() => run_shape_check(&arguments, solvers),
        ("cap-hits", solvers) if !solvers.is_empty() => run_cap_hits(&arguments, solvers),
        ("base-vectors", [solver]) => run_base_vectors(&arguments, solver),
        ("query-vectors", [solver]) => run_query_vectors(&arguments, solver),
        ("state-vectors", [solver]) => run_state_vectors(&arguments, solver),
        ("candidate-lists", [out, sources @ ..]) if !sources.is_empty() => run_candidate_lists(&arguments, out, sources),
        ("serve-lists", []) => run_serve_lists(&arguments),
        ("all-lists", [root, sources @ ..]) if !sources.is_empty() => run_all_lists(&arguments, root, sources),
        ("term-counts", [pattern, file]) => run_term_counts(&arguments, pattern, file),
        ("term-stats", [types]) => run_term_stats(&arguments, types),
        ("family-names", [types]) => run_family_names(&arguments, types),
        ("refine-explain", [call, arity, key]) => {
            println!("{}", arclog_encoder::refine_parts::explain(call, arity.parse().unwrap_or(1), arclog_encoder::refine::Mask::from_str_radix(key, 2).unwrap_or(0)));
            Ok(())
        }
        ("shape-count", files) if !files.is_empty() => run_shape_count(&arguments, files),
        ("shapes-refresh", [rows, task, out]) => run_shapes_refresh(&arguments, rows, task, out),
        ("engine", []) => {
            println!("{}", arclog_encoder::shapes_refresh::producers());
            Ok(())
        }
        ("count", [solver, tables @ ..]) if !tables.is_empty() => run_count(&arguments, solver, tables),
        ("grid-values", [grids]) => run_grid_values(&arguments, grids),
        ("grid-vectors", [grids]) => run_grid_vectors(&arguments, grids),
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
