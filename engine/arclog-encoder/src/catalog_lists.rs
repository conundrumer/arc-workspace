//! The catalog's kinds as a table's entries: each kind's shape, with its greatest value at each example
//! of its scope, which is the train pairs for a kind that reads the output, and every example otherwise.

use arclog::registry::Registry;
use arclog::terms::{Constant, Term, TermId};
use arclog::types::ValueType;

use crate::catalog::{orientation, pass, pass_input, Cell, Kind, Record, TableAt, Value};
use crate::catalog_facts::PairFacts;
use crate::catalog_vector::shape_name;
use crate::lookup::{LookupMap, LookupSet};
use crate::gen_constants::{margins_of, number_of};
use crate::stored::Stored;

fn kind_of(ty: &ValueType) -> Kind {
    match ty {
        ValueType::Position => Kind::Position,
        ValueType::Box => Kind::Box,
        ValueType::Offset => Kind::Offset,
        ValueType::Color => Kind::Color,
        ValueType::Nat => Kind::Nat,
        ValueType::Int => Kind::Int,
        ValueType::Ident(_) => Kind::Ident,
        ValueType::Dir => Kind::Dir,
        ValueType::DiagDir => Kind::DiagDir,
        ValueType::Dir8 => Kind::Dir8,
        ValueType::Axis => Kind::Axis,
        ValueType::DiagAxis => Kind::DiagAxis,
        ValueType::Axis4 => Kind::Axis4,
        ValueType::D4 => Kind::D4,
        ValueType::C4 => Kind::C4,
        ValueType::Sym => Kind::Sym,
        ValueType::Sense => Kind::Sense,
        _ => Kind::Other,
    }
}

fn cell_of(bits: u32, ty: &ValueType, kind: Kind) -> Cell {
    match kind {
        Kind::Position | Kind::Box | Kind::Offset => margins_of(bits),
        Kind::Nat | Kind::Int => [number_of(bits) as i32, 0, 0, 0],
        Kind::Dir | Kind::DiagDir | Kind::Dir8 | Kind::Axis | Kind::DiagAxis | Kind::Axis4 | Kind::D4 | Kind::C4 => match Term::decode(TermId::from_encoding(bits), ty) {
            Term::Constant(Constant::Orientation(constant)) => [orientation(Registry::get().constant_name(constant)), 0, 0, 0],
            _ => [bits as i32, 0, 0, 0],
        },
        _ => [bits as i32, 0, 0, 0],
    }
}

/// A record's number, and the column a word gives beside the kind's name.
fn number(value: Value) -> Option<f64> {
    match value {
        Value::Null | Value::Word(_) => None,
        Value::Bool(flag) => Some(f64::from(u8::from(flag))),
        Value::Num(number) => Some(number as f64),
        Value::Share(hits, of) => (of > 0).then(|| f64::from(hits) / f64::from(of)),
    }
}

fn greatest_of(records: &[Record], kinds: &[Kind], per: &mut LookupMap<String, f64>) {
    for record in records {
        let name = shape_name(record, kinds);
        if let Value::Word(word) = record.value {
            let held = per.entry(format!("{name} :{word}")).or_insert(0.0);
            *held = 1.0;
        } else if let Some(value) = number(record.value) {
            let held = per.entry(name).or_insert(f64::NEG_INFINITY);
            *held = held.max(value);
        }
    }
}

/// Whether a kind's shape reads the output: a test input has none, so it has no value there.
pub fn reads_output(name: &str) -> bool {
    name.contains("output") || name.contains("change")
}

/// A named shape of a table: its name, and its value at each example, or None where it has no value.
pub struct NamedShape {
    pub name: String,
    pub at: Vec<Option<f64>>,
}

/// The shapes of a table over its examples: `facts` for each train pair, then `tests` for each test input. Over an example's TableRows, a shape
/// takes the mean of its value where it has one. A shape that reads the output has values at the train pairs alone.
pub fn named_shapes(table: &Stored, facts: &[PairFacts], tests: &[PairFacts], inputs: &[PairFacts]) -> Vec<NamedShape> {
    let kinds: Vec<Kind> = table.types.iter().map(kind_of).collect();
    let pairs = facts.len() + tests.len();
    let mut shapes: LookupMap<String, Vec<Option<f64>>> = LookupMap::new();
    let mut records = Vec::with_capacity(256);
    let mut cells: Vec<Cell> = Vec::new();
    for (pair, fact) in facts.iter().chain(tests).enumerate() {
        let models = table.rows.get(pair).map_or(&[][..], Vec::as_slice);
        let mut sums: LookupMap<String, (f64, usize)> = LookupMap::new();
        for model in models {
            cells.clear();
            for row in model.rows() {
                cells.extend(row.iter().zip(&table.types).zip(&kinds).map(|((bits, ty), kind)| cell_of(*bits, ty, *kind)));
            }
            records.clear();
            pass(&TableAt { kinds: &kinds, keys: &table.keys, rows: model.len, cells: &cells }, fact, &mut records);
            let mut per = LookupMap::new();
            greatest_of(&records, &kinds, &mut per);
            // A kind that reads the output alone also stands for the input, read as its own output.
            records.clear();
            let own = if pair < inputs.len() { &inputs[pair] } else { fact };
            pass(&TableAt { kinds: &kinds, keys: &table.keys, rows: model.len, cells: &cells }, own, &mut records);
            records.retain(|record| record.kind.contains("output") && !record.kind.contains("input") && !record.kind.contains("change"));
            let mut mirrored = LookupMap::new();
            greatest_of(&records, &kinds, &mut mirrored);
            // A mirrored shape replaces the shape of the same name that the input gave. Two mirrored shapes of one name keep the one with the least name before the renaming.
            let mut renamed = LookupSet::new();
            for (name, value) in mirrored.into_sorted_vec() {
                let name = name.replace("output", "input");
                if renamed.insert(name.clone()) {
                    per.insert(name, value);
                }
            }
            records.clear();
            pass_input(&TableAt { kinds: &kinds, keys: &table.keys, rows: model.len, cells: &cells }, own, &mut records);
            greatest_of(&records, &kinds, &mut per);
            for (name, value) in per.into_sorted_vec() {
                let held = sums.entry(name).or_insert((0.0, 0));
                held.0 += value;
                held.1 += 1;
            }
        }
        for (name, (sum, count)) in sums.into_sorted_vec() {
            if pair < facts.len() || !reads_output(&name) {
                shapes.entry(name).or_insert_with(|| vec![None; pairs])[pair] = Some(sum / count as f64);
            }
        }
    }
    shapes.into_sorted_vec().into_iter().map(|(name, at)| NamedShape { name, at }).collect()
}
