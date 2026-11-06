//! What the protocol's Candidate recognition reads of a task's tables: each table's stable roots,
//! taken from its `TableVector`. The statistic itself stands in `model/feature_eval/candidate.py`.
//! The lists hold only the names of shapes and their numbers over examples, so a test input's rows
//! leave nothing behind. A table's stable roots stand with their value, and its other active roots
//! with the least, the mean and the greatest of their value, so a model can read both. A wide run
//! writes in their place each table's task-wide roots, and the numbers of the base parts. A parents
//! run writes the lists of the tables that the candidates' forms read, by name.

use std::collections::BTreeMap;
use std::sync::Arc;

use crate::gen_constants::number_of;
use crate::generate::{is_number, Generated, Generators, Walker, READS_INPUT, READS_OUTPUT, SLOT_NO_VALUE};
use crate::native::{hash_words, FastMap};
use crate::stored::Stored;
use crate::table_vector::{base_vectors, table_vector, task_wide_vector, Grids, TableVector};

/// A list as the file writes it: shapes, and the mean of each one's greatest value over its scope.
struct Written {
    owner: serde_json::Value,
    ids: Vec<u64>,
    values: Vec<f32>,
    /// The shapes active at some example of their scope and not stable: the least, the mean and the
    /// greatest of each one's greatest value, in the order of the shapes. A shape with no value at
    /// any example has NaN for all three, since no value differs from a default.
    graded: Vec<(u64, f32, f32, f32)>,
}

fn stable_of(owner: serde_json::Value, vector: &TableVector) -> Written {
    let mut ids = Vec::new();
    let mut values = Vec::new();
    let mut graded = Vec::new();
    for shape in 0..vector.shapes.len() {
        let (least, mean, most, count) = vector.over_examples(shape, false);
        if vector.stable(shape) {
            ids.push(vector.shapes[shape]);
            values.push(mean as f32);
        } else if count == 0 || least != 0.0 || most != 0.0 {
            graded.push((vector.shapes[shape], least as f32, mean as f32, most as f32));
        }
    }
    Written { owner, ids, values, graded }
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
    Written { owner: "constants".into(), ids: order.iter().map(|at| ids[*at]).collect(), values: order.iter().map(|at| values[*at]).collect(), graded }
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
            values.push(if slot.state == SLOT_NO_VALUE { f32::NAN } else { slot.greatest.float() as f32 });
        }
    }
    Written { owner, ids, values, graded: Vec::new() }
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
    Written { owner: "constant-values".into(), ids: Vec::new(), values: Vec::new(), graded }
}

/// What a run of the lists writes of a task.
#[derive(Clone, Copy, PartialEq)]
pub enum ListsOf {
    /// Each table's lists, at its place among the task's tables, and the base tables'.
    Tables,
    /// Each table's task-wide roots at this size.
    Wide(usize),
    /// The lists of the tables that the `parents` of the candidates name, each under its name.
    Parents,
}

pub struct TaskLists {
    pub task: String,
    pub bytes: Vec<u8>,
    pub walks: u64,
    pub seconds: f64,
    pub shapes: u64,
}

