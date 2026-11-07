//! The check of the rules on `=` and `0`, as
//! `docs/arclog/arclog.md#negation-and-constraints` gives them, and the
//! signatures of the clauses that its result on a clause reads.

use super::safety::{form_bodies, label_scope, FormBody};
use super::types::{result, PoseOr};
use super::{each_node, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, Scope, SolverClauses, CheckCacheKey, KeyInput};
use crate::program::path::{node_at, NodePath, NodeRef, PathStep};
use crate::program::canonical::{prediction, relation_of};
use crate::program::{constraint_second, Body, ChoosePart, Clause, ClauseKeyword, ColumnName, Conjunct, Constraint, ConstraintOp, Form, LabelId, LabelUse, Operand, RigidDetPart, SiteArg};
use crate::read::columns::exports;
use crate::resolver::Signature;
use crate::safety::{list_of, site_label_uses};
use crate::types::ValueType;

/// [`CheckId::EqualityAndZero`].
pub struct EqualityAndZeroCheck;

impl Check for EqualityAndZeroCheck {
    fn id(&self) -> CheckId {
        CheckId::EqualityAndZero
    }

    /// The base key with, after its signatures, those of the clauses of the
    /// form's relation across the solver's blocks, as
    /// `zero_clause_signatures` gives them.
    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        let mut key = at.base(self.id());
        let signatures = key.signatures.iter().cloned().chain(zero_clause_signatures(at.form, at.clauses).cloned());
        key.signatures = signatures.collect();
        Some(key)
    }

    /// Refuses:
    ///
    /// - a `(= *X 0)` at the top level of a clause's body, where each
    ///   clause of the relation in the solver, as [`SolverClauses`] gives
    ///   them across its blocks, holds such a constraint on the label of
    ///   the same column, so that the column is `0` in every clause;
    /// - a constraint whose second label is `0`, under any operator, where
    ///   the type of its first label is fixed and is neither a number nor a
    ///   Box;
    /// - a site that holds `0` on a column whose type is fixed and is
    ///   neither a number nor a Box, on a relation of any kind that the
    ///   site reads, and a field site that holds `0` on such a field of a
    ///   record;
    /// - a `=` whose second label is made, `(= Y *X)`;
    /// - a `(= X Y)` whose first label a site or a `=` of its own list
    ///   makes, where `Y` is no label it makes;
    /// - a `(= *V Y)` at the top level of a body, or in an `OR`'s first
    ///   branch or an `IF`'s then, whose label `Y` a site of a positive atom
    ///   of the same list makes, where that site could make `V`. In the first
    ///   branch of an `OR` that is a body's one conjunct, the `OR` may export
    ///   `V`, and the check refuses the `=` only where it does not.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let mut refused = rule_refusals(input.form, input.path, &input.scope, &|_| false);
        refused.extend(head_zero(input.form, input.scope.clauses));
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        result(refused.into_iter().map(|refusal| Refusal { at: input.refusal_path(&refusal.at), ..refusal }).collect())
    }

    /// The refusals of each complete node of the partial form, and, since
    /// each relation of a decode has one clause, each complete `(= *X 0)` at
    /// the top level of a `RULE` or a `DET`, and of each list that
    /// [`inner_zeros`] gives. An `=` in the first branch of
    /// an `OR` that is the one conjunct so far of an open body is
    /// undecided, since the body may yet take a conjunct or the `OR` export
    /// its label. A site that holds `0` on a column with no `0` is refused
    /// while it stands open too: it takes no other label, and the type of
    /// its column, which the forms before it and the registry fix, does not
    /// change.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        let mut refused = rule_refusals(prefix.partial, prefix.path, &prefix.scope, &|at| prefix.is_open(at));
        if let Form::Clause(clause) = prefix.partial {
            if matches!(clause.value().keyword, ClauseKeyword::Rule | ClauseKeyword::Det) {
                let zeros = top_level_zeros(clause.value()).into_iter().map(|(at, _)| at);
                refused.extend(zeros.map(|at| refusal(HEAD_ZERO, at)));
            }
        }
        refused.extend(inner_zeros(prefix.partial).into_iter().map(|at| refusal(INNER_ZERO, at)));
        super::prefix::refused(refused.into_iter().filter(|refusal| !prefix.is_open(&refusal.at) || *refusal.message == *ZERO_ON).collect())
    }
}

