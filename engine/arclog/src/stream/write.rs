//! The writer from a case program to its token stream, each token with the
//! side that emits it, in the order of `docs/engine/arclog-stream.md#token-stream`.
//!
//! A name that the engine emits, an input's or a named clause's, is a
//! [`Token::Column`] at the name's position: an instance's `key` at 0 and
//! the component's input `k` at `1 + k`, and a `CHOOSE` form's `for`,
//! `from` and `never` at 0, 1 and 2. The engine emits the name of each
//! named clause of a form and of each input of its component, and the
//! language model declines an unwritten one by `SKIP`. The inputs of an
//! instance's key clause follow the key's body, one name per input of the
//! component, and the inputs after the key clause follow them, one name per
//! input that the key clause does not write. An instance declares each
//! output of its component, then each input whose name no output shares,
//! written or not, right after its component token. A `RIGID_DET` form's
//! `key` and `instance` are named at 0 and 1, its parts follow them and end
//! with `END`, and it declares its outputs in the order
//! `crate::resolver::form_columns::rigid_outputs` gives. A projection gives one column
//! name per column of the input, each followed by the head site's arguments
//! at that column and `END`.
//!
//! A program that holds a `DEMONSTRATED` form has no stream: the grammar of
//! the stream has no form for it.

use crate::check::CheckedProgram;
use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::hash::{StableHashMap, StableHashSet};
use crate::program::path::{node_at, NodePath, NodeRef};
use crate::program::{
    Body, Choose, Clause, ClauseKeyword, ColumnName, Conjunct, ConstraintLabel, Form, Instance, InstanceInput,
    LabelId, LabelUse, Negated, Operand, Out, OutputName, OutputOwner, OutputStep, ProgramRelation, RelationRef, RigidDet, Site, SiteArg,
};
use crate::program::Atom;
use crate::registry::{Component, InputPort, LibEntry, Registry};
use crate::resolver::registry_columns::{component, proposer_columns, typed_columns};
use crate::resolver::columns::{example, projection};
use crate::resolver::form_columns::rigid_outputs;
use crate::resolver::{DependencyKind, Resolution, ResolvedProgram, Side};

use super::{Control, Emitter, Token, Vocabulary};

/// The token stream of `program`'s forms, the forms of each claim in its
/// place, in the case program's order where that order puts each form after
/// the first form that declares each relation it reads, and otherwise with
/// each form after the forms it reads from. Each relation the program declares takes the
/// next relation slot at its declaration, and each label the next label
/// slot of its top-level form at its first use.
///
/// Fails at the first token that `vocabulary` does not hold, with a
/// diagnostic that names the cap the program passes or the proposer the
/// settings do not offer, and at a form that the stream has no form for: a
/// `DEMONSTRATED` form, an `ALTS` form, and a `DET_OR_RULE` or `RULE_OR_DET`
/// line.
pub fn token_stream(program: &CheckedProgram, vocabulary: &Vocabulary) -> Result<Vec<(Token, Emitter)>, Diagnostic> {
    Ok(written_stream(program, vocabulary)?.tokens)
}

/// The token stream of [`token_stream`] with the relation that the program
/// declares at each slot and the labels of each form.
#[derive(Clone, Debug)]
pub struct WrittenStream {
    pub tokens: Vec<(Token, Emitter)>,
    /// Source-order AST path at each token, from the same writer run.
    pub paths: Vec<NodePath>,
    /// The relation declared at each slot, in slot order.
    pub relations: Vec<ProgramRelation>,
    /// Each form of the stream, in the order of the stream.
    pub forms: Vec<WrittenForm>,
}

/// A form that the stream writes, a form of the program that holds no form.
#[derive(Clone, Debug)]
pub struct WrittenForm {
    /// Half-open token span and relation-slot span emitted by this form.
    pub tokens: std::ops::Range<usize>,
    pub relations: std::ops::Range<usize>,
    /// Readable relation slots: outputs and written inputs, excluding SKIP reservations.
    pub readable: Vec<usize>,
    /// The form's path in the program.
    pub path: NodePath,
    /// The program's label at each label slot of the form, in slot order.
    pub labels: Vec<LabelId>,
}

/// The stream of [`token_stream`] with the relations its slots name and the
/// labels of its forms, from one run of the writer.
pub fn written_stream(program: &CheckedProgram, vocabulary: &Vocabulary) -> Result<WrittenStream, Diagnostic> {
    let WriterOutput { stream, slots, forms } = write_program(program, vocabulary)?;
    let (tokens,paths)=stream.into_iter().map(|(token,emitter,path)|((token,emitter),path)).unzip();
    Ok(WrittenStream { tokens, paths, relations: slots, forms })
}

