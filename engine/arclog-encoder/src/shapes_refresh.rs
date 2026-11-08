//! The `shapes` records of a task's tables, from the tables' stored rows and the task's grids, with no replay of the engine.
//!
//! A rows file is zstd (or plain) JSON lines, one per distinct TableHash: `{"hash": "<32 hex digits>", "table": T}`, where `T` is the table in the form that `atom_lists::stored_of` reads (`stored_json` writes
//! it). For each line the walk of the table's shapes runs on a walker of its own, so a record depends on the table, the task's grids and the list of shapes alone, whatever else the run walked. The output has a line
//! for each line of the input, in its order: `{"record":"shapes","table":HASH,"h":B,"v":B,"stopped":FLAG}`. `h` is the base64 of the shape hashes as little-endian u64, and `v` the base64 of the least, mean and
//! most of each shape as little-endian f32, three to a shape. With a list of shape hashes, the record holds those shapes alone, in the list's order, and a shape the table lacks has 0; otherwise it holds each shape of
//! the table's vector in the order of their hashes. `stopped` says that the walk passed its bound on cells, so that the terms after that point have no value (NaN), or that the table has more columns than the
//! generator takes, which gives no vector and NaN for each listed shape.

use crate::atom_lists::{base64, stored_of, PAST_MAX_COLUMNS};
use crate::generate::{Generators, ShapeList, ShapeMask, Walker};
use crate::lookup::LookupMap;
use crate::table_vector::{table_vector, table_vector_of_shapes, Grids, TableVector};
use std::collections::BTreeMap;
use std::io::{BufRead, Read, Write};
use std::path::Path;
use std::sync::Mutex;

/// The size of the shapes, as the candidate lists build them.
const SIZE: usize = 2;

/// The hashes and the numbers of a vector's shapes: the listed shapes, or each shape of the vector. A shape that the vector lacks is at its default at every example.
fn numbers_of(vector: &TableVector, only: Option<&[u64]>) -> (Vec<u64>, Vec<f32>) {
    let places: Vec<(u64, Option<usize>)> = match only {
        None => vector.shapes.iter().enumerate().map(|(place, shape)| (*shape, Some(place))).collect(),
        Some(only) => only.iter().map(|hash| (*hash, vector.shapes.binary_search(hash).ok())).collect(),
    };
    let mut values = Vec::with_capacity(places.len() * 3);
    for (_, place) in &places {
        match place {
            Some(shape) => {
                let (least, mean, most, _) = vector.over_examples(*shape, false);
                values.extend([least as f32, mean as f32, most as f32]);
            }
            None => values.extend([0.0; 3]),
        }
    }
    (places.iter().map(|(hash, _)| *hash).collect(), values)
}

/// One table's record, none for a line that holds no table.
struct Walked {
    hash: String,
    line: Option<String>,
    seconds: f64,
    shapes: usize,
    stopped: bool,
    too_wide: bool,
}

/// The record of one line of a rows file.
#[allow(clippy::too_many_arguments)]
fn record_of(text: &str, train: usize, test: usize, grids: &Grids, generators: &Generators, only: Option<&[u64]>, masks: &mut LookupMap<String, ShapeMask>) -> Result<Walked, &'static str> {
    let none = Walked { hash: String::new(), line: None, seconds: 0.0, shapes: 0, stopped: false, too_wide: false };
    if text.trim().is_empty() {
        return Ok(none);
    }
    let held: serde_json::Value = serde_json::from_str(text).map_err(|_| "a line that is not JSON")?;
    let hash = held["hash"].as_str().filter(|hash| !hash.is_empty() && hash.bytes().all(|byte| byte.is_ascii_hexdigit())).ok_or("a line with no hash")?;
    let begun = std::time::Instant::now();
    let (hashes, values, stopped, too_wide) = match stored_of(&held["table"], train, test, &LookupMap::new()) {
        Ok(None) => return Ok(none),
        Err(why) if why == PAST_MAX_COLUMNS => match only {
            None => (Vec::new(), Vec::new(), true, true),
            Some(only) => (only.to_vec(), vec![f32::NAN; only.len() * 3], true, true),
        },
        Err(why) => return Err(why),
        Ok(Some(stored)) => {
            let family = generators.get(&stored, SIZE);
            let mut walker = Walker::new(&family);
            let vector = match only {
                None => table_vector(&mut walker, &stored, grids, train + test, false),
                Some(only) => {
                    if masks.len() >= 4096 {
                        masks.clear();
                    }
                    let mask = masks.entry(stored.key.clone()).or_insert_with(|| family.shape_mask(&ShapeList::new(only.iter().copied())));
                    table_vector_of_shapes(&mut walker, &stored, grids, train + test, false, mask)
                }
            };
            let (hashes, values) = numbers_of(&vector, only);
            (hashes, values, vector.over_budget, false)
        }
    };
    let seconds = begun.elapsed().as_secs_f64();
    let shapes = hashes.len();
    let line = format!(
        "{{\"record\":\"shapes\",\"table\":\"{hash}\",\"h\":\"{}\",\"v\":\"{}\",\"stopped\":{stopped}}}",
        base64(&hashes.iter().flat_map(|hash| hash.to_le_bytes()).collect::<Vec<u8>>()),
        base64(&values.iter().flat_map(|value| value.to_le_bytes()).collect::<Vec<u8>>())
    );
    Ok(Walked { hash: hash.to_string(), line: Some(line), seconds, shapes, stopped, too_wide })
}

