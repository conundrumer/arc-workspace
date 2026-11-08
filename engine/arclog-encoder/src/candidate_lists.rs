//! What the protocol's Candidate recognition reads of a task's tables: each table's stable roots,
//! taken from its `TableVector`. The statistic itself stands in `model/feature_eval/candidate.py`.
//! The lists hold only the names of shapes and their numbers over examples, so a test input's rows
//! leave nothing behind. A table's stable roots stand with their value, and its other active roots
//! with the least, the mean and the greatest of their value, so a model can read both. A wide run
//! writes in their place each table's task-wide roots, and the numbers of the base parts. A parents
//! run writes the lists of the tables that the candidates' forms read, by name. A state run writes each
//! candidate's State features.

use std::collections::BTreeMap;
use std::sync::Arc;

use crate::catalog_lists::{named_shapes, reads_output};
use crate::gen_constants::number_of;
use crate::generate::{is_number, Generated, Generators, Walker, READS_INPUT, READS_OUTPUT, READS_TABLE, SlotState};
use crate::native::{hash_words, FastMap};
use crate::program_relations::{add_table_columns, program_facts, table_numbers, ProgramFacts};
use crate::stored::Stored;
use crate::table_stream::{TableIn, TablesIn};
use crate::state_features::{graph_numbers, nodes_of, relations, Relation};
use crate::table_vector::{base_vectors, pair_vector, table_vector, task_wide_vector, two_tables_vector, Grids, TableVector};

/// A list as the file writes it: shapes, and the mean of each one's greatest value over its scope.
struct Written {
    owner: serde_json::Value,
    ids: Vec<u64>,
    values: Vec<f32>,
    /// The shapes active at some example of their scope and not stable: the least, the mean and the
    /// greatest of each one's greatest value, in the order of the shapes. A shape with no value at
    /// any example has NaN for all three, since no value differs from a default.
    graded: Vec<(u64, f32, f32, f32)>,
    /// How many examples each graded shape has a value for, and those values, shape by shape. A
    /// default is 0, as is an example past the shape's scope, and no value is NaN.
    pairs: usize,
    at_pairs: Vec<f32>,
}

fn stable_of(owner: serde_json::Value, vector: &TableVector) -> Written {
    let mut ids = Vec::new();
    let mut values = Vec::new();
    let mut graded = Vec::new();
    let mut at_pairs = Vec::new();
    for shape in 0..vector.shapes.len() {
        let (least, mean, most, count) = vector.over_examples(shape, false);
        if vector.stable(shape) {
            ids.push(vector.shapes[shape]);
            values.push(mean as f32);
        } else if count == 0 || least != 0.0 || most != 0.0 {
            graded.push((vector.shapes[shape], least as f32, mean as f32, most as f32));
            at_pairs.extend(vector.at(shape).iter().enumerate().map(|(example, slot)| match slot.state {
                // An example past the shape's scope is written as 0.
                _ if example >= vector.scope(shape) => 0.0,
                SlotState::NoValue => f32::NAN,
                SlotState::Default => 0.0,
                SlotState::Value => slot.greatest.float() as f32,
            }));
        }
    }
    Written { owner, ids, values, graded, pairs: vector.examples, at_pairs }
}

/// A table's list of named shapes. A shape that reads the output has the train pairs as its scope, and past them it is 0. Under `only_output`, the
/// list holds only those.
fn named_of(owner: serde_json::Value, table: &Stored, grids: &Grids, families: &Generators, examples: usize, only_output: bool) -> Written {
    let shapes = named_shapes(table, &grids.facts, &grids.test_facts, &grids.input_facts);
    written_shapes(owner, shapes, "named", &[], grids, families, examples, only_output)
}

/// A list of shapes given by name, each written as `(head name)`, with `numbers` that hold at every example beside them.
#[allow(clippy::too_many_arguments)]
fn written_shapes(owner: serde_json::Value, shapes: Vec<crate::catalog_lists::NamedShape>, head: &str, numbers: &[(String, f64)], grids: &Grids, families: &Generators, examples: usize, only_output: bool) -> Written {
    let mut stable: Vec<(u64, f32)> = Vec::new();
    let mut others: Vec<((u64, f32, f32, f32), Vec<f32>)> = Vec::new();
    for (name, value) in numbers.iter().filter(|(_, value)| *value != 0.0) {
        let text = format!("({head} {name})");
        let hash = hash_words(text.bytes().map(u64::from));
        families.names.add_root(hash, text, 0);
        stable.push((hash as u64, *value as f32));
    }
    for shape in shapes {
        let output = reads_output(&shape.name);
        if only_output && !output {
            continue;
        }
        let scope = if output { grids.train } else { examples };
        let values: Vec<f64> = shape.at[..scope].iter().flatten().copied().collect();
        if values.iter().all(|value| *value == 0.0) {
            continue;
        }
        let text = format!("({head} {})", shape.name);
        let hash = hash_words(text.bytes().map(u64::from));
        let input = if shape.name.contains("input") || shape.name.contains("change") { READS_INPUT } else { 0 };
        families.names.add_root(hash, text, READS_TABLE | (if output { READS_OUTPUT } else { 0 }) | input);
        if values.len() == scope && values.iter().all(|value| *value == values[0]) {
            stable.push((hash as u64, values[0] as f32));
        } else {
            let least = values.iter().copied().fold(f64::INFINITY, f64::min) as f32;
            let most = values.iter().copied().fold(f64::NEG_INFINITY, f64::max) as f32;
            let mean = (values.iter().sum::<f64>() / values.len() as f64) as f32;
            let at: Vec<f32> = shape.at.iter().enumerate().map(|(example, value)| if example >= scope { 0.0 } else { value.map_or(f32::NAN, |value| value as f32) }).collect();
            others.push(((hash as u64, least, mean, most), at));
        }
    }
    stable.sort_unstable_by_key(|entry| entry.0);
    others.sort_unstable_by_key(|entry| entry.0.0);
    let mut at_pairs = Vec::with_capacity(others.len() * examples);
    let mut graded = Vec::with_capacity(others.len());
    for (entry, at) in others {
        graded.push(entry);
        at_pairs.extend(at);
    }
    let (ids, values) = stable.into_iter().unzip();
    Written { owner, ids, values, graded, pairs: examples, at_pairs }
}

