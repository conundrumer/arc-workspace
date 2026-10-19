//! The Souffle record of an inputs file, which `scripts/souffle_parity.py
//! lib` writes.

use std::path::Path;

use serde_json::Value;

use super::coverage::{orientation_type, Souffle};
use super::evaluation::{Cell, Rows};
use super::inputs::{emptied_inputs, Element};

/// The Souffle side of an element, as its record gives it.
pub(super) enum Record {
    /// The rows the record gives, and what of the element it covers.
    Rows(Souffle),
    /// The Souffle lib has no form of the element.
    NoSouffleForm,
    /// The kind of the Souffle run's failure.
    Failed(String),
    /// The inputs of the element that its Souffle form does not declare.
    Undeclared(Vec<String>),
    /// No record of the element's present inputs.
    Missing,
    /// A record made from other Souffle sources than the present ones.
    Stale,
    /// The fault that keeps the digest of the present sources from being
    /// computed.
    NoSources(String),
}

/// The record of `element` whose inputs are `inputs`, made from the
/// sources of the digest `sources`: that of its second inputs file where
/// the record of `inputs` gives undeclared inputs and the second file has
/// a record.
pub(super) fn read_record(snapshot: &Path, element: &Element<'_>, inputs: &Value, sources: &Result<String, String>) -> Record {
    let name = element.name();
    let record = record_of(&snapshot.join(format!("{name}.json")), element, inputs, sources);
    let Record::Undeclared(ports) = &record else { return record };
    match record_of(&snapshot.join(format!("{name}.souffle.json")), element, &emptied_inputs(inputs, ports), sources) {
        Record::Missing => record,
        second => second,
    }
}

pub(super) fn record_of(path: &Path, element: &Element<'_>, inputs: &Value, sources: &Result<String, String>) -> Record {
    let Ok(text) = std::fs::read_to_string(path) else { return Record::Missing };
    let Ok(record) = serde_json::from_str::<Value>(&text) else { return Record::Missing };
    if record.get("inputs") != Some(inputs) {
        return Record::Missing;
    }
    match sources {
        Err(fault) => return Record::NoSources(fault.clone()),
        Ok(digest) if record.get("sources").and_then(Value::as_str) != Some(digest.as_str()) => return Record::Stale,
        Ok(_) => {}
    }
    if let Some(ports) = record.get("undeclared").and_then(Value::as_array) {
        return Record::Undeclared(ports.iter().filter_map(Value::as_str).map(str::to_owned).collect());
    }
    if record.get("no_souffle_form").and_then(Value::as_bool) == Some(true) {
        return Record::NoSouffleForm;
    }
    if let Some(failure) = record.get("failure").and_then(Value::as_str) {
        return Record::Failed(failure.to_owned());
    }
    souffle(&record, element, inputs).map_or(Record::Missing, Record::Rows)
}

/// The rows of the record `record` of `element`, made from `inputs`, and
/// what of the element they cover, or `None` where the record is not of
/// that form.
fn souffle(record: &Value, element: &Element<'_>, inputs: &Value) -> Option<Souffle> {
    let rows = |rows: &Value| -> Option<Rows> {
        let row = |row: &Value| row.as_array().into_iter().flatten().cloned().map(Cell::Value).collect();
        Some(rows.as_array()?.iter().map(row).collect())
    };
    let given = record.get("rows")?;
    if let Element::Relation { .. } = element {
        let columns: Vec<&str> = inputs["columns"].as_array()?.iter().filter_map(|c| c[0].as_str()).collect();
        let types = record.get("types")?.as_object()?;
        let mut column_types = Vec::new();
        for (index, column) in columns.iter().enumerate() {
            if let Some(ty) = orientation_type(types.get(*column)?.as_str()?) {
                column_types.push((index, ty));
            }
        }
        let parts = given.as_array()?.iter().map(rows).collect::<Option<Vec<Rows>>>()?;
        return Some(Souffle { parts: parts.into_iter().enumerate().collect(), left_out: Vec::new(), column_types });
    }
    let outputs: Vec<&str> = inputs["outputs"].as_array()?.iter().filter_map(|o| o["port"].as_str()).collect();
    let index = |port: &str| outputs.iter().position(|o| *o == port);
    let mut parts = Vec::new();
    for (port, part) in given.as_object()? {
        parts.push((index(port)?, rows(part)?));
    }
    parts.sort_by_key(|(at, _)| *at);
    let mut left_out = Vec::new();
    for entry in record.get("left_out")?.as_array()? {
        let width = match entry.get("columns") {
            Some(columns) => Some(columns.as_u64()? as usize),
            None => None,
        };
        left_out.push((index(entry["port"].as_str()?)?, width));
    }
    Some(Souffle { parts, left_out, column_types: Vec::new() })
}
