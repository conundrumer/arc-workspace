//! Connectivity, Quotient, Propagation, Enclosure and Flood: union-find,
//! flood fill, and forward chaining to a fixpoint.
//!
//! An Ident that `class`, `component` or `enclosed` gives is interned by
//! the set of members it labels, so no output reads the order in which a
//! construction met the members, as `docs/engine/equivariance.md#free-choices`
//! gives.

use std::hash::Hash;

use arclog::algebra::boxes::compose;
use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::eval::join::Batch;
use arclog::hash::{StableHashMap, StableHashSet};
use arclog::program::ColumnName;
use arclog::relations::{Row, RowSet};
use arclog::terms::{Content, Margins, MemberSet, Term, TermId};
use arclog::types::ValueType;

/// The connected components of the group's nodes under its steps, the
/// cardinals by default.
#[derive(Clone, Copy, Debug, Default)]
pub struct Connectivity;

impl Construction for Connectivity {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [node, step] = group.inputs else { panic!("Connectivity's inputs `node` and `step`") };
        let mut work = Batch::default();
        let (classes, adjacent) = components(&column(node), &column(step), &mut work, context)?;
        let component = identified(context, &group.types[0], &classes);
        let mut connected = RowSet::empty(2);
        for members in &classes {
            for p in members {
                for q in members {
                    connected.insert(p.iter().chain(q.iter()).copied().collect());
                }
            }
            work.count(context.budget, members.len() as u64 * members.len() as u64)?;
        }
        rows_held(context, [&component, &connected, &adjacent])?;
        Ok(GroupOutputs { outputs: Box::new([component, connected, adjacent]) })
    }
}

/// One class id per equivalence class of the closure of `equivalent` and
/// `edge`, each id the Ident of its class, so no member is a
/// representative.
#[derive(Clone, Copy, Debug, Default)]
pub struct Quotient;

impl Construction for Quotient {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [equivalent, edge] = group.inputs else { panic!("Quotient's inputs `equivalent` and `edge`") };
        let width = group.types[0].len() / 2;
        let mut work = Batch::default();
        let mut classes = UnionFind::default();
        for row in equivalent.rows().chain(edge.rows()) {
            let (a, b) = row.split_at(width);
            classes.union(Row::from(a), Row::from(b));
            work.count(context.budget, 1)?;
        }
        let class = identified(context, &group.types[0][..width], &classes.classes());
        rows_held(context, [&class])?;
        Ok(GroupOutputs { outputs: Box::new([class]) })
    }
}

/// Forward chaining from the sources over `edge` and `join` to a
/// fixpoint.
#[derive(Clone, Copy, Debug, Default)]
pub struct Propagation;

impl Construction for Propagation {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [source, edge, join] = group.inputs else { panic!("Propagation's inputs `source`, `edge` and `join`") };
        let width = group.types[0].len();
        let node = |row: &[TermId], at: usize| Row::from(&row[at * width..(at + 1) * width]);
        let mut heads: StableHashMap<Row, Vec<Row>> = StableHashMap::default();
        for row in edge.rows() {
            heads.entry(node(row, 0)).or_default().push(node(row, 1));
        }
        // Each join under each of its tails, with its other tail and its head.
        let mut joins: StableHashMap<Row, Vec<(Row, Row)>> = StableHashMap::default();
        for row in join.rows() {
            let (a, b, c) = (node(row, 0), node(row, 1), node(row, 2));
            joins.entry(a.clone()).or_default().push((b.clone(), c.clone()));
            joins.entry(b).or_default().push((a, c));
        }
        let mut work = Batch::default();
        let mut reached: StableHashSet<Row> = StableHashSet::default();
        let mut pending: Vec<Row> = source.rows().map(Row::from).collect();
        while let Some(n) = pending.pop() {
            if !reached.insert(n.clone()) {
                continue;
            }
            for b in heads.get(&n).into_iter().flatten() {
                pending.push(b.clone());
            }
            for (other, c) in joins.get(&n).into_iter().flatten() {
                if reached.contains(other) {
                    pending.push(c.clone());
                }
            }
            let tried = heads.get(&n).map_or(0, Vec::len) + joins.get(&n).map_or(0, Vec::len);
            work.count(context.budget, 1 + tried as u64)?;
        }
        let mut rows = RowSet::empty(width as u16);
        for n in reached {
            rows.insert(n);
        }
        rows_held(context, [&rows])?;
        Ok(GroupOutputs { outputs: Box::new([rows]) })
    }
}