/// A part's own roots: those stable at every example of its scope, with their value, and the others
/// that have rows somewhere in it, with their least, mean and greatest.
fn constant_roots(grids: &Grids, families: &Generators) -> Written {
    let parts = crate::gen_constants::constant_parts();
    let mut ids = Vec::new();
    let mut values = Vec::new();
    let mut graded = Vec::new();
    for (at, part) in parts.iter().enumerate() {
        let scope: Vec<&Arc<crate::native::Table>> = grids.constants.iter().filter_map(|tables| tables[at].as_ref()).collect();
        let Some(first) = scope.first() else { continue };
        let rows = first.len;
        let stable = rows != 0 && scope.iter().all(|table| table.len == rows);
        if !stable && scope.iter().all(|table| table.len == 0) {
            continue;
        }
        let root = if part.columns.is_empty() { "nonempty" } else { "cardinality" };
        let text = format!("({root} {})", part.name);
        let hash = hash_words(text.bytes().map(u64::from));
        let flags = (if part.reads_output { READS_OUTPUT } else { 0 }) | (if part.reads_input { READS_INPUT } else { 0 });
        families.names.add_root(hash, text, flags);
        if stable {
            ids.push(hash as u64);
            values.push(rows as f32);
        } else {
            let lens = || scope.iter().map(|table| table.len as f32);
            graded.push((hash as u64, lens().fold(f32::INFINITY, f32::min), lens().sum::<f32>() / scope.len() as f32, lens().fold(f32::NEG_INFINITY, f32::max)));
        }
    }
    graded.sort_unstable_by_key(|entry: &(u64, f32, f32, f32)| entry.0);
    let mut order: Vec<usize> = (0..ids.len()).collect();
    order.sort_unstable_by_key(|at| ids[*at]);
    Written { owner: "constants".into(), ids: order.iter().map(|at| ids[*at]).collect(), values: order.iter().map(|at| values[*at]).collect(), graded, pairs: 0, at_pairs: Vec::new() }
}

/// A table's task-wide roots, each with its one value. A shape with no value has NaN, since no value
/// differs from a default.
fn wide_of(owner: serde_json::Value, table: &Stored, grids: &Grids, families: &Generators, d: usize, only_output: bool) -> Written {
    let mut ids = Vec::new();
    let mut values = Vec::new();
    if let Some(wide) = task_wide_vector(table, grids, families, d, only_output) {
        for (at, shape) in wide.shapes.iter().enumerate() {
            let slot = &wide.slots[at];
            ids.push(*shape);
            values.push(if slot.state == SlotState::NoValue { f32::NAN } else { slot.greatest.float() as f32 });
        }
    }
    Written { owner, ids, values, graded: Vec::new(), pairs: 0, at_pairs: Vec::new() }
}

/// The number of each base part with one number column that holds one somewhere in its scope: the least,
/// the mean and the greatest over the examples of the column's greatest number, where no rows count as 0.
fn constant_values(grids: &Grids, families: &Generators) -> Written {
    let parts = crate::gen_constants::constant_parts();
    let mut graded = Vec::new();
    for (at, part) in parts.iter().enumerate() {
        if !part.reads_input && !part.reads_output {
            continue;
        }
        let numbers: Vec<usize> = part.columns.iter().enumerate().filter(|(_, (_, ty))| is_number(ty)).map(|(place, _)| place).collect();
        let [place] = numbers.as_slice() else { continue };
        let held: Vec<f32> = grids.constants.iter().filter_map(|tables| tables[at].as_ref()).map(|table| table.rows().map(|row| number_of(row[*place])).max().unwrap_or(0) as f32).collect();
        if held.iter().all(|value| *value == 0.0) {
            continue;
        }
        let name = part.columns[*place].0;
        let text = if part.columns.len() == 1 { format!("(value-set {} {name})", part.name) } else { format!("(value-set (project {} {name}) {name})", part.name) };
        let hash = hash_words(text.bytes().map(u64::from));
        let flags = (if part.reads_output { READS_OUTPUT } else { 0 }) | (if part.reads_input { READS_INPUT } else { 0 });
        families.names.add_root(hash, text, flags);
        let (least, most) = held.iter().fold((f32::INFINITY, f32::NEG_INFINITY), |(least, most), value| (least.min(*value), most.max(*value)));
        graded.push((hash as u64, least, held.iter().sum::<f32>() / held.len() as f32, most));
    }
    graded.sort_unstable_by_key(|entry: &(u64, f32, f32, f32)| entry.0);
    Written { owner: "constant-values".into(), ids: Vec::new(), values: Vec::new(), graded, pairs: 0, at_pairs: Vec::new() }
}

