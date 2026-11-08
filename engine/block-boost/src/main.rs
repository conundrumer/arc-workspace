//! A gradient-boosted ranker over rows that share their entries.
//!
//! A row is a candidate at an example. What holds of a whole candidate or a whole task stands once, in a block that each of
//! its rows points to, so a fit's memory follows the facts and not how many rows repeat them. A row's value at a column is
//! the entry of one of its blocks, and a column with no entry there is at its default, 0.
//!
//!     block-boost scan DIR      each column's hash, rows and entries, from DIR/plan.json
//!     block-boost compile DIR   each entry as the number of its bin, for the columns DIR/keep.i32 keeps
//!     block-boost fit FILE      one lambdarank model per seed, from the JSON in FILE
//!     block-boost softmax FILE  a model of the writer's softmax over the ids of each writing point, from the JSON in FILE
//!     block-boost softmax-gpu FILE  the same, with the gradient, histograms, partitions and scores on a CUDA card (build with --features gpu)
//!
//! The objective and the tree growth are those of LightGBM's lambdarank, with the same parameters. A column that plan.json lists as `categorical` has one bin
//! for each of its values, and splits as LightGBM splits a categorical feature: a set of values goes left (see `best_in_categorical`). A histogram entry holds
//! the sums of a bin, and a leaf's rows add their sums to the blocks first, so one block's entries are read once for a leaf.
//! Rows with the same blocks in every map have the same leaf in every tree, so `softmax` grows its trees over those pairs of rows, keeps one score for
//! each pair, and goes over rows only for the gradient and for the sums of each pair's rows.

mod gpu;

use rayon::prelude::*;
use serde_json::{Value, json};
use std::fs::{self, File};
use std::io::{BufRead, BufReader, BufWriter, Read, Write};
use std::ops::Deref;
use std::sync::atomic::{AtomicU32, Ordering};
use std::os::fd::AsRawFd;
use std::path::{Path, PathBuf};
use std::time::Instant;

const NONE: u32 = u32::MAX;
const EPSILON: f64 = 1e-15;
const ZERO: f64 = 1e-35;
const MIN_DATA_IN_BIN: f64 = 3.0;
const HISTOGRAM_BYTES: usize = 3 << 30;
const SIGMOID_BINS: usize = 1 << 20;
const SIGMOID_LOW: f64 = -25.0;
const SIGMOID_FACTOR: f64 = SIGMOID_BINS as f64 / 50.0;

fn bytes_of<T: Copy>(values: &[T]) -> &[u8] {
    unsafe { std::slice::from_raw_parts(values.as_ptr() as *const u8, std::mem::size_of_val(values)) }
}

fn bytes_of_mut<T: Copy>(values: &mut [T]) -> &mut [u8] {
    unsafe { std::slice::from_raw_parts_mut(values.as_mut_ptr() as *mut u8, std::mem::size_of_val(values)) }
}

fn read_all<T: Copy + Default>(path: &Path) -> Vec<T> {
    let bytes = fs::read(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    let mut out = vec![T::default(); bytes.len() / std::mem::size_of::<T>()];
    bytes_of_mut(&mut out).copy_from_slice(&bytes);
    out
}

fn write_all<T: Copy>(path: &Path, values: &[T]) {
    let working = path.with_extension("working");
    fs::write(&working, bytes_of(values)).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    fs::rename(&working, path).unwrap();
}

/// An array read from a file's pages, which the system can drop and read again, and which processes share.
struct Mapped<T> {
    at: *const T,
    len: usize,
}

unsafe impl<T> Send for Mapped<T> {}
unsafe impl<T> Sync for Mapped<T> {}

impl<T> Mapped<T> {
    fn open(path: &Path) -> Self {
        let file = File::open(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        let size = file.metadata().unwrap().len() as usize;
        if size == 0 {
            return Mapped { at: std::ptr::NonNull::dangling().as_ptr(), len: 0 };
        }
        let at = unsafe { libc::mmap(std::ptr::null_mut(), size, libc::PROT_READ, libc::MAP_SHARED, file.as_raw_fd(), 0) };
        assert!(at != libc::MAP_FAILED, "{}: no mapping", path.display());
        Mapped { at: at as *const T, len: size / std::mem::size_of::<T>() }
    }
}

impl<T> Deref for Mapped<T> {
    type Target = [T];
    #[inline]
    fn deref(&self) -> &[T] {
        unsafe { std::slice::from_raw_parts(self.at, self.len) }
    }
}

impl<T> Drop for Mapped<T> {
    fn drop(&mut self) {
        if self.len > 0 {
            unsafe { libc::munmap(self.at as *mut libc::c_void, self.len * std::mem::size_of::<T>()) };
        }
    }
}

fn mix(mut x: u64) -> u64 {
    x = x.wrapping_add(0x9e3779b97f4a7c15);
    x = (x ^ (x >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)).wrapping_mul(0x94d049bb133111eb);
    x ^ (x >> 31)
}

struct Random(u64);

impl Random {
    fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9e3779b97f4a7c15);
        mix(self.0)
    }
    fn below(&mut self, n: usize) -> usize {
        (self.next() % n as u64) as usize
    }
    fn unit(&mut self) -> f64 {
        (self.next() >> 11) as f64 / (1u64 << 53) as f64
    }
}

/// A build's stream of rows: frames of a row count, an entry count, each row's length, each entry's column as its difference
/// from the entry before, and each entry's value.
struct Records {
    input: zstd::stream::read::Decoder<'static, BufReader<File>>,
    lengths: Vec<u32>,
    columns: Vec<i32>,
    values: Vec<f32>,
}

impl Records {
    fn open(path: &Path) -> Self {
        let file = File::open(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
        Records { input: zstd::stream::read::Decoder::new(file).unwrap(), lengths: vec![], columns: vec![], values: vec![] }
    }

    fn next(&mut self) -> bool {
        let mut head = [0u8; 12];
        let mut got = 0;
        while got < head.len() {
            let n = self.input.read(&mut head[got..]).unwrap();
            if n == 0 {
                assert!(got == 0, "a stream ends inside a frame");
                return false;
            }
            got += n;
        }
        let rows = u32::from_le_bytes(head[..4].try_into().unwrap()) as usize;
        let entries = u64::from_le_bytes(head[4..].try_into().unwrap()) as usize;
        self.lengths.resize(rows, 0);
        self.columns.resize(entries, 0);
        self.values.resize(entries, 0.0);
        self.input.read_exact(bytes_of_mut(&mut self.lengths)).unwrap();
        self.input.read_exact(bytes_of_mut(&mut self.columns)).unwrap();
        self.input.read_exact(bytes_of_mut(&mut self.values)).unwrap();
        let mut at = 0i32;
        for column in &mut self.columns {
            at = at.wrapping_add(*column);
            *column = at;
        }
        true
    }

    /// Calls `each` with every row's place and its columns and values.
    fn for_each_row(&mut self, mut each: impl FnMut(usize, &[i32], &[f32])) -> usize {
        let mut row = 0;
        while self.next() {
            let mut at = 0;
            for &length in &self.lengths {
                let end = at + length as usize;
                each(row, &self.columns[at..end], &self.values[at..end]);
                at = end;
                row += 1;
            }
        }
        row
    }
}

struct PlanMap {
    file: PathBuf,
    domain: usize,
}

struct PlanUse {
    file: PathBuf,
    map: usize,
    col_map: PathBuf,
}

struct Plan {
    rows: usize,
    columns: usize,
    max_bin: usize,
    sample_cap: u64,
    threads: usize,
    reference: Option<PathBuf>,
    /// The columns (by their number in the plan's column map) that split as categories, each value a category.
    categorical: Vec<usize>,
    maps: Vec<PlanMap>,
    uses: Vec<PlanUse>,
}

fn read_json(path: &Path) -> Value {
    serde_json::from_str(&fs::read_to_string(path).unwrap_or_else(|e| panic!("{}: {e}", path.display()))).unwrap()
}

impl Plan {
    fn read(dir: &Path) -> Plan {
        let v = read_json(&dir.join("plan.json"));
        let path = |x: &Value| {
            let p = PathBuf::from(x.as_str().unwrap());
            if p.is_absolute() { p } else { dir.join(p) }
        };
        Plan {
            rows: v["rows"].as_u64().unwrap() as usize,
            columns: v["columns"].as_u64().unwrap() as usize,
            max_bin: v["max_bin"].as_u64().unwrap() as usize,
            sample_cap: v["sample_cap"].as_u64().unwrap(),
            threads: v["threads"].as_u64().unwrap() as usize,
            reference: v["reference"].as_str().map(PathBuf::from),
            categorical: v["categorical"]
                .as_array()
                .unwrap_or_else(|| panic!("{}: plan.json has no list `categorical` (the columns that split as categories; [] for none)", dir.display()))
                .iter()
                .map(|x| x.as_u64().expect("`categorical` lists column numbers") as usize)
                .collect(),
            maps: v["maps"].as_array().unwrap().iter().map(|m| PlanMap { file: path(&m["file"]), domain: m["domain"].as_u64().unwrap() as usize }).collect(),
            uses: v["uses"]
                .as_array()
                .unwrap()
                .iter()
                .map(|u| PlanUse { file: path(&u["file"]), map: u["map"].as_u64().unwrap() as usize, col_map: path(&u["col_map"]) })
                .collect(),
        }
    }
}

fn threads(count: usize) {
    rayon::ThreadPoolBuilder::new().num_threads(count).build_global().unwrap();
}

/// Each column's two hashes, which are sums over its rows, so equal columns have equal hashes whatever blocks hold them.
fn scan(dir: &Path) {
    let plan = Plan::read(dir);
    threads(plan.threads);
    let started = Instant::now();
    let weight = |seed: u64, row: usize| mix(seed ^ mix(row as u64));
    let blocks: Vec<(Vec<u64>, Vec<u64>, Vec<u32>)> = plan
        .maps
        .iter()
        .map(|m| {
            let of: Vec<u32> = read_all(&m.file);
            assert_eq!(of.len(), plan.rows, "{}", m.file.display());
            let (mut w0, mut w1, mut rows) = (vec![0u64; m.domain], vec![0u64; m.domain], vec![0u32; m.domain]);
            for (row, &block) in of.iter().enumerate() {
                if block != NONE {
                    let b = block as usize;
                    w0[b] = w0[b].wrapping_add(weight(11, row));
                    w1[b] = w1[b].wrapping_add(weight(13, row));
                    rows[b] += 1;
                }
            }
            (w0, w1, rows)
        })
        .collect();
    type Sums = (Vec<u64>, Vec<u64>, Vec<u64>, Vec<u64>, Vec<u64>);
    let empty = || -> Sums {
        let c = plan.columns;
        (vec![0; c], vec![0; c], vec![0; c], vec![0; c], vec![0; c])
    };
    let sums = plan
        .uses
        .par_iter()
        .map(|u| {
            let col_map: Vec<i32> = read_all(&u.col_map);
            let (w0, w1, rows) = &blocks[u.map];
            let mut out = empty();
            let read = Records::open(&u.file).for_each_row(|block, columns, values| {
                if rows[block] == 0 {
                    return;
                }
                for (&column, &value) in columns.iter().zip(values) {
                    let c = col_map[column as usize];
                    if c < 0 || value == 0.0 {
                        continue;
                    }
                    let c = c as usize;
                    let bits = if value.is_nan() { u64::MAX } else { value.to_bits() as u64 };
                    let hashed = mix(bits);
                    out.0[c] = out.0[c].wrapping_add(hashed.wrapping_mul(w0[block]));
                    out.1[c] = out.1[c].wrapping_add(hashed.wrapping_mul(w1[block]));
                    out.2[c] += rows[block] as u64;
                    out.3[c] += 1;
                    if value.is_nan() {
                        out.4[c] += 1;
                    }
                }
            });
            assert_eq!(read, plan.maps[u.map].domain, "{}", u.file.display());
            println!("scan {} {:.0}s", u.file.display(), started.elapsed().as_secs_f64());
            out
        })
        .reduce(empty, |mut a, b| {
            for c in 0..plan.columns {
                a.0[c] = a.0[c].wrapping_add(b.0[c]);
                a.1[c] = a.1[c].wrapping_add(b.1[c]);
                a.2[c] += b.2[c];
                a.3[c] += b.3[c];
                a.4[c] += b.4[c];
            }
            a
        });
    write_all(&dir.join("hash0.u64"), &sums.0);
    write_all(&dir.join("hash1.u64"), &sums.1);
    write_all(&dir.join("count.u64"), &sums.2);
    write_all(&dir.join("entries.u64"), &sums.3);
    write_all(&dir.join("nans.u64"), &sums.4);
}

/// The upper bounds of at most `max_bin` bins over ascending values, as LightGBM's greedy search finds them.
fn greedy_bounds(values: &[f64], counts: &[f64], max_bin: usize, total: f64) -> Vec<f64> {
    let n = values.len();
    let mut bounds = Vec::new();
    if n == 0 || max_bin <= 1 {
        bounds.push(f64::INFINITY);
        return bounds;
    }
    if n <= max_bin {
        let mut current = 0.0;
        for i in 0..n - 1 {
            current += counts[i];
            if current >= MIN_DATA_IN_BIN {
                bounds.push((values[i] + values[i + 1]) / 2.0);
                current = 0.0;
            }
        }
        bounds.push(f64::INFINITY);
        return bounds;
    }
    let max_bin = (((total / MIN_DATA_IN_BIN) as usize).min(max_bin)).max(1);
    if max_bin == 1 {
        bounds.push(f64::INFINITY);
        return bounds;
    }
    let mut mean = total / max_bin as f64;
    let mut rest_bins = max_bin as i64;
    let mut rest = total;
    let large: Vec<bool> = counts.iter().map(|&c| c >= mean).collect();
    for i in 0..n {
        if large[i] {
            rest_bins -= 1;
            rest -= counts[i];
        }
    }
    mean = rest / rest_bins.max(1) as f64;
    let (mut upper, mut lower) = (Vec::new(), vec![values[0]]);
    let mut current = 0.0;
    for i in 0..n - 1 {
        if !large[i] {
            rest -= counts[i];
        }
        current += counts[i];
        if large[i] || current >= mean || (large[i + 1] && current >= (mean * 0.5).max(1.0)) {
            upper.push(values[i]);
            lower.push(values[i + 1]);
            if upper.len() >= max_bin - 1 {
                break;
            }
            current = 0.0;
            if !large[i] {
                rest_bins -= 1;
                mean = rest / rest_bins.max(1) as f64;
            }
        }
    }
    for i in 0..upper.len() {
        bounds.push((upper[i] + lower[i + 1]) / 2.0);
    }
    bounds.push(f64::INFINITY);
    bounds
}

/// A column's upper bounds with its default bin among them, and that bin's place.
fn column_bounds(values: &[f64], counts: &[f64], max_bin: usize, has_nan: bool) -> (Vec<f64>, u32) {
    let negative = values.partition_point(|&v| v < 0.0);
    let left_total: f64 = counts[..negative].iter().sum();
    let right_total: f64 = counts[negative..].iter().sum();
    let room = max_bin.saturating_sub(1 + has_nan as usize).max(1);
    let mut bounds = Vec::new();
    if negative > 0 {
        let share = left_total / (left_total + right_total);
        let left_bins = ((share * room as f64) as usize).max(1);
        bounds = greedy_bounds(&values[..negative], &counts[..negative], left_bins, left_total);
        *bounds.last_mut().unwrap() = -ZERO;
    }
    let zero = bounds.len() as u32;
    if negative < values.len() {
        bounds.push(ZERO);
        let right_bins = room.saturating_sub(zero as usize).max(1);
        bounds.extend(greedy_bounds(&values[negative..], &counts[negative..], right_bins, right_total));
    } else {
        bounds.push(f64::INFINITY);
    }
    (bounds, zero)
}

/// A categorical column's upper bounds: its default bin (the value 0), then one bound for each value that has an entry, which is that value. A value's place
/// is the place of the first bound at or above it, and a value with no bound of its own has no category.
fn category_bounds(k: usize, values: &[f64]) -> (Vec<f64>, u32) {
    let mut bounds = vec![ZERO];
    for &value in values {
        assert!(value > 0.0 && value == value.trunc(), "categorical column {k} holds {value}, which is not a whole number of at least 0");
        bounds.push(value);
    }
    (bounds, 0)
}

/// Which kept columns are categorical: 1 for each, else 0.
fn categorical_of(plan: &Plan, keep: &[i32], kept: usize) -> Vec<u8> {
    let mut categorical = vec![0u8; kept];
    for &column in &plan.categorical {
        assert!(column < keep.len(), "plan.json: categorical column {column} is not a column");
        assert!(keep[column] >= 0, "plan.json: categorical column {column} is not kept");
        categorical[keep[column] as usize] = 1;
    }
    categorical
}

#[derive(Clone, Copy)]
struct Sample {
    column: u32,
    value: f32,
    weight: u32,
}

/// One sample for each value of each column, weighing what they weighed. A column holds few distinct values, so this keeps
/// a column's whole distribution in far less memory than its entries take.
fn merge_samples(samples: &mut Vec<Sample>) {
    samples.par_sort_unstable_by(|a, b| a.column.cmp(&b.column).then(a.value.total_cmp(&b.value)));
    samples.dedup_by(|later, kept| {
        let same = later.column == kept.column && later.value == kept.value;
        if same {
            kept.weight += later.weight;
        }
        same
    });
}

/// Bins from a sample of each column's values, at most `sample_cap` of them, so a rare column keeps every value it has.
fn find_bins(dir: &Path, plan: &Plan, keep: &[i32], kept: usize, categorical: &[u8]) {
    let started = Instant::now();
    let entries: Vec<u64> = read_all(&dir.join("entries.u64"));
    let nans: Vec<u64> = read_all(&dir.join("nans.u64"));
    let rows_of: Vec<Vec<u32>> = plan
        .maps
        .iter()
        .map(|m| {
            let of: Vec<u32> = read_all(&m.file);
            let mut rows = vec![0u32; m.domain];
            for &block in &of {
                if block != NONE {
                    rows[block as usize] += 1;
                }
            }
            rows
        })
        .collect();
    let mut samples: Vec<Sample> = plan
        .uses
        .par_iter()
        .enumerate()
        .map(|(place, u)| {
            let col_map: Vec<i32> = read_all(&u.col_map);
            let rows = &rows_of[u.map];
            let mut random = Random(mix(place as u64 + 1));
            let mut out = Vec::new();
            let mut limit = 1usize << 26;
            Records::open(&u.file).for_each_row(|block, columns, values| {
                if rows[block] == 0 {
                    return;
                }
                for (&column, &value) in columns.iter().zip(values) {
                    let logical = col_map[column as usize];
                    if logical < 0 || value == 0.0 || value.is_nan() {
                        continue;
                    }
                    let k = keep[logical as usize];
                    if k < 0 {
                        continue;
                    }
                    let held = entries[logical as usize];
                    // A categorical column keeps every value it has.
                    if categorical[k as usize] != 0 || held <= plan.sample_cap || random.unit() < plan.sample_cap as f64 / held as f64 {
                        out.push(Sample { column: k as u32, value, weight: rows[block] });
                    }
                }
                if out.len() >= limit {
                    merge_samples(&mut out);
                    limit = limit.max(2 * out.len());
                }
            });
            merge_samples(&mut out);
            out
        })
        .reduce(Vec::new, |mut a, mut b| {
            if a.len() < b.len() {
                std::mem::swap(&mut a, &mut b);
            }
            a.extend(b);
            a
        });
    println!("samples {} {:.0}s", samples.len(), started.elapsed().as_secs_f64());
    samples.par_sort_unstable_by(|a, b| a.column.cmp(&b.column).then(a.value.total_cmp(&b.value)));
    let mut starts = vec![0usize; kept + 1];
    for sample in &samples {
        starts[sample.column as usize + 1] += 1;
    }
    for k in 0..kept {
        starts[k + 1] += starts[k];
    }
    let mut has_nan = vec![0u8; kept];
    for (logical, &k) in keep.iter().enumerate() {
        // A categorical column has a bin for the NaN and for the values that it had no entry for in the fit.
        if k >= 0 && (nans[logical] > 0 || categorical[k as usize] != 0) {
            has_nan[k as usize] = 1;
        }
    }
    let found: Vec<(Vec<f64>, u32)> = (0..kept)
        .into_par_iter()
        .map(|k| {
            let here = &samples[starts[k]..starts[k + 1]];
            let (mut values, mut counts): (Vec<f64>, Vec<f64>) = (Vec::new(), Vec::new());
            for sample in here {
                let value = sample.value as f64;
                if values.last() == Some(&value) {
                    *counts.last_mut().unwrap() += sample.weight as f64;
                } else {
                    values.push(value);
                    counts.push(sample.weight as f64);
                }
            }
            if categorical[k] != 0 { category_bounds(k, &values) } else { column_bounds(&values, &counts, plan.max_bin, has_nan[k] != 0) }
        })
        .collect();
    let (mut bound_start, mut col_start, mut zero_pos) = (vec![0u32; kept + 1], vec![0u32; kept + 1], vec![0u32; kept]);
    let mut bounds = Vec::new();
    for (k, (here, zero)) in found.iter().enumerate() {
        bounds.extend_from_slice(here);
        bound_start[k + 1] = bounds.len() as u32;
        zero_pos[k] = *zero;
        col_start[k + 1] = col_start[k] + (here.len() - 1) as u32 + has_nan[k] as u32;
    }
    write_all(&dir.join("bounds.f64"), &bounds);
    write_all(&dir.join("bound_start.u32"), &bound_start);
    write_all(&dir.join("col_start.u32"), &col_start);
    write_all(&dir.join("zero_pos.u32"), &zero_pos);
    write_all(&dir.join("has_nan.u8"), &has_nan);
    println!("bins {} over {kept} columns {:.0}s", col_start[kept], started.elapsed().as_secs_f64());
}

/// Writes each block's entries as their bins' numbers, ascending, and each row's block in each map.
fn compile(dir: &Path) {
    let plan = Plan::read(dir);
    threads(plan.threads);
    let started = Instant::now();
    let keep: Vec<i32> = read_all(&dir.join("keep.i32"));
    let kept = keep.iter().map(|&k| k + 1).max().unwrap_or(0) as usize;
    let source = match &plan.reference {
        Some(train) => train.clone(),
        None => {
            find_bins(dir, &plan, &keep, kept, &categorical_of(&plan, &keep, kept));
            dir.to_path_buf()
        }
    };
    // A set that has a reference splits the columns as the reference's set does.
    let categorical: Vec<u8> = match &plan.reference {
        Some(_) => read_all(&source.join("categorical.u8")),
        None => categorical_of(&plan, &keep, kept),
    };
    assert_eq!(categorical.len(), kept, "{}: categorical.u8 has an entry for each kept column", source.display());
    write_all(&dir.join("categorical.u8"), &categorical);
    let bounds: Vec<f64> = read_all(&source.join("bounds.f64"));
    let bound_start: Vec<u32> = read_all(&source.join("bound_start.u32"));
    let col_start: Vec<u32> = read_all(&source.join("col_start.u32"));
    let zero_pos: Vec<u32> = read_all(&source.join("zero_pos.u32"));
    let has_nan: Vec<u8> = read_all(&source.join("has_nan.u8"));
    if plan.reference.is_some() {
        write_all(&dir.join("col_start.u32"), &col_start);
        write_all(&dir.join("zero_pos.u32"), &zero_pos);
        write_all(&dir.join("has_nan.u8"), &has_nan);
    }
    // Each map's blocks are numbered by the rows that point to them, in their order in the source.
    let compact: Vec<Vec<u32>> = plan
        .maps
        .iter()
        .enumerate()
        .map(|(m, map)| {
            let of: Vec<u32> = read_all(&map.file);
            let mut used = vec![false; map.domain];
            for &block in &of {
                if block != NONE {
                    used[block as usize] = true;
                }
            }
            let mut count = 0u32;
            let numbers: Vec<u32> = used
                .iter()
                .map(|&here| {
                    if here {
                        count += 1;
                        count - 1
                    } else {
                        NONE
                    }
                })
                .collect();
            let numbered: Vec<u32> = of.iter().map(|&block| if block == NONE { NONE } else { numbers[block as usize] }).collect();
            write_all(&dir.join(format!("map{m}.blocks.u32")), &numbered);
            numbers
        })
        .collect();
    let per_use: Vec<(Vec<bool>, Vec<u32>, u32, u32)> = plan
        .uses
        .par_iter()
        .enumerate()
        .map(|(place, u)| {
            let col_map: Vec<i32> = read_all(&u.col_map);
            let numbers = &compact[u.map];
            let working = dir.join(format!("use{place}.bid.working"));
            let mut sink = BufWriter::with_capacity(1 << 22, File::create(&working).unwrap());
            let mut ptr: Vec<u64> = vec![0];
            let mut written = 0u64;
            let mut has_column = vec![false; kept];
            let mut count = vec![0u32; kept];
            let mut held: Vec<u32> = Vec::new();
            let (mut least, mut most) = (u32::MAX, 0u32);
            Records::open(&u.file).for_each_row(|block, columns, values| {
                if numbers[block] == NONE {
                    return;
                }
                held.clear();
                for (&column, &value) in columns.iter().zip(values) {
                    let logical = col_map[column as usize];
                    if logical < 0 || value == 0.0 {
                        continue;
                    }
                    let k = keep[logical as usize];
                    if k < 0 {
                        continue;
                    }
                    let k = k as usize;
                    let bid = if value.is_nan() {
                        if has_nan[k] == 0 {
                            continue;
                        }
                        col_start[k + 1] - 1
                    } else if categorical[k] != 0 {
                        let x = value as f64;
                        assert!(x >= 0.0 && x == x.trunc(), "categorical column {k} holds {x}, which is not a whole number of at least 0");
                        let here = &bounds[bound_start[k] as usize..bound_start[k + 1] as usize];
                        let place = here.partition_point(|&bound| bound < x);
                        // A value that the fit had no entry for stands in the last bin, with the NaN.
                        if here.get(place) == Some(&x) { col_start[k] + place as u32 - 1 } else { col_start[k + 1] - 1 }
                    } else {
                        let here = &bounds[bound_start[k] as usize..bound_start[k + 1] as usize];
                        let x = value as f64;
                        let place = here.partition_point(|&bound| bound < x) as u32;
                        let zero = zero_pos[k];
                        if place == zero {
                            continue;
                        }
                        col_start[k] + if place < zero { place } else { place - 1 }
                    };
                    held.push(bid);
                    has_column[k] = true;
                    count[k] += 1;
                }
                held.sort_unstable();
                if let (Some(&first), Some(&last)) = (held.first(), held.last()) {
                    least = least.min(first);
                    most = most.max(last);
                }
                sink.write_all(bytes_of(&held)).unwrap();
                written += held.len() as u64;
                ptr.push(written);
            });
            sink.flush().unwrap();
            drop(sink);
            fs::rename(&working, dir.join(format!("use{place}.bid.u32"))).unwrap();
            write_all(&dir.join(format!("use{place}.ptr.u64")), &ptr);
            println!("compile {} blocks {} entries {written} {:.0}s", u.file.display(), ptr.len() - 1, started.elapsed().as_secs_f64());
            (has_column, count, least, most)
        })
        .collect();
    let (mut col_uses, mut col_entries) = (vec![0u64; kept], vec![0u64; kept]);
    assert!(plan.uses.len() <= 64, "a column's uses are a mask of 64");
    for (place, (has_column, count, _, _)) in per_use.iter().enumerate() {
        for k in 0..kept {
            if has_column[k] {
                col_uses[k] |= 1u64 << place;
            }
            col_entries[k] += count[k] as u64;
        }
    }
    write_all(&dir.join("col_uses.u64"), &col_uses);
    write_all(&dir.join("col_entries.u64"), &col_entries);
    let meta = json!({
        "rows": plan.rows,
        "kept": kept,
        "bins": col_start[kept],
        "maps": plan.maps.len(),
        "uses": plan.uses.iter().enumerate().map(|(place, u)| json!({"map": u.map, "least": per_use[place].2, "most": per_use[place].3})).collect::<Vec<_>>(),
    });
    fs::write(dir.join("compiled.json"), meta.to_string()).unwrap();
    println!("compiled {} entries {:.0}s", col_entries.iter().sum::<u64>(), started.elapsed().as_secs_f64());
}

struct UseData {
    map: usize,
    ptr: Mapped<u64>,
    bid: Mapped<u32>,
}

struct Store {
    rows: usize,
    kept: usize,
    bins: usize,
    col_start: Vec<u32>,
    zero_pos: Vec<u32>,
    has_nan: Vec<u8>,
    /// 1 for a categorical column. Its places are its values: place 0 is the value 0 (the default bin), place p the p-th value with an entry, and the last bin
    /// (the NaN bin) holds the NaN and the values with no place.
    categorical: Vec<u8>,
    col_uses: Vec<u64>,
    col_entries: Vec<u64>,
    maps: Vec<Mapped<u32>>,
    uses: Vec<UseData>,
}

impl Store {
    fn open(dir: &Path) -> Store {
        let meta = read_json(&dir.join("compiled.json"));
        let store = Store {
            rows: meta["rows"].as_u64().unwrap() as usize,
            kept: meta["kept"].as_u64().unwrap() as usize,
            bins: meta["bins"].as_u64().unwrap() as usize,
            col_start: read_all(&dir.join("col_start.u32")),
            zero_pos: read_all(&dir.join("zero_pos.u32")),
            has_nan: read_all(&dir.join("has_nan.u8")),
            categorical: read_all(&dir.join("categorical.u8")),
            col_uses: read_all(&dir.join("col_uses.u64")),
            col_entries: read_all(&dir.join("col_entries.u64")),
            maps: (0..meta["maps"].as_u64().unwrap()).map(|m| Mapped::open(&dir.join(format!("map{m}.blocks.u32")))).collect(),
            uses: meta["uses"]
                .as_array()
                .unwrap()
                .iter()
                .enumerate()
                .map(|(place, u)| UseData {
                    map: u["map"].as_u64().unwrap() as usize,
                    ptr: Mapped::open(&dir.join(format!("use{place}.ptr.u64"))),
                    bid: Mapped::open(&dir.join(format!("use{place}.bid.u32"))),
                })
                .collect(),
        };
        assert_eq!(store.categorical.len(), store.kept, "{}: categorical.u8 has an entry for each column", dir.display());
        for k in 0..store.kept {
            assert!(store.categorical[k] == 0 || (store.zero_pos[k] == 0 && store.has_nan[k] != 0), "categorical column {k} has its default bin first and a NaN bin");
        }
        store
    }

