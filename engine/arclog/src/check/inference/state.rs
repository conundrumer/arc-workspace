//! The types of a mask's state, which the candidates of the mask extend: a
//! candidate whose form differs from the form in progress at the state only
//! by what its token adds to the sites of some atoms takes the type of each
//! label the token leaves alone from the state's inference, and infers the
//! rest.
//!
//! A label's type is the meet of the types of its sites and of those of the
//! labels that constraints make equal to it, so it changes only when a site
//! or a constraint of its class changes. The state's types stand for a
//! candidate's label where no site or constraint of the label's class
//! differs, and the candidate has the shape of the state's form.

use std::cell::OnceCell;
use std::sync::Arc;

use super::Inference;
use crate::hash::{StableHashMap, StableHashSet};
use crate::program::path::NodePath;
use crate::program::{Atom, Body, Conjunct, Form, LabelId, Negated, Node, Operand, Program};
use crate::resolver::{resolve_for_checks, ResolvedProgram};
use crate::types::{each_conjunct, each_site_label, use_label, LabelFault, ValueType};

type LabelTypes = Result<Option<ValueType>, LabelFault>;

/// The form in progress at a mask's state, which `earlier` resolves the
/// forms before.
pub(in crate::check) struct HeldState {
    earlier: Arc<ResolvedProgram>,
    program: Node<Program>,
    resolved: OnceCell<ResolvedProgram>,
    types: OnceCell<Option<StateTypes>>,
    flat: OnceCell<Option<StateFlat>>,
}

impl HeldState {
    pub(in crate::check) fn new(earlier: Arc<ResolvedProgram>, program: Node<Program>) -> Self {
        HeldState { earlier, program, resolved: OnceCell::new(), types: OnceCell::new(), flat: OnceCell::new() }
    }
}

/// The inference of the form in progress at a mask's state, where it is a
/// clause that gives no label a type by anything but its sites and
/// constraints.
pub(super) struct StateTypes {
    path: NodePath,
    body: Node<Body>,
    labels: StableHashMap<LabelId, LabelTypes>,
    pairs: Vec<(LabelId, LabelId)>,
}

/// The entries that [`Inference::flat_form`] takes of the form in progress at
/// a mask's state, where it is a clause of atoms alone that `flat_form`
/// types: for each label that stands at a site, the meet of its site types
/// read under [`PoseOr::Open`] and under [`PoseOr::Given`].
///
/// An entry reads only the sites at which its label stands, with the types
/// that the state's resolution and inference give them. A candidate whose
/// clause holds the state's atoms, each with the relation it has in the
/// state, and whose sites differ from the state's in some atoms alone, holds
/// each other atom as the state does, so a label that stands at none of the
/// atoms that differ has the sites, in the order, and the types it has in the
/// state. The state's form is read as an inference in progress reads it: a
/// read of the clause's own relation gives no type.
pub(super) struct StateFlat {
    path: NodePath,
    body: Node<Body>,
    pub(super) open: StableHashMap<LabelId, Option<ValueType>>,
    pub(super) given: StableHashMap<LabelId, Option<ValueType>>,
}

impl StateFlat {
    /// The labels that stand at an atom of `body` that differs from the atom
    /// at its place in the state's clause, each at any of its sites; `None`
    /// where `body` is not the state's with the sites of some atoms changed:
    /// a conjunct that is no atom, another number of conjuncts, or an atom of
    /// another relation, which can change what a read of a form's other atoms
    /// gives.
    fn touched(&self, body: &Body) -> Option<StableHashSet<LabelId>> {
        let old = &self.body.value().conjuncts;
        if old.len() != body.conjuncts.len() {
            return None;
        }
        let mut touched = StableHashSet::default();
        for (old, new) in old.iter().zip(body.conjuncts.iter()) {
            let (Conjunct::Atom(old), Conjunct::Atom(new)) = (old, new) else { return None };
            if std::ptr::eq(old.value(), new.value()) {
                continue;
            }
            let (old, new) = (old.value(), new.value());
            if old.relation != new.relation {
                return None;
            }
            if old.sites[..] != new.sites[..] {
                for site in old.sites.iter().chain(new.sites.iter()) {
                    each_site_label(site, &mut Vec::new(), &mut |use_, _| touched.extend(use_label(use_)));
                }
            }
        }
        Some(touched)
    }
}

/// The labels whose sites or constraints differ between two forms of one
/// shape.
#[derive(Default)]
struct Touched {
    labels: Vec<LabelId>,
}

