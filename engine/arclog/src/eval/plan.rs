//! The variable order of a clause, which generic join binds the variables
//! in.
//!
//! The order is a function of the clause's IR and the sizes of the
//! relations it reads, so a body of equal content over relations of equal
//! ids has one plan: variables in order of the smallest relation that
//! binds them, ties in the order of their canonical positions, with each
//! output of an algebra relation directly after the inputs of the first of
//! its modes that the order satisfies.

use super::ir::{Argument, Arguments, ClauseIr, IrNode, Operand, Variable};
use crate::program::ConstraintOp;
use crate::registry::{AlgebraRelation, LibEntry, LibName, Macro, Registry};
use crate::terms::OrientationType;
use crate::types::ValueType;

/// The order the join binds a clause's variables in, each variable once.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct VariableOrder(pub Box<[Variable]>);

/// The count of rows of the relation each node of a clause reads, by the
/// node's index in [`ClauseIr::nodes`], `None` for a node that reads no
/// relation with rows, such as a comparison or an algebra relation's atom.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct RelationSizes(pub Box<[Option<u64>]>);

/// The variable order of `clause` over relations of `sizes`. Each variable
/// that an algebra relation binds stands after the inputs of the mode that
/// binds it, so the order grounds every variable that the clause grounds.
///
/// The variables ordered are those the clause's atoms, comparisons and
/// unions bind; a variable that stands only in a filter's body is the
/// filter's own. A variable that an `=` binds from another stands directly
/// after that other, as an algebra relation's output does.
pub fn variable_order(clause: &ClauseIr, sizes: &RelationSizes) -> VariableOrder {
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
    for variable in by_size {
        place(variable, &mut placed, &mut order);
        follow(&mut placed, &mut order, &mut place);
    }
    for variable in (0..count).filter(|&v| bound[v]).map(|v| Variable(v as u16)) {
        place(variable, &mut placed, &mut order);
        follow(&mut placed, &mut order, &mut place);
    }
    VariableOrder(order.into())
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
    match registry.entry(name) {
        Some(LibEntry::Relation(relation)) | Some(LibEntry::Macro(Macro::Relation { relation, .. })) => relation,
        _ => panic!("a lib atom of a checked clause reads an algebra relation or a relation macro"),
    }
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

/// The constants of an orientation type, its finite domain: the D4
/// constants that are C4, or the constants of each orientation type it
/// unites.
pub(super) enum OrientationDomain {
    C4,
    Types(&'static [OrientationType]),
}

/// The domain of `ty`, or `None` where `ty` is no orientation type.
pub(super) fn orientation_domain(ty: &ValueType) -> Option<OrientationDomain> {
    match ty {
        ValueType::C4 => Some(OrientationDomain::C4),
        ty => ty.orientation_types().map(OrientationDomain::Types),
    }
}
