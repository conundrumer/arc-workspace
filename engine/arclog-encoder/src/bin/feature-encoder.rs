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
//!   feature-encoder walk MANIFEST (--scene | --rule) [--size D] [--threads N] [--seconds S] [--passes P] [--shard I/N] [--max-columns K]
//!   feature-encoder walk-check GRIDS_JSON (--scene | --rule) [--size D] [--rate R]
//!   feature-encoder candidate OUT_DIR FILE... [--size D] [--rate R] [--passes NULLS] [--threads N] [--max-columns K] [--relational] [--rule]
//!   feature-encoder family OUT_DIR FILE... [--size D] [--passes NULLS] [--threads N] [--rule] [--names SHAPES_FILE]
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

fn run_vector(arguments: &Arguments, solver: &str, table: &str) -> Result<(), String> {
    let holes = vec![TABLE_HOLE.to_string()];
    let host = host(arguments, solver)?;
    host.set_work_cap(arguments.work_cap);
    let found = match &arguments.names {
        Some(path) => {
            let text = arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?;
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
        Some(path) => arclog_encoder::zio::writer(path, false)?,
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

/// Writes a walk's words, sizes and counts under `prefix`, each file whole.
fn write_walk(prefix: &str, size: usize, result: &arclog_encoder::walk::WalkResult) -> Result<(), String> {
    let put = |suffix: &str, bytes: &[u8]| -> Result<(), String> {
        arclog_encoder::zio::write_bytes(format!("{prefix}.d{size}.{suffix}.zst"), bytes)
    };
    let mut bytes = Vec::with_capacity(result.words.len() * 8);
    for word in &result.words {
        bytes.extend_from_slice(&word.to_le_bytes());
    }
    put("words", &bytes)?;
    put("sizes", &result.sizes)?;
    let mut order = Vec::with_capacity(result.order.len() * 4);
    for at in &result.order {
        order.extend_from_slice(&at.to_le_bytes());
    }
    put("order", &order)?;
    let mut by_name: std::collections::BTreeMap<&str, (u64, f64)> = Default::default();
    for (name, runs, seconds) in &result.shape_time {
        let held = by_name.entry(name.as_str()).or_default();
        held.0 += runs;
        held.1 += seconds;
    }
    let meta = serde_json::json!({
        "grids": result.grids, "roots": result.sizes.len(), "classes_by_size": result.classes_by_size, "edges": result.edges,
        "evaluations": result.evaluations, "component_runs": result.component_runs, "seconds": result.seconds, "timed_out": result.timed_out,
        "top_edges": result.top_edges, "top_done": result.top_done, "tier_edges": result.tier_edges,
        "lower_seconds": result.lower_seconds, "counted": result.counted, "built": result.built,
        "tiers": arclog_encoder::optable::TIER_NAMES, "component_seconds": by_name.iter().map(|(name, (runs, seconds))| (name.to_string(), serde_json::json!([runs, seconds]))).collect::<serde_json::Map<String, serde_json::Value>>(),
    });
    put("json", meta.to_string().as_bytes())
}

/// What an earlier slice of a walk wrote under `prefix`.
fn read_slice(prefix: &str, size: usize) -> arclog_encoder::walk::Resume {
    let mut resume = arclog_encoder::walk::Resume::default();
    let Ok(meta) = arclog_encoder::zio::read_text(format!("{prefix}.d{size}.json")) else { return resume };
    let Ok(meta) = serde_json::from_str::<serde_json::Value>(&meta) else { return resume };
    let (Ok(words), Ok(sizes)) = (arclog_encoder::zio::read_bytes(format!("{prefix}.d{size}.words")), arclog_encoder::zio::read_bytes(format!("{prefix}.d{size}.sizes"))) else { return resume };
    resume.words = words.chunks_exact(8).map(|chunk| u64::from_le_bytes(chunk.try_into().expect("eight bytes"))).collect();
    resume.sizes = sizes;
    resume.order = arclog_encoder::zio::read_bytes(format!("{prefix}.d{size}.order")).unwrap_or_default().chunks_exact(4).map(|chunk| u32::from_le_bytes(chunk.try_into().expect("four bytes"))).collect();
    resume.top_done = meta["top_done"].as_u64().unwrap_or(0);
    resume
}

/// Whether an earlier slice of a walk reached its end.
fn slice_ended(prefix: &str, size: usize) -> bool {
    arclog_encoder::zio::read_text(format!("{prefix}.d{size}.json")).ok().and_then(|text| serde_json::from_str::<serde_json::Value>(&text).ok()).is_some_and(|meta| meta["top_edges"].as_u64().is_some() && meta["top_done"] == meta["top_edges"])
}

fn run_walk(arguments: &Arguments, manifest: &str) -> Result<(), String> {
    use arclog_encoder::optable::{build, Mode};
    use arclog_encoder::walk::walk;
    let size = arguments.size;
    let rule = arguments.rule;
    let all: Vec<(String, String, String)> = arclog_encoder::zio::read_text(manifest)
        .map_err(|error| error.to_string())?
        .lines()
        .filter_map(|line| {
            let mut parts = line.split('\t');
            Some((parts.next()?.to_string(), parts.next()?.to_string(), parts.next()?.to_string()))
        })
        .collect();
    let start = Instant::now();
    let host = scratch_host()?;
    let table = build(&host, if rule { Mode::Rule } else { Mode::Scene }, size, false, arguments.max_columns)?;
    drop(host);
    eprintln!("op table: {} entries, {} schemas, {} shapes, {} instances, {} refused, {} with no native form, {:.1}s", table.entries.len(), table.schemas.len(), table.shapes.len(), table.instances.len(), table.refused, table.no_native.len(), start.elapsed().as_secs_f64());
    for line in table.no_native.iter().take(20) {
        eprintln!("no native form: {}", line.chars().take(300).collect::<String>());
    }
    let threads = arguments.threads.max(1);
    let seconds = arguments.seconds;
    let (shard, shards) = arguments.shard;
    // Each pass gives every task a slice, and the next pass adds to each one that
    // has not ended.
    for pass in 0..arguments.passes {
        let lines: Vec<&(String, String, String)> = all.iter().enumerate().filter(|(at, _)| at % shards == shard).map(|(_, line)| line).filter(|(_, _, prefix)| !slice_ended(prefix, size)).collect();
        eprintln!("pass {pass}: {} tasks to walk", lines.len());
        if lines.is_empty() {
            break;
        }
        let next = std::sync::atomic::AtomicUsize::new(0);
        let finished = std::sync::atomic::AtomicUsize::new(0);
        let begun = Instant::now();
        std::thread::scope(|scope| {
            for _ in 0..threads {
                scope.spawn(|| loop {
                    let at = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                    let Some((task, grids, prefix)) = lines.get(at).copied() else { break };
                    let outcome = arclog_encoder::zio::read_text(grids).map_err(|error| error.to_string()).and_then(|text| grids_task(&text, rule));
                    let task_value = match outcome {
                        Ok(task_value) => task_value,
                        Err(message) => {
                            eprintln!("{task}: {message}");
                            continue;
                        }
                    };
                    let slice = (seconds > 0.0).then_some(seconds);
                    let (result, _) = walk(&table, &task_value, size, slice, None, read_slice(prefix, size));
                    if let Err(message) = write_walk(prefix, size, &result) {
                        eprintln!("{task}: {message}");
                    }
                    let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                    let rate = done as f64 / begun.elapsed().as_secs_f64();
                    eprintln!("pass {pass} {done}/{} {task}: {} grids, {} root classes, relation classes {:?}, top operators {}/{}, {} counted, {} built, {} component runs, {:.1}s below the top, {:.1}s; ETA {:.0}s", lines.len(), result.grids, result.sizes.len(), result.classes_by_size, result.top_done, result.top_edges, result.counted, result.built, result.component_runs, result.lower_seconds, result.seconds, (lines.len() - done) as f64 / rate);
                });
            }
        });
    }
    Ok(())
}

/// Each task's stable generated shapes, one folder per size, under `OUT-d1`, `OUT-d2`; each new
/// shape's text goes to `OUT-names.tsv` beside them.
fn run_generate_dump(arguments: &Arguments, out: &str, files: &[String]) -> Result<(), String> {
    use arclog_encoder::generate::{dump_task, Generators};
    let mut families = Generators::default();
    families.names = arclog_encoder::generate::NameStore::to_file(&format!("{out}-names-all.tsv.zst"))?;
    let path = arguments.names.clone().ok_or("`generate-dump` reads the derangements from --names")?;
    let derangements: std::collections::BTreeMap<String, Option<Vec<usize>>> = serde_json::from_str(&arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let d = arguments.size.max(1);
    for size in 1..=d {
        std::fs::create_dir_all(format!("{out}-d{size}")).map_err(|error| error.to_string())?;
    }
    let next = std::sync::atomic::AtomicUsize::new(0);
    let finished = std::sync::atomic::AtomicUsize::new(0);
    let totals = std::sync::Mutex::new((0u64, 0f64));
    let begun = Instant::now();
    std::thread::scope(|scope| {
        for _ in 0..arguments.threads.max(1) {
            scope.spawn(|| loop {
                let at = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let Some(file) = files.get(at) else { break };
                let stem = arclog_encoder::zio::stem(file);
                if std::path::Path::new(&format!("{out}-d{d}/{stem}.json.zst")).exists() {
                    continue;
                }
                match dump_task(file, &arguments.tasks, &families, &derangements, d) {
                    Ok((name, results, walks, seconds)) => {
                        for (size, result) in results.iter().enumerate() {
                            let target = format!("{out}-d{}/{name}.json.zst", size + 1);
                            if arclog_encoder::zio::write_text(&target, &result.to_string()).is_err() {
                                eprintln!("{stem}: the result does not write");
                            }
                        }
                        families.names.flush();
                        let mut held = totals.lock().expect("no panic");
                        held.0 += walks;
                        held.1 += seconds;
                        let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                        let rate = done as f64 / begun.elapsed().as_secs_f64();
                        eprintln!("{done}/{} {stem}: {:.0} ms per walk so far; ETA {:.0}s", files.len(), held.1 * 1e3 / held.0.max(1) as f64, (files.len() - done) as f64 / rate);
                    }
                    Err(message) => eprintln!("{stem}: {message}"),
                }
            });
        }
    });
    Ok(())
}

/// Which written kinds the generated shapes reach, by value.
fn run_generate_reach(arguments: &Arguments, out: &str, files: &[String]) -> Result<(), String> {
    let mut sink = arclog_encoder::zio::writer(out, false)?;
    arclog_encoder::generate::reach(files, &arguments.tasks, arguments.size, arguments.passes.max(1), &mut sink)?;
    sink.flush().map_err(|error| error.to_string())
}

/// Candidate's line on the generated shapes, one result per file, and the seconds per walk.
fn run_generate(arguments: &Arguments, out: &str, files: &[String]) -> Result<(), String> {
    use arclog_encoder::generate::{generate_task, Generators};
    use arclog_encoder::native::hash_words;
    std::fs::create_dir_all(out).map_err(|error| error.to_string())?;
    let mut families = Generators::default();
    if let Ok(path) = std::env::var("GENERATE_CLASSES") {
        families.extend = serde_json::from_str(&arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    }
    let allow: Option<HashSet<u128>> = match &arguments.names {
        Some(path) => Some(arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?.lines().map(|line| hash_words(line.bytes().map(u64::from))).collect()),
        None => None,
    };
    let next = std::sync::atomic::AtomicUsize::new(0);
    let finished = std::sync::atomic::AtomicUsize::new(0);
    let totals = std::sync::Mutex::new((0u64, 0f64));
    let begun = Instant::now();
    std::thread::scope(|scope| {
        for _ in 0..arguments.threads.max(1) {
            scope.spawn(|| loop {
                let at = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let Some(file) = files.get(at) else { break };
                let stem = arclog_encoder::zio::stem(file);
                let target = format!("{out}/{stem}.d{}.json.zst", arguments.size);
                if std::path::Path::new(&target).exists() {
                    continue;
                }
                match generate_task(file, &arguments.tasks, &families, arguments.size, arguments.passes, allow.as_ref(), 8) {
                    Ok(result) => {
                        if arclog_encoder::zio::write_text(&target, &result.to_string()).is_err() {
                            eprintln!("{stem}: the result does not write");
                        }
                        let mut held = totals.lock().expect("no panic");
                        held.0 += result["walks"].as_u64().unwrap_or(0);
                        held.1 += result["walk_seconds"].as_f64().unwrap_or(0.0);
                        let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                        let rate = done as f64 / begun.elapsed().as_secs_f64();
                        eprintln!("{done}/{} {stem}: {:.0} ms per walk so far; ETA {:.0}s", files.len(), held.1 * 1e3 / held.0.max(1) as f64, (files.len() - done) as f64 / rate);
                    }
                    Err(message) => eprintln!("{stem}: {message}"),
                }
            });
        }
    });
    Ok(())
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

/// Candidate's stable templates per task, on the catalog's values.
fn run_catalog_dump(arguments: &Arguments, out: &str, files: &[String]) -> Result<(), String> {
    use arclog_encoder::catalog_run::{dump_task, Form};
    std::fs::create_dir_all(out).map_err(|error| error.to_string())?;
    let form = if arguments.rule { Form::All } else { Form::Ratio };
    let path = arguments.names.clone().ok_or("`catalog-dump` reads the derangements from --names")?;
    let orders: std::collections::BTreeMap<String, Option<Vec<usize>>> = serde_json::from_str(&arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let next = std::sync::atomic::AtomicUsize::new(0);
    let finished = std::sync::atomic::AtomicUsize::new(0);
    let totals = std::sync::Mutex::new((0u64, 0f64, 0f64));
    let begun = Instant::now();
    std::thread::scope(|scope| {
        for _ in 0..arguments.threads.max(1) {
            scope.spawn(|| loop {
                let at = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let Some(file) = files.get(at) else { break };
                let stem = arclog_encoder::zio::stem(file);
                let target = format!("{out}/{stem}.json.zst");
                if std::path::Path::new(&target).exists() {
                    continue;
                }
                match dump_task(file, &arguments.tasks, &orders, form) {
                    Ok((result, spent, facts)) => {
                        if arclog_encoder::zio::write_text(&target, &result.to_string()).is_err() {
                            eprintln!("{stem}: the result does not write");
                        }
                        let mut held = totals.lock().expect("no panic");
                        held.0 += spent.0;
                        held.1 += spent.1.as_secs_f64();
                        held.2 += facts.as_secs_f64();
                        let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                        let rate = done as f64 / begun.elapsed().as_secs_f64();
                        eprintln!("{done}/{} {stem}: {:.1} us per table at a pair so far; ETA {:.0}s", files.len(), held.1 * 1e6 / held.0.max(1) as f64, (files.len() - done) as f64 / rate);
                    }
                    Err(message) => eprintln!("{stem}: {message}"),
                }
            });
        }
    });
    Ok(())
}

/// The value of relation terms on a stored table, through the engine. Each request
/// is a line with `task`, `types`, `rows` by `train/i`, and `terms`, whose table is
/// `&t`, with columns `T0`, `T1`. Each result line gives a term's size, why the
/// checker refuses it, and at each example its count of rows and its first cell.
fn run_stored_eval(arguments: &Arguments, requests: &str) -> Result<(), String> {
    use arclog_encoder::expression::Reader;
    use arclog_encoder::run::StoredRows;
    use arclog_encoder::schema::{type_of_name, TableColumn};
    use arclog_encoder::tablewalk::cell_bits;
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

/// Candidate recognition on the relational shapes: one result per file, as each ends,
/// and a restart skips those written. `--names` limits it to the shapes a file lists,
/// one per line.
fn run_family(arguments: &Arguments, out: &str, files: &[String]) -> Result<(), String> {
    use arclog_encoder::family::{family_task, Families};
    use arclog_encoder::native::hash_words;
    use arclog_encoder::tablewalk::StableRule;
    std::fs::create_dir_all(out).map_err(|error| error.to_string())?;
    let families = Families::default();
    let rule = if arguments.rule { StableRule::NonVacuous } else { StableRule::Active };
    let allow: Option<HashSet<u128>> = match &arguments.names {
        Some(path) => Some(arclog_encoder::zio::read_text(path).map_err(|error| error.to_string())?.lines().map(|line| hash_words(line.bytes().map(u64::from))).collect()),
        None => None,
    };
    let next = std::sync::atomic::AtomicUsize::new(0);
    let finished = std::sync::atomic::AtomicUsize::new(0);
    let begun = Instant::now();
    std::thread::scope(|scope| {
        for _ in 0..arguments.threads.max(1) {
            scope.spawn(|| loop {
                let at = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let Some(file) = files.get(at) else { break };
                let stem = arclog_encoder::zio::stem(file);
                let target = format!("{out}/{stem}.d{}.json.zst", arguments.size);
                if std::path::Path::new(&target).exists() {
                    continue;
                }
                match family_task(file, &arguments.tasks, &families, arguments.size, arguments.passes, rule, allow.as_ref(), 8) {
                    Ok(result) => {
                        if arclog_encoder::zio::write_text(&target, &result.to_string()).is_err() {
                            eprintln!("{stem}: the result does not write");
                        }
                        let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                        let rate = done as f64 / begun.elapsed().as_secs_f64();
                        eprintln!("{done}/{} {stem}: {}; {} walks, {:.3}s per walk; ETA {:.0}s", files.len(), result["sizes"].to_string().chars().take(220).collect::<String>(), result["walks"], result["walk_seconds"].as_f64().unwrap_or(0.0) / result["walks"].as_f64().unwrap_or(1.0).max(1.0), (files.len() - done) as f64 / rate);
                    }
                    Err(message) => eprintln!("{stem}: {message}"),
                }
            });
        }
    });
    Ok(())
}

/// Candidate recognition on shapes: one result per file, as each ends, and a restart
/// skips those written. `--passes` gives the null's draws, `--rate` the sample of
/// size 2's shapes per million.
fn run_candidate(arguments: &Arguments, out: &str, files: &[String]) -> Result<(), String> {
    use arclog_encoder::tablewalk::{candidate_task, OpsCache, StableRule};
    std::fs::create_dir_all(out).map_err(|error| error.to_string())?;
    let cache = OpsCache::new(arguments.size, arguments.max_columns, !arguments.relational);
    let next = std::sync::atomic::AtomicUsize::new(0);
    let finished = std::sync::atomic::AtomicUsize::new(0);
    let begun = Instant::now();
    let rate = u64::from(arguments.rate);
    // `--rule` chooses the rule of the non-vacuous claims; otherwise the active ones.
    let rule = if arguments.rule { StableRule::NonVacuous } else { StableRule::Active };
    std::thread::scope(|scope| {
        for _ in 0..arguments.threads.max(1) {
            scope.spawn(|| loop {
                let at = next.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
                let Some(file) = files.get(at) else { break };
                let stem = arclog_encoder::zio::stem(file);
                let target = format!("{out}/{stem}{}.d{}.r{rate}.json", if arguments.relational { ".relational" } else { "" }, arguments.size);
                if std::path::Path::new(&target).exists() {
                    continue;
                }
                match candidate_task(file, &arguments.tasks, &cache, rate, arguments.passes, 12, rule) {
                    Ok(result) => {
                        if arclog_encoder::zio::write_text(&target, &result.to_string()).is_err() {
                            eprintln!("{stem}: the result does not write");
                        }
                        let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                        eprintln!("{done}/{} {stem}: {}; {:.0}s so far", files.len(), result["sizes"].to_string().chars().take(300).collect::<String>(), begun.elapsed().as_secs_f64());
                    }
                    Err(message) => eprintln!("{stem}: {message}"),
                }
            });
        }
    });
    Ok(())
}

fn run_walk_check(arguments: &Arguments, grids: &str) -> Result<(), String> {
    use arclog_encoder::optable::{build, Mode};
    use arclog_encoder::walk::{walk, Checker};
    let text = arclog_encoder::zio::read_text(grids).map_err(|error| error.to_string())?;
    let task = grids_task(&text, arguments.rule)?;
    let start = Instant::now();
    let scratch = scratch_host()?;
    let table = build(&scratch, if arguments.rule { Mode::Rule } else { Mode::Scene }, arguments.size, arguments.rate > 0, arguments.max_columns)?;
    eprintln!("op table: {} entries, {} schemas, {} refused, {} with no native form, {:.1}s", table.entries.len(), table.schemas.len(), table.refused, table.no_native.len(), start.elapsed().as_secs_f64());
    for line in table.no_native.iter().take(20) {
        eprintln!("no native form: {}", line.chars().take(300).collect::<String>());
    }
    let host = Host::of_task("(OUT (input ^P ^Col))", task.clone())?;
    host.set_work_cap(arguments.work_cap);
    let checker = Checker { host: &host, rate_per_million: u64::from(arguments.rate), tally: Default::default(), by_kind: Default::default() };
    let (result, tally) = walk(&table, &task, arguments.size, None, Some(checker), Default::default());
    eprintln!("walk: {} grids, {} root classes, relation classes {:?}, {} edges, {} evaluations, {:.1}s", result.grids, result.sizes.len(), result.classes_by_size, result.edges, result.evaluations, result.seconds);
    if let Some(tally) = tally {
        println!("compared {} equal {} different {} stopped on one side {} large {} refused {} column faults {}", tally.compared, tally.equal, tally.different, tally.stopped_either, tally.skipped_large, tally.refused, tally.fault);
        for example in &tally.examples {
            println!("{}", example.chars().take(700).collect::<String>());
        }
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
        ("count", [solver, tables @ ..]) if !tables.is_empty() => run_count(&arguments, solver, tables),
        ("grid-values", [grids]) => run_grid_values(&arguments, grids),
        ("law", [tasks_file]) => run_law(&arguments, tasks_file),
        ("walk", [manifest]) => run_walk(&arguments, manifest),
        ("walk-check", [grids]) => run_walk_check(&arguments, grids),
        ("candidate", [out, files @ ..]) if !files.is_empty() => run_candidate(&arguments, out, files),
        ("family", [out, files @ ..]) if !files.is_empty() => run_family(&arguments, out, files),
        ("stored-eval", [requests]) => run_stored_eval(&arguments, requests),
        ("catalog-values", [requests]) => run_catalog_values(&arguments, requests),
        ("generate", [out, files @ ..]) if !files.is_empty() => run_generate(&arguments, out, files),
        ("generate-reach", [out, files @ ..]) if !files.is_empty() => run_generate_reach(&arguments, out, files),
        ("generate-dump", [out, files @ ..]) if !files.is_empty() => run_generate_dump(&arguments, out, files),
        ("generate-classes", [out, files @ ..]) if !files.is_empty() => {
            arclog_encoder::generate::classes(files, &arguments.tasks, arguments.passes.max(1)).and_then(|found| {
                let text = serde_json::to_string(&found).map_err(|error| error.to_string())?;
                arclog_encoder::zio::write_text(out, &text)
            })
        }
        ("catalog-dump", [out, files @ ..]) if !files.is_empty() => run_catalog_dump(&arguments, out, files),
        _ => Err("usage: feature-encoder eval|rows|worked|encode|names|vector ...; the file's first lines give each form".to_string()),
    };
    if let Err(message) = result {
        eprintln!("{message}");
        std::process::exit(1);
    }
}