    /// Whether a row goes left at a split: the cut sends its value's place among the column's bins left. A NaN goes the way `default_left` says.
    #[inline]
    fn left(&self, row: u32, column: u32, cut: &Cut, default_left: bool) -> bool {
        let k = column as usize;
        let (start, end) = (self.col_start[k], self.col_start[k + 1]);
        let zero = self.zero_pos[k];
        let mut mask = self.col_uses[k];
        while mask != 0 {
            let place = mask.trailing_zeros() as usize;
            mask &= mask - 1;
            let data = &self.uses[place];
            let block = self.maps[data.map][row as usize];
            if block == NONE {
                continue;
            }
            let b = block as usize;
            let entries = &data.bid[data.ptr[b] as usize..data.ptr[b + 1] as usize];
            let at = entries.partition_point(|&x| x < start);
            if at < entries.len() && entries[at] < end {
                let bid = entries[at];
                if self.has_nan[k] != 0 && bid == end - 1 {
                    return default_left;
                }
                let index = bid - start;
                let place = if index < zero { index } else { index + 1 };
                return cut.left(place);
            }
        }
        cut.left(zero)
    }
}

/// How a split sends the places of its column.
#[derive(Clone, Debug)]
enum Cut {
    /// The places up to this one go left.
    Upto(u32),
    /// The places whose bit is set go left: bit `p % 64` of word `p / 64` is place p. The column's NaN bin is not a place, and goes right.
    Set(Vec<u64>),
}

impl Cut {
    #[inline]
    fn left(&self, place: u32) -> bool {
        match self {
            Cut::Upto(pos) => place <= *pos,
            Cut::Set(bits) => bits[(place >> 6) as usize] >> (place & 63) & 1 != 0,
        }
    }
}

#[derive(Clone, Copy, Default)]
#[repr(C)]
struct Bin {
    g: f64,
    h: f64,
}

#[derive(Clone)]
struct Split {
    column: u32,
    cut: Cut,
    default_left: bool,
    gain: f64,
    left_g: f64,
    left_h: f64,
    /// The `lambda_l2` of the leaf values that the split makes: the fit's, and for a categorical split with sorted categories, that and `cat_l2`, as in LightGBM.
    child_l2: f64,
}

struct Config {
    learning_rate: f64,
    num_leaves: usize,
    min_data_in_leaf: f64,
    min_sum_hessian: f64,
    /// LightGBM's `lambda_l2`: a leaf's output is -G/(H + lambda_l2). 0 asks for none.
    lambda_l2: f64,
    /// LightGBM's `max_delta_step`: a leaf's output, before the learning rate, is at most this in size. 0 asks for no limit.
    max_delta_step: f64,
    fraction: f64,
    truncation: usize,
    max_rounds: usize,
    patience: usize,
    admit: Option<Admit>,
    /// Where a fit's first run writes each tree as it is made.
    stream: Option<PathBuf>,
    /// The least count of tasks on each side of a split, and each row's task. 0 asks for no such test.
    min_tasks: usize,
    row_task: Vec<u32>,
    categorical: CategoricalConfig,
}

/// The parameters of a categorical split, with their meaning and default values in LightGBM.
struct CategoricalConfig {
    /// `max_cat_threshold` (32): the most categories that one side of a split holds.
    max_cat_threshold: usize,
    /// `cat_l2` (10): added to `lambda_l2` when the gain of a split of sorted categories is found, and in the values of its two leaves.
    cat_l2: f64,
    /// `cat_smooth` (10): a category is considered where it holds at least this many rows, and categories are sorted by G / (H + cat_smooth).
    cat_smooth: f64,
    /// `max_cat_to_onehot` (4): a column with this many bins or fewer is split as one category against the others.
    max_cat_to_onehot: usize,
    /// `min_data_per_group` (100): the least count of rows in the categories that the scan adds between two splits that it considers, and on the right of a split.
    min_data_per_group: f64,
}

impl CategoricalConfig {
    /// From the settings JSON, where each parameter that is left out has LightGBM's default.
    fn read(v: &Value) -> CategoricalConfig {
        CategoricalConfig {
            max_cat_threshold: v["max_cat_threshold"].as_u64().unwrap_or(32) as usize,
            cat_l2: v["cat_l2"].as_f64().unwrap_or(10.0),
            cat_smooth: v["cat_smooth"].as_f64().unwrap_or(10.0),
            max_cat_to_onehot: v["max_cat_to_onehot"].as_u64().unwrap_or(4) as usize,
            min_data_per_group: v["min_data_per_group"].as_f64().unwrap_or(100.0),
        }
    }

