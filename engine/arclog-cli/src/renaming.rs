//! The renaming of Idents between the engine's rows and the rows of a
//! record of them, Souffle's rerun or a stored `param` record: the leaves of
//! a row on each side, whether the two sides agree at each place that holds
//! no Ident, and whether one bijection of Idents maps the engine's rows of
//! each relation onto the record's, the search for which is in
//! [`arclog::eval::rigid::renaming`].

use std::collections::BTreeSet;

use arclog::eval::rigid::renaming::{renaming_between, IdentRows, IdentRowsBuilder};
use arclog::registry::Registry;
use arclog::terms::{Constant, Ident, Term};
use serde::{Deserialize, Deserializer};
use serde_json::Value;

/// One leaf of a row of a record: an integer, or another value by its
/// text, as `scripts/souffle_parity.py rerun --json` writes a row.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
pub(crate) enum Leaf {
    Number(i64),
    Other(Box<str>),
}

impl Leaf {
    /// The leaf that `json` gives, `None` for a JSON value that is no
    /// number and no string.
    pub(crate) fn of(json: &Value) -> Option<Leaf> {
        match json {
            Value::Number(n) => Some(n.as_i64().map_or_else(|| Leaf::Other(n.to_string().into()), Leaf::Number)),
            Value::String(s) => Some(Leaf::Other(s.as_str().into())),
            _ => None,
        }
    }
}

impl<'de> Deserialize<'de> for Leaf {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Leaf, D::Error> {
        let json = Value::deserialize(deserializer)?;
        Leaf::of(&json).ok_or_else(|| serde::de::Error::custom("a leaf is no number and no string"))
    }
}

/// One leaf of a row of the engine: a leaf as a record writes it, or an
/// Ident, which stands for the record's number of the same entity under a
/// renaming that [`renaming_exists`] looks for.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub(crate) enum EngineLeaf {
    Written(Leaf),
    Ident(Ident),
}

/// The engine's side of `relations`, for [`renaming_exists`]: each row with
/// its Idents left out of its leaves, and its Idents.
fn engine_rows(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> IdentRows<Leaf> {
    let mut builder: IdentRowsBuilder<Leaf, Ident> = IdentRowsBuilder::default();
    for (relation, (_, engine)) in relations.iter().enumerate() {
        for row in engine {
            let leaves = row
                .iter()
                .map(|leaf| match leaf {
                    EngineLeaf::Written(leaf) => Some(leaf.clone()),
                    EngineLeaf::Ident(_) => None,
                })
                .collect();
            let idents = row.iter().filter_map(|leaf| match leaf {
                EngineLeaf::Ident(ident) => Some(*ident),
                EngineLeaf::Written(_) => None,
            });
            builder.push(relation, leaves, idents);
        }
    }
    builder.finish()
}

/// The record's side of `relations`, for [`renaming_exists`]: each leaf at
/// the place of an Ident in the engine's rows of the relation is an Ident,
/// `None` where one such leaf is no number.
fn record_rows(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> Option<IdentRows<Leaf>> {
    let mut builder: IdentRowsBuilder<Leaf, i64> = IdentRowsBuilder::default();
    for (relation, (record, engine)) in relations.iter().enumerate() {
        let places: Vec<bool> = engine.first().map_or_else(Vec::new, |row| row.iter().map(|leaf| matches!(leaf, EngineLeaf::Ident(_))).collect());
        for row in record.iter() {
            let mut idents = Vec::new();
            let mut leaves = Vec::new();
            for (leaf, &is_ident) in row.iter().zip(&places) {
                if !is_ident {
                    leaves.push(Some(leaf.clone()));
                    continue;
                }
                let Leaf::Number(n) = leaf else { return None };
                idents.push(*n);
                leaves.push(None);
            }
            builder.push(relation, leaves, idents);
        }
    }
    Some(builder.finish())
}

/// Whether one renaming of Idents, a bijection from the engine's Idents to
/// the record's numbers, maps the engine's rows of each relation of
/// `relations` one to one onto the record's, as
/// [`arclog::eval::rigid::renaming::renaming_between`] gives.
pub(crate) fn renaming_exists(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> bool {
    let Some(record) = record_rows(relations) else { return false };
    renaming_between(&engine_rows(relations), &record)
}

/// The leaves of `term` as a record writes them: a number, a color's digit,
/// an example's index and a Box's margins as numbers, an orientation
/// constant as `orientation` gives the leaf of its name, an Ident as itself,
/// and Unit as no leaf.
pub(crate) fn term_leaves(term: Term, registry: &Registry, orientation: &dyn Fn(&str) -> Result<Leaf, String>) -> Result<Vec<EngineLeaf>, String> {
    let number = |n: i64| EngineLeaf::Written(Leaf::Number(n));
    Ok(match term {
        Term::Number(n) => vec![number(n.0.into())],
        Term::Box(m) => [m.top, m.bottom, m.left, m.right].into_iter().map(|n| number(n.into())).collect(),
        Term::Ident(ident) => vec![EngineLeaf::Ident(ident)],
        Term::Constant(Constant::Color(color)) => vec![number(color.digit().into())],
        Term::Constant(Constant::Example(example)) => vec![number(example.index().into())],
        Term::Constant(Constant::Unit) => vec![],
        Term::Constant(Constant::Orientation(constant)) => vec![EngineLeaf::Written(orientation(registry.constant_name(constant))?)],
    })
}

/// Whether `engine` and `record` hold rows of equal leaves at each place
/// that holds no Ident in the engine's row, each row once.
pub(crate) fn same_without_idents(engine: &[Vec<EngineLeaf>], record: &BTreeSet<Vec<Leaf>>) -> bool {
    let masked = |row: &[EngineLeaf]| row.iter().map(|leaf| match leaf {
        EngineLeaf::Written(leaf) => Some(leaf.clone()),
        EngineLeaf::Ident(_) => None,
    }).collect::<Vec<_>>();
    let mut engine_masked: Vec<Vec<Option<Leaf>>> = engine.iter().map(|row| masked(row)).collect();
    engine_masked.sort();
    let Some(first) = engine.first() else { return record.is_empty() };
    if record.iter().any(|row| row.len() != first.len()) {
        return false;
    }
    let mut record_masked: Vec<Vec<Option<Leaf>>> = record
        .iter()
        .map(|row| row.iter().zip(first).map(|(leaf, at)| matches!(at, EngineLeaf::Written(_)).then(|| leaf.clone())).collect())
        .collect();
    record_masked.sort();
    engine_masked == record_masked
}
