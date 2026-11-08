//! Reads tables and grids from JSON for the catalog's pass, writes its values, and gives
//! Candidate's stable templates in the form the scoring reads.

use std::collections::{BTreeMap, BTreeSet};

use crate::catalog::*;
use crate::catalog_facts::*;
use crate::lookup::LookupMap;

/// A table's columns, and its rows at each train pair.
pub struct ParsedTable {
    pub kinds: Vec<Kind>,
    pub keys: Vec<bool>,
    /// Per train pair, the cells of its rows, or None where the table gives none.
    pub rows: Vec<Option<(usize, Vec<Cell>)>>,
}

fn cell_of(value: &serde_json::Value, kind: Kind, names: &mut LookupMap<String, i32>) -> Cell {
    match kind {
        Kind::Position | Kind::Box | Kind::Offset => {
            let mut out = [0i32; 4];
            if let Some(items) = value.as_array() {
                for (slot, item) in out.iter_mut().zip(items) {
                    *slot = item.as_i64().unwrap_or(0) as i32;
                }
            }
            out
        }
        Kind::Color | Kind::Nat | Kind::Int => [value.as_i64().unwrap_or(0) as i32, 0, 0, 0],
        Kind::Dir | Kind::DiagDir | Kind::Dir8 | Kind::Axis | Kind::DiagAxis | Kind::Axis4 | Kind::D4 | Kind::C4 => [orientation(value.as_str().unwrap_or("")), 0, 0, 0],
        _ => {
            let text = value.to_string();
            let next = names.len() as i32;
            [*names.entry(text).or_insert(next), 0, 0, 0]
        }
    }
}

pub fn parse_table(table: &serde_json::Value, train: usize) -> ParsedTable {
    let empty = Vec::new();
    let types = table["types"].as_array().unwrap_or(&empty);
    let columns = table["columns"].as_array().unwrap_or(&empty);
    let kinds: Vec<Kind> = types.iter().map(|name| Kind::of(name.as_str().unwrap_or(""))).collect();
    let keys: Vec<bool> = columns.iter().map(|name| name.as_str().unwrap_or("").starts_with("key.")).collect();
    let mut names = LookupMap::new();
    let rows = (0..train).map(|pair| {
        let held = table["rows"].get(format!("train/{pair}"))?.as_array()?;
        let mut cells = Vec::with_capacity(held.len() * kinds.len());
        for row in held {
            for (value, kind) in row.as_array().unwrap_or(&empty).iter().zip(&kinds) {
                cells.push(cell_of(value, *kind, &mut names));
            }
        }
        Some((held.len(), cells))
    }).collect();
    ParsedTable { kinds, keys, rows }
}

pub fn grid_of(value: &serde_json::Value) -> GridFacts {
    let empty = Vec::new();
    let rows = value.as_array().unwrap_or(&empty);
    let h = rows.len();
    let w = rows.first().and_then(|row| row.as_array()).map_or(0, Vec::len);
    let mut color = Vec::with_capacity(h * w);
    for row in rows {
        for cell in row.as_array().unwrap_or(&empty) {
            color.push(cell.as_u64().unwrap_or(0) as u8);
        }
    }
    GridFacts::new(h, w, color)
}

/// The grids of each train pair, with the outputs taken in the given order.
pub fn pairs_of_task(task: &serde_json::Value, order: Option<&[usize]>) -> Vec<PairFacts> {
    let empty = Vec::new();
    let train = task["train"].as_array().unwrap_or(&empty);
    train.iter().enumerate().map(|(at, pair)| {
        let from = order.map_or(at, |order| order[at]);
        PairFacts::new(grid_of(&pair["input"]), grid_of(&train[from]["output"]))
    }).collect()
}

/// A value as the first version writes it.
pub fn value_json(value: Value) -> serde_json::Value {
    match value {
        Value::Null => serde_json::Value::Null,
        Value::Bool(flag) => serde_json::json!(flag),
        Value::Num(number) => serde_json::json!(number),
        Value::Share(hits, of) => {
            let text = format!("{:.3}", f64::from(hits) / f64::from(of.max(1)));
            serde_json::json!(text.parse::<f64>().unwrap_or(0.0))
        }
        Value::Word(word) => serde_json::json!(word),
    }
}

/// How a root reads a value.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Form {
    /// A share is its exact fraction.
    Ratio,
    /// A share says only whether it is 1.
    All,
}

/// The templates that a table holds stably under the active rule, read from its sparse vector:
/// one value at every train pair, and not the default. Under `Form::All` a share counts only
/// where it is 1 at every pair.
pub fn stable_templates(table: &ParsedTable, facts: &[PairFacts], form: Form, spent: &mut (u64, std::time::Duration)) -> BTreeSet<String> {
    let started = std::time::Instant::now();
    let entries = crate::catalog_vector::table_vector(&table.kinds, &table.keys, &table.rows, facts);
    spent.1 += started.elapsed();
    spent.0 += table.rows.iter().filter(|rows| rows.is_some()).count() as u64;
    let one = crate::catalog_vector::Fraction::of(1, 1);
    let mut out = BTreeSet::new();
    for entry in &entries {
        if !entry.stable(facts.len()) || (form == Form::All && entry.ratio && (entry.greatest.max != one || entry.second.min != one)) {
            continue;
        }
        out.insert(entry.name.clone());
    }
    out
}

