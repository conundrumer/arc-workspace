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
//!
//! The objective and the tree growth are those of LightGBM's lambdarank, with the same parameters. A histogram entry holds
//! the sums of a bin, and a leaf's rows add their sums to the blocks first, so one block's entries are read once for a leaf.

use rayon::prelude::*;
use serde_json::{Value, json};
use std::fs::{self, File};
use std::io::{BufReader, BufWriter, Read, Write};
use std::ops::Deref;
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
fn find_bins(dir: &Path, plan: &Plan, keep: &[i32], kept: usize) {
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
                    if held <= plan.sample_cap || random.unit() < plan.sample_cap as f64 / held as f64 {
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
        if k >= 0 && nans[logical] > 0 {
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
            column_bounds(&values, &counts, plan.max_bin, has_nan[k] != 0)
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
            find_bins(dir, &plan, &keep, kept);
            dir.to_path_buf()
        }
    };
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
    least: u32,
    most: u32,
}

struct Store {
    rows: usize,
    kept: usize,
    bins: usize,
    col_start: Vec<u32>,
    zero_pos: Vec<u32>,
    has_nan: Vec<u8>,
    col_uses: Vec<u64>,
    col_entries: Vec<u64>,
    maps: Vec<Mapped<u32>>,
    uses: Vec<UseData>,
}

impl Store {
    fn open(dir: &Path) -> Store {
        let meta = read_json(&dir.join("compiled.json"));
        Store {
            rows: meta["rows"].as_u64().unwrap() as usize,
            kept: meta["kept"].as_u64().unwrap() as usize,
            bins: meta["bins"].as_u64().unwrap() as usize,
            col_start: read_all(&dir.join("col_start.u32")),
            zero_pos: read_all(&dir.join("zero_pos.u32")),
            has_nan: read_all(&dir.join("has_nan.u8")),
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
                    least: u["least"].as_u64().unwrap() as u32,
                    most: u["most"].as_u64().unwrap() as u32,
                })
                .collect(),
        }
    }

    /// Whether a row goes left at a split: its value's place among the column's bins is at or before `pos`.
    #[inline]
    fn left(&self, row: u32, column: u32, pos: u32, default_left: bool) -> bool {
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
                return place <= pos;
            }
        }
        zero <= pos
    }
}

#[derive(Clone, Copy, Default)]
#[repr(C)]
struct Bin {
    g: f64,
    h: f64,
}

#[derive(Clone, Copy)]
struct Split {
    column: u32,
    pos: u32,
    default_left: bool,
    gain: f64,
    left_g: f64,
    left_h: f64,
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
}

/// A leaf's output before the learning rate: -G/(H + lambda_l2), limited to +-max_delta_step where that is above 0.
fn leaf_output(g: f64, h: f64, config: &Config) -> f64 {
    let output = -g / (h + config.lambda_l2);
    if config.max_delta_step > 0.0 { output.clamp(-config.max_delta_step, config.max_delta_step) } else { output }
}

