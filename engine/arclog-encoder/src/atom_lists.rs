//! A table of the stored form that a rows file holds, read as a `Stored`: `stored_of` reads a table, and `base64` writes the bytes of an array.

use crate::lookup::LookupMap;
use crate::schema::type_of_name;
use crate::stored::{cell_bits, Stored};
use arclog::types::ValueType;

/// The assignments of a table that a read takes.
const ASSIGNMENT_CAP: usize = 16;

pub(crate) fn base64(bytes: &[u8]) -> String {
    const LETTERS: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let held = (u32::from(chunk[0]) << 16) | (u32::from(*chunk.get(1).unwrap_or(&0)) << 8) | u32::from(*chunk.get(2).unwrap_or(&0));
        out.push(LETTERS[(held >> 18) as usize & 63] as char);
        out.push(LETTERS[(held >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 { LETTERS[(held >> 6) as usize & 63] as char } else { '=' });
        out.push(if chunk.len() > 2 { LETTERS[held as usize & 63] as char } else { '=' });
    }
    out
}

/// Why `stored_of` can't read a table that has more columns than the generator takes.
pub const PAST_MAX_COLUMNS: &str = "past MAX_TABLE_COLUMNS columns";

/// A file's table as a table of the candidate lists, with each assignment's each model as a model at its example. `Ok(None)` is no table, and `Err` says why a table can't be read.
pub fn stored_of(table: &serde_json::Value, train: usize, test: usize, orient: &LookupMap<i64, String>) -> Result<Option<Stored>, &'static str> {
    use serde_json::Value;
    let Some(parts) = table.as_array() else { return Ok(None) };
    if parts.len() != 1 {
        return Err("several slots");
    }
    let part = &parts[0];
    let names: Vec<&str> = part["types"].as_array().ok_or("types")?.iter().filter_map(Value::as_str).collect();
    let types: Vec<ValueType> = names.iter().map(|name| type_of_name(name)).collect::<Option<_>>().ok_or("a type")?;
    if types.len() > crate::generate::MAX_TABLE_COLUMNS {
        return Err(PAST_MAX_COLUMNS);
    }
    let examples = train + test;
    let mut rows: Vec<Vec<Vec<Vec<u32>>>> = vec![Vec::new(); examples];
    let mut blocked = vec![false; examples];
    for at in part["at"].as_array().ok_or("at")?.iter().take(ASSIGNMENT_CAP) {
        for entry in at["entries"].as_array().ok_or("entries")? {
            let kind = entry[0].as_i64().ok_or("kind")?;
            let index = entry[1].as_u64().ok_or("index")? as usize;
            let scope: Vec<usize> = match kind {
                0 => (0..examples).collect(),
                1 => vec![index],
                2 => vec![train + index],
                _ => return Err("a kind of example"),
            };
            let count = entry[4].as_u64().unwrap_or(0);
            let cells = entry[5].as_array();
            if entry[3].as_bool() != Some(true) || cells.is_none() {
                for example in scope {
                    if example < examples {
                        blocked[example] = true;
                    }
                }
                continue;
            }
            let mut model: Vec<Vec<u32>> = Vec::with_capacity(count as usize);
            if types.is_empty() {
                model.resize(count as usize, Vec::new());
            } else if let Some(cells) = cells {
                let mut place = 0;
                while place < cells.len() {
                    let mut row = Vec::with_capacity(types.len());
                    for ty in &types {
                        let value = if ty.is_box() {
                            let held = Value::Array(cells.get(place..place + 4).ok_or("a cell")?.to_vec());
                            place += 4;
                            held
                        } else {
                            let held = cells.get(place).ok_or("a cell")?.clone();
                            place += 1;
                            match orient.get(&held.as_i64().unwrap_or(-1)) {
                                Some(name) if !matches!(ty, ValueType::Color | ValueType::Int | ValueType::Nat | ValueType::Example | ValueType::Ident(_)) => Value::String(name.clone()),
                                _ => held,
                            }
                        };
                        row.push(cell_bits(&value, ty).ok_or("a cell")?);
                    }
                    model.push(row);
                }
            }
            for example in scope {
                if example < examples {
                    rows[example].push(model.clone());
                }
            }
        }
    }
    for (example, held) in rows.iter_mut().enumerate() {
        if blocked[example] {
            held.clear();
        }
    }
    Ok(Some(Stored::of_rows(&types, rows)))
}
