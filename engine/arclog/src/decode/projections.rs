//! The maximal projections of the body so far, as
//! `docs/engine/synthesis.md#decode-interface` gives them: the largest sets of the body's columns whose projection,
//! without repeated rows, holds at most the projection cap of
//! `docs/engine/synthesis.md#decode-settings` on every example, at every
//! assignment.
//!
//! A relation is the product of its parts, so the count of a set's
//! projection is the product of the counts of its plain projections onto the
//! parts it meets. The search projects each part apart and builds no product. A
//! set over the cap has every larger set over the cap too, so the search
//! extends only the sets under it. A set under the cap has every smaller set
//! under the cap too, so the search reads no row for a set that a set it read
//! as under the cap holds, or that holds a set it read as over the cap.
//!
//! A column is a function of a set where adding it to the set leaves the
//! set's count the same on every relation, and then of each larger set. A read
//! of a set under the cap finds each column that its rows give one value in each
//! row of the set's projection, and the search finds others where two sets it
//! knows the counts of differ by the column and have the same counts. A set that holds such a set and the column has the count
//! of the set without the column, so the search reads no row for it. A set
//! that holds such a set and not the column is under the cap with the column
//! added, so no set that holds it and not the column is maximal: the search
//! visits none of them.
//!
//! The rows of a part are read once for all the parts that hold the same
//! columns and the same rows in the same order, which the relations of other
//! assignments and examples often do: [`classify`] puts such parts in one
//! class. What a read of a part's rows gives is the count of its projection onto
//! some positions, the count of rows read to find it, and the columns that are
//! a function of the projection. Those depend on the part's columns, its rows in
//! their order, the positions and the cap, and on nothing of the relation that
//! holds the part, so each relation takes the answer of the first read of its
//! class. Each relation still counts the work that its own read would count, in
//! the same order, so the work it counts, and the bound it reaches, are those of a
//! read of its own. The projection a found set builds from a class's rows is also
//! built once, as a read of it for each relation would build equal rows.

use std::sync::Arc;

use super::interface::Assigned;
use super::Decoder;
use crate::eval::join::Budget;
use crate::eval::{BodyValue, Limits, Outcome, ReachedBound, RelationValue, Stop};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::relations::{ColumnIndex, Relation, RelationPart, RowSet};
use crate::session::TaskSession;
use crate::terms::TermId;

/// One projection: a set of the body's columns, and the body's rows projected
/// onto them.
#[derive(Clone, Debug)]
pub struct Projection {
    /// The set's columns in the body, in increasing order. Column `i` of
    /// `rows` is the body's column `columns[i]`.
    pub columns: Box<[ColumnIndex]>,
    /// The projection of the body's rows on each example, at each
    /// assignment, in the order of the body's: `None` where the body is
    /// undefined.
    pub rows: Box<[Assigned<Option<Arc<Relation>>>]>,
}

/// The projections of a body, or the bound that stopped the search.
#[derive(Clone, Debug)]
pub enum Projections {
    /// The projections, in the order of their columns. Empty where no column
    /// stands alone under the cap.
    Found(Vec<Projection>),
    /// A bound that ended the walk of the body's assignments, or the search:
    /// no set's projection is known on every example. A bound of one evaluation
    /// leaves that assignment without rows, and the search reads the others.
    Stopped(Stop),
}

