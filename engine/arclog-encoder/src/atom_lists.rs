//! Lists for a study of whole atoms. A writer's rows hold, for each decision of a task, the body's table and each candidate's table, in files `<source>/<task>.tables.zst`. For each distinct table of such a
//! file, `<source>/<task>.gen.zst` holds what the candidate lists hold: each shape's value where it is stable over the examples, and otherwise its least, its mean and its greatest. `<source>/<task>.null.zst`
//! holds the same for the shapes that read the output, with each train pair reading another pair's output.
//!
//! A file holds a header line and then a line per decision, each its own zstd frame, so a reader can read a file in progress:
//! `{"record": "decision", "decision": D, "body": I, "cands": [I, ..], "shapes": ids, "reads_output": flags, "tables": [{"at": I, "ids": places, "values": floats, "graded": places, "least": floats,
//! "mean": floats, "most": floats}, ..]}`. `I` is a table's place in the task, and -1 where the decision has no table there. `shapes` adds shape ids (u64) to the file's list of shapes, `reads_output`
//! (u8) says which of them read the output, and `places` (u32) index that list. Arrays are little-endian in base64. A shape with no value at any example has NaN for its least, mean and most.

use crate::generate::{Generated, Generators, Walker, READS_OUTPUT};
use crate::lookup::{LookupMap, LookupSet};
use crate::schema::type_of_name;
use crate::stored::{cell_bits, Stored};
use crate::table_vector::{table_vector, Grids, TableVector};
use arclog::types::ValueType;
use std::collections::BTreeMap;
use std::io::{BufRead, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

/// The assignments of a table that a list reads.
const ASSIGNMENT_CAP: usize = 16;
/// What a thread's walkers hold at most, and past either bound they start over: their memo entries and values, their cells, and the keys of second relations. A value costs some hundreds of bytes, so these
/// bounds set the memory of a run at about 400 MiB per thread.
const HELD_ENTRIES: usize = 2_000_000;
const HELD_CELLS: usize = 10_000_000;
const HELD_KEYS: usize = 4_000_000;

pub(crate) fn base64(bytes: &[u8]) -> String {
    const LETTERS: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let held = (u32::from(chunk[0]) << 16) | (u32::from(*chunk.get(1).unwrap_or(&0)) << 8) | u32::from(*chunk.get(2).unwrap_or(&0));
        out.push(LETTERS[(held >> 18) as usize & 63] as char);
        out.push(LETTERS[(held >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 { LETTERS[(held >> 6) as usize & 63] as char } else { '=' });
        out.push(if chunk.len() > 2 { LETTERS[held as usize & 63] as char } else { '=' });
    }
    out
}

fn floats(values: &[f32]) -> String {
    base64(&values.iter().flat_map(|value| value.to_le_bytes()).collect::<Vec<u8>>())
}

fn places(values: &[u32]) -> String {
    base64(&values.iter().flat_map(|value| value.to_le_bytes()).collect::<Vec<u8>>())
}

/// A table's list before its shapes have places: its place in the task, the shapes with one value at every example (shape, whether it reads the output, value), and the others (shape, whether it reads the output, least, mean and greatest).
struct Pending {
    at: i64,
    stable: Vec<(u64, bool, f32)>,
    graded: Vec<(u64, bool, [f32; 3])>,
}

/// One of a task's two files: its shapes so far, and each line as its own frame under a working name.
struct Sink {
    path: PathBuf,
    working: PathBuf,
    file: std::io::BufWriter<std::fs::File>,
    index: LookupMap<u64, u32>,
    fresh: Vec<(u64, u8)>,
}

impl Sink {
    fn new(path: PathBuf, header: &serde_json::Value) -> Result<Sink, String> {
        let working = path.with_extension("working");
        let file = std::io::BufWriter::new(std::fs::File::create(&working).map_err(|error| error.to_string())?);
        let mut sink = Sink { path, working, file, index: LookupMap::new(), fresh: Vec::new() };
        sink.line(header)?;
        Ok(sink)
    }

    fn line(&mut self, value: &serde_json::Value) -> Result<(), String> {
        let mut text = serde_json::to_vec(value).map_err(|error| error.to_string())?;
        text.push(b'\n');
        let packed = zstd::stream::encode_all(&text[..], 3).map_err(|error| error.to_string())?;
        self.file.write_all(&packed).map_err(|error| error.to_string())?;
        self.file.flush().map_err(|error| error.to_string())
    }

    /// A table's list before its shapes have places.
    fn pending(at: i64, vector: &TableVector) -> Pending {
        let mut pending = Pending { at, stable: Vec::new(), graded: Vec::new() };
        for shape in 0..vector.shapes.len() {
            let (low, middle, high, count) = vector.over_examples(shape, false);
            let reads_output = vector.meta[shape].0 & READS_OUTPUT != 0;
            if vector.stable(shape) {
                pending.stable.push((vector.shapes[shape], reads_output, middle as f32));
            } else if count == 0 || low != 0.0 || high != 0.0 {
                pending.graded.push((vector.shapes[shape], reads_output, [low as f32, middle as f32, high as f32]));
            }
        }
        pending
    }

    /// The lists of one decision's new tables, as the line's entries. The shapes that the file does not list yet take the next places in the order of their ids.
    fn lists(&mut self, pending: &[Pending]) -> Vec<serde_json::Value> {
        let mut fresh: BTreeMap<u64, bool> = BTreeMap::new();
        for list in pending {
            let stable = list.stable.iter().map(|(shape, reads_output, _)| (*shape, *reads_output));
            let graded = list.graded.iter().map(|(shape, reads_output, _)| (*shape, *reads_output));
            for (shape, reads_output) in stable.chain(graded) {
                if !self.index.contains_key(&shape) {
                    fresh.entry(shape).or_insert(reads_output);
                }
            }
        }
        for (shape, reads_output) in fresh {
            let next = self.index.len() as u32;
            self.index.insert(shape, next);
            self.fresh.push((shape, u8::from(reads_output)));
        }
        pending.iter().map(|list| {
            let place_of = |shape: &u64| self.index[shape];
            let ids: Vec<u32> = list.stable.iter().map(|(shape, _, _)| place_of(shape)).collect();
            let values: Vec<f32> = list.stable.iter().map(|(_, _, value)| *value).collect();
            let graded: Vec<u32> = list.graded.iter().map(|(shape, _, _)| place_of(shape)).collect();
            let least: Vec<f32> = list.graded.iter().map(|(_, _, bounds)| bounds[0]).collect();
            let mean: Vec<f32> = list.graded.iter().map(|(_, _, bounds)| bounds[1]).collect();
            let most: Vec<f32> = list.graded.iter().map(|(_, _, bounds)| bounds[2]).collect();
            serde_json::json!({"at": list.at, "ids": places(&ids), "values": floats(&values), "graded": places(&graded), "least": floats(&least), "mean": floats(&mean), "most": floats(&most)})
        }).collect()
    }

    fn fresh_shapes(&mut self) -> (String, String) {
        let ids = base64(&self.fresh.iter().flat_map(|(shape, _)| shape.to_le_bytes()).collect::<Vec<u8>>());
        let flags = base64(&self.fresh.iter().map(|(_, flag)| *flag).collect::<Vec<u8>>());
        self.fresh.clear();
        (ids, flags)
    }

    fn finish(mut self) -> Result<(), String> {
        self.file.flush().map_err(|error| error.to_string())?;
        drop(self.file);
        std::fs::rename(&self.working, &self.path).map_err(|error| error.to_string())
    }
}

/// Why `stored_of` can't read a table that has more columns than the generator takes.
pub const PAST_MAX_COLUMNS: &str = "past MAX_TABLE_COLUMNS columns";

/// A file's table as a table of the candidate lists, with each assignment's each model as a model at its example. `Ok(None)` is no table, and `Err` says why a table can't be read.
pub fn stored_of(table: &serde_json::Value, train: usize, test: usize, orient: &LookupMap<i64, String>) -> Result<Option<Stored>, &'static str> {
    use serde_json::Value;
    let Some(parts) = table.as_array() else { return Ok(None) };
    if parts.len() != 1 {
        return Err("several slots");
    }
    let part = &parts[0];
    let names: Vec<&str> = part["types"].as_array().ok_or("types")?.iter().filter_map(Value::as_str).collect();
    let types: Vec<ValueType> = names.iter().map(|name| type_of_name(name)).collect::<Option<_>>().ok_or("a type")?;
    if types.len() > crate::generate::MAX_TABLE_COLUMNS {
        return Err(PAST_MAX_COLUMNS);
    }
    let examples = train + test;
    let mut rows: Vec<Vec<Vec<Vec<u32>>>> = vec![Vec::new(); examples];
    let mut blocked = vec![false; examples];
    for at in part["at"].as_array().ok_or("at")?.iter().take(ASSIGNMENT_CAP) {
        for entry in at["entries"].as_array().ok_or("entries")? {
            let kind = entry[0].as_i64().ok_or("kind")?;
            let index = entry[1].as_u64().ok_or("index")? as usize;
            let scope: Vec<usize> = match kind {
                0 => (0..examples).collect(),
                1 => vec![index],
                2 => vec![train + index],
                _ => return Err("a kind of example"),
            };
            let count = entry[4].as_u64().unwrap_or(0);
            let cells = entry[5].as_array();
            if entry[3].as_bool() != Some(true) || cells.is_none() {
                for example in scope {
                    if example < examples {
                        blocked[example] = true;
                    }
                }
                continue;
            }
            let mut model: Vec<Vec<u32>> = Vec::with_capacity(count as usize);
            if types.is_empty() {
                model.resize(count as usize, Vec::new());
            } else if let Some(cells) = cells {
                let mut place = 0;
                while place < cells.len() {
                    let mut row = Vec::with_capacity(types.len());
                    for ty in &types {
                        let value = if ty.is_box() {
                            let held = Value::Array(cells.get(place..place + 4).ok_or("a cell")?.to_vec());
                            place += 4;
                            held
                        } else {
                            let held = cells.get(place).ok_or("a cell")?.clone();
                            place += 1;
                            match orient.get(&held.as_i64().unwrap_or(-1)) {
                                Some(name) if !matches!(ty, ValueType::Color | ValueType::Int | ValueType::Nat | ValueType::Example | ValueType::Ident(_)) => Value::String(name.clone()),
                                _ => held,
                            }
                        };
                        row.push(cell_bits(&value, ty).ok_or("a cell")?);
                    }
                    model.push(row);
                }
            }
            for example in scope {
                if example < examples {
                    rows[example].push(model.clone());
                }
            }
        }
    }
    for (example, held) in rows.iter_mut().enumerate() {
        if blocked[example] {
            held.clear();
        }
    }
    Ok(Some(Stored::of_rows(&types, rows)))
}

/// What one file's walks hold. The walkers stand before the families, so they leave memory first. A walker's memos are keyed by content, so one serves real and permuted outputs, and a term that reads no output runs once.
struct Walkers {
    real: LookupMap<String, Walker<'static>>,
    families: LookupMap<String, Arc<Generated>>,
}

impl Walkers {
    /// A walker of `stored`'s family. `family` stands in `families` until the walkers have left, which makes the longer lifetime sound.
    fn walker<'w>(walkers: &'w mut LookupMap<String, Walker<'static>>, families: &mut LookupMap<String, Arc<Generated>>, generators: &Generators, stored: &Stored, d: usize) -> &'w mut Walker<'static> {
        let family = families.entry(stored.key.clone()).or_insert_with(|| generators.get(stored, d));
        let family: &'static Generated = unsafe { &*Arc::as_ptr(family) };
        walkers.entry(stored.key.clone()).or_insert_with(|| Walker::with_budget(family, HELD_CELLS, HELD_ENTRIES))
    }

    fn over_budget(walkers: &LookupMap<String, Walker<'static>>) -> bool {
        let entries = walkers.sum_of(|_, walker| walker.held().0);
        let cells = walkers.sum_of(|_, walker| walker.held().1);
        entries > HELD_ENTRIES || cells > HELD_CELLS
    }
}