const HEAD_ZERO: &str = "the column is `0` in every clause of the relation, so the relation drops it";
const ZERO_ON: &str = "`0` stands only on a column of a number or a Box";
const ZERO_ON_FIELD: &str = "`0` stands only on a field of a number or a Box";
const INNER_ZERO: &str = "a `(= *X 0)` at the top level of a `CHOOSE` form's `from`, a `RIGID_DET` form's `instance` clause or a clause of a `DEMO_RULE` makes a column that is `0` in every clause";
const ZERO_AGAINST: &str = "`0` stands only as the second label of a constraint whose first label is a number or a Box";

/// Whether the second label of `constraint` is one it makes, `*X`.
pub(super) fn second_made(constraint: &Constraint) -> bool {
    constraint_second(constraint).is_some_and(|label| label.fresh)
}

fn refusal(message: &str, at: NodePath) -> Refusal {
    Refusal { message: message.into(), at }
}

/// The signatures of the clauses of the relation that `form`, a clause,
/// derives, across the solver's blocks, which the check of `form` reads.
pub(super) fn zero_clause_signatures<'c>(form: &Form, clauses: &'c SolverClauses) -> impl Iterator<Item = &'c Signature> {
    let entries = match form {
        Form::Clause(clause) if !top_level_zeros(clause.value()).is_empty() => clauses.of_relation(&super::FileScope::Program, &clause.value().derives),
        _ => &[],
    };
    entries.iter().map(|entry| &entry.signature)
}

/// Each `(= *X 0)` at the top level of the body of `clause`, at its path
/// relative to the clause, with the label it makes.
fn top_level_zeros(clause: &Clause) -> Vec<(NodePath, LabelId)> {
    let body = NodePath::default().child(0);
    let zero = |(at, conjunct): (NodePath, &Conjunct)| match conjunct {
        Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second: Operand::Zero }) if first.fresh => Some((at, first.label)),
        _ => None,
    };
    list_of(clause.body.value(), &body).into_iter().filter_map(zero).collect()
}

/// Each `(= *X 0)` at the top level of a list of `form` whose labels its form
/// or its clause has as columns, other than the form's own clause: a
/// `CHOOSE` form's `from`, a `RIGID_DET` form's `instance` clause, and a
/// `RULE` or a `DET` of a `DEMO_RULE`, but its `&prediction` clause, whose
/// columns the `DEMONSTRATED` form fixes as a component fixes an input's.
/// Each is at its path relative to `form`. A decode gives each such list's
/// relation no other clause, so the column is `0` in every clause of it
/// (`docs/arclog/arclog.md#negation-and-constraints`).
fn inner_zeros(form: &Form) -> Vec<NodePath> {
    let mut out = Vec::new();
    let mut zeros = |body: &Body, at: NodePath| {
        for (at, conjunct) in list_of(body, &at) {
            if let Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second: Operand::Zero }) = conjunct {
                if first.fresh {
                    out.push(at);
                }
            }
        }
    };
    for (at, node) in super::reads::forms_within(form) {
        match node {
            NodeRef::Clause(clause) if !at.0.is_empty() && matches!(clause.keyword, ClauseKeyword::Rule | ClauseKeyword::Det) && relation_of(&clause.derives) != prediction() => {
                zeros(clause.body.value(), at.child(0));
            }
            NodeRef::Choose(choose) => zeros(choose.from.value(), at.child(choose.position(ChoosePart::From))),
            NodeRef::RigidDet(rigid) => {
                if let Some(instance) = &rigid.instance {
                    zeros(instance.body.value(), at.child(rigid.position(RigidDetPart::Instance)));
                }
            }
            _ => {}
        }
    }
    out
}

/// The names of the columns of `clause` that a `(= *X 0)` at the top level
/// of its body makes.
fn zero_columns(clause: &Clause) -> Vec<&crate::program::ColumnName> {
    let zeros = top_level_zeros(clause);
    clause.columns.iter().filter(|column| zeros.iter().any(|(_, label)| *label == column.label)).map(|column| &column.name).collect()
}

/// The refusals of the head-zero rule on `form`, at their source paths.
fn head_zero(form: &Form, clauses: &SolverClauses) -> Vec<Refusal> {
    let Form::Clause(clause) = form else { return Vec::new() };
    let clause = clause.value();
    let zeros = top_level_zeros(clause);
    if zeros.is_empty() {
        return Vec::new();
    }
    let others: Vec<Vec<&crate::program::ColumnName>> = clauses
        .of_relation(&super::FileScope::Program, &clause.derives)
        .iter()
        .filter_map(|entry| match node_at(NodeRef::Program(clauses.program(entry).program.value()), &entry.at) {
            Some(NodeRef::Clause(other)) => Some(zero_columns(other)),
            _ => None,
        })
        .collect();
    let mut refused = Vec::new();
    for (at, label) in zeros {
        let Some(column) = clause.columns.iter().find(|column| column.label == label) else { continue };
        if others.iter().all(|zeroed| zeroed.contains(&&column.name)) {
            refused.push(refusal(HEAD_ZERO, at));
        }
    }
    refused
}