/// The input as a table of `P` and `Col`.
fn input_table(task: &serde_json::Value) -> ParsedTable {
    let empty = Vec::new();
    let train = task["train"].as_array().unwrap_or(&empty);
    let rows = train.iter().map(|pair| {
        let grid = pair["input"].as_array().unwrap_or(&empty);
        let h = grid.len() as i32;
        let w = grid.first().and_then(|row| row.as_array()).map_or(0, Vec::len) as i32;
        let mut cells = Vec::new();
        for (r, row) in grid.iter().enumerate() {
            for (c, cell) in row.as_array().unwrap_or(&empty).iter().enumerate() {
                cells.push([r as i32, h - 1 - r as i32, c as i32, w - 1 - c as i32]);
                cells.push([cell.as_i64().unwrap_or(0) as i32, 0, 0, 0]);
            }
        }
        Some(((h * w) as usize, cells))
    }).collect();
    ParsedTable { kinds: vec![Kind::Position, Kind::Color], keys: vec![false, false], rows }
}

fn side(item: &serde_json::Value, input: &ParsedTable, facts: &[PairFacts], train: usize, form: Form, spent: &mut (u64, std::time::Duration)) -> serde_json::Value {
    let empty = Vec::new();
    let mut tables: Vec<Vec<String>> = Vec::new();
    let gold = parse_table(&item["gold"], train);
    tables.push(stable_templates(&gold, facts, form, spent).into_iter().collect());
    for mutant in item["mutants"].as_array().unwrap_or(&empty) {
        let parsed = parse_table(&mutant["table"], train);
        tables.push(stable_templates(&parsed, facts, form, spent).into_iter().collect());
    }
    let mut contexts: Vec<Vec<String>> = Vec::new();
    if let Some(reads) = item["reads"].as_object() {
        for table in reads.values() {
            let parsed = parse_table(table, train);
            contexts.push(stable_templates(&parsed, facts, form, spent).into_iter().collect());
        }
    }
    contexts.push(stable_templates(input, facts, form, spent).into_iter().collect());
    serde_json::json!({"tables": tables, "contexts": contexts})
}

/// One task's stable templates, on the true outputs and on the deranged ones.
pub fn dump_task(path: &str, tasks: &std::path::Path, orders: &BTreeMap<String, Option<Vec<usize>>>, form: Form) -> Result<(serde_json::Value, (u64, std::time::Duration), std::time::Duration), String> {
    let data: serde_json::Value = serde_json::from_str(&crate::zio::read_text(path).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let name = data["task"].as_str().ok_or("a file's task")?.to_string();
    let task: serde_json::Value = serde_json::from_str(&crate::zio::read_text(tasks.join(format!("{name}.json"))).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
    let train = task["train"].as_array().map_or(0, Vec::len);
    let started = std::time::Instant::now();
    let facts = pairs_of_task(&task, None);
    let order = orders.get(&name).and_then(Option::as_ref);
    let null_facts = order.map(|order| pairs_of_task(&task, Some(order)));
    let facts_time = started.elapsed();
    let input = input_table(&task);
    let last = data["last_query"].as_str().unwrap_or("").to_string();
    let empty = Vec::new();
    let mut spent = (0u64, std::time::Duration::ZERO);
    let items: Vec<serde_json::Value> = data["items"].as_array().unwrap_or(&empty).iter().map(|item| {
        let query = item["query"].as_str().unwrap_or("");
        let truth = side(item, &input, &facts, train, form, &mut spent);
        let deranged = null_facts.as_ref().map(|facts| side(item, &input, facts, train, form, &mut spent));
        serde_json::json!({"query": query, "last": query == last, "true": truth, "null": deranged})
    }).collect();
    Ok((serde_json::json!({"task": name, "items": items}), spent, facts_time))
}

/// The value of every kind on each requested table, for the check against the first version.
pub fn values_of(requests: &str, tasks: &std::path::Path, out: &mut impl std::io::Write) -> Result<(u64, std::time::Duration), String> {
    let text = crate::zio::read_text(requests).map_err(|error| error.to_string())?;
    let mut spent = (0u64, std::time::Duration::ZERO);
    let mut held: LookupMap<String, Vec<PairFacts>> = LookupMap::new();
    for (at, line) in text.lines().enumerate() {
        let request: serde_json::Value = serde_json::from_str(line).map_err(|error| error.to_string())?;
        let name = request["task"].as_str().ok_or("a request's task")?.to_string();
        if !held.contains_key(&name) {
            let task: serde_json::Value = serde_json::from_str(&crate::zio::read_text(tasks.join(format!("{name}.json"))).map_err(|error| error.to_string())?).map_err(|error| error.to_string())?;
            held.insert(name.clone(), pairs_of_task(&task, None));
        }
        let facts = &held[&name];
        let table = parse_table(&request, facts.len());
        let mut records = Vec::with_capacity(256);
        for (pair, fact) in facts.iter().enumerate() {
            let Some(Some((rows, cells))) = table.rows.get(pair) else { continue };
            records.clear();
            let view = TableAt { kinds: &table.kinds, keys: &table.keys, rows: *rows, cells };
            let started = std::time::Instant::now();
            pass(&view, fact, &mut records);
            spent.1 += started.elapsed();
            spent.0 += 1;
            for record in &records {
                let holes: Vec<u8> = record.holes.iter().copied().filter(|hole| *hole != NONE).collect();
                let line = serde_json::json!({"line": at, "pair": pair, "kind": record.kind, "holes": holes, "value": value_json(record.value)});
                writeln!(out, "{line}").map_err(|error| error.to_string())?;
            }
        }
    }
    Ok(spent)
}