    /// The parameters as numbers, for the fingerprint of a fit.
    fn bits(&self) -> [u64; 5] {
        [self.max_cat_threshold as u64, self.cat_l2.to_bits(), self.cat_smooth.to_bits(), self.max_cat_to_onehot as u64, self.min_data_per_group.to_bits()]
    }
}

/// A leaf's output before the learning rate: -G/(H + l2), with `l2` the L2 term (`lambda_l2`, or more for a leaf of a categorical split), limited to +-max_delta_step where that is above 0.
fn leaf_output_l2(g: f64, h: f64, l2: f64, config: &Config) -> f64 {
    let output = -g / (h + l2);
    if config.max_delta_step > 0.0 { output.clamp(-config.max_delta_step, config.max_delta_step) } else { output }
}

/// What a leaf adds to the sum of gains, as LightGBM's `GetLeafGain`: G^2/(H + lambda_l2), and with max_delta_step the gain of the limited output w,
/// -(2 G w + (H + lambda_l2) w^2).
fn leaf_gain(g: f64, h: f64, config: &Config) -> f64 {
    leaf_gain_l2(g, h, config.lambda_l2, config)
}

/// `leaf_gain` with the L2 term `l2`.
fn leaf_gain_l2(g: f64, h: f64, l2: f64, config: &Config) -> f64 {
    if config.max_delta_step > 0.0 {
        let w = leaf_output_l2(g, h, l2, config);
        -(2.0 * g * w + (h + l2) * w * w)
    } else {
        g * g / (h + l2)
    }
}

/// Which columns a fit starts with, and which columns a split on a column admits.
struct Admit {
    first: Vec<u8>,
    ptr: Vec<u32>,
    child: Vec<u32>,
}

impl Admit {
    fn open(dir: &str) -> Admit {
        let dir = Path::new(dir);
        Admit { first: read_all(&dir.join("first.u8")), ptr: read_all(&dir.join("ptr.u32")), child: read_all(&dir.join("child.u32")) }
    }
}

#[derive(Default)]
struct Tree {
    column: Vec<u32>,
    cut: Vec<Cut>,
    default_left: Vec<bool>,
    left: Vec<i32>,
    right: Vec<i32>,
    gain: Vec<f64>,
    value: Vec<f64>,
    /// The L2 term of each leaf's value.
    leaf_l2: Vec<f64>,
}

impl Tree {
    fn leaf_of(&self, store: &Store, row: u32) -> usize {
        if self.column.is_empty() {
            return 0;
        }
        let mut node = 0i32;
        loop {
            let n = node as usize;
            node = if store.left(row, self.column[n], &self.cut[n], self.default_left[n]) { self.left[n] } else { self.right[n] };
            if node < 0 {
                return !node as usize;
            }
        }
    }
}

/// A leaf's items' sums per block of one map.
struct Sums {
    g: Vec<f64>,
    h: Vec<f64>,
    seen: Vec<bool>,
    /// The blocks that hold an item of the leaf, in ascending order.
    touched: Vec<u32>,
    /// A large leaf's items, grouped by the owner of their block, while the sums are added.
    bucket: Vec<u32>,
}

/// What a tree is grown over. An item has one block in each map, a gradient and a Hessian, and stands for one or more rows. A row's leaf depends on
/// its blocks alone, so rows with the same blocks are one item (`PairItems`), or each row is an item (`RowItems`).
trait Items: Sync {
    /// The count of items: item numbers are below it.
    fn count(&self) -> usize;
    /// The item's block in the map, or NONE.
    fn block(&self, map: usize, item: u32) -> u32;
    /// The item's gradient and Hessian sums.
    fn weight(&self, item: u32) -> (f64, f64);
    /// The count of rows the item stands for.
    fn rows(&self, item: u32) -> usize;
    /// The item that stands for the row.
    fn item_of_row(&self, row: u32) -> u32;
    /// The map in whose blocks the item numbers go up (a block's items stand together), if there is one.
    fn sorted_map(&self) -> Option<usize> {
        None
    }
}

/// Each row is an item.
struct RowItems<'a> {
    store: &'a Store,
    grad: &'a [f32],
    hess: &'a [f32],
}

impl Items for RowItems<'_> {
    #[inline]
    fn count(&self) -> usize {
        self.store.rows
    }
    #[inline]
    fn block(&self, map: usize, item: u32) -> u32 {
        self.store.maps[map][item as usize]
    }
    #[inline]
    fn weight(&self, item: u32) -> (f64, f64) {
        (self.grad[item as usize] as f64, self.hess[item as usize] as f64)
    }
    #[inline]
    fn rows(&self, _item: u32) -> usize {
        1
    }
    #[inline]
    fn item_of_row(&self, row: u32) -> u32 {
        row
    }
}

/// The distinct tuples of a row's blocks, one in each map, in ascending order of the tuple (the block in the map with the most blocks first, and a row with
/// no block in that map last), and which rows have each.
struct Pairs {
    maps: usize,
    /// The map whose blocks order the pairs: pair numbers go up with the block in this map.
    primary: usize,
    /// Pair p has block `block[p * maps + m]` in map m.
    block: Vec<u32>,
    /// Pair p has the rows `rows[start[p]..start[p + 1]]`, in ascending order.
    start: Vec<u32>,
    rows: Vec<u32>,
    /// The pair of each row.
    row_pair: Vec<u32>,
}

impl Pairs {
    fn build(store: &Store) -> Pairs {
        let maps = store.maps.len();
        assert!(maps >= 1, "a store has a map");
        assert!(store.rows < u32::MAX as usize, "a row number has 32 bits");
        let rows = store.rows;
        // The map with the most blocks orders the pairs: a leaf's items then go through that map's blocks in ascending order, which a pass over the
        // blocks' entries reads in memory order.
        let block_counts: Vec<usize> = store.maps.iter().map(|map| map[..].par_iter().filter(|&&b| b != NONE).map(|&b| b as usize + 1).max().unwrap_or(0)).collect();
        let primary = (0..maps).max_by_key(|&m| (block_counts[m], std::cmp::Reverse(m))).unwrap();
        let others: Vec<usize> = (0..maps).filter(|&m| m != primary).collect();
        let first = &store.maps[primary];
        // The rows with no block in that map stand in the last bucket.
        let buckets = block_counts[primary] + 1;
        let bucket_of = |row: usize| if first[row] == NONE { buckets - 1 } else { first[row] as usize };
        let mut offset = vec![0u32; buckets + 1];
        for row in 0..rows {
            offset[bucket_of(row) + 1] += 1;
        }
        for b in 0..buckets {
            offset[b + 1] += offset[b];
        }
        let mut sorted = vec![0u32; rows];
        {
            let mut next = offset.clone();
            for row in 0..rows {
                let b = bucket_of(row);
                sorted[next[b] as usize] = row as u32;
                next[b] += 1;
            }
        }
        // In each bucket the rows go in ascending order of their blocks in the other maps, then of their numbers. A run of equal blocks is a pair, and
        // the record of a group of buckets lists each run as its place in its bucket and its blocks in the other maps; `runs` gives the count of runs of
        // each bucket.
        const GROUP: usize = 1024;
        let groups = buckets.div_ceil(GROUP);
        let group_range = |g: usize| (g * GROUP, ((g + 1) * GROUP).min(buckets));
        let results: Vec<(Vec<u32>, Vec<u32>)> = {
            let mut slices: Vec<&mut [u32]> = Vec::with_capacity(groups);
            let mut rest = sorted.as_mut_slice();
            for g in 0..groups {
                let (low, high) = group_range(g);
                let (here, after) = rest.split_at_mut((offset[high] - offset[low]) as usize);
                slices.push(here);
                rest = after;
            }
            slices
                .par_iter_mut()
                .enumerate()
                .map(|(g, slice)| {
                    let (low, high) = group_range(g);
                    let (mut record, mut runs) = (Vec::new(), Vec::with_capacity(high - low));
                    let (mut keys, mut order, mut ordered) = (Vec::new(), Vec::new(), Vec::new());
                    let k = others.len();
                    for b in low..high {
                        let here = &mut slice[(offset[b] - offset[low]) as usize..(offset[b + 1] - offset[low]) as usize];
                        let n = here.len();
                        if n == 0 {
                            runs.push(0);
                            continue;
                        }
                        if k == 0 {
                            record.push(0);
                            runs.push(1);
                            continue;
                        }
                        keys.clear();
                        keys.extend(here.iter().flat_map(|&r| others.iter().map(move |&m| store.maps[m][r as usize])));
                        order.clear();
                        order.extend(0..n as u32);
                        if n > 1 {
                            order.sort_unstable_by(|&a, &b| keys[a as usize * k..][..k].cmp(&keys[b as usize * k..][..k]).then(a.cmp(&b)));
                            ordered.clear();
                            ordered.extend(order.iter().map(|&i| here[i as usize]));
                            here.copy_from_slice(&ordered);
                        }
                        let mut count = 0u32;
                        let mut previous: Option<&[u32]> = None;
                        for (place, &i) in order.iter().enumerate() {
                            let key = &keys[i as usize * k..][..k];
                            if previous != Some(key) {
                                record.push(place as u32);
                                record.extend_from_slice(key);
                                previous = Some(key);
                                count += 1;
                            }
                        }
                        runs.push(count);
                    }
                    (record, runs)
                })
                .collect()
        };
        let mut first_pair = vec![0usize; groups + 1];
        for g in 0..groups {
            first_pair[g + 1] = first_pair[g] + results[g].0.len() / maps;
        }
        let count = first_pair[groups];
        assert!(count < u32::MAX as usize, "a pair number has 32 bits");
        let mut block = vec![0u32; count * maps];
        let mut start = vec![0u32; count + 1];
        let mut row_pair = vec![0u32; rows];
        {
            let (block_out, start_out, row_out) = (Disjoint(block.as_mut_ptr()), Disjoint(start.as_mut_ptr()), Disjoint(row_pair.as_mut_ptr()));
            let (offset, first_pair, sorted, results, others) = (&offset, &first_pair, &sorted, &results, &others);
            (0..groups).into_par_iter().for_each(|g| {
                let (low, high) = group_range(g);
                let (record, runs) = (&results[g].0, &results[g].1);
                let (mut p, mut at) = (first_pair[g], 0usize);
                for b in low..high {
                    let n = (offset[b + 1] - offset[b]) as usize;
                    let count = runs[b - low] as usize;
                    for i in 0..count {
                        let place = record[(at + i) * maps] as usize;
                        let to = if i + 1 < count { record[(at + i + 1) * maps] as usize } else { n };
                        // Each group writes the pairs and the rows of its own.
                        unsafe {
                            *start_out.at(p) = offset[b] + place as u32;
                            *block_out.at(p * maps + primary) = if b == buckets - 1 { NONE } else { b as u32 };
                            for (j, &m) in others.iter().enumerate() {
                                *block_out.at(p * maps + m) = record[(at + i) * maps + 1 + j];
                            }
                            for &row in &sorted[offset[b] as usize + place..offset[b] as usize + to] {
                                *row_out.at(row as usize) = p as u32;
                            }
                        }
                        p += 1;
                    }
                    at += count;
                }
            });
        }
        start[count] = rows as u32;
        Pairs { maps, primary, block, start, rows: sorted, row_pair }
    }

    fn count(&self) -> usize {
        self.start.len() - 1
    }

    /// A number that stands for the pairs' blocks and the rows' counts, to tell one store's pairs from another's.
    fn fingerprint(&self) -> u64 {
        let parts: Vec<u64> = self.block.par_chunks(1 << 16).map(|chunk| chunk.iter().fold(0u64, |a, &x| mix(a ^ x as u64))).collect();
        let mut hash = mix(self.maps as u64);
        for part in parts {
            hash = mix(hash ^ part);
        }
        let sizes: Vec<u64> = self.start.par_chunks(1 << 16).map(|chunk| chunk.iter().fold(0u64, |a, &x| mix(a ^ x as u64))).collect();
        for part in sizes {
            hash = mix(hash ^ part);
        }
        hash
    }
}

/// Each pair is an item, with the sums `g` and `h` of its rows' gradients and Hessians.
struct PairItems<'a> {
    pairs: &'a Pairs,
    g: &'a [f64],
    h: &'a [f64],
}

impl Items for PairItems<'_> {
    #[inline]
    fn count(&self) -> usize {
        self.pairs.count()
    }
    #[inline]
    fn block(&self, map: usize, item: u32) -> u32 {
        self.pairs.block[item as usize * self.pairs.maps + map]
    }
    #[inline]
    fn weight(&self, item: u32) -> (f64, f64) {
        (self.g[item as usize], self.h[item as usize])
    }
    #[inline]
    fn rows(&self, item: u32) -> usize {
        (self.pairs.start[item as usize + 1] - self.pairs.start[item as usize]) as usize
    }
    #[inline]
    fn item_of_row(&self, row: u32) -> u32 {
        self.pairs.row_pair[row as usize]
    }
    fn sorted_map(&self) -> Option<usize> {
        Some(self.pairs.primary)
    }
}

/// The sums of each pair's rows' gradients and Hessians, in ascending order of the rows.
fn pair_sums(pairs: &Pairs, grad: &[f32], hess: &[f32], g: &mut [f64], h: &mut [f64]) {
    g.par_iter_mut().zip(h.par_iter_mut()).enumerate().with_min_len(2048).for_each(|(p, (g, h))| {
        let (mut sum_g, mut sum_h) = (0.0f64, 0.0f64);
        for &row in &pairs.rows[pairs.start[p] as usize..pairs.start[p + 1] as usize] {
            sum_g += grad[row as usize] as f64;
            sum_h += hess[row as usize] as f64;
        }
        *g = sum_g;
        *h = sum_h;
    });
}

/// The owners that share the blocks of a map when a large leaf's sums are added.
const OWNERS: usize = 256;
/// A histogram is read from private histograms of parts of the leaf's blocks, one part for each this many blocks, up to `MAX_PARTS`.
const BLOCKS_PER_PART: usize = 8192;
const MAX_PARTS: usize = 32;
/// The private histograms together take at most about this many bytes, so a store with many bins has fewer parts.
const PART_BYTES: usize = 64 << 20;

struct Work {
    sums: Vec<Sums>,
    pool: Vec<Vec<Bin>>,
    seen: Vec<bool>,
    /// Private histograms of zeros, for the parts of a large leaf's blocks.
    parts: Vec<Vec<Bin>>,
    indices: Vec<u32>,
    scratch: Vec<u32>,
    flags: Vec<bool>,
    /// For each use, what the latest split's column holds at each of its blocks (see `SplitTest`).
    memo: Vec<Vec<AtomicU32>>,
    stamp: u32,
    /// The columns are in `groups` runs of columns, `group_of[k]` being the run of column k. For each use, where each of its blocks' entries cross from one
    /// run to the next, as offsets from the block's first entry: `groups + 1` of them a block. None where a block holds more entries than a u16 counts.
    group_of: Vec<u8>,
    groups: usize,
    offsets: Vec<Option<Vec<u16>>>,
    /// The seconds spent in `partition`, in adding blocks, in filling histograms from them, and in `best_split`.
    time: [f64; 4],
}

/// Where each block of a use crosses from one run of columns to the next (see `Work`): `bounds` are the first bins of the runs, and the bins end.
fn group_offsets(data: &UseData, bounds: &[u32]) -> Option<Vec<u16>> {
    let blocks = data.ptr.len().saturating_sub(1);
    let width = bounds.len();
    if (0..blocks).into_par_iter().any(|b| data.ptr[b + 1] - data.ptr[b] > u16::MAX as u64) {
        return None;
    }
    let mut out = vec![0u16; blocks * width];
    out.par_chunks_mut(width * 4096).enumerate().for_each(|(chunk, part)| {
        for (i, offsets) in part.chunks_mut(width).enumerate() {
            let b = chunk * 4096 + i;
            let entries = &data.bid[data.ptr[b] as usize..data.ptr[b + 1] as usize];
            for (r, &low) in bounds[..width - 1].iter().enumerate() {
                offsets[r] = if low == 0 { 0 } else { entries.partition_point(|&x| x < low) as u16 };
            }
            offsets[width - 1] = entries.len() as u16;
        }
    });
    Some(out)
}

impl Work {
    fn new(store: &Store) -> Work {
        let sums = store
            .maps
            .iter()
            .map(|map| {
                let blocks = map.iter().filter(|&&b| b != NONE).map(|&b| b as usize + 1).max().unwrap_or(0);
                Sums { g: vec![0.0; blocks], h: vec![0.0; blocks], seen: vec![false; blocks], touched: Vec::new(), bucket: Vec::new() }
            })
            .collect();
        let memo = store.uses.iter().map(|_| Vec::new()).collect();
        // About `GROUPS` runs of columns of equal counts.
        const GROUPS: usize = 32;
        let groups = store.kept.clamp(1, GROUPS);
        let first_column: Vec<usize> = (0..=groups).map(|i| store.kept * i / groups).collect();
        let mut group_of = vec![0u8; store.kept];
        for i in 0..groups {
            for k in first_column[i]..first_column[i + 1] {
                group_of[k] = i as u8;
            }
        }
        let bounds: Vec<u32> = first_column.iter().map(|&k| store.col_start[k]).collect();
        let offsets = store.uses.iter().map(|data| group_offsets(data, &bounds)).collect();
        Work { sums, pool: Vec::new(), seen: vec![false; store.bins], parts: Vec::new(), indices: Vec::new(), scratch: Vec::new(), flags: Vec::new(), memo, stamp: 0, group_of, groups, offsets, time: [0.0; 4] }
    }

    /// A `Work` with no arrays, for a fit whose tree steps run on the card.
    fn lean() -> Work {
        Work { sums: Vec::new(), pool: Vec::new(), seen: Vec::new(), parts: Vec::new(), indices: Vec::new(), scratch: Vec::new(), flags: Vec::new(), memo: Vec::new(), stamp: 0, group_of: Vec::new(), groups: 0, offsets: Vec::new(), time: [0.0; 4] }
    }

    /// A histogram of zeros.
    fn take(&mut self, store: &Store) -> Vec<Bin> {
        self.pool.pop().unwrap_or_else(|| vec![Bin::default(); store.bins])
    }

    /// Takes back a histogram and clears it, by the bins it knows it touched, so a small leaf costs what it touched.
    fn give(&mut self, mut hist: Vec<Bin>, touched: Option<Vec<u32>>) {
        match touched {
            Some(list) => {
                for b in list {
                    hist[b as usize] = Bin::default();
                }
            }
            None => hist.par_chunks_mut(1 << 16).for_each(|chunk| chunk.fill(Bin::default())),
        }
        self.pool.push(hist);
    }
}

/// `add_blocks` for a map whose blocks only go up along `here`: a block's items stand together, so one pass over chunks of runs adds them, in their
/// order, and the blocks of a chunk are above the blocks of the chunks before it. Chunks start where a run starts.
fn add_sorted<I: Items>(sums: &mut Sums, items: &I, m: usize, here: &[u32]) {
    const CHUNK: usize = 1 << 16;
    let n = here.len();
    let block_at = |j: usize| items.block(m, here[j]);
    let chunks = n.div_ceil(CHUNK);
    let bounds: Vec<usize> = (0..=chunks)
        .into_par_iter()
        .map(|c| {
            if c == 0 {
                return 0;
            }
            // The items of the block that stands before the chunk go to the chunk before it.
            let j = c * CHUNK;
            if j >= n {
                return n;
            }
            let before = block_at(j - 1);
            (j + here[j..].partition_point(|&item| items.block(m, item) <= before)).min(n)
        })
        .collect();
    let (g, h, seen) = (Disjoint(sums.g.as_mut_ptr()), Disjoint(sums.h.as_mut_ptr()), Disjoint(sums.seen.as_mut_ptr()));
    let lists: Vec<Vec<u32>> = (0..chunks)
        .into_par_iter()
        .map(|c| {
            let mut mine = Vec::new();
            let (mut j, end) = (bounds[c], bounds[c + 1]);
            while j < end {
                let block = block_at(j);
                if block == NONE {
                    // The items with no block come last.
                    j = end;
                    continue;
                }
                debug_assert!(mine.last().is_none_or(|&last| last < block), "the blocks go up");
                let (mut sum_g, mut sum_h) = (0.0f64, 0.0f64);
                while j < end && block_at(j) == block {
                    let (item_g, item_h) = items.weight(here[j]);
                    sum_g += item_g;
                    sum_h += item_h;
                    j += 1;
                }
                // A run lies in one chunk, and a block in one run, so no two chunks write one block's sums.
                unsafe {
                    *g.at(block as usize) = sum_g;
                    *h.at(block as usize) = sum_h;
                    *seen.at(block as usize) = true;
                }
                mine.push(block);
            }
            mine
        })
        .collect();
    sums.touched.extend(lists.into_iter().flatten());
}

