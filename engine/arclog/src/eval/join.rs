//! Generic join over a clause's IR: it binds one variable at a time, in the
//! clause's variable order, by intersecting the atoms that hold it, and
//! counts its work and its rows against the caps per batch of bindings. A
//! body is joined part by part, as [`parts`] gives its parts, and its
//! relation is their product.
//!
//! An algebra relation is evaluated at the point in the order where one of
//! its modes is satisfied, and its outputs are variables that later atoms
//! join on through an index.
//!
//! The evaluation of one clause or part serves a lib atom, a filter and a
//! branch at bound values it has evaluated them at from its [`SearchMemo`],
//! with the counts of their evaluation, and builds the plan of each nested
//! clause once per set of bound variables.

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::Arc;

use super::ir::{Argument, Arguments, ClauseIr, Comparison, Filter, IrNode, Operand, Variable};
use super::plan::{
    algebra_relation, bound_variables, mode_holds, variable_order, RelationSizes,
    VariableOrder,
};
use super::{Caps, Limits, ReachedBound};
use crate::algebra::geometry::domain;
use crate::hash::StableHashMap;
use crate::program::ConstraintOp;
use crate::registry::{LibName, Registry};
use crate::relations::{ColumnIndex, ColumnOrder, Index, Relation, RelationPart, Row, RowSet};
use crate::session::{Counts, TaskSession};
use crate::terms::{Term, TermId};
use crate::types::ValueType;

/// The bindings a [`Batch`] counts before it charges its budget.
const BATCH: u64 = 1024;

/// The counts of one evaluation against its caps and its other bounds: the
/// bindings tried and the rows held. A native construction counts its own
/// bindings and rows through the same counter.
#[derive(Debug)]
pub struct Budget<'a> {
    limits: &'a Limits,
    session: &'a TaskSession,
    bindings: u64,
    rows: u64,
    /// The charges made since [`Budget::log`] began a log, in order.
    log: Option<Vec<Charge>>,
}

/// A charge to a [`Budget`]: bindings tried, or rows held.
#[derive(Clone, Copy, Debug)]
enum Charge {
    Work(u64),
    Rows(u64),
}

impl<'a> Budget<'a> {
    /// A budget with no work and no rows counted, under `limits` and the
    /// caps of `session`.
    pub fn new(limits: &'a Limits, session: &'a TaskSession) -> Self {
        Budget { limits, session, bindings: 0, rows: 0, log: None }
    }

    /// The caps of the session.
    pub fn caps(&self) -> Caps {
        self.session.caps
    }

    /// Counts a batch of `bindings` tried, and checks the caps, the
    /// session's byte bound, the deadline and the cancellation.
    pub fn charge_work(&mut self, bindings: u64) -> Result<(), ReachedBound> {
        if let Some(log) = &mut self.log {
            match log.last_mut() {
                Some(Charge::Work(last)) => *last += bindings,
                _ => log.push(Charge::Work(bindings)),
            }
        }
        self.bindings += bindings;
        let caps = self.session.caps;
        if self.bindings > caps.bindings {
            return Err(ReachedBound::Bindings { cap: caps.bindings });
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
        if let Some(log) = &mut self.log {
            match log.last_mut() {
                Some(Charge::Rows(last)) => *last += rows,
                _ => log.push(Charge::Rows(rows)),
            }
        }
        self.rows += rows;
        let cap = self.session.caps.rows;
        if self.rows > cap { Err(ReachedBound::Rows { cap }) } else { Ok(()) }
    }

    /// Runs `evaluate` and gives its result with the charges it made, in
    /// order, so that [`Budget::replay`] charges them again as they were
    /// made. The charges also stand in the log of an enclosing call.
    fn logged<T>(&mut self, evaluate: impl FnOnce(&mut Self) -> Result<T, ReachedBound>) -> Result<(T, Charges), ReachedBound> {
        let outer = self.log.replace(Vec::new());
        let result = evaluate(self);
        let inner = std::mem::replace(&mut self.log, outer).expect("the log this call began");
        if let Some(outer) = &mut self.log {
            outer.extend_from_slice(&inner);
        }
        Ok((result?, inner.into()))
    }

    /// Charges `charges` in order, as they were made.
    fn replay(&mut self, charges: &Charges) -> Result<(), ReachedBound> {
        if charges.is_empty() {
            return self.charge_work(0);
        }
        for charge in charges.iter() {
            match *charge {
                Charge::Work(bindings) => self.charge_work(bindings)?,
                Charge::Rows(rows) => self.charge_rows(rows)?,
            }
        }
        Ok(())
    }

    /// Records the budget's counts in its session, as
    /// [`TaskSession::record_counts`] gives.
    pub fn record(&self) {
        self.session.record_counts(Counts { bindings: self.bindings, rows: self.rows });
    }
}

/// The bindings one search has tried and not yet charged to its budget.
/// Each search holds its own, so no count passes from one join or
/// construction to the next.
#[derive(Debug, Default)]
pub struct Batch {
    pending: u64,
}

impl Batch {
    /// Counts `bindings` more tried, and charges `budget` with the whole
    /// count once it reaches a batch.
    pub fn count(&mut self, budget: &mut Budget<'_>, bindings: u64) -> Result<(), ReachedBound> {
        self.pending += bindings;
        if self.pending >= BATCH {
            budget.charge_work(std::mem::take(&mut self.pending))?;
        }
        Ok(())
    }

