//! The variable order of a clause, which generic join binds the variables
//! in.
//!
//! The order is a function of the clause's IR and the sizes of the
//! relations it reads, so a body of equal content over relations of equal
//! ids has one plan. It is the order of least estimated bindings: the
//! estimate of a variable that an atom binds is the row count of the
//! smallest atom that binds it, a variable that an algebra relation or an
//! `=` places costs nothing, and the cost of a sequence of choices is the sum
//! over its choices of the product of the estimates up to that choice.
//! Each sized variable that the order chooses is followed by the outputs of
//! each algebra relation whose mode the placed variables satisfy, and by each
//! variable an `=` binds from a placed one. A tie in cost goes to the
//! sequence of the smaller relations, then of the canonical positions. A
//! clause with more than 12 sized variables takes that sequence of smaller
//! relations alone. Each export of a union that no atom or comparison binds
//! stands after the columns its branches read.

use super::join::node_variables;
use super::ir::{Argument, Arguments, ClauseIr, IrNode, Operand, Variable};
use crate::program::ConstraintOp;
use crate::registry::{AlgebraRelation, LibName, Registry};
use crate::algebra::geometry::orientation_domain;

/// The most sized variables whose choices the order searches subsets of;
/// past it the order places the sized variables by size.
const SUBSET_BOUND: usize = 12;

/// The order the join binds a clause's variables in, each variable once.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct VariableOrder(pub Box<[Variable]>);

/// The count of rows of the relation each node of a clause reads, by the
/// node's index in [`ClauseIr::nodes`], `None` for a node that reads no
/// relation with rows, such as a comparison or an algebra relation's atom.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct RelationSizes(pub Box<[Option<u64>]>);

/// The variable order of `clause` over relations of `sizes`: the sequence of
/// sized variables of least estimated bindings, each followed by its closure,
/// as the module doc gives. Each variable
/// that an algebra relation binds stands after the inputs of the mode that
/// binds it, and each variable that a union exports, and no atom or
/// comparison binds, after the columns that the branches of that union read
/// from `clause`, so the order binds every variable that the clause
/// binds.
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
    let mut size: Vec<Option<u64>> = vec![None; count];
    let mut bound = vec![false; count];
    for (node, node_size) in clause.nodes.iter().zip(sizes.0.iter()) {
        for variable in bound_variables(node) {
            bound[usize::from(variable.0)] = true;
            if let (IrNode::Atom(_), Some(rows)) = (node, node_size) {
                let held = &mut size[usize::from(variable.0)];
                *held = Some(held.map_or(*rows, |held| held.min(*rows)));
            }
        }
    }
    let mut by_size: Vec<Variable> = (0..count).filter(|&v| size[v].is_some()).map(|v| Variable(v as u16)).collect();
    by_size.sort_by_key(|v| (size[usize::from(v.0)], v.0));
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
    let sequence = if (2..=SUBSET_BOUND).contains(&by_size.len()) {
        let estimates: Vec<u128> = by_size.iter().map(|v| u128::from(size[usize::from(v.0)].expect("a sized variable"))).collect();
        let extend = |placed: &mut Vec<bool>, chosen: Variable| {
            let mut order = Vec::new();
            place(chosen, placed, &mut order);
            follow(placed, &mut order, &mut place);
        };
        cheapest_sequence(&by_size, &estimates, &placed, extend)
    } else {
        by_size
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

/// The sequence of `sized` variables to place, each followed by its closure,
/// of least cost, where the cost of a sequence is the sum over its choices of
/// the product of the `estimates` of the choices up to and including that
/// one. A choice is a variable outside the closure of the earlier choices,
/// and the sequence ends when that closure holds every sized variable.
/// `sized` is in the order of size then index, and a tie in cost goes to the
/// sequence that is least in that order, so the order of that sort is the
/// order where costs are equal. `extend` adds a variable and its closure to
/// a set of placed variables, and `placed` holds the variables placed before
/// any choice.
///
/// The closure of a set of choices does not depend on their order, and the
/// product of their estimates does not either, so the search is a minimum over
/// subsets of the sized variables.
fn cheapest_sequence(
    sized: &[Variable],
    estimates: &[u128],
    placed: &[bool],
    mut extend: impl FnMut(&mut Vec<bool>, Variable),
) -> Vec<Variable> {
    let count = sized.len();
    let mut closures: Vec<Vec<bool>> = Vec::with_capacity(1 << count);
    let mut products: Vec<u128> = Vec::with_capacity(1 << count);
    // The best (cost, choices as indexes into `sized`) to reach each subset.
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
            extend(&mut closure, sized[low]);
            closures.push(closure);
            products.push(products[mask & (mask - 1)].saturating_mul(estimates[low]));
            let mut found: Option<(u128, Vec<usize>)> = None;
            for choice in (0..count).filter(|c| mask >> c & 1 == 1) {
                let before = mask & !(1 << choice);
                let Some((cost, choices)) = &best[before] else { continue };
                if closures[before][usize::from(sized[choice].0)] {
                    continue;
                }
                let mut next = choices.clone();
                next.push(choice);
                let candidate = (cost.saturating_add(products[mask]), next);
                if found.as_ref().is_none_or(|found| candidate < *found) {
                    found = Some(candidate);
                }
            }
            best[mask] = found;
        }
        if let Some(candidate) = &best[mask] {
            if sized.iter().all(|v| closures[mask][usize::from(v.0)]) && finish.as_ref().is_none_or(|finish| candidate < finish) {
                finish = Some(candidate.clone());
            }
        }
    }
    let (_, choices) = finish.expect("the sized variables in order reach a set whose closure holds them all");
    choices.into_iter().map(|c| sized[c]).collect()
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
    for node in clause.nodes.iter() {
        if let IrNode::Or(union) = node {
            let reads: Box<[Variable]> =
                union.branches.iter().flat_map(|branch| branch.columns.iter().copied()).filter(|column| !union.exported.contains(column)).collect();
            for variable in union.exported.iter() {
                dependencies[usize::from(variable.0)].get_or_insert_with(|| reads.clone());
            }
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