impl Touched {
    fn site_labels(&mut self, site: &crate::program::Site) {
        each_site_label(site, &mut Vec::new(), &mut |use_, _| self.labels.extend(use_label(use_)));
    }

    /// Notes the labels of the sites of `old` and of `new`, atoms of one
    /// relation, that differ. Gives `None` where the relations differ.
    fn atom(&mut self, old: &Atom, new: &Atom) -> Option<()> {
        if old.relation != new.relation {
            return None;
        }
        let common = old.sites.len().min(new.sites.len());
        for (a, b) in old.sites.iter().zip(new.sites.iter()) {
            if a != b {
                self.site_labels(a);
                self.site_labels(b);
            }
        }
        for site in old.sites[common..].iter().chain(&new.sites[common..]) {
            self.site_labels(site);
        }
        Some(())
    }

    fn constraint(&mut self, conjunct: &Conjunct) {
        if let Conjunct::Constraint(constraint) = conjunct {
            self.labels.push(constraint.first.label);
            if let Operand::Label(second) = constraint.second {
                self.labels.push(second.label);
            }
        }
    }

    /// Notes what differs between `old` and `new`, bodies of one shape: the
    /// same conjuncts but for the sites of atoms, and, at the end of a body,
    /// a constraint that `new` adds. Gives `None` where the shapes differ.
    fn body(&mut self, old: &Node<Body>, new: &Node<Body>) -> Option<()> {
        if std::ptr::eq(old.value(), new.value()) {
            return Some(());
        }
        let (old, new) = (&old.value().conjuncts, &new.value().conjuncts);
        let added = match new.len().checked_sub(old.len())? {
            0 => None,
            1 => Some(new.last().filter(|conjunct| matches!(conjunct, Conjunct::Constraint(_)))?),
            _ => return None,
        };
        for (a, b) in old.iter().zip(new.iter()) {
            self.conjunct(a, b)?;
        }
        added.inspect(|constraint| self.constraint(constraint));
        Some(())
    }

    fn conjunct(&mut self, old: &Conjunct, new: &Conjunct) -> Option<()> {
        match (old, new) {
            (Conjunct::Atom(a), Conjunct::Atom(b)) | (Conjunct::Not(Negated::Atom(a)), Conjunct::Not(Negated::Atom(b))) => {
                if std::ptr::eq(a.value(), b.value()) {
                    return Some(());
                }
                self.atom(a.value(), b.value())
            }
            (Conjunct::Constraint(a), Conjunct::Constraint(b)) => (a == b).then_some(()),
            (Conjunct::Not(Negated::Form(a)), Conjunct::Not(Negated::Form(b))) => self.conjunct(a, b),
            (Conjunct::Or(a), Conjunct::Or(b)) if a.len() == b.len() => a.iter().zip(b.iter()).try_for_each(|(a, b)| self.body(a, b)),
            (Conjunct::If { test: t, then: n, otherwise: o }, Conjunct::If { test: t2, then: n2, otherwise: o2 }) => {
                self.body(t, t2)?;
                self.body(n, n2)?;
                self.body(o, o2)
            }
            (Conjunct::All { domain: d, body: b }, Conjunct::All { domain: d2, body: b2 }) => {
                self.body(d, d2)?;
                self.body(b, b2)
            }
            _ => None,
        }
    }

    /// The labels noted and each label that the constraints of `old` or of
    /// the new form make equal to one of them, directly or through others.
    fn closed(mut self, old: &[(LabelId, LabelId)], new: &Body) -> Vec<LabelId> {
        let mut pairs = old.to_vec();
        pairs.extend(constraint_pairs(new));
        let mut grown = true;
        while grown {
            grown = false;
            for &(a, b) in &pairs {
                for (x, y) in [(a, b), (b, a)] {
                    if self.labels.contains(&x) && !self.labels.contains(&y) {
                        self.labels.push(y);
                        grown = true;
                    }
                }
            }
        }
        self.labels
    }
}

/// The pairs of labels that the constraints of `body`, at any depth, make
/// equal.
fn constraint_pairs(body: &Body) -> Vec<(LabelId, LabelId)> {
    let mut pairs = Vec::new();
    each_conjunct(body, &mut |conjunct| {
        if let Conjunct::Constraint(constraint) = conjunct {
            if let Some(second) = crate::program::constraint_second(constraint) {
                pairs.push((constraint.first.label, second.label));
            }
        }
    });
    pairs
}

