//! Exact source keys for prefix verdicts. Node equality is canonical, so it
//! cannot key checks that read source order, open paths, and original labels.
use std::hash::{Hash, Hasher};
use crate::program::*;
use crate::program::path::NodePath;

/// A hasher that keeps the bytes written to it, so a key holds the whole
/// source of its form.
#[derive(Default)]
struct Source(Vec<u8>);
impl Hasher for Source {
    fn write(&mut self, bytes: &[u8]) { self.0.extend_from_slice(bytes); }
    fn finish(&self) -> u64 { unreachable!("source keys retain all bytes") }
}
impl Source {
    fn scalar(&mut self, value: &impl Hash) { value.hash(self); }
    fn atom(&mut self, atom: &Atom) {
        self.scalar(&atom.relation);
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
            Form::Claim(_) | Form::Alts(_) | Form::Demonstrated(_) => return None,
        }
        Some(())
    }
}

/// The key of the prefix whose last form is `form`, with its open node at
/// `open`: each field of the form that the form's kind holds, in source
/// order, and the path. Equal keys give the checks equal input: they read
/// the source order, the open path and the original labels, which node
/// equality leaves out. `Form::Claim`, `Form::Alts` and `Form::Demonstrated`
/// take no key.
pub(super) fn key(form: &Form, open: Option<&NodePath>) -> Option<Vec<u8>> {
    let mut source = Source::default();
    source.form(form)?;
    source.scalar(&open);
    Some(source.0)
}
