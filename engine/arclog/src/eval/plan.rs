//! The variable order of a clause, which generic join binds the variables
//! in.
//!
//! The order is a function of the clause's IR and the sizes of the
//! relations it reads, so a body of equal content over relations of equal
//! ids has one plan: variables in order of the smallest relation that
//! binds them, ties in the order of their canonical positions, with each
//! output of an algebra relation directly after the inputs of the first of
//! its modes that the order satisfies.

#![allow(unused_variables, dead_code)]

use super::ir::{ClauseIr, Variable};

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
pub fn variable_order(clause: &ClauseIr, sizes: &RelationSizes) -> VariableOrder {
    todo!()
}