/// The token stream of [`token_stream`], each token with the path in
/// `program` of the node whose writing emits it: a node's tokens stand at
/// its path or below it, and its last such token ends it. A token that
/// closes a list or a clause of a form stands at the form's path, but the
/// `END` of a key's body, which gives the key its columns, stands at the
/// body's path, and a clause's proposers stand at its body's path, which
/// they precede.
pub fn token_stream_with_paths(program: &CheckedProgram, vocabulary: &Vocabulary) -> Result<Vec<(Token, Emitter, NodePath)>, Diagnostic> {
    let written=written_stream(program,vocabulary)?;
    Ok(written.tokens.into_iter().zip(written.paths).map(|((token,emitter),path)|(token,emitter,path)).collect())
}

/// What one run of the writer gives: the tokens with their paths, the
/// relation declared at each slot, and the forms written.
struct WriterOutput {
    stream: Vec<(Token, Emitter, NodePath)>,
    slots: Vec<ProgramRelation>,
    forms: Vec<WrittenForm>,
}

/// The tokens of `program` with their paths, the relations the writer declared, and the forms it wrote.
fn write_program(program: &CheckedProgram, vocabulary: &Vocabulary) -> Result<WriterOutput, Diagnostic> {
    let mut writer = Writer {
        vocabulary,
        registry: vocabulary.registry(),
        resolved: &program.program,
        declared: StableHashMap::default(),
        slots: Vec::new(),
        labels: StableHashMap::default(),
        next_label: 0,
        stream: Vec::new(),
        written: Vec::new(),
    };
    writer.forms(&program.program.program.value().forms)?;
    Ok(WriterOutput { stream: writer.stream, slots: writer.slots, forms: writer.written })
}

/// The forms of `forms` that hold no form, each with its path under `path`,
/// the forms of a claim in the claim's place.
fn leaf_forms<'a>(forms: &'a [Form], path: &NodePath, out: &mut Vec<(&'a Form, NodePath)>) {
    for (index, form) in forms.iter().enumerate() {
        let at = path.child(index as u32);
        match form {
            Form::Claim(claim) => leaf_forms(&claim.value().forms, &at, out),
            _ => out.push((form, at)),
        }
    }
}

/// The relations, with their columns, that `instance` of `component`
/// declares, one for each relation port, in the component's order.
fn instance_outputs(component: &Component, instance: &Instance) -> Vec<(ProgramRelation, Box<[ColumnName]>)> {
    let every: Vec<_> = component.inputs.iter().map(|input| &input.port.name).collect();
    component
        .relation_ports(&every)
        .map(|port| {
            let output = OutputName { of: OutputOwner::Instance(instance.name.clone()), path: [OutputStep::Port(port.name.clone())].into() };
            (ProgramRelation::Output(output), port.columns.iter().map(|column| column.name.clone()).collect())
        })
        .collect()
}

/// The program relation that a read of `relation` looks up, `None` for a
/// read of a fact, a lib relation or an input port.
fn read_relation(relation: &RelationRef) -> Option<ProgramRelation> {
    match relation {
        RelationRef::Declared(name) => Some(ProgramRelation::Declared(name.clone())),
        RelationRef::Output(output) => Some(ProgramRelation::Output(output.clone())),
        _ => None,
    }
}

/// The relation that `choose` declares.
fn choose_relation(choose: &Choose) -> ProgramRelation {
    ProgramRelation::Declared(choose.name.clone())
}

/// The relations, with their columns, that `rigid` declares, in the order
/// `rigid_outputs` gives.
fn rigid_det_outputs(rigid: &RigidDet) -> Vec<(ProgramRelation, Box<[ColumnName]>)> {
    rigid_outputs(rigid)
        .into_iter()
        .map(|(steps, columns)| (ProgramRelation::Output(OutputName { of: OutputOwner::RigidDet(rigid.name.clone()), path: steps }), columns.names().cloned().collect()))
        .collect()
}

/// The relations that `form` declares.
fn declarations(registry: &Registry, form: &Form) -> Vec<ProgramRelation> {
    match form {
        Form::Clause(clause) => vec![clause.value().derives.clone()],
        Form::Choose(choose) => vec![choose_relation(choose.value())],
        Form::Instance(instance) => {
            let instance = instance.value();
            component(registry, &instance.component).map_or_else(Vec::new, |component| instance_outputs(component, instance).into_iter().map(|(relation, _)| relation).collect())
        }
        Form::RigidDet(rigid) => rigid_det_outputs(rigid.value()).into_iter().map(|(relation, _)| relation).collect(),
        Form::Claim(_) | Form::Demonstrated(_) | Form::Alts(_) | Form::Out(_) => Vec::new(),
    }
}

