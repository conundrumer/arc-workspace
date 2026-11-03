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

use std::sync::Arc;
use std::time::Instant;

use super::interface::Assigned;
use super::Decoder;
use crate::eval::join::Budget;
use crate::eval::{BodyValue, Limits, Outcome, ReachedBound, RelationValue, Stop};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::relations::{ColumnIndex, Relation, RelationPart, RowSet};
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
    /// A bound that ended the body on some example or assignment, or the
    /// search: no set's projection is known on every example.
    Stopped(Stop),
}

/// The projections of `values`, the body's value on each example at each
/// assignment, at `cap` rows. A stop is at `form`.
pub fn projections(values: &[Assigned<BodyValue>], cap: u64, budget: &mut Budget<'_>, form: &NodePath) -> Projections {
    let mut relations: Vec<&Relation> = Vec::new();
    for assigned in values {
        if let Some(stop) = &assigned.stop {
            return Projections::Stopped(stop.clone());
        }
        for (_, value) in &assigned.at {
            match &value.0 {
                RelationValue::Rows(relation) => relations.push(relation),
                RelationValue::Undefined => {}
                RelationValue::Stopped(stop) => return Projections::Stopped(stop.clone()),
            }
        }
    }
    let stopped = |bound: ReachedBound| Projections::Stopped(Stop { bound, form: form.clone() });
    let Some(arity) = relations.first().map(|relation| relation.arity()) else { return Projections::Found(Vec::new()) };
    let exact = relations.iter().map(|relation| usize::from(!relation.is_empty())).collect();
    let mut search = Search {
        relations, cap, budget,
        projected: StableHashMap::default(), counted: StableHashMap::default(), under: StableHashMap::default(),
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

/// The search over the sets of columns of `relations`, which hold one arity.
struct Search<'a, 'b> {
    relations: Vec<&'a Relation>,
    cap: u64,
    budget: &'a mut Budget<'b>,
    /// The plain projections of a part, by relation, part and the positions in the
    /// part's rows, in increasing order.
    projected: StableHashMap<(usize, usize, Box<[u16]>), RowSet>,
    /// The count of the rows of a part projected, without repeats and up to
    /// one over the cap, for a projection that `is_under` counted and that
    /// `projected` does not hold.
    /// With each count, the columns of the relation outside the projection
    /// that are a function of it in the part's rows, none where the count is
    /// over the cap.
    counted: StableHashMap<(usize, usize, Box<[u16]>), (usize, Box<[u16]>)>,
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

impl Search<'_, '_> {
    /// The sets under the cap that no larger set under the cap holds, in the
    /// order of their columns: the set of all columns where it is under the
    /// cap, with no further search. Each set tested counts as one binding
    /// tried.
    fn maximal(&mut self, arity: u16) -> Result<Vec<Vec<u16>>, ReachedBound> {
        let all: Vec<u16> = (0..arity).collect();
        if arity > 0 && self.is_under(&all)? {
            return Ok(vec![all]);
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
        self.budget.charge_work(1)?;
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
        for relation in 0..self.relations.len() {
            if self.relations[relation].is_empty() {
                continue;
            }
            let mut count: u128 = 1;
            let mut own: Vec<u16> = Vec::new();
            for part in 0..self.relations[relation].parts().len() {
                let positions = self.positions(relation, part, set);
                if positions.is_empty() {
                    continue;
                }
                let (part_count, part_functions) = self.part_len(relation, part, positions)?;
                count = count.saturating_mul(part_count as u128);
                own.extend_from_slice(&part_functions);
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

    /// The positions in the rows of `part` of `relation` of the columns of
    /// `set` that the part holds, in increasing order.
    fn positions(&self, relation: usize, part: usize, set: &[u16]) -> Box<[u16]> {
        let columns = &self.relations[relation].parts()[part].columns;
        let mut positions: Vec<u16> = columns
            .iter()
            .enumerate()
            .filter(|(_, column)| set.contains(&column.0))
            .map(|(position, _)| u16::try_from(position).expect("a part of fewer than 2^16 columns"))
            .collect();
        positions.sort_unstable();
        positions.into()
    }

    /// The count of the rows of `part` of `relation` projected onto
    /// `positions`, without repeats, or one over the cap where more rows
    /// than the cap result. The count reads the rows until its projection
    /// passes the cap, counts each row it reads as one binding tried, and
    /// keeps the count and no row: only the projections of the sets the
    /// search finds are built, by `part_rows`.
    /// With the count, it gives the columns that are a function of the
    /// projection in the part's rows ([`Search::count`]).
    fn part_len(&mut self, relation: usize, part: usize, positions: Box<[u16]>) -> Result<(usize, Box<[u16]>), ReachedBound> {
        let key = (relation, part, positions);
        if let Some(rows) = self.projected.get(&key) {
            return Ok((rows.len(), Box::default()));
        }
        if let Some(counted) = self.counted.get(&key) {
            return Ok(counted.clone());
        }
        let this = &self.relations[relation].parts()[part];
        if key.2.len() == this.columns.len() {
            return Ok((this.rows.len(), Box::default()));
        }
        self.budget.charge_work(0)?;
        let (count, read, functions) = Self::count(this, &key.2, self.cap);
        self.budget.charge_work(read)?;
        let functions: Box<[u16]> = functions.into_iter().map(|position| this.columns[usize::from(position)].0).collect();
        self.counted.insert(key, (count, functions.clone()));
        Ok((count, functions))
    }

    /// The count of the rows of `part` projected onto `positions`, without
    /// repeats, up to one over `cap`, the count of the rows read to find it,
    /// and, where the count is under the cap, the positions of the part's rows
    /// outside `positions` that hold one value in all the rows of each row of
    /// the projection: each is a function of the projection.
    fn count(part: &RelationPart, positions: &[u16], cap: u64) -> (usize, u64, Vec<u16>) {
        // A row of at most four cells packs into one key.
        if positions.len() <= 4 {
            let mut groups: StableHashMap<u128, u32> = StableHashMap::default();
            return Self::scan(part, positions, cap, |row| {
                let next = groups.len() as u32;
                let key = positions.iter().fold(0u128, |packed, &position| packed << 32 | u128::from(row[usize::from(position)].encoding()));
                let group = *groups.entry(key).or_insert(next);
                (group, group == next)
            });
        }
        let mut groups: StableHashMap<Box<[TermId]>, u32> = StableHashMap::default();
        let mut projected: Vec<TermId> = Vec::with_capacity(positions.len());
        Self::scan(part, positions, cap, |row| {
            projected.clear();
            projected.extend(positions.iter().map(|&position| row[usize::from(position)]));
            // A repeat of a row takes no allocation.
            if let Some(&group) = groups.get(projected.as_slice()) {
                return (group, false);
            }
            let next = groups.len() as u32;
            groups.insert(projected.as_slice().into(), next);
            (next, true)
        })
    }

    /// [`Search::count`] where `group` gives the number of a row's projection,
    /// numbered from 0 in the order first read, and whether the row is the
    /// first read of it.
    fn scan(part: &RelationPart, positions: &[u16], cap: u64, mut group: impl FnMut(&[TermId]) -> (u32, bool)) -> (usize, u64, Vec<u16>) {
        let width = part.columns.len();
        let mut functions: Vec<u16> = (0..width as u16).filter(|position| !positions.contains(position)).collect();
        // The cells of the first row read of each projection, row after row.
        let mut first: Vec<TermId> = Vec::new();
        let (mut count, mut read) = (0usize, 0u64);
        for row in part.rows.rows() {
            read += 1;
            let (number, new) = group(row);
            if new {
                count += 1;
                if count as u64 > cap {
                    return (count, read, Vec::new());
                }
                first.extend_from_slice(row);
            } else if !functions.is_empty() {
                let held = &first[number as usize * width..(number as usize + 1) * width];
                functions.retain(|&position| row[usize::from(position)] == held[usize::from(position)]);
            }
        }
        (count, read, functions)
    }

    /// The rows of `part` of `relation` projected onto `positions`, without
    /// repeats. A projection that reads the rows counts each as one binding
    /// tried, unless `part_len` counted them: it counted all of them, since
    /// the search finds only sets under the cap.
    fn part_rows(&mut self, relation: usize, part: usize, positions: Box<[u16]>) -> Result<&RowSet, ReachedBound> {
        let key = (relation, part, positions);
        if !self.projected.contains_key(&key) {
            let this = &self.relations[relation].parts()[part];
            let projection = if key.2.len() == this.columns.len() {
                this.rows.clone()
            } else {
                if !self.counted.contains_key(&key) {
                    self.budget.charge_work(this.rows.len() as u64)?;
                }
                Self::project(this, &key.2)
            };
            self.projected.insert(key.clone(), projection);
        }
        Ok(&self.projected[&key])
    }

    /// The rows of `part` projected onto `positions`, without repeats.
    fn project(part: &RelationPart, positions: &[u16]) -> RowSet {
        let mut projection = RowSet::empty(positions.len() as u16);
        let mut projected: Vec<TermId> = Vec::with_capacity(positions.len());
        for row in part.rows.rows() {
            projected.clear();
            projected.extend(positions.iter().map(|&position| row[usize::from(position)]));
            // A repeat of a row takes no allocation.
            if !projection.contains(&projected) {
                projection.insert(projected.as_slice().into());
            }
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
            let positions = self.positions(relation, part, set);
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
            parts.push(RelationPart { columns, rows: self.part_rows(relation, part, positions)?.clone() });
        }
        Ok(Relation::from_parts(arity, parts.into()))
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
    /// fault where it gives one. The search runs as one evaluation of its
    /// own, under the binding cap, the deadline and the cancellation. It
    /// writes no record of the trace.
    pub fn projections(&self) -> Option<Outcome<Projections>> {
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
        let limits = Limits::new(self.context.settings.deadline.map(|deadline| Instant::now() + deadline), self.cancellation.clone());
        let mut budget = Budget::new(&limits, self.session);
        let found = projections(&assigned, self.context.settings.projection_cap, &mut budget, &form);
        budget.record();
        Some(Ok(found))
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
        let mut budget = Budget::new(&limits, &session);
        let Projections::Found(found) = projections(&values, cap, &mut budget, &NodePath::top(0)) else { panic!("the search ends") };
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
        let mut budget = Budget::new(&limits, &session);
        let Projections::Found(found) = projections(&values, 6, &mut budget, &NodePath::top(0)) else { panic!("the search ends") };
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
