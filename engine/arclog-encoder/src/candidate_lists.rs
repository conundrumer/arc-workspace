//! What the protocol's Candidate recognition reads of a task's tables: each table's stable roots,
//! taken from its `TableVector`. The statistic itself stands in `model/feature_eval/candidate.py`.
//! The lists hold only the names of shapes and their means over examples, so a test input's rows
//! leave nothing behind.

use std::collections::BTreeMap;
use std::sync::Arc;

use crate::generate::{Generated, Generators, Walker, READS_INPUT, READS_OUTPUT};
use crate::native::{hash_words, FastMap};
use crate::stored::Stored;
use crate::table_vector::{base_vectors, table_vector, Grids, TableVector};

/// A list as the file writes it: shapes, and the mean of each one's greatest value over its scope.
struct Written {
    owner: serde_json::Value,
    ids: Vec<u64>,
    values: Vec<f32>,
}

fn stable_of(owner: serde_json::Value, vector: &TableVector) -> Written {
    let mut ids = Vec::new();
    let mut values = Vec::new();
    for shape in 0..vector.shapes.len() {
        if vector.stable(shape) {
            ids.push(vector.shapes[shape]);
            values.push(vector.over_examples(shape, false).1 as f32);
        }
    }
    Written { owner, ids, values }
}

/// A part's own roots that are stable at every example of its scope.
fn constant_roots(grids: &Grids, families: &Generators) -> Written {
    let parts = crate::gen_constants::constant_parts();
    let mut ids = Vec::new();
    let mut values = Vec::new();
    for (at, part) in parts.iter().enumerate() {
        let scope: Vec<&Arc<crate::native::Table>> = grids.constants.iter().filter_map(|tables| tables[at].as_ref()).collect();
        let Some(first) = scope.first() else { continue };
        let rows = first.len;
        if rows == 0 || !scope.iter().all(|table| table.len == rows) {
            continue;
        }
        let root = if part.columns.is_empty() { "nonempty" } else { "cardinality" };
        let text = format!("({root} {})", part.name);
        let hash = hash_words(text.bytes().map(u64::from));
        let flags = (if part.reads_output { READS_OUTPUT } else { 0 }) | (if part.reads_input { READS_INPUT } else { 0 });
        families.names.add_root(hash, text, flags);
        ids.push(hash as u64);
        values.push(rows as f32);
    }
    let mut order: Vec<usize> = (0..ids.len()).collect();
    order.sort_unstable_by_key(|at| ids[*at]);
    Written { owner: "constants".into(), ids: order.iter().map(|at| ids[*at]).collect(), values: order.iter().map(|at| values[*at]).collect() }
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
pub fn lists_task(text: &str, task_dir: &std::path::Path, families: &Generators, order: Option<&[usize]>, d: usize) -> Result<TaskLists, String> {
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
            mutants.push(serde_json::json!({"mutant": mutant["mutant"], "edit": mutant["edit"], "extra": mutant["extra"], "table": table, "parents": reads(&mutant["parents"]), "types": mutant["table"]["types"], "task_level": mutant["table"]["task_level"]}));
        }
        if !whole {
            left_out += 1;
            continue;
        }
        items.push(serde_json::json!({"query": item["query"], "form": item["form"], "table": item["table"], "last": item["query"].as_str() == Some(last_query.as_str()), "gold": gold, "parents": reads(&item["parents"]), "types": item["gold"]["types"], "task_level": item["gold"]["task_level"], "mutants": mutants}));
    }
    let header_rest = (data["case"].clone(), data["budget_cut"].clone(), data["left_out"].clone());
    drop(data);

    let mut held: Vec<(String, Arc<Generated>)> = Vec::new();
    for table in &stored {
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
        let walker = &mut walkers.iter_mut().find(|(key, _)| *key == table.key).expect("a schema's walker").1;
        let vector = table_vector(walker, table, &grids, examples, only_output);
        lists.push(stable_of(at.into(), &vector));
        rows_at.push(serde_json::json!(table.rows[..train].iter().map(|models| models.iter().map(|model| model.len).max().map_or(serde_json::Value::Null, Into::into)).collect::<Vec<serde_json::Value>>()));
    }
    let mut walks = stored.len() as u64;
    if !only_output {
        let base = base_vectors(&grids, families, d);
        lists.push(stable_of("input".into(), &base.input));
        lists.push(stable_of("ex_output".into(), &base.ex_output));
        lists.push(constant_roots(&grids, families));
        walks += 2;
    }
    let seconds = started.elapsed().as_secs_f64();

    // The file: its header's length, its header, then the shapes, then each list as places in them
    // and its values.
    let mut dictionary: Vec<u64> = lists.iter().flat_map(|list| list.ids.iter().copied()).collect();
    dictionary.sort_unstable();
    dictionary.dedup();
    let header = serde_json::json!({
        "task": task_name, "case": header_rest.0, "train": train, "test": test, "last_query": last_query, "budget_cut": header_rest.1,
        "left_out": left_out, "left_at_source": header_rest.2, "items": items, "train_rows": rows_at,
        "shapes": dictionary.len(),
        "lists": lists.iter().map(|list| serde_json::json!({"owner": list.owner, "count": list.ids.len()})).collect::<Vec<_>>(),
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
    }
    Ok(TaskLists { task: task_name, bytes, walks, seconds, shapes: dictionary.len() as u64 })
}
