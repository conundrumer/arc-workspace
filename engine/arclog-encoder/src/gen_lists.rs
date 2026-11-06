//! Each table's list of generated shapes, one list per table with nothing from the other tables of
//! its item, at every example where the shape has a value. Nothing here prints what a test input
//! holds, and a list holds only the names of shapes.

use std::collections::BTreeMap;
use std::sync::Arc;

use arclog::types::ValueType;

use crate::catalog_facts::{GridFacts, PairFacts};
use crate::gen_constants::{constant_parts, constant_tables, input_only_tables, number_of};
use crate::generate::{leaves_at_examples, Generated, Generators, Walker, READS_INPUT, READS_OUTPUT};
use crate::native::{hash_words, FastMap, Table};
use crate::tablewalk::{stored_at_examples, ShapeMap, Stored, MAX_EXAMPLES};

/// A shape on a table's list: its name, the hash of its value's multiset at the first example, and
/// its greatest value there.
type Listed = (u64, u64, f32);

/// A table's lists: its stable shapes, and those of them that read no output and that a test input
/// breaks.
#[derive(Default)]
struct Lists {
    stable: Vec<Listed>,
    breaks: Vec<u64>,
}

fn lists_of(map: &ShapeMap, train: usize, total: usize) -> Lists {
    let mut out = Lists::default();
    let train = train.min(MAX_EXAMPLES);
    let total = total.min(MAX_EXAMPLES);
    let train_mask = (1u32 << train) - 1;
    for (name, entry) in map {
        if u32::from(entry.none) & train_mask != 0 || entry.sums[0] == 0 || !entry.sums[..train].iter().all(|sum| *sum == entry.sums[0]) {
            continue;
        }
        out.stable.push((*name as u64, entry.sums[0], entry.head));
        if entry.flags & READS_OUTPUT == 0 && total > train && (train..total).any(|at| entry.none >> at & 1 == 1 || entry.sums[at] != entry.sums[0]) {
            out.breaks.push(*name as u64);
        }
    }
    out.stable.sort_unstable_by_key(|held| held.0);
    out.breaks.sort_unstable();
    out
}

/// The protocol's two readings of a table's stable shapes against the input and the tables it reads:
/// those that not every one of them has as stable, and those whose value none of them has.
fn against(list: &[Listed], bases: &[&[Listed]]) -> (Vec<u64>, Vec<u64>) {
    let (mut contingent, mut fresh) = (Vec::new(), Vec::new());
    for (name, sum, _) in list {
        let mut every = true;
        let mut same = false;
        for base in bases {
            match base.binary_search_by_key(name, |held| held.0) {
                Ok(at) => same |= base[at].1 == *sum,
                Err(_) => every = false,
            }
        }
        if !every {
            contingent.push(*name);
        }
        if !same {
            fresh.push(*name);
        }
    }
    (contingent, fresh)
}

/// A part's own roots that are stable: `nonempty`, `cardinality`, and the value of one number.
fn constant_roots(constants: &[Vec<Option<Arc<Table>>>], families: &Generators) -> Vec<u64> {
    let parts = constant_parts();
    let mut out = Vec::new();
    for (at, part) in parts.iter().enumerate() {
        let scope: Vec<&Arc<Table>> = constants.iter().filter_map(|tables| tables[at].as_ref()).collect();
        if scope.is_empty() {
            continue;
        }
        let flags = (if part.reads_output { READS_OUTPUT } else { 0 }) | (if part.reads_input { READS_INPUT } else { 0 });
        let mut add = |root: &str, name: &str| {
            let text = format!("({root} {name})");
            let hash = hash_words(text.bytes().map(u64::from));
            families.names.add_root(hash, text, flags);
            out.push(hash as u64);
        };
        let rows = scope[0].len;
        if rows > 0 && scope.iter().all(|table| table.len > 0) {
            add("nonempty", &part.name);
        }
        if rows > 0 && scope.iter().all(|table| table.len == rows) {
            add("cardinality", &part.name);
            let is_number = part.columns.len() == 1 && matches!(part.columns[0].1, ValueType::Int | ValueType::Nat);
            if is_number && rows == 1 {
                let value = number_of(scope[0].cells[0]);
                if scope.iter().all(|table| number_of(table.cells[0]) == value) {
                    add("value", &part.name);
                }
            }
        }
    }
    out.sort_unstable();
    out
}