impl<'a> Inference<'a> {
    /// Holds the form in progress at the mask's state, `program` with that
    /// form as its last, over `earlier`, the resolution of the forms before it,
    /// for the candidates of the mask.
    pub(in crate::check) fn hold_state(&self, earlier: Arc<ResolvedProgram>, program: Node<Program>) {
        let _ = self.state.set(HeldState::new(earlier, program));
    }

    /// The form in progress at the mask's state, where it is held.
    pub(in crate::check) fn state_form(&self) -> Option<&Form> {
        self.state.get()?.program.value().forms.last()
    }

    /// The types of the state's form, made on the first read.
    fn state_types(&self) -> Option<&'a StateTypes> {
        let earlier = self.earlier?;
        let held = earlier.held_state()?;
        held.types
            .get_or_init(|| {
                let Some(Form::Clause(_)) = held.program.value().forms.last() else { return None };
                let resolved = held.resolved.get_or_init(|| resolve_for_checks(&held.earlier, &held.program, self.registry));
                let Some(Form::Clause(clause)) = resolved.program.value().forms.last() else { return None };
                let path = NodePath::top(resolved.program.value().forms.len() as u32 - 1);
                let inference = Inference { splits: false, any_label_order: true, ..Inference::layered(resolved, self.cases, earlier) };
                let inferred = inference.infer(&path)?;
                let plain = inferred.given.is_empty() && inferred.zero_typed.is_empty() && inferred.bindings.is_empty() && clause.value().columns.is_empty();
                plain.then(|| StateTypes {
                    path,
                    body: clause.value().body.clone(),
                    labels: inferred.labels.iter().cloned().collect(),
                    pairs: constraint_pairs(clause.value().body.value()),
                })
            })
            .as_ref()
    }

    /// The state's entries for [`Inference::flat_form`], made on the first
    /// read.
    fn state_flat(&self) -> Option<&'a StateFlat> {
        let earlier = self.earlier?;
        let held = earlier.held_state()?;
        held.flat
            .get_or_init(|| {
                let Some(Form::Clause(_)) = held.program.value().forms.last() else { return None };
                let resolved = held.resolved.get_or_init(|| resolve_for_checks(&held.earlier, &held.program, self.registry));
                let Some(form @ Form::Clause(clause)) = resolved.program.value().forms.last() else { return None };
                let path = NodePath::top(resolved.program.value().forms.len() as u32 - 1);
                let inference = Inference { splits: false, any_label_order: true, fast: true, ..Inference::layered(resolved, self.cases, earlier) };
                // The form's types are in progress while its sites are read.
                inference.forms.borrow_mut().insert(path.clone(), None);
                let (open, given) = inference.flat_entries(form, &path)?;
                Some(StateFlat { path, body: clause.value().body.clone(), open, given })
            })
            .as_ref()
    }

    /// The state's entries and the labels that stand at an atom of `form`,
    /// at `path`, that differs from the state's, where `form` is the state's
    /// clause with the sites of some atoms changed, as [`StateFlat`] gives.
    pub(super) fn flat_split(&self, form: &Form, path: &NodePath) -> Option<(&'a StateFlat, StableHashSet<LabelId>)> {
        let Form::Clause(clause) = form else { return None };
        if !self.splits {
            return None;
        }
        let state = self.state_flat()?;
        if state.path != *path {
            return None;
        }
        Some((state, state.touched(clause.value().body.value())?))
    }

    /// The labels of `form`, at `path`, whose types the state's inference
    /// does not give, with that inference: `None` where `form` is not the
    /// state's clause with what its token adds.
    pub(super) fn state_split(&self, form: &Form, path: &NodePath, labels: &[LabelId]) -> Option<(&'a StateTypes, Vec<LabelId>)> {
        let Form::Clause(clause) = form else { return None };
        let clause = clause.value();
        if !self.splits || !(clause.columns.is_empty() && clause.ones.is_empty() && !clause.set) {
            return None;
        }
        let state = self.state_types()?;
        if state.path != *path {
            return None;
        }
        let mut touched = Touched::default();
        touched.body(&state.body, &clause.body)?;
        let touched = touched.closed(&state.pairs, clause.body.value());
        let own = labels.iter().copied().filter(|label| touched.contains(label) || !state.labels.contains_key(label));
        Some((state, own.collect()))
    }
}

impl StateTypes {
    /// The type the state's inference gives `label`.
    pub(super) fn label(&self, label: LabelId) -> Option<&LabelTypes> {
        self.labels.get(&label)
    }
}