/// The projections of `values`, the body's value on each example at each
/// assignment, at `cap` rows. The rows the search reads of one value count
/// under the binding cap, as the bindings of one evaluation count. A stop is at
/// `form`.
pub fn projections(values: &[Assigned<BodyValue>], cap: u64, limits: &Limits, session: &TaskSession, form: &NodePath) -> Projections {
    let mut relations: Vec<&Relation> = Vec::new();
    for assigned in values {
        if let Some(stop) = assigned.stop.as_ref().filter(|stop| !stop.bound.is_assignment()) {
            return Projections::Stopped(stop.clone());
        }
        for (_, value) in &assigned.at {
            match &value.0 {
                RelationValue::Rows(relation) => relations.push(relation),
                RelationValue::Undefined => {}
                RelationValue::Stopped(stop) if stop.bound.is_assignment() => {}
                RelationValue::Stopped(stop) => return Projections::Stopped(stop.clone()),
            }
        }
    }
    let stopped = |bound: ReachedBound| Projections::Stopped(Stop { bound, form: form.clone() });
    let Some(arity) = relations.first().map(|relation| relation.arity()) else { return Projections::Found(Vec::new()) };
    let exact = relations.iter().map(|relation| usize::from(!relation.is_empty())).collect();
    let budgets = relations.iter().map(|_| Budget::new(limits, session)).collect();
    let (classes, class_part) = classify(&relations);
    let mut search = Search {
        relations, cap, request: limits.request.clone(), budgets, classes, reads: class_part.iter().map(|_| StableHashMap::default()).collect(), class_part, entries: Vec::new(),
        under: StableHashMap::default(),
        read_under: Vec::new(), read_over: Vec::new(),
        exact: StableHashMap::from_iter([(Box::default(), exact)]), determined: Vec::new(),
    };
    let sets = match search.maximal(arity) {
        Ok(sets) => sets,
        Err(bound) => return stopped(bound),
    };
    let mut found = Vec::new();
    for set in sets {
        let mut next = 0;
        let mut rows = Vec::new();
        for assigned in values {
            let mut at = Vec::new();
            for (assignment, value) in &assigned.at {
                let projection = match &value.0 {
                    RelationValue::Rows(_) => {
                        next += 1;
                        match search.relation_on(next - 1, &set) {
                            Ok(relation) => Some(Arc::new(relation)),
                            Err(bound) => return stopped(bound),
                        }
                    }
                    RelationValue::Undefined | RelationValue::Stopped(_) => None,
                };
                at.push((assignment.clone(), projection));
            }
            rows.push(Assigned { at, stop: None });
        }
        found.push(Projection { columns: set.iter().map(|&column| ColumnIndex(column)).collect(), rows: rows.into() });
    }
    Projections::Found(found)
}

/// The class of each part of each relation of `relations`, as `classes[relation][part]`,
/// and for each class the relation and the part of the first part in it. Two
/// parts are in one class where they hold the same columns, in the same order,
/// and the same rows in the same order ([`RowSet::laid_out_as`]), so a read of
/// the rows of either gives what a read of the other gives. A relation with no
/// row has no class for its parts: the search reads none of them.
fn classify(relations: &[&Relation]) -> (Vec<Box<[u32]>>, Vec<(usize, usize)>) {
    // The parts of one bucket may differ in rows that the fingerprint does not read.
    let mut buckets: StableHashMap<(Box<[u16]>, usize, u64), Vec<u32>> = StableHashMap::default();
    let mut class_part: Vec<(usize, usize)> = Vec::new();
    let mut classes = Vec::with_capacity(relations.len());
    for (relation, held) in relations.iter().enumerate() {
        if held.is_empty() {
            classes.push(Box::default());
            continue;
        }
        let mut of = Vec::with_capacity(held.parts().len());
        for (part, this) in held.parts().iter().enumerate() {
            let key = (this.columns.iter().map(|column| column.0).collect(), this.rows.len(), fingerprint(&this.rows));
            let bucket = buckets.entry(key).or_default();
            let same = bucket.iter().copied().find(|&class| {
                let (first, at) = class_part[class as usize];
                relations[first].parts()[at].rows.laid_out_as(&this.rows)
            });
            of.push(same.unwrap_or_else(|| {
                let class = u32::try_from(class_part.len()).expect("fewer than 2^32 classes");
                class_part.push((relation, part));
                bucket.push(class);
                class
            }));
        }
        classes.push(of.into());
    }
    (classes, class_part)
}

/// A hash of the rows at about sixteen places of `rows`, and of its last row,
/// and of its count. Two sets that hold the same rows in the same order have
/// equal fingerprints. It reads a few rows, and the classes check the rest.
fn fingerprint(rows: &RowSet) -> u64 {
    let count = rows.len();
    let mut hash = count as u64;
    let mut mix = |row: &[TermId]| {
        for cell in row {
            hash = (hash.rotate_left(5) ^ u64::from(cell.encoding())).wrapping_mul(0x517C_C1B7_2722_0A95);
        }
    };
    for number in (0..count).step_by((count / 16).max(1)) {
        mix(rows.row(number));
    }
    if count > 0 {
        mix(rows.row(count - 1));
    }
    hash
}

/// A set of relation numbers.
#[derive(Default)]
struct Marked(Vec<u64>);

impl Marked {
    fn has(&self, relation: usize) -> bool {
        self.0.get(relation / 64).is_some_and(|word| word >> (relation % 64) & 1 == 1)
    }

    fn mark(&mut self, relation: usize) {
        if self.0.len() <= relation / 64 {
            self.0.resize(relation / 64 + 1, 0);
        }
        self.0[relation / 64] |= 1 << (relation % 64);
    }
}