/// One task's lists, from the text of a tables file. `order` gives the train output each train pair
/// reads, and with it only the shapes that read the output have a list, since no other shape reads it.
pub fn lists_task(text: &str, task_dir: &std::path::Path, families: &Generators, order: Option<&[usize]>, d: usize, lists_of: ListsOf) -> Result<TaskLists, String> {
    let data: serde_json::Value = serde_json::from_str(text).map_err(|error| error.to_string())?;
    let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
    let train = data["train"].as_u64().ok_or("a file's train")? as usize;
    let test = data["test"].as_u64().unwrap_or(0) as usize;
    let last_query = data["last_query"].as_str().unwrap_or("").to_string();
    let (_, grids) = Grids::of_file(task_dir, &task_name, order)?;
    let cap = 2000;
    let mut stored: Vec<Stored> = Vec::new();
    let mut content_at: FastMap<u128, usize> = FastMap::default();
    let mut add_table = |value: &serde_json::Value, stored: &mut Vec<Stored>| -> Option<usize> {
        if value["too_large"].as_bool() == Some(true) {
            return None;
        }
        let table = Stored::of_json(value, train, test, cap)?;
        if table.types.len() > 8 {
            return None;
        }
        Some(*content_at.entry(table.content()).or_insert_with(|| {
            stored.push(table);
            stored.len() - 1
        }))
    };
    let mut prefix: BTreeMap<String, usize> = BTreeMap::new();
    let mut read_names: std::collections::BTreeSet<String> = std::collections::BTreeSet::new();
    let mut note_names = |names: &serde_json::Value| {
        read_names.extend(names.as_array().into_iter().flatten().filter_map(|name| name.as_str().map(str::to_string)));
    };
    if let Some(tables) = data["prefix"].as_object() {
        for (name, value) in tables {
            if let Some(at) = add_table(value, &mut stored) {
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
    for item in data["items"].as_array().ok_or("a file's items")? {
        note_names(&item["parents"]);
        for mutant in item["mutants"].as_array().into_iter().flatten() {
            note_names(&mutant["parents"]);
        }
        let Some(gold) = add_table(&item["gold"], &mut stored) else {
            left_out += 1;
            continue;
        };
        let mut mutants = Vec::new();
        let mut whole = true;
        for mutant in item["mutants"].as_array().ok_or("an item's mutants")? {
            let Some(table) = add_table(&mutant["table"], &mut stored) else {
                whole = false;
                break;
            };
            mutants.push(serde_json::json!({"mutant": mutant["mutant"], "edit": mutant["edit"], "extra": mutant["extra"], "table": table, "parents": reads(&mutant["parents"]), "types": mutant["table"]["types"], "task_level": mutant["table"]["task_level"], "assignments": mutant["table"]["assignments"]}));
        }
        if !whole {
            left_out += 1;
            continue;
        }
        items.push(serde_json::json!({"query": item["query"], "form": item["form"], "table": item["table"], "last": item["query"].as_str() == Some(last_query.as_str()), "gold": gold, "parents": reads(&item["parents"]), "types": item["gold"]["types"], "task_level": item["gold"]["task_level"], "assignments": item["gold"]["assignments"], "mutants": mutants}));
    }
    let header_rest = (data["case"].clone(), data["budget_cut"].clone(), data["left_out"].clone());
    // The names a candidate reads and the lists have no table for: one too large, or one no item stores.
    let too_large: Vec<&String> = read_names.iter().filter(|name| !prefix.contains_key(*name) && !data["prefix"][name.as_str()].is_null()).collect();
    let no_table: Vec<&String> = read_names.iter().filter(|name| data["prefix"][name.as_str()].is_null()).collect();
    let skipped = serde_json::json!({"too_large": too_large, "no_table": no_table});
    let named: Vec<(&String, usize)> = read_names.iter().filter_map(|name| prefix.get(name).map(|at| (name, *at))).collect();
    drop(data);

    let mut held: Vec<(String, Arc<Generated>)> = Vec::new();
    let walked: Vec<usize> = match lists_of {
        ListsOf::Tables => (0..stored.len()).collect(),
        ListsOf::Wide(_) => Vec::new(),
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
    let mut lists: Vec<Written> = Vec::new();
    let mut rows_at: Vec<serde_json::Value> = Vec::new();
    for (at, table) in stored.iter().enumerate() {
        match lists_of {
            ListsOf::Wide(size) => lists.push(wide_of(at.into(), table, &grids, families, size, only_output)),
            ListsOf::Tables => {
                let walker = &mut walkers.iter_mut().find(|(key, _)| *key == table.key).expect("a schema's walker").1;
                let vector = table_vector(walker, table, &grids, examples, only_output);
                lists.push(stable_of(at.into(), &vector));
            }
            ListsOf::Parents => {}
        }
        rows_at.push(serde_json::json!(table.rows[..train].iter().map(|models| models.iter().map(|model| model.len).max().map_or(serde_json::Value::Null, Into::into)).collect::<Vec<serde_json::Value>>()));
    }
    let mut walks = stored.len() as u64;
    if lists_of == ListsOf::Parents {
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

    // The file: its header's length, its header, then the shapes, then each list as places in them
    // and its values, then its graded shapes as places and their least, mean and greatest.
    let mut dictionary: Vec<u64> = lists.iter().flat_map(|list| list.ids.iter().copied().chain(list.graded.iter().map(|entry| entry.0))).collect();
    dictionary.sort_unstable();
    dictionary.dedup();
    let header = serde_json::json!({
        "task": task_name, "case": header_rest.0, "train": train, "test": test, "last_query": last_query, "budget_cut": header_rest.1,
        "left_out": left_out, "left_at_source": header_rest.2, "items": items, "train_rows": rows_at, "read_names_skipped": skipped,
        "shapes": dictionary.len(),
        "lists": lists.iter().map(|list| serde_json::json!({"owner": list.owner, "count": list.ids.len(), "graded": list.graded.len()})).collect::<Vec<_>>(),
    }).to_string();
    let total: usize = lists.iter().map(|list| list.ids.len()).sum();
    let mut bytes = Vec::with_capacity(8 + header.len() + dictionary.len() * 8 + total * 8);
    bytes.extend_from_slice(&(header.len() as u64).to_le_bytes());
    bytes.extend_from_slice(header.as_bytes());
    for shape in &dictionary {
        bytes.extend_from_slice(&shape.to_le_bytes());
    }
    for list in &lists {
        // Each list is sorted, so its places come by one walk over the dictionary.
        let mut at = 0usize;
        for shape in &list.ids {
            while dictionary[at] != *shape {
                at += 1;
            }
            bytes.extend_from_slice(&(at as u32).to_le_bytes());
        }
        for value in &list.values {
            bytes.extend_from_slice(&value.to_le_bytes());
        }
        let mut at = 0usize;
        for entry in &list.graded {
            while dictionary[at] != entry.0 {
                at += 1;
            }
            bytes.extend_from_slice(&(at as u32).to_le_bytes());
        }
        for number in [|entry: &(u64, f32, f32, f32)| entry.1, |entry: &(u64, f32, f32, f32)| entry.2, |entry: &(u64, f32, f32, f32)| entry.3] {
            for entry in &list.graded {
                bytes.extend_from_slice(&number(entry).to_le_bytes());
            }
        }
    }
    Ok(TaskLists { task: task_name, bytes, walks, seconds, shapes: dictionary.len() as u64 })
}
