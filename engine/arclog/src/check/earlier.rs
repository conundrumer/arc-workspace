//! What the check of a program holds for each top-level form before its
//! last, kept for the programs that one set of finished forms is the start
//! of.
//!
//! A decode checks, in one mask, one program for each token that may end
//! the form in progress, and each of those programs holds the same finished
//! forms with another last form. The check of a program reads its forms
//! each time, which costs in proportion to the finished forms, though what
//! it reads of a finished form is the same from one of those programs to
//! the next. [`EarlierForms`] holds that, for the programs that
//! [`crate::resolver::resolve_last`] resolves over one resolution of the
//! finished forms, which gives each of those forms' reads the signature
//! that resolution gives them:
//!
//! - the signatures of the names that the form reads;
//! - the labels of the form's label scopes, before the type check types
//!   them;
//! - the outcome of the form's checks, for a form whose checks read the form,
//!   the signatures of its keys and the clauses of its relation alone, as
//!   [`Kept`] gives them.

use std::sync::{Arc, Mutex, OnceLock};

use super::LabelInScope;
use crate::diagnostic::Diagnostic;
use crate::hash::StableHashMap;
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Form, OutputName, OutputOwner, RelationRef};
use crate::resolver::Signature;
use crate::types::FormTypes;

/// The forms before the last of the programs of one set of finished forms,
/// by their index.
#[derive(Debug, Default)]
pub struct EarlierForms {
    forms: Mutex<StableHashMap<u32, Arc<EarlierForm>>>,
}

impl EarlierForms {
    /// What is kept of the form at `index`.
    pub(super) fn form(&self, index: u32) -> Arc<EarlierForm> {
        let mut forms = self.forms.lock().expect("a memo that no panic poisoned");
        Arc::clone(forms.entry(index).or_default())
    }
}

/// What is kept of one form, each part made on its first ask.
#[derive(Debug, Default)]
pub(super) struct EarlierForm {
    /// The signatures of the names that the form reads, as
    /// [`super::read_signatures`] gives them.
    pub(super) reads: OnceLock<Box<[Signature]>>,
    /// The labels of the form's label scopes with no type.
    pub(super) untyped: OnceLock<Arc<[LabelInScope]>>,
    /// Whether no check of the form that has no cache key reads more than
    /// the form: the form is no `OUT` form, and reads no output of a
    /// `RIGID_DET` form.
    pub(super) alone: OnceLock<bool>,
    kept: Mutex<Option<Arc<Kept>>>,
}

/// What the checks of a form gave, with what their cache keys are built from.
#[derive(Debug)]
pub(super) struct Kept {
    /// The signatures that the keys of the form's checks hold, after those
    /// of the clauses that [`super::CheckId::EqualityAndZero`] adds.
    pub(super) signatures: Box<[Signature]>,
    pub(super) zero: Box<[Signature]>,
    pub(super) types: Arc<super::types::ScopeTypes>,
    pub(super) labels: Arc<[LabelInScope]>,
    /// The diagnostics of the form's checks, in the order of the checks.
    pub(super) refused: Vec<Diagnostic>,
    /// The types of the form's label scopes as the program's types hold them,
    /// each at the scope's path in the program, made on the first ask for a
    /// program with no `RIGID_DET` form, whose own Idents they would hold.
    pub(in crate::check) scopes: OnceLock<Vec<(NodePath, Arc<FormTypes>)>>,
}

impl EarlierForm {
    /// What the checks of the form gave where their keys held `signatures`
    /// and `zero`, which every check of the form's key is built from, with
    /// the form.
    pub(super) fn kept(&self, signatures: &[Signature], zero: &[Signature]) -> Option<Arc<Kept>> {
        let kept = self.kept.lock().expect("a memo that no panic poisoned");
        kept.as_ref().filter(|kept| *kept.signatures == *signatures && *kept.zero == *zero).cloned()
    }

    /// Keeps what the checks of the form gave.
    pub(super) fn keep(&self, kept: Arc<Kept>) {
        *self.kept.lock().expect("a memo that no panic poisoned") = Some(kept);
    }
}

/// Whether the checks of `form` that no cache key stands for read the form
/// alone, where the program has no files: each is a pass on a form that is
/// no `OUT` form, and the check of the proposers reads another form only for
/// an atom that reads an output of a `RIGID_DET` form.
pub(super) fn alone(form: &Form) -> bool {
    if matches!(form, Form::Out(_)) {
        return false;
    }
    let mut reads = false;
    super::each_node(NodeRef::from(form), &NodePath::default(), &mut |node, _| {
        reads |= matches!(node.atom().map(|atom| &atom.relation), Some(RelationRef::Output(OutputName { of: OutputOwner::RigidDet(_), .. })));
    });
    !reads
}
