//! The renaming of Idents between the engine's rows and the rows of a
//! record of them, Souffle's rerun or a stored `param` record: the leaves of
//! a row on each side, whether the two sides agree at each place that holds
//! no Ident, and whether one bijection of Idents maps the engine's rows of
//! each relation onto the record's.

use std::collections::{BTreeMap, BTreeSet};

use arclog::hash::StableHashMap;
use arclog::registry::Registry;
use arclog::terms::{Constant, Ident, Term};
use serde_json::Value;

/// One leaf of a row of a record: an integer, or another value by its
/// text, as `scripts/souffle_parity.py rerun --json` writes a row.
#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Debug)]
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

/// One leaf of a row of the engine: a leaf as a record writes it, or an
/// Ident, which stands for the record's number of the same entity under a
/// renaming that [`renaming_exists`] looks for.
#[derive(Clone, PartialEq, Eq, Debug)]
pub(crate) enum EngineLeaf {
    Written(Leaf),
    Ident(Ident),
}

/// One side's rows of the relations compared, for [`renaming_exists`]: each
/// row as its relation's place in the list, its leaves with each Ident's
/// place left empty, and its Idents, each by its number on that side, in
/// the order of their places.
struct IdentRows {
    rows: Vec<(usize, Vec<Option<Leaf>>, Vec<usize>)>,
    idents: usize,
}

impl IdentRows {
    /// The engine's side of `relations`.
    fn engine(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> IdentRows {
        let mut numbers: StableHashMap<Ident, usize> = StableHashMap::default();
        let mut rows = Vec::new();
        for (relation, (_, engine)) in relations.iter().enumerate() {
            for row in engine {
                let mut idents = Vec::new();
                let leaves = row
                    .iter()
                    .map(|leaf| match leaf {
                        EngineLeaf::Written(leaf) => Some(leaf.clone()),
                        EngineLeaf::Ident(ident) => {
                            let next = numbers.len();
                            idents.push(*numbers.entry(*ident).or_insert(next));
                            None
                        }
                    })
                    .collect();
                rows.push((relation, leaves, idents));
            }
        }
        IdentRows { rows, idents: numbers.len() }
    }

    /// The record's side of `relations`: each leaf at the place of an Ident
    /// in the engine's rows of the relation is an Ident, `None` where one
    /// such leaf is no number.
    fn record(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> Option<IdentRows> {
        let mut numbers: BTreeMap<i64, usize> = BTreeMap::new();
        let mut rows = Vec::new();
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
                    let next = numbers.len();
                    idents.push(*numbers.entry(*n).or_insert(next));
                    leaves.push(None);
                }
                rows.push((relation, leaves, idents));
            }
        }
        Some(IdentRows { rows, idents: numbers.len() })
    }

    /// The row sets of the side, each Ident written as its class in
    /// `classes`.
    fn by_classes(&self, classes: &[usize]) -> BTreeSet<(usize, Vec<Option<Leaf>>, Vec<usize>)> {
        self.rows.iter().map(|(relation, leaves, idents)| (*relation, leaves.clone(), idents.iter().map(|&i| classes[i]).collect())).collect()
    }
}

/// The classes of the Idents of both sides, each class a number, refined
/// round by round until no class splits: an Ident's key is its class and
/// the rows that hold it, each row by its relation, its leaves, the classes
/// of its Idents and the places this Ident stands at. Classes are numbered
/// by the order of their keys, so the numbering reads no order of Idents.
fn refine(sides: [&IdentRows; 2], mut classes: [Vec<usize>; 2]) -> [Vec<usize>; 2] {
    loop {
        type Key = (usize, Vec<(usize, Vec<Option<Leaf>>, Vec<usize>, Vec<usize>)>);
        let keys: [Vec<Key>; 2] = [0, 1].map(|s| {
            let mut keys: Vec<Key> = (0..sides[s].idents).map(|i| (classes[s][i], Vec::new())).collect();
            for (relation, leaves, idents) in &sides[s].rows {
                let row_classes: Vec<usize> = idents.iter().map(|&i| classes[s][i]).collect();
                for (place, &ident) in idents.iter().enumerate() {
                    if idents[..place].contains(&ident) {
                        continue;
                    }
                    let places = idents.iter().enumerate().filter(|(_, other)| **other == ident).map(|(p, _)| p).collect();
                    keys[ident].1.push((*relation, leaves.clone(), row_classes.clone(), places));
                }
            }
            keys.iter_mut().for_each(|key| key.1.sort());
            keys
        });
        let numbering: BTreeMap<&Key, usize> = keys.iter().flatten().collect::<BTreeSet<_>>().into_iter().enumerate().map(|(n, key)| (key, n)).collect();
        let before = classes[0].iter().chain(&classes[1]).collect::<BTreeSet<_>>().len();
        classes = [0, 1].map(|s| keys[s].iter().map(|key| numbering[key]).collect());
        if numbering.len() == before {
            return classes;
        }
    }
}

/// Whether one renaming of Idents, a bijection from the engine's Idents to
/// the record's numbers, maps the engine's rows of each relation of
/// `relations` one to one onto the record's. It refines the classes of
/// Idents of both sides, as [`refine`] gives, and, where a class holds more
/// than one Ident of a side, pairs one engine Ident of a smallest such class
/// with each record Ident of that class in turn, and refines again.
pub(crate) fn renaming_exists(relations: &[(&BTreeSet<Vec<Leaf>>, Vec<Vec<EngineLeaf>>)]) -> bool {
    let engine = IdentRows::engine(relations);
    let Some(record) = IdentRows::record(relations) else { return false };
    if engine.idents != record.idents {
        return false;
    }
    let classes = [vec![0; engine.idents], vec![0; record.idents]];
    individualized(&engine, &record, classes)
}

/// Whether a renaming exists that keeps each Ident in its class of
/// `classes`, as [`renaming_exists`] gives.
fn individualized(engine: &IdentRows, record: &IdentRows, classes: [Vec<usize>; 2]) -> bool {
    let classes = refine([engine, record], classes);
    let mut members: BTreeMap<usize, [Vec<usize>; 2]> = BTreeMap::new();
    for (s, side) in classes.iter().enumerate() {
        for (ident, &class) in side.iter().enumerate() {
            members.entry(class).or_default()[s].push(ident);
        }
    }
    if members.values().any(|[ours, theirs]| ours.len() != theirs.len()) {
        return false;
    }
    let Some((_, [ours, theirs])) = members.iter().filter(|(_, [ours, _])| ours.len() > 1).min_by_key(|(class, [ours, _])| (ours.len(), **class)) else {
        return engine.by_classes(&classes[0]) == record.by_classes(&classes[1]);
    };
    let fresh = classes[0].iter().chain(&classes[1]).max().map_or(0, |&max| max + 1);
    theirs.iter().any(|&other| {
        let mut split = classes.clone();
        split[0][ours[0]] = fresh;
        split[1][other] = fresh;
        individualized(engine, record, split)
    })
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
