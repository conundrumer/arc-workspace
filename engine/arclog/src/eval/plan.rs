//! The variable order of a clause, which generic join binds the variables
//! in.
//!
//! The order is a function of the clause's IR and the sizes of the
//! relations it reads, so a body of equal content over relations of equal
//! ids has one plan. It is the order of least estimated bindings. A choice
//! of the order is a variable that an atom binds, estimated at the row count
//! of the smallest atom that binds it, or a variable that a union exports
//! and no atom or comparison binds, estimated at the sum over the union's
//! branches of the estimate of the variable in the branch, and chosen only
//! after the columns that the branches read from the clause. A variable that
//! an algebra relation or an `=` places costs nothing, and the cost of a
//! sequence of choices is the sum over its choices of the product of the
//! estimates up to that choice. Each choice is followed by the outputs of
//! each algebra relation whose mode the placed variables satisfy, and by each
//! variable an `=` binds from a placed one. A tie in cost goes to the
//! sequence of the smaller estimates, then of the canonical positions. A
//! clause with more than 12 choices takes its choices in order of estimate
//! then canonical position, each export of a union that no atom or
//! comparison binds after the columns its branches read.

use super::join::node_variables;
use super::ir::{Argument, Arguments, ClauseIr, IrNode, Operand, Union, Variable};
use crate::program::ConstraintOp;
use crate::registry::{AlgebraRelation, LibName, Registry};
use crate::algebra::geometry::orientation_domain;

/// The most choices the order searches subsets of; past it the order places
/// the choices by estimate.
const SUBSET_BOUND: usize = 12;

/// The order the join binds a clause's variables in, each variable once.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct VariableOrder(pub Box<[Variable]>);

/// What the order knows of the relations a node of a clause reads.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum NodeSize {
    /// No relation with rows, such as a comparison or an algebra relation's
    /// atom.
    Unread,
    /// The count of rows of an atom's relation.
    Rows(u64),
    /// The sizes of the node's own clauses: a filter's body, or a union's
    /// branches, in the node's order.
    Clauses(Box<[RelationSizes]>),
}

/// The sizes of the relations each node of a clause reads, by the node's
/// index in [`ClauseIr::nodes`].
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct RelationSizes(pub Box<[NodeSize]>);

/// The variable order of `clause` over relations of `sizes`: the sequence of
/// choices of least estimated bindings, each followed by its closure, as the
/// module doc gives. Each variable that an algebra relation binds stands
/// after the inputs of the mode that binds it, and each variable that a union
/// exports, and no atom or comparison binds, after the columns that the
/// branches of that union read from `clause`, so the order binds every
/// variable that the clause binds.
///
/// The order holds each variable that a node of the clause holds
/// ([`node_variables`]), other than `outer`'s, and a variable that no node
/// binds stands after the ones that nodes bind; a variable that stands only
/// in a filter's body is the filter's own. A variable that an `=` binds from
/// another stands directly after that other, as an algebra relation's output
/// does.
///
/// `outer` holds the variables of `clause` that its caller binds before the
/// join. They count as bound, so the inputs of a mode they satisfy are
/// held, and they stand in no place of the order, as the join drops a bound
/// variable from it.
pub fn variable_order(clause: &ClauseIr, sizes: &RelationSizes, outer: &[Variable]) -> VariableOrder {
    let count = clause.variables.len();
    let mut bound = vec![false; count];
    for variable in clause.nodes.iter().flat_map(bound_variables) {
        bound[usize::from(variable.0)] = true;
    }
    let registry = Registry::get();
    let mut placed = vec![false; count];
    let mut order = Vec::new();
    let mut place = |variable: Variable, placed: &mut Vec<bool>, order: &mut Vec<Variable>| {
        if !std::mem::replace(&mut placed[usize::from(variable.0)], true) {
            order.push(variable);
        }
    };
    for variable in outer {
        placed[usize::from(variable.0)] = true;
    }
    let follow = |placed: &mut Vec<bool>, order: &mut Vec<Variable>, place: &mut dyn FnMut(Variable, &mut Vec<bool>, &mut Vec<Variable>)| loop {
        let before = order.len();
        for node in clause.nodes.iter() {
            match node {
                IrNode::Lib(atom) => {
                    let relation = algebra_relation(registry, &atom.relation);
                    if mode_holds(relation, &atom.arguments, clause, placed) {
                        let mut outputs: Vec<Variable> = variables_of(&atom.arguments).collect();
                        outputs.sort_by_key(|v| v.0);
                        outputs.into_iter().for_each(|v| place(v, placed, order));
                    }
                }
                IrNode::Comparison(comparison) if comparison.op == ConstraintOp::Eq => match comparison.second {
                    Operand::Zero => place(comparison.first, placed, order),
                    Operand::Variable(second) => {
                        if placed[usize::from(comparison.first.0)] {
                            place(second, placed, order);
                        } else if placed[usize::from(second.0)] {
                            place(comparison.first, placed, order);
                        }
                    }
                },
                _ => {}
            }
        }
        if order.len() == before {
            break;
        }
    };
    follow(&mut placed, &mut order, &mut place);
    let mut extend = |placed: &mut Vec<bool>, chosen: Variable| {
        let mut order = Vec::new();
        place(chosen, placed, &mut order);
        follow(placed, &mut order, &mut place);
    };
    let choices = choices(clause, sizes, &placed, &mut extend);
    let sequence = if (2..=SUBSET_BOUND).contains(&choices.len()) {
        cheapest_sequence(&choices, &placed, &mut extend)
    } else {
        sequence_in_order(&choices, &placed, &mut extend)
    };
    for variable in sequence {
        place(variable, &mut placed, &mut order);
        follow(&mut placed, &mut order, &mut place);
    }
    let dependencies = dependencies(clause);
    let ready = |placed: &[bool]| {
        (0..count).map(|v| Variable(v as u16)).find(|variable| {
            !placed[usize::from(variable.0)]
                && dependencies[usize::from(variable.0)].as_ref().is_some_and(|reads| reads.iter().all(|read| placed[usize::from(read.0)]))
        })
    };
    while let Some(variable) = ready(&placed) {
        place(variable, &mut placed, &mut order);
        follow(&mut placed, &mut order, &mut place);
    }
    for variable in (0..count).filter(|&v| bound[v]).map(|v| Variable(v as u16)) {
        place(variable, &mut placed, &mut order);
        follow(&mut placed, &mut order, &mut place);
    }
    let mut held = vec![false; count];
    for variable in clause.nodes.iter().flat_map(node_variables) {
        held[usize::from(variable.0)] = true;
    }
    for variable in (0..count).filter(|&v| held[v]).map(|v| Variable(v as u16)) {
        place(variable, &mut placed, &mut order);
        follow(&mut placed, &mut order, &mut place);
    }
    VariableOrder(order.into())
}