/// What a run of the lists writes of a task.
#[derive(Clone, Copy, PartialEq)]
pub enum ListsOf {
    /// Each table's lists, at its place among the task's tables, and the base tables'.
    Tables,
    /// Each table's lists of the family that its `Generators` give, with no base table's.
    TablesOnly,
    /// Each table's task-wide roots at this size.
    Wide(usize),
    /// The lists of the tables that the `parents` of the candidates name, each under its name.
    Parents,
    /// Each candidate's State features, and the numbers of the pair.
    State,
    /// Each candidate's values against the tables of its state, at each example.
    StateEach,
    /// Each table's named shapes, at its place among the task's tables.
    Named,
}

/// A shape over several tables of a state: the least, the mean and the greatest of its mean over the examples,
/// where a table with no value of the shape counts as 0.
fn pooled(owner: String, pairs: &[&PairValues]) -> Written {
    Written { owner: owner.into(), ids: Vec::new(), values: Vec::new(), graded: pool_values(pairs), pairs: 0, at_pairs: Vec::new() }
}

/// A shape over several tables of a state, at each example: its greatest value over the tables, where a table with no value counts as 0.
fn pooled_each(owner: String, pairs: &[&PairValues], examples: usize) -> Written {
    let mut held: BTreeMap<u64, Vec<f32>> = BTreeMap::new();
    for pair in pairs {
        for (place, shape) in pair.shapes.iter().enumerate() {
            for (example, value) in pair.at[place * examples..(place + 1) * examples].iter().enumerate() {
                if *value != 0.0 {
                    let entry = held.entry(*shape).or_insert_with(|| vec![0.0; examples]);
                    entry[example] = entry[example].max(*value);
                }
            }
        }
    }
    let mut graded = Vec::with_capacity(held.len());
    let mut at_pairs = Vec::with_capacity(held.len() * examples);
    for (shape, values) in held {
        let least = values.iter().copied().fold(f32::INFINITY, f32::min);
        let most = values.iter().copied().fold(f32::NEG_INFINITY, f32::max);
        graded.push((shape, least, values.iter().sum::<f32>() / examples.max(1) as f32, most));
        at_pairs.extend(values);
    }
    Written { owner: owner.into(), ids: Vec::new(), values: Vec::new(), graded, pairs: examples, at_pairs }
}

/// A table's two-table values with another table of the state, each the mean over the examples.
fn edge_of(owner: String, pair: &PairValues) -> Written {
    Written { owner: owner.into(), ids: pair.shapes.clone(), values: pair.means.clone(), graded: Vec::new(), pairs: 0, at_pairs: Vec::new() }
}

/// What the lists read of a table's two-table values with another table of the state, so that memory holds no slot of a pair past its walk.
struct PairValues {
    shapes: Vec<u64>,
    /// Each shape's mean over the examples.
    means: Vec<f32>,
    /// Whether a shape has a value at some example.
    counted: Vec<bool>,
    /// With `each`, each shape's value at each example: 0 where it has none, or past its scope.
    at: Vec<f32>,
}

impl PairValues {
    fn of(vector: &TableVector, each: bool, examples: usize) -> PairValues {
        let count = vector.shapes.len();
        let mut means = Vec::with_capacity(count);
        let mut counted = Vec::with_capacity(count);
        let mut at = Vec::with_capacity(if each { count * examples } else { 0 });
        for shape in 0..count {
            let (_, mean, _, seen) = vector.over_examples(shape, false);
            means.push(mean as f32);
            counted.push(seen != 0);
            if each {
                let scope = vector.scope(shape);
                // A slot with no value is written as 0 here, as an example past the scope and a default are. The other lists in this file write NaN for it.
                at.extend(vector.at(shape).iter().enumerate().map(|(example, slot)| if example < scope && slot.state == SlotState::Value { slot.greatest.float() as f32 } else { 0.0 }));
            }
        }
        PairValues { shapes: vector.shapes.clone(), means, counted, at }
    }
}