/// What a read of the rows of the parts of one class gives for the projection
/// onto some positions ([`Search::count`]).
struct Counted {
    /// The count of the rows of the projection, without repeats and up to one
    /// over the cap.
    count: usize,
    /// The count of the rows read to find it.
    read: u64,
    /// The columns of the part outside the projection that are a function of
    /// it in the part's rows, none where the count is over the cap.
    functions: Box<[u16]>,
}

/// The projection of the parts of one class onto some positions, with what the
/// search has found of it.
#[derive(Default)]
struct Projected {
    /// What the first read of the rows gave, none before a read.
    counted: Option<Counted>,
    /// The rows of the projection, without repeats, none before a found set
    /// builds them.
    rows: Option<RowSet>,
    /// The relations that have counted the work of the read ([`Search::part_len`]).
    counted_by: Marked,
    /// The relations that have asked for the rows ([`Search::part_rows`]).
    built_by: Marked,
}

/// The search over the sets of columns of `relations`, which hold one arity.
struct Search<'a> {
    relations: Vec<&'a Relation>,
    cap: u64,
    /// The work of the request, whose gauge of the projection cap the search notes.
    request: crate::eval::RequestWork,
    /// The count of the rows read of each relation.
    budgets: Vec<Budget<'a>>,
    /// The class of each part of each relation ([`classify`]).
    classes: Vec<Box<[u32]>>,
    /// The relation and the part of the first part of each class.
    class_part: Vec<(usize, usize)>,
    /// For each class, the number in `entries` of its projection onto the
    /// positions in the part's rows, in increasing order.
    reads: Vec<StableHashMap<Box<[u16]>, usize>>,
    entries: Vec<Projected>,
    /// Whether a set of columns, in increasing order, is under the cap.
    under: StableHashMap<Box<[u16]>, bool>,
    /// The sets that `is_under` read the rows of and found under the cap.
    read_under: Vec<Box<[u16]>>,
    /// The sets that `is_under` read the rows of and found over the cap.
    read_over: Vec<Box<[u16]>>,
    /// The count of the projection of each relation onto a set under the
    /// cap, 0 for an empty relation, where the search knows it.
    exact: StableHashMap<Box<[u16]>, Box<[usize]>>,
    /// Each column found to be a function of a set, on every relation, with
    /// that set, which does not hold it. No set of a pair holds the set of
    /// another pair of the same column.
    determined: Vec<(Box<[u16]>, u16)>,
}

impl<'a> Search<'a> {
    /// The sets under the cap that no larger set under the cap holds, in the
    /// order of their columns: the set of all columns where it is under the
    /// cap, with no further search. Each set tested counts as one binding
    /// tried.
    fn maximal(&mut self, arity: u16) -> Result<Vec<Vec<u16>>, ReachedBound> {
        let all: Vec<u16> = (0..arity).collect();
        if arity > 0 && self.is_under(&all)? {
            return Ok(vec![all]);
        }
        // A set that leaves out one column holds most of the sets the visit
        // below tests, so one read of it answers them with no read of their own.
        for column in 0..arity {
            let rest: Vec<u16> = all.iter().copied().filter(|&other| other != column).collect();
            if !rest.is_empty() {
                self.is_under(&rest)?;
            }
        }
        let mut found = Vec::new();
        self.extend(&mut Vec::new(), 0, arity, &mut found)?;
        found.sort();
        Ok(found)
    }

    /// Visits each set under the cap that adds columns from `from` on to
    /// `set`, and gives those that are maximal.
    /// A set that holds `set` and lacks a column that `set` determines
    /// is not maximal, so the visit skips each such set: it ends where
    /// `set` determines a column under `from`, and adds no column after one
    /// that `set` determines.
    fn extend(&mut self, set: &mut Vec<u16>, from: u16, arity: u16, found: &mut Vec<Vec<u16>>) -> Result<(), ReachedBound> {
        if self.determines_up_to(set, from.checked_sub(1)) {
            return Ok(());
        }
        let mut larger = false;
        for column in from..arity {
            set.push(column);
            if self.is_under(set)? {
                larger = true;
                self.extend(set, column + 1, arity, found)?;
            }
            set.pop();
            if self.determines_up_to(set, Some(column)) {
                break;
            }
        }
        if !set.is_empty() && !larger {
            for column in (0..from.saturating_sub(1)).filter(|column| !set.contains(column)) {
                let mut with = set.clone();
                with.insert(with.partition_point(|&c| c < column), column);
                if self.is_under(&with)? {
                    return Ok(());
                }
            }
            found.push(set.clone());
        }
        Ok(())
    }

