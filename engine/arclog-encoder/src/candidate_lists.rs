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
use crate::generate::{is_number, Generated, Generators, Walker, READS_INPUT, READS_OUTPUT, READS_TABLE, SLOT_DEFAULT, SLOT_NO_VALUE};
use crate::native::{hash_words, FastMap};
use crate::stored::Stored;
use crate::state_features::{graph_numbers, nodes_of, pool, relations, Relation};
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
                _ if example >= vector.scope(shape) => 0.0,
                SLOT_NO_VALUE => f32::NAN,
                SLOT_DEFAULT => 0.0,
                _ => slot.greatest.float() as f32,
            }));
        }
    }
    Written { owner, ids, values, graded, pairs: vector.examples, at_pairs }
}

/// A table's list of named shapes. A shape that reads the output has the train pairs as its scope, and past them it is 0. Under `only_output`, the
/// list holds only those.
fn named_of(owner: serde_json::Value, table: &Stored, grids: &Grids, families: &Generators, examples: usize, only_output: bool) -> Written {
    let mut stable: Vec<(u64, f32)> = Vec::new();
    let mut others: Vec<((u64, f32, f32, f32), Vec<f32>)> = Vec::new();
    for shape in named_shapes(table, &grids.facts, &grids.test_facts) {
        let output = reads_output(&shape.name);
        if only_output && !output {
            continue;
        }
        let scope = if output { grids.train } else { examples };
        let values: Vec<f64> = shape.at[..scope].iter().flatten().copied().collect();
        if values.iter().all(|value| *value == 0.0) {
            continue;
        }
        let text = format!("(named {})", shape.name);
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
            values.push(if slot.state == SLOT_NO_VALUE { f32::NAN } else { slot.greatest.float() as f32 });
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
    /// Each table's task-wide roots at this size.
    Wide(usize),
    /// The lists of the tables that the `parents` of the candidates name, each under its name.
    Parents,
    /// Each candidate's State features, and the numbers of the pair.
    State,
    /// Each table's named shapes, at its place among the task's tables.
    Named,
}

/// A shape over several tables of a state: the least, the mean and the greatest of its mean over the examples,
/// where a table with no value of the shape counts as 0.
fn pooled(owner: String, vectors: &[&TableVector]) -> Written {
    Written { owner: owner.into(), ids: Vec::new(), values: Vec::new(), graded: pool(vectors), pairs: 0, at_pairs: Vec::new() }
}

/// A table's two-table values with another table of the state, each the mean over the examples.
fn edge_of(owner: String, vector: &TableVector) -> Written {
    let mut ids = Vec::with_capacity(vector.shapes.len());
    let mut values = Vec::with_capacity(vector.shapes.len());
    for shape in 0..vector.shapes.len() {
        let (_, mean, _, _) = vector.over_examples(shape, false);
        ids.push(vector.shapes[shape]);
        values.push(mean as f32);
    }
    Written { owner: owner.into(), ids, values, graded: Vec::new(), pairs: 0, at_pairs: Vec::new() }
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
    let nodes = nodes_of(&data["state"]);
    let strings = |names: &serde_json::Value| -> Vec<String> { names.as_array().into_iter().flatten().filter_map(|name| name.as_str().map(str::to_string)).collect() };
    // Per item: its form, and for its gold table and each mutant, the table's place and the names its form reads.
    let mut candidates: Vec<(u64, Vec<(usize, Vec<String>)>)> = Vec::new();
    // Per item and member: what the first version's reading of the program gives of its table.
    let mut query_numbers: Vec<Vec<Vec<(String, f64)>>> = Vec::new();
    let numbers_of = |table: &serde_json::Value| -> Vec<(String, f64)> {
        table["query"].as_object().into_iter().flatten().filter_map(|(name, value)| Some((name.clone(), value.as_f64()?))).collect()
    };
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
        let mut own_candidates = vec![(gold, strings(&item["parents"]))];
        let mut own_numbers = vec![numbers_of(&item["gold"])];
        for mutant in item["mutants"].as_array().ok_or("an item's mutants")? {
            let Some(table) = add_table(&mutant["table"], &mut stored) else {
                whole = false;
                break;
            };
            own_candidates.push((table, strings(&mutant["parents"])));
            own_numbers.push(numbers_of(&mutant["table"]));
            mutants.push(serde_json::json!({"mutant": mutant["mutant"], "edit": mutant["edit"], "extra": mutant["extra"], "table": table, "parents": reads(&mutant["parents"]), "types": mutant["table"]["types"], "task_level": mutant["table"]["task_level"], "assignments": mutant["table"]["assignments"]}));
        }
        if !whole {
            left_out += 1;
            continue;
        }
        candidates.push((item["form"].as_u64().unwrap_or(0), own_candidates));
        query_numbers.push(own_numbers);
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
        ListsOf::Wide(_) | ListsOf::State | ListsOf::Named => Vec::new(),
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
            ListsOf::Named => lists.push(named_of(at.into(), table, &grids, families, examples, only_output)),
            ListsOf::Parents | ListsOf::State => {}
        }
        rows_at.push(serde_json::json!(table.rows[..train].iter().map(|models| models.iter().map(|model| model.len).max().map_or(serde_json::Value::Null, Into::into)).collect::<Vec<serde_json::Value>>()));
    }
    let mut walks = stored.len() as u64;
    if lists_of == ListsOf::Named && !only_output {
        for (at, members) in query_numbers.iter().enumerate() {
            for (member, numbers) in members.iter().enumerate() {
                let mut written: Vec<(u64, f32)> = numbers.iter().filter(|(_, value)| *value != 0.0).map(|(name, value)| {
                    let text = format!("(query {name})");
                    let hash = hash_words(text.bytes().map(u64::from));
                    families.names.add_root(hash, text, 0);
                    (hash as u64, *value as f32)
                }).collect();
                written.sort_unstable_by_key(|entry| entry.0);
                lists.push(Written { owner: format!("{at}/{member}/query").into(), ids: written.iter().map(|entry| entry.0).collect(), values: written.iter().map(|entry| entry.1).collect(), graded: Vec::new(), pairs: 0, at_pairs: Vec::new() });
            }
        }
    }
    if lists_of == ListsOf::State {
        // Each pair of a candidate's table and a table of its state, once.
        let mut pairs: Vec<(usize, usize)> = Vec::new();
        for (form, members) in &candidates {
            for (table, _) in members {
                for node in nodes.iter().filter(|node| node.form < *form) {
                    if let Some(other) = prefix.get(&node.name) {
                        if other != table {
                            pairs.push((*table, *other));
                        }
                    }
                }
            }
        }
        pairs.sort_unstable();
        pairs.dedup();
        let families_of: Vec<Arc<Generated>> = pairs.iter().map(|(t, u)| families.get_two_tables(&stored[*t], &stored[*u])).collect();
        let mut walker_of: FastMap<*const Generated, usize> = FastMap::default();
        let mut two_families: Vec<&Arc<Generated>> = Vec::new();
        for family in &families_of {
            walker_of.entry(Arc::as_ptr(family)).or_insert_with(|| {
                two_families.push(family);
                two_families.len() - 1
            });
        }
        let mut two_walkers: Vec<Walker<'_>> = two_families.iter().map(|family| Walker::new(family)).collect();
        let mut vectors: FastMap<(usize, usize), TableVector> = FastMap::default();
        for ((t, u), family) in pairs.iter().zip(&families_of) {
            let walker = &mut two_walkers[walker_of[&Arc::as_ptr(family)]];
            vectors.insert((*t, *u), two_tables_vector(walker, &stored[*t], &stored[*u], &grids, examples, only_output));
        }
        walks = pairs.len() as u64;
        // A candidate's numbers, and its values pooled by each table's relation to it.
        let mut edges: BTreeMap<(usize, usize), ()> = BTreeMap::new();
        for (at, (form, members)) in candidates.iter().enumerate() {
            for (member, (table, parents)) in members.iter().enumerate() {
                let related = relations(&nodes, *form, parents);
                for relation in Relation::ALL {
                    let others: Vec<&TableVector> = related.iter().filter(|(_, own)| *own == relation).filter_map(|(node, _)| prefix.get(&node.name)).filter(|other| *other != table).filter_map(|other| vectors.get(&(*table, *other))).collect();
                    if !others.is_empty() {
                        lists.push(pooled(format!("{at}/{member}/{}", relation.word()), &others));
                    }
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
                            if other != table {
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
        let pair = pair_vector(&grids, families, d, only_output);
        lists.push(stable_of("pair".into(), &pair));
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

    // The file: its header's length, its header, then the shapes, then each list as places in them
    // and its values, then its graded shapes as places, their least, mean and greatest, and their
    // value at each example.
    let mut dictionary: Vec<u64> = lists.iter().flat_map(|list| list.ids.iter().copied().chain(list.graded.iter().map(|entry| entry.0))).collect();
    dictionary.sort_unstable();
    dictionary.dedup();
    let header = serde_json::json!({
        "task": task_name, "case": header_rest.0, "train": train, "test": test, "last_query": last_query, "budget_cut": header_rest.1,
        "left_out": left_out, "left_at_source": header_rest.2, "items": items, "train_rows": rows_at, "read_names_skipped": skipped, "places": prefix,
        "shapes": dictionary.len(),
        "lists": lists.iter().map(|list| serde_json::json!({"owner": list.owner, "count": list.ids.len(), "graded": list.graded.len(), "pairs": list.pairs})).collect::<Vec<_>>(),
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
        for value in &list.at_pairs {
            bytes.extend_from_slice(&value.to_le_bytes());
        }
    }
    Ok(TaskLists { task: task_name, bytes, walks, seconds, shapes: dictionary.len() as u64, left_out })
}