/// Adds each item's gradient and Hessian to its block's sums, one map to a thread. `touched` lists the blocks in ascending order. A block's sums add its
/// items in the order of `work.indices`.
fn add_blocks<I: Items>(work: &mut Work, items: &I, range: std::ops::Range<usize>) {
    let here = &work.indices[range];
    work.sums.par_iter_mut().enumerate().for_each(|(m, sums)| {
        if here.len() < 1 << 16 {
            for &item in here {
                let block = items.block(m, item);
                if block == NONE {
                    continue;
                }
                let b = block as usize;
                if !sums.seen[b] {
                    sums.seen[b] = true;
                    sums.touched.push(block);
                }
                let (g, h) = items.weight(item);
                sums.g[b] += g;
                sums.h[b] += h;
            }
            sums.touched.sort_unstable();
            return;
        }
        if items.sorted_map() == Some(m) {
            add_sorted(sums, items, m, here);
            return;
        }
        // The items go to the owner of their block, which adds them in their order, so no two owners write one block's sums. Three passes over the
        // items do it: they count by chunk and owner, they move into buckets, and each owner adds its bucket.
        const CHUNK: usize = 1 << 16;
        let blocks = sums.g.len();
        if blocks == 0 {
            return;
        }
        let owners = OWNERS.min(blocks);
        let owner = |block: u32| (block as u64 * owners as u64 / blocks as u64) as usize;
        let chunks = here.len().div_ceil(CHUNK);
        let mut counts = vec![0u32; chunks * owners];
        counts.par_chunks_mut(owners).zip(here.par_chunks(CHUNK)).for_each(|(count, part)| {
            for &item in part {
                let block = items.block(m, item);
                if block != NONE {
                    count[owner(block)] += 1;
                }
            }
        });
        // Owner o takes the places `first[o]..first[o + 1]`, and chunk c writes at `places[c * owners + o]` on.
        let mut first = vec![0usize; owners + 1];
        for o in 0..owners {
            first[o + 1] = first[o] + (0..chunks).map(|c| counts[c * owners + o] as usize).sum::<usize>();
        }
        let mut places = vec![0usize; chunks * owners];
        for o in 0..owners {
            let mut at = first[o];
            for c in 0..chunks {
                places[c * owners + o] = at;
                at += counts[c * owners + o] as usize;
            }
        }
        if sums.bucket.len() < first[owners] {
            sums.bucket.resize(first[owners], 0);
        }
        {
            let out = Disjoint(sums.bucket.as_mut_ptr());
            places.par_chunks(owners).zip(here.par_chunks(CHUNK)).for_each(|(place, part)| {
                let mut place = place.to_vec();
                for &item in part {
                    let block = items.block(m, item);
                    if block != NONE {
                        let o = owner(block);
                        // Each chunk writes at places that no other chunk writes at.
                        unsafe { *out.at(place[o]) = item };
                        place[o] += 1;
                    }
                }
            });
        }
        let (g, h, seen) = (Disjoint(sums.g.as_mut_ptr()), Disjoint(sums.h.as_mut_ptr()), Disjoint(sums.seen.as_mut_ptr()));
        let bucket = &sums.bucket;
        let first = &first;
        let lists: Vec<Vec<u32>> = (0..owners)
            .into_par_iter()
            .map(|o| {
                let mut mine = Vec::new();
                for &item in &bucket[first[o]..first[o + 1]] {
                    let block = items.block(m, item);
                    let b = block as usize;
                    let (wg, wh) = items.weight(item);
                    // An owner writes the sums of its own blocks.
                    unsafe {
                        if !*seen.at(b) {
                            *seen.at(b) = true;
                            mine.push(block);
                        }
                        *g.at(b) += wg;
                        *h.at(b) += wh;
                    }
                }
                mine.sort_unstable();
                mine
            })
            .collect();
        // Owners take ascending ranges of blocks, so the lists together are in ascending order.
        sums.touched.extend(lists.into_iter().flatten());
    });
}

fn clear_blocks(work: &mut Work) {
    for sums in &mut work.sums {
        for &block in &sums.touched {
            let b = block as usize;
            sums.g[b] = 0.0;
            sums.h[b] = 0.0;
            sums.seen[b] = false;
        }
        sums.touched.clear();
    }
}

/// Adds a block's sums to the bins of `entries`, which all lie in the slice that starts at bin `low`.
#[inline(always)]
fn add_entries<const TRACK: bool>(slice: &mut [Bin], marks: &mut [bool], local: &mut Vec<u32>, entries: &[u32], low: u32, g: f64, h: f64) {
    for &bid in entries {
        // A bid in this range lies inside this slice.
        let bin = unsafe { slice.get_unchecked_mut((bid - low) as usize) };
        bin.g += g;
        bin.h += h;
        if TRACK {
            let mark = unsafe { marks.get_unchecked_mut((bid - low) as usize) };
            if !*mark {
                *mark = true;
                local.push(bid);
            }
        }
    }
}

/// Adds the blocks of part `j` of `parts`, of each use, to `buffer`.
#[inline(never)]
fn fill_part(store: &Store, sums: &[Sums], j: usize, parts: usize, buffer: &mut [Bin]) {
    let (mut no_marks, mut no_list): (Vec<bool>, Vec<u32>) = (Vec::new(), Vec::new());
    for data in &store.uses {
        let held = &sums[data.map];
        let n = held.touched.len();
        for &block in &held.touched[n * j / parts..n * (j + 1) / parts] {
            let b = block as usize;
            let entries = &data.bid[data.ptr[b] as usize..data.ptr[b + 1] as usize];
            add_entries::<false>(buffer, &mut no_marks, &mut no_list, entries, 0, held.g[b], held.h[b]);
        }
    }
}

/// Adds each touched block's sums to the bins of its entries. With `track`, gives each bin that the rows' entries make non-zero, once. (A row with a
/// gradient has a Hessian above 0, so a bin with an entry of such a row has a sum other than 0. A row with a Hessian of 0 and a gradient other than 0
/// would break this, because a bin could sum to 0 and still need its parent's value to be taken from it.)
///
/// A leaf with few blocks adds them in one thread, in ascending order of block. A leaf with many splits its blocks into parts of ascending blocks,
/// adds each part to a private histogram, and then adds the private histograms to `hist`, bin by bin, in the order of the parts.
fn fill_histogram<I: Items>(work: &mut Work, store: &Store, items: &I, range: std::ops::Range<usize>, hist: &mut [Bin], track: bool) -> Vec<u32> {
    let began = Instant::now();
    add_blocks(work, items, range);
    work.time[1] += began.elapsed().as_secs_f64();
    let began = Instant::now();
    let total: usize = store.uses.iter().map(|data| work.sums[data.map].touched.len()).sum();
    let most_parts = (PART_BYTES / (store.bins.max(1) * std::mem::size_of::<Bin>())).clamp(1, MAX_PARTS);
    let parts = (total / BLOCKS_PER_PART).min(most_parts);
    let touched = if parts < 2 {
        let mut marks = std::mem::take(&mut work.seen);
        let mut local = Vec::new();
        for data in &store.uses {
            let held = &work.sums[data.map];
            for &block in &held.touched {
                let b = block as usize;
                let entries = &data.bid[data.ptr[b] as usize..data.ptr[b + 1] as usize];
                if track {
                    add_entries::<true>(hist, &mut marks, &mut local, entries, 0, held.g[b], held.h[b]);
                } else {
                    add_entries::<false>(hist, &mut marks, &mut local, entries, 0, held.g[b], held.h[b]);
                }
            }
        }
        for &b in &local {
            marks[b as usize] = false;
        }
        work.seen = marks;
        local
    } else {
        let mut buffers = std::mem::take(&mut work.parts);
        while buffers.len() < parts {
            buffers.push(vec![Bin::default(); store.bins]);
        }
        {
            let sums = &work.sums;
            buffers[..parts].par_iter_mut().enumerate().for_each(|(j, buffer)| fill_part(store, sums, j, parts, buffer));
        }
        // Each span of bins is added from the private histograms, which it clears, by one thread.
        const SPAN: usize = 4096;
        let pointers: Vec<Disjoint<Bin>> = buffers[..parts].iter_mut().map(|buffer| Disjoint(buffer.as_mut_ptr())).collect();
        let lists: Vec<Vec<u32>> = hist
            .par_chunks_mut(SPAN)
            .enumerate()
            .map(|(c, out)| {
                let mut local = Vec::new();
                for (i, bin) in out.iter_mut().enumerate() {
                    let (mut g, mut h) = (0.0f64, 0.0f64);
                    for part in &pointers {
                        // A span of bins belongs to one thread.
                        unsafe {
                            let x = part.at(c * SPAN + i);
                            g += (*x).g;
                            h += (*x).h;
                            *x = Bin::default();
                        }
                    }
                    bin.g += g;
                    bin.h += h;
                    if track && (bin.g != 0.0 || bin.h != 0.0) {
                        local.push((c * SPAN + i) as u32);
                    }
                }
                local
            })
            .collect();
        work.parts = buffers;
        lists.concat()
    };
    clear_blocks(work);
    work.time[2] += began.elapsed().as_secs_f64();
    touched
}

/// The best split of a column, by the leaf's sums: the column's default bin holds what its other bins do not.
///
/// It scans as LightGBM does: from the highest place down with NaN on the left, and, where the column has NaN, from the
/// lowest place up with NaN on the right. A count is estimated from hessians, so the side a scan sums decides how a count
/// rounds at `min_data_in_leaf`, and the direction decides which of two thresholds of equal gain a split takes.
fn best_in_column(store: &Store, k: usize, hist: &[Bin], total: (f64, f64, f64), config: &Config, parent: f64) -> Option<Split> {
    let (g, h, n) = total;
    let start = store.col_start[k] as usize;
    let bins = &hist[start..store.col_start[k + 1] as usize];
    if bins.is_empty() {
        return None;
    }
    if store.categorical[k] != 0 {
        return best_in_categorical(store, k, bins, total, config, parent);
    }
    let (mut other_g, mut other_h, mut filled) = (0.0, 0.0, 0.0);
    for bin in bins {
        other_g += bin.g;
        other_h += bin.h;
        if bin.h > 0.0 {
            filled += 1.0;
        }
    }
    let sum_h = h + EPSILON;
    let factor = n / sum_h;
    // One side of any split holds no default bin. Rounding moves each bin's count by at most 0.5, so this column cannot fill that side.
    if other_h * factor + 0.5 * (filled + 1.0) < config.min_data_in_leaf {
        return None;
    }
    let (min_n, min_h) = (config.min_data_in_leaf, config.min_sum_hessian);
    let has_nan = store.has_nan[k] != 0;
    let numeric = bins.len() - has_nan as usize;
    let zero = store.zero_pos[k] as usize;
    let default = Bin { g: g - other_g, h: (h - other_h).max(0.0) };
    // Places 0..=numeric: the default bin stands at `zero`.
    let at = |place: usize| {
        if place == zero {
            default
        } else if place < zero {
            bins[place]
        } else {
            bins[place - 1]
        }
    };
    let mut best: Option<Split> = None;
    let mut consider = |pos: usize, nan_left: bool, left_g: f64, left_h: f64, right_g: f64, right_h: f64| {
        let gain = leaf_gain(left_g, left_h, config) + leaf_gain(right_g, right_h, config);
        if gain > parent && best.as_ref().is_none_or(|b| gain - parent > b.gain) {
            best = Some(Split { column: k as u32, cut: Cut::Upto(pos as u32), default_left: nan_left, gain: gain - parent, left_g, left_h: left_h - EPSILON, child_l2: config.lambda_l2 });
        }
    };
    let (mut right_g, mut right_h, mut right_n) = (0.0, EPSILON, 0.0);
    for place in (1..=numeric).rev() {
        let bin = at(place);
        right_g += bin.g;
        right_h += bin.h;
        right_n += (bin.h * factor).round();
        if right_n < min_n || right_h < min_h {
            continue;
        }
        if n - right_n < min_n || sum_h - right_h < min_h {
            break;
        }
        consider(place - 1, has_nan, g - right_g, sum_h - right_h, right_g, right_h);
    }
    if has_nan {
        let (mut left_g, mut left_h, mut left_n) = (0.0, EPSILON, 0.0);
        for place in 0..=numeric {
            let bin = at(place);
            left_g += bin.g;
            left_h += bin.h;
            left_n += (bin.h * factor).round();
            if left_n < min_n || left_h < min_h {
                continue;
            }
            if n - left_n < min_n || sum_h - left_h < min_h {
                break;
            }
            consider(place, false, left_g, left_h, g - left_g, sum_h - left_h);
        }
    }
    best
}

/// The bits of the given places, of a column with `count` places.
fn place_set(count: usize, places: &mut dyn Iterator<Item = usize>) -> Vec<u64> {
    let mut bits = vec![0u64; count.div_ceil(64)];
    for place in places {
        bits[place >> 6] |= 1u64 << (place & 63);
    }
    bits
}

/// The best split of a categorical column, as LightGBM's `FindBestThresholdCategoricalInner` finds it, from the column's bins `bins` in the leaf's histogram.
///
/// A category is a place of the column: place 0, the default bin, is the value 0, and the others are the values with an entry. The last bin, which holds the NaN
/// and the values that the fit has no category for, is no category: its rows go right. The split sends a set of categories left.
///
/// A column with `max_cat_to_onehot` bins or fewer, counting the last bin, is split as one category against the others. In a larger column, the categories
/// with at least `cat_smooth` rows are sorted by G / (H + cat_smooth), and a scan from each end of that order adds one category at a time to the left side. The
/// scan adds at most `max_cat_threshold` categories and half of them, and it considers a split only once the categories added since the last split that it
/// considered hold `min_data_per_group` rows. It stops at the first split that leaves too few rows on the right. The gain of those splits, and the values of the
/// leaves they make, use `lambda_l2 + cat_l2`, and the gain of the parent uses `lambda_l2`.
fn best_in_categorical(store: &Store, k: usize, bins: &[Bin], total: (f64, f64, f64), config: &Config, parent: f64) -> Option<Split> {
    let (g, h, n) = total;
    let numeric = bins.len() - 1;
    debug_assert!(store.has_nan[k] != 0 && store.zero_pos[k] == 0);
    let (other_g, other_h) = bins.iter().fold((0.0, 0.0), |(sg, sh), bin| (sg + bin.g, sh + bin.h));
    let sum_h = h + EPSILON;
    let factor = n / sum_h;
    let (min_n, min_h) = (config.min_data_in_leaf, config.min_sum_hessian);
    let cat = &config.categorical;
    let default = Bin { g: g - other_g, h: (h - other_h).max(0.0) };
    // The categories, places 0..=numeric, each with its sums and its estimated count of rows.
    let categories: Vec<(Bin, f64)> = (0..=numeric)
        .map(|place| {
            let bin = if place == 0 { default } else { bins[place - 1] };
            (bin, (bin.h * factor).round())
        })
        .collect();
    let set_of = |places: &mut dyn Iterator<Item = usize>| place_set(numeric + 1, places);
    let mut best_gain = f64::NEG_INFINITY;
    let mut best: Option<Split> = None;
    if numeric + 2 <= cat.max_cat_to_onehot {
        for (place, &(bin, count)) in categories.iter().enumerate() {
            if count < min_n || bin.h < min_h || n - count < min_n {
                continue;
            }
            let other_h = sum_h - bin.h - EPSILON;
            if other_h < min_h {
                continue;
            }
            let gain = leaf_gain(g - bin.g, other_h, config) + leaf_gain(bin.g, bin.h + EPSILON, config);
            if gain > parent && gain > best_gain {
                best_gain = gain;
                best = Some(Split { column: k as u32, cut: Cut::Set(set_of(&mut std::iter::once(place))), default_left: false, gain: gain - parent, left_g: bin.g, left_h: bin.h, child_l2: config.lambda_l2 });
            }
        }
        return best;
    }
    let mut sorted: Vec<usize> = (0..=numeric).filter(|&place| categories[place].1 >= cat.cat_smooth).collect();
    let ratio = |place: usize| categories[place].0.g / (categories[place].0.h + cat.cat_smooth);
    sorted.sort_by(|&a, &b| ratio(a).total_cmp(&ratio(b)));
    let used = sorted.len();
    let l2 = config.lambda_l2 + cat.cat_l2;
    let most = cat.max_cat_threshold.min(used.div_ceil(2));
    // The best scan so far: the direction, the count of categories it added, and the sums of the left side.
    let mut found: Option<(bool, usize, f64, f64)> = None;
    for forward in [true, false] {
        let (mut since_split, mut left_g, mut left_h, mut left_n) = (0.0, 0.0, EPSILON, 0.0);
        for added in 0..used.min(most) {
            let (bin, count) = categories[sorted[if forward { added } else { used - 1 - added }]];
            left_g += bin.g;
            left_h += bin.h;
            left_n += count;
            since_split += count;
            if left_n < min_n || left_h < min_h {
                continue;
            }
            let right_n = n - left_n;
            if right_n < min_n || right_n < cat.min_data_per_group {
                break;
            }
            let right_h = sum_h - left_h;
            if right_h < min_h {
                break;
            }
            if since_split < cat.min_data_per_group {
                continue;
            }
            since_split = 0.0;
            let gain = leaf_gain_l2(left_g, left_h, l2, config) + leaf_gain_l2(g - left_g, right_h, l2, config);
            if gain > parent && gain > best_gain {
                best_gain = gain;
                found = Some((forward, added + 1, left_g, left_h));
            }
        }
    }
    let (forward, count, left_g, left_h) = found?;
    let mut places = (0..count).map(|added| sorted[if forward { added } else { used - 1 - added }]);
    Some(Split { column: k as u32, cut: Cut::Set(set_of(&mut places)), default_left: false, gain: best_gain - parent, left_g, left_h: left_h - EPSILON, child_l2: l2 })
}

