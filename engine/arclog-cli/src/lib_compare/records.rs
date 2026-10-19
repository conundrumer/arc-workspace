//! The Souffle record of an inputs file, which `scripts/souffle_parity.py
//! lib` writes.

use std::path::Path;

use serde_json::Value;

use super::evaluation::{Cell, Rows};
use super::inputs::emptied_inputs;

/// The Souffle side of an element, as its record gives it.
pub(super) enum Record {
    /// The rows of each mode, or of each output, each as JSON text.
    Rows(Vec<Rows>),
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
pub(super) fn read_record(snapshot: &Path, element: &str, inputs: &Value, sources: &Result<String, String>) -> Record {
    let record = record_of(&snapshot.join(format!("{element}.json")), inputs, sources);
    let Record::Undeclared(ports) = &record else { return record };
    match record_of(&snapshot.join(format!("{element}.souffle.json")), &emptied_inputs(inputs, ports), sources) {
        Record::Missing => record,
        second => second,
    }
}

pub(super) fn record_of(path: &Path, inputs: &Value, sources: &Result<String, String>) -> Record {
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
    match record.get("rows").and_then(Value::as_array) {
        Some(parts) => {
            let row = |row: &Value| row.as_array().into_iter().flatten().cloned().map(Cell::Value).collect();
            Record::Rows(parts.iter().map(|rows| rows.as_array().into_iter().flatten().map(row).collect()).collect())
        }
        None => Record::Missing,
    }
}