/// What a leaf adds to the sum of gains, as LightGBM's `GetLeafGain`: G^2/(H + lambda_l2), and with max_delta_step the gain of the limited output w,
/// -(2 G w + (H + lambda_l2) w^2).
fn leaf_gain(g: f64, h: f64, config: &Config) -> f64 {
    if config.max_delta_step > 0.0 {
        let w = leaf_output(g, h, config);
        -(2.0 * g * w + (h + config.lambda_l2) * w * w)
    } else {
        g * g / (h + config.lambda_l2)
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
    pos: Vec<u32>,
    default_left: Vec<bool>,
    left: Vec<i32>,
    right: Vec<i32>,
    gain: Vec<f64>,
    value: Vec<f64>,
}

impl Tree {
    fn leaf_of(&self, store: &Store, row: u32) -> usize {
        if self.column.is_empty() {
            return 0;
        }
        let mut node = 0i32;
        loop {
            let n = node as usize;
            node = if store.left(row, self.column[n], self.pos[n], self.default_left[n]) { self.left[n] } else { self.right[n] };
            if node < 0 {
                return !node as usize;
            }
        }
    }
}

/// A leaf's rows' sums per block of one map.
struct Sums {
    g: Vec<f64>,
    h: Vec<f64>,
    seen: Vec<bool>,
    touched: Vec<u32>,
}

struct Work {
    sums: Vec<Sums>,
    pool: Vec<Vec<Bin>>,
    seen: Vec<bool>,
    indices: Vec<u32>,
    scratch: Vec<u32>,
    flags: Vec<bool>,
    ranges: Vec<(u32, u32)>,
}

impl Work {
    fn new(store: &Store, threads: usize) -> Work {
        let sums = store
            .maps
            .iter()
            .map(|map| {
                let blocks = map.iter().filter(|&&b| b != NONE).map(|&b| b as usize + 1).max().unwrap_or(0);
                Sums { g: vec![0.0; blocks], h: vec![0.0; blocks], seen: vec![false; blocks], touched: Vec::new() }
            })
            .collect();
        // Each range of bins holds about one share of the entries, and one thread at a time works on it.
        let total: u64 = store.col_entries.iter().sum();
        let shares = (threads * 2).max(1) as u64;
        let mut ranges = Vec::new();
        let (mut low, mut held) = (0u32, 0u64);
        for k in 0..store.kept {
            held += store.col_entries[k];
            if held >= total / shares + 1 {
                ranges.push((low, store.col_start[k + 1]));
                low = store.col_start[k + 1];
                held = 0;
            }
        }
        if (low as usize) < store.bins {
            ranges.push((low, store.bins as u32));
        }
        Work { sums, pool: Vec::new(), seen: vec![false; store.bins], indices: Vec::new(), scratch: Vec::new(), flags: Vec::new(), ranges }
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

fn add_blocks(work: &mut Work, store: &Store, rows: std::ops::Range<usize>, grad: &[f32], hess: &[f32]) {
    let here = &work.indices[rows];
    for (m, map) in store.maps.iter().enumerate() {
        let sums = &mut work.sums[m];
        for &row in here {
            let block = map[row as usize];
            if block == NONE {
                continue;
            }
            let b = block as usize;
            if !sums.seen[b] {
                sums.seen[b] = true;
                sums.touched.push(block);
            }
            sums.g[b] += grad[row as usize] as f64;
            sums.h[b] += hess[row as usize] as f64;
        }
    }
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

/// Adds each touched block's sums to the bins of its entries. With `track`, gives each bin that holds an entry of these rows, once.
fn fill_histogram(work: &mut Work, store: &Store, rows: std::ops::Range<usize>, grad: &[f32], hess: &[f32], hist: &mut [Bin], track: bool) -> Vec<u32> {
    add_blocks(work, store, rows, grad, hess);
    let mut seen = std::mem::take(&mut work.seen);
    let mut slices: Vec<(u32, u32, &mut [Bin], &mut [bool])> = Vec::with_capacity(work.ranges.len());
    let (mut rest, mut rest_seen) = (hist, seen.as_mut_slice());
    let mut at = 0u32;
    for &(low, high) in &work.ranges {
        assert_eq!(low, at);
        let (here, after) = rest.split_at_mut((high - low) as usize);
        let (marks, after_marks) = rest_seen.split_at_mut((high - low) as usize);
        slices.push((low, high, here, marks));
        rest = after;
        rest_seen = after_marks;
        at = high;
    }
    let sums = &work.sums;
    let lists: Vec<Vec<u32>> = slices.par_iter_mut().map(|(low, high, slice, marks)| {
        let (low, high) = (*low, *high);
        let mut local = Vec::new();
        for data in &store.uses {
            if data.most < low || data.least >= high {
                continue;
            }
            let held = &sums[data.map];
            for &block in &held.touched {
                let b = block as usize;
                let entries = &data.bid[data.ptr[b] as usize..data.ptr[b + 1] as usize];
                let start = if low == 0 { 0 } else { entries.partition_point(|&x| x < low) };
                let (g, h) = (held.g[b], held.h[b]);
                for &bid in &entries[start..] {
                    if bid >= high {
                        break;
                    }
                    // A bid in this range lies inside this slice.
                    let bin = unsafe { slice.get_unchecked_mut((bid - low) as usize) };
                    bin.g += g;
                    bin.h += h;
                    if track {
                        let mark = unsafe { marks.get_unchecked_mut((bid - low) as usize) };
                        if !*mark {
                            *mark = true;
                            local.push(bid);
                        }
                    }
                }
            }
        }
        local
    }).collect();
    let touched = lists.concat();
    for &b in &touched {
        seen[b as usize] = false;
    }
    work.seen = seen;
    clear_blocks(work);
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
        if gain > parent && best.is_none_or(|b| gain - parent > b.gain) {
            best = Some(Split { column: k as u32, pos: pos as u32, default_left: nan_left, gain: gain - parent, left_g, left_h: left_h - EPSILON });
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
        .par_chunks(4096)
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
    let best = if config.min_tasks == 0 { tops.first().copied() } else { tops.into_iter().find(|split| both_sides_hold_tasks(store, config, rows, split)) };
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
        if store.left(row, split.column, split.pos, split.default_left) {
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

struct Leaf {
    start: usize,
    len: usize,
    g: f64,
    h: f64,
    hist: Option<Vec<Bin>>,
    touched: Option<Vec<u32>>,
    best: Option<Split>,
    open: Vec<u32>,
    parent: i32,
    is_left: bool,
}

/// One tree over the rows in `active`, best leaf first. It leaves each leaf's rows in `work.indices` and gives each leaf's
/// place in that array.
fn grow(work: &mut Work, store: &Store, config: &Config, active: &[u32], grad: &[f32], hess: &[f32], used: &[u32]) -> (Tree, Vec<(usize, usize)>) {
    work.indices.clear();
    work.indices.extend_from_slice(active);
    let (mut g, mut h) = (0.0f64, EPSILON);
    for &row in active {
        g += grad[row as usize] as f64;
        h += hess[row as usize] as f64;
    }
    let mut hist = work.take(store);
    fill_histogram(work, store, 0..active.len(), grad, hess, &mut hist, false);
    let (best, open) = best_split(store, used, &hist, (g, h, active.len() as f64), config, active);
    let mut leaves = vec![Leaf { start: 0, len: active.len(), g, h, hist: Some(hist), touched: None, best, open, parent: -1, is_left: false }];
    let mut tree = Tree::default();
    while leaves.len() < config.num_leaves {
        let mut chosen = None;
        let mut most = 0.0;
        for (at, leaf) in leaves.iter().enumerate() {
            if let Some(split) = leaf.best {
                if split.gain > most {
                    most = split.gain;
                    chosen = Some(at);
                }
            }
        }
        let Some(at) = chosen else { break };
        let split = leaves[at].best.take().unwrap();
        let (start, len) = (leaves[at].start, leaves[at].len);
        // A stable partition of the leaf's rows.
        work.flags.resize(len, false);
        {
            let rows = &work.indices[start..start + len];
            work.flags.par_iter_mut().zip(rows.par_iter()).with_min_len(1024).for_each(|(flag, &row)| {
                *flag = store.left(row, split.column, split.pos, split.default_left);
            });
        }
        work.scratch.clear();
        let mut left_len = 0;
        for i in 0..len {
            let row = work.indices[start + i];
            if work.flags[i] {
                work.indices[start + left_len] = row;
                left_len += 1;
            } else {
                work.scratch.push(row);
            }
        }
        work.indices[start + left_len..start + len].copy_from_slice(&work.scratch);
        let node = tree.column.len() as i32;
        tree.column.push(split.column);
        tree.pos.push(split.pos);
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
        // The smaller child's histogram is read from its rows, and the larger's is what remains of its parent's. Where the
        // parent's histogram was given up, the larger child's is read from its rows too.
        let parent_hist = leaves[at].hist.take();
        let parent_touched = leaves[at].touched.take();
        let mut smaller = work.take(store);
        let (small_rows, large_rows) = if left_len < right_len { (start..start + left_len, start + left_len..start + len) } else { (start + left_len..start + len, start..start + left_len) };
        let small_touched = fill_histogram(work, store, small_rows, grad, hess, &mut smaller, true);
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
                let touched = fill_histogram(work, store, large_rows, grad, hess, &mut larger, true);
                (larger, Some(touched))
            }
        };
        let (left_hist, left_touched, right_hist, right_touched) = if left_len < right_len { (smaller, Some(small_touched), larger, large_touched) } else { (larger, large_touched, smaller, Some(small_touched)) };
        let open = std::mem::take(&mut leaves[at].open);
        let (left_best, left_open) = best_split(store, &open, &left_hist, (left_g, left_h, left_len as f64), config, &work.indices[start..start + left_len]);
        let (right_best, right_open) = best_split(store, &open, &right_hist, (right_g, right_h, right_len as f64), config, &work.indices[start + left_len..start + len]);
        leaves[at] = Leaf { start, len: left_len, g: left_g, h: left_h, hist: None, touched: None, best: left_best, open: left_open, parent: node, is_left: true };
        if left_best.is_some() {
            leaves[at].hist = Some(left_hist);
            leaves[at].touched = left_touched;
        } else {
            work.give(left_hist, left_touched);
        }
        let mut right = Leaf { start: start + left_len, len: right_len, g: right_g, h: right_h, hist: None, touched: None, best: right_best, open: right_open, parent: node, is_left: false };
        if right_best.is_some() {
            right.hist = Some(right_hist);
            right.touched = right_touched;
        } else {
            work.give(right_hist, right_touched);
        }
        leaves.push(right);
        // Past the pool's size, the leaf least likely to split next gives up its histogram.
        let pool = (HISTOGRAM_BYTES / (store.bins.max(1) * std::mem::size_of::<Bin>())).max(2);
        while leaves.iter().filter(|leaf| leaf.hist.is_some()).count() > pool {
            let weakest = leaves.iter().enumerate().filter(|(_, leaf)| leaf.hist.is_some()).min_by(|(_, a), (_, b)| a.best.map_or(0.0, |s| s.gain).total_cmp(&b.best.map_or(0.0, |s| s.gain))).unwrap().0;
            let hist = leaves[weakest].hist.take().unwrap();
            let touched = leaves[weakest].touched.take();
            work.give(hist, touched);
        }
    }
    let mut places = Vec::with_capacity(leaves.len());
    tree.value = vec![0.0; leaves.len()];
    for (at, leaf) in leaves.iter_mut().enumerate() {
        if let Some(hist) = leaf.hist.take() {
            let touched = leaf.touched.take();
            work.give(hist, touched);
        }
        places.push((leaf.start, leaf.len));
        tree.value[at] = if tree.column.is_empty() { 0.0 } else { leaf_output(leaf.g, leaf.h, config) * config.learning_rate };
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
fn boost(store: &Store, groups: &Groups, active: &[bool], held: Option<&[bool]>, dev: Option<(&Store, &Groups)>, config: &Config, seed: u64, rounds: usize, threads: usize, name: &str) -> (Vec<Tree>, usize, Vec<f64>) {
    let mut work = Work::new(store, threads);
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
        let (tree, places) = grow(&mut work, store, config, &active_rows, &grad, &hess, &used);
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
        for (leaf, &(start, len)) in places.iter().enumerate() {
            for &row in &work.indices[start..start + len] {
                score[row as usize] += tree.value[leaf];
            }
        }
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

fn tree_json(tree: &Tree, bounds: &[f64], bound_start: &[u32], has_nan: &[u8]) -> Value {
    let threshold: Vec<f64> = tree.column.iter().zip(&tree.pos).map(|(&k, &pos)| bounds[bound_start[k as usize] as usize + pos as usize]).collect();
    // A threshold of no finite bound sends every number left.
    let threshold: Vec<Value> = threshold.iter().map(|&x| if x.is_finite() { json!(x) } else { Value::Null }).collect();
    // A column with no NaN in the fit reads a NaN as its default, 0, as `compile` does.
    let nan_seen: Vec<bool> = tree.column.iter().map(|&k| has_nan[k as usize] != 0).collect();
    json!({"column": tree.column, "threshold": threshold, "default_left": tree.default_left, "nan_seen": nan_seen, "gain": tree.gain, "left": tree.left, "right": tree.right, "value": tree.value})
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
        let (trees, best_round, _) = boost(&store, &groups, &inner, Some(&held), dev_watch, &config, seed, config.max_rounds, count, &format!("seed {seed} inner"));
        drop(trees);
        let rounds = best_round.max(10);
        let every = vec![true; groups.count()];
        let (trees, _, score) = boost(&store, &groups, &every, None, None, &config, seed, rounds, count, &format!("seed {seed} final"));
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
fn softmax_group(score: &[f64], label: &[u8], grad: &mut [f32], hess: &mut [f32]) -> f64 {
    let (most, most_positive) = group_maxima(score, label);
    let (mut all, mut positive) = (0.0, 0.0);
    for (&s, &l) in score.iter().zip(label) {
        all += (s - most).exp();
        if l > 0 {
            positive += (s - most_positive).exp();
        }
    }
    for i in 0..score.len() {
        let p = (score[i] - most).exp() / all;
        let q = if label[i] > 0 { (score[i] - most_positive).exp() / positive } else { 0.0 };
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

/// Checks one grown tree against its rows. For each leaf it sums the gradients and Hessians of the rows that the partition put in it, and compares the leaf's
/// value with -G/H x learning rate of those sums; it prints the leaf where they differ by a relative 1e-6, and the leaf with the largest value where that
/// is above 50. With `full`, it prints every leaf, and it walks every row through the tree (`Store::left`) and counts the rows whose leaf differs from the partition's.
fn audit_tree(store: &Store, tree: &Tree, places: &[(usize, usize)], indices: &[u32], grad: &[f32], hess: &[f32], config: &Config, round: usize, full: bool, biggest: &mut f64) {
    if tree.column.is_empty() {
        return;
    }
    let sums: Vec<(f64, f64)> = places
        .par_iter()
        .map(|&(start, len)| {
            let (mut g, mut h) = (0.0f64, 0.0f64);
            for &row in &indices[start..start + len] {
                g += grad[row as usize] as f64;
                h += hess[row as usize] as f64;
            }
            (g, h)
        })
        .collect();
    let mut largest = 0usize;
    for (leaf, &(g, h)) in sums.iter().enumerate() {
        let implied = leaf_output(g, h + EPSILON, config) * config.learning_rate;
        let relative = (tree.value[leaf] - implied).abs() / implied.abs().max(1e-12);
        if relative > 1e-6 {
            println!("audit round {round} leaf {leaf}: value {:.6e} but -G/H x rate of its {} rows is {implied:.6e} (G {g:.6e} H {h:.6e})", tree.value[leaf], places[leaf].1);
        }
        if full {
            println!("audit round {round} leaf {leaf}: rows {} G {g:.6e} H {h:.6e} value {:.6e} implied {implied:.6e}", places[leaf].1, tree.value[leaf]);
        }
        if tree.value[leaf].abs() > tree.value[largest].abs() {
            largest = leaf;
        }
    }
    *biggest = biggest.max(tree.value[largest].abs());
    if tree.value[largest].abs() > 50.0 {
        let (g, h) = sums[largest];
        println!("big leaf round {round} leaf {largest}: value {:.4e} rows {} G {g:.4e} H {h:.4e}", tree.value[largest], places[largest].1);
    }
    if full {
        let mut leaf_of_row = vec![0u32; store.rows];
        for (leaf, &(start, len)) in places.iter().enumerate() {
            for &row in &indices[start..start + len] {
                leaf_of_row[row as usize] = leaf as u32;
            }
        }
        let wrong: Vec<u32> = (0..store.rows as u32).into_par_iter().filter(|&row| tree.leaf_of(store, row) != leaf_of_row[row as usize] as usize).collect();
        println!("audit round {round}: {} of {} rows walk to another leaf than the partition put them in; first {:?}", wrong.len(), store.rows, &wrong[..wrong.len().min(5)]);
    }
}

/// Fits on the train groups and stops on the dev groups, as `fit_trees.py` does with LightGBM. Where the JSON has no `dev`, it
/// reads no dev store, runs exactly `max_rounds` rounds, and writes no dev score and no best round.
fn softmax(file: &Path) {
    let v = read_json(file);
    let count = v["threads"].as_u64().unwrap() as usize;
    threads(count);
    let has_dev = v.get("dev").is_some_and(|d| !d.is_null());
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
    };
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
    let mut work = Work::new(&store, count);
    let mut score = vec![0.0f64; store.rows];
    let mut dev_score = dev.as_ref().map_or(Vec::new(), |(dev_store, _, _)| vec![0.0f64; dev_store.rows]);
    let (mut grad, mut hess) = (vec![0.0f32; store.rows], vec![0.0f32; store.rows]);
    let mut random = Random(mix(v["seed"].as_u64().unwrap_or(0)));
    let mut columns: Vec<u32> = (0..store.kept as u32).collect();
    let sampled = ((config.fraction * store.kept as f64).round() as usize).clamp(1, store.kept.max(1));
    let active: Vec<u32> = (0..store.rows as u32).collect();
    let dev_rows: Vec<u32> = dev.as_ref().map_or(Vec::new(), |(dev_store, _, _)| (0..dev_store.rows as u32).collect());
    let (mut gain, mut splits) = (vec![0.0f64; store.kept], vec![0u32; store.kept]);
    let mut model = BufWriter::new(File::create(out.join("model.jsonl")).unwrap());
    let (mut best_loss, mut best_round, mut best_top) = (f64::INFINITY, 0usize, 0.0);
    let (first_loss, first_top) = match &dev {
        Some((_, dev_start, dev_label)) => softmax_read(dev_start, dev_label, &dev_score),
        None => (f64::NAN, f64::NAN),
    };
    if dev.is_some() {
        println!("uniform dev loss {first_loss:.4} top {first_top:.4}");
    }
    let (mut last_train_loss, mut rounds_run) = (f64::NAN, 0usize);
    // The rounds (1-based) at which the audit prints each leaf and walks every row through the tree; the sums of every tree are checked in all rounds.
    let audit_rounds: Vec<usize> = v["audit_rounds"].as_array().map_or(Vec::new(), |a| a.iter().filter_map(|x| x.as_u64()).map(|x| x as usize).collect());
    let mut biggest_leaf = 0.0f64;
    let started = Instant::now();
    for round in 1..=config.max_rounds {
        let mut train_loss = 0.0;
        {
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
                .map(|(g, here_g, here_h)| {
                    let (a, b) = (start[g] as usize, start[g + 1] as usize);
                    softmax_group(&score[a..b], &label[a..b], here_g, here_h)
                })
                .sum();
            train_loss += total / (start.len() - 1).max(1) as f64;
        }
        for i in 0..sampled {
            let j = i + random.below(store.kept - i);
            columns.swap(i, j);
        }
        let mut used = columns[..sampled].to_vec();
        used.sort_unstable();
        let (tree, places) = grow(&mut work, &store, &config, &active, &grad, &hess, &used);
        let empty = tree.column.is_empty();
        audit_tree(&store, &tree, &places, &work.indices, &grad, &hess, &config, round, audit_rounds.contains(&round), &mut biggest_leaf);
        for (leaf, &(start_at, len)) in places.iter().enumerate() {
            for &row in &work.indices[start_at..start_at + len] {
                score[row as usize] += tree.value[leaf];
            }
        }
        rounds_run = round;
        last_train_loss = train_loss;
        for (&k, &g) in tree.column.iter().zip(&tree.gain) {
            gain[k as usize] += g;
            splits[k as usize] += 1;
        }
        let Some((dev_store, dev_start, dev_label)) = &dev else {
            // No dev set: every round runs, and each tree is on disk once it is made.
            writeln!(model, "{}", tree_json(&tree, &bounds, &bound_start, &store.has_nan)).unwrap();
            model.flush().unwrap();
            if round % 25 == 0 || round == config.max_rounds || empty {
                let seconds = started.elapsed().as_secs_f64();
                let rate = round as f64 / seconds;
                println!("round {round} of {} train loss {train_loss:.4}{} max |leaf| so far {biggest_leaf:.1} {rate:.2} rounds/s eta {:.0}s rss {:.2} GiB", config.max_rounds, if empty { " (no split)" } else { "" }, (config.max_rounds - round) as f64 / rate, resident_gib());
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
    let usage = "block-boost scan DIR | compile DIR | fit FILE | softmax FILE";
    let command = arguments.get(1).expect(usage).as_str();
    let path = PathBuf::from(arguments.get(2).expect(usage));
    match command {
        "scan" => scan(&path),
        "compile" => compile(&path),
        "fit" => fit(&path),
        "softmax" => softmax(&path),
        _ => panic!("{usage}"),
    }
}