    /// Whether the projection of every nonempty relation onto `set`, in
    /// increasing order, holds at most the cap. Where a set read before
    /// gives the answer, as the module doc gives, it reads no row.
    fn is_under(&mut self, set: &[u16]) -> Result<bool, ReachedBound> {
        if let Some(&under) = self.under.get(set) {
            return Ok(under);
        }
        self.budgets[0].charge_work(1)?;
        let reduced = self.reduced(set);
        if reduced.len() < set.len() {
            let under = self.is_under(&reduced)?;
            if let Some(counts) = self.exact.get(reduced.as_slice()).cloned() {
                self.exact.insert(set.into(), counts);
            }
            self.under.insert(set.into(), under);
            return Ok(under);
        }
        let known = if self.read_under.iter().any(|read| is_subset(set, read)) {
            Some(true)
        } else if self.read_over.iter().any(|read| is_subset(read, set)) {
            Some(false)
        } else {
            None
        };
        if let Some(under) = known {
            self.under.insert(set.into(), under);
            return Ok(under);
        }
        let mut under = true;
        let mut counts = vec![0usize; self.relations.len()];
        // The columns that are a function of `set` on every relation read.
        let mut functions: Option<Vec<u16>> = None;
        // The positions of `set` in the parts of each class, found when a relation first meets the class.
        let mut positions: Vec<Option<Box<[u16]>>> = vec![None; self.class_part.len()];
        for relation in 0..self.relations.len() {
            if self.relations[relation].is_empty() {
                continue;
            }
            let mut count: u128 = 1;
            let mut own: Vec<u16> = Vec::new();
            for part in 0..self.relations[relation].parts().len() {
                let class = self.classes[relation][part] as usize;
                let at = positions[class].get_or_insert_with(|| {
                    let (first, at) = self.class_part[class];
                    Self::positions(&self.relations[first].parts()[at], set)
                });
                if at.is_empty() {
                    continue;
                }
                let part_count = self.part_len(relation, part, at, &mut own)?;
                count = count.saturating_mul(part_count as u128);
            }
            if count > u128::from(self.cap) {
                under = false;
                break;
            }
            counts[relation] = count as usize;
            functions = Some(match functions {
                None => own,
                Some(held) => held.into_iter().filter(|column| own.contains(column)).collect(),
            });
        }
        self.under.insert(set.into(), under);
        if under { &mut self.read_under } else { &mut self.read_over }.push(set.into());
        if under {
            for column in functions.unwrap_or_default() {
                self.determine(set, column);
            }
            self.learn(set, counts.into());
        }
        Ok(under)
    }

    /// Keeps `counts`, the exact counts of `set`, which is under the cap,
    /// and each column of `set` that the rest of `set` determines: the rest
    /// has the same counts. A column is a function of the rest wherever the
    /// two counts are equal, since the count of a projection grows with its
    /// columns.
    fn learn(&mut self, set: &[u16], counts: Box<[usize]>) {
        for at in 0..set.len() {
            let column = set[at];
            let rest: Vec<u16> = set.iter().copied().filter(|&other| other != column).collect();
            if self.exact.get(rest.as_slice()) == Some(&counts) {
                self.determine(&rest, column);
            }
        }
        self.exact.insert(set.into(), counts);
    }

    /// Keeps that `column` is a function of `from`, where no set that
    /// `from` holds is known to determine it, and drops each larger set
    /// kept for it.
    fn determine(&mut self, from: &[u16], column: u16) {
        if self.determined.iter().any(|(held, by)| *by == column && is_subset(held, from)) {
            return;
        }
        self.determined.retain(|(held, by)| *by != column || !is_subset(from, held));
        self.determined.push((from.into(), column));
    }

    /// `set` without each column that a set it holds without that column
    /// determines, one column at a time. It has the counts of `set`.
    fn reduced(&self, set: &[u16]) -> Vec<u16> {
        let mut reduced = set.to_vec();
        while let Some(column) = self.determined.iter().find(|(from, by)| reduced.contains(by) && is_subset(from, &reduced)).map(|(_, by)| *by) {
            reduced.retain(|&other| other != column);
        }
        reduced
    }