/// A variable the order places by a choice of its own, with its estimate.
struct Choice {
    variable: Variable,
    /// The estimated count of the variable's values.
    estimate: u64,
    /// For a variable that a union exports and no atom binds, the columns
    /// that the union's branches read from the clause, which stand before the
    /// choice; `None` for a variable that an atom binds.
    reads: Option<Box<[Variable]>>,
}

impl Choice {
    /// Whether the choice can come next: its variable is outside `closure`
    /// and its `reads` stand in it.
    fn is_next(&self, closure: &[bool]) -> bool {
        !closure[usize::from(self.variable.0)] && self.reads.as_deref().unwrap_or_default().iter().all(|read| closure[usize::from(read.0)])
    }
}

/// The choices of `clause` in the order of estimate then variable: each
/// variable that an atom binds, estimated at the rows of the smallest atom
/// that binds it, and each variable that a union exports and no atom or
/// comparison binds, estimated by [`union_estimate`], that the closure of the
/// choices before it has not placed, and whose union reads columns that the
/// closure has placed. `placed` holds the variables placed before any choice,
/// and `extend` adds a variable and its closure to a set of placed variables.
fn choices(clause: &ClauseIr, sizes: &RelationSizes, placed: &[bool], extend: &mut impl FnMut(&mut Vec<bool>, Variable)) -> Vec<Choice> {
    let atoms = atom_rows(clause, sizes);
    let mut choices: Vec<Choice> = (0..clause.variables.len())
        .filter_map(|v| Some(Choice { variable: Variable(v as u16), estimate: atoms[v]?, reads: None }))
        .collect();
    let mut closure = placed.to_vec();
    for choice in &choices {
        extend(&mut closure, choice.variable);
    }
    let unions = union_binders(clause);
    loop {
        let before = choices.len();
        for v in 0..clause.variables.len() {
            let (false, Some((_, union))) = (closure[v], unions[v]) else { continue };
            let variable = Variable(v as u16);
            let reads = union_reads(union);
            if let Some(estimate) = union_estimate(clause, sizes, variable).filter(|_| reads.iter().all(|read| closure[usize::from(read.0)])) {
                extend(&mut closure, variable);
                choices.push(Choice { variable, estimate, reads: Some(reads) });
            }
        }
        if choices.len() == before {
            break;
        }
    }
    choices.sort_by_key(|choice| (choice.estimate, choice.variable.0));
    choices
}