/// The relations that the atoms below `node` read and that a form declares.
fn reads_below(node: NodeRef<'_>, reads: &mut Vec<ProgramRelation>) {
    if let Some(atom) = node.atom() {
        reads.extend(read_relation(&atom.relation));
    }
    for child in node.children() {
        reads_below(child, reads);
    }
}

/// The indexes of `forms` in the order the writer writes them: at each
/// step the earliest form, in the given order, each of whose reads, other
/// than of what it declares itself, is of a relation that a form already
/// written declares or that no form of `forms` declares. Where no form is
/// ready, as in a cycle, the earliest form left. A list whose forms follow
/// what they read keeps its order.
pub(super) fn write_order(registry: &Registry, forms: &[(&Form, NodePath)]) -> Vec<usize> {
    let declares: Vec<Vec<ProgramRelation>> = forms.iter().map(|(form, _)| declarations(registry, form)).collect();
    let reads: Vec<Vec<ProgramRelation>> = forms
        .iter()
        .zip(&declares)
        .map(|((form, _), own)| {
            let mut reads = Vec::new();
            reads_below(NodeRef::from(*form), &mut reads);
            reads.retain(|relation| !own.contains(relation));
            reads
        })
        .collect();
    let mut waiting: StableHashSet<&ProgramRelation> = declares.iter().flatten().collect();
    let mut order = Vec::with_capacity(forms.len());
    let mut left: Vec<usize> = (0..forms.len()).collect();
    while !left.is_empty() {
        let ready = left.iter().position(|&index| reads[index].iter().all(|relation| !waiting.contains(relation)));
        let index = left.remove(ready.unwrap_or(0));
        for relation in &declares[index] {
            waiting.remove(relation);
        }
        order.push(index);
    }
    order
}

/// A relation the program has declared: its slot and the names of its
/// columns, in the order of its declaration.
struct Declared {
    slot: u32,
    columns: Box<[ColumnName]>,
}

type Written = Result<(), Diagnostic>;

struct Writer<'w> {
    vocabulary: &'w Vocabulary<'w>,
    registry: &'w Registry,
    resolved: &'w ResolvedProgram,
    /// The relations that the program's forms declare.
    declared: StableHashMap<ProgramRelation, Declared>,
    /// The relation declared at each slot.
    slots: Vec<ProgramRelation>,
    /// The slot of each label of the current label scope, as far as a read
    /// takes it.
    labels: StableHashMap<LabelId, u32>,
    /// The next label slot of the current label scope.
    next_label: u32,
    stream: Vec<(Token, Emitter, NodePath)>,
    /// The forms written so far.
    written: Vec<WrittenForm>,
}

