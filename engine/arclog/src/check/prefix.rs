//! The prefixes of a form, the run of the checks of [`super::checks`] on a
//! prefix, and the rule by which a check's refusals of a partial form stand
//! as refusals of the prefix.

use std::sync::Arc;

use super::{checks, inference, labels_in_scopes, typed_labels, types, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, Scope, SolverClauses};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{node_at, NodePath, NodeRef, PathStep};
use crate::program::{Atom, Body, Choose, Clause, Conjunct, Form, Instance, InstanceInput, KeyBody, KeyClause, LabelUse, Negated, Node, RigidDet, Site, SiteArg, SiteValue};
use crate::registry::Registry;
use crate::resolver::ResolvedProgram;
use crate::types::each_site_label;

/// A prefix of a form: its partial form, as [`Prefix`] gives it, and the
/// path there of the node at whose end the prefix stands.
#[derive(Clone, Debug)]
pub struct FormPrefix {
    pub partial: Form,
    pub end: NodePath,
}

impl FormPrefix {
    /// The open node, as [`Prefix`] gives it: the node above the end, or
    /// none where the prefix ends at the form.
    pub fn open(&self) -> Option<NodePath> {
        self.end.0.split_last().map(|(_, above)| NodePath(above.into()))
    }
}

/// Each prefix of `form`, one at the end of each of its nodes, in the order
/// in which a token stream ends them: the nodes the stream writes before
/// that node and the node itself, with each node above it open, and the
/// last prefix `form` itself. The stream writes the source's order, but for
/// an instance input's body, which it writes before the head sites that
/// project its labels. A node of a claim, an `ALTS` form or a
/// `DEMONSTRATED` form ends no prefix of its own, since no token stream
/// holds one.
///
/// A list that the prefix has not reached stands empty, and an open clause,
/// key body or `CHOOSE` form holds no columns yet, since the columns of a
/// clause follow its body.
pub fn prefixes(form: &Form) -> Vec<FormPrefix> {
    let mut ends = Vec::new();
    each_end(NodeRef::from(form), NodePath::default(), &mut ends);
    let prefix = |at: NodePath| FormPrefix { partial: cut_form(form, &at.0), end: partial_path(form, &at) };
    ends.into_iter().map(prefix).collect()
}

/// Pushes onto `out` the path of each node of `node`, at `at`, after the
/// paths of its children, each input's body before its head sites.
fn each_end(node: NodeRef<'_>, at: NodePath, out: &mut Vec<NodePath>) {
    if !matches!(node, NodeRef::Claim(_) | NodeRef::Alts(_) | NodeRef::Demonstrated(_)) {
        let mut children: Vec<(NodeRef<'_>, u32)> = node.children().into_iter().zip(0u32..).collect();
        if let NodeRef::InstanceInput(_) = node {
            children.rotate_right(1);
        }
        for (child, index) in children {
            each_end(child, at.child(index), out);
        }
    }
    out.push(at);
}

/// The path, in the prefix of `form` that ends at the node at `at`, of that
/// node: `at`, but at an input whose body the prefix ends in, which stands
/// first while the input holds no head site.
fn partial_path(form: &Form, at: &NodePath) -> NodePath {
    let mut within = Vec::new();
    for (depth, step) in at.0.iter().enumerate() {
        let above = node_at(NodeRef::from(form), &NodePath(at.0[..depth].into()));
        match above {
            Some(NodeRef::InstanceInput(input)) if step.0 as usize == input.head.len() => within.push(PathStep(0)),
            _ => within.push(*step),
        }
    }
    NodePath(within.into())
}

/// The result of each check of [`checks`] on the prefix whose partial form
/// is the last top-level form of `program`, with the earlier forms
/// complete, and whose open node is at `open`. `clauses` holds the clauses
/// of `program`'s solver, or of `program` alone for a synthesized program.
pub fn check_prefix(program: &ResolvedProgram, clauses: &SolverClauses, registry: &Registry, open: Option<&NodePath>) -> Vec<(CheckId, PrefixResult)> {
    let (partial, complete) = program.program.value().forms.split_last().expect("a prefix's program holds its partial form");
    let path = NodePath::top(complete.len() as u32);
    let cases = inference::CaseInferences::new(clauses, registry);
    let inference = inference::Inference::new(program, &cases);
    let scope = |labels| Scope { program, registry, labels, clauses, inference: &inference, files: None };
    let order = CanonicalOrder::of(partial, &mut SearchBudget::new());
    let untyped = labels_in_scopes(&order, &|_, _| None);
    let (_, form_types) = types::infer_form(&CheckInput { form: partial, path: &path, scope: scope(&untyped) }, &order);
    let labels = typed_labels(&order, &form_types);
    let prefix = Prefix { complete, partial, path: &path, open, scope: scope(&labels) };
    checks().iter().map(|check| (check.id(), check.check_prefix(&prefix))).collect()
}

/// The input of a check over the whole partial form of `prefix`.
pub(super) fn whole<'a>(prefix: &Prefix<'a>) -> CheckInput<'a> {
    CheckInput { form: prefix.partial, path: prefix.path, scope: prefix.scope }
}