/// The refusals of the rules on `=` and `0` but the head-zero rule, at
/// their source paths, on `form`, the top-level form at `path`. A union
/// `OR` at a path that `open` holds is undecided.
fn rule_refusals(form: &Form, path: &NodePath, scope: &Scope<'_>, open: &dyn Fn(&NodePath) -> bool) -> Vec<Refusal> {
    let mut refused = Vec::new();
    each_node(NodeRef::from(form), &NodePath::default(), &mut |node, at| match node {
        NodeRef::Conjunct(Conjunct::Constraint(constraint)) if constraint.op == ConstraintOp::Eq && second_made(constraint) => {
            refused.push(refusal("`=` makes its first label only", at.into()));
        }
        NodeRef::Conjunct(Conjunct::Constraint(Constraint { first, second: Operand::Zero, .. })) => {
            let at = NodePath::from(at);
            let label = label_scope(scope.labels, &at).into_iter().find(|entry| entry.label == first.label);
            if label.and_then(|entry| entry.ty.as_ref()).is_some_and(|ty| !ty.has_zero()) {
                refused.push(refusal(ZERO_AGAINST, at));
            }
        }
        NodeRef::Conjunct(conjunct @ (Conjunct::Atom(_) | Conjunct::Not(_))) => {
            if let Some(atom) = conjunct.atom() {
                zero_sites(atom.value(), path, at, scope, &mut refused);
            }
        }
        _ => {}
    });
    for form_body in form_bodies(form) {
        let union = matches!(&form_body.body.value().conjuncts[..], [Conjunct::Or(_)]);
        let union_open = union && open(&form_body.at);
        same_list(form_body.body.value(), &form_body.at, &mut refused);
        lists(&form_body, union, union_open, &mut refused);
    }
    refused
}

/// Pushes onto `refused` each site of `atom`, at `at` of the form at
/// `path`, that holds `0` on a column whose type is fixed and has no `0`,
/// and each field site of a site on a record that holds `0` on a field
/// whose type is fixed and has no `0`, since the rule on sites applies at
/// every level (`docs/arclog/arclog.md#sites`).
fn zero_sites(atom: &crate::program::Atom, path: &NodePath, at: &[PathStep], scope: &Scope<'_>, refused: &mut Vec<Refusal>) {
    let at = NodePath::from(at);
    let no_zero = |columns: &[ColumnName]| column_type(atom, path, &at, columns, scope).is_some_and(|ty| !ty.has_zero());
    for (site, index) in atom.sites.iter().zip(0u32..) {
        if matches!(&site.value.args[..], [SiteArg::Label(LabelUse::Zero)]) {
            if no_zero(std::slice::from_ref(&site.column)) {
                refused.push(refusal(ZERO_ON, at.child(index)));
            }
            continue;
        }
        for (arg, field) in site.value.args.iter().zip(0u32..) {
            let name = match arg {
                SiteArg::NamedLabel { name, label: LabelUse::Zero } => name,
                SiteArg::Field(inner) if matches!(&inner.value.args[..], [SiteArg::Label(LabelUse::Zero)]) => &inner.column,
                _ => continue,
            };
            if no_zero(&[site.column.clone(), name.clone()]) {
                refused.push(refusal(ZERO_ON_FIELD, at.child(index).child(field)));
            }
        }
    }
}

/// The fixed type of the column at `columns`, a column and a field of its
/// record where it holds one, of the relation that `atom`, at `at` of the
/// form at `path`, reads, as the type inference gives it in the scope that
/// holds the atom: the form, or a `DEMO_RULE` within it. The scopes are
/// tried from the innermost, the longest prefix of `at`.
fn column_type(atom: &crate::program::Atom, path: &NodePath, at: &NodePath, columns: &[ColumnName], scope: &Scope<'_>) -> Option<ValueType> {
    (0..=at.0.len()).rev().find_map(|depth| {
        let form = scope.inference.infer(&path.join(&NodePath(at.0[..depth].into())))?;
        scope.inference.site_type(form.reading(PoseOr::Open), atom, columns)
    })
}