/// A leaf's best split among the columns its parent could split, and the columns that have a split here, which alone stand
/// for its children, as in LightGBM.
fn best_split(store: &Store, used: &[u32], hist: &[Bin], total: (f64, f64, f64), config: &Config, rows: &[u32]) -> (Option<Split>, Vec<u32>) {
    let (g, h, n) = total;
    if n < 2.0 * config.min_data_in_leaf || h < 2.0 * config.min_sum_hessian {
        return (None, Vec::new());
    }
    let most = if config.min_tasks > 0 { 16 } else { 1 };
    let parent = leaf_gain(g, h + EPSILON, config);
    let (tops, open) = used
        .par_chunks(32)
        .map(|chunk| {
            let mut tops: Vec<Split> = Vec::new();
            let mut open = Vec::new();
            for &k in chunk {
                if let Some(found) = best_in_column(store, k as usize, hist, total, config, parent) {
                    open.push(k);
                    keep_top(&mut tops, found, most);
                }
            }
            (tops, open)
        })
        .reduce(
            || (Vec::new(), Vec::new()),
            |(mut tops, mut open), (more_tops, more)| {
                open.extend(more);
                for found in more_tops {
                    keep_top(&mut tops, found, most);
                }
                (tops, open)
            },
        );
    let best = if config.min_tasks == 0 { tops.first().cloned() } else { tops.into_iter().find(|split| both_sides_hold_tasks(store, config, rows, split)) };
    (best, open)
}

/// The best splits so far, best first, with a lower column first at equal gain.
fn keep_top(tops: &mut Vec<Split>, found: Split, most: usize) {
    let at = tops.partition_point(|x| x.gain > found.gain || (x.gain == found.gain && x.column < found.column));
    if at < most {
        tops.insert(at, found);
        tops.truncate(most);
    }
}

/// Whether each side of a split holds rows of at least `min_tasks` tasks.
fn both_sides_hold_tasks(store: &Store, config: &Config, rows: &[u32], split: &Split) -> bool {
    let (mut left, mut right) = (std::collections::HashSet::new(), std::collections::HashSet::new());
    for &row in rows {
        let task = config.row_task[row as usize];
        if store.left(row, split.column, &split.cut, split.default_left) {
            left.insert(task);
        } else {
            right.insert(task);
        }
        if left.len() >= config.min_tasks && right.len() >= config.min_tasks {
            return true;
        }
    }
    false
}

/// A raw pointer that parallel workers write through at places that no two of them share.
struct Disjoint<T>(*mut T);

unsafe impl<T> Send for Disjoint<T> {}
unsafe impl<T> Sync for Disjoint<T> {}

impl<T> Disjoint<T> {
    #[inline]
    fn at(&self, i: usize) -> *mut T {
        unsafe { self.0.add(i) }
    }
}

const NO_ENTRY: u32 = 1;
const GOES_LEFT: u32 = 2;
const GOES_RIGHT: u32 = 3;

/// `Store::left` for one split, for many items. What a use says of an item depends on the item's block in the use's map alone, so it is found once for
/// each block and kept, tagged with the split's stamp, in `memo`. The answer of an item is the answer of its first use whose block has an entry in the
/// column, as in `Store::left`.
struct SplitTest<'a, I: Items> {
    store: &'a Store,
    items: &'a I,
    memo: &'a [Vec<AtomicU32>],
    stamp: u32,
    start: u32,
    end: u32,
    zero: u32,
    cut: &'a Cut,
    /// Whether the column's default bin goes left, for an item with no entry in the column.
    zero_left: bool,
    has_nan: bool,
    default_left: bool,
    mask: u64,
    /// `Work::offsets`, and the width of a block's offsets and the run of the split's column.
    offsets: &'a [Option<Vec<u16>>],
    width: usize,
    group: usize,
}

impl<I: Items> SplitTest<'_, I> {
    #[inline]
    fn left(&self, item: u32) -> bool {
        let mut mask = self.mask;
        while mask != 0 {
            let place = mask.trailing_zeros() as usize;
            mask &= mask - 1;
            let data = &self.store.uses[place];
            let block = self.items.block(data.map, item);
            if block == NONE {
                continue;
            }
            let b = block as usize;
            let cell = &self.memo[place][b];
            let seen = cell.load(Ordering::Relaxed);
            let code = if seen >> 2 == self.stamp {
                seen & 3
            } else {
                let code = self.code(data, place, b);
                cell.store(self.stamp << 2 | code, Ordering::Relaxed);
                code
            };
            if code != NO_ENTRY {
                return code == GOES_LEFT;
            }
        }
        self.zero_left
    }

    /// What the use's block `b` says: no entry in the column, or the side its entry goes to.
    fn code(&self, data: &UseData, place: usize, b: usize) -> u32 {
        let entries = &data.bid[data.ptr[b] as usize..data.ptr[b + 1] as usize];
        // The column's entries lie in its run of columns.
        let entries = match &self.offsets[place] {
            Some(offsets) => &entries[offsets[b * self.width + self.group] as usize..offsets[b * self.width + self.group + 1] as usize],
            None => entries,
        };
        let at = entries.partition_point(|&x| x < self.start);
        if at < entries.len() && entries[at] < self.end {
            let bid = entries[at];
            let left = if self.has_nan && bid == self.end - 1 {
                self.default_left
            } else {
                let index = bid - self.start;
                let place = if index < self.zero { index } else { index + 1 };
                self.cut.left(place)
            };
            return if left { GOES_LEFT } else { GOES_RIGHT };
        }
        NO_ENTRY
    }
}

/// Tests the items of one chunk, writes each item's flag, and gives the count of items that go left and of the rows they stand for.
#[inline(never)]
fn test_chunk<I: Items>(test: &SplitTest<I>, items: &I, flags: &mut [bool], here: &[u32]) -> (usize, usize) {
    let (mut count, mut rows) = (0usize, 0usize);
    for (flag, &item) in flags.iter_mut().zip(here) {
        let left = test.left(item);
        *flag = left;
        if left {
            count += 1;
            rows += items.rows(item);
        }
    }
    (count, rows)
}

/// Writes the items of one chunk to `out`, the left ones from `l` on and the right ones from `r` on, in their order.
#[inline(never)]
fn scatter_chunk(out: &Disjoint<u32>, flags: &[bool], here: &[u32], mut l: usize, mut r: usize) {
    for (&flag, &item) in flags.iter().zip(here) {
        // Chunks write to places that no other chunk writes to.
        if flag {
            unsafe { *out.at(l) = item };
            l += 1;
        } else {
            unsafe { *out.at(r) = item };
            r += 1;
        }
    }
}

/// Stably partitions the leaf's items `work.indices[start..start + len]` by whether they go left at `split`. It returns the count of items that go left
/// and the count of rows they stand for.
fn partition<I: Items>(work: &mut Work, store: &Store, items: &I, start: usize, len: usize, column: u32, cut: &Cut, default_left: bool) -> (usize, usize) {
    let began = Instant::now();
    let k = column as usize;
    let mask = store.col_uses[k];
    work.stamp += 1;
    assert!(work.stamp < 1 << 30, "a memo stamp has 30 bits");
    let mut mask_bits = mask;
    while mask_bits != 0 {
        let place = mask_bits.trailing_zeros() as usize;
        mask_bits &= mask_bits - 1;
        if work.memo[place].is_empty() {
            let blocks = store.uses[place].ptr.len().saturating_sub(1);
            work.memo[place] = (0..blocks).map(|_| AtomicU32::new(0)).collect();
        }
    }
    let test = SplitTest {
        store,
        items,
        memo: &work.memo,
        stamp: work.stamp,
        start: store.col_start[k],
        end: store.col_start[k + 1],
        zero: store.zero_pos[k],
        cut,
        zero_left: cut.left(store.zero_pos[k]),
        has_nan: store.has_nan[k] != 0,
        default_left,
        mask,
        offsets: &work.offsets,
        width: work.groups + 1,
        group: work.group_of[k] as usize,
    };
    work.flags.resize(len, false);
    // The items go in chunks. A chunk's left items go to the front of `scratch` after the left items of the chunks before it, and its right items after
    // all left items.
    const CHUNK: usize = 1 << 14;
    let lefts: Vec<(usize, usize)> = work
        .flags
        .par_chunks_mut(CHUNK)
        .zip(work.indices[start..start + len].par_chunks(CHUNK))
        .map(|(flags, here)| test_chunk(&test, items, flags, here))
        .collect();
    let left_len: usize = lefts.iter().map(|x| x.0).sum();
    let left_rows: usize = lefts.iter().map(|x| x.1).sum();
    let mut left_at = Vec::with_capacity(lefts.len());
    let mut right_at = Vec::with_capacity(lefts.len());
    let (mut l, mut r) = (0usize, left_len);
    for (i, &(count, _)) in lefts.iter().enumerate() {
        left_at.push(l);
        right_at.push(r);
        l += count;
        r += CHUNK.min(len - i * CHUNK) - count;
    }
    if work.scratch.len() < len {
        work.scratch.resize(len, 0);
    }
    {
        let out = Disjoint(work.scratch.as_mut_ptr());
        let here = &work.indices[start..start + len];
        let flags = &work.flags;
        (0..lefts.len()).into_par_iter().for_each(|i| {
            let from = i * CHUNK;
            let to = (from + CHUNK).min(len);
            scatter_chunk(&out, &flags[from..to], &here[from..to], left_at[i], right_at[i]);
        });
    }
    let scratch = &work.scratch;
    work.indices[start..start + len].par_chunks_mut(CHUNK).zip(scratch[..len].par_chunks(CHUNK)).for_each(|(to, from)| to.copy_from_slice(from));
    work.time[0] += began.elapsed().as_secs_f64();
    (left_len, left_rows)
}

/// Adds each leaf's value to the score of each row the leaf holds. A row stands in one leaf, so no two workers write one score.
fn add_leaf_values(score: &mut [f64], indices: &[u32], places: &[(usize, usize)], values: &[f64]) {
    let out = Disjoint(score.as_mut_ptr());
    for (leaf, &(start, len)) in places.iter().enumerate() {
        let value = values[leaf];
        indices[start..start + len].par_chunks(1 << 16).for_each(|rows| {
            for &row in rows {
                unsafe { *out.at(row as usize) += value };
            }
        });
    }
}

struct Leaf {
    start: usize,
    /// The count of items, and of the rows they stand for.
    len: usize,
    rows: usize,
    g: f64,
    h: f64,
    hist: Option<Vec<Bin>>,
    touched: Option<Vec<u32>>,
    best: Option<Split>,
    open: Vec<u32>,
    parent: i32,
    is_left: bool,
    /// The L2 term of the leaf's value.
    l2: f64,
}

/// One tree over the items in `active`, best leaf first. It leaves each leaf's items in `work.indices` and gives each leaf's
/// place in that array. A leaf's count of rows is the count of rows its items stand for. `config.min_tasks` is for items that are rows.
fn grow<I: Items>(work: &mut Work, store: &Store, config: &Config, items: &I, active: &[u32], used: &[u32]) -> (Tree, Vec<(usize, usize)>) {
    work.indices.clear();
    work.indices.extend_from_slice(active);
    let (mut g, mut h) = (0.0f64, EPSILON);
    for &item in active {
        let (item_g, item_h) = items.weight(item);
        g += item_g;
        h += item_h;
    }
    let total_rows: usize = active.par_iter().map(|&item| items.rows(item)).sum();
    let mut hist = work.take(store);
    fill_histogram(work, store, items, 0..active.len(), &mut hist, false);
    let began = Instant::now();
    let (best, open) = best_split(store, used, &hist, (g, h, total_rows as f64), config, active);
    work.time[3] += began.elapsed().as_secs_f64();
    let mut leaves = vec![Leaf { start: 0, len: active.len(), rows: total_rows, g, h, hist: Some(hist), touched: None, best, open, parent: -1, is_left: false, l2: config.lambda_l2 }];
    let mut tree = Tree::default();
    while leaves.len() < config.num_leaves {
        let mut chosen = None;
        let mut most = 0.0;
        for (at, leaf) in leaves.iter().enumerate() {
            if let Some(split) = &leaf.best {
                if split.gain > most {
                    most = split.gain;
                    chosen = Some(at);
                }
            }
        }
        let Some(at) = chosen else { break };
        let split = leaves[at].best.take().unwrap();
        let (start, len) = (leaves[at].start, leaves[at].len);
        let (left_len, left_rows) = partition(work, store, items, start, len, split.column, &split.cut, split.default_left);
        let node = tree.column.len() as i32;
        tree.column.push(split.column);
        tree.cut.push(split.cut.clone());
        tree.default_left.push(split.default_left);
        tree.gain.push(split.gain);
        let right_leaf = leaves.len();
        tree.left.push(!(at as i32));
        tree.right.push(!(right_leaf as i32));
        let (parent, is_left) = (leaves[at].parent, leaves[at].is_left);
        if parent >= 0 {
            if is_left {
                tree.left[parent as usize] = node;
            } else {
                tree.right[parent as usize] = node;
            }
        }
        let (total_g, total_h) = (leaves[at].g, leaves[at].h);
        let (left_g, left_h) = (split.left_g, split.left_h + EPSILON);
        let (right_g, right_h) = (total_g - split.left_g, (total_h - split.left_h).max(EPSILON));
        let right_len = len - left_len;
        let right_rows = leaves[at].rows - left_rows;
        // The smaller child's histogram is read from its rows, and the larger's is what remains of its parent's. Where the
        // parent's histogram was given up, the larger child's is read from its rows too.
        let parent_hist = leaves[at].hist.take();
        let parent_touched = leaves[at].touched.take();
        let mut smaller = work.take(store);
        let (small_rows, large_rows) = if left_len < right_len { (start..start + left_len, start + left_len..start + len) } else { (start + left_len..start + len, start..start + left_len) };
        let small_touched = fill_histogram(work, store, items, small_rows, &mut smaller, true);
        let (larger, large_touched) = match parent_hist {
            Some(mut larger) => {
                for &b in &small_touched {
                    let y = smaller[b as usize];
                    let x = &mut larger[b as usize];
                    x.g -= y.g;
                    x.h -= y.h;
                }
                (larger, parent_touched)
            }
            None => {
                let mut larger = work.take(store);
                let touched = fill_histogram(work, store, items, large_rows, &mut larger, true);
                (larger, Some(touched))
            }
        };
        let (left_hist, left_touched, right_hist, right_touched) = if left_len < right_len { (smaller, Some(small_touched), larger, large_touched) } else { (larger, large_touched, smaller, Some(small_touched)) };
        let open = std::mem::take(&mut leaves[at].open);
        let began = Instant::now();
        let (left_best, left_open) = best_split(store, &open, &left_hist, (left_g, left_h, left_rows as f64), config, &work.indices[start..start + left_len]);
        let (right_best, right_open) = best_split(store, &open, &right_hist, (right_g, right_h, right_rows as f64), config, &work.indices[start + left_len..start + len]);
        work.time[3] += began.elapsed().as_secs_f64();
        leaves[at] = Leaf { start, len: left_len, rows: left_rows, g: left_g, h: left_h, hist: None, touched: None, best: left_best, open: left_open, parent: node, is_left: true, l2: split.child_l2 };
        if leaves[at].best.is_some() {
            leaves[at].hist = Some(left_hist);
            leaves[at].touched = left_touched;
        } else {
            work.give(left_hist, left_touched);
        }
        let mut right = Leaf { start: start + left_len, len: right_len, rows: right_rows, g: right_g, h: right_h, hist: None, touched: None, best: right_best, open: right_open, parent: node, is_left: false, l2: split.child_l2 };
        if right.best.is_some() {
            right.hist = Some(right_hist);
            right.touched = right_touched;
        } else {
            work.give(right_hist, right_touched);
        }
        leaves.push(right);
        // Past the pool's size, the leaf least likely to split next gives up its histogram.
        let pool = (HISTOGRAM_BYTES / (store.bins.max(1) * std::mem::size_of::<Bin>())).max(2);
        while leaves.iter().filter(|leaf| leaf.hist.is_some()).count() > pool {
            let weakest = leaves.iter().enumerate().filter(|(_, leaf)| leaf.hist.is_some()).min_by(|(_, a), (_, b)| a.best.as_ref().map_or(0.0, |s| s.gain).total_cmp(&b.best.as_ref().map_or(0.0, |s| s.gain))).unwrap().0;
            let hist = leaves[weakest].hist.take().unwrap();
            let touched = leaves[weakest].touched.take();
            work.give(hist, touched);
        }
    }
    let mut places = Vec::with_capacity(leaves.len());
    tree.value = vec![0.0; leaves.len()];
    tree.leaf_l2 = leaves.iter().map(|leaf| leaf.l2).collect();
    for (at, leaf) in leaves.iter_mut().enumerate() {
        if let Some(hist) = leaf.hist.take() {
            let touched = leaf.touched.take();
            work.give(hist, touched);
        }
        places.push((leaf.start, leaf.len));
        tree.value[at] = if tree.column.is_empty() { 0.0 } else { leaf_output_l2(leaf.g, leaf.h, leaf.l2, config) * config.learning_rate };
    }
    (tree, places)
}

/// The rows of each group stand together, and its gold rows have label 1.
struct Groups {
    start: Vec<u32>,
    label: Vec<u8>,
    inverse_max_dcg: Vec<f64>,
    discount: Vec<f64>,
    weight: Vec<f32>,
}

impl Groups {
    fn new(start: Vec<u32>, label: Vec<u8>, truncation: usize) -> Groups {
        let longest = start.windows(2).map(|w| (w[1] - w[0]) as usize).max().unwrap_or(0);
        let discount: Vec<f64> = (0..longest + 1).map(|i| 1.0 / ((i + 2) as f64).log2()).collect();
        let inverse_max_dcg = start
            .windows(2)
            .map(|w| {
                let gold = label[w[0] as usize..w[1] as usize].iter().filter(|&&x| x > 0).count();
                let best: f64 = discount[..gold.min(truncation)].iter().sum();
                if best > 0.0 { 1.0 / best } else { 0.0 }
            })
            .collect();
        Groups { start, label, inverse_max_dcg, discount, weight: Vec::new() }
    }

    fn count(&self) -> usize {
        self.start.len() - 1
    }
}

/// LightGBM's lambdarank gradients of one group.
/// LightGBM's lookup for the sigmoid of a pair's score difference, 2^20 bins from -25 to 25. A bin's value stands for every
/// difference in that bin, so a fit's trees depend on it.
fn sigmoid_table() -> &'static [f64] {
    static TABLE: std::sync::OnceLock<Vec<f64>> = std::sync::OnceLock::new();
    TABLE.get_or_init(|| (0..SIGMOID_BINS).map(|i| 1.0 / (1.0 + (i as f64 / SIGMOID_FACTOR + SIGMOID_LOW).exp())).collect())
}

