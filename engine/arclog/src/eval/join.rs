//! Generic join over a clause's IR: it binds one variable at a time, in the
//! clause's variable order, by intersecting the atoms that hold it, and
//! counts its work and its rows against the caps per batch of bindings.
//!
//! An algebra relation is evaluated at the point in the order where one of
//! its modes is satisfied, and its outputs are variables that later atoms
//! join on through an index. Where two algebra outputs join on a computed
//! key, the join builds a [`KeyIndex`] on the key over the smaller side.

use std::sync::Arc;

use super::ir::{Argument, ClauseIr, Comparison, Filter, IrNode, Operand, Variable};
use super::plan::{
    algebra_relation, bound_variables, mode_holds, orientation_domain, variable_order, OrientationDomain, RelationSizes,
    VariableOrder,
};
use super::{Caps, Limits, ReachedBound};
use crate::hash::StableHashMap;
use crate::program::ConstraintOp;
use crate::registry::Registry;
use crate::relations::{ColumnIndex, ColumnOrder, Index, Relation, RelationPart, Row, RowSet};
use crate::session::TaskSession;
use crate::terms::{Constant, Number, Term, TermId};
use crate::types::ValueType;

/// The bindings a join tries between two charges of its budget.
const BATCH: u64 = 1024;

/// The counts of one evaluation against its caps and its other bounds: the
/// bindings tried and the rows held. A native construction counts its own
/// bindings and rows through the same counter.
#[derive(Debug)]
pub struct Budget<'a> {
    limits: &'a Limits,
    session: &'a TaskSession,
    work: u64,
    rows: u64,
}

impl<'a> Budget<'a> {
    /// A budget with no work and no rows counted, under `limits`, in
    /// `session`.
    pub fn new(limits: &'a Limits, session: &'a TaskSession) -> Self {
        Budget { limits, session, work: 0, rows: 0 }
    }

    pub fn caps(&self) -> Caps {
        self.limits.caps
    }

    /// Counts a batch of `bindings` tried, and checks the caps, the
    /// session's byte bound, the deadline and the cancellation.
    pub fn charge_work(&mut self, bindings: u64) -> Result<(), ReachedBound> {
        self.work += bindings;
        let caps = self.limits.caps;
        if self.work > caps.work {
            return Err(ReachedBound::Work { cap: caps.work });
        }
        if self.rows > caps.rows {
            return Err(ReachedBound::Rows { cap: caps.rows });
        }
        self.session.within_bound().map_err(ReachedBound::SessionBytes)?;
        if self.limits.deadline.is_some_and(|deadline| std::time::Instant::now() >= deadline) {
            return Err(ReachedBound::Deadline);
        }
        if self.limits.cancellation.is_cancelled() {
            return Err(ReachedBound::Cancelled);
        }
        Ok(())
    }

    /// Counts `rows` more rows held, and checks the row cap.
    pub fn charge_rows(&mut self, rows: u64) -> Result<(), ReachedBound> {
        self.rows += rows;
        let cap = self.limits.caps.rows;
        if self.rows > cap { Err(ReachedBound::Rows { cap }) } else { Ok(()) }
    }
}

/// What each node of a clause reads, by the node's index in
/// [`ClauseIr::nodes`].
#[derive(Clone, Debug)]
pub struct JoinInputs(pub Box<[NodeInput]>);

/// What one node of a clause reads.
#[derive(Clone, Debug)]
pub enum NodeInput {
    /// No relation with rows: a comparison's, or an algebra relation's atom.
    Unread,
    /// The relation of an atom.
    Relation(Arc<Relation>),
    /// The inputs of the node's own clauses: a filter's body, an `IF`'s
    /// test, then and else, or an `OR`'s branches, in the node's order.
    Clauses(Box<[JoinInputs]>),
}

/// The relation of `clause`: each binding of its variables that every node
/// passes, held as its parts, one per connected set of its variables, by
/// generic join in `order`.
pub fn join(
    clause: &ClauseIr,
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    let components = components(clause);
    let mut parts = Vec::new();
    for component in &components {
        let columns: Vec<ColumnIndex> = (0..clause.columns.len())
            .filter(|&i| component.variables.contains(&clause.columns[i]))
            .map(|i| ColumnIndex(i as u16))
            .collect();
        let projected: Vec<Variable> = columns.iter().map(|c| clause.columns[usize::from(c.0)]).collect();
        let order: Vec<Variable> = order.0.iter().copied().filter(|v| component.variables.contains(v)).collect();
        let rows = Search::new(clause, &component.nodes, order, inputs, registry).run(&projected, budget)?;
        if !columns.is_empty() || rows.is_empty() {
            parts.push(RelationPart { columns: columns.into(), rows });
        }
    }
    for (i, column) in clause.columns.iter().enumerate() {
        assert!(components.iter().any(|c| c.variables.contains(column)), "column {i} of a clause is bound by a node of its body");
    }
    Ok(Relation::from_parts(clause.columns.len() as u16, parts.into()))
}