/// One task's state as its decisions come.
struct TaskRun<'r> {
    train: usize,
    test: usize,
    examples: usize,
    grids: Grids,
    null_grids: Option<Grids>,
    real: Sink,
    null: Sink,
    table_at: LookupMap<u128, i64>,
    walkers: Walkers,
    generators: &'r Generators,
    d: usize,
    walks: u64,
    reads: u64,
    faults: BTreeMap<&'static str, u64>,
}

impl TaskRun<'_> {
    /// The content of the table in `table`, or None where the file gives no table. The table goes into `fresh` where the task has not listed it yet.
    fn content_of(&mut self, table: &serde_json::Value, orient: &LookupMap<i64, String>, fresh: &mut BTreeMap<u128, Stored>) -> Option<u128> {
        let stored = match stored_of(table, self.train, self.test, orient) {
            Ok(Some(stored)) => stored,
            Ok(None) => return None,
            Err(why) => {
                *self.faults.entry(why).or_insert(0) += 1;
                return None;
            }
        };
        self.reads += 1;
        let content = stored.content();
        if !self.table_at.contains_key(&content) {
            fresh.entry(content).or_insert(stored);
        }
        Some(content)
    }

    /// The lists of a decision's new tables, which take the next places in the task in the order of their contents: the real lists, then the lists of the permuted outputs.
    fn walk_fresh(&mut self, fresh: BTreeMap<u128, Stored>) -> (Vec<Pending>, Vec<Pending>) {
        let (mut real, mut null) = (Vec::new(), Vec::new());
        for (content, stored) in fresh {
            let at = self.table_at.len() as i64;
            self.table_at.insert(content, at);
            self.walks += 1;
            let walker = Walkers::walker(&mut self.walkers.real, &mut self.walkers.families, self.generators, &stored, self.d);
            let vector = table_vector(walker, &stored, &self.grids, self.examples, false);
            real.push(Sink::pending(at, &vector));
            if let Some(grids) = &self.null_grids {
                let vector = table_vector(walker, &stored, grids, self.examples, true);
                null.push(Sink::pending(at, &vector));
            }
        }
        (real, null)
    }

    /// The place in the task of a table that `content_of` gave, or -1 where the file gives no table.
    fn place_of(&self, content: Option<u128>) -> i64 {
        content.and_then(|content| self.table_at.get(&content).copied()).unwrap_or(-1)
    }
}