fn group_gradients(score: &[f64], label: &[u8], inverse_max_dcg: f64, discount: &[f64], truncation: usize, grad: &mut [f32], hess: &mut [f32]) {
    let n = score.len();
    grad.fill(0.0);
    hess.fill(0.0);
    let sigmoids = sigmoid_table();
    let mut sorted: Vec<u32> = (0..n as u32).collect();
    sorted.sort_by(|&a, &b| score[b as usize].total_cmp(&score[a as usize]));
    let best = score[sorted[0] as usize];
    let worst = score[sorted[n - 1] as usize];
    let mut sum_lambdas = 0.0;
    for i in 0..(n - 1).min(truncation) {
        for j in i + 1..n {
            let (a, b) = (sorted[i] as usize, sorted[j] as usize);
            if label[a] == label[b] {
                continue;
            }
            let (high_rank, low_rank, high, low) = if label[a] > label[b] { (i, j, a, b) } else { (j, i, b, a) };
            let delta = score[high] - score[low];
            let gain_gap = (label[high] as f64) - (label[low] as f64);
            let paired = (discount[high_rank] - discount[low_rank]).abs();
            let mut delta_ndcg = gain_gap * paired * inverse_max_dcg;
            if best != worst {
                delta_ndcg /= 0.01f32 as f64 + delta.abs();
            }
            let sigmoid = if delta <= SIGMOID_LOW {
                sigmoids[0]
            } else if delta >= -SIGMOID_LOW {
                sigmoids[SIGMOID_BINS - 1]
            } else {
                sigmoids[((delta - SIGMOID_LOW) * SIGMOID_FACTOR) as usize]
            };
            let p_hessian = sigmoid * (1.0 - sigmoid) * delta_ndcg;
            let p_lambda = -sigmoid * delta_ndcg;
            grad[low] -= p_lambda as f32;
            hess[low] += p_hessian as f32;
            grad[high] += p_lambda as f32;
            hess[high] += p_hessian as f32;
            sum_lambdas -= 2.0 * p_lambda;
        }
    }
    if sum_lambdas > 0.0 {
        let factor = (1.0 + sum_lambdas).log2() / sum_lambdas;
        for i in 0..n {
            grad[i] = (grad[i] as f64 * factor) as f32;
            hess[i] = (hess[i] as f64 * factor) as f32;
        }
    }
}

fn gradients(groups: &Groups, active: &[bool], score: &[f64], truncation: usize, grad: &mut [f32], hess: &mut [f32]) {
    let mut slices = Vec::with_capacity(groups.count());
    let (mut rest_g, mut rest_h) = (grad, hess);
    for g in 0..groups.count() {
        let length = (groups.start[g + 1] - groups.start[g]) as usize;
        let (here_g, after_g) = rest_g.split_at_mut(length);
        let (here_h, after_h) = rest_h.split_at_mut(length);
        rest_g = after_g;
        rest_h = after_h;
        if active[g] {
            slices.push((g, here_g, here_h));
        }
    }
    slices.into_par_iter().for_each(|(g, here_g, here_h)| {
        let (a, b) = (groups.start[g] as usize, groups.start[g + 1] as usize);
        group_gradients(&score[a..b], &groups.label[a..b], groups.inverse_max_dcg[g], &groups.discount, truncation, here_g, here_h);
        if let Some(&weight) = groups.weight.get(g) {
            for (x, y) in here_g.iter_mut().zip(here_h.iter_mut()) {
                *x *= weight;
                *y *= weight;
            }
        }
    });
}

/// The mean over the held groups of how often a gold row stands above a mutant's row.
fn group_auc(groups: &Groups, held: &[bool], score: &[f64]) -> f64 {
    let (mut total, mut count) = (0.0, 0.0);
    for g in 0..groups.count() {
        if !held[g] {
            continue;
        }
        let (a, b) = (groups.start[g] as usize, groups.start[g + 1] as usize);
        let (mut wins, mut pairs) = (0.0, 0.0);
        for i in a..b {
            if groups.label[i] == 0 {
                continue;
            }
            for j in a..b {
                if groups.label[j] != 0 {
                    continue;
                }
                pairs += 1.0;
                if score[i] > score[j] {
                    wins += 1.0;
                } else if score[i] == score[j] {
                    wins += 0.5;
                }
            }
        }
        if pairs > 0.0 {
            total += wins / pairs;
        }
        count += 1.0;
    }
    total / f64::max(count, 1.0)
}

/// Boosts over the active groups. With held groups, it stops once they have not improved for `patience` rounds.
fn boost(store: &Store, groups: &Groups, active: &[bool], held: Option<&[bool]>, dev: Option<(&Store, &Groups)>, config: &Config, seed: u64, rounds: usize, name: &str) -> (Vec<Tree>, usize, Vec<f64>) {
    let mut work = Work::new(store);
    let mut score = vec![0.0f64; store.rows];
    let (mut grad, mut hess) = (vec![0.0f32; store.rows], vec![0.0f32; store.rows]);
    let mut random = Random(mix(seed));
    let mut columns: Vec<u32> = (0..store.kept as u32).filter(|&k| config.admit.as_ref().is_none_or(|a| a.first[k as usize] != 0)).collect();
    let mut admitted = vec![false; store.kept];
    for &k in &columns {
        admitted[k as usize] = true;
    }
    let rows_of = |flags: &[bool]| -> Vec<u32> {
        let mut rows = Vec::new();
        for g in 0..groups.count() {
            if flags[g] {
                rows.extend(groups.start[g]..groups.start[g + 1]);
            }
        }
        rows
    };
    let active_rows = rows_of(active);
    let held_rows = held.map(rows_of).unwrap_or_default();
    let mut trees = Vec::new();
    let (mut best_auc, mut best_round) = (f64::NEG_INFINITY, 0usize);
    let started = Instant::now();
    let mut stream = config.stream.as_ref().filter(|_| held.is_some()).map(|dir| BufWriter::new(File::create(dir.join(format!("inner.{seed}.jsonl"))).unwrap()));
    let mut dev_score = dev.map_or(Vec::new(), |(dev_store, _)| vec![0.0f64; dev_store.rows]);
    let dev_every = dev.map_or(Vec::new(), |(_, dev_groups)| vec![true; dev_groups.count()]);
    for round in 1..=rounds {
        gradients(groups, active, &score, config.truncation, &mut grad, &mut hess);
        let sampled = ((config.fraction * columns.len() as f64).round() as usize).clamp(1, columns.len().max(1));
        for i in 0..sampled {
            let j = i + random.below(columns.len() - i);
            columns.swap(i, j);
        }
        let mut used = columns[..sampled].to_vec();
        used.sort_unstable();
        let (tree, places) = {
            let items = RowItems { store, grad: &grad, hess: &hess };
            grow(&mut work, store, config, &items, &active_rows, &used)
        };
        let empty = tree.column.is_empty();
        if let Some(admit) = &config.admit {
            for &k in &tree.column {
                for &c in &admit.child[admit.ptr[k as usize] as usize..admit.ptr[k as usize + 1] as usize] {
                    if !admitted[c as usize] {
                        admitted[c as usize] = true;
                        columns.push(c);
                    }
                }
            }
        }
        add_leaf_values(&mut score, &work.indices, &places, &tree.value);
        if let Some(flags) = held {
            let moves: Vec<f64> = held_rows.par_iter().with_min_len(64).map(|&row| tree.value[tree.leaf_of(store, row)]).collect();
            for (&row, step) in held_rows.iter().zip(moves) {
                score[row as usize] += step;
            }
            let auc = group_auc(groups, flags, &score);
            if auc > best_auc {
                best_auc = auc;
                best_round = round;
            }
        }
        let mut dev_auc = None;
        if let Some((dev_store, dev_groups)) = dev {
            let moves: Vec<f64> = (0..dev_store.rows as u32).into_par_iter().with_min_len(64).map(|row| tree.value[tree.leaf_of(dev_store, row)]).collect();
            for (value, step) in dev_score.iter_mut().zip(moves) {
                *value += step;
            }
            if round % 10 == 0 {
                dev_auc = Some(group_auc(dev_groups, &dev_every, &dev_score));
            }
        }
        if let Some(sink) = &mut stream {
            writeln!(sink, "{}", json!({"round": round, "column": tree.column, "gain": tree.gain, "left": tree.left, "right": tree.right, "dev_auc": dev_auc, "columns": columns.len()})).unwrap();
            sink.flush().unwrap();
        }
        trees.push(tree);
        if round % 25 == 0 || empty {
            let rate = round as f64 / started.elapsed().as_secs_f64();
            println!("{name} round {round} held auc {best_auc:.4} at {best_round} columns {} {rate:.2} rounds/s rss {:.2} GiB", columns.len(), resident_gib());
        }
        if empty || (held.is_some() && round >= best_round + config.patience) {
            break;
        }
    }
    (trees, best_round, score)
}

fn resident_gib() -> f64 {
    let mut usage: libc::rusage = unsafe { std::mem::zeroed() };
    unsafe { libc::getrusage(libc::RUSAGE_SELF, &mut usage) };
    // `ru_maxrss` is in bytes on macOS and in KiB on Linux.
    let unit = if cfg!(target_os = "macos") { 1u64 << 30 } else { 1u64 << 20 };
    usage.ru_maxrss as f64 / unit as f64
}

/// A tree as a line of JSON. A split on a numeric column has a `threshold`, a number or null (no finite bound), and null in `categories`. A split on a categorical
/// column has the string "categorical" as its `threshold`, so that a reader that does not know categories fails on it, and in `categories` the ascending values that
/// go left. A value that is not among them goes right, as does a NaN.
fn tree_json(tree: &Tree, bounds: &[f64], bound_start: &[u32], has_nan: &[u8]) -> Value {
    // A threshold of no finite bound sends every number left.
    let threshold: Vec<Value> = tree
        .column
        .iter()
        .zip(&tree.cut)
        .map(|(&k, cut)| match cut {
            Cut::Upto(pos) => {
                let x = bounds[bound_start[k as usize] as usize + *pos as usize];
                if x.is_finite() { json!(x) } else { Value::Null }
            }
            Cut::Set(_) => json!("categorical"),
        })
        .collect();
    // A place of a categorical column is its value, which is the bound at that place, and the default bin's is 0.
    let categories: Vec<Value> = tree
        .column
        .iter()
        .zip(&tree.cut)
        .map(|(&k, cut)| match cut {
            Cut::Upto(_) => Value::Null,
            Cut::Set(bits) => {
                let places = (0..bits.len() * 64).filter(|&place| bits[place >> 6] >> (place & 63) & 1 != 0);
                json!(places.map(|place| if place == 0 { 0 } else { bounds[bound_start[k as usize] as usize + place] as u64 }).collect::<Vec<u64>>())
            }
        })
        .collect();
    // A column with no NaN in the fit reads a NaN as its default, 0, as `compile` does.
    let nan_seen: Vec<bool> = tree.column.iter().map(|&k| has_nan[k as usize] != 0).collect();
    json!({"column": tree.column, "threshold": threshold, "categories": categories, "default_left": tree.default_left, "nan_seen": nan_seen, "gain": tree.gain, "left": tree.left, "right": tree.right, "value": tree.value})
}

fn fit(file: &Path) {
    let v = read_json(file);
    let count = v["threads"].as_u64().unwrap() as usize;
    threads(count);
    let config = Config {
        learning_rate: v["learning_rate"].as_f64().unwrap(),
        num_leaves: v["num_leaves"].as_u64().unwrap() as usize,
        min_data_in_leaf: v["min_data_in_leaf"].as_f64().unwrap(),
        min_sum_hessian: v["min_sum_hessian"].as_f64().unwrap(),
        lambda_l2: v["lambda_l2"].as_f64().unwrap_or(0.0),
        max_delta_step: v["max_delta_step"].as_f64().unwrap_or(0.0),
        fraction: v["fraction"].as_f64().unwrap(),
        truncation: v["truncation"].as_u64().unwrap() as usize,
        max_rounds: v["max_rounds"].as_u64().unwrap() as usize,
        patience: v["patience"].as_u64().unwrap() as usize,
        admit: v["admit"].as_str().map(Admit::open),
        stream: v["out"].as_str().map(PathBuf::from),
        min_tasks: v["min_tasks"].as_u64().unwrap_or(0) as usize,
        row_task: v["row_task"].as_str().map_or(Vec::new(), |path| read_all(Path::new(path))),
        categorical: CategoricalConfig::read(&v),
    };
    let train_dir = PathBuf::from(v["train"].as_str().unwrap());
    let store = Store::open(&train_dir);
    let out = PathBuf::from(v["out"].as_str().unwrap());
    fs::create_dir_all(&out).unwrap();
    let mut groups = Groups::new(read_all(Path::new(v["groups"].as_str().unwrap())), read_all(Path::new(v["labels"].as_str().unwrap())), config.truncation);
    assert_eq!(groups.label.len(), store.rows);
    let bounds: Vec<f64> = read_all(&train_dir.join("bounds.f64"));
    let bound_start: Vec<u32> = read_all(&train_dir.join("bound_start.u32"));
    println!("rows {} columns {} bins {} entries {} groups {}", store.rows, store.kept, store.bins, store.col_entries.iter().sum::<u64>(), groups.count());
    if let Some(path) = v["group_weights"].as_str() {
        groups.weight = read_all(Path::new(path));
    }
    let dev_store = v["dev"].as_str().map(|d| Store::open(Path::new(d)));
    let dev_groups = v["dev_groups"].as_str().map(|path| Groups::new(read_all(Path::new(path)), read_all(Path::new(v["dev_labels"].as_str().unwrap())), config.truncation));
    let dev_watch = dev_store.as_ref().zip(dev_groups.as_ref());
    for seeded in v["seeds"].as_array().unwrap() {
        let seed = seeded["seed"].as_u64().unwrap();
        let done = out.join(format!("done.{seed}.json"));
        if done.exists() {
            println!("seed {seed} is done");
            continue;
        }
        let held: Vec<u8> = read_all(Path::new(seeded["held"].as_str().unwrap()));
        let held: Vec<bool> = held.iter().map(|&x| x != 0).collect();
        let inner: Vec<bool> = held.iter().map(|&x| !x).collect();
        let (trees, best_round, _) = boost(&store, &groups, &inner, Some(&held), dev_watch, &config, seed, config.max_rounds, &format!("seed {seed} inner"));
        drop(trees);
        let rounds = best_round.max(10);
        let every = vec![true; groups.count()];
        let (trees, _, score) = boost(&store, &groups, &every, None, None, &config, seed, rounds, &format!("seed {seed} final"));
        let (mut gain, mut splits) = (vec![0.0f64; store.kept], vec![0u32; store.kept]);
        let mut model = BufWriter::new(File::create(out.join(format!("model.{seed}.jsonl"))).unwrap());
        for tree in &trees {
            for (&k, &g) in tree.column.iter().zip(&tree.gain) {
                gain[k as usize] += g;
                splits[k as usize] += 1;
            }
            writeln!(model, "{}", tree_json(tree, &bounds, &bound_start, &store.has_nan)).unwrap();
        }
        model.flush().unwrap();
        write_all(&out.join(format!("gain.{seed}.f64")), &gain);
        write_all(&out.join(format!("splits.{seed}.u32")), &splits);
        write_all(&out.join(format!("train.{seed}.f64")), &score);
        if let Some(dev) = &dev_store {
            let rows: Vec<u32> = (0..dev.rows as u32).collect();
            let mut scores = vec![0.0f64; dev.rows];
            for tree in &trees {
                let moves: Vec<f64> = rows.par_iter().with_min_len(64).map(|&row| tree.value[tree.leaf_of(dev, row)]).collect();
                for (held, step) in scores.iter_mut().zip(moves) {
                    *held += step;
                }
            }
            write_all(&out.join(format!("dev.{seed}.f64")), &scores);
        }
        fs::write(&done, json!({"seed": seed, "rounds": rounds, "trees": trees.len()}).to_string()).unwrap();
        println!("seed {seed} rounds {rounds} rss {:.2} GiB", resident_gib());
    }
}

/// The softmax over one group's ids and over its positive ids: the gradient p - q, the Hessian p(1 - p) with a floor, and the loss.
/// The largest score of a group, over all its ids and over its positive ids.
fn group_maxima(score: &[f64], label: &[u8]) -> (f64, f64) {
    let (mut most, mut most_positive) = (f64::NEG_INFINITY, f64::NEG_INFINITY);
    for (&s, &l) in score.iter().zip(label) {
        most = most.max(s);
        if l > 0 {
            most_positive = most_positive.max(s);
        }
    }
    (most, most_positive)
}

/// One group's loss, -ln(sum of p over the positive ids), with its gradients p - q and hessians p(1 - p) floored at 1e-6. The sums are taken in log space,
/// p against the group's largest score and q against its positives' largest, so a group whose positive ids score far below its best id keeps a finite
/// loss and q is never 0/0.
fn softmax_group(score: &[f64], label: &[u8], grad: &mut [f32], hess: &mut [f32], terms: &mut Vec<(f64, f64)>) -> f64 {
    let (most, most_positive) = group_maxima(score, label);
    let (mut all, mut positive) = (0.0, 0.0);
    terms.clear();
    for (&s, &l) in score.iter().zip(label) {
        let a = (s - most).exp();
        all += a;
        let mut e = 0.0;
        if l > 0 {
            e = (s - most_positive).exp();
            positive += e;
        }
        terms.push((a, e));
    }
    for i in 0..score.len() {
        let (a, e) = terms[i];
        let p = a / all;
        let q = if label[i] > 0 { e / positive } else { 0.0 };
        grad[i] = (p - q) as f32;
        hess[i] = (p * (1.0 - p)).max(1e-6) as f32;
    }
    (most + all.ln()) - (most_positive + positive.ln())
}

/// The mean loss over the groups, and how often a group's best id is positive.
fn softmax_read(start: &[u32], label: &[u8], score: &[f64]) -> (f64, f64) {
    let groups = start.len() - 1;
    let (mut loss, mut top) = (0.0, 0.0);
    for g in 0..groups {
        let (a, b) = (start[g] as usize, start[g + 1] as usize);
        let (most, most_positive) = group_maxima(&score[a..b], &label[a..b]);
        let (mut all, mut positive) = (0.0, 0.0);
        let (mut tied, mut tied_positive) = (0.0, 0.0);
        for i in a..b {
            all += (score[i] - most).exp();
            if label[i] > 0 {
                positive += (score[i] - most_positive).exp();
            }
            if score[i] == most {
                tied += 1.0;
                if label[i] > 0 {
                    tied_positive += 1.0;
                }
            }
        }
        loss += (most + all.ln()) - (most_positive + positive.ln());
        // Ids tied at the top share the point's credit, as `fit_trees.evaluate` gives.
        top += tied_positive / tied;
    }
    (loss / groups.max(1) as f64, top / groups.max(1) as f64)
}