/// The refusals of `check` on the whole partial form of `prefix` that stand
/// at a complete node, as the prefix's refusals: those of a check whose
/// refusal of a node no node written after it undoes.
pub(super) fn settled(prefix: &Prefix<'_>, check: &dyn Check) -> PrefixResult {
    settled_result(prefix, check.check(&whole(prefix)))
}

/// The refusals of `result`, a check's result on the whole partial form of
/// `prefix`, that stand at a complete node.
pub(super) fn settled_result(prefix: &Prefix<'_>, result: CheckResult) -> PrefixResult {
    standing(prefix, result, &|at| !prefix.is_open(at))
}

/// The refusals of `result`, a check's result on the whole partial form of
/// `prefix`, at each path that `stands` keeps, each at its source path
/// relative to the partial form.
pub(super) fn standing(prefix: &Prefix<'_>, result: CheckResult, stands: &dyn Fn(&NodePath) -> bool) -> PrefixResult {
    let CheckResult::Refuse(refusals) = result else { return PrefixResult::Undecided };
    let order = CanonicalOrder::of(prefix.partial, &mut SearchBudget::new());
    let source = refusals.iter().map(|refusal| Refusal { message: refusal.message.clone(), at: order.source_path(&refusal.at) });
    refused(source.filter(|refusal| stands(&refusal.at)).collect())
}

/// A refusal of each of `refusals`, or undecided where it holds none.
pub(super) fn refused(refusals: Vec<Refusal>) -> PrefixResult {
    if refusals.is_empty() {
        PrefixResult::Undecided
    } else {
        PrefixResult::Refuse(refusals.into())
    }
}

/// `form` cut to the prefix that ends at the node at `path`: the nodes
/// before it in the source, the node itself, and the nodes above it, each
/// open.
fn cut_form(form: &Form, path: &[PathStep]) -> Form {
    let Some((step, rest)) = path.split_first() else { return form.clone() };
    let index = step.0 as usize;
    match form {
        Form::Clause(clause) => {
            let clause = clause.value();
            Form::Clause(Node::new(Clause { body: cut_body(&clause.body, rest), ones: Arc::from([]), columns: Arc::from([]), ..clause.clone() }))
        }
        Form::Instance(instance) => {
            let instance = instance.value();
            let (key, inputs) = match &instance.key {
                Some(key) if index == 0 => (Some(Node::new(cut_key_clause(key.value(), rest))), Arc::from([])),
                key => (key.clone(), cut_list(&instance.inputs, index - usize::from(key.is_some()), |input| cut_input(input, rest))),
            };
            Form::Instance(Node::new(Instance { key, inputs, ..instance.clone() }))
        }
        Form::Choose(choose) => Form::Choose(Node::new(cut_choose(choose.value(), index, rest))),
        Form::RigidDet(rigid) => Form::RigidDet(Node::new(cut_rigid(rigid.value(), index, rest))),
        Form::Claim(_) | Form::Alts(_) | Form::Demonstrated(_) => unreachable!("no prefix ends at a node of a claim, an `ALTS` form or a `DEMONSTRATED` form"),
    }
}