impl Writer<'_> {
    fn push(&mut self, token: Token, emitter: Emitter, path: &NodePath) -> Written {
        if self.vocabulary.id(&token).is_none() {
            return Err(self.missing(&token, path));
        }
        self.stream.push((token, emitter, path.clone()));
        Ok(())
    }

    fn model(&mut self, control: Control, path: &NodePath) -> Written {
        self.push(Token::Control(control), Emitter::Model, path)
    }

    /// The diagnostic of `token`, which the vocabulary does not hold, at
    /// `path`.
    fn missing(&self, token: &Token, path: &NodePath) -> Diagnostic {
        let caps = self.vocabulary.caps();
        let (kind, severity, message) = match token {
            Token::Relation(_) => (DiagnosticKind::Bound, Severity::Alert, format!("the program declares more relations than the relation cap, {}", caps.relations)),
            Token::Column(position) => (DiagnosticKind::Bound, Severity::Alert, format!("the column position {position} passes the column cap, {}", caps.columns)),
            Token::Label(_) => (DiagnosticKind::Bound, Severity::Alert, format!("the form holds more labels than the label cap, {}", caps.labels)),
            Token::Proposer(name) => (DiagnosticKind::Run, Severity::Error, format!("the decode settings offer no token for the proposer `{}`", name.0)),
            Token::Lib(name) => (DiagnosticKind::Run, Severity::Error, format!("the vocabulary holds no lib name `{}`", name.0)),
            Token::Control(_) | Token::Fact(_) => (DiagnosticKind::Run, Severity::Error, format!("the vocabulary holds no token {token:?}")),
        };
        diagnostic(kind, severity, message, path)
    }

    /// Writes the forms in the order of [`write_order`].
    fn forms(&mut self, forms: &[Form]) -> Written {
        let mut leaves = Vec::new();
        leaf_forms(forms, &NodePath::default(), &mut leaves);
        for index in write_order(self.registry, &leaves) {
            let (form, at) = &leaves[index];
            let token_start=self.stream.len();
            let relation_start=self.slots.len();
            self.clear_labels();
            match form {
                Form::Claim(_) => unreachable!("leaf forms hold no claim"),
                Form::Clause(clause) => self.clause(clause.value(), at)?,
                Form::Instance(instance) => self.instance(instance.value(), at)?,
                Form::Choose(choose) => self.choose(choose.value(), at)?,
                Form::RigidDet(rigid) => self.rigid_det(rigid.value(), at)?,
                Form::Out(out) => self.out(out.value(), at)?,
                Form::Demonstrated(_) => return Err(no_form("a `DEMONSTRATED` form", at)),
                Form::Alts(_) => return Err(no_form("an `ALTS` form", at)),
            }
            let mut labels: Vec<(u32, LabelId)> = self.labels.iter().map(|(id, slot)| (*slot, *id)).collect();
            labels.sort_by_key(|(slot, _)| *slot);
            let readable = match form {
                Form::Instance(instance) => {
                    let instance = instance.value();
                    let written = crate::program::written_inputs(instance.key.as_ref(), &instance.inputs).map(|input| &input.name).collect::<Vec<_>>();
                    component(self.registry, &instance.component).expect("checked component")
                        .relation_ports(&written)
                        .map(|port| ProgramRelation::Output(OutputName { of: OutputOwner::Instance(instance.name.clone()), path: [OutputStep::Port(port.name.clone())].into() }))
                        .map(|relation| self.declared[&relation].slot as usize).collect()
                }
                _ => (relation_start..self.slots.len()).collect(),
            };
            self.written.push(WrittenForm { tokens:token_start..self.stream.len(),relations:relation_start..self.slots.len(),readable,path: at.clone(), labels: labels.into_iter().map(|(_, id)| id).collect() });
        }
        Ok(())
    }

    /// Takes the next relation slot for `relation`, with the columns
    /// `columns`, and emits it.
    fn declare(&mut self, relation: ProgramRelation, columns: Box<[ColumnName]>, path: &NodePath) -> Written {
        let slot = self.reserve(relation, columns, path)?;
        self.push(Token::Relation(slot), Emitter::Engine, path)
    }

    /// Takes the next relation slot for `relation`, with the columns
    /// `columns`, and gives it. A relation already declared is a fault: the
    /// decoder takes a new slot at each declaration, so a second declaration
    /// would give a stream whose later slots differ from the decoder's.
    fn reserve(&mut self, relation: ProgramRelation, columns: Box<[ColumnName]>, path: &NodePath) -> Result<u32, Diagnostic> {
        if self.declared.contains_key(&relation) {
            return Err(run_fault(format!("the stream declares a relation once for each form that derives it, and {relation:?} has more than one"), path));
        }
        let slot = u32::try_from(self.slots.len()).expect("fewer than 2^32 relations");
        self.declared.insert(relation.clone(), Declared { slot, columns });
        self.slots.push(relation);
        Ok(slot)
    }

    /// Starts a label scope.
    fn clear_labels(&mut self) {
        self.labels.clear();
        self.next_label = 0;
    }

    /// Emits the clause. A `DET` with no body and no proposer has no labels, so
    /// the stream gives it no column, and a decoded program carries no stored
    /// value for it: it gives no stream, and its fault is the conversion fault
    /// of [Determination](../../../../docs/engine/determination.md#det).
    fn clause(&mut self, clause: &Clause, path: &NodePath) -> Written {
        if let Some(fault) = crate::eval::determinations::conversion_fault(clause, path) {
            return Err(run_fault(fault.message.into(), path));
        }
        let keyword = match clause.keyword {
            ClauseKeyword::Rule => Control::Rule,
            ClauseKeyword::Det => Control::Det,
            ClauseKeyword::DetOrRule => return Err(no_form("a `DET_OR_RULE` line", path)),
            ClauseKeyword::RuleOrDet => return Err(no_form("a `RULE_OR_DET` line", path)),
        };
        self.model(keyword, path)?;
        for proposer in clause.proposers.iter() {
            self.push(Token::Proposer(proposer.clone()), Emitter::Model, &path.child(0))?;
        }
        self.body(clause.body.value(), &path.child(0))?;
        if clause.set {
            self.model(Control::Set, path)?;
        }
        for mark in clause.ones.iter() {
            self.model(Control::One, path)?;
            for label in mark.key.iter() {
                self.label(LabelUse::Join(*label), path)?;
            }
            self.model(Control::End, path)?;
        }
        self.model(Control::End, path)?;
        let columns = match (clause.columns.is_empty(), clause.proposers.first()) {
            (true, Some(proposer)) => proposer_columns(self.registry, proposer).ok_or_else(|| run_fault(format!("the lib names no proposer `{}`", proposer.0), path))?,
            _ => clause.columns.iter().map(|column| column.name.clone()).collect(),
        };
        self.declare(clause.derives.clone(), columns, path)
    }

    fn body(&mut self, body: &Body, path: &NodePath) -> Written {
        for (index, conjunct) in body.conjuncts.iter().enumerate() {
            self.conjunct(conjunct, &path.child(index as u32))?;
        }
        Ok(())
    }

    fn conjunct(&mut self, conjunct: &Conjunct, path: &NodePath) -> Written {
        match conjunct {
            Conjunct::Atom(atom) => self.atom(atom.value(), path),
            Conjunct::Not(Negated::Atom(atom)) => {
                self.model(Control::Not, path)?;
                self.atom(atom.value(), path)
            }
            Conjunct::Not(Negated::Form(form)) => {
                self.model(Control::Not, path)?;
                self.conjunct(form, &path.child(0))
            }
            Conjunct::Constraint(constraint) => {
                self.model(Control::Op(constraint.op), path)?;
                self.constraint_label(constraint.first, path)?;
                match constraint.second {
                    Operand::Label(label) => self.constraint_label(label, path),
                    Operand::Zero => self.model(Control::Zero, path),
                }
            }
            Conjunct::Or(branches) => {
                self.model(Control::Or, path)?;
                for (index, branch) in branches.iter().enumerate() {
                    if index > 0 {
                        self.model(Control::Also, path)?;
                    }
                    self.body(branch.value(), &path.child(index as u32))?;
                }
                self.model(Control::End, path)
            }
            Conjunct::If { test, then, otherwise } => {
                self.model(Control::If, path)?;
                self.lists([test, then, otherwise].map(|body| body.value()), path)
            }
            Conjunct::All { domain, body } => {
                self.model(Control::All, path)?;
                self.lists([domain, body].map(|body| body.value()), path)
            }
        }
    }

    /// The lists of an `IF` or an `ALL` form at `path`, each followed by
    /// `END`.
    fn lists<const N: usize>(&mut self, bodies: [&Body; N], path: &NodePath) -> Written {
        for (index, body) in bodies.into_iter().enumerate() {
            self.body(body, &path.child(index as u32))?;
            self.model(Control::End, path)?;
        }
        Ok(())
    }

    fn constraint_label(&mut self, label: ConstraintLabel, path: &NodePath) -> Written {
        self.label(label.into(), path)
    }

    /// A label with its mark, the engine's echo after `*` and `^`.
    fn label(&mut self, label: LabelUse, path: &NodePath) -> Written {
        let (mark, id) = match label {
            LabelUse::Fresh(id) => (Some(Control::Fresh), id),
            LabelUse::Key(id) => (Some(Control::Key), id),
            LabelUse::Join(id) => (None, id),
            LabelUse::Zero => return self.model(Control::Zero, path),
        };
        let slot = match self.labels.get(&id) {
            Some(slot) => *slot,
            None => {
                let slot = self.next_label;
                self.next_label += 1;
                self.labels.insert(id, slot);
                slot
            }
        };
        match mark {
            Some(mark) => {
                self.model(mark, path)?;
                self.push(Token::Label(slot), Emitter::Engine, path)
            }
            None => self.push(Token::Label(slot), Emitter::Model, path),
        }
    }

    fn atom(&mut self, atom: &Atom, path: &NodePath) -> Written {
        let (token, columns) = match &atom.relation {
            RelationRef::Fact(fact) => (Token::Fact(*fact), self.lib_columns(&atom.relation, path)?),
            RelationRef::Lib(name) => {
                let token = match self.registry.entry(name) {
                    Some(LibEntry::Proposer(_)) => Token::Proposer(name.clone()),
                    _ => Token::Lib(name.clone()),
                };
                (token, self.lib_columns(&atom.relation, path)?)
            }
            RelationRef::Declared(_) | RelationRef::Output(_) => self.declared_relation(&read_relation(&atom.relation).expect("a declared or output read names a program relation"), path)?,
            RelationRef::DefinedPort(_) => return Err(no_form("a read of an input port", path)),
        };
        let columns: Box<[ColumnName]> = match reads_example_column(self.resolved, path) {
            true => std::iter::once(example()).chain(columns.iter().cloned()).collect(),
            false => columns,
        };
        self.push(token, Emitter::Model, path)?;
        for (index, site) in atom.sites.iter().enumerate() {
            let at = path.child(index as u32);
            let position = columns.iter().position(|column| *column == site.column).ok_or_else(|| run_fault(format!("the relation has no column {:?}", site.column), &at))?;
            self.push(Token::Column(position as u32), Emitter::Model, &at)?;
            self.site_value(site, &at)?;
        }
        Ok(())
    }

    /// The slot and the columns of a relation the program has declared.
    fn declared_relation(&self, relation: &ProgramRelation, path: &NodePath) -> Result<(Token, Box<[ColumnName]>), Diagnostic> {
        let declared = self.declared.get(relation).ok_or_else(|| run_fault(format!("the program reads {relation:?} before it declares it"), path))?;
        Ok((Token::Relation(declared.slot), declared.columns.clone()))
    }

    /// The names of the columns of a fact relation or of a lib relation,
    /// relation macro or proposer.
    fn lib_columns(&self, relation: &RelationRef, path: &NodePath) -> Result<Box<[ColumnName]>, Diagnostic> {
        let columns = typed_columns(self.registry, relation).ok_or_else(|| run_fault(format!("the lib declares no columns of {relation:?}"), path))?;
        Ok(columns.iter().map(|column| column.name.clone()).collect())
    }

    /// The arguments of the site at `path` of an atom. A site on a record
    /// gives each field site and each named label the column of its field
    /// within the record, as the resolver places it, and ends with `END`.
    fn site_value(&mut self, site: &Site, path: &NodePath) -> Written {
        let Some(group) = self.resolved.column_group(path) else {
            for (index, arg) in site.value.args.iter().enumerate() {
                match arg {
                    SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => self.label(*label, &path.child(index as u32))?,
                    SiteArg::Field(_) => return Err(run_fault("a field site on a site that reads no record".to_owned(), &path.child(index as u32))),
                }
            }
            return Ok(());
        };
        for (index, arg) in site.value.args.iter().enumerate() {
            let at = path.child(index as u32);
            if let SiteArg::Label(label) = arg {
                self.label(*label, &at)?;
                continue;
            }
            let position = self.resolved.column_position(&at).ok_or_else(|| run_fault("the resolver gives the field no position".to_owned(), &at))?;
            let field = position.0.checked_sub(group.start.0).ok_or_else(|| run_fault("the field stands before its record".to_owned(), &at))?;
            self.push(Token::Column(u32::from(field)), Emitter::Model, &at)?;
            match arg {
                SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => self.label(*label, &at)?,
                SiteArg::Field(field) => self.site_value(field, &at)?,
            }
        }
        self.model(Control::End, path)
    }

    fn instance(&mut self, instance: &Instance, path: &NodePath) -> Written {
        self.model(Control::Init, path)?;
        self.push(Token::Lib(instance.component.clone()), Emitter::Model, path)?;
        let component = component(self.registry, &instance.component).ok_or_else(|| run_fault(format!("the lib names no component `{}`", instance.component.0), path))?;
        let keyed: &[_] = instance.key.as_ref().map_or(&[], |key| &key.value().inputs);
        let outputs: Vec<u32> = instance_outputs(component, instance).into_iter().map(|(relation, columns)| self.reserve(relation, columns, path)).collect::<Result<_, _>>()?;
        for slot in outputs {
            self.push(Token::Relation(slot), Emitter::Engine, path)?;
        }
        self.push(Token::Column(0), Emitter::Engine, path)?;
        match &instance.key {
            None => self.model(Control::Skip, path)?,
            Some(key) => {
                let key = key.value();
                let at = path.child(0);
                self.body(key.key.body.value(), &at.child(0))?;
                self.model(Control::End, &at.child(0))?;
                self.inputs(component, &key.inputs, |_| true, &at, 1)?;
            }
        }
        let written_in_key = |port: &InputPort| keyed.iter().any(|input| input.value().name == port.port.name);
        self.inputs(component, &instance.inputs, |port| !written_in_key(port), path, u32::from(instance.key.is_some()))
    }

    /// The name of each input of `component` that `named` takes, each
    /// followed by the input of `inputs` it names, the children of the node
    /// at `path` from `first`, or by `SKIP`.
    fn inputs(
        &mut self,
        component: &Component,
        inputs: &[crate::program::Node<InstanceInput>],
        named: impl Fn(&InputPort) -> bool,
        path: &NodePath,
        first: u32,
    ) -> Written {
        if let Some(input) = inputs.iter().find(|input| !component.inputs.iter().any(|port| port.port.name == input.value().name)) {
            return Err(run_fault(format!("the component has no input `{}`", input.value().name.0), path));
        }
        for (position, port) in component.inputs.iter().enumerate() {
            if !named(port) {
                continue;
            }
            self.push(Token::Column(1 + position as u32), Emitter::Engine, path)?;
            match inputs.iter().position(|input| input.value().name == port.port.name) {
                Some(index) => self.input(inputs[index].value(), port, &path.child(first + index as u32))?,
                None => self.model(Control::Skip, path)?,
            }
        }
        Ok(())
    }

    /// An input's body, then its projection: each column of `port`, the
    /// engine's, with the arguments of the head site at that column.
    fn input(&mut self, input: &InstanceInput, port: &InputPort, path: &NodePath) -> Written {
        self.body(input.body.value(), &path.child(input.head.len() as u32))?;
        self.model(Control::End, path)?;
        if let Some(site) = input.head.iter().find(|site| !port.port.columns.iter().any(|column| column.name == site.column)) {
            return Err(run_fault(format!("the input `{}` has no column {:?}", input.name.0, site.column), path));
        }
        for (position, column) in port.port.columns.iter().enumerate() {
            self.push(Token::Column(position as u32), Emitter::Engine, path)?;
            if let Some(index) = input.head.iter().position(|site| site.column == column.name) {
                self.head_site(&input.head[index], &path.child(index as u32))?;
            }
            self.model(Control::End, path)?;
        }
        Ok(())
    }

    /// The arguments of the head site at `path`. A head site that projects
    /// a record gives each field the column of its place among the fields
    /// it writes, which is the record's order of fields, and ends with
    /// `END`.
    fn head_site(&mut self, site: &Site, path: &NodePath) -> Written {
        let record = projection(site).is_some();
        let mut field = 0;
        for (index, arg) in site.value.args.iter().enumerate() {
            let at = path.child(index as u32);
            match arg {
                SiteArg::Label(label) => self.label(*label, &at)?,
                SiteArg::NamedLabel { label, .. } if !record => self.label(*label, &at)?,
                SiteArg::NamedLabel { label, .. } => {
                    self.push(Token::Column(field), Emitter::Model, &at)?;
                    field += 1;
                    self.label(*label, &at)?;
                }
                SiteArg::Field(inner) => {
                    self.push(Token::Column(field), Emitter::Model, &at)?;
                    field += 1;
                    self.head_site(inner, &at)?;
                }
            }
        }
        match record {
            true => self.model(Control::End, path),
            false => Ok(()),
        }
    }

    fn rigid_det(&mut self, rigid: &RigidDet, path: &NodePath) -> Written {
        self.model(Control::RigidDet, path)?;
        let mut child = 0;
        for (name, clause) in [&rigid.key, &rigid.instance].into_iter().enumerate() {
            self.push(Token::Column(name as u32), Emitter::Engine, path)?;
            match clause {
                None => self.model(Control::Skip, path)?,
                Some(clause) => {
                    self.body(clause.body.value(), &path.child(child))?;
                    self.model(Control::End, &path.child(child))?;
                    child += 1;
                }
            }
        }
        for (index, part) in rigid.parts.iter().enumerate() {
            self.atom(part.value(), &path.child(child + index as u32))?;
        }
        self.model(Control::End, path)?;
        for (relation, columns) in rigid_det_outputs(rigid) {
            self.declare(relation, columns, path)?;
        }
        Ok(())
    }

    /// Emits the `OUT` form: its atoms as the body of a key clause, then
    /// `END`. It declares nothing.
    fn out(&mut self, out: &Out, path: &NodePath) -> Written {
        self.model(Control::Out, path)?;
        self.body(out.key.body.value(), &path.child(Out::BODY))?;
        self.model(Control::End, path)
    }

    fn choose(&mut self, choose: &Choose, path: &NodePath) -> Written {
        self.model(Control::Choose, path)?;
        let rows = u32::from(choose.rows.is_some());
        self.push(Token::Column(0), Emitter::Engine, path)?;
        match &choose.rows {
            None => self.model(Control::Skip, path)?,
            Some(rows) => {
                self.body(rows.body.value(), &path.child(0))?;
                self.model(Control::End, &path.child(0))?;
            }
        }
        self.push(Token::Column(1), Emitter::Engine, path)?;
        self.body(choose.from.value(), &path.child(rows))?;
        self.model(Control::End, path)?;
        self.push(Token::Column(2), Emitter::Engine, path)?;
        if choose.never.is_empty() {
            self.model(Control::Skip, path)?;
        }
        for (index, never) in choose.never.iter().enumerate() {
            if index > 0 {
                self.model(Control::Also, path)?;
            }
            self.body(never.value(), &path.child(rows + 1 + index as u32))?;
            self.model(Control::End, path)?;
        }
        if !choose.never.is_empty() {
            self.model(Control::End, path)?;
        }
        let row_columns = choose.rows.iter().flat_map(|rows| rows.columns.iter());
        let columns = row_columns.chain(choose.candidate_columns.iter()).map(|column| column.name.clone()).collect();
        self.declare(choose_relation(choose), columns, path)
    }
}

