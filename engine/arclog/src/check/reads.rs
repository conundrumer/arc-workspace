//! The check of the pooled and lifted reads, the walk of a form's reads
//! that the checks of reads share, and the decision of which relations of a
//! checked program have an Example column.

use super::types::{form_side, result};
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal};
use crate::hash::StableHashSet;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Atom, FactRelation, Form};
use crate::resolver::{DependencyKind, GraphNodeIndex, Resolution, ResolvedProgram, Side};
use crate::types::each_site_label;

/// [`CheckId::PooledAndLiftedReads`].
pub struct PooledAndLiftedReadsCheck;

impl Check for PooledAndLiftedReadsCheck {
    fn id(&self) -> CheckId {
        CheckId::PooledAndLiftedReads
    }

    /// Refuses each read that `docs/arclog/arclog.md#program` does not let
    /// its form make: a per-input form's read of `ex_input` or `ex_output`, a
    /// task-wide form's read of `input`, and a per-input form's read at a
    /// site on a column that holds an Example of the relation it reads, as
    /// [`ResolvedProgram::example_columns`] gives. A read of a form's own
    /// nodes, as an `Unfold` instance's of its outputs, is no read of another
    /// side.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let program = input.scope.program;
        let mut order = None;
        let mut refusals = Vec::new();
        for read in form_reads(input.form, input.path) {
            let Some(Resolution::Node(node)) = program.resolution(&input.path.join(&read.at)) else { continue };
            if program.form_of(*node) == &read.form {
                continue;
            }
            let Some(side) = form_side(program, &read.form) else { continue };
            let Some(message) = refused_read(program, side, *node, read.atom) else { continue };
            let order = order.get_or_insert_with(|| CanonicalOrder::of(input.form, &mut SearchBudget::new()));
            refusals.push(Refusal { message: message.into(), at: order.canonical_path(&read.at) });
        }
        result(refusals)
    }

    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}

/// Why a form of side `side` may not make `atom`, its read of `node`, or
/// `None` where it may.
fn refused_read(program: &ResolvedProgram, side: Side, node: GraphNodeIndex, atom: &Atom) -> Option<&'static str> {
    let fact = match program.graph.nodes[node.0 as usize].kind {
        DependencyKind::Fact(fact) => Some(fact),
        _ => None,
    };
    match (side, fact) {
        (Side::PerInput, Some(FactRelation::ExInput | FactRelation::ExOutput)) => {
            Some("a per-input form reads `ex_input` or `ex_output`, which only a task-wide form reads")
        }
        (Side::TaskWide, Some(FactRelation::Input)) => Some("a task-wide form reads `input`, which only a per-input form reads"),
        (Side::PerInput, None) if reads_example(program.example_columns(node, crate::resolver::output_of(&atom.relation)), atom) => {
            Some("a per-input form reads the Example column of a relation, which it reads only pooled, with no site on that column")
        }
        _ => None,
    }
}

/// Whether a site of `atom` stands on a column of `examples`, at any depth
/// of the site.
fn reads_example(examples: &[crate::resolver::ExamplePath], atom: &Atom) -> bool {
    let mut found = false;
    for site in atom.sites.iter() {
        each_site_label(site, &mut Vec::new(), &mut |_, path| {
            found |= examples.iter().any(|example| path.starts_with(example));
        });
    }
    found
}

/// One read of a form: the atom, its path relative to the form the check
/// reads, and the path in the program of the innermost form that holds it,
/// a form of a `DEMO_RULE` included, whose side the read takes.
pub(super) struct FormRead<'a> {
    pub atom: &'a Atom,
    pub at: NodePath,
    pub form: NodePath,
}

/// Each read of `form`, the form at `path` in the program, and of each form
/// it holds, in the order of the forms' paths.
pub(super) fn form_reads<'a>(form: &'a Form, path: &NodePath) -> Vec<FormRead<'a>> {
    fn walk<'a>(node: NodeRef<'a>, at: NodePath, form: &NodePath, out: &mut Vec<FormRead<'a>>) {
        if let Some(atom) = node.atom() {
            return out.push(FormRead { atom, at, form: form.clone() });
        }
        for (child, index) in node.children().into_iter().zip(0u32..) {
            if !is_form(child) {
                walk(child, at.child(index), form, out);
            }
        }
    }
    let mut out = Vec::new();
    for (at, node) in forms_within(form) {
        walk(node, at.clone(), &path.join(&at), &mut out);
    }
    out
}

/// `form` and each form of a `DEMO_RULE` it holds, with its path relative
/// to `form`, in the order of the paths.
pub(super) fn forms_within(form: &Form) -> Vec<(NodePath, NodeRef<'_>)> {
    fn walk<'a>(node: NodeRef<'a>, at: NodePath, out: &mut Vec<(NodePath, NodeRef<'a>)>) {
        if is_form(node) {
            out.push((at.clone(), node));
        }
        if matches!(node, NodeRef::Demonstrated(_) | NodeRef::DemoRule(_)) {
            for (child, index) in node.children().into_iter().zip(0u32..) {
                walk(child, at.child(index), out);
            }
        }
    }
    let mut out = Vec::new();
    walk(NodeRef::from(form), NodePath::default(), &mut out);
    out
}

/// Whether `node` is a form whose reads take its own side.
fn is_form(node: NodeRef<'_>) -> bool {
    matches!(node, NodeRef::Clause(_) | NodeRef::Instance(_) | NodeRef::Choose(_) | NodeRef::RigidDet(_) | NodeRef::Demonstrated(_))
}

/// The relations of `program` that have an Example column: `ex_input`,
/// `ex_output`, and each node of the dependency graph a column of which holds
/// an Example, as [`ResolvedProgram::example_columns`] gives. A per-input relation that a task-wide form reads lifted
/// has none of its own (`docs/arclog/arclog.md#program`).
pub fn example_relations(program: &ResolvedProgram) -> StableHashSet<GraphNodeIndex> {
    let nodes = (0..program.graph.nodes.len() as u32).map(GraphNodeIndex);
    let has_example = |node: &GraphNodeIndex| match program.graph.nodes[node.0 as usize].kind {
        DependencyKind::Fact(FactRelation::ExInput | FactRelation::ExOutput) => true,
        _ => !program.example_columns(*node, None).is_empty(),
    };
    nodes.filter(has_example).collect()
}
