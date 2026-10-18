//! The columns of a relation the program declares, derived from the labels
//! of the finished body that declares it: the labels a body keeps, as
//! `docs/arclog/arclog.md#disjunction` gives, and the `^` labels of a key
//! body.

use std::collections::BTreeSet;
use std::sync::Arc;

use crate::program::*;

use super::labels::LabelScope;

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
            Conjunct::Atom(atom) => {
                for site in atom.value().sites.iter() {
                    site_labels(site, &mut |use_| {
                        if let LabelUse::Fresh(label) = use_ {
                            push_new(&mut out, label);
                        }
                    });
                }
            }
            Conjunct::Constraint(constraint) => {
                for label in [Some(constraint.first), constraint_second(constraint)].into_iter().flatten() {
                    if label.fresh {
                        push_new(&mut out, label.label);
                    }
                }
            }
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
fn exports(first: &Body, later: &[&Body], out: &mut Vec<LabelId>) {
    let named: Vec<BTreeSet<u32>> = later.iter().map(|b| body_labels(b)).collect();
    for label in made_labels(first) {
        if named.iter().all(|set| set.contains(&label.0)) {
            push_new(out, label);
        }
    }
}

fn site_labels(site: &Site, visit: &mut dyn FnMut(LabelUse)) {
    for arg in site.value.args.iter() {
        match arg {
            SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => visit(*label),
            SiteArg::Field(field) => site_labels(field, visit),
        }
    }
}

/// Each label use of `body`, at any depth, in source order.
fn each_label(body: &Body, visit: &mut dyn FnMut(LabelUse)) {
    crate::types::each_conjunct(body, &mut |c| match c {
        Conjunct::Atom(a) | Conjunct::Not(Negated::Atom(a)) => {
            a.value().sites.iter().for_each(|site| site_labels(site, visit))
        }
        Conjunct::Constraint(k) => {
            for label in [Some(k.first), constraint_second(k)].into_iter().flatten() {
                visit(label.into());
            }
        }
        _ => {}
    });
}

fn body_labels(body: &Body) -> BTreeSet<u32> {
    let mut out = BTreeSet::new();
    each_label(body, &mut |use_| match use_ {
        LabelUse::Fresh(l) | LabelUse::Join(l) | LabelUse::Key(l) => {
            out.insert(l.0);
        }
        LabelUse::Zero => {}
    });
    out
}

/// The `^` labels of a key body, in order of appearance.
pub(super) fn key_labels(body: &Body) -> Vec<LabelId> {
    let mut out = Vec::new();
    each_label(body, &mut |use_| {
        if let LabelUse::Key(label) = use_ {
            push_new(&mut out, label);
        }
    });
    out
}