    /// Whether `set` determines a column it does not hold, at or under
    /// `column`; none where `column` is `None`.
    fn determines_up_to(&self, set: &[u16], column: Option<u16>) -> bool {
        let Some(column) = column else { return false };
        self.determined.iter().any(|(from, by)| *by <= column && !set.contains(by) && is_subset(from, set))
    }

    /// The positions in the rows of `part` of the columns of `set` that the
    /// part holds, in increasing order.
    fn positions(part: &RelationPart, set: &[u16]) -> Box<[u16]> {
        let mut positions: Vec<u16> = part
            .columns
            .iter()
            .enumerate()
            .filter(|(_, column)| set.contains(&column.0))
            .map(|(position, _)| u16::try_from(position).expect("a part of fewer than 2^16 columns"))
            .collect();
        positions.sort_unstable();
        positions.into()
    }

    /// The number in `entries` of the projection of the parts of `class` onto
    /// `positions`, which the search adds where it has none.
    fn entry(&mut self, class: usize, positions: &[u16]) -> usize {
        if let Some(&at) = self.reads[class].get(positions) {
            return at;
        }
        self.entries.push(Projected::default());
        self.reads[class].insert(positions.into(), self.entries.len() - 1);
        self.entries.len() - 1
    }

    /// The count of the rows of `part` of `relation` projected onto
    /// `positions`, without repeats, or one over the cap where more rows
    /// than the cap result. It adds to `functions` the columns that are a function
    /// of the projection in the part's rows, none where the count is over the
    /// cap.
    ///
    /// The count reads the rows until its projection passes the cap, counts
    /// each row it reads as one binding tried, and keeps the count and no row:
    /// only the projections of the sets the search finds are built, by
    /// `part_rows`. The first relation of a class that asks reads the rows
    /// ([`Search::count`]) and keeps what the read gave. Each relation, the
    /// first included, counts the work of that read once, on its own budget, as
    /// a read of its own would count it: a check of the bounds before the
    /// read, and then the rows read. A later ask of the same relation for the
    /// same projection counts none, as before.
    fn part_len(&mut self, relation: usize, part: usize, positions: &[u16], functions: &mut Vec<u16>) -> Result<usize, ReachedBound> {
        let class = self.classes[relation][part] as usize;
        let (first, at) = self.class_part[class];
        let held: &'a Relation = self.relations[first];
        let this: &'a RelationPart = &held.parts()[at];
        if positions.len() == this.columns.len() {
            return Ok(this.rows.len());
        }
        let entry = self.entry(class, positions);
        if !self.entries[entry].counted_by.has(relation) {
            self.budgets[relation].charge_work(0)?;
            if self.entries[entry].counted.is_none() {
                let (count, read, found) = Self::count(this, positions, self.cap);
                // A projection over the cap is how the search finds a set too large, which it expects; the gauge counts each.
                if count as u64 > self.cap {
                    self.request.gauges().hit(crate::eval::Gauge::ProjectionRows, count as u64, self.cap);
                } else {
                    self.request.gauges().note(crate::eval::Gauge::ProjectionRows, count as u64, self.cap);
                }
                let functions = found.into_iter().map(|position| this.columns[usize::from(position)].0).collect();
                self.entries[entry].counted = Some(Counted { count, read, functions });
            }
            let read = self.entries[entry].counted.as_ref().map_or(0, |counted| counted.read);
            self.budgets[relation].charge_work(read)?;
            self.entries[entry].counted_by.mark(relation);
        }
        let counted = self.entries[entry].counted.as_ref().expect("a projection that the relation counted");
        functions.extend_from_slice(&counted.functions);
        Ok(counted.count)
    }

    /// The count of the rows of `part` projected onto `positions`, without
    /// repeats, up to one over `cap`, the count of the rows read to find it,
    /// and, where the count is under the cap, the positions of the part's rows
    /// outside `positions` that hold one value in all the rows of each row of
    /// the projection: each is a function of the projection.
    ///
    /// The rows are numbered in the groups of [`Groups`], from 0 in the order
    /// first read, as the projected rows are read, which gives the same count,
    /// the same rows read and the same columns as a table that holds each
    /// projected row whole. A group's first row is kept only while a column may
    /// still be a function, since no other read of it follows.
    fn count(part: &RelationPart, positions: &[u16], cap: u64) -> (usize, u64, Vec<u16>) {
        let width = part.columns.len();
        let mut functions: Vec<u16> = (0..width as u16).filter(|position| !positions.contains(position)).collect();
        let mut groups = Groups::new(positions.len());
        // The cells of the first row read of each projection, row after row.
        let mut first: Vec<TermId> = Vec::new();
        let (mut count, mut read) = (0usize, 0u64);
        for row in part.rows.rows() {
            read += 1;
            let (group, new) = groups.number(row, positions);
            if new {
                count += 1;
                if count as u64 > cap {
                    return (count, read, Vec::new());
                }
                if !functions.is_empty() {
                    first.extend_from_slice(row);
                }
            } else if !functions.is_empty() {
                let held = &first[group as usize * width..(group as usize + 1) * width];
                functions.retain(|&position| row[usize::from(position)] == held[usize::from(position)]);
            }
        }
        (count, read, functions)
    }

