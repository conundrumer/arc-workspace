//! The input domain of each construction that admits less than every row
//! set its input columns type: the constraints on one key group's inputs,
//! which the construction checks before it reads them, and which the inputs
//! that `arclog-cli lib-compare` generates meet.
//!
//! A constraint names an input by its place among the construction's
//! inputs, and a column by its place among the input's columns other than
//! `key`.

use std::fmt;

use arclog::hash::StableHashMap;
use arclog::relations::RowSet;
use arclog::terms::{Term, TermId};

use crate::order::Order;
use crate::wallpaper::Wallpaper;

/// One constraint on a key group's inputs.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Constraint {
    /// At most one of these inputs holds rows.
    Exclusive(&'static [usize]),
    /// The input's rows are a function of their columns but the last: no
    /// two rows agree on every column but the last.
    Function(usize),
    /// The column of the input holds a positive number in each row.
    Positive { input: usize, column: usize },
    /// The input's rows are pairs of two halves of equal width, and no
    /// row pairs a half with itself.
    Irreflexive(usize),
}

impl fmt::Display for Constraint {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Constraint::Exclusive(inputs) => write!(f, "at most one of the inputs {inputs:?} holds rows"),
            Constraint::Function(input) => write!(f, "the rows of input {input} are a function of their columns but the last"),
            Constraint::Positive { input, column } => write!(f, "column {column} of input {input} holds a positive number"),
            Constraint::Irreflexive(input) => write!(f, "no row of input {input} pairs an element with itself"),
        }
    }
}

/// Order's domain: `before` or `score` alone, `before` strict, each element
/// one score.
const ORDER: &[Constraint] = &[Constraint::Exclusive(&[1, 2]), Constraint::Irreflexive(1), Constraint::Function(2)];

/// Wallpaper's domain: one positive period on each axis.
const WALLPAPER: &[Constraint] = &[Constraint::Function(3), Constraint::Positive { input: 3, column: 1 }];

/// The constraints of the construction of the registry name `name`, none
/// where it admits every row set its input columns type.
pub fn constraints(name: &str) -> &'static [Constraint] {
    match name {
        Order::NAME => ORDER,
        Wallpaper::NAME => WALLPAPER,
        _ => &[],
    }
}

/// Whether the inputs `inputs` of one key group meet `constraint`.
fn meets(constraint: &Constraint, inputs: &[RowSet]) -> bool {
    match *constraint {
        Constraint::Exclusive(of) => of.iter().filter(|&&input| !inputs[input].is_empty()).count() <= 1,
        Constraint::Function(input) => {
            let mut values: StableHashMap<&[TermId], TermId> = StableHashMap::default();
            inputs[input].rows().all(|row| {
                let (leading, last) = row.split_at(row.len() - 1);
                values.insert(leading, last[0]).is_none()
            })
        }
        Constraint::Positive { input, column } => inputs[input].rows().all(|row| Term::decode_number(row[column]) > 0),
        Constraint::Irreflexive(input) => inputs[input].rows().all(|row| {
            let (a, b) = row.split_at(row.len() / 2);
            a != b
        }),
    }
}

/// Checks the inputs `inputs` of one key group of the construction `name`
/// against its constraints.
///
/// Panics with the first constraint they break.
pub fn check(name: &str, inputs: &[RowSet]) {
    if let Some(broken) = constraints(name).iter().find(|c| !meets(c, inputs)) {
        panic!("{name}'s inputs break its domain: {broken}");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Order's check refuses a `before` row that pairs an element with
    /// itself.
    #[test]
    #[should_panic(expected = "no row of input 1 pairs an element with itself")]
    fn order_refuses_a_reflexive_before() {
        let t = Term::encode_number(1);
        let mut before = RowSet::empty(2);
        before.insert([t, t].into());
        let inputs = [RowSet::empty(1), before, RowSet::empty(2), RowSet::empty(1)];
        check(Order::NAME, &inputs);
    }
}