/// A shape over several tables of a state: the least, the mean and the greatest of its mean over the examples, where a table with no value of the shape counts as 0.
fn pool_values(pairs: &[&PairValues]) -> Vec<(u64, f32, f32, f32)> {
    let mut held: FastMap<u64, (f32, f32, f32, usize)> = FastMap::default();
    for pair in pairs {
        for ((shape, mean), counted) in pair.shapes.iter().zip(&pair.means).zip(&pair.counted) {
            if *counted {
                let entry = held.entry(*shape).or_insert((f32::INFINITY, 0.0, f32::NEG_INFINITY, 0));
                entry.0 = entry.0.min(*mean);
                entry.1 += *mean;
                entry.2 = entry.2.max(*mean);
                entry.3 += 1;
            }
        }
    }
    let total = pairs.len();
    held.into_sorted_vec().into_iter().map(|(shape, (least, sum, most, seen))| {
        let least = if seen < total { least.min(0.0) } else { least };
        let most = if seen < total { most.max(0.0) } else { most };
        (shape, least, sum / total as f32, most)
    }).collect()
}

/// A task's lists as they are made. Each list leaves memory as a zstd frame, into a file beside the task's lists where one is named, and memory holds only where it stands and
/// the shapes it names.
struct ListSink {
    spool: Spool,
    heads: Vec<ListHead>,
    shapes: FastMap<u64, ()>,
    next_rank: usize,
    written: u64,
    fault: Option<String>,
}

enum Spool {
    Memory(Vec<u8>),
    File(std::io::BufWriter<std::fs::File>, std::path::PathBuf),
}

struct ListHead {
    rank: usize,
    owner: serde_json::Value,
    count: usize,
    graded: usize,
    pairs: usize,
    at_pairs: usize,
    offset: u64,
    /// How many bytes it takes where it stands.
    stored: u64,
}

impl ListSink {
    fn new(spill: Option<std::path::PathBuf>) -> Result<ListSink, String> {
        let spool = match spill {
            Some(path) => Spool::File(std::io::BufWriter::new(std::fs::File::create(&path).map_err(|error| error.to_string())?), path),
            None => Spool::Memory(Vec::new()),
        };
        Ok(ListSink { spool, heads: Vec::new(), shapes: FastMap::default(), next_rank: 0, written: 0, fault: None })
    }

    fn put(&mut self, bytes: &[u8]) {
        match &mut self.spool {
            Spool::Memory(held) => {
                held.extend_from_slice(bytes);
                self.written += bytes.len() as u64;
            }
            Spool::File(writer, _) => match zstd::stream::encode_all(bytes, 1) {
                Ok(packed) => {
                    self.written += packed.len() as u64;
                    if let Err(error) = std::io::Write::write_all(writer, &packed) {
                        self.fault.get_or_insert(error.to_string());
                    }
                }
                Err(error) => {
                    self.fault.get_or_insert(error.to_string());
                }
            },
        }
    }

    /// A list after those before it.
    fn push(&mut self, list: Written) {
        let rank = self.next_rank;
        self.push_at(rank, list);
    }

    /// A list at its rank among the task's lists, wherever it comes in the writing.
    fn push_at(&mut self, rank: usize, list: Written) {
        self.next_rank = self.next_rank.max(rank + 1);
        let offset = self.written;
        let mut raw = Vec::with_capacity(list.ids.len() * 12 + list.graded.len() * 20 + list.at_pairs.len() * 4);
        for shape in list.ids.iter().copied().chain(list.graded.iter().map(|entry| entry.0)) {
            self.shapes.insert(shape, ());
            raw.extend_from_slice(&shape.to_le_bytes());
        }
        for value in &list.values {
            raw.extend_from_slice(&value.to_le_bytes());
        }
        for number in [|entry: &(u64, f32, f32, f32)| entry.1, |entry: &(u64, f32, f32, f32)| entry.2, |entry: &(u64, f32, f32, f32)| entry.3] {
            for entry in &list.graded {
                raw.extend_from_slice(&number(entry).to_le_bytes());
            }
        }
        for value in &list.at_pairs {
            raw.extend_from_slice(&value.to_le_bytes());
        }
        self.put(&raw);
        let stored = self.written - offset;
        self.heads.push(ListHead { rank, owner: list.owner, count: list.ids.len(), graded: list.graded.len(), pairs: list.pairs, at_pairs: list.at_pairs.len(), offset, stored });
    }

    /// Writes the file: its header's length, its header, then the shapes, then each list as places in them and its values, then its graded shapes as places, their least, mean and
    /// greatest, and their value at each example. `header` gives the header from the count of shapes and the lists in order.
    fn finish(self, header: impl FnOnce(usize, &[ListHead]) -> String, target: Option<&std::path::Path>) -> Result<(Vec<u8>, u64), String> {
        let ListSink { spool, mut heads, shapes, fault, .. } = self;
        if let Some(fault) = fault {
            return Err(fault);
        }
        heads.sort_by_key(|head| head.rank);
        let dictionary: Vec<u64> = shapes.into_sorted_keys();
        let header = header(dictionary.len(), &heads);
        let shape_count = dictionary.len() as u64;
        match (spool, target) {
            (Spool::Memory(held), None) => {
                let mut out = Vec::with_capacity(8 + header.len() + dictionary.len() * 8 + held.len());
                write_lists(&header, &dictionary, &heads, &mut |head: &ListHead, into: &mut Vec<u8>| {
                    let start = head.offset as usize;
                    let end = start + into.len();
                    into.copy_from_slice(&held[start..end]);
                    Ok(())
                }, &mut out)?;
                Ok((out, shape_count))
            }
            (Spool::File(writer, path), Some(target)) => {
                let file = writer.into_inner().map_err(|error| error.to_string())?;
                drop(file);
                let mut reader = std::fs::File::open(&path).map_err(|error| error.to_string())?;
                let mut packed = Vec::new();
                let result = crate::zio::write_with(target, |out| {
                    write_lists(&header, &dictionary, &heads, &mut |head: &ListHead, into: &mut Vec<u8>| {
                        std::io::Seek::seek(&mut reader, std::io::SeekFrom::Start(head.offset)).map_err(|error| error.to_string())?;
                        packed.resize(head.stored as usize, 0);
                        std::io::Read::read_exact(&mut reader, &mut packed).map_err(|error| error.to_string())?;
                        let raw = zstd::stream::decode_all(&packed[..]).map_err(|error| error.to_string())?;
                        into.copy_from_slice(&raw);
                        Ok(())
                    }, out)
                });
                let _ = std::fs::remove_file(&path);
                result?;
                Ok((Vec::new(), shape_count))
            }
            _ => Err("a list sink's spool and its target disagree".to_string()),
        }
    }
}