/// Whether the read at `read` gives the Example column the column token 0,
/// with the columns of its relation after it, as
/// `docs/engine/arclog-stream.md#token-stream` gives: a clause's read where it is
/// lifted, and a read in an `INIT`, a `CHOOSE` or a `RIGID_DET` form, or in
/// the key or an input of a `DEMONSTRATED` form, of a per-input relation
/// that is no fact and no relation of the form, lifted or not. The side of
/// such a form follows from its reads, a site on `E` among them, so the rule
/// reads only what stands at the read's relation token. A read in a form of
/// a `DEMO_RULE` form takes the rule of that form.
pub(crate) fn reads_example_column(resolved: &ResolvedProgram, read: &NodePath) -> bool {
    let program = NodeRef::Program(resolved.program.value());
    let Some(form) = read_form(program, read) else { return false };
    if !takes_example_column(program, &form) {
        return resolved.reads_lifted(read);
    }
    let Some(Resolution::Node(node)) = resolved.resolution(read) else { return false };
    let fact = matches!(resolved.graph.nodes[node.0 as usize].kind, DependencyKind::Fact(_));
    !fact && !resolved.nodes_of(&form).contains(node) && resolved.side(*node) == Side::PerInput
}

/// The path of the form whose rule [`reads_example_column`] takes for the
/// read at `read` in `program`: the first form on the path that is no
/// claim, or, inside a `DEMO_RULE` form of a `DEMONSTRATED` form, the form of
/// that rule.
pub(crate) fn read_form(program: NodeRef<'_>, read: &NodePath) -> Option<NodePath> {
    let depths = 1..=read.0.len();
    let mut form = depths.map(|depth| NodePath(read.0[..depth].into())).find(|at| !matches!(node_at(program, at), Some(NodeRef::Claim(_))))?;
    if read.0.len() > form.0.len() + 1 && matches!(node_at(program, &form), Some(NodeRef::Demonstrated(_))) {
        let rule = NodePath(read.0[..form.0.len() + 1].into());
        if matches!(node_at(program, &rule), Some(NodeRef::DemoRule(_))) {
            form = NodePath(read.0[..form.0.len() + 2].into());
        }
    }
    Some(form)
}

/// Whether a read in the form at `form` of `program` gives the Example
/// column the column token 0 by the rule of an `INIT`, a `CHOOSE`, a
/// `RIGID_DET` or a `DEMONSTRATED` form, rather than where it is lifted.
pub(crate) fn takes_example_column(program: NodeRef<'_>, form: &NodePath) -> bool {
    matches!(node_at(program, form), Some(NodeRef::Instance(_) | NodeRef::Choose(_) | NodeRef::RigidDet(_) | NodeRef::Demonstrated(_)))
}

fn diagnostic(kind: DiagnosticKind, severity: Severity, message: String, path: &NodePath) -> Diagnostic {
    Diagnostic { kind, severity, message: message.into(), location: Location::Path(path.clone()), cases: Box::new([]) }
}

fn run_fault(message: String, path: &NodePath) -> Diagnostic {
    diagnostic(DiagnosticKind::Run, Severity::Error, message, path)
}

fn no_form(form: &str, path: &NodePath) -> Diagnostic {
    run_fault(format!("the token stream has no form for {form}"), path)
}