    /// Charges `budget` with the count not yet charged, at the end of the
    /// search.
    pub fn finish(&mut self, budget: &mut Budget<'_>) -> Result<(), ReachedBound> {
        budget.charge_work(std::mem::take(&mut self.pending))
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
    /// The inputs of the node's own clauses: a filter's body, or a union's
    /// branches, in the node's order.
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
    join_at(clause, order, inputs, registry, &[], budget)
}

/// The relation of `clause` as [`join`] gives it, at the values `bound`
/// gives some of its variables before the search: the join of the rest of
/// `order`.
///
/// Once every variable left in the order is a variable that no column
/// holds, the first binding that passes ends the search over them, and the
/// search visits their values in their order as terms. At a variable of
/// type Ident, whose order as terms is the order of interning, the search
/// tries every value, so the work it counts does not depend on that order.
pub fn join_at(
    clause: &ClauseIr,
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    bound: &[(Variable, TermId)],
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    join_in(&SearchMemo::default(), clause, order, inputs, registry, bound, budget)
}

/// The relation of `clause` as [`join_at`] gives it, in the evaluation whose
/// memo is `memo`.
pub fn join_in(
    memo: &SearchMemo,
    clause: &ClauseIr,
    order: &VariableOrder,
    inputs: &JoinInputs,
    registry: &crate::registry::Registry,
    bound: &[(Variable, TermId)],
    budget: &mut Budget<'_>,
) -> Result<Relation, ReachedBound> {
    let plan = memo.plan(clause, order, inputs, bound);
    let mut found = Vec::new();
    for part in &plan.parts {
        let rows = Search::new(clause, &part.plan, inputs, registry, memo, bound).run(&part.projected, budget)?;
        found.push(RelationPart { columns: part.columns.clone().into(), rows });
    }
    Ok(product(clause, found))
}

/// The relation of `clause` whose parts are `parts`: their product. A part
/// that holds no column is left out where it holds a row, and where it holds
/// none it makes the relation empty.
pub fn product(clause: &ClauseIr, parts: Vec<RelationPart>) -> Relation {
    let parts: Vec<RelationPart> = parts.into_iter().filter(|part| !part.columns.is_empty() || part.rows.is_empty()).collect();
    Relation::from_parts(clause.columns.len() as u16, parts.into())
}

/// The rows of `columns`, columns of `clause`, over each binding of the
/// variables of `order` that passes every node of `nodes` and agrees with a
/// row of each relation of `tries`, by generic join in `order`, at the
/// values `bound` gives some of the clause's variables. A relation of
/// `tries` is read as an atom over its arguments.
#[allow(clippy::too_many_arguments)]
pub fn search(
    clause: &ClauseIr,
    nodes: &[usize],
    tries: &[(Arc<Relation>, Arguments)],
    order: Vec<Variable>,
    bound: &[(Variable, TermId)],
    inputs: &JoinInputs,
    registry: &Registry,
    columns: &[ColumnIndex],
    budget: &mut Budget<'_>,
) -> Result<RowSet, ReachedBound> {
    let projected: Vec<Variable> = columns.iter().map(|c| clause.columns[usize::from(c.0)]).collect();
    let variables: Vec<Variable> = bound.iter().map(|&(variable, _)| variable).collect();
    let plan = Plan::new(clause, nodes, tries, order, &variables, inputs);
    Search::new(clause, &plan, inputs, registry, &SearchMemo::default(), bound).run(&projected, budget)
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

/// The union of `relations`, of one arity: the one relation where there is
/// one, and otherwise their rows in one part.
pub fn union(mut relations: Vec<Arc<Relation>>) -> Arc<Relation> {
    if relations.len() == 1 {
        return relations.pop().expect("one relation");
    }
    let arity = relations.first().expect("a relation to unite").arity();
    let mut rows = RowSet::empty(arity);
    for relation in &relations {
        each_row(relation, &mut |row| {
            rows.insert(row.into());
        });
    }
    Arc::new(one_part(rows))
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

/// A part of a clause's body: a connected set of its nodes, two nodes
/// connected where they share a variable or stand in one group, as
/// [`parts`] gives the groups, with the variables they hold. A node with no
/// variable and no other node in its group is a part of its own.
#[derive(Clone, Debug)]
pub struct Part {
    pub variables: Vec<Variable>,
    pub nodes: Vec<usize>,
}

impl Part {
    /// The columns of `clause` that the part holds, in the clause's order.
    pub fn columns(&self, clause: &ClauseIr) -> Vec<ColumnIndex> {
        (0..clause.columns.len()).filter(|&i| self.variables.contains(&clause.columns[i])).map(|i| ColumnIndex(i as u16)).collect()
    }

    /// The variables of `order` that the part holds and `bound` leaves
    /// unbound, in their order.
    pub fn order(&self, order: &VariableOrder, bound: &[Variable]) -> Vec<Variable> {
        order.0.iter().copied().filter(|v| self.variables.contains(v) && !bound.contains(v)).collect()
    }

    /// Whether each variable that a node of `nodes` holds and the part
    /// holds too is one of the part's columns in `clause`, so that the
    /// part's rows link it to those nodes.
    pub fn links(&self, clause: &ClauseIr, nodes: &[usize]) -> bool {
        nodes
            .iter()
            .flat_map(|&node| node_variables(&clause.nodes[node]))
            .filter(|v| self.variables.contains(v))
            .all(|v| clause.columns.contains(&v))
    }
}

/// The variables a node joins in its clause: those it binds, the outer
/// variables of a filter, and the columns of a union's branches.
pub fn node_variables(node: &IrNode) -> Vec<Variable> {
    match node {
        IrNode::Not(filter) | IrNode::Counterexample(filter) => filter.outer.to_vec(),
        IrNode::Or(union) => union.branches.iter().flat_map(|branch| branch.columns.iter().copied()).collect(),
        _ => bound_variables(node),
    }
}

/// The parts of the nodes `nodes` of `clause`, the nodes to which `group`
/// gives one group standing in one part, in the order of their first nodes.
pub fn parts<G: Eq + Copy>(clause: &ClauseIr, nodes: &[usize], group: &dyn Fn(usize) -> G) -> Vec<Part> {
    let mut parent: Vec<usize> = (0..nodes.len()).collect();
    fn root(parent: &mut [usize], at: usize) -> usize {
        let mut r = at;
        while parent[r] != r {
            r = parent[r];
        }
        parent[at] = r;
        r
    }
    let variables: Vec<Vec<Variable>> = nodes.iter().map(|&node| node_variables(&clause.nodes[node])).collect();
    let mut holder: Vec<Option<usize>> = vec![None; clause.variables.len()];
    for (at, held) in variables.iter().enumerate() {
        let mut joined: Vec<usize> = held.iter().filter_map(|v| holder[usize::from(v.0)].replace(at)).collect();
        joined.extend((0..at).filter(|&other| group(nodes[other]) == group(nodes[at])).take(1));
        for other in joined {
            let (a, b) = (root(&mut parent, at), root(&mut parent, other));
            parent[a.max(b)] = a.min(b);
        }
    }
    let mut by_root: std::collections::BTreeMap<usize, Part> = std::collections::BTreeMap::new();
    for (at, held) in variables.iter().enumerate() {
        let r = root(&mut parent, at);
        let part = by_root.entry(r).or_insert_with(|| Part { variables: Vec::new(), nodes: Vec::new() });
        part.nodes.push(nodes[at]);
        for v in held {
            if !part.variables.contains(v) {
                part.variables.push(*v);
            }
        }
    }
    by_root.into_values().collect()
}

/// An atom's trie in the join's order: its relation's index over the
/// atom's columns, a term's column first, then the column of each variable
/// bound before the search, then each other variable's in the order it is
/// bound.
struct AtomTrie {
    index: Arc<Index>,
    levels: Vec<Argument>,
    /// Whether the relation holds no row, which its trie shows at a level
    /// only, and so shows for an atom that reads no column at none.
    empty: bool,
}

/// What the search of one connected set of a clause's nodes builds that
/// depends on no bound value, for one set of variables bound before the
/// search.
struct Plan {
    order: Vec<Variable>,
    atoms: Vec<AtomTrie>,
    /// The nodes checked once the variable at each rank is bound, and, last,
    /// the nodes with no variable.
    checks: Vec<Vec<usize>>,
    /// The lib atoms that hold each variable, by the variable's index.
    libs: Vec<Vec<usize>>,
    /// The variable order of each filter's body, by its node.
    filter_orders: StableHashMap<usize, VariableOrder>,
    /// The variable order of each branch of a union, by its node and the
    /// branch's index.
    branch_orders: StableHashMap<(usize, usize), VariableOrder>,
    /// The nodes of the unions.
    unions: Vec<usize>,
    /// The rank from which no variable left in the order is projected,
    /// where the early stop of [`join_at`] begins.
    stop_from: usize,
}

impl Plan {
    fn new(
        clause: &ClauseIr,
        nodes: &[usize],
        tries: &[(Arc<Relation>, Arguments)],
        order: Vec<Variable>,
        bound: &[Variable],
        inputs: &JoinInputs,
    ) -> Self {
        let mut rank = vec![usize::MAX; clause.variables.len()];
        for (r, v) in order.iter().enumerate() {
            rank[usize::from(v.0)] = r;
        }
        let trie = |relation: &Relation, arguments: &Arguments| {
            let mut columns: Vec<(ColumnIndex, Argument)> = arguments.0.iter().copied().collect();
            columns.sort_by_key(|(column, argument)| match argument {
                Argument::Variable(v) if !bound.contains(v) => (1 + rank[usize::from(v.0)], column.0 as usize),
                _ => (0, column.0 as usize),
            });
            let index = relation.index(&ColumnOrder(columns.iter().map(|(c, _)| *c).collect()));
            AtomTrie { index, levels: columns.into_iter().map(|(_, a)| a).collect(), empty: relation.is_empty() }
        };
        let mut atoms: Vec<AtomTrie> = tries.iter().map(|(relation, arguments)| trie(relation, arguments)).collect();
        let mut checks = vec![Vec::new(); order.len() + 1];
        let mut libs = vec![Vec::new(); clause.variables.len()];
        let mut filter_orders = StableHashMap::default();
        let mut branch_orders = StableHashMap::default();
        let mut unions = Vec::new();
        for &node in nodes {
            let held = node_variables(&clause.nodes[node]);
            let last = held.iter().filter(|v| !bound.contains(v)).map(|v| rank[usize::from(v.0)]).max().unwrap_or(order.len());
            match &clause.nodes[node] {
                IrNode::Atom(atom) => {
                    let NodeInput::Relation(relation) = &inputs.0[node] else { panic!("the relation of each atom") };
                    atoms.push(trie(relation, &atom.arguments));
                }
                IrNode::Lib(atom) => {
                    for v in super::plan::variables_of(&atom.arguments) {
                        libs[usize::from(v.0)].push(node);
                    }
                    checks[last].push(node);
                }
                IrNode::Not(filter) | IrNode::Counterexample(filter) => {
                    let NodeInput::Clauses(bodies) = &inputs.0[node] else { panic!("the inputs of each filter's body") };
                    filter_orders.insert(node, variable_order(&filter.body, &sizes(&bodies[0]), &filter.outer));
                    checks[last].push(node);
                }
                IrNode::Or(union) => {
                    let NodeInput::Clauses(bodies) = &inputs.0[node] else { panic!("the inputs of each branch") };
                    for (branch, (body, inputs)) in union.branches.iter().zip(bodies.iter()).enumerate() {
                        let outer: Vec<Variable> = body.columns.iter().copied().filter(|c| !union.exported.contains(c)).collect();
                        branch_orders.insert((node, branch), variable_order(body, &sizes(inputs), &outer));
                    }
                    unions.push(node);
                    checks[last].push(node);
                }
                IrNode::Comparison(_) => checks[last].push(node),
            }
        }
        for slot in &mut checks {
            slot.sort_by_key(|&node| (check_cost(&clause.nodes[node]), node));
        }
        let stop_from = order.len() - order.iter().rev().take_while(|v| !clause.columns.contains(v)).count();
        Plan { order, atoms, checks, libs, filter_orders, branch_orders, unions, stop_from }
    }
}

/// The place of a node among the nodes checked at one variable, cheapest
/// first: a comparison, an algebra relation, a filter's probe, a union's
/// branches. A check that fails ends the binding, so the order depends on
/// the kinds of the nodes and not on where they stand in the body.
fn check_cost(node: &IrNode) -> u8 {
    match node {
        IrNode::Comparison(_) => 0,
        IrNode::Lib(_) => 1,
        IrNode::Not(_) | IrNode::Counterexample(_) => 2,
        IrNode::Or(_) => 3,
        IrNode::Atom(_) => unreachable!("an atom is joined, not checked"),
    }
}

/// The plan of one part of a clause.
struct PartPlan {
    columns: Vec<ColumnIndex>,
    /// The variables of the part's columns.
    projected: Vec<Variable>,
    plan: Plan,
}

/// The plans of the parts of a clause, for one set of variables bound
/// before its search.
struct ClausePlan {
    parts: Vec<PartPlan>,
}

/// The bytes of entries that a [`SearchMemo`] takes, past which it takes no
/// new entry. A provisional bound, which changes no output.
const MEMO_BYTES: usize = 256 << 20;

/// What an evaluation charged to its budget, in order.
type Charges = Rc<[Charge]>;

/// The rows of a lib atom's algebra relation at bound values.
type LibRows = Rc<Vec<Box<[TermId]>>>;

#[derive(Default)]
struct MemoTables {
    bytes: usize,
    plans: StableHashMap<(usize, Vec<Variable>), Rc<ClausePlan>>,
    libs: StableHashMap<LibName, StableHashMap<Vec<Option<TermId>>, LibRows>>,
    probes: StableHashMap<(usize, Vec<TermId>), (bool, Charges)>,
    branches: StableHashMap<(usize, Vec<(Variable, TermId)>), (Arc<Relation>, Charges)>,
}

impl MemoTables {
    /// Takes `size` more bytes and gives whether the memo took them.
    fn take(&mut self, size: usize) -> bool {
        let fits = self.bytes.saturating_add(size) <= MEMO_BYTES;
        if fits {
            self.bytes += size;
        }
        fits
    }
}

/// What the evaluation of one clause or part keeps, for the searches it
/// starts: the rows of a lib atom, whether a filter holds and the relation
/// of an `OR` branch at the values they were evaluated at, with the counts
/// of a filter's and a branch's evaluation, and the plan of each nested
/// clause at each set of bound variables. A clause, a filter and a branch
/// stand in the memo by their address, and stand at one address in one
/// evaluation.
#[derive(Default)]
pub struct SearchMemo {
    tables: RefCell<MemoTables>,
}

impl SearchMemo {
    /// The plan of `clause` with `bound` bound before its search, made at
    /// its first use.
    fn plan(&self, clause: &ClauseIr, order: &VariableOrder, inputs: &JoinInputs, bound: &[(Variable, TermId)]) -> Rc<ClausePlan> {
        let mut variables: Vec<Variable> = bound.iter().map(|&(variable, _)| variable).collect();
        variables.sort_by_key(|variable| variable.0);
        let key = (std::ptr::from_ref(clause) as usize, variables);
        if let Some(plan) = self.tables.borrow().plans.get(&key) {
            return plan.clone();
        }
        let nodes: Vec<usize> = (0..clause.nodes.len()).collect();
        let parts = parts(clause, &nodes, &|node| node)
            .into_iter()
            .map(|part| PartPlan {
                columns: part.columns(clause),
                projected: clause.columns.iter().copied().filter(|v| part.variables.contains(v)).collect(),
                plan: Plan::new(clause, &part.nodes, &[], part.order(order, &key.1), &key.1, inputs),
            })
            .collect();
        let plan = Rc::new(ClausePlan { parts });
        self.tables.borrow_mut().plans.insert(key, plan.clone());
        plan
    }

    /// The rows of the algebra relation `relation` at `bound`, if held.
    fn lib(&self, relation: &LibName, bound: &[Option<TermId>]) -> Option<LibRows> {
        self.tables.borrow().libs.get(relation)?.get(bound).cloned()
    }

    fn keep_lib(&self, relation: &LibName, bound: &[Option<TermId>], rows: &LibRows) {
        let mut tables = self.tables.borrow_mut();
        let size = 64 + bound.len() * 8 + rows.iter().map(|row| 24 + row.len() * 8).sum::<usize>();
        if tables.take(size) {
            tables.libs.entry(relation.clone()).or_default().insert(bound.to_vec(), rows.clone());
        }
    }

    /// Whether the filter at `key` holds, with the counts of its probe, if
    /// held.
    fn probe(&self, key: &(usize, Vec<TermId>)) -> Option<(bool, Charges)> {
        self.tables.borrow().probes.get(key).cloned()
    }

    fn keep_probe(&self, key: (usize, Vec<TermId>), entry: (bool, Charges)) {
        let mut tables = self.tables.borrow_mut();
        if tables.take(64 + key.1.len() * 8 + entry.1.len() * 16) {
            tables.probes.insert(key, entry);
        }
    }

    /// The relation of the branch at `key`, with the counts of its join, if
    /// held.
    fn branch(&self, key: &(usize, Vec<(Variable, TermId)>)) -> Option<(Arc<Relation>, Charges)> {
        self.tables.borrow().branches.get(key).cloned()
    }

    fn keep_branch(&self, key: (usize, Vec<(Variable, TermId)>), entry: (Arc<Relation>, Charges)) {
        let mut tables = self.tables.borrow_mut();
        let size = 96 + key.1.len() * 16 + entry.1.len() * 16 + usize::from(entry.0.arity()) * 8 * (entry.0.len().min(1 << 20) as usize);
        if tables.take(size) {
            tables.branches.insert(key, entry);
        }
    }
}

/// The generic join of one connected set of a clause's nodes.
struct Search<'c> {
    clause: &'c ClauseIr,
    registry: &'c Registry,
    inputs: &'c JoinInputs,
    plan: &'c Plan,
    memo: &'c SearchMemo,
    binding: Vec<Option<TermId>>,
    tried: Batch,
}

impl<'c> Search<'c> {
    /// The search over `plan` at the values `bound` gives some variables.
    fn new(
        clause: &'c ClauseIr,
        plan: &'c Plan,
        inputs: &'c JoinInputs,
        registry: &'c Registry,
        memo: &'c SearchMemo,
        bound: &[(Variable, TermId)],
    ) -> Self {
        let mut binding = vec![None; clause.variables.len()];
        for &(variable, value) in bound {
            binding[usize::from(variable.0)] = Some(value);
        }
        Search { clause, registry, inputs, plan, memo, binding, tried: Batch::default() }
    }

    /// The rows of `projected` over each binding that passes every node.
    fn run(mut self, projected: &[Variable], budget: &mut Budget<'_>) -> Result<RowSet, ReachedBound> {
        let mut rows = RowSet::empty(projected.len() as u16);
        let plan = self.plan;
        let mut cursors: Vec<(&Index, usize)> = Vec::with_capacity(plan.atoms.len());
        for atom in &plan.atoms {
            if atom.empty {
                return Ok(rows);
            }
            let mut at: &Index = &atom.index;
            let mut depth = 0;
            while let Some(&argument) = atom.levels.get(depth) {
                let term = match argument {
                    Argument::Term(term) => term,
                    Argument::Variable(v) => match self.binding[usize::from(v.0)] {
                        Some(term) => term,
                        None => break,
                    },
                };
                match at.child(term) {
                    Some(child) => at = child,
                    None => return Ok(rows),
                }
                depth += 1;
            }
            cursors.push((at, depth));
        }
        let unbound = plan.checks.len() - 1;
        if self.passes(unbound, budget)? {
            self.step(0, &plan.atoms, &mut cursors, projected, &mut rows, budget)?;
        }
        self.tried.finish(budget)?;
        Ok(rows)
    }

    /// Searches the variables of the order from `rank` on, and gives whether
    /// a binding passed.
    fn step<'t>(
        &mut self,
        rank: usize,
        atoms: &'t [AtomTrie],
        cursors: &mut Vec<(&'t Index, usize)>,
        projected: &[Variable],
        rows: &mut RowSet,
        budget: &mut Budget<'_>,
    ) -> Result<bool, ReachedBound> {
        let Some(&variable) = self.plan.order.get(rank) else {
            let row: Row = projected.iter().map(|v| self.binding[usize::from(v.0)].expect("a bound column")).collect();
            if rows.insert(row) {
                budget.charge_rows(1)?;
            }
            return Ok(true);
        };
        let at = |atom: &AtomTrie, depth: usize| matches!(atom.levels.get(depth), Some(Argument::Variable(v)) if *v == variable);
        let sources: Vec<usize> = (0..atoms.len()).filter(|&a| at(&atoms[a], cursors[a].1)).collect();
        let candidates: Vec<TermId> = if let Some(value) = self.equal_value(variable) {
            vec![value]
        } else if let Some(&smallest) = sources.iter().min_by_key(|&&a| (cursors[a].0.len(), a)) {
            cursors[smallest].0.entries().map(|(value, _)| value).collect()
        } else if let Some(values) = self.lib_values(variable)? {
            values
        } else if let Some(values) = self.union_values(variable, budget)? {
            values
        } else {
            let ty = &self.clause.variables[usize::from(variable.0)].ty;
            domain(self.registry, ty).expect("a variable of the order that a node of the clause binds")
        };
        let early = rank >= self.plan.stop_from;
        let mut candidates = candidates;
        if early {
            candidates.sort_by_key(|value| value.encoding());
        }
        let stops = early && self.clause.variables[usize::from(variable.0)].ty != ValueType::Ident;
        let mut passed = false;
        for value in candidates {
            self.tried.count(budget, 1)?;
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
                passed |= self.step(rank + 1, atoms, cursors, projected, rows, budget)?;
            }
            self.binding[usize::from(variable.0)] = None;
            for (a, cursor) in saved {
                cursors[a] = cursor;
            }
            if passed && stops {
                break;
            }
        }
        Ok(passed)
    }

    /// The value an `=` gives `variable` from a bound variable or `0`.
    fn equal_value(&self, variable: Variable) -> Option<TermId> {
        self.plan.checks.iter().flatten().find_map(|&node| match &self.clause.nodes[node] {
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
        for &node in &self.plan.libs[usize::from(variable.0)] {
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

    /// The values that the first union that exports `variable` gives it,
    /// each branch joined at the bound values of its columns, or `None`
    /// where no union exports it.
    fn union_values(&self, variable: Variable, budget: &mut Budget<'_>) -> Result<Option<Vec<TermId>>, ReachedBound> {
        let found = self.plan.unions.iter().find_map(|&node| match &self.clause.nodes[node] {
            IrNode::Or(union) if union.exported.contains(&variable) => Some((node, union)),
            _ => None,
        });
        let Some((node, union)) = found else { return Ok(None) };
        let mut values = Vec::new();
        for (index, branch) in union.branches.iter().enumerate() {
            for column in branch.columns.iter() {
                assert!(
                    union.exported.contains(column) || self.binding[usize::from(column.0)].is_some(),
                    "a union binds its exports once the variables it reads from its clause are bound"
                );
            }
            let at = branch.columns.iter().position(|column| *column == variable).expect("each branch holds each export");
            each_row(&*self.branch(node, index, branch, budget)?, &mut |row| values.push(row[at]));
        }
        values.sort_by_key(|value| value.encoding());
        values.dedup();
        Ok(Some(values))
    }

    /// Whether a branch of `union`, the union of the node at `node`, holds
    /// at the bound values of its columns.
    fn union_holds(&self, node: usize, union: &super::ir::Union, budget: &mut Budget<'_>) -> Result<bool, ReachedBound> {
        for (index, branch) in union.branches.iter().enumerate() {
            if !self.branch(node, index, branch, budget)?.is_empty() {
                return Ok(true);
            }
        }
        Ok(false)
    }

    /// The relation of `branch`, the branch at `index` of the union of the
    /// node at `node`, at the bound values of its columns. The memo serves
    /// a branch joined at those values before, and counts what its join
    /// counted.
    fn branch(&self, node: usize, index: usize, branch: &ClauseIr, budget: &mut Budget<'_>) -> Result<Arc<Relation>, ReachedBound> {
        let NodeInput::Clauses(bodies) = &self.inputs.0[node] else { unreachable!("the inputs of a union's branches") };
        let bound: Vec<(Variable, TermId)> =
            branch.columns.iter().filter_map(|&column| Some((column, self.binding[usize::from(column.0)]?))).collect();
        let key = (std::ptr::from_ref(branch) as usize, bound);
        if let Some((relation, charges)) = self.memo.branch(&key) {
            budget.replay(&charges)?;
            return Ok(relation);
        }
        let order = &self.plan.branch_orders[&(node, index)];
        let (relation, charges) = budget.logged(|budget| join_in(self.memo, branch, order, &bodies[index], self.registry, &key.1, budget))?;
        let relation = Arc::new(relation);
        self.memo.keep_branch(key, (relation.clone(), charges));
        Ok(relation)
    }

    /// Calls `emit` on each row of the lib atom at `node` that agrees with
    /// the atom's terms and bound variables. The memo serves an atom
    /// evaluated at those values before.
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
        let rows = match self.memo.lib(&atom.relation, &bound) {
            Some(rows) => rows,
            None => {
                let algebra = crate::algebra::algebra(&atom.relation).expect("a native form of each algebra relation");
                let mut found = Vec::new();
                algebra
                    .evaluate(&bound, self.registry, &mut |row| {
                        if bound.iter().zip(row).all(|(b, value)| b.is_none_or(|b| b == *value)) {
                            found.push(row.into());
                        }
                    })
                    .map_err(ReachedBound::Margin)?;
                let rows = Rc::new(found);
                self.memo.keep_lib(&atom.relation, &bound, &rows);
                rows
            }
        };
        for row in rows.iter() {
            emit(row);
        }
        Ok(())
    }

    /// Whether the binding passes each node checked at `rank`.
    fn passes(&self, rank: usize, budget: &mut Budget<'_>) -> Result<bool, ReachedBound> {
        for &node in &self.plan.checks[rank] {
            let holds = match &self.clause.nodes[node] {
                IrNode::Comparison(comparison) => self.compare(comparison),
                IrNode::Lib(_) => {
                    let mut found = false;
                    self.evaluate_lib(node, &mut |_| found = true)?;
                    found
                }
                IrNode::Not(filter) | IrNode::Counterexample(filter) => !self.probe(node, filter, budget)?,
                IrNode::Or(union) => self.union_holds(node, union, budget)?,
                IrNode::Atom(_) => unreachable!("an atom is joined, not checked"),
            };
            if !holds {
                return Ok(false);
            }
        }
        Ok(true)
    }

    /// Whether `filter`, the filter of the node at `node`, holds a binding
    /// at the bound values of its outer variables. The memo serves a filter
    /// probed at those values before, and counts what its probe counted.
    fn probe(&self, node: usize, filter: &Filter, budget: &mut Budget<'_>) -> Result<bool, ReachedBound> {
        let outer: Vec<TermId> = filter.outer.iter().map(|v| self.binding[usize::from(v.0)].expect("a bound outer variable")).collect();
        let key = (std::ptr::from_ref(filter) as usize, outer);
        if let Some((holds, charges)) = self.memo.probe(&key) {
            budget.replay(&charges)?;
            return Ok(holds);
        }
        let NodeInput::Clauses(bodies) = &self.inputs.0[node] else { unreachable!("the inputs of a filter's body") };
        let (holds, charges) = budget
            .logged(|budget| super::filters::probe(self.memo, filter, &key.1, &self.plan.filter_orders[&node], &bodies[0], self.registry, budget))?;
        self.memo.keep_probe(key, (holds, charges));
        Ok(holds)
    }

    /// Whether the bound operands of `comparison` satisfy it. An order
    /// compares its operands as numbers.
    fn compare(&self, comparison: &Comparison) -> bool {
        let first = self.binding[usize::from(comparison.first.0)].expect("a bound operand");
        let second = match comparison.second {
            Operand::Variable(v) => self.binding[usize::from(v.0)].expect("a bound operand"),
            Operand::Zero => TermId::from_encoding(0),
        };
        match comparison.op {
            ConstraintOp::Eq => first == second,
            ConstraintOp::Ne => first != second,
            ConstraintOp::Lt => Term::decode_number(first) < Term::decode_number(second),
            ConstraintOp::Le => Term::decode_number(first) <= Term::decode_number(second),
            ConstraintOp::Gt => Term::decode_number(first) > Term::decode_number(second),
            ConstraintOp::Ge => Term::decode_number(first) >= Term::decode_number(second),
        }
    }
}