/// Calls `visit` on each row of `relation`, the product of its parts, in an
/// order of encodings and no order of the content.
pub fn each_row(relation: &Relation, visit: &mut dyn FnMut(&[TermId])) {
    fn product(parts: &[RelationPart], row: &mut [TermId], visit: &mut dyn FnMut(&[TermId])) {
        let Some((part, rest)) = parts.split_first() else {
            visit(row);
            return;
        };
        for part_row in part.rows.rows() {
            for (column, &value) in part.columns.iter().zip(part_row) {
                row[usize::from(column.0)] = value;
            }
            product(rest, row, visit);
        }
    }
    let mut row = vec![TermId::from_encoding(0); usize::from(relation.arity())];
    product(relation.parts(), &mut row, visit);
}

/// The relation of one part that holds `rows`.
pub fn one_part(rows: RowSet) -> Relation {
    let arity = rows.arity();
    let columns = (0..arity).map(ColumnIndex).collect();
    Relation::from_parts(arity, Box::new([RelationPart { columns, rows }]))
}

/// The sizes of the relations of `inputs`, for [`variable_order`].
pub fn sizes(inputs: &JoinInputs) -> RelationSizes {
    RelationSizes(
        inputs
            .0
            .iter()
            .map(|input| match input {
                NodeInput::Relation(relation) => Some(relation.len()),
                NodeInput::Unread | NodeInput::Clauses(_) => None,
            })
            .collect(),
    )
}

/// A connected set of a clause's variables, with the nodes that hold them;
/// a node with no variable is a set of its own.
struct Component {
    variables: Vec<Variable>,
    nodes: Vec<usize>,
}

/// The variables a node joins in its clause: those it binds, and the outer
/// variables of a filter.
fn node_variables(node: &IrNode) -> Vec<Variable> {
    match node {
        IrNode::Not(filter) | IrNode::Counterexample(filter) => filter.outer.to_vec(),
        IrNode::If(conditional) => conditional.test.outer.to_vec(),
        _ => bound_variables(node),
    }
}

/// The connected sets of `clause`'s variables, two variables connected
/// where a node holds both, in the order of their least variables.
fn components(clause: &ClauseIr) -> Vec<Component> {
    let mut parent: Vec<usize> = (0..clause.variables.len()).collect();
    fn root(parent: &mut [usize], v: usize) -> usize {
        let mut r = v;
        while parent[r] != r {
            r = parent[r];
        }
        parent[v] = r;
        r
    }
    let variables: Vec<Vec<Variable>> = clause.nodes.iter().map(node_variables).collect();
    for held in &variables {
        for pair in held.windows(2) {
            let (a, b) = (root(&mut parent, usize::from(pair[0].0)), root(&mut parent, usize::from(pair[1].0)));
            parent[a.max(b)] = a.min(b);
        }
    }
    let mut by_root: std::collections::BTreeMap<usize, Component> = std::collections::BTreeMap::new();
    let mut alone = Vec::new();
    for (node, held) in variables.iter().enumerate() {
        let Some(first) = held.first() else {
            alone.push(Component { variables: Vec::new(), nodes: vec![node] });
            continue;
        };
        let r = root(&mut parent, usize::from(first.0));
        let component = by_root.entry(r).or_insert_with(|| Component { variables: Vec::new(), nodes: Vec::new() });
        component.nodes.push(node);
        for v in held {
            if !component.variables.contains(v) {
                component.variables.push(*v);
            }
        }
    }
    by_root.into_values().chain(alone).collect()
}

/// An atom's trie in the join's order: its relation's index over the
/// atom's columns, a term's column first, then each variable's in the order
/// it is bound.
struct AtomTrie {
    index: Arc<Index>,
    levels: Vec<Argument>,
}