/// The parts of the group's cells that the frame's edge does not reach,
/// each under its id.
///
/// The edge's cells are those at no distance from an edge of the frame, and
/// both the walk from them and the parts take the cardinal steps, as
/// `docs/lib-spec.md#cell-instances` gives Enclosure: Flood, then
/// Connectivity, over the cell set alone.
#[derive(Clone, Copy, Debug, Default)]
pub struct Enclosure;

impl Construction for Enclosure {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [cell] = group.inputs else { panic!("Enclosure's input `cell`") };
        let cells = column(cell);
        let steps = cardinals();
        let edge = cells.iter().copied().filter(|&p| {
            let m = Term::decode_box(p);
            [m.top, m.bottom, m.left, m.right].contains(&0)
        });
        let mut work = Batch::default();
        let open = flood(&cells, edge, &steps, &mut work, context)?;
        let closed: StableHashSet<TermId> = cells.difference(&open).copied().collect();
        let (classes, _) = components(&closed, &steps, &mut work, context)?;
        let enclosed = identified(context, &group.types[0], &classes);
        rows_held(context, [&enclosed])?;
        Ok(GroupOutputs { outputs: Box::new([enclosed]) })
    }
}

/// The nodes a walk from a source reaches by steps inside the set, the
/// cardinals by default.
#[derive(Clone, Copy, Debug, Default)]
pub struct Flood;

impl Construction for Flood {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [node, source, step] = group.inputs else { panic!("Flood's inputs `node`, `source` and `step`") };
        let nodes = column(node);
        let steps = column(step);
        let mut work = Batch::default();
        let reached = flood(&nodes, column(source), &steps, &mut work, context)?;
        let mut rows = RowSet::empty(1);
        for p in reached {
            rows.insert([p].into());
        }
        rows_held(context, [&rows])?;
        Ok(GroupOutputs { outputs: Box::new([rows]) })
    }
}

/// The connected components of `nodes` under `steps`, each step taken
/// both ways, with each pair of nodes one of `steps` joins.
fn components(
    nodes: &StableHashSet<TermId>,
    steps: &StableHashSet<TermId>,
    work: &mut Batch,
    context: &mut ConstructionContext<'_, '_>,
) -> Result<(Vec<Vec<Row>>, RowSet), ReachedBound> {
    let mut classes = UnionFind::default();
    let mut adjacent = RowSet::empty(2);
    for &p in nodes {
        classes.insert(Row::from([p]));
        for q in stepped(p, steps, nodes, work, context)? {
            classes.union(Row::from([p]), Row::from([q]));
            adjacent.insert([p, q].into());
        }
    }
    Ok((classes.classes(), adjacent))
}

/// The nodes of `nodes` that a walk from each of `sources` that is a node
/// reaches by `steps`, each step to a node.
fn flood(
    nodes: &StableHashSet<TermId>,
    sources: impl IntoIterator<Item = TermId>,
    steps: &StableHashSet<TermId>,
    work: &mut Batch,
    context: &mut ConstructionContext<'_, '_>,
) -> Result<StableHashSet<TermId>, ReachedBound> {
    let mut reached = StableHashSet::default();
    let mut pending: Vec<TermId> = sources.into_iter().filter(|p| nodes.contains(p)).collect();
    while let Some(p) = pending.pop() {
        if reached.insert(p) {
            pending.extend(stepped(p, steps, nodes, work, context)?);
        }
    }
    Ok(reached)
}

/// The nodes of `nodes` that one of `steps` from `p` reaches, as `compose`
/// of `programs/lib/box.dl` gives a step: the sum of the margins.
fn stepped(
    p: TermId,
    steps: &StableHashSet<TermId>,
    nodes: &StableHashSet<TermId>,
    work: &mut Batch,
    context: &mut ConstructionContext<'_, '_>,
) -> Result<Vec<TermId>, ReachedBound> {
    work.count(context.budget, steps.len() as u64)?;
    let from = Term::decode_box(p);
    Ok(steps
        .iter()
        .filter_map(|&step| {
            let by = Term::decode_box(step);
            // A Box no term id holds is no node.
            Term::Box(compose(from, by)).encode().ok()
        })
        .filter(|q| nodes.contains(q))
        .collect())
}