/// Writes the lists of one file of tables.
#[allow(clippy::too_many_arguments)]
fn lists_of_file(input: &Path, out: &Path, task_dir: &Path, generators: &Generators, d: usize, order_of: &BTreeMap<String, Option<Vec<usize>>>, orient: &LookupMap<i64, String>) -> Result<String, String> {
    let begun = std::time::Instant::now();
    let raw = std::fs::File::open(input).map_err(|error| error.to_string())?;
    let reader = std::io::BufReader::new(zstd::stream::read::Decoder::new(raw).map_err(|error| error.to_string())?);
    let mut run: Option<TaskRun> = None;
    let mut decisions = 0u64;
    let mut name = String::new();
    for line in reader.lines() {
        let line = line.map_err(|error| error.to_string())?;
        let record: serde_json::Value = serde_json::from_str(&line).map_err(|error| error.to_string())?;
        drop(line);
        match record["record"].as_str() {
            Some("header") => {
                name = record["task"].as_str().ok_or("a task's name")?.to_string();
                let (task, grids) = Grids::of_file(task_dir, &name, None)?;
                let (train, test) = (task.train.len(), task.test.len());
                let order = order_of.get(&name).and_then(Option::as_ref);
                let null_grids = match order {
                    Some(order) => Some(Grids::of_file(task_dir, &name, Some(order))?.1),
                    None => None,
                };
                let header = serde_json::json!({"record": "header", "task": name, "train": train, "test": test});
                let mut null_header = header.clone();
                null_header["order"] = order.map_or(serde_json::Value::Null, |order| serde_json::json!(order));
                run = Some(TaskRun {
                    train,
                    test,
                    examples: train + test,
                    grids,
                    null_grids,
                    real: Sink::new(out.join(format!("{name}.gen.zst")), &header)?,
                    null: Sink::new(out.join(format!("{name}.null.zst")), &null_header)?,
                    table_at: LookupMap::new(),
                    walkers: Walkers { real: LookupMap::new(), families: LookupMap::new() },
                    generators,
                    d,
                    walks: 0,
                    reads: 0,
                    faults: BTreeMap::new(),
                });
            }
            Some("decision") => {
                let run = run.as_mut().ok_or("a decision before its header")?;
                let mut fresh = BTreeMap::new();
                let body = run.content_of(&record["body"], orient, &mut fresh);
                let empty = Vec::new();
                let cands: Vec<Option<u128>> = record["candidates"].as_array().unwrap_or(&empty).iter().map(|table| run.content_of(table, orient, &mut fresh)).collect();
                let (real, null) = run.walk_fresh(fresh);
                let (real, null) = (run.real.lists(&real), run.null.lists(&null));
                let body = run.place_of(body);
                let cands: Vec<i64> = cands.into_iter().map(|content| run.place_of(content)).collect();
                let line_of = |shapes: (String, String), tables: Vec<serde_json::Value>| serde_json::json!({"record": "decision", "decision": record["decision"], "body": body, "cands": cands, "shapes": shapes.0, "reads_output": shapes.1, "tables": tables});
                let (real_shapes, null_shapes) = (run.real.fresh_shapes(), run.null.fresh_shapes());
                run.real.line(&line_of(real_shapes, real))?;
                run.null.line(&line_of(null_shapes, null))?;
                decisions += 1;
                if Walkers::over_budget(&run.walkers.real) || crate::gen_parts::keys_held() > HELD_KEYS {
                    run.walkers.real.clear();
                    crate::gen_parts::clear_views();
                }
            }
            other => return Err(format!("a line of no known record: {other:?}")),
        }
    }
    let run = run.ok_or("a file with no header")?;
    let summary = format!("{name}: {decisions} decisions, {} tables read, {} walked, {:.1} s, {:.2} walks/s, faults {:?}", run.reads, run.walks, begun.elapsed().as_secs_f64(), run.walks as f64 / begun.elapsed().as_secs_f64().max(1e-3), run.faults);
    let TaskRun { real, null, walkers, .. } = run;
    drop(walkers);
    real.finish()?;
    null.finish()?;
    Ok(summary)
}