/// A list as the file writes it.
struct Written {
    owner: serde_json::Value,
    kind: &'static str,
    ids: Vec<u64>,
    values: Option<Vec<f32>>,
}

pub struct TaskLists {
    pub task: String,
    pub bytes: Vec<u8>,
    pub walks: u64,
    pub seconds: f64,
    pub shapes: u64,
}

/// One task's lists, from the text of a tables file. `derangement` gives the train output each
/// train pair reads in the null, where the task has one.
pub fn lists_task(text: &str, task_dir: &std::path::Path, families: &Generators, derangement: Option<&[usize]>, d: usize) -> Result<TaskLists, String> {
    let data: serde_json::Value = serde_json::from_str(text).map_err(|error| error.to_string())?;
    let task_name = data["task"].as_str().ok_or("a file's task")?.to_string();
    let train = data["train"].as_u64().ok_or("a file's train")? as usize;
    let test = data["test"].as_u64().unwrap_or(0) as usize;
    let total = train + test;
    let last_query = data["last_query"].as_str().unwrap_or("").to_string();
    let task_path = task_dir.join(format!("{task_name}.json"));
    let task = arclog::task::read_task(&task_path).map_err(|error| format!("the task does not read: {error:?}"))?;
    let task_json: serde_json::Value = serde_json::from_str(&crate::zio::read_text(&task_path)?).map_err(|error| error.to_string())?;
    let grid = |fact: arclog::program::FactRelation, at: usize| {
        let relation = task.fact_rows(fact, Some(arclog::terms::Example::at(at as u16)));
        let mut cells = Vec::new();
        arclog::eval::join::each_row(&relation, &mut |row| cells.extend(row.iter().map(|cell| cell.encoding())));
        Table::new(2, cells)
    };
    let inputs: Vec<Arc<Table>> = (0..total).map(|at| grid(arclog::program::FactRelation::Input, at)).collect();
    let outputs: Vec<Arc<Table>> = (0..train).map(|at| grid(arclog::program::FactRelation::Output, at)).collect();
    let as_table = |tables: &[Arc<Table>]| -> Stored {
        let rows: Vec<Option<Arc<Table>>> = tables.iter().map(|table| {
            let mut cells = Vec::with_capacity(table.cells.len());
            for row in table.rows() {
                cells.push(row[1]);
                cells.push(row[0]);
            }
            Some(Table::new(2, cells))
        }).collect();
        let types = vec![ValueType::Color, ValueType::Position];
        Stored { key: format!("{types:?}"), types, rows }
    };
    let input_table = as_table(&inputs);
    let output_table = as_table(&outputs);

    // The tables and the items that read them. A table's content is walked once; a candidate is a
    // table with the tables its query reads.
    let cap = 2000;
    let mut stored: Vec<Stored> = Vec::new();
    let mut content_at: FastMap<u128, usize> = FastMap::default();
    let mut add_table = |value: &serde_json::Value, stored: &mut Vec<Stored>| -> Option<usize> {
        if value["too_large"].as_bool() == Some(true) {
            return None;
        }
        let table = stored_at_examples(value, train, test, usize::MAX)?;
        if table.types.len() > 8 || table.rows[..train].iter().any(|rows| rows.as_ref().is_some_and(|held| held.len > cap)) {
            return None;
        }
        let rows: Vec<Option<Arc<Table>>> = table.rows.iter().map(|rows| rows.clone().filter(|held| held.len <= cap)).collect();
        let table = Stored { rows, ..table };
        let content = hash_words(table.key.bytes().map(u64::from).chain(table.rows.iter().flat_map(|rows| rows.as_ref().map_or([0, 0], |held| [held.hash as u64, (held.hash >> 64) as u64]))));
        Some(*content_at.entry(content).or_insert_with(|| {
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
    // A candidate: a table and the tables its query reads.
    let mut candidates: Vec<(usize, Vec<usize>)> = Vec::new();
    let mut records: Vec<serde_json::Value> = Vec::new();
    let mut add_candidate = |value: &serde_json::Value, parents: &serde_json::Value, stored: &mut Vec<Stored>| -> Option<usize> {
        let at = add_table(value, stored)?;
        let mut reads: Vec<usize> = parents.as_array().map_or_else(Vec::new, |names| names.iter().filter_map(|name| prefix.get(name.as_str().unwrap_or("")).copied()).collect());
        reads.sort_unstable();
        reads.dedup();
        if let Some(found) = candidates.iter().position(|(table, held)| *table == at && *held == reads) {
            return Some(found);
        }
        let train_rows: Vec<serde_json::Value> = stored[at].rows[..train].iter().map(|rows| rows.as_ref().map_or(serde_json::Value::Null, |held| held.len.into())).collect();
        records.push(serde_json::json!({"types": value["types"], "task_level": value["task_level"], "train_rows": train_rows, "parents": reads.len()}));
        candidates.push((at, reads));
        Some(candidates.len() - 1)
    };
    let mut items: Vec<serde_json::Value> = Vec::new();
    let mut left_out = 0u64;
    for item in data["items"].as_array().ok_or("a file's items")? {
        let Some(gold) = add_candidate(&item["gold"], &item["parents"], &mut stored) else {
            left_out += 1;
            continue;
        };
        let mut mutants = Vec::new();
        let mut whole = true;
        for mutant in item["mutants"].as_array().ok_or("an item's mutants")? {
            let Some(table) = add_candidate(&mutant["table"], &mutant["parents"], &mut stored) else {
                whole = false;
                break;
            };
            mutants.push(serde_json::json!({"mutant": mutant["mutant"], "edit": mutant["edit"], "extra": mutant["extra"], "table": table}));
        }
        if !whole {
            left_out += 1;
            continue;
        }
        items.push(serde_json::json!({"query": item["query"], "form": item["form"], "table": item["table"], "last": item["query"].as_str() == Some(last_query.as_str()), "gold": gold, "mutants": mutants}));
    }
    let case = data["case"].clone();
    let budget_cut = data["budget_cut"].clone();
    let left_at_source = data["left_out"].clone();
    drop(data);

    // A walker per schema.
    let mut held: Vec<(String, Arc<Generated>)> = Vec::new();
    for table in stored.iter().chain([&input_table, &output_table]) {
        if !held.iter().any(|(key, _)| *key == table.key) {
            held.push((table.key.clone(), families.get(table, d)));
        }
    }
    let mut walkers: Vec<(String, Walker<'_>)> = held.iter().map(|(key, family)| (key.clone(), Walker::new(family))).collect();
    let constants_for = |order: Option<&[usize]>| -> Vec<Vec<Option<Arc<Table>>>> {
        crate::gen_parts::clear_views();
        let facts: Vec<PairFacts> = crate::catalog_run::pairs_of_task(&task_json, order);
        let mut out: Vec<Vec<Option<Arc<Table>>>> = facts.iter().map(|fact| constant_tables(fact).into_iter().map(Some).collect()).collect();
        let empty = Vec::new();
        for pair in task_json["test"].as_array().unwrap_or(&empty).iter().take(test) {
            let grid: GridFacts = crate::catalog_run::grid_of(&pair["input"]);
            out.push(input_only_tables(&grid));
        }
        out
    };
    let constants = constants_for(None);
    let moved: Option<(Vec<Arc<Table>>, Vec<Vec<Option<Arc<Table>>>>)> = derangement.map(|order| {
        ((0..train).map(|at| outputs[order[at]].clone()).collect(), constants_for(Some(order)))
    });
    let mut walks = 0u64;
    let mut seconds = 0f64;
    struct Walked {
        stable: Vec<Listed>,
        breaks: Vec<u64>,
        null: Vec<Listed>,
    }
    let mut walk_one = |table: &Stored, examples: usize, with_null: bool| -> Walked {
        let walker = &mut walkers.iter_mut().find(|(key, _)| *key == table.key).expect("a schema's walker").1;
        let started = std::time::Instant::now();
        let leaves = leaves_at_examples(&table.rows[..examples], &inputs, &outputs, &constants);
        let found = lists_of(&walker.walk_examples(&leaves, train.min(examples), None, false), train, examples);
        walks += 1;
        let mut null = Vec::new();
        if with_null {
            if let Some((outputs_moved, constants_moved)) = &moved {
                let leaves = leaves_at_examples(&table.rows[..examples], &inputs, outputs_moved, constants_moved);
                null = lists_of(&walker.walk_examples(&leaves, train.min(examples), None, true), train, examples).stable;
                walks += 1;
            }
        }
        seconds += started.elapsed().as_secs_f64();
        Walked { stable: found.stable, breaks: found.breaks, null }
    };
    let input_walk = walk_one(&input_table, total, true);
    let output_walk = walk_one(&output_table, train, false);
    let walked: Vec<Walked> = stored.iter().map(|table| walk_one(table, total, true)).collect();
    let mut lists: Vec<Written> = Vec::new();
    let ids = |list: &[Listed]| -> Vec<u64> { list.iter().map(|held| held.0).collect() };
    lists.push(Written { owner: "input".into(), kind: "stable", ids: ids(&input_walk.stable), values: Some(input_walk.stable.iter().map(|held| held.2).collect()) });
    lists.push(Written { owner: "input".into(), kind: "breaks", ids: input_walk.breaks.clone(), values: None });
    lists.push(Written { owner: "output".into(), kind: "stable", ids: ids(&output_walk.stable), values: Some(output_walk.stable.iter().map(|held| held.2).collect()) });
    lists.push(Written { owner: "constants".into(), kind: "stable", ids: constant_roots(&constants, families), values: None });
    for (at, (table, reads)) in candidates.iter().enumerate() {
        let own = &walked[*table];
        let owner: serde_json::Value = at.into();
        lists.push(Written { owner: owner.clone(), kind: "stable", ids: ids(&own.stable), values: Some(own.stable.iter().map(|held| held.2).collect()) });
        lists.push(Written { owner: owner.clone(), kind: "breaks", ids: own.breaks.clone(), values: None });
        let bases: Vec<&[Listed]> = std::iter::once(input_walk.stable.as_slice()).chain(reads.iter().map(|read| walked[*read].stable.as_slice())).collect();
        let (contingent, fresh) = against(&own.stable, &bases);
        lists.push(Written { owner: owner.clone(), kind: "contingent", ids: contingent, values: None });
        lists.push(Written { owner: owner.clone(), kind: "fresh", ids: fresh, values: None });
        lists.push(Written { owner: owner.clone(), kind: "null", ids: ids(&own.null), values: Some(own.null.iter().map(|held| held.2).collect()) });
        let bases: Vec<&[Listed]> = std::iter::once(input_walk.null.as_slice()).chain(reads.iter().map(|read| walked[*read].null.as_slice())).collect();
        let (contingent, fresh) = against(&own.null, &bases);
        lists.push(Written { owner: owner.clone(), kind: "null_contingent", ids: contingent, values: None });
        lists.push(Written { owner, kind: "null_fresh", ids: fresh, values: None });
    }

    // The file: its header's length, its header, then the shapes and each list as places in them.
    let mut dictionary: Vec<u64> = lists.iter().flat_map(|list| list.ids.iter().copied()).collect();
    dictionary.sort_unstable();
    dictionary.dedup();
    let header = serde_json::json!({
        "task": task_name, "case": case, "train": train, "test": test, "last_query": last_query, "budget_cut": budget_cut,
        "left_out": left_out, "left_at_source": left_at_source, "items": items, "tables": records,
        "shapes": dictionary.len(),
        "lists": lists.iter().map(|list| serde_json::json!({"owner": list.owner, "kind": list.kind, "count": list.ids.len(), "values": list.values.is_some()})).collect::<Vec<_>>(),
    }).to_string();
    let total_listed: usize = lists.iter().map(|list| list.ids.len()).sum();
    let mut bytes = Vec::with_capacity(8 + header.len() + dictionary.len() * 8 + total_listed * 8);
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
        if let Some(values) = &list.values {
            for value in values {
                bytes.extend_from_slice(&value.to_le_bytes());
            }
        }
    }
    Ok(TaskLists { task: task_name, bytes, walks, seconds, shapes: dictionary.len() as u64 })
}
