//! The types of a case program: the type check in its module
//! `form_check`, the typing of a program's relations in its module
//! `program_columns`, which hands the check's types to
//! [`super::check_program`], the helpers that the check and the inference
//! of a case program's label types share, in its module `key_rows` the
//! mapping of the key rows of Pose types, and, in its module `within`, the
//! lookups of forms and label scopes that they read.

use super::{CheckResult, ClauseEntry, FileScope, HeldClauses, Refusal, SolverClauses};
use crate::hash::StableHashMap;
use crate::program::canonical::CanonicalOrder;
use crate::program::{ColumnName, Form, LabelId, Site, SiteArg};
use crate::registry::{Column, ColumnType, TypeParameter};
use crate::resolver::registry_columns;
use crate::resolver::Signature;
use crate::types::{use_label, LabelFault, ValueType, ZeroMade};
pub(super) use key_rows::{try_map_key_rows, try_map_labels};
use key_rows::map_labels;
pub(super) use within::{demo_rule, form_at, form_within, rule_scope_forms, scope_forms};
use within::rule_within;

mod form_check;
mod key_rows;
pub(crate) mod own_idents;
mod program_columns;
mod within;

pub use form_check::{infer_form, ScopeTypes, TypesCheck};
pub(super) use program_columns::{program_types, FormScopes};
use form_check::{inferred_scopes, scope_forms_within};

/// The signatures of the clauses that the type check of `form`, a
/// top-level form whose canonical order is `order`, reads, as
/// [`crate::check::CheckId::Types`] gives, each once: for a clause, those of the clauses
/// of its relation, then, for each clause form that stands in a label scope
/// of the form, as [`CanonicalOrder::label_scopes`] gives them, in their
/// order, where it has a head label that only `(= *X 0)` gives a type,
/// those of the clauses of its
/// relation in all of the solver's case programs, each relation's in the
/// order [`SolverClauses`] gives. Otherwise the clauses of a relation are
/// those that the case program of `held` holds.
pub fn type_clause_signatures<'a>(form: &Form, order: &CanonicalOrder, clauses: &'a SolverClauses, held: &'a HeldClauses) -> impl Iterator<Item = &'a Signature> {
    let mut signatures: Vec<&'a Signature> = Vec::new();
    let mut add = |entries: &mut dyn Iterator<Item = &'a ClauseEntry>| {
        for entry in entries {
            if !signatures.contains(&&entry.signature) {
                signatures.push(&entry.signature);
            }
        }
    };
    if let Form::Clause(clause) = form {
        add(&mut clauses.of_relation_in(&clause.value().derives, held));
    }
    for source in inferred_scopes(order) {
        for (_, found) in scope_forms_within(form, &source) {
            if let Form::Clause(clause) = found {
                if !zero_typed_heads(clause.value()).is_empty() {
                    add(&mut clauses.of_relation(&FileScope::Program, &clause.value().derives).iter());
                }
            }
        }
    }
    signatures.into_iter()
}

/// The head labels of `clause` that only `(= *X 0)` gives a type: each
/// stands at no site of an atom and is made by such a constraint.
pub(super) fn zero_typed_heads(clause: &crate::program::Clause) -> Vec<LabelId> {
    let ZeroMade { zeroed, at_sites } = ZeroMade::of(clause.body.value());
    let heads = clause.columns.iter().map(|column| column.label);
    heads.filter(|label| zeroed.contains(&(*label, true)) && !at_sites.contains(label)).collect()
}

/// A pass, or a refusal of each of `refusals`.
pub(super) fn result(refusals: Vec<Refusal>) -> CheckResult {
    if refusals.is_empty() {
        CheckResult::Pass
    } else {
        CheckResult::Refuse(refusals.into())
    }
}

/// The Pose type of the label that `fault` is of, where one of its sites
/// gives it one.
pub(super) fn pose_of_fault(fault: &LabelFault) -> Option<&ValueType> {
    match fault {
        LabelFault::EmptyMeet(a, b) => [a, b].into_iter().find(|ty| matches!(ty, ValueType::Pose(_))),
        LabelFault::NoJoin(..) => None,
    }
}

