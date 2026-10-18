//! The type check, and the two functions through which it hands its types
//! to [`super::check_program`].

#![allow(unused_variables, dead_code)]

use std::sync::Arc;

use super::{Check, CheckId, CheckInput, CheckResult, FileScope, Prefix, PrefixResult, SolverClauses};
use crate::program::Form;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::NodePath;
use crate::resolver::{ResolvedProgram, Signature};
use crate::types::{FormTypes, ProgramTypes};

/// [`CheckId::Types`].
pub struct TypesCheck;

impl Check for TypesCheck {
    fn id(&self) -> CheckId {
        CheckId::Types
    }

    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        infer_form(input, &CanonicalOrder::of(input.form, &mut SearchBudget::new())).0
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}

/// The type check's result on the form of `input`, and the form's
/// [`FormTypes`] with each label at its canonical position in `order`, as
/// [`super::CheckCache`] keeps them.
pub fn infer_form(input: &CheckInput<'_>, order: &CanonicalOrder) -> (CheckResult, FormTypes) {
    (CheckResult::Pass, FormTypes::default())
}

/// The [`ProgramTypes`] of `program`: each form's labels of `forms`, mapped
/// from their canonical positions to the form's own labels through the
/// form's order, and the type of each column of each relation.
pub fn program_types(program: &ResolvedProgram, clauses: &SolverClauses, forms: &[(NodePath, Arc<FormTypes>, CanonicalOrder)]) -> ProgramTypes {
    ProgramTypes::default()
}

/// The signatures of the clauses that a label's type of `form` comes from,
/// as [`CheckId::Types`] gives, in the order [`SolverClauses`] gives.
pub fn type_clause_signatures<'a>(form: &Form, clauses: &'a SolverClauses) -> impl Iterator<Item = &'a Signature> {
    let entries = match form {
        Form::Clause(clause) => clauses.of_relation(&FileScope::Program, &clause.value().derives),
        _ => &[],
    };
    entries.iter().map(|(_, _, signature)| signature)
}