/// The sequence of `choices` to place, each followed by its closure, of least
/// cost, where the cost of a sequence is the sum over its choices of the
/// product of the estimates of the choices up to and including that one. A
/// choice is a variable outside the closure of the earlier choices, whose
/// `reads` stand in that closure, and the sequence ends when that closure
/// holds every choice. `choices` is in the order of estimate then index, and a
/// tie in cost goes to the sequence that is least in that order, so the order
/// of that sort is the order where costs are equal. `extend` adds a variable
/// and its closure to a set of placed variables, and `placed` holds the
/// variables placed before any choice.
///
/// The closure of a set of choices does not depend on their order, and the
/// product of their estimates does not either, so the search is a minimum over
/// subsets of the choices.
fn cheapest_sequence(choices: &[Choice], placed: &[bool], extend: &mut impl FnMut(&mut Vec<bool>, Variable)) -> Vec<Variable> {
    let count = choices.len();
    let mut closures: Vec<Vec<bool>> = Vec::with_capacity(1 << count);
    let mut products: Vec<u128> = Vec::with_capacity(1 << count);
    // The best (cost, choices as indexes into `choices`) to reach each subset.
    let mut best: Vec<Option<(u128, Vec<usize>)>> = vec![None; 1 << count];
    let mut finish: Option<(u128, Vec<usize>)> = None;
    for mask in 0..1usize << count {
        if mask == 0 {
            closures.push(placed.to_vec());
            products.push(1);
            best[0] = Some((0, Vec::new()));
        } else {
            let low = mask.trailing_zeros() as usize;
            let mut closure = closures[mask & (mask - 1)].clone();
            extend(&mut closure, choices[low].variable);
            closures.push(closure);
            products.push(products[mask & (mask - 1)].saturating_mul(u128::from(choices[low].estimate)));
            let mut found: Option<(u128, Vec<usize>)> = None;
            for choice in (0..count).filter(|c| mask >> c & 1 == 1) {
                let before = mask & !(1 << choice);
                let Some((cost, earlier)) = &best[before] else { continue };
                let closure = &closures[before];
                if !choices[choice].is_next(closure) {
                    continue;
                }
                let mut next = earlier.clone();
                next.push(choice);
                let candidate = (cost.saturating_add(products[mask]), next);
                if found.as_ref().is_none_or(|found| candidate < *found) {
                    found = Some(candidate);
                }
            }
            best[mask] = found;
        }
        if let Some(candidate) = &best[mask] {
            if choices.iter().all(|c| closures[mask][usize::from(c.variable.0)]) && finish.as_ref().is_none_or(|finish| candidate < finish) {
                finish = Some(candidate.clone());
            }
        }
    }
    let (_, sequence) = finish.expect("the choices in order reach a set whose closure holds them all");
    sequence.into_iter().map(|c| choices[c].variable).collect()
}

/// The sequence of `choices` to place, each followed by its closure, where
/// the count of choices is outside the range that [`cheapest_sequence`]
/// searches, 0 or 1 or past [`SUBSET_BOUND`]: the first of `choices`, in
/// their order of estimate then index, that the closure of the earlier ones
/// does not hold and whose `reads` stand in that closure, until none is left.
/// `extend` and `placed` are as for [`cheapest_sequence`].
fn sequence_in_order(choices: &[Choice], placed: &[bool], extend: &mut impl FnMut(&mut Vec<bool>, Variable)) -> Vec<Variable> {
    let mut closure = placed.to_vec();
    let mut sequence = Vec::new();
    while let Some(choice) = choices.iter().find(|choice| choice.is_next(&closure)) {
        extend(&mut closure, choice.variable);
        sequence.push(choice.variable);
    }
    sequence
}

/// The count of rows of the smallest atom of `clause` that binds each
/// variable, by the variable's index, `None` for a variable that no atom of
/// known size binds.
fn atom_rows(clause: &ClauseIr, sizes: &RelationSizes) -> Vec<Option<u64>> {
    let mut rows: Vec<Option<u64>> = vec![None; clause.variables.len()];
    for (node, size) in clause.nodes.iter().zip(sizes.0.iter()) {
        if let (IrNode::Atom(atom), NodeSize::Rows(count)) = (node, size) {
            for variable in variables_of(&atom.arguments) {
                let held = &mut rows[usize::from(variable.0)];
                *held = Some(held.map_or(*count, |held| held.min(*count)));
            }
        }
    }
    rows
}

/// The union node of `clause` that binds each variable that no atom or
/// comparison binds, by the variable's index: the first union that exports
/// it, since the join takes its values from that union.
fn union_binders(clause: &ClauseIr) -> Vec<Option<(usize, &Union)>> {
    let mut binders: Vec<Option<(usize, &Union)>> = vec![None; clause.variables.len()];
    for (node, union) in clause.nodes.iter().enumerate().filter_map(|(node, n)| if let IrNode::Or(union) = n { Some((node, union)) } else { None }) {
        for variable in union.exported.iter() {
            binders[usize::from(variable.0)].get_or_insert((node, union));
        }
    }
    for node in clause.nodes.iter() {
        if let IrNode::Atom(_) | IrNode::Comparison(_) = node {
            for variable in bound_variables(node) {
                binders[usize::from(variable.0)] = None;
            }
        }
    }
    binders
}