/// A rows file's lines.
fn lines_of(path: &Path) -> Result<std::io::Lines<std::io::BufReader<Box<dyn Read + Send>>>, String> {
    let file = std::fs::File::open(path).map_err(|error| format!("{}: {error}", path.display()))?;
    let reader: Box<dyn Read + Send> = if path.extension().is_some_and(|extension| extension == "zst") { Box::new(zstd::stream::read::Decoder::new(file).map_err(|error| error.to_string())?) } else { Box::new(file) };
    Ok(std::io::BufReader::new(reader).lines())
}

/// Writes the `shapes` records of the tables in `input` to `out`, on `threads` threads, for the task `task` of `task_dir`, and gives a line of counts. `only` lists the shapes to walk, or is none for each shape.
/// It fails, with `out` unwritten, where a line can't be read.
pub fn run(input: &Path, out: &Path, task_dir: &Path, task: &str, only: Option<&[u64]>, threads: usize, generators: &Generators) -> Result<String, String> {
    let begun = std::time::Instant::now();
    let (parsed, grids) = Grids::of_file(task_dir, task, None)?;
    let (train, test) = (parsed.train.len(), parsed.test.len());
    let source = Mutex::new((lines_of(input)?, 0usize));
    let done: Mutex<Vec<(usize, Result<Walked, String>)>> = Mutex::new(Vec::new());
    std::thread::scope(|scope| {
        for _ in 0..threads.max(1) {
            scope.spawn(|| {
                let mut masks: LookupMap<String, ShapeMask> = LookupMap::new();
                loop {
                    let next = {
                        let mut source = source.lock().expect("no panic");
                        let line = source.0.next();
                        let at = source.1;
                        if line.is_some() {
                            source.1 += 1;
                        }
                        line.map(|line| (at, line))
                    };
                    let Some((at, line)) = next else { break };
                    let outcome = match line {
                        Err(error) => Err(error.to_string()),
                        Ok(text) => match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| record_of(&text, train, test, &grids, generators, only, &mut masks))) {
                            Ok(Ok(walked)) => Ok(walked),
                            Ok(Err(why)) => Err(why.to_string()),
                            Err(_) => Err("a panic".to_string()),
                        },
                    };
                    done.lock().expect("no panic").push((at, outcome));
                }
            });
        }
    });
    let mut done = done.into_inner().expect("no panic");
    done.sort_by_key(|(at, _)| *at);
    let mut faults: BTreeMap<String, u64> = BTreeMap::new();
    for (_, outcome) in &done {
        if let Err(why) = outcome {
            *faults.entry(why.clone()).or_insert(0) += 1;
        }
    }
    if !faults.is_empty() {
        return Err(format!("{task}: lines that can't be read: {faults:?}"));
    }
    let walked: Vec<&Walked> = done.iter().filter_map(|(_, outcome)| outcome.as_ref().ok()).filter(|walked| walked.line.is_some()).collect();
    crate::zio::write_with(out, |sink| {
        for held in &walked {
            sink.write_all(held.line.as_deref().unwrap_or_default().as_bytes()).map_err(|error| error.to_string())?;
            sink.write_all(b"\n").map_err(|error| error.to_string())?;
        }
        Ok(())
    })?;
    let mut slowest: Vec<(f64, usize, &str)> = walked.iter().map(|held| (held.seconds, held.shapes, held.hash.as_str())).collect();
    slowest.sort_by(|a, b| b.0.total_cmp(&a.0));
    slowest.truncate(5);
    Ok(format!(
        "{task}: {} tables, {} stopped, {} too wide, {:.1} s of walks, {:.1} s wall; slowest (s, shapes, table) {:?}",
        walked.len(),
        walked.iter().filter(|held| held.stopped && !held.too_wide).count(),
        walked.iter().filter(|held| held.too_wide).count(),
        walked.iter().map(|held| held.seconds).sum::<f64>(),
        begun.elapsed().as_secs_f64(),
        slowest.iter().map(|(seconds, shapes, hash)| ((seconds * 10.0).round() / 10.0, *shapes, *hash)).collect::<Vec<_>>()
    ))
}
