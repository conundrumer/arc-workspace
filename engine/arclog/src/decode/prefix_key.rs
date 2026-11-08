//! Exact source keys for prefix verdicts. Node equality is canonical, so it
//! cannot key checks that read source order, open paths, and original labels.
use std::hash::{Hash, Hasher};
use crate::program::*;
use crate::program::path::{node_at, NodePath, NodeRef};

/// A hasher that keeps the bytes written to it, so a key holds the whole
/// source of its form. Where it holds an atom, the atom's relation is left
/// out of the bytes: the atom is the one that an atom-head key stands on.
#[derive(Default)]
struct Source(Vec<u8>, Option<*const Atom>);
impl Hasher for Source {
    fn write(&mut self, bytes: &[u8]) { self.0.extend_from_slice(bytes); }
    fn finish(&self) -> u64 { unreachable!("source keys retain all bytes") }
}
impl Source {
    fn scalar(&mut self, value: &impl Hash) { value.hash(self); }
    fn atom(&mut self, atom: &Atom) {
        if self.1 == Some(atom as *const Atom) {
            self.scalar(&0u8);
        } else {
            self.scalar(&atom.relation);
        }
        self.scalar(&atom.sites);
    }
    fn body(&mut self, body: &Body) {
        self.scalar(&body.conjuncts.len());
        for conjunct in body.conjuncts.iter() { self.conjunct(conjunct); }
    }
    fn conjunct(&mut self, conjunct: &Conjunct) {
        self.scalar(&std::mem::discriminant(conjunct));
        match conjunct {
            Conjunct::Atom(atom) => self.atom(atom.value()),
            Conjunct::Not(negated) => {
                self.scalar(&std::mem::discriminant(negated));
                match negated {
                    Negated::Atom(atom) => self.atom(atom.value()),
                    Negated::Form(form) => self.conjunct(form),
                }
            }
            Conjunct::Constraint(constraint) => self.scalar(constraint),
            Conjunct::Or(branches) => {
                self.scalar(&branches.len());
                for body in branches.iter() { self.body(body.value()); }
            }
            Conjunct::If { test, then, otherwise } => {
                self.body(test.value()); self.body(then.value()); self.body(otherwise.value());
            }
            Conjunct::All { domain, body } => { self.body(domain.value()); self.body(body.value()); }
        }
    }
    fn key(&mut self, key: &KeyBody) { self.scalar(&key.columns); self.body(key.body.value()); }
    fn optional_key(&mut self, key: Option<&KeyBody>) {
        self.scalar(&key.is_some());
        if let Some(key) = key { self.key(key); }
    }
    fn inputs(&mut self, inputs: &[Node<InstanceInput>]) {
        self.scalar(&inputs.len());
        for input in inputs {
            let input = input.value();
            self.scalar(&input.name); self.scalar(&input.head); self.body(input.body.value());
        }
    }
    fn form(&mut self, form: &Form) -> Option<()> {
        self.scalar(&std::mem::discriminant(form));
        match form {
            Form::Clause(clause) => {
                let c = clause.value();
                self.scalar(&c.keyword); self.scalar(&c.derives); self.scalar(&c.gloss);
                self.scalar(&c.proposers); self.body(c.body.value()); self.scalar(&c.ones);
                self.scalar(&c.set); self.scalar(&c.columns);
            }
            Form::Instance(instance) => {
                let i = instance.value();
                self.scalar(&i.name); self.scalar(&i.component); self.scalar(&i.key.is_some());
                if let Some(key) = &i.key { self.key(&key.value().key); self.inputs(&key.value().inputs); }
                self.inputs(&i.inputs);
            }
            Form::Choose(choose) => {
                let c = choose.value();
                self.scalar(&c.name); self.optional_key(c.rows.as_ref()); self.scalar(&c.candidate_columns);
                self.scalar(&c.from_inside_for); self.body(c.from.value()); self.scalar(&c.never.len());
                for body in c.never.iter() { self.body(body.value()); }
            }
            Form::RigidDet(rigid) => {
                let r = rigid.value();
                self.scalar(&r.name); self.optional_key(r.key.as_ref()); self.optional_key(r.instance.as_ref());
                self.scalar(&r.parts.len());
                for atom in r.parts.iter() { self.atom(atom.value()); }
            }
            Form::Out(out) => self.key(&out.value().key),
            Form::Demonstrated(_) | Form::Claim(_) | Form::Alts(_) => return None,
        }
        Some(())
    }
}

/// The key of the clause `form` with its body cut to the first `conjuncts`
/// conjuncts: with equal forms before it, equal keys give equal programs. A
/// form that is no clause takes no key.
pub(super) fn clause_cut_key(form: &Form, conjuncts: usize) -> Option<Vec<u8>> {
    let Form::Clause(clause) = form else { return None };
    let c = clause.value();
    let mut source = Source::default();
    source.scalar(&std::mem::discriminant(form));
    source.scalar(&c.keyword); source.scalar(&c.derives); source.scalar(&c.gloss);
    source.scalar(&c.proposers);
    let kept = &c.body.value().conjuncts[..conjuncts.min(c.body.value().conjuncts.len())];
    source.scalar(&kept.len());
    for conjunct in kept { source.conjunct(conjunct); }
    source.scalar(&c.ones); source.scalar(&c.set); source.scalar(&c.columns);
    Some(source.0)
}

/// The key of the clause `clause` with the body `kept` in place of its own:
/// with equal finished forms before it, equal keys give equal sub-bodies
/// ([`super::Decoder::sub_body`]), whose columns `kept` gives.
pub(super) fn sub_body_key(clause: &Clause, kept: &[Conjunct]) -> Vec<u8> {
    let mut source = Source::default();
    source.scalar(&clause.keyword); source.scalar(&clause.derives); source.scalar(&clause.gloss);
    source.scalar(&clause.proposers); source.scalar(&clause.ones); source.scalar(&clause.set);
    source.scalar(&kept.len());
    for conjunct in kept { source.conjunct(conjunct); }
    source.0
}

/// The key of the prefix whose last form is `form`, with its open node at
/// `open`: each field of the form that the form's kind holds, in source
/// order, and the path. Equal keys give the checks equal input: they read
/// the source order, the open path and the original labels, which node
/// equality leaves out. `Form::Claim` and `Form::Alts` take no key.
pub(super) fn key(form: &Form, open: Option<&NodePath>) -> Option<Vec<u8>> {
    let mut source = Source::default();
    source.form(form)?;
    source.scalar(&open);
    Some(source.0)
}

/// The key of the prefix whose last form is `form`, with its open node at
/// `open`, an atom, but for the relation of that atom: the bytes of
/// [`key`] with the relation left out. Two prefixes with equal keys, over
/// equal finished forms, are one program but for the relation of the atom
/// at `open`, which is the case in which a resolution of one retargets to
/// the other ([`crate::check::prefix::PrefixChecks`]). None where the form
/// takes no key, or `open` is no atom of the form.
pub(crate) fn atom_head_key(form: &Form, open: &NodePath) -> Option<Vec<u8>> {
    let atom = node_at(NodeRef::from(form), open)?.atom()?;
    let mut source = Source(Vec::new(), Some(atom as *const Atom));
    source.form(form)?;
    source.scalar(&Some(open));
    Some(source.0)
}