/// The columns that the branches of `union` read from the clause around it:
/// those that it does not export.
fn union_reads(union: &Union) -> Box<[Variable]> {
    union.branches.iter().flat_map(|branch| branch.columns.iter().copied()).filter(|column| !union.exported.contains(column)).collect()
}

/// The estimate of the count of values that the union which binds `variable`
/// in `clause` gives it: the sum over the union's branches of the rows of
/// the smallest atom of the branch that binds it, or, where a union of the
/// branch binds it, that union's estimate. `None` where `variable` has no
/// such union or a branch has no estimate.
fn union_estimate(clause: &ClauseIr, sizes: &RelationSizes, variable: Variable) -> Option<u64> {
    let (node, union) = union_binders(clause)[usize::from(variable.0)]?;
    let NodeSize::Clauses(branch_sizes) = &sizes.0[node] else { return None };
    union.branches.iter().zip(branch_sizes.iter()).try_fold(0u64, |total, (branch, sizes)| {
        let rows = atom_rows(branch, sizes)[usize::from(variable.0)].or_else(|| union_estimate(branch, sizes, variable))?;
        Some(total.saturating_add(rows))
    })
}

/// The variables that each variable of `clause` waits on before the order
/// places it, by the variable's index. A variable that an atom or a
/// comparison binds waits on none. A variable that only unions bind waits
/// on the columns that the branches of the first union that exports it read
/// from `clause`, since the join takes its values from that union. A
/// variable that only an algebra relation binds has `None`: the order places
/// it once a mode of that relation holds.
fn dependencies(clause: &ClauseIr) -> Vec<Option<Box<[Variable]>>> {
    let mut dependencies: Vec<Option<Box<[Variable]>>> = vec![None; clause.variables.len()];
    for node in clause.nodes.iter() {
        if let IrNode::Atom(_) | IrNode::Comparison(_) = node {
            for variable in bound_variables(node) {
                dependencies[usize::from(variable.0)] = Some(Box::new([]));
            }
        }
    }
    for (variable, binder) in union_binders(clause).into_iter().enumerate() {
        if let Some((_, union)) = binder {
            dependencies[variable] = Some(union_reads(union));
        }
    }
    dependencies
}

/// The variables that `node` binds in its enclosing clause: an atom's, a
/// comparison's, and the variables a union exports.
pub(super) fn bound_variables(node: &IrNode) -> Vec<Variable> {
    match node {
        IrNode::Atom(atom) => variables_of(&atom.arguments).collect(),
        IrNode::Lib(atom) => variables_of(&atom.arguments).collect(),
        IrNode::Comparison(comparison) => {
            let second = match comparison.second {
                Operand::Variable(second) => Some(second),
                Operand::Zero => None,
            };
            std::iter::once(comparison.first).chain(second).collect()
        }
        IrNode::Or(union) => union.exported.to_vec(),
        IrNode::Not(_) | IrNode::Counterexample(_) => Vec::new(),
    }
}

/// Each variable that stands at a column of `arguments`.
pub(super) fn variables_of(arguments: &Arguments) -> impl Iterator<Item = Variable> + '_ {
    arguments.0.iter().filter_map(|(_, argument)| match argument {
        Argument::Variable(variable) => Some(*variable),
        Argument::Term(_) => None,
    })
}

/// The declaration of the algebra relation or relation macro `name`.
pub(super) fn algebra_relation<'r>(registry: &'r Registry, name: &LibName) -> &'r AlgebraRelation {
    registry.algebra_relation(name).expect("a lib atom of a checked clause reads an algebra relation or a relation macro")
}

/// Whether the columns of `arguments` whose variables `bound` holds, or
/// whose argument is a term, satisfy a mode of `relation`, or `relation`
/// has none. A variable of an orientation type is bound by its finite
/// domain.
pub(super) fn mode_holds(relation: &AlgebraRelation, arguments: &Arguments, clause: &ClauseIr, bound: &[bool]) -> bool {
    if relation.modes.is_empty() {
        return true;
    }
    let mut columns = vec![false; relation.columns.len()];
    for (column, argument) in arguments.0.iter() {
        columns[usize::from(column.0)] = match argument {
            Argument::Term(_) => true,
            Argument::Variable(variable) => {
                bound[usize::from(variable.0)] || orientation_domain(&clause.variables[usize::from(variable.0)].ty).is_some()
            }
        };
    }
    crate::algebra::satisfied_mode(relation, &columns).is_some()
}