/// Pushes onto `refused` each `(= X Y)` of the list `body`, at `at`, whose
/// first label a site or a `=` of the list makes and whose second label it
/// does not make, and so for each list below it.
fn same_list(body: &Body, at: &NodePath, refused: &mut Vec<Refusal>) {
    let list = list_of(body, at);
    let mut made = Vec::new();
    for (_, conjunct) in &list {
        if matches!(conjunct, Conjunct::Atom(_) | Conjunct::Constraint(_)) {
            site_label_uses(conjunct, &mut |use_| {
                if let LabelUse::Fresh(label) | LabelUse::Key(label) = use_ {
                    made.push(label);
                }
            });
        }
    }
    for (at, conjunct) in &list {
        match conjunct {
            Conjunct::Constraint(constraint @ Constraint { op: ConstraintOp::Eq, first, .. }) if !first.fresh && !second_made(constraint) && made.contains(&first.label) => {
                refused.push(refusal("a site of the list makes the label, so the site names its partner", at.clone()));
            }
            _ => {
                each_body(conjunct, at, &mut |body, at| same_list(body, at, refused));
            }
        }
    }
}

/// Visits each list below `conjunct`, at `at`, that no list below it holds:
/// the branches of an `OR`, the test, the then and the else of an `IF`,
/// the lists of an `ALL`, and those of the form of a `NOT`.
fn each_body(conjunct: &Conjunct, at: &NodePath, visit: &mut dyn FnMut(&Body, &NodePath)) {
    for (child, index) in NodeRef::Conjunct(conjunct).children().into_iter().zip(0u32..) {
        match child {
            NodeRef::Body(body) => visit(body, &at.child(index)),
            NodeRef::Conjunct(inner) => each_body(inner, &at.child(index), visit),
            _ => {}
        }
    }
}

/// Pushes onto `refused` each `(= *V Y)` at the top level of `form_body`, or
/// in an `OR`'s first branch or an `IF`'s then within it, whose `Y` a site
/// of a positive atom of the same list makes. `union` holds where the body's
/// one conjunct is an `OR`, whose first branch may make `V` where the `OR`
/// exports it, and `union_open` where the body is open, so that its first
/// branch is undecided.
fn lists(form_body: &FormBody<'_>, union: bool, union_open: bool, refused: &mut Vec<Refusal>) {
    fn walk(body: &Body, at: &NodePath, top: Option<(bool, bool)>, refused: &mut Vec<Refusal>) {
        for (at, conjunct) in list_of(body, at) {
            match conjunct {
                Conjunct::Or(branches) => {
                    let exported = |label| {
                        let later: Vec<&Body> = branches[1..].iter().map(|b| b.value()).collect();
                        let mut out = Vec::new();
                        exports(branches[0].value(), &later, &mut out);
                        out.contains(&label)
                    };
                    match top {
                        Some((_, true)) => {}
                        Some((true, false)) => made_from_site(branches[0].value(), &at.child(0), &|label| !exported(label), MADE_IN_BRANCH, refused),
                        _ => made_from_site(branches[0].value(), &at.child(0), &|_| true, MADE_IN_BRANCH, refused),
                    }
                }
                Conjunct::If { then, .. } => made_from_site(then.value(), &at.child(1), &|_| true, MADE_IN_BRANCH, refused),
                _ => {}
            }
            each_body(conjunct, &at, &mut |body, at| walk(body, at, None, refused));
        }
    }
    // At the top level of a body, the `=` makes a column of the clause or a label of the body that a head site
    // projects, which the site that makes `Y` could make as well.
    made_from_site(form_body.body.value(), &form_body.at, &|_| true, MADE_AT_TOP, refused);
    walk(form_body.body.value(), &form_body.at, Some((union, union_open)), refused);
}

const MADE_IN_BRANCH: &str = "a site of the list makes the second label, so it could make the first";
const MADE_AT_TOP: &str = "at the top level of a body, a site of the list makes the second label of `=`, so it could make the first";

/// Pushes onto `refused`, with `message`, each `(= *V Y)` of the list
/// `body`, at `at`, whose `Y` a site of a positive atom of the list makes, a
/// site of one label on a column of a fixed type, where `refuse` holds for
/// `V`.
fn made_from_site(body: &Body, at: &NodePath, refuse: &dyn Fn(LabelId) -> bool, message: &str, refused: &mut Vec<Refusal>) {
    let list = list_of(body, at);
    let mut made = Vec::new();
    for (_, conjunct) in &list {
        if let Conjunct::Atom(atom) = conjunct {
            for site in atom.value().sites.iter() {
                if let [SiteArg::Label(LabelUse::Fresh(label))] = &site.value.args[..] {
                    made.push(*label);
                }
            }
        }
    }
    for (at, conjunct) in list {
        if let Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second: Operand::Label(second) }) = conjunct {
            if first.fresh && !second.fresh && made.contains(&second.label) && refuse(first.label) {
                refused.push(refusal(message, at));
            }
        }
    }
}
