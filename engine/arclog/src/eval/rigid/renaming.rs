//! The search for one renaming of Idents between two sides' rows of
//! several relations: whether one bijection of the Idents of one side onto
//! those of the other maps the rows of each relation of one side onto the
//! other's. A row is its relation's place in the list, its leaves with
//! each Ident's place left empty, and its Idents in the order of their
//! places. A leaf is any value that compares in a total order. The
//! `RIGID_DET` evaluation searches it over a part's rows, and `arclog-cli`
//! over the engine's rows and a record's.

use std::collections::{BTreeMap, BTreeSet};
use std::hash::Hash;

use crate::hash::StableHashMap;

/// One row: the place of its relation, its leaves with each Ident's place
/// `None`, and its Idents, each by its number on its side.
type Row<L> = (usize, Vec<Option<L>>, Vec<usize>);

/// One side's rows of the relations compared, with the count of its Idents.
pub struct IdentRows<L> {
    rows: Vec<Row<L>>,
    idents: usize,
}

/// The rows of one side, as it is built: each Ident, whatever its key `K`
/// is, takes a number when it first stands in a row.
pub struct IdentRowsBuilder<L, K> {
    numbers: StableHashMap<K, usize>,
    rows: Vec<Row<L>>,
}

impl<L, K: Hash + Eq> Default for IdentRowsBuilder<L, K> {
    fn default() -> Self {
        IdentRowsBuilder { numbers: StableHashMap::default(), rows: Vec::new() }
    }
}

impl<L, K: Hash + Eq> IdentRowsBuilder<L, K> {
    /// Adds a row of the relation at `relation`: its `leaves`, `None` at
    /// the place of each Ident, and its Idents, in the order of their
    /// places.
    pub fn push(&mut self, relation: usize, leaves: Vec<Option<L>>, idents: impl IntoIterator<Item = K>) {
        let idents = idents
            .into_iter()
            .map(|ident| {
                let next = self.numbers.len();
                *self.numbers.entry(ident).or_insert(next)
            })
            .collect();
        self.rows.push((relation, leaves, idents));
    }

    /// The rows added.
    pub fn finish(self) -> IdentRows<L> {
        IdentRows { rows: self.rows, idents: self.numbers.len() }
    }
}

impl<L: Ord + Clone> IdentRows<L> {
    /// The row sets of the side, each Ident written as its class in
    /// `classes`.
    fn by_classes(&self, classes: &[usize]) -> BTreeSet<Row<L>> {
        self.rows.iter().map(|(relation, leaves, idents)| (*relation, leaves.clone(), idents.iter().map(|&i| classes[i]).collect())).collect()
    }
}

/// The classes of the Idents of both sides, each class a number, refined
/// round by round until no class splits: an Ident's key is its class and
/// the rows that hold it, each row by its relation, its leaves, the classes
/// of its Idents and the places this Ident stands at. Classes are numbered
/// by the order of their keys, so the numbering reads no order of Idents.
fn refine<L: Ord + Clone>(sides: [&IdentRows<L>; 2], mut classes: [Vec<usize>; 2]) -> [Vec<usize>; 2] {
    loop {
        type Key<L> = (usize, Vec<(usize, Vec<Option<L>>, Vec<usize>, Vec<usize>)>);
        let keys: [Vec<Key<L>>; 2] = [0, 1].map(|s| {
            let mut keys: Vec<Key<L>> = (0..sides[s].idents).map(|i| (classes[s][i], Vec::new())).collect();
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
        let numbering: BTreeMap<&Key<L>, usize> = keys.iter().flatten().collect::<BTreeSet<_>>().into_iter().enumerate().map(|(n, key)| (key, n)).collect();
        let before = classes[0].iter().chain(&classes[1]).collect::<BTreeSet<_>>().len();
        classes = [0, 1].map(|s| keys[s].iter().map(|key| numbering[key]).collect());
        if numbering.len() == before {
            return classes;
        }
    }
}

/// Whether one renaming of Idents, a bijection from the Idents of `ours`
/// onto those of `theirs`, maps the rows of `ours` one to one onto the rows
/// of `theirs`. It refines the classes of Idents of both sides, as
/// `refine` gives, and, where a class holds more than one Ident of a
/// side, pairs one Ident of `ours` of a smallest such class with each Ident
/// of `theirs` of that class in turn, and refines again.
pub fn renaming_between<L: Ord + Clone>(ours: &IdentRows<L>, theirs: &IdentRows<L>) -> bool {
    if ours.idents != theirs.idents {
        return false;
    }
    individualized(ours, theirs, [vec![0; ours.idents], vec![0; theirs.idents]])
}

/// Whether a renaming exists that keeps each Ident in its class of
/// `classes`, as [`renaming_between`] gives.
fn individualized<L: Ord + Clone>(ours: &IdentRows<L>, theirs: &IdentRows<L>, classes: [Vec<usize>; 2]) -> bool {
    let classes = refine([ours, theirs], classes);
    let mut members: BTreeMap<usize, [Vec<usize>; 2]> = BTreeMap::new();
    for (s, side) in classes.iter().enumerate() {
        for (ident, &class) in side.iter().enumerate() {
            members.entry(class).or_default()[s].push(ident);
        }
    }
    if members.values().any(|[ours, theirs]| ours.len() != theirs.len()) {
        return false;
    }
    let Some((_, [ours_idents, theirs_idents])) = members.iter().filter(|(_, [ours, _])| ours.len() > 1).min_by_key(|(class, [ours, _])| (ours.len(), **class)) else {
        return ours.by_classes(&classes[0]) == theirs.by_classes(&classes[1]);
    };
    let fresh = classes[0].iter().chain(&classes[1]).max().map_or(0, |&max| max + 1);
    theirs_idents.iter().any(|&other| {
        let mut split = classes.clone();
        split[0][ours_idents[0]] = fresh;
        split[1][other] = fresh;
        individualized(ours, theirs, split)
    })
}