/// The generic join of one connected set of a clause's nodes.
struct Search<'c> {
    clause: &'c ClauseIr,
    registry: &'c Registry,
    inputs: &'c JoinInputs,
    order: Vec<Variable>,
    atoms: Vec<AtomTrie>,
    /// The nodes checked once the variable at each rank is bound, and, last,
    /// the nodes with no variable.
    checks: Vec<Vec<usize>>,
    /// The lib atoms that hold each variable, by the variable's index.
    libs: Vec<Vec<usize>>,
    /// The variable order of each filter's body, by its node.
    filter_orders: StableHashMap<usize, VariableOrder>,
    binding: Vec<Option<TermId>>,
    tried: u64,
}

impl<'c> Search<'c> {
    fn new(clause: &'c ClauseIr, nodes: &[usize], order: Vec<Variable>, inputs: &'c JoinInputs, registry: &'c Registry) -> Self {
        let mut rank = vec![usize::MAX; clause.variables.len()];
        for (r, v) in order.iter().enumerate() {
            rank[usize::from(v.0)] = r;
        }
        let mut atoms = Vec::new();
        let mut checks = vec![Vec::new(); order.len() + 1];
        let mut libs = vec![Vec::new(); clause.variables.len()];
        let mut filter_orders = StableHashMap::default();
        for &node in nodes {
            let held = node_variables(&clause.nodes[node]);
            let last = held.iter().map(|v| rank[usize::from(v.0)]).max().unwrap_or(order.len());
            match &clause.nodes[node] {
                IrNode::Atom(atom) => {
                    let NodeInput::Relation(relation) = &inputs.0[node] else { panic!("the relation of each atom") };
                    let mut columns: Vec<(ColumnIndex, Argument)> = atom.arguments.0.to_vec();
                    columns.sort_by_key(|(column, argument)| match argument {
                        Argument::Term(_) => (0, column.0 as usize),
                        Argument::Variable(v) => (1 + rank[usize::from(v.0)], column.0 as usize),
                    });
                    let index = relation.index(&ColumnOrder(columns.iter().map(|(c, _)| *c).collect()));
                    atoms.push(AtomTrie { index, levels: columns.into_iter().map(|(_, a)| a).collect() });
                }
                IrNode::Lib(atom) => {
                    for v in super::plan::variables_of(&atom.arguments) {
                        libs[usize::from(v.0)].push(node);
                    }
                    checks[last].push(node);
                }
                IrNode::Not(filter) | IrNode::Counterexample(filter) => {
                    let NodeInput::Clauses(bodies) = &inputs.0[node] else { panic!("the inputs of each filter's body") };
                    filter_orders.insert(node, variable_order(&filter.body, &sizes(&bodies[0])));
                    checks[last].push(node);
                }
                IrNode::Comparison(_) | IrNode::If(_) | IrNode::Or(_) => checks[last].push(node),
            }
        }
        Search { clause, registry, inputs, order, atoms, checks, libs, filter_orders, binding: vec![None; clause.variables.len()], tried: 0 }
    }

    /// The rows of `projected` over each binding that passes every node.
    fn run(mut self, projected: &[Variable], budget: &mut Budget<'_>) -> Result<RowSet, ReachedBound> {
        let mut rows = RowSet::empty(projected.len() as u16);
        let atoms = std::mem::take(&mut self.atoms);
        let mut cursors: Vec<(&Index, usize)> = Vec::with_capacity(atoms.len());
        for atom in &atoms {
            let mut at: &Index = &atom.index;
            let mut depth = 0;
            while let Some(Argument::Term(term)) = atom.levels.get(depth) {
                match at.child(*term) {
                    Some(child) => at = child,
                    None => return Ok(rows),
                }
                depth += 1;
            }
            cursors.push((at, depth));
        }
        let unbound = self.checks.len() - 1;
        if self.passes(unbound, budget)? {
            self.step(0, &atoms, &mut cursors, projected, &mut rows, budget)?;
        }
        budget.charge_work(self.tried % BATCH)?;
        Ok(rows)
    }

