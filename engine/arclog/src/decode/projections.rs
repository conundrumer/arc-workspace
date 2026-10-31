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
//! extends only the sets under it.

use std::sync::Arc;
use std::time::Instant;

use super::interface::Assigned;
use super::Decoder;
use crate::eval::join::Budget;
use crate::eval::{BodyValue, Limits, Outcome, ReachedBound, RelationValue, Stop};
use crate::hash::{StableHashMap, StableHashSet};
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
    let mut search = Search { relations, cap, budget, projected: StableHashMap::default(), counted: StableHashMap::default(), under: StableHashMap::default() };
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
    counted: StableHashMap<(usize, usize, Box<[u16]>), usize>,
    /// Whether a set of columns, in increasing order, is under the cap.
    under: StableHashMap<Box<[u16]>, bool>,
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
    fn extend(&mut self, set: &mut Vec<u16>, from: u16, arity: u16, found: &mut Vec<Vec<u16>>) -> Result<(), ReachedBound> {
        let mut larger = false;
        for column in from..arity {
            set.push(column);
            if self.is_under(set)? {
                larger = true;
                self.extend(set, column + 1, arity, found)?;
            }
            set.pop();
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
    /// increasing order, holds at most the cap.
    fn is_under(&mut self, set: &[u16]) -> Result<bool, ReachedBound> {
        if let Some(&under) = self.under.get(set) {
            return Ok(under);
        }
        self.budget.charge_work(1)?;
        let mut under = true;
        for relation in 0..self.relations.len() {
            if self.relations[relation].is_empty() {
                continue;
            }
            let mut count: u128 = 1;
            for part in 0..self.relations[relation].parts().len() {
                let positions = self.positions(relation, part, set);
                if positions.is_empty() {
                    continue;
                }
                count = count.saturating_mul(self.part_len(relation, part, positions)? as u128);
            }
            if count > u128::from(self.cap) {
                under = false;
                break;
            }
        }
        self.under.insert(set.into(), under);
        Ok(under)
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
    /// than the cap result: `part_rows` gives the rows. A projection that
    /// reads the rows counts each as one binding tried, once for each
    /// projection whichever of the two reads it first.
    fn part_len(&mut self, relation: usize, part: usize, positions: Box<[u16]>) -> Result<usize, ReachedBound> {
        let key = (relation, part, positions);
        if let Some(rows) = self.projected.get(&key) {
            return Ok(rows.len());
        }
        if let Some(&count) = self.counted.get(&key) {
            return Ok(count);
        }
        let this = &self.relations[relation].parts()[part];
        if key.2.len() == this.columns.len() {
            return Ok(this.rows.len());
        }
        self.budget.charge_work(this.rows.len() as u64)?;
        // A row of at most four cells packs into one key.
        if key.2.len() > 4 {
            let projection = Self::project(this, &key.2);
            let count = projection.len();
            self.projected.insert(key, projection);
            return Ok(count);
        }
        let mut seen: StableHashSet<u128> = StableHashSet::default();
        for row in this.rows.rows() {
            seen.insert(key.2.iter().fold(0u128, |packed, &position| packed << 32 | u128::from(row[usize::from(position)].encoding())));
            if seen.len() as u64 > self.cap {
                break;
            }
        }
        let count = seen.len();
        self.counted.insert(key, count);
        Ok(count)
    }

    /// The rows of `part` of `relation` projected onto `positions`, without
    /// repeats. A projection that reads the rows counts each as one binding
    /// tried, unless `part_len` counted them.
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