/// The body of a lists file. Each list is sorted, so a shape's place stands after the one before it.
fn write_lists(header: &str, dictionary: &[u64], heads: &[ListHead], read: &mut dyn FnMut(&ListHead, &mut Vec<u8>) -> Result<(), String>, out: &mut dyn std::io::Write) -> Result<(), String> {
    let fail = |error: std::io::Error| error.to_string();
    out.write_all(&(header.len() as u64).to_le_bytes()).map_err(fail)?;
    out.write_all(header.as_bytes()).map_err(fail)?;
    let mut block = Vec::with_capacity(1 << 16);
    for shape in dictionary {
        block.extend_from_slice(&shape.to_le_bytes());
        if block.len() >= 1 << 16 {
            out.write_all(&block).map_err(fail)?;
            block.clear();
        }
    }
    out.write_all(&block).map_err(fail)?;
    let mut raw = Vec::new();
    let mut places = Vec::new();
    for head in heads {
        let size = head.count * 12 + head.graded * 20 + head.at_pairs * 4;
        raw.resize(size, 0);
        read(head, &mut raw)?;
        let (ids, rest) = raw.split_at(head.count * 8);
        let (graded_ids, rest) = rest.split_at(head.graded * 8);
        let (values, rest) = rest.split_at(head.count * 4);
        for (shapes, tail) in [(ids, values), (graded_ids, rest)] {
            places.clear();
            let mut at = 0usize;
            for shape in shapes.chunks_exact(8) {
                let shape = u64::from_le_bytes(shape.try_into().expect("eight bytes"));
                at += dictionary[at..].partition_point(|held| *held < shape);
                places.extend_from_slice(&(at as u32).to_le_bytes());
            }
            out.write_all(&places).map_err(fail)?;
            out.write_all(tail).map_err(fail)?;
        }
    }
    Ok(())
}

pub struct TaskLists {
    pub task: String,
    pub bytes: Vec<u8>,
    pub walks: u64,
    pub seconds: f64,
    pub shapes: u64,
    /// The items with no list, since a table of theirs can't be stored.
    pub left_out: u64,
}

/// One task's lists, from the text of a tables file. `order` gives the train output each train pair
/// reads, and with it only the shapes that read the output have a list, since no other shape reads it.
pub fn lists_task(text: &str, task_dir: &std::path::Path, families: &Generators, order: Option<&[usize]>, d: usize, lists_of: ListsOf) -> Result<TaskLists, String> {
    lists_task_to(text, task_dir, families, order, d, lists_of, None)
}

/// As [`lists_task`]. Where `target` names a file, each list leaves memory as it is made, the file stands at `target` when the task ends, and the result holds no bytes.
pub fn lists_task_to(text: &str, task_dir: &std::path::Path, families: &Generators, order: Option<&[usize]>, d: usize, lists_of: ListsOf, target: Option<&std::path::Path>) -> Result<TaskLists, String> {
    lists_from(&TablesIn::from_json(text)?, task_dir, families, order, d, lists_of, target)
}