fn cut_key_clause(clause: &KeyClause, path: &[PathStep]) -> KeyClause {
    let Some((step, rest)) = path.split_first() else { return clause.clone() };
    match step.0 {
        0 => KeyClause { key: cut_key_body(&clause.key, rest), inputs: Arc::from([]) },
        index => KeyClause { key: clause.key.clone(), inputs: cut_list(&clause.inputs, index as usize - 1, |input| cut_input(input, rest)) },
    }
}

fn cut_input(input: &Node<InstanceInput>, path: &[PathStep]) -> Node<InstanceInput> {
    let Some((step, rest)) = path.split_first() else { return input.clone() };
    let input = input.value();
    let index = step.0 as usize;
    let cut = if index < input.head.len() {
        InstanceInput { head: cut_list(&input.head, index, |site| cut_site(site, rest)), ..input.clone() }
    } else {
        InstanceInput { head: Arc::from([]), body: cut_body(&input.body, rest), ..input.clone() }
    };
    Node::new(cut)
}

fn cut_choose(choose: &Choose, index: usize, rest: &[PathStep]) -> Choose {
    let open = Choose { candidate_columns: Arc::from([]), ..choose.clone() };
    match (&choose.rows, index) {
        (Some(rows), 0) => Choose { rows: Some(cut_key_body(rows, rest)), from: empty(), never: Arc::from([]), ..open },
        (rows, index) => match index - usize::from(rows.is_some()) {
            0 => Choose { from: cut_body(&choose.from, rest), never: Arc::from([]), ..open },
            never => Choose { never: cut_list(&choose.never, never - 1, |body| cut_body(body, rest)), ..open },
        },
    }
}

fn cut_rigid(rigid: &RigidDet, index: usize, rest: &[PathStep]) -> RigidDet {
    let none = |clause: &Option<KeyBody>| clause.as_ref().map(|_| KeyBody { body: empty(), columns: Arc::from([]) });
    let key = usize::from(rigid.key.is_some());
    let instance = usize::from(rigid.instance.is_some());
    if rigid.key.is_some() && index == 0 {
        let key = rigid.key.as_ref().map(|clause| cut_key_body(clause, rest));
        return RigidDet { key, instance: none(&rigid.instance), parts: Arc::from([]), ..rigid.clone() };
    }
    if rigid.instance.is_some() && index == key {
        let instance = rigid.instance.as_ref().map(|clause| cut_key_body(clause, rest));
        return RigidDet { instance, parts: Arc::from([]), ..rigid.clone() };
    }
    let parts = cut_list(&rigid.parts, index - key - instance, |part| Node::new(cut_atom(part.value(), rest)));
    RigidDet { parts, ..rigid.clone() }
}

/// A key body cut at `path`, which holds no columns yet where it is open.
fn cut_key_body(clause: &KeyBody, path: &[PathStep]) -> KeyBody {
    if path.is_empty() {
        return clause.clone();
    }
    KeyBody { body: cut_body(&clause.body, path), columns: Arc::from([]) }
}

fn cut_body(body: &Node<Body>, path: &[PathStep]) -> Node<Body> {
    let Some((step, rest)) = path.split_first() else { return body.clone() };
    Node::new(Body { conjuncts: cut_list(&body.value().conjuncts, step.0 as usize, |conjunct| cut_conjunct(conjunct, rest)) })
}

fn cut_conjunct(conjunct: &Conjunct, path: &[PathStep]) -> Conjunct {
    let Some((step, rest)) = path.split_first() else { return conjunct.clone() };
    let index = step.0 as usize;
    match conjunct {
        Conjunct::Atom(atom) => Conjunct::Atom(Node::new(cut_atom(atom.value(), path))),
        Conjunct::Not(Negated::Atom(atom)) => Conjunct::Not(Negated::Atom(Node::new(cut_atom(atom.value(), path)))),
        Conjunct::Not(Negated::Form(form)) => Conjunct::Not(Negated::Form(Arc::new(cut_conjunct(form, rest)))),
        Conjunct::Or(branches) => Conjunct::Or(cut_list(branches, index, |branch| cut_body(branch, rest))),
        Conjunct::If { test, then, otherwise } => match index {
            0 => Conjunct::If { test: cut_body(test, rest), then: empty(), otherwise: empty() },
            1 => Conjunct::If { test: test.clone(), then: cut_body(then, rest), otherwise: empty() },
            _ => Conjunct::If { test: test.clone(), then: then.clone(), otherwise: cut_body(otherwise, rest) },
        },
        Conjunct::All { domain, body } => match index {
            0 => Conjunct::All { domain: cut_body(domain, rest), body: empty() },
            _ => Conjunct::All { domain: domain.clone(), body: cut_body(body, rest) },
        },
        Conjunct::Constraint(_) => unreachable!("a constraint has no children"),
    }
}