/// The four cardinal steps, as `step_offset` of `programs/lib/box.dl` gives
/// them.
fn cardinals() -> StableHashSet<TermId> {
    let zero = Margins { top: 0, bottom: 0, left: 0, right: 0 };
    [
        Margins { top: -1, bottom: 1, ..zero },
        Margins { top: 1, bottom: -1, ..zero },
        Margins { left: -1, right: 1, ..zero },
        Margins { left: 1, right: -1, ..zero },
    ]
    .into_iter()
    .map(|step| Term::Box(step).encode().expect("a unit step packs"))
    .collect()
}

/// The values of `rows`, rows of one column.
fn column(rows: &RowSet) -> StableHashSet<TermId> {
    rows.rows().map(|row| row[0]).collect()
}

/// The type of a member whose positions have `types`: the one type, or a
/// record of one field per position.
fn member_type(types: &[ValueType]) -> ValueType {
    match types {
        [ty] => ty.clone(),
        fields => ValueType::Record(
            fields.iter().enumerate().map(|(slot, ty)| (ColumnName::Slot(slot as u32), ty.clone())).collect(),
        ),
    }
}

/// The rows of each member of `classes`, sets of members whose positions
/// have `types`, each row the member then the term id of the Ident of its
/// class's set.
fn identified(context: &ConstructionContext<'_, '_>, types: &[ValueType], classes: &[Vec<Row>]) -> RowSet {
    let ty = member_type(types);
    let mut table = context.session.intern.write().expect("an intern table that no panic poisoned");
    let mut rows = RowSet::empty(types.len() as u16 + 1);
    for members in classes {
        let content = Content::Set(MemberSet::new(ty.clone(), members.iter().cloned()));
        let id = Term::Ident(table.intern(content)).encode().expect("an Ident has a term id");
        for member in members {
            rows.insert(member.iter().copied().chain([id]).collect());
        }
    }
    rows
}

/// Counts the rows of `outputs` against the budget.
fn rows_held<const N: usize>(
    context: &mut ConstructionContext<'_, '_>,
    outputs: [&RowSet; N],
) -> Result<(), ReachedBound> {
    context.budget.charge_rows(outputs.iter().map(|rows| rows.len() as u64).sum())
}

/// The classes of a union-find over the elements it is given.
struct UnionFind<T> {
    index: StableHashMap<T, usize>,
    elements: Vec<T>,
    parent: Vec<usize>,
}

impl<T> Default for UnionFind<T> {
    fn default() -> Self {
        UnionFind { index: StableHashMap::default(), elements: Vec::new(), parent: Vec::new() }
    }
}

impl<T: Hash + Eq + Clone> UnionFind<T> {
    /// The index of `element`, which takes a class of its own on first
    /// use.
    fn insert(&mut self, element: T) -> usize {
        if let Some(&at) = self.index.get(&element) {
            return at;
        }
        let at = self.elements.len();
        self.index.insert(element.clone(), at);
        self.elements.push(element);
        self.parent.push(at);
        at
    }

    /// The root of the class of the element at `at`.
    fn find(&mut self, mut at: usize) -> usize {
        while self.parent[at] != at {
            self.parent[at] = self.parent[self.parent[at]];
            at = self.parent[at];
        }
        at
    }

    /// Merges the classes of `a` and `b`.
    fn union(&mut self, a: T, b: T) {
        let (a, b) = (self.insert(a), self.insert(b));
        let (a, b) = (self.find(a), self.find(b));
        self.parent[a] = b;
    }

    /// The members of each class.
    fn classes(mut self) -> Vec<Vec<T>> {
        let mut by_root: StableHashMap<usize, Vec<T>> = StableHashMap::default();
        for at in 0..self.elements.len() {
            let root = self.find(at);
            by_root.entry(root).or_default().push(self.elements[at].clone());
        }
        by_root.into_values().collect()
    }
}
