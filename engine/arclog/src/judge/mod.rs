//! The judge's comparison of a case's output on a pair with the pair's
//! candidates, as `docs/engine/cases.md#judge` gives: the candidates of a
//! pair in [`candidates`], and the output set of a case on a pair, the
//! solves test and the enumeration's stops in [`solves`], and the judged
//! run of a case, its grid columns and its output set on each pair, in
//! [`run`].

pub mod candidates;
pub mod run;
pub mod solves;