/// As [`lists_task_to`], from tables already read, so that a caller reads them once for each kind of list.
pub fn lists_from(input: &TablesIn, task_dir: &std::path::Path, families: &Generators, order: Option<&[usize]>, d: usize, lists_of: ListsOf, target: Option<&std::path::Path>) -> Result<TaskLists, String> {
    let head = &input.head;
    let task_name = head["task"].as_str().ok_or("a file's task")?.to_string();
    let train = head["train"].as_u64().ok_or("a file's train")? as usize;
    let test = head["test"].as_u64().unwrap_or(0) as usize;
    let last_query = head["last_query"].as_str().unwrap_or("").to_string();
    let (_, grids) = Grids::of_file(task_dir, &task_name, order)?;
    let mut stored: Vec<Stored> = Vec::new();
    let mut content_at: FastMap<u128, usize> = FastMap::default();
    let mut place = |table: Stored, stored: &mut Vec<Stored>| -> Option<usize> {
        if table.types.len() > crate::generate::MAX_TABLE_COLUMNS {
            return None;
        }
        Some(*content_at.entry(table.content()).or_insert_with(|| {
            stored.push(table);
            stored.len() - 1
        }))
    };
    let candidate_table = |table: &TableIn| -> Option<Stored> { table.stored() };
    // `prefix` places each table of the state, with all its rows, as a walk reads it as T and as U.
    let mut prefix: BTreeMap<String, usize> = BTreeMap::new();
    let mut read_names: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    let mut note_names = |names: &serde_json::Value| {
        read_names.extend(names.as_array().into_iter().flatten().filter_map(|name| name.as_str().map(str::to_string)));
    };
    {
        for (name, table) in &input.prefix {
            let Some(whole) = table.stored() else { continue };
            if let Some(at) = place(whole, &mut stored) {
                prefix.insert(name.clone(), at);
            }
        }
    }
    let reads = |names: &serde_json::Value| -> Vec<usize> {
        let mut out: Vec<usize> = names.as_array().map_or_else(Vec::new, |names| names.iter().filter_map(|name| prefix.get(name.as_str().unwrap_or("")).copied()).collect());
        out.sort_unstable();
        out.dedup();
        out
    };
    let mut items: Vec<serde_json::Value> = Vec::new();
    let mut left_out = 0u64;
    let nodes = nodes_of(&head["state"]);
    let strings = |names: &serde_json::Value| -> Vec<String> { names.as_array().into_iter().flatten().filter_map(|name| name.as_str().map(str::to_string)).collect() };
    // Per item: its form, and for its gold table and each mutant, the table's place and the names its form reads.
    let mut candidates: Vec<(u64, Vec<(usize, Vec<String>)>)> = Vec::new();
    // Per item and member: what the program relations say of its table.
    let mut query_numbers: Vec<Vec<Vec<(String, f64)>>> = Vec::new();
    let mut check_cache = arclog::check::CheckCache::default();
    let mut facts_of: FastMap<u128, Option<ProgramFacts>> = FastMap::default();
    let mut numbers_of = |text: &serde_json::Value, table: &serde_json::Value, name: &str, form: Option<usize>| -> Vec<(String, f64)> {
        if lists_of != ListsOf::Named {
            return Vec::new();
        }
        let Some(text) = text.as_str() else { return Vec::new() };
        let registry = arclog::registry::Registry::get();
        let facts = facts_of.entry(hash_words(text.bytes().map(u64::from))).or_insert_with(|| arclog::study::StudyProgram::from_sexp_cached(text, registry, &mut check_cache).ok().map(|program| {
            let mut facts = program_facts(program.checked(), registry);
            add_table_columns(&mut facts, program.checked(), registry);
            facts
        }));
        let mut out = facts.as_ref().map_or_else(Vec::new, |facts| table_numbers(facts, name, form));
        // The contract's AssignmentVector, as far as one table's rows at each assignment give it.
        let count = table["assignments"].as_f64().unwrap_or(0.0);
        let distinct = table["distinct_assignments"].as_f64().unwrap_or(count);
        out.push(("assignments count".to_string(), count));
        if count > 0.0 {
            out.push(("assignments distinct".to_string(), distinct / count));
        }
        out.push(("assignments differ".to_string(), f64::from(u8::from(distinct >= 2.0))));
        out.push(("assignments capped".to_string(), f64::from(u8::from(table["capped"].as_bool().unwrap_or(false)))));
        out
    };
    for read in &input.items {
        let item = &read.meta;
        note_names(&item["parents"]);
        for mutant in &read.mutants {
            note_names(&mutant.meta["parents"]);
        }
        let Some(gold) = candidate_table(&read.gold).and_then(|table| place(table, &mut stored)) else {
            left_out += 1;
            continue;
        };
        let mut mutants = Vec::new();
        let mut whole = true;
        let mut own_candidates = vec![(gold, strings(&item["parents"]))];
        let table_name = item["table"].as_str().unwrap_or("");
        let form_at = item["form"].as_u64().map(|form| form as usize);
        let mut own_numbers = vec![numbers_of(&item["text"], &read.gold.meta, table_name, form_at)];
        for read_mutant in &read.mutants {
            let mutant = &read_mutant.meta;
            // An item with a mutant that has no table is left out.
            let Some(table) = candidate_table(&read_mutant.table).and_then(|table| place(table, &mut stored)) else {
                whole = false;
                break;
            };
            own_candidates.push((table, strings(&mutant["parents"])));
            own_numbers.push(numbers_of(&mutant["text"], &read_mutant.table.meta, table_name, form_at));
            mutants.push(serde_json::json!({"mutant": mutant["mutant"], "edit": mutant["edit"], "extra": mutant["extra"], "table": table, "parents": reads(&mutant["parents"]), "types": read_mutant.table.meta["types"], "task_level": read_mutant.table.meta["task_level"], "assignments": read_mutant.table.meta["assignments"]}));
        }
        if !whole {
            left_out += 1;
            continue;
        }
        candidates.push((item["form"].as_u64().unwrap_or(0), own_candidates));
        query_numbers.push(own_numbers);
        items.push(serde_json::json!({"query": item["query"], "form": item["form"], "table": item["table"], "last": item["query"].as_str() == Some(last_query.as_str()), "gold": gold, "parents": reads(&item["parents"]), "types": read.gold.meta["types"], "task_level": read.gold.meta["task_level"], "assignments": read.gold.meta["assignments"], "mutants": mutants}));
    }
    let walked_as_t = stored.len();
    let header_rest = (head["case"].clone(), head["budget_cut"].clone(), head["left_out"].clone());
    // The names a candidate reads and the lists have no table for: one with more columns than a term holds, or one no item stores.
    let wide: Vec<&String> = read_names.iter().filter(|name| !prefix.contains_key(*name) && input.prefix.contains_key(name.as_str())).collect();
    let no_table: Vec<&String> = read_names.iter().filter(|name| !input.prefix.contains_key(name.as_str())).collect();
    let skipped = serde_json::json!({"wide": wide, "no_table": no_table});
    let named: Vec<(&String, usize)> = read_names.iter().filter_map(|name| prefix.get(name).map(|at| (name, *at))).collect();

    let mut held: Vec<(String, Arc<Generated>)> = Vec::new();
    let walked: Vec<usize> = match lists_of {
        ListsOf::Tables | ListsOf::TablesOnly | ListsOf::Wide(_) | ListsOf::State | ListsOf::StateEach | ListsOf::Named => Vec::new(),
        ListsOf::Parents => {
            let mut places: Vec<usize> = named.iter().map(|(_, at)| *at).collect();
            places.sort_unstable();
            places.dedup();
            places
        }
    };
    for table in walked.iter().map(|at| &stored[*at]) {
        if !held.iter().any(|(key, _)| *key == table.key) {
            held.push((table.key.clone(), families.get(table, d)));
        }
    }
    let mut walkers: Vec<(String, Walker<'_>)> = held.iter().map(|(key, family)| (key.clone(), Walker::new(family))).collect();
    let started = std::time::Instant::now();
    let examples = train + test;
    let only_output = order.is_some();
    let mut lists = ListSink::new(target.map(|path| {
        let mut spill = path.as_os_str().to_os_string();
        spill.push(".spill.zst");
        std::path::PathBuf::from(spill)
    }))?;
    let mut rows_at: Vec<serde_json::Value> = Vec::new();
    // The tables of one schema together, so a schema's family and walker leave memory with its last table.
    if matches!(lists_of, ListsOf::Tables | ListsOf::TablesOnly) {
        let mut by_schema: Vec<usize> = (0..walked_as_t).collect();
        by_schema.sort_by(|a, b| stored[*a].key.cmp(&stored[*b].key).then(a.cmp(b)));
        let mut next = 0;
        while next < by_schema.len() {
            let first = &stored[by_schema[next]];
            let family = families.get(first, d);
            let mut walker = Walker::new(&family);
            while next < by_schema.len() && stored[by_schema[next]].key == first.key {
                let at = by_schema[next];
                let vector = table_vector(&mut walker, &stored[at], &grids, examples, only_output);
                lists.push_at(at, stable_of(at.into(), &vector));
                next += 1;
            }
        }
        lists.next_rank = walked_as_t;
    }
    for (at, table) in stored[..walked_as_t].iter().enumerate() {
        match lists_of {
            ListsOf::Wide(size) => lists.push(wide_of(at.into(), table, &grids, families, size, only_output)),
            ListsOf::Named => lists.push(named_of(at.into(), table, &grids, families, examples, only_output)),
            ListsOf::Tables | ListsOf::TablesOnly | ListsOf::Parents | ListsOf::State | ListsOf::StateEach => {}
        }
        rows_at.push(serde_json::json!(table.rows[..train].iter().map(|models| models.iter().map(|model| model.len).max().map_or(serde_json::Value::Null, Into::into)).collect::<Vec<serde_json::Value>>()));
    }
    let mut walks = walked_as_t as u64;
    if lists_of == ListsOf::Named {
        lists.push(named_of("input".into(), &Stored::of_grids(&grids.inputs), &grids, families, examples, only_output));
    }
    if lists_of == ListsOf::Named && !only_output {
        lists.push(named_of("ex_output".into(), &Stored::of_grids(&grids.outputs), &grids, families, examples, only_output));
        for (at, members) in query_numbers.iter().enumerate() {
            for (member, numbers) in members.iter().enumerate() {
                lists.push(written_shapes(format!("{at}/{member}/query").into(), Vec::new(), "query", numbers, &grids, families, examples, false));
            }
        }
    }
    if lists_of == ListsOf::State || lists_of == ListsOf::StateEach {
        // Each pair of a candidate's table and a table of its state, once.
        let mut pairs: Vec<(usize, usize)> = Vec::new();
        for (form, members) in &candidates {
            for (table, _) in members {
                for node in nodes.iter().filter(|node| node.form < *form) {
                    if let Some(other) = prefix.get(&node.name) {
                        pairs.push((*table, *other));
                    }
                }
            }
        }
        pairs.sort_unstable();
        pairs.dedup();
        // The pairs of one family together, so a family and its walker leave memory with its last pair, and a pair keeps only what the lists read.
        let each = lists_of == ListsOf::StateEach;
        let mut by_family: BTreeMap<(&str, &str), Vec<(usize, usize)>> = BTreeMap::new();
        for (t, u) in &pairs {
            by_family.entry((stored[*t].key.as_str(), stored[*u].key.as_str())).or_default().push((*t, *u));
        }
        let mut vectors: FastMap<(usize, usize), PairValues> = FastMap::default();
        for members in by_family.values() {
            let family = families.get_two_tables(&stored[members[0].0], &stored[members[0].1]);
            let mut walker = Walker::new(&family);
            for (t, u) in members {
                let vector = two_tables_vector(&mut walker, &stored[*t], &stored[*u], &grids, examples, only_output);
                vectors.insert((*t, *u), PairValues::of(&vector, each, examples));
            }
        }
        walks = pairs.len() as u64;
        // A candidate's numbers, and its values pooled by each table's relation to it.
        let mut edges: BTreeMap<(usize, usize), ()> = BTreeMap::new();
        for (at, (form, members)) in candidates.iter().enumerate() {
            for (member, (table, parents)) in members.iter().enumerate() {
                let related = relations(&nodes, *form, parents);
                for relation in Relation::ALL {
                    let others: Vec<&PairValues> = related.iter().filter(|(_, own)| *own == relation).filter_map(|(node, _)| prefix.get(&node.name)).filter_map(|other| vectors.get(&(*table, *other))).collect();
                    if !others.is_empty() {
                        let owner = format!("{at}/{member}/{}", relation.word());
                        lists.push(if lists_of == ListsOf::StateEach { pooled_each(owner, &others, examples) } else { pooled(owner, &others) });
                    }
                }
                if lists_of == ListsOf::StateEach {
                    continue;
                }
                let mut numbers = graph_numbers(&nodes, *form, parents);
                numbers.push(("same-table", related.iter().filter(|(node, _)| prefix.get(&node.name) == Some(table)).count() as f32));
                let mut written: Vec<(u64, f32)> = numbers.into_iter().map(|(name, value)| {
                    let text = format!("(state {name})");
                    let hash = hash_words(text.bytes().map(u64::from));
                    families.names.add_root(hash, text, 0);
                    (hash as u64, value)
                }).collect();
                written.sort_unstable_by_key(|entry| entry.0);
                lists.push(Written { owner: format!("{at}/{member}/graph").into(), ids: written.iter().map(|entry| entry.0).collect(), values: written.iter().map(|entry| entry.1).collect(), graded: Vec::new(), pairs: 0, at_pairs: Vec::new() });
                // A later gold query joins two gold tables, so the edges of gold tables are the ones to read.
                if member == 0 {
                    for (node, _) in &related {
                        if let Some(other) = prefix.get(&node.name) {
                            if prefix.get(&node.name) != Some(table) {
                                edges.insert((*table, *other), ());
                            }
                        }
                    }
                }
            }
        }
        for (t, u) in edges.keys() {
            lists.push(edge_of(format!("edge/{t}/{u}"), &vectors[&(*t, *u)]));
        }
        if lists_of == ListsOf::State {
            let pair = pair_vector(&grids, families, d, only_output);
            lists.push(stable_of("pair".into(), &pair));
        }
    } else if lists_of == ListsOf::Parents {
        walks = walked.len() as u64;
        let mut vectors: FastMap<usize, TableVector> = FastMap::default();
        for at in &walked {
            let table = &stored[*at];
            let walker = &mut walkers.iter_mut().find(|(key, _)| *key == table.key).expect("a schema's walker").1;
            vectors.insert(*at, table_vector(walker, table, &grids, examples, only_output));
        }
        for (name, at) in &named {
            lists.push(stable_of(name.as_str().into(), &vectors[at]));
        }
    } else if let (ListsOf::Wide(size), false) = (lists_of, only_output) {
        lists.push(wide_of("input".into(), &Stored::of_grids(&grids.inputs), &grids, families, size, false));
        lists.push(wide_of("ex_output".into(), &Stored::of_grids(&grids.outputs), &grids, families, size, false));
        lists.push(constant_values(&grids, families));
        walks += 2;
    } else if lists_of == ListsOf::Tables && !only_output {
        let base = base_vectors(&grids, families, d);
        lists.push(stable_of("input".into(), &base.input));
        lists.push(stable_of("ex_output".into(), &base.ex_output));
        lists.push(constant_roots(&grids, families));
        walks += 2;
    }
    let seconds = started.elapsed().as_secs_f64();
    let (bytes, shapes) = lists.finish(|shapes, heads| serde_json::json!({
        "task": task_name, "case": header_rest.0, "train": train, "test": test, "last_query": last_query, "budget_cut": header_rest.1,
        "left_out": left_out, "left_at_source": header_rest.2, "items": items, "train_rows": rows_at, "read_names_skipped": skipped, "places": prefix,
        "shapes": shapes,
        "lists": heads.iter().map(|head| serde_json::json!({"owner": head.owner, "count": head.count, "graded": head.graded, "pairs": head.pairs})).collect::<Vec<_>>(),
    }).to_string(), target)?;
    Ok(TaskLists { task: task_name, bytes, walks, seconds, shapes, left_out })
}
