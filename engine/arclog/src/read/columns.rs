//! The columns of a relation the program declares, derived from the labels
//! of the finished body that declares it: the labels a body keeps, as
//! `docs/arclog/arclog.md#disjunction` gives, and the `^` labels of a key
//! body.

use std::sync::Arc;

use crate::program::*;

use super::labels::LabelScope;
use crate::safety::{body_labels, each_label_use, site_label_uses};

/// The columns of a relation the program declares, which `labels` give.
pub(super) fn relation_columns(labels: &[LabelId], scope: &LabelScope) -> Arc<[RelationColumn]> {
    labels.iter().map(|&label| RelationColumn { name: ColumnName::Written(scope.name(label).into()), label }).collect()
}

fn push_new(out: &mut Vec<LabelId>, label: LabelId) {
    if !out.contains(&label) {
        out.push(label);
    }
}

/// The labels a body keeps, in source order: each that a site or a `=` of
/// its own list makes, and each that an `OR` or an `IF` of its own list
/// exports, as `docs/arclog/arclog.md#disjunction` gives.
pub(super) fn made_labels(body: &Body) -> Vec<LabelId> {
    let mut out = Vec::new();
    for conjunct in body.conjuncts.iter() {
        match conjunct {
            Conjunct::Atom(_) | Conjunct::Constraint(_) => site_label_uses(conjunct, &mut |use_| {
                if let LabelUse::Fresh(label) | LabelUse::Key(label) = use_ {
                    push_new(&mut out, label);
                }
            }),
            Conjunct::Or(branches) => {
                let later: Vec<&Body> = branches[1..].iter().map(|b| b.value()).collect();
                exports(branches[0].value(), &later, &mut out);
            }
            Conjunct::If { then, otherwise, .. } => exports(then.value(), &[otherwise.value()], &mut out),
            Conjunct::Not(_) | Conjunct::All { .. } => {}
        }
    }
    out
}


/// The labels `first` keeps that each of `later` names.
pub(crate) fn exports(first: &Body, later: &[&Body], out: &mut Vec<LabelId>) {
    let named: Vec<_> = later.iter().map(|b| body_labels(b)).collect();
    for label in made_labels(first) {
        if named.iter().all(|set| set.contains(&label)) {
            push_new(out, label);
        }
    }
}


/// The `^` labels of a key body, in order of appearance.
pub(super) fn key_labels(body: &Body) -> Vec<LabelId> {
    let mut out = Vec::new();
    each_label_use(body, &mut |use_| {
        if let LabelUse::Key(label) = use_ {
            push_new(&mut out, label);
        }
    });
    out
}