fn cut_atom(atom: &Atom, path: &[PathStep]) -> Atom {
    let Some((step, rest)) = path.split_first() else { return atom.clone() };
    Atom { relation: atom.relation.clone(), sites: cut_list(&atom.sites, step.0 as usize, |site| cut_site(site, rest)) }
}

fn cut_site(site: &Site, path: &[PathStep]) -> Site {
    let Some((step, rest)) = path.split_first() else { return site.clone() };
    let arg = |arg: &SiteArg| match arg {
        SiteArg::Field(field) => SiteArg::Field(cut_site(field, rest)),
        arg => arg.clone(),
    };
    Site { column: site.column.clone(), value: SiteValue { args: cut_list(&site.value.args, step.0 as usize, arg) } }
}

/// The items of `items` before `index`, then `last` of the item at `index`.
fn cut_list<T: Clone>(items: &[T], index: usize, last: impl FnOnce(&T) -> T) -> Arc<[T]> {
    items[..index].iter().cloned().chain([last(&items[index])]).collect()
}

/// A list the prefix has not reached.
fn empty() -> Node<Body> {
    Node::new(Body { conjuncts: Arc::from([]) })
}

/// The refusals of the grammar on `prefix`: each complete node of its
/// partial form that no reader gives, as `crate::read::arclog` refuses
/// it: an `OR` of no branch, a site of no argument, and a head site that
/// makes its label or holds `0`.
pub(super) fn grammar(prefix: &Prefix<'_>) -> PrefixResult {
    let mut refusals = Vec::new();
    grammar_node(prefix, NodeRef::from(prefix.partial), NodePath::default(), &mut refusals);
    refused(refusals)
}

fn grammar_node(prefix: &Prefix<'_>, node: NodeRef<'_>, at: NodePath, out: &mut Vec<Refusal>) {
    let complete = !prefix.is_open(&at);
    let mut refuse = |message: &str, at: NodePath| out.push(Refusal { message: message.into(), at });
    match node {
        NodeRef::Conjunct(Conjunct::Or(branches)) if complete && branches.is_empty() => refuse("an `OR` holds its branches", at.clone()),
        NodeRef::Site(site) if complete && site.value.args.is_empty() => refuse("a site holds a label or a field site", at.clone()),
        NodeRef::InstanceInput(input) => {
            for (site, index) in input.head.iter().zip(0u32..) {
                let site_at = at.child(index);
                each_site_label(site, &mut Vec::new(), &mut |use_, _| match use_ {
                    LabelUse::Fresh(_) => refuse("a head site carries no `*`: the body or the key makes its label", site_at.clone()),
                    LabelUse::Zero => refuse("a head site holds no `0`: the body makes its label with `(= *X 0)`", site_at.clone()),
                    LabelUse::Join(_) | LabelUse::Key(_) => {}
                });
            }
        }
        _ => {}
    }
    for (child, index) in node.children().into_iter().zip(0u32..) {
        grammar_node(prefix, child, at.child(index), out);
    }
}

/// The refusals of the scope on `prefix`: each read of its partial form
/// whose name resolves to nothing, which no node written later declares,
/// since a form reads only the relations declared before it.
pub(super) fn scope(prefix: &Prefix<'_>) -> PrefixResult {
    let path = prefix.path;
    let program = prefix.scope.program;
    let unresolved = super::reads::form_reads(prefix.partial, path).into_iter().filter(|read| {
        matches!(program.resolution(&path.join(&read.at)), Some(crate::resolver::Resolution::Unresolved))
    });
    refused(unresolved.map(|read| Refusal { message: "the name resolves to nothing visible".into(), at: read.at }).collect())
}