/// The types of the columns that a value of type `ty` takes, in their
/// order: a record's fields, each a column of its own, or `ty`.
fn flatten(ty: ValueType, out: &mut Vec<ValueType>) {
    match ty {
        ValueType::Record(fields) => fields.into_vec().into_iter().for_each(|(_, field)| flatten(field, out)),
        ty => out.push(ty),
    }
}

/// The types of the columns of a relation whose columns are `names`, in
/// their order, each name's type as `column` gives it and a record's fields
/// each a column of its own, or `None` where `column` gives a name no type.
pub(super) fn relation_columns<'n>(names: impl IntoIterator<Item = &'n ColumnName>, column: &dyn Fn(&ColumnName) -> Option<ValueType>) -> Option<Box<[ValueType]>> {
    let mut out = Vec::new();
    for name in names {
        flatten(column(name)?, &mut out);
    }
    Some(out.into())
}

/// The type at `rest` of a value of type `ty`: a record's field for each
/// step, and `ty` itself past a type that is no record, as a bare label's
/// name after a column of a type parameter bound to one label's type.
pub(super) fn project(ty: &ValueType, rest: &[ColumnName]) -> Option<ValueType> {
    match (ty, rest) {
        (ValueType::Record(fields), [field, rest @ ..]) => project(&fields.iter().find(|(found, _)| found == field)?.1, rest),
        (ty, _) => Some(ty.clone()),
    }
}

/// How a site's column type reads the Pose type a lib column may take.
#[derive(Clone, Copy, PartialEq, Eq)]
pub(super) enum PoseOr {
    /// A column of `(pose-or <type>)` gives no type, so its label takes its
    /// Pose type from its other sites.
    Open,
    /// Such a column gives its type, for a label that no other site gives
    /// one.
    Given,
}

/// The type a declared column of the type `ty` gives a site at `rest`
/// below the column, with `bindings` binding the type parameters.
pub(super) fn column_type(ty: &ColumnType, rest: &[ColumnName], bindings: &StableHashMap<TypeParameter, ValueType>, pose_or: PoseOr) -> Option<ValueType> {
    match ty {
        ColumnType::Fixed(ty) => Some(ty.clone()),
        ColumnType::PoseOr(ty) => (pose_or == PoseOr::Given).then(|| ty.clone()),
        ColumnType::Pose | ColumnType::SharedPose => None,
        ColumnType::Parameter(parameter) => project(bindings.get(parameter)?, rest),
    }
}

/// The type the column at `path` of `columns` gives a site.
pub(super) fn declared_type(columns: &[Column], path: &[ColumnName], pose_or: PoseOr) -> Option<ValueType> {
    let (first, rest) = path.split_first()?;
    column_type(&columns.iter().find(|column| column.name == *first)?.ty, rest, &StableHashMap::default(), pose_or)
}

pub(super) use registry_columns::component;

/// The type of the value at `site` of a head or of a read: its one bare
/// label's type, or a record with a field per argument.
pub(super) fn site_value_type(site: &Site, label: &dyn Fn(LabelId) -> Option<ValueType>) -> Option<ValueType> {
    site_value_type_or(site, &[], label, &|_| None)
}

/// [`site_value_type`], except that a label with no type, at the field path
/// `path` below `site`, takes the type `missing` gives that path.
pub(super) fn site_value_type_or(
    site: &Site,
    path: &[ColumnName],
    label: &dyn Fn(LabelId) -> Option<ValueType>,
    missing: &dyn Fn(&[ColumnName]) -> Option<ValueType>,
) -> Option<ValueType> {
    match &site.value.args[..] {
        [SiteArg::Label(use_) | SiteArg::NamedLabel { label: use_, .. }] => label(use_label(*use_)?).or_else(|| missing(path)),
        args => {
            let at = |name: &ColumnName| -> Vec<ColumnName> { path.iter().chain(std::iter::once(name)).cloned().collect() };
            let field = |arg: &SiteArg| match arg {
                SiteArg::NamedLabel { name, label: use_ } => Some((name.clone(), label(use_label(*use_)?).or_else(|| missing(&at(name)))?)),
                SiteArg::Field(field) => Some((field.column.clone(), site_value_type_or(field, &at(&field.column), label, missing)?)),
                SiteArg::Label(_) => None,
            };
            Some(ValueType::Record(args.iter().map(field).collect::<Option<_>>()?))
        }
    }
}