    /// The rows of `part` of `relation` projected onto `positions`, without
    /// repeats. A projection that reads the rows counts each as one binding
    /// tried, unless `part_len` counted them for this relation: it counted all
    /// of them, since the search finds only sets under the cap. A relation that
    /// asks again counts none. The first ask of a class builds the rows, and
    /// the others take them: the rows of the projection depend on the class's
    /// rows and the positions alone.
    fn part_rows(&mut self, relation: usize, part: usize, positions: &[u16]) -> Result<RowSet, ReachedBound> {
        let class = self.classes[relation][part] as usize;
        let (first, at) = self.class_part[class];
        let held: &'a Relation = self.relations[first];
        let this: &'a RelationPart = &held.parts()[at];
        if positions.len() == this.columns.len() {
            return Ok(this.rows.clone());
        }
        let entry = self.entry(class, positions);
        if !self.entries[entry].built_by.has(relation) {
            if !self.entries[entry].counted_by.has(relation) {
                self.budgets[relation].charge_work(this.rows.len() as u64)?;
            }
            self.entries[entry].built_by.mark(relation);
        }
        let projected = self.entries[entry].rows.get_or_insert_with(|| Self::project(this, positions));
        Ok(projected.clone())
    }

    /// The rows of `part` projected onto `positions`, without repeats.
    fn project(part: &RelationPart, positions: &[u16]) -> RowSet {
        let mut projection = RowSet::empty(positions.len() as u16);
        let mut projected: Vec<TermId> = Vec::with_capacity(positions.len());
        for row in part.rows.rows() {
            projected.clear();
            projected.extend(positions.iter().map(|&position| row[usize::from(position)]));
            projection.insert_slice(&projected);
        }
        projection
    }

    /// The `relation`th relation projected onto `set`, whose columns stand at
    /// their ranks in `set`: the product of the plain projections of the parts it
    /// meets, or the empty relation where the relation is empty.
    fn relation_on(&mut self, relation: usize, set: &[u16]) -> Result<Relation, ReachedBound> {
        let arity = set.len() as u16;
        if self.relations[relation].is_empty() {
            let columns = (0..arity).map(ColumnIndex).collect();
            return Ok(Relation::from_parts(arity, Box::new([RelationPart { columns, rows: RowSet::empty(arity) }])));
        }
        let mut parts = Vec::new();
        for part in 0..self.relations[relation].parts().len() {
            let positions = Self::positions(&self.relations[relation].parts()[part], set);
            if positions.is_empty() {
                continue;
            }
            let columns = positions
                .iter()
                .map(|&position| {
                    let column = self.relations[relation].parts()[part].columns[usize::from(position)].0;
                    ColumnIndex(set.iter().position(|&c| c == column).expect("a column of the set") as u16)
                })
                .collect();
            parts.push(RelationPart { columns, rows: self.part_rows(relation, part, &positions)? });
        }
        Ok(Relation::from_parts(arity, parts.into()))
    }
}

/// The numbers of the distinct projected rows that a scan reads, in the order it
/// reads them first. A table of open addressing holds, for each group, the group's
/// projected cells, and a slot holds the hash of the cells in its upper 32 bits and
/// 1 + the group's number in its lower 32 bits, as a slot of a row set does, so a
/// probe that passes a slot of another group ends at the compare of two hashes. The
/// groups are those of a table that holds each projected row whole, because a
/// hash decides no group: a slot with the hash of a row is its group only where the
/// cells are equal.
struct Groups {
    /// The count of cells of a projected row.
    width: usize,
    /// The cells of each group, group after group.
    cells: Vec<u32>,
    count: u32,
    /// 0 in an empty slot. The length is a power of two, and at most half of the
    /// slots are in use.
    slots: Vec<u64>,
}

