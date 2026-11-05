//! Distance indexes over the finite values of an atom's trie. Spatial
//! predicates keep their usual final checks; these indexes avoid binding
//! cells whose distance already rules them out.

use super::*;
use crate::algebra::geometry::{Edge, Edges};

/// A sorted distance column of one trie run. Keeping the index alive makes
/// the run's address a stable memo key, including when its plan is released.
pub(super) struct DistanceIndex {
    _owner: Arc<Index>,
    rows: Vec<(i32, TermId)>,
}

fn mask(edges: Edges) -> u8 {
    edges.each().fold(0, |mask, edge| mask | (1 << edge as u8))
}

fn distance(value: TermId, edges: Option<Edges>) -> i32 {
    let Some(edges) = edges else { return Term::decode_number(value) };
    let p = Term::decode_box(value);
    edges.each().map(|edge| match edge {
        Edge::Top => p.top,
        Edge::Bottom => p.bottom,
        Edge::Left => p.left,
        Edge::Right => p.right,
    }).sum()
}

impl SearchMemo {
    fn distance_index(&self, owner: &Arc<Index>, run: &[TermId], edges: Option<Edges>, budget: &mut Budget<'_>) -> Result<Rc<DistanceIndex>, ReachedBound> {
        let key = (run.as_ptr() as usize, run.len(), edges.map_or(0, mask));
        if let Some(index) = self.tables.borrow().spatial.get(&key) {
            return Ok(index.clone());
        }
        let mut rows = Vec::with_capacity(run.len());
        for (at, &value) in run.iter().enumerate() {
            // As with an atom's trie, building an index creates no search
            // bindings. Still observe the operation's other bounds.
            if at % BATCH as usize == 0 { budget.charge_work(0)?; }
            rows.push((distance(value, edges), value));
        }
        rows.sort_unstable_by_key(|&(distance, value)| (distance, value.encoding()));
        let index = Rc::new(DistanceIndex { _owner: owner.clone(), rows });
        let mut tables = self.tables.borrow_mut();
        if tables.take(96 + run.len() * size_of::<(i32, TermId)>()) {
            tables.spatial.insert(key, index.clone());
        }
        Ok(index)
    }
}

impl Search<'_> {
    /// Intersect every applicable range before creating candidate bindings.
    /// Alternatives within one line predicate are unioned; separate
    /// predicates and the edges of containment are intersected.
    pub(super) fn spatial_values(&self, variable: Variable, owner: &Arc<Index>, at: IndexNode<'_>, budget: &mut Budget<'_>) -> Result<Option<Vec<TermId>>, ReachedBound> {
        let ty = &self.clause.variables[usize::from(variable.0)].ty;
        if at.is_empty() {
            return Ok(None);
        }
        let mut groups: Vec<Vec<(Option<Edges>, i32, i8)>> = Vec::new();
        if matches!(ty, ValueType::Int | ValueType::Nat) {
            groups.extend(self.number_bounds(variable).into_iter().map(|(value,comparison)|vec![(None,value,comparison)]));
        }
        if !ty.is_box() { return self.range_values(owner, at, groups, budget); }
        for &node in &self.plan.libs[usize::from(variable.0)] {
            let IrNode::Lib(atom) = &self.clause.nodes[node] else { unreachable!("a lib atom") };
            let Some(algebra) = crate::algebra::algebra(&atom.relation) else { continue };
            let arity = self.registry.algebra_relation(&atom.relation).expect("a declared algebra").columns.len();
            let mut bound = vec![None; arity];
            for (column, argument) in &atom.arguments.0 {
                bound[column.0 as usize] = self.bound_argument(*argument);
            }
            for (column, argument) in &atom.arguments.0 {
                if *argument == Argument::Variable(variable) {
                    groups.extend(algebra.margin_ranges(column.0, &bound).into_iter().map(|group|
                        group.into_iter().map(|range| (Some(range.edges), range.value, range.comparison)).collect()));
                }
            }
        }
        self.range_values(owner, at, groups, budget)
    }

    fn bound_argument(&self, argument: Argument) -> Option<TermId> {
        match argument {
            Argument::Term(value) => Some(value),
            Argument::Variable(v) => self.binding[usize::from(v.0)],
        }
    }

    fn number_bounds(&self, variable: Variable) -> Vec<(i32,i8)> {
        self.plan.checks.iter().flatten().map(|&node| &self.clause.nodes[node]).filter_map(|node| {
            let IrNode::Comparison(c) = node else { return None };
            let mut comparison = match c.op {
                ConstraintOp::Eq => 0, ConstraintOp::Lt => -1, ConstraintOp::Le => -2,
                ConstraintOp::Gt => 1, ConstraintOp::Ge => 2, ConstraintOp::Ne => return None,
            };
            let other = if c.first == variable {
                match c.second { Operand::Zero => TermId::from_encoding(0), Operand::Variable(v) => self.binding[usize::from(v.0)]? }
            } else if c.second == Operand::Variable(variable) {
                comparison = -comparison;
                self.binding[usize::from(c.first.0)]?
            } else { return None };
            Some((Term::decode_number(other),comparison))
        }).collect()
    }

    fn range_values(&self, owner: &Arc<Index>, at: IndexNode<'_>, groups: Vec<Vec<(Option<Edges>,i32,i8)>>,
        budget: &mut Budget<'_>) -> Result<Option<Vec<TermId>>,ReachedBound> {
        let mut runs = Vec::new();
        for group in groups {
            let mut values = Vec::new();
            for (edges,reference,comparison) in group {
                let index = self.memo.distance_index(owner, at.values(), edges, budget)?;
                values.extend(range(&index.rows,reference,comparison).iter().map(|&(_,value)|value));
            }
            values.sort_unstable_by_key(|value|value.encoding());
            values.dedup();
            if values.is_empty() { return Ok(Some(values)); }
            runs.push(values);
        }
        if runs.is_empty() { return Ok(None); }
        runs.sort_by_key(Vec::len);
        intersect_runs(runs.iter().map(Vec::as_slice).collect(),budget).map(Some)
    }
}

fn range(rows: &[(i32, TermId)], reference: i32, comparison: i8) -> &[(i32, TermId)] {
    let below = rows.partition_point(|&(distance, _)| distance < reference);
    let through = rows.partition_point(|&(distance, _)| distance <= reference);
    match comparison {
        -2 => &rows[..through],
        -1 => &rows[..below],
        0 => &rows[below..through],
        1 => &rows[through..],
        2 => &rows[below..],
        _ => unreachable!("a distance comparison"),
    }
}
