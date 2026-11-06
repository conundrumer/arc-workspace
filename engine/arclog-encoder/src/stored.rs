//! A table as the generator reads it: its column types and its rows at each example, with the words
//! that a shape's name and a value's hash are written from.

use std::sync::Arc;

use arclog::registry::Registry;
use arclog::types::ValueType;

use crate::native::{hash_words, Table};

pub fn mix_word(word: u64) -> u64 {
    let mut x = word;
    x ^= x >> 33;
    x = x.wrapping_mul(0xff51_afd7_ed55_8ccd);
    x ^= x >> 33;
    x = x.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    x ^ (x >> 33)
}

enum Symbol {
    /// A column of the table, and which reading of it: `T0`, or `T0_2`.
    Hole { column: u16, reading: u16 },
    Fixed,
}

fn symbol_of(name: &str) -> Symbol {
    if let Some(rest) = name.strip_prefix('T') {
        let (base, reading) = rest.split_once('_').unwrap_or((rest, "1"));
        if let (Ok(column), Ok(reading)) = (base.parse::<u16>(), reading.parse::<u16>()) {
            return Symbol::Hole { column, reading };
        }
    }
    Symbol::Fixed
}

/// A term's text as a shape: the table `table` as `T`, and each of its columns as a hole typed by
/// the column's value type, numbered by first appearance.
pub fn shape_text(text: &str, table: &str, types: &[ValueType]) -> String {
    let mut out = String::with_capacity(text.len());
    let mut numbers: Vec<u16> = Vec::new();
    let mut token = String::new();
    let mut flush = |token: &mut String, out: &mut String| {
        if token.is_empty() {
            return;
        }
        if token == table {
            out.push('T');
        } else if token.starts_with("T*:") {
            out.push_str("T*");
        } else if let Symbol::Hole { column, reading } = symbol_of(token) {
            let number = match numbers.iter().position(|held| *held == column) {
                Some(at) => at + 1,
                None => {
                    numbers.push(column);
                    numbers.len()
                }
            };
            let ty = types.get(usize::from(column)).map_or_else(String::new, |ty| format!("{:?}", ty.without_source()));
            out.push_str(&format!("?{number}:{ty}"));
            if reading > 1 {
                out.push_str(&format!("#{reading}"));
            }
        } else {
            out.push_str(token);
        }
        token.clear();
    };
    for ch in text.chars() {
        if ch == ' ' || ch == '(' || ch == ')' {
            flush(&mut token, &mut out);
            out.push(ch);
        } else {
            token.push(ch);
        }
    }
    flush(&mut token, &mut out);
    out
}

/// A table at one assignment: its column types, with its columns ordered by type, and at each
/// example of the task each of its TableRows. An example with none has no value there, since the
/// table is undefined or a bound stopped it.
#[derive(Clone)]
pub struct Stored {
    pub key: String,
    pub types: Vec<ValueType>,
    pub rows: Vec<Vec<Arc<Table>>>,
}

/// The name of a family: each column's type, and which Ident columns share a source. A source's own
/// value does not enter, so tables of one form share a family.
pub fn schema_key(types: &[ValueType]) -> String {
    let mut out = String::new();
    for (at, ty) in types.iter().enumerate() {
        out.push_str(&format!("{:?}", ty.without_source()));
        if matches!(ty, ValueType::Ident(_)) && *ty != ValueType::OPEN_IDENT {
            let first = types.iter().position(|other| other == ty).unwrap_or(at);
            out.push_str(&format!("@{first}"));
        }
        out.push(',');
    }
    out
}

/// The order of a table's columns: by type, so a shape's text does not read a program's order.
pub fn column_order(types: &[ValueType]) -> Vec<usize> {
    let mut order: Vec<usize> = (0..types.len()).collect();
    order.sort_by_key(|at| format!("{:?}", types[*at].without_source()));
    order
}

impl Stored {
    /// A hash of the table's types and rows, as `TableHash` covers them, with equal TableRows as one.
    pub fn content(&self) -> u128 {
        let mut words: Vec<u64> = self.key.bytes().map(u64::from).collect();
        for tables in &self.rows {
            let mut hashes: Vec<u128> = tables.iter().map(|table| table.hash).collect();
            hashes.sort_unstable();
            hashes.dedup();
            words.push(hashes.len() as u64);
            words.extend(hashes.iter().flat_map(|hash| [*hash as u64, (*hash >> 64) as u64]));
        }
        hash_words(words)
    }