/// An odd 64-bit number for each rank of a cell in a projected row, which
/// [`Groups::number`] multiplies the cell by.
const CELL_MULTIPLIERS: [u64; 64] = {
    let mut table = [0u64; 64];
    let mut rank = 0;
    while rank < table.len() {
        let mut z = (rank as u64 + 1).wrapping_mul(0x9E37_79B9_7F4A_7C15);
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        table[rank] = (z ^ (z >> 31)) | 1;
        rank += 1;
    }
    table
};

impl Groups {
    fn new(width: usize) -> Self {
        Groups { width, cells: Vec::new(), count: 0, slots: vec![0; 64] }
    }

    /// The number of the group of `row` projected onto `positions`, whose count
    /// is the groups' `width`, and whether the row is the first read of it.
    fn number(&mut self, row: &[TermId], positions: &[u16]) -> (u32, bool) {
        // The cells' products are independent of each other, so a row of many cells
        // takes about one step of the machine's multiplier for each, and not the
        // latency of a chain. A hash decides no group, so any hash of equal cells is one.
        let mut sum = 0u64;
        for (rank, &position) in positions.iter().enumerate() {
            sum = sum.wrapping_add((u64::from(row[usize::from(position)].encoding()) + 1).wrapping_mul(CELL_MULTIPLIERS[rank % CELL_MULTIPLIERS.len()]));
        }
        let mixed = (sum ^ (sum >> 29)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        let hash = (mixed ^ (mixed >> 32)) as u32;
        let mask = self.slots.len() - 1;
        let mut at = hash as usize & mask;
        loop {
            let slot = self.slots[at];
            if slot == 0 {
                break;
            }
            if (slot >> 32) as u32 == hash {
                let group = slot as u32 - 1;
                let held = &self.cells[group as usize * self.width..(group as usize + 1) * self.width];
                if positions.iter().zip(held).all(|(&position, &cell)| row[usize::from(position)].encoding() == cell) {
                    return (group, false);
                }
            }
            at = (at + 1) & mask;
        }
        let group = self.count;
        self.count += 1;
        self.cells.extend(positions.iter().map(|&position| row[usize::from(position)].encoding()));
        self.slots[at] = u64::from(hash) << 32 | u64::from(group + 1);
        if self.count as usize * 2 > self.slots.len() {
            self.grow();
        }
        (group, true)
    }

    /// Doubles the table. The groups are distinct, so each takes the first
    /// empty slot of its probe, and a slot keeps its hash, so no cell is read.
    fn grow(&mut self) {
        let mut slots = vec![0u64; self.slots.len() * 2];
        let mask = slots.len() - 1;
        for &held in self.slots.iter().filter(|&&held| held != 0) {
            let mut at = (held >> 32) as usize & mask;
            while slots[at] != 0 {
                at = (at + 1) & mask;
            }
            slots[at] = held;
        }
        self.slots = slots;
    }
}

/// Whether each column of `small` stands in `large`, both in increasing
/// order.
fn is_subset(small: &[u16], large: &[u16]) -> bool {
    let mut large = large.iter();
    small.iter().all(|column| large.any(|other| other == column))
}

impl Decoder<'_> {
    /// The projections of the sub-body that [`Decoder::rows`] gives, at the
    /// decode's projection cap, as `docs/engine/synthesis.md#decode-interface`
    /// gives them. `None` where no clause is in progress, and the sub-body's
    /// fault where it gives one. The search reads under the binding cap, as
    /// [`projections`] gives, and the cancellation. It writes no
    /// record of the trace.
    pub fn projections(&self) -> Option<Outcome<Projections>> {
        let _request = self.begin_request();
        let values = self.sub_body_values()?;
        let (program, _) = self.state.partial()?;
        let form = NodePath::top(program.value().forms.len() as u32 - 1);
        let mut assigned = Vec::new();
        for value in values.into_vec() {
            match value {
                Ok(value) => assigned.push(value),
                Err(fault) => return Some(Err(fault)),
            }
        }
        let limits = Limits::new(None, self.cancellation.clone()).in_request(self.request_work());
        Some(Ok(projections(&assigned, self.context.settings.projection_cap, &limits, self.session, &form)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::eval::Caps;
    use crate::session::{SessionBound, TaskSession};

    fn part(columns: &[u16], rows: &[&[u32]]) -> RelationPart {
        let mut set = RowSet::empty(columns.len() as u16);
        for row in rows {
            set.insert(row.iter().map(|&bits| TermId::from_encoding(bits)).collect::<Vec<_>>().into());
        }
        RelationPart { columns: columns.iter().map(|&column| ColumnIndex(column)).collect(), rows: set }
    }

    fn relation(arity: u16, parts: Vec<RelationPart>) -> Relation {
        Relation::from_parts(arity, parts.into())
    }

    /// The columns of each projection of `relations`, one on each example, at `cap`.
    fn projections_of(relations: Vec<Relation>, cap: u64) -> Vec<Vec<u16>> {
        let values: Vec<_> = relations
            .into_iter()
            .map(|relation| Assigned { at: vec![(Vec::new(), BodyValue(RelationValue::Rows(Arc::new(relation))))], stop: None })
            .collect();
        let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
        let limits = Limits::new(None, Default::default());
        let Projections::Found(found) = projections(&values, cap, &limits, &session, &NodePath::top(0)) else { panic!("the search ends") };
        found.iter().map(|projection| projection.columns.iter().map(|column| column.0).collect()).collect()
    }

    /// Nine rows over columns P, A, K at 0, 1, 2 with A = (P + K) % 2.
    fn pak() -> Relation {
        let rows: Vec<Vec<u32>> = (0..3).flat_map(|p| (0..3).map(move |k| vec![p, (p + k) % 2, k])).collect();
        let rows: Vec<&[u32]> = rows.iter().map(|row| &row[..]).collect();
        relation(3, vec![part(&[0, 1, 2], &rows)])
    }

    #[test]
    fn the_sets_under_the_cap_that_no_larger_set_holds_are_the_projections() {
        assert_eq!(projections_of(vec![pak()], 6), vec![vec![0, 1], vec![1, 2]]);
    }

    #[test]
    fn a_relation_under_the_cap_is_its_one_projection() {
        assert_eq!(projections_of(vec![pak()], 9), vec![vec![0, 1, 2]]);
    }

    #[test]
    fn the_product_of_two_parts_over_the_cap_gives_no_projection_across_them() {
        let product = |cap| {
            let rows: [&[u32]; 3] = [&[0], &[1], &[2]];
            projections_of(vec![relation(2, vec![part(&[0], &rows), part(&[1], &rows)])], cap)
        };
        assert_eq!(product(5), vec![vec![0], vec![1]]);
        assert_eq!(product(9), vec![vec![0, 1]]);
    }

    #[test]
    fn a_relation_over_the_cap_on_one_example_alone_gives_the_projections_under_it_on_both() {
        let small = relation(3, vec![part(&[0, 1, 2], &[&[0, 0, 0], &[1, 1, 1], &[2, 2, 2]])]);
        let rows: Vec<Vec<u32>> = (0..3).flat_map(|i| (0..3).map(move |j| vec![i, j, i])).collect();
        let rows: Vec<&[u32]> = rows.iter().map(|row| &row[..]).collect();
        let large = relation(3, vec![part(&[0, 1, 2], &rows)]);
        assert_eq!(projections_of(vec![small, large], 5), vec![vec![0, 2], vec![1]]);
    }

    #[test]
    fn a_column_alone_over_the_cap_is_in_no_projection() {
        let rows: [&[u32]; 3] = [&[0, 0], &[1, 1], &[2, 0]];
        assert_eq!(projections_of(vec![relation(2, vec![part(&[0, 1], &rows)])], 2), vec![vec![1]]);
        assert_eq!(projections_of(vec![relation(2, vec![part(&[0, 1], &rows)])], 1), Vec::<Vec<u16>>::new());
    }

    #[test]
    fn a_projection_holds_the_projected_rows_of_the_body() {
        let values = [Assigned { at: vec![(Vec::new(), BodyValue(RelationValue::Rows(Arc::new(pak()))))], stop: None }];
        let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
        let limits = Limits::new(None, Default::default());
        let Projections::Found(found) = projections(&values, 6, &limits, &session, &NodePath::top(0)) else { panic!("the search ends") };
        let [(_, Some(projected))] = &found[0].rows[0].at[..] else { panic!("one projection") };
        assert_eq!((projected.arity(), projected.len()), (2, 6));
    }

    #[test]
    fn a_wide_relation_under_the_cap_is_its_one_projection_with_no_search_over_its_subsets() {
        let columns: Vec<u16> = (0..40).collect();
        let row = vec![0; 40];
        assert_eq!(projections_of(vec![relation(40, vec![part(&columns, &[&row])])], 1), vec![columns]);
    }
}