/// Checks one grown tree against its items. For each leaf it sums the gradients and Hessians of the items that the partition put in it, and compares the leaf's
/// value with -G/H x learning rate of those sums; it prints the leaf where they differ by a relative 1e-6, and the leaf with the largest value where that
/// is above 50. With `full`, it prints every leaf, and it walks every row through the tree (`Store::left`) and counts the rows whose leaf differs from the
/// leaf of the row's item.
fn audit_tree<I: Items>(store: &Store, items: &I, tree: &Tree, places: &[(usize, usize)], indices: &[u32], config: &Config, round: usize, full: bool, biggest: &mut f64) {
    if tree.column.is_empty() {
        return;
    }
    let sums: Vec<(f64, f64, usize)> = places
        .par_iter()
        .map(|&(start, len)| {
            let (mut g, mut h, mut rows) = (0.0f64, 0.0f64, 0usize);
            for &item in &indices[start..start + len] {
                let (item_g, item_h) = items.weight(item);
                g += item_g;
                h += item_h;
                rows += items.rows(item);
            }
            (g, h, rows)
        })
        .collect();
    for (leaf, &(g, h, rows)) in sums.iter().enumerate() {
        let implied = leaf_output_l2(g, h + EPSILON, tree.leaf_l2[leaf], config) * config.learning_rate;
        let relative = (tree.value[leaf] - implied).abs() / implied.abs().max(1e-12);
        if relative > 1e-6 {
            println!("audit round {round} leaf {leaf}: value {:.6e} but -G/H x rate of its {rows} rows is {implied:.6e} (G {g:.6e} H {h:.6e})", tree.value[leaf]);
        }
        if full {
            println!("audit round {round} leaf {leaf}: rows {rows} G {g:.6e} H {h:.6e} value {:.6e} implied {implied:.6e}", tree.value[leaf]);
        }
    }
    let largest = largest_leaf(tree);
    *biggest = biggest.max(tree.value[largest].abs());
    if tree.value[largest].abs() > 50.0 {
        let (g, h, rows) = sums[largest];
        println!("big leaf round {round} leaf {largest}: value {:.4e} rows {rows} G {g:.4e} H {h:.4e}", tree.value[largest]);
    }
    if full {
        let mut leaf_of_item = vec![0u32; items.count()];
        for (leaf, &(start, len)) in places.iter().enumerate() {
            for &item in &indices[start..start + len] {
                leaf_of_item[item as usize] = leaf as u32;
            }
        }
        let wrong: Vec<u32> = (0..store.rows as u32).into_par_iter().filter(|&row| tree.leaf_of(store, row) != leaf_of_item[items.item_of_row(row) as usize] as usize).collect();
        println!("audit round {round}: {} of {} rows walk to another leaf than the partition put them in; first {:?}", wrong.len(), store.rows, &wrong[..wrong.len().min(5)]);
    }
}

/// The leaf with the largest value in size, the first of equals.
fn largest_leaf(tree: &Tree) -> usize {
    let mut largest = 0usize;
    for leaf in 0..tree.value.len() {
        if tree.value[leaf].abs() > tree.value[largest].abs() {
            largest = leaf;
        }
    }
    largest
}

/// A tree from a line of `tree_json`. A threshold is the bound at the split's position in the column's bounds, and no threshold stands for the
/// last bound, which is infinite.
fn tree_from_json(line: &Value, bounds: &[f64], bound_start: &[u32]) -> Tree {
    let list = |name: &str| line[name].as_array().unwrap_or_else(|| panic!("a tree has no {name}"));
    let column: Vec<u32> = list("column").iter().map(|x| x.as_u64().unwrap() as u32).collect();
    let cut = column
        .iter()
        .zip(list("threshold"))
        .zip(list("categories"))
        .map(|((&k, threshold), categories)| {
            let here = &bounds[bound_start[k as usize] as usize..bound_start[k as usize + 1] as usize];
            if let Some(values) = categories.as_array() {
                assert!(threshold.as_str() == Some("categorical"), "column {k} lists categories and has a threshold");
                let mut places = values.iter().map(|value| {
                    let x = value.as_u64().expect("a category is a whole number") as f64;
                    if x == 0.0 {
                        return 0;
                    }
                    let at = here.partition_point(|&bound| bound < x);
                    assert!(here.get(at) == Some(&x), "column {k} has no category {x}");
                    at
                });
                return Cut::Set(place_set(here.len(), &mut places));
            }
            match threshold.as_f64() {
                None => {
                    assert!(here.last() == Some(&f64::INFINITY), "column {k} has a null threshold and no infinite last bound");
                    Cut::Upto(here.len() as u32 - 1)
                }
                Some(t) => {
                    let at = here.partition_point(|&bound| bound < t);
                    assert!(here.get(at) == Some(&t), "column {k} has no bound {t}");
                    Cut::Upto(at as u32)
                }
            }
        })
        .collect();
    Tree {
        column,
        cut,
        default_left: list("default_left").iter().map(|x| x.as_bool().unwrap()).collect(),
        left: list("left").iter().map(|x| x.as_i64().unwrap() as i32).collect(),
        right: list("right").iter().map(|x| x.as_i64().unwrap() as i32).collect(),
        gain: list("gain").iter().map(|x| x.as_f64().unwrap()).collect(),
        value: list("value").iter().map(|x| x.as_f64().unwrap()).collect(),
        leaf_l2: Vec::new(),
    }
}

/// Partitions the items of `active` as the tree's splits did when `grow` made it, and gives each leaf's place in `work.indices`, as `grow` does.
fn replay<I: Items>(work: &mut Work, store: &Store, items: &I, tree: &Tree, active: &[u32]) -> Vec<(usize, usize)> {
    work.indices.clear();
    work.indices.extend_from_slice(active);
    let mut places = vec![(0usize, active.len())];
    // Split n made leaf n + 1 from the leaf `leaf_split[n]`; a node's left child is that leaf's descendant, its right child is a new leaf.
    let mut leaf_split = vec![0usize; tree.column.len()];
    for n in 0..tree.column.len() {
        for (child, is_left) in [(tree.left[n], true), (tree.right[n], false)] {
            if child >= 0 {
                leaf_split[child as usize] = if is_left { leaf_split[n] } else { n + 1 };
            }
        }
    }
    for n in 0..tree.column.len() {
        let at = leaf_split[n];
        let (start, len) = places[at];
        let (left_len, _) = partition(work, store, items, start, len, tree.column[n], &tree.cut[n], tree.default_left[n]);
        assert_eq!(places.len(), n + 1);
        places[at] = (start, left_len);
        places.push((start + left_len, len - left_len));
    }
    assert_eq!(places.len(), tree.value.len(), "a tree's leaves and values differ in count");
    places
}

/// `replay` on the card: partitions the pairs as the tree's splits did, and adds each leaf's value to the scores of its pairs.
fn replay_gpu(card: &gpu::Gpu, tree: &Tree, count: usize) {
    card.reset_items();
    let mut places = vec![(0usize, count)];
    let mut leaf_split = vec![0usize; tree.column.len()];
    for n in 0..tree.column.len() {
        for (child, is_left) in [(tree.left[n], true), (tree.right[n], false)] {
            if child >= 0 {
                leaf_split[child as usize] = if is_left { leaf_split[n] } else { n + 1 };
            }
        }
    }
    for n in 0..tree.column.len() {
        let at = leaf_split[n];
        let (start, len) = places[at];
        let (left_len, _) = card.partition(start, len, tree.column[n], &tree.cut[n], tree.default_left[n]);
        places[at] = (start, left_len);
        places.push((start + left_len, len - left_len));
    }
    assert_eq!(places.len(), tree.value.len(), "a tree's leaves and values differ in count");
    for (leaf, &(start, len)) in places.iter().enumerate() {
        card.add_value(start, len, tree.value[leaf]);
    }
}

struct CardLeaf {
    start: usize,
    len: usize,
    rows: usize,
    g: f64,
    h: f64,
    /// The card's histogram of the leaf, while the leaf can split.
    slot: Option<u32>,
    best: Option<Split>,
    open: Vec<u32>,
    parent: i32,
    is_left: bool,
    /// The L2 term of the leaf's value.
    l2: f64,
}

/// `grow` with the histograms, the partitions and the order of the pairs on the card. The choice of the leaf, the best split of a histogram (the histogram is copied
/// to the host) and the tree are as in `grow`. `times` gets the seconds of the partitions, of the copies of the histograms, of the fills, and of `best_split`.
fn grow_gpu(card: &mut gpu::Gpu, store: &Store, config: &Config, used: &[u32], count: usize, times: &mut [f64; 4]) -> (Tree, Vec<(usize, usize)>) {
    let profile = std::env::var_os("BB_SYNC_PROFILE").is_some();
    let root_slot = card.take_slot();
    let began = Instant::now();
    let (sum_g, sum_h) = card.root(root_slot);
    let (g, h) = (sum_g, EPSILON + sum_h);
    times[2] += began.elapsed().as_secs_f64();
    let began = Instant::now();
    let mut left_hist = vec![Bin::default(); store.bins];
    let mut right_hist = vec![Bin::default(); store.bins];
    card.download(root_slot, &mut left_hist);
    times[1] += began.elapsed().as_secs_f64();
    let began = Instant::now();
    let (best, open) = best_split(store, used, &left_hist, (g, h, store.rows as f64), config, &[]);
    times[3] += began.elapsed().as_secs_f64();
    let mut leaves = vec![CardLeaf { start: 0, len: count, rows: store.rows, g, h, slot: Some(root_slot), best, open, parent: -1, is_left: false, l2: config.lambda_l2 }];
    let mut tree = Tree::default();
    while leaves.len() < config.num_leaves {
        let mut chosen = None;
        let mut most = 0.0;
        for (at, leaf) in leaves.iter().enumerate() {
            if let Some(split) = &leaf.best {
                if split.gain > most {
                    most = split.gain;
                    chosen = Some(at);
                }
            }
        }
        let Some(at) = chosen else { break };
        let split = leaves[at].best.take().unwrap();
        let (start, len) = (leaves[at].start, leaves[at].len);
        let began = Instant::now();
        let (left_len, left_rows) = card.partition(start, len, split.column, &split.cut, split.default_left);
        times[0] += began.elapsed().as_secs_f64();
        let node = tree.column.len() as i32;
        tree.column.push(split.column);
        tree.cut.push(split.cut.clone());
        tree.default_left.push(split.default_left);
        tree.gain.push(split.gain);
        let right_leaf = leaves.len();
        tree.left.push(!(at as i32));
        tree.right.push(!(right_leaf as i32));
        let (parent, is_left) = (leaves[at].parent, leaves[at].is_left);
        if parent >= 0 {
            if is_left {
                tree.left[parent as usize] = node;
            } else {
                tree.right[parent as usize] = node;
            }
        }
        let (total_g, total_h) = (leaves[at].g, leaves[at].h);
        let (left_g, left_h) = (split.left_g, split.left_h + EPSILON);
        let (right_g, right_h) = (total_g - split.left_g, (total_h - split.left_h).max(EPSILON));
        let right_len = len - left_len;
        let right_rows = leaves[at].rows - left_rows;
        // The smaller child's histogram is read from its pairs, and the larger's is what remains of its parent's.
        let began = Instant::now();
        let parent_slot = leaves[at].slot.take().expect("a leaf that splits has its histogram");
        let small_slot = card.take_slot();
        let (small_start, small_len) = if left_len < right_len { (start, left_len) } else { (start + left_len, right_len) };
        card.fill(small_slot, small_start, small_len);
        card.subtract(parent_slot, small_slot);
        if profile {
            card.sync();
        }
        times[2] += began.elapsed().as_secs_f64();
        let (left_slot, right_slot) = if left_len < right_len { (small_slot, parent_slot) } else { (parent_slot, small_slot) };
        let began = Instant::now();
        card.download(left_slot, &mut left_hist);
        card.download(right_slot, &mut right_hist);
        times[1] += began.elapsed().as_secs_f64();
        let open = std::mem::take(&mut leaves[at].open);
        let began = Instant::now();
        let (left_best, left_open) = best_split(store, &open, &left_hist, (left_g, left_h, left_rows as f64), config, &[]);
        let (right_best, right_open) = best_split(store, &open, &right_hist, (right_g, right_h, right_rows as f64), config, &[]);
        times[3] += began.elapsed().as_secs_f64();
        leaves[at] = CardLeaf { start, len: left_len, rows: left_rows, g: left_g, h: left_h, slot: Some(left_slot), best: left_best, open: left_open, parent: node, is_left: true, l2: split.child_l2 };
        if leaves[at].best.is_none() {
            card.give_slot(leaves[at].slot.take().unwrap());
        }
        let mut right = CardLeaf { start: start + left_len, len: right_len, rows: right_rows, g: right_g, h: right_h, slot: Some(right_slot), best: right_best, open: right_open, parent: node, is_left: false, l2: split.child_l2 };
        if right.best.is_none() {
            card.give_slot(right.slot.take().unwrap());
        }
        leaves.push(right);
    }
    let mut places = Vec::with_capacity(leaves.len());
    tree.value = vec![0.0; leaves.len()];
    tree.leaf_l2 = leaves.iter().map(|leaf| leaf.l2).collect();
    for (at, leaf) in leaves.iter_mut().enumerate() {
        if let Some(slot) = leaf.slot.take() {
            card.give_slot(slot);
        }
        places.push((leaf.start, leaf.len));
        tree.value[at] = if tree.column.is_empty() { 0.0 } else { leaf_output_l2(leaf.g, leaf.h, leaf.l2, config) * config.learning_rate };
    }
    (tree, places)
}

const CHECKPOINT_MAGIC: u64 = 0x4b43_5042_4f4f_5354;

fn checkpoint_path(dir: &Path, trees: usize) -> PathBuf {
    dir.join(format!("checkpoint.{trees}.zst"))
}

/// What a resume needs besides the trees, as a fit holds it after `trees` rounds.
struct CheckpointState<'a> {
    trees: usize,
    /// The column sampler's state: the generator, and the order of the columns that its swaps made.
    random: u64,
    columns: &'a [u32],
    gain: &'a [f64],
    splits: &'a [u32],
    biggest_leaf: f64,
    /// The score of each pair of rows.
    pair_score: &'a [f64],
    /// `line_hash` of the model lines of the trees, so a checkpoint is used only with the lines it was made with.
    model_hash: u64,
}

/// The hash of the model lines so far, with `line` (its bytes, with its newline) after them.
fn line_hash(before: u64, line: &[u8]) -> u64 {
    let mut hash = mix(before ^ line.len() as u64);
    for chunk in line.chunks(8) {
        let mut word = [0u8; 8];
        word[..chunk.len()].copy_from_slice(chunk);
        hash = mix(hash ^ u64::from_le_bytes(word));
    }
    hash
}

struct Loaded {
    random: u64,
    columns: Vec<u32>,
    gain: Vec<f64>,
    splits: Vec<u32>,
    biggest_leaf: f64,
    pair_score: Vec<f64>,
}

/// Writes a checkpoint as one zstd stream to `checkpoint.working` in `dir`, and then renames it to `checkpoint.<trees>.zst`. A rename is whole or absent,
/// so a fit that stops while it writes leaves the last whole checkpoint.
fn write_checkpoint(dir: &Path, fingerprint: u64, state: &CheckpointState) -> std::io::Result<PathBuf> {
    let working = dir.join("checkpoint.working");
    let mut out = zstd::stream::write::Encoder::new(BufWriter::new(File::create(&working)?), 1)?;
    let header = [CHECKPOINT_MAGIC, fingerprint, state.trees as u64, state.random, state.columns.len() as u64, state.pair_score.len() as u64, state.biggest_leaf.to_bits(), state.model_hash];
    out.write_all(bytes_of(&header))?;
    out.write_all(bytes_of(state.columns))?;
    out.write_all(bytes_of(state.gain))?;
    out.write_all(bytes_of(state.splits))?;
    out.write_all(bytes_of(state.pair_score))?;
    out.write_all(bytes_of(&[CHECKPOINT_MAGIC]))?;
    out.finish()?.flush()?;
    let path = checkpoint_path(dir, state.trees);
    fs::rename(&working, &path)?;
    Ok(path)
}

fn read_array<T: Copy + Default>(input: &mut impl Read, len: usize, what: &str) -> Result<Vec<T>, String> {
    let mut out = vec![T::default(); len];
    input.read_exact(bytes_of_mut(&mut out)).map_err(|e| format!("{what}: {e}"))?;
    Ok(out)
}

/// Reads a checkpoint of `trees` trees. It gives why it cannot where the file is cut short or was made for other settings or another store.
fn read_checkpoint(path: &Path, fingerprint: u64, trees: usize, kept: usize, pairs: usize, model_hash: u64) -> Result<Loaded, String> {
    let file = File::open(path).map_err(|e| format!("{}: {e}", path.display()))?;
    let mut input = zstd::stream::read::Decoder::new(file).map_err(|e| e.to_string())?;
    let header: Vec<u64> = read_array(&mut input, 8, "header")?;
    if header[0] != CHECKPOINT_MAGIC {
        return Err("not a checkpoint".to_string());
    }
    if header[1] != fingerprint {
        return Err("made for other settings, seed or store".to_string());
    }
    if header[2] != trees as u64 || header[4] != kept as u64 || header[5] != pairs as u64 {
        return Err("made for other counts of trees, columns or pairs".to_string());
    }
    if header[7] != model_hash {
        return Err("made with other model lines".to_string());
    }
    let columns = read_array(&mut input, kept, "columns")?;
    let gain = read_array(&mut input, kept, "gain")?;
    let splits = read_array(&mut input, kept, "splits")?;
    let pair_score = read_array(&mut input, pairs, "score")?;
    let end: Vec<u64> = read_array(&mut input, 1, "end")?;
    if end[0] != CHECKPOINT_MAGIC {
        return Err("no end mark".to_string());
    }
    Ok(Loaded { random: header[3], columns, gain, splits, biggest_leaf: f64::from_bits(header[6]), pair_score })
}

