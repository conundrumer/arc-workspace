//! The judge's comparison of a case's output on a pair with the pair's
//! candidates, as `docs/engine/cases.md#judge` gives: the candidates of a
//! pair in [`candidates`], and the output set of a case on a pair, the
//! solves test and the enumeration's stops in [`solves`], and the judged
//! run of a case, its grid columns and its output set on each pair, in
//! [`run`]. [`determination`] gives the values of a solver's `DET`s from
//! the train pairs that its base cases solve.

pub mod candidates;
pub mod determination;
pub mod run;
pub mod solves;