    fn step<'t>(
        &mut self,
        rank: usize,
        atoms: &'t [AtomTrie],
        cursors: &mut Vec<(&'t Index, usize)>,
        projected: &[Variable],
        rows: &mut RowSet,
        budget: &mut Budget<'_>,
    ) -> Result<(), ReachedBound> {
        let Some(&variable) = self.order.get(rank) else {
            let row: Row = projected.iter().map(|v| self.binding[usize::from(v.0)].expect("a bound column")).collect();
            if rows.insert(row) {
                budget.charge_rows(1)?;
            }
            return Ok(());
        };
        let at = |atom: &AtomTrie, depth: usize| matches!(atom.levels.get(depth), Some(Argument::Variable(v)) if *v == variable);
        let sources: Vec<usize> = (0..atoms.len()).filter(|&a| at(&atoms[a], cursors[a].1)).collect();
        let candidates: Vec<TermId> = if let Some(value) = self.equal_value(variable) {
            vec![value]
        } else if let Some(&smallest) = sources.iter().min_by_key(|&&a| (cursors[a].0.len(), a)) {
            cursors[smallest].0.entries().map(|(value, _)| value).collect()
        } else if let Some(values) = self.lib_values(variable)? {
            values
        } else {
            let ty = &self.clause.variables[usize::from(variable.0)].ty;
            assert!(orientation_domain(ty).is_some(), "a variable of the order that a node of the clause binds");
            domain(self.registry, ty)
        };
        for value in candidates {
            self.tried += 1;
            if self.tried % BATCH == 0 {
                budget.charge_work(BATCH)?;
            }
            let saved: Vec<(usize, (&'t Index, usize))> = sources.iter().map(|&a| (a, cursors[a])).collect();
            let mut held = true;
            for &a in &sources {
                while held && at(&atoms[a], cursors[a].1) {
                    match cursors[a].0.child(value) {
                        Some(child) => cursors[a] = (child, cursors[a].1 + 1),
                        None => held = false,
                    }
                }
            }
            self.binding[usize::from(variable.0)] = Some(value);
            if held && self.passes(rank, budget)? {
                self.step(rank + 1, atoms, cursors, projected, rows, budget)?;
            }
            self.binding[usize::from(variable.0)] = None;
            for (a, cursor) in saved {
                cursors[a] = cursor;
            }
        }
        Ok(())
    }

    /// The value an `=` gives `variable` from a bound variable or `0`.
    fn equal_value(&self, variable: Variable) -> Option<TermId> {
        self.checks.iter().flatten().find_map(|&node| match &self.clause.nodes[node] {
            IrNode::Comparison(Comparison { op: ConstraintOp::Eq, first, second, .. }) => match (*first == variable, second) {
                (true, Operand::Zero) => Some(TermId::from_encoding(0)),
                (true, Operand::Variable(other)) => self.binding[usize::from(other.0)],
                (false, Operand::Variable(other)) if *other == variable => self.binding[usize::from(first.0)],
                _ => None,
            },
            _ => None,
        })
    }

    /// The values that a lib atom whose bound columns satisfy one of its
    /// modes gives `variable`, from the first such atom, or `None` where no
    /// lib atom that holds it is satisfied.
    fn lib_values(&self, variable: Variable) -> Result<Option<Vec<TermId>>, ReachedBound> {
        let bound: Vec<bool> = self.binding.iter().map(Option::is_some).collect();
        for &node in &self.libs[usize::from(variable.0)] {
            let IrNode::Lib(atom) = &self.clause.nodes[node] else { unreachable!("a lib atom") };
            let relation = algebra_relation(self.registry, &atom.relation);
            if !mode_holds(relation, &atom.arguments, self.clause, &bound) {
                continue;
            }
            let columns: Vec<ColumnIndex> = atom
                .arguments
                .0
                .iter()
                .filter(|(_, argument)| *argument == Argument::Variable(variable))
                .map(|(column, _)| *column)
                .collect();
            let mut values = Vec::new();
            self.evaluate_lib(node, &mut |row| {
                let value = row[usize::from(columns[0].0)];
                if columns.iter().all(|c| row[usize::from(c.0)] == value) {
                    values.push(value);
                }
            })?;
            values.sort_by_key(|value| value.encoding());
            values.dedup();
            return Ok(Some(values));
        }
        Ok(None)
    }

    /// Calls `emit` on each row of the lib atom at `node` that agrees with
    /// the atom's terms and bound variables.
    fn evaluate_lib(&self, node: usize, emit: &mut dyn FnMut(&[TermId])) -> Result<(), ReachedBound> {
        let IrNode::Lib(atom) = &self.clause.nodes[node] else { unreachable!("a lib atom") };
        let relation = algebra_relation(self.registry, &atom.relation);
        let mut bound = vec![None; relation.columns.len()];
        for (column, argument) in atom.arguments.0.iter() {
            bound[usize::from(column.0)] = match argument {
                Argument::Term(term) => Some(*term),
                Argument::Variable(v) => self.binding[usize::from(v.0)],
            };
        }
        let algebra = crate::algebra::algebra(&atom.relation).expect("a native form of each algebra relation");
        algebra.evaluate(&bound, self.registry, &mut |row| {
            if bound.iter().zip(row).all(|(b, value)| b.is_none_or(|b| b == *value)) {
                emit(row);
            }
        })
        .map_err(ReachedBound::Margin)
    }

    /// Whether the binding passes each node checked at `rank`.
    fn passes(&self, rank: usize, budget: &mut Budget<'_>) -> Result<bool, ReachedBound> {
        for &node in &self.checks[rank] {
            let holds = match &self.clause.nodes[node] {
                IrNode::Comparison(comparison) => self.compare(comparison),
                IrNode::Lib(_) => {
                    let mut found = false;
                    self.evaluate_lib(node, &mut |_| found = true)?;
                    found
                }
                IrNode::Not(filter) | IrNode::Counterexample(filter) => !self.probe(node, filter, budget)?,
                IrNode::If(_) | IrNode::Or(_) => todo!(),
                IrNode::Atom(_) => unreachable!("an atom is joined, not checked"),
            };
            if !holds {
                return Ok(false);
            }
        }
        Ok(true)
    }

    /// Whether `filter`, the filter of the node at `node`, holds a binding
    /// at the bound values of its outer variables.
    fn probe(&self, node: usize, filter: &Filter, budget: &mut Budget<'_>) -> Result<bool, ReachedBound> {
        let outer: Vec<TermId> = filter.outer.iter().map(|v| self.binding[usize::from(v.0)].expect("a bound outer variable")).collect();
        let NodeInput::Clauses(bodies) = &self.inputs.0[node] else { unreachable!("the inputs of a filter's body") };
        super::filters::probe(filter, &outer, &self.filter_orders[&node], &bodies[0], self.registry, budget)
    }

    /// Whether the bound operands of `comparison` satisfy it. An order
    /// compares numbers, the one type the checker admits it on.
    fn compare(&self, comparison: &Comparison) -> bool {
        let first = self.binding[usize::from(comparison.first.0)].expect("a bound operand");
        let second = match comparison.second {
            Operand::Variable(v) => self.binding[usize::from(v.0)].expect("a bound operand"),
            Operand::Zero => TermId::from_encoding(0),
        };
        let number = |id: TermId| match Term::decode(id, &ValueType::Number) {
            Term::Number(Number(n)) => n,
            _ => unreachable!("a number decodes to a number"),
        };
        match comparison.op {
            ConstraintOp::Eq => first == second,
            ConstraintOp::Ne => first != second,
            ConstraintOp::Lt => number(first) < number(second),
            ConstraintOp::Le => number(first) <= number(second),
            ConstraintOp::Gt => number(first) > number(second),
            ConstraintOp::Ge => number(first) >= number(second),
        }
    }
}

/// The term id of each constant of the orientation type `ty`.
fn domain(registry: &Registry, ty: &ValueType) -> Vec<TermId> {
    let encode = |constant| Term::Constant(Constant::Orientation(constant)).encode().expect("a constant's term id");
    match orientation_domain(ty).expect("an orientation type") {
        OrientationDomain::C4 => registry.c4_constants().each().map(encode).collect(),
        OrientationDomain::Types(types) => types.iter().flat_map(|&t| registry.constants_of(t).each()).map(encode).collect(),
    }
}

/// A hash index on a key computed by an algebra relation: each key's rows
/// of one side of the join.
#[derive(Debug, Default)]
pub struct KeyIndex {
    rows: StableHashMap<Box<[TermId]>, Vec<Row>>,
}

impl KeyIndex {
    /// The index of `rows` on the key that `key` computes from each row.
    pub fn build(rows: impl Iterator<Item = Row>, key: impl Fn(&[TermId]) -> Box<[TermId]>) -> Self {
        let mut index = KeyIndex::default();
        for row in rows {
            index.rows.entry(key(&row)).or_default().push(row);
        }
        index
    }

    /// The rows whose key is `key`.
    pub fn get(&self, key: &[TermId]) -> &[Row] {
        self.rows.get(key).map_or(&[], Vec::as_slice)
    }
}