/// The finished files of tables under `input`, as (source folder's name, task, path), in a mixed order that does not change as files come.
fn files_of(input: &Path) -> Vec<(String, String, PathBuf)> {
    let mut out = Vec::new();
    let Ok(sources) = std::fs::read_dir(input) else { return out };
    for source in sources.flatten() {
        let Ok(files) = std::fs::read_dir(source.path()) else { continue };
        let folder = source.file_name().to_string_lossy().to_string();
        for file in files.flatten() {
            let name = file.file_name().to_string_lossy().to_string();
            if let Some(task) = name.strip_suffix(".tables.zst") {
                out.push((folder.clone(), task.to_string(), file.path()));
            }
        }
    }
    out.sort_by_key(|(folder, task, _)| crate::native::hash_words(format!("{folder}/{task}").bytes().map(u64::from)));
    out
}

/// Writes the lists of each finished file of tables under `input` into the same folders under `out`, on `threads` threads, with a line of progress per file, and goes on as files come. It ends once no new
/// file has come for `idle_seconds`, and a restart skips the files whose lists stand.
#[allow(clippy::too_many_arguments)]
pub fn run(input: &Path, out: &Path, task_dir: &Path, generators: &Generators, d: usize, order_of: &BTreeMap<String, Option<Vec<usize>>>, orient: &LookupMap<i64, String>, threads: usize, idle_seconds: u64) -> Result<(), String> {
    let claimed: Mutex<LookupSet<PathBuf>> = Mutex::new(LookupSet::new());
    let finished = std::sync::atomic::AtomicUsize::new(0);
    let begun = std::time::Instant::now();
    let last_new = Mutex::new(std::time::Instant::now());
    std::thread::scope(|scope| {
        for _ in 0..threads.max(1) {
            scope.spawn(|| loop {
                let next = {
                    let mut claimed = claimed.lock().expect("no panic");
                    files_of(input).into_iter().find(|(folder, task, path)| {
                        !claimed.contains(path) && !out.join(folder).join(format!("{task}.gen.zst")).exists()
                    }).inspect(|(_, _, path)| {
                        claimed.insert(path.clone());
                    })
                };
                let Some((folder, _, path)) = next else {
                    if last_new.lock().expect("no panic").elapsed().as_secs() > idle_seconds {
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_secs(20));
                    continue;
                };
                *last_new.lock().expect("no panic") = std::time::Instant::now();
                let target = out.join(&folder);
                let _ = std::fs::create_dir_all(&target);
                let written = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| lists_of_file(&path, &target, task_dir, generators, d, order_of, orient)));
                match written {
                    Ok(Ok(summary)) => {
                        let done = finished.fetch_add(1, std::sync::atomic::Ordering::SeqCst) + 1;
                        eprintln!("{done} files, {:.2} files/min; {folder}/{summary}", done as f64 * 60.0 / begun.elapsed().as_secs_f64());
                    }
                    Ok(Err(message)) => eprintln!("{folder}/{}: {message}", path.display()),
                    Err(_) => eprintln!("{folder}/{}: a panic", path.display()),
                }
            });
        }
    });
    Ok(())
}