    /// The table of `rows`, where `rows` writes each row in the order of `types`: at each example,
    /// each TableRows, and with a table that the task reads once, one list that stands at each.
    pub fn of_rows(types: &[ValueType], rows: Vec<Vec<Vec<Vec<u32>>>>) -> Stored {
        let order = column_order(types);
        let sorted: Vec<ValueType> = order.iter().map(|at| types[*at].clone()).collect();
        let tables = rows.into_iter().map(|models| {
            let mut held: Vec<Arc<Table>> = models.into_iter().map(|model| {
                if order.is_empty() {
                    return Table::unit(!model.is_empty());
                }
                let mut cells = Vec::with_capacity(model.len() * order.len());
                for row in &model {
                    cells.extend(order.iter().map(|at| row[*at]));
                }
                Table::distinct(order.len(), cells)
            }).collect();
            held.sort_by_key(|table| table.hash);
            held.dedup_by_key(|table| table.hash);
            held
        }).collect();
        Stored { key: schema_key(&sorted), types: sorted, rows: tables }
    }

    /// The table of a tables file's `value`: `rows` holds one TableRows per example under
    /// `train/<i>` and `test/<i>`, or under `task` for a table that the task reads once, and
    /// `models` holds several under the same keys. An example with more than `cap` rows in a
    /// TableRows has no value there.
    pub fn of_json(value: &serde_json::Value, train: usize, test: usize, cap: usize) -> Option<Stored> {
        let names = value["types"].as_array()?;
        let types: Vec<ValueType> = names.iter().map(|name| crate::schema::type_of_name(name.as_str()?)).collect::<Option<_>>()?;
        let read_one = |held: &serde_json::Value| -> Option<Option<Vec<Vec<u32>>>> {
            let list = held.as_array()?;
            if list.len() > cap {
                return Some(None);
            }
            let mut rows = Vec::with_capacity(list.len());
            for row in list {
                let row = row.as_array()?;
                let cells: Option<Vec<u32>> = row.iter().zip(&types).map(|(cell, ty)| cell_bits(cell, ty)).collect();
                rows.push(cells?);
            }
            Some(Some(rows))
        };
        let read_at = |key: &str| -> Option<Vec<Vec<Vec<u32>>>> {
            if let Some(models) = value["models"].get(key).and_then(serde_json::Value::as_array) {
                let mut out = Vec::with_capacity(models.len());
                for model in models {
                    match read_one(model) {
                        Some(Some(rows)) => out.push(rows),
                        Some(None) => return Some(Vec::new()),
                        None => return None,
                    }
                }
                return Some(out);
            }
            match value["rows"].get(key) {
                None | Some(serde_json::Value::Null) => Some(Vec::new()),
                Some(held) => match read_one(held) {
                    Some(Some(rows)) => Some(vec![rows]),
                    Some(None) => Some(Vec::new()),
                    None => None,
                },
            }
        };
        let mut rows = Vec::with_capacity(train + test);
        if value["rows"].get("task").is_some() || value["models"].get("task").is_some() {
            let once = read_at("task")?;
            rows.resize(train + test, once);
        } else {
            for pair in 0..train {
                rows.push(read_at(&format!("train/{pair}"))?);
            }
            for pair in 0..test {
                rows.push(read_at(&format!("test/{pair}"))?);
            }
        }
        Some(Stored::of_rows(&types, rows))
    }

    /// The rows of a grid's table as a table of `Col` and `P`, whose columns stand in type order.
    pub fn of_grids(tables: &[Arc<Table>]) -> Stored {
        let rows = tables.iter().map(|table| {
            let mut cells = Vec::with_capacity(table.cells.len());
            for row in table.rows() {
                cells.push(row[1]);
                cells.push(row[0]);
            }
            vec![Table::new(2, cells)]
        }).collect();
        let types = vec![ValueType::Color, ValueType::Position];
        Stored { key: schema_key(&types), types, rows }
    }
}

pub fn cell_bits(value: &serde_json::Value, ty: &ValueType) -> Option<u32> {
    use arclog::terms::{Color, Constant, Margins, Term, TermId};
    let term = match ty {
        ty if ty.is_box() => {
            let cells = value.as_array()?;
            let margin = |at: usize| cells.get(at).and_then(serde_json::Value::as_i64).map(|margin| margin as i32);
            Term::Box(Margins { top: margin(0)?, bottom: margin(1)?, left: margin(2)?, right: margin(3)? })
        }
        ValueType::Color => Term::Constant(Constant::Color(Color::from_digit(value.as_u64()? as u8)?)),
        ValueType::Int | ValueType::Nat => return Some(Term::encode_number(value.as_i64()? as i32).encoding()),
        ValueType::Ident(_) => {
            let bits = match value {
                serde_json::Value::String(text) => hash_words(text.bytes().map(u64::from)) as u32,
                other => other.as_i64()? as u32,
            };
            return Some(bits);
        }
        _ => Term::Constant(Constant::Orientation(Registry::get().orientation_constant(value.as_str()?)?)),
    };
    term.encode().ok().map(TermId::encoding)
}