/// Fits on the train groups and stops on the dev groups, as `fit_trees.py` does with LightGBM. Where the JSON has no `dev`, it
/// reads no dev store, runs exactly `max_rounds` rounds, and writes no dev score and no best round.
///
/// A row's leaf depends on its blocks alone, so the trees grow over pairs of rows with the same blocks (`Pairs`), and a row's score is its pair's score.
/// Only the gradient and the sums of a pair's rows go over rows.
///
/// Where the JSON has no `dev`, a fit writes a checkpoint in the folder `out` after every `checkpoint_every` rounds (default 10, 0 asks for none), and
/// after the last round. It keeps the latest. A checkpoint holds what a resume would otherwise replay the trees for.
/// Where the JSON has `resume` as {"model": FILE, "trees": k}, it starts from the first k trees of FILE, a `model.jsonl` of an earlier fit
/// with the same train store, seed and settings, and runs the rounds after k as the earlier fit would have. It reads the checkpoint of k trees from the
/// folder of FILE where there is one, and replays the k trees where there is none. It needs no dev store.
fn softmax(file: &Path, use_gpu: bool) {
    let v = read_json(file);
    let count = v["threads"].as_u64().unwrap() as usize;
    threads(count);
    let has_dev = v.get("dev").is_some_and(|d| !d.is_null());
    assert!(!(use_gpu && has_dev), "softmax-gpu has no dev store");
    let config = Config {
        learning_rate: v["learning_rate"].as_f64().unwrap(),
        num_leaves: v["num_leaves"].as_u64().unwrap() as usize,
        min_data_in_leaf: v["min_data_in_leaf"].as_f64().unwrap(),
        min_sum_hessian: v["min_sum_hessian"].as_f64().unwrap(),
        lambda_l2: v["lambda_l2"].as_f64().unwrap_or(0.0),
        max_delta_step: v["max_delta_step"].as_f64().unwrap_or(0.0),
        fraction: v["fraction"].as_f64().unwrap(),
        truncation: 0,
        max_rounds: v["max_rounds"].as_u64().unwrap() as usize,
        patience: if has_dev { v["patience"].as_u64().unwrap() as usize } else { 0 },
        admit: None,
        stream: None,
        min_tasks: 0,
        row_task: Vec::new(),
        categorical: CategoricalConfig::read(&v),
    };
    let checkpoint_every = v["checkpoint_every"].as_u64().unwrap_or(10) as usize;
    let path = |name: &str| PathBuf::from(v[name].as_str().unwrap());
    let store = Store::open(&path("train"));
    // The dev store with its group starts and labels, where the JSON names a dev store.
    let dev: Option<(Store, Vec<u32>, Vec<u8>)> = if has_dev {
        let store = Store::open(&path("dev"));
        let (start, label): (Vec<u32>, Vec<u8>) = (read_all(&path("dev_groups")), read_all(&path("dev_labels")));
        assert_eq!(label.len(), store.rows);
        Some((store, start, label))
    } else {
        None
    };
    let out = path("out");
    fs::create_dir_all(&out).unwrap();
    let (start, label): (Vec<u32>, Vec<u8>) = (read_all(&path("groups")), read_all(&path("labels")));
    assert_eq!(label.len(), store.rows);
    if !has_dev {
        assert_eq!(*start.last().unwrap() as usize, store.rows, "the last group start is the row count");
    }
    match &dev {
        Some((dev_store, dev_start, _)) => println!("rows {} dev rows {} columns {} bins {} entries {} groups {} dev groups {}", store.rows, dev_store.rows, store.kept, store.bins, store.col_entries.iter().sum::<u64>(), start.len() - 1, dev_start.len() - 1),
        None => println!("rows {} columns {} bins {} entries {} groups {} rounds {}", store.rows, store.kept, store.bins, store.col_entries.iter().sum::<u64>(), start.len() - 1, config.max_rounds),
    }
    let bounds: Vec<f64> = read_all(&path("train").join("bounds.f64"));
    let bound_start: Vec<u32> = read_all(&path("train").join("bound_start.u32"));
    let pairs_started = Instant::now();
    let mut pairs = Pairs::build(&store);
    println!("pairs {} of {} rows, {:.2} rows a pair, {:.0}s", pairs.count(), store.rows, store.rows as f64 / pairs.count().max(1) as f64, pairs_started.elapsed().as_secs_f64());
    let seed = v["seed"].as_u64().unwrap_or(0);
    let settings = [config.learning_rate.to_bits(), config.num_leaves as u64, config.min_data_in_leaf.to_bits(), config.min_sum_hessian.to_bits(), config.lambda_l2.to_bits(), config.max_delta_step.to_bits(), config.fraction.to_bits(), seed, store.rows as u64, store.kept as u64, store.bins as u64];
    let fingerprint = settings.iter().chain(&config.categorical.bits()).fold(pairs.fingerprint(), |a, &x| mix(a ^ x));
    let mut work = if use_gpu { Work::lean() } else { Work::new(&store) };
    let mut pair_score = vec![0.0f64; pairs.count()];
    let (mut pair_g, mut pair_h) = if use_gpu { (Vec::new(), Vec::new()) } else { (vec![0.0f64; pairs.count()], vec![0.0f64; pairs.count()]) };
    let mut dev_score = dev.as_ref().map_or(Vec::new(), |(dev_store, _, _)| vec![0.0f64; dev_store.rows]);
    let (mut grad, mut hess) = if use_gpu { (Vec::new(), Vec::new()) } else { (vec![0.0f32; store.rows], vec![0.0f32; store.rows]) };
    let mut random = Random(mix(seed));
    let mut columns: Vec<u32> = (0..store.kept as u32).collect();
    let sampled = ((config.fraction * store.kept as f64).round() as usize).clamp(1, store.kept.max(1));
    let active: Vec<u32> = if use_gpu { Vec::new() } else { (0..pairs.count() as u32).collect() };
    let mut gpu: Option<gpu::Gpu> = if use_gpu {
        let began = Instant::now();
        let card = gpu::Gpu::new(&store, &pairs, &label, &start, config.num_leaves);
        // The card holds the pairs of the rows now.
        pairs.rows = Vec::new();
        pairs.row_pair = Vec::new();
        println!("card holds the store {:.0}s", began.elapsed().as_secs_f64());
        Some(card)
    } else {
        None
    };
    let dev_rows: Vec<u32> = dev.as_ref().map_or(Vec::new(), |(dev_store, _, _)| (0..dev_store.rows as u32).collect());
    let (mut gain, mut splits) = (vec![0.0f64; store.kept], vec![0u32; store.kept]);
    if let Some(resume) = v.get("resume").filter(|r| !r.is_null()) {
        let same = matches!((fs::canonicalize(resume["model"].as_str().unwrap()), fs::canonicalize(out.join("model.jsonl"))), (Ok(a), Ok(b)) if a == b);
        assert!(!same, "a resume writes its own model.jsonl, so it cannot read the same file");
    }
    let mut model = BufWriter::new(File::create(out.join("model.jsonl")).unwrap());
    let (mut best_loss, mut best_round, mut best_top) = (f64::INFINITY, 0usize, 0.0);
    let (first_loss, first_top) = match &dev {
        Some((_, dev_start, dev_label)) => softmax_read(dev_start, dev_label, &dev_score),
        None => (f64::NAN, f64::NAN),
    };
    if dev.is_some() {
        println!("uniform dev loss {first_loss:.4} top {first_top:.4}");
    }
    // The rounds (1-based) at which the audit prints each leaf and walks every row through the tree; the sums of every tree are checked in all rounds.
    let audit_rounds: Vec<usize> = v["audit_rounds"].as_array().map_or(Vec::new(), |a| a.iter().filter_map(|x| x.as_u64()).map(|x| x as usize).collect());
    let mut biggest_leaf = 0.0f64;
    let mut resumed = 0usize;
    let mut model_hash = 0u64;
    if let Some(resume) = v.get("resume").filter(|r| !r.is_null()) {
        assert!(dev.is_none(), "a resumed fit has no dev store");
        let (from, count) = (PathBuf::from(resume["model"].as_str().unwrap()), resume["trees"].as_u64().unwrap() as usize);
        assert!(count <= config.max_rounds, "resume trees {count} are above max_rounds");
        let from_dir = from.parent().unwrap_or(Path::new(""));
        let saved = checkpoint_path(from_dir, count);
        let mut input = BufReader::new(File::open(&from).unwrap_or_else(|e| panic!("{}: {e}", from.display())));
        // Exactly `count` lines are read; the earlier fit may be writing the next. The earlier fit's lines stand as written.
        let mut lines = Vec::with_capacity(count);
        for _ in 0..count {
            let mut line = String::new();
            input.read_line(&mut line).unwrap();
            assert!(line.ends_with('\n'), "{} has fewer than {count} whole lines", from.display());
            model_hash = line_hash(model_hash, line.as_bytes());
            lines.push(line);
        }
        let loaded = if saved.exists() {
            match read_checkpoint(&saved, fingerprint, count, store.kept, pairs.count(), model_hash) {
                Ok(loaded) => Some(loaded),
                Err(why) => {
                    println!("{} is not used, so the {count} trees are replayed: {why}", saved.display());
                    None
                }
            }
        } else {
            None
        };
        let replay_started = Instant::now();
        for (tree_at, line) in (1..=count).zip(&lines) {
            model.write_all(line.as_bytes()).unwrap();
            if loaded.is_some() {
                continue;
            }
            let tree = tree_from_json(&serde_json::from_str(&line).unwrap(), &bounds, &bound_start);
            for i in 0..sampled {
                let j = i + random.below(store.kept - i);
                columns.swap(i, j);
            }
            if let Some(card) = &gpu {
                replay_gpu(card, &tree, pairs.count());
            } else {
                let places = {
                    let items = PairItems { pairs: &pairs, g: &pair_g, h: &pair_h };
                    replay(&mut work, &store, &items, &tree, &active)
                };
                add_leaf_values(&mut pair_score, &work.indices, &places, &tree.value);
            }
            for (&k, &g) in tree.column.iter().zip(&tree.gain) {
                gain[k as usize] += g;
                splits[k as usize] += 1;
            }
            if !tree.column.is_empty() {
                biggest_leaf = biggest_leaf.max(tree.value[largest_leaf(&tree)].abs());
            }
            if tree_at % 10 == 0 || tree_at == count {
                println!("resumed {tree_at} of {count} trees {:.0}s", replay_started.elapsed().as_secs_f64());
            }
        }
        if let Some(loaded) = loaded {
            random = Random(loaded.random);
            columns = loaded.columns;
            gain = loaded.gain;
            splits = loaded.splits;
            biggest_leaf = loaded.biggest_leaf;
            pair_score = loaded.pair_score;
            if let Some(card) = &gpu {
                card.set_score(&pair_score);
            }
            println!("resumed {count} trees from {} {:.0}s", saved.display(), replay_started.elapsed().as_secs_f64());
        }
        model.flush().unwrap();
        resumed = count;
    }
    let (mut last_train_loss, mut rounds_run) = (f64::NAN, resumed);
    let started = Instant::now();
    // The seconds of the rounds so far in the gradient, in the pairs' sums, in growing the tree, and in the rest (the score, the model and the checkpoint).
    let mut seconds = [0.0f64; 4];
    let mut last_checkpoint: Option<PathBuf> = None;
    work.time = [0.0; 4];
    for round in resumed + 1..=config.max_rounds {
        let mut train_loss = 0.0;
        let round_started = Instant::now();
        let phase = Instant::now();
        if let Some(card) = &gpu {
            train_loss += card.gradient() / (start.len() - 1).max(1) as f64;
        } else {
            let (mut rest_g, mut rest_h) = (&mut grad[..], &mut hess[..]);
            let mut slices = Vec::with_capacity(start.len() - 1);
            for g in 0..start.len() - 1 {
                let length = (start[g + 1] - start[g]) as usize;
                let (here_g, after_g) = rest_g.split_at_mut(length);
                let (here_h, after_h) = rest_h.split_at_mut(length);
                rest_g = after_g;
                rest_h = after_h;
                slices.push((g, here_g, here_h));
            }
            let total: f64 = slices
                .into_par_iter()
                .map_init(
                    || (Vec::<(f64, f64)>::new(), Vec::<f64>::new()),
                    |(terms, scores), (g, here_g, here_h)| {
                        let (a, b) = (start[g] as usize, start[g + 1] as usize);
                        scores.clear();
                        scores.extend(pairs.row_pair[a..b].iter().map(|&p| pair_score[p as usize]));
                        softmax_group(scores, &label[a..b], here_g, here_h, terms)
                    },
                )
                .sum();
            train_loss += total / (start.len() - 1).max(1) as f64;
        }
        seconds[0] += phase.elapsed().as_secs_f64();
        let phase = Instant::now();
        if !use_gpu {
            pair_sums(&pairs, &grad, &hess, &mut pair_g, &mut pair_h);
        }
        seconds[1] += phase.elapsed().as_secs_f64();
        let phase = Instant::now();
        for i in 0..sampled {
            let j = i + random.below(store.kept - i);
            columns.swap(i, j);
        }
        let mut used = columns[..sampled].to_vec();
        used.sort_unstable();
        let items = PairItems { pairs: &pairs, g: &pair_g, h: &pair_h };
        let (tree, places) = match &mut gpu {
            Some(card) => grow_gpu(card, &store, &config, &used, pairs.count(), &mut work.time),
            None => grow(&mut work, &store, &config, &items, &active, &used),
        };
        let empty = tree.column.is_empty();
        if !use_gpu {
            audit_tree(&store, &items, &tree, &places, &work.indices, &config, round, audit_rounds.contains(&round), &mut biggest_leaf);
        }
        seconds[2] += phase.elapsed().as_secs_f64();
        let phase = Instant::now();
        match &gpu {
            Some(card) => {
                for (leaf, &(at, len)) in places.iter().enumerate() {
                    card.add_value(at, len, tree.value[leaf]);
                }
            }
            None => add_leaf_values(&mut pair_score, &work.indices, &places, &tree.value),
        }
        rounds_run = round;
        last_train_loss = train_loss;
        for (&k, &g) in tree.column.iter().zip(&tree.gain) {
            gain[k as usize] += g;
            splits[k as usize] += 1;
        }
        let Some((dev_store, dev_start, dev_label)) = &dev else {
            // No dev set: every round runs, and each tree is on disk once it is made.
            let line = format!("{}\n", tree_json(&tree, &bounds, &bound_start, &store.has_nan));
            model.write_all(line.as_bytes()).unwrap();
            model_hash = line_hash(model_hash, line.as_bytes());
            model.flush().unwrap();
            if checkpoint_every > 0 && (round % checkpoint_every == 0 || round == config.max_rounds) {
                let checkpoint_started = Instant::now();
                if let Some(card) = &gpu {
                    card.get_score(&mut pair_score);
                }
                let state = CheckpointState { trees: round, random: random.0, columns: &columns, gain: &gain, splits: &splits, biggest_leaf, pair_score: &pair_score, model_hash };
                match write_checkpoint(&out, fingerprint, &state) {
                    Ok(saved) => {
                        let bytes = fs::metadata(&saved).map_or(0, |m| m.len());
                        if let Some(older) = last_checkpoint.replace(saved.clone()) {
                            if older != saved {
                                let _ = fs::remove_file(older);
                            }
                        }
                        println!("checkpoint of {round} trees, {:.0} MB, {:.1}s", bytes as f64 / 1e6, checkpoint_started.elapsed().as_secs_f64());
                    }
                    Err(why) => println!("checkpoint of {round} trees was not written: {why}"),
                }
            }
            seconds[3] += phase.elapsed().as_secs_f64();
            if use_gpu {
                println!("round {round} train loss {train_loss:.6} {:.3}s", round_started.elapsed().as_secs_f64());
            }
            if round % 25 == 0 || round == config.max_rounds || empty {
                let elapsed = started.elapsed().as_secs_f64();
                let done = (round - resumed) as f64;
                let rate = done / elapsed;
                println!(
                    "round {round} of {} train loss {train_loss:.4}{} max |leaf| so far {biggest_leaf:.1} {rate:.2} rounds/s eta {:.0}s rss {:.2} GiB; a round: gradient {:.2}s pair sums {:.2}s tree {:.2}s (partition {:.2}s gather {:.2}s fill {:.2}s best split {:.2}s other {:.2}s) rest {:.2}s",
                    config.max_rounds,
                    if empty { " (no split)" } else { "" },
                    (config.max_rounds - round) as f64 / rate,
                    resident_gib(),
                    seconds[0] / done,
                    seconds[1] / done,
                    seconds[2] / done,
                    work.time[0] / done,
                    work.time[1] / done,
                    work.time[2] / done,
                    work.time[3] / done,
                    (seconds[2] - work.time.iter().sum::<f64>()) / done,
                    seconds[3] / done
                );
            }
            continue;
        };
        let moves: Vec<f64> = dev_rows.par_iter().with_min_len(256).map(|&row| tree.value[tree.leaf_of(dev_store, row)]).collect();
        for (held, step) in dev_score.iter_mut().zip(moves) {
            *held += step;
        }
        let (loss, top) = softmax_read(dev_start, dev_label, &dev_score);
        if loss < best_loss {
            best_loss = loss;
            best_round = round;
            best_top = top;
            write_all(&out.join("dev_best.f64"), &dev_score);
        }
        writeln!(model, "{}", tree_json(&tree, &bounds, &bound_start, &store.has_nan)).unwrap();
        if round % 25 == 0 || empty {
            println!("round {round} train loss {train_loss:.4} dev loss {loss:.4} top {top:.4} best {best_loss:.4} at {best_round} {:.2} rounds/s rss {:.2} GiB", round as f64 / started.elapsed().as_secs_f64(), resident_gib());
        }
        if empty || round >= best_round + config.patience {
            break;
        }
    }
    model.flush().unwrap();
    write_all(&out.join("gain.f64"), &gain);
    write_all(&out.join("splits.u32"), &splits);
    let result = if dev.is_some() {
        json!({"best_round": best_round, "dev_loss": best_loss, "dev_top": best_top, "uniform_loss": first_loss, "uniform_top": first_top, "seconds": started.elapsed().as_secs_f64(), "rss_gib": resident_gib()})
    } else {
        json!({"rounds": rounds_run, "train_loss": last_train_loss, "seconds": started.elapsed().as_secs_f64(), "rss_gib": resident_gib()})
    };
    fs::write(out.join("result.json"), result.to_string()).unwrap();
    println!("done {result}");
}

fn main() {
    let arguments: Vec<String> = std::env::args().collect();
    let usage = "block-boost scan DIR | compile DIR | fit FILE | softmax FILE | softmax-gpu FILE";
    let command = arguments.get(1).expect(usage).as_str();
    let path = PathBuf::from(arguments.get(2).expect(usage));
    match command {
        "scan" => scan(&path),
        "compile" => compile(&path),
        "fit" => fit(&path),
        "softmax" => softmax(&path, false),
        "softmax-gpu" => softmax(&path, true),
        _ => panic!("{usage}"),
    }
}
