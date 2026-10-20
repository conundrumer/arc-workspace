//! The writer from a case program to its token stream, each token with the
//! side that emits it, in the order of `docs/arclog/arclog.md#token-stream`.
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
//! written or not. A `RIGID_DET` form's `key` and `instance` are named at 0
//! and 1, its parts follow them and end with `END`, and it declares its
//! outputs in the order `crate::resolver::form_columns::rigid_outputs`
//! gives. A projection gives one column
//! name per column of the input, each followed by the head site's arguments
//! at that column and `END`.

use crate::check::CheckedProgram;
use crate::diagnostic::{Diagnostic, DiagnosticKind, Location, Severity};
use crate::hash::StableHashMap;
use crate::program::path::NodePath;
use crate::program::{
    Body, Choose, Clause, ClauseKeyword, ColumnName, Conjunct, ConstraintLabel, Form, Instance, InstanceInput, LabelId, LabelUse, Negated,
    Operand, OutputName, OutputOwner, OutputStep, ProgramRelation, RelationRef, RigidDet, Site, SiteArg,
};
use crate::program::Atom;
use crate::registry::{Component, InputPort, LibEntry, Registry};
use crate::resolver::registry_columns::{component, proposer_columns, typed_columns};
use crate::resolver::columns::{example, projection};
use crate::resolver::form_columns::rigid_outputs;
use crate::resolver::ResolvedProgram;

use super::{Control, Emitter, Token, Vocabulary};

/// The token stream of `program`'s forms, in declaration order, the forms
/// of each claim in its place. Each relation the program declares takes the
/// next relation slot at its declaration, and each label the next label
/// slot of its top-level form at its first use.
///
/// Fails at the first token that `vocabulary` does not hold, with a
/// diagnostic that names the cap the program passes or the proposer the
/// settings do not offer, and at a form that the stream has no form for: a
/// `DEMONSTRATED` or an `ALTS` form, and a `DET_OR_RULE` or `RULE_OR_DET`
/// line.
pub fn token_stream(program: &CheckedProgram, vocabulary: &Vocabulary) -> Result<Vec<(Token, Emitter)>, Diagnostic> {
    let mut writer = Writer {
        vocabulary,
        registry: vocabulary.registry(),
        resolved: &program.program,
        declared: StableHashMap::default(),
        labels: StableHashMap::default(),
        stream: Vec::new(),
    };
    writer.forms(&program.program.program.value().forms, &NodePath::default())?;
    Ok(writer.stream)
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
    declared: StableHashMap<ProgramRelation, Declared>,
    /// The slot of each label of the current top-level form.
    labels: StableHashMap<LabelId, u32>,
    stream: Vec<(Token, Emitter)>,
}

impl Writer<'_> {
    fn push(&mut self, token: Token, emitter: Emitter, path: &NodePath) -> Written {
        if self.vocabulary.id(&token).is_none() {
            return Err(self.missing(&token, path));
        }
        self.stream.push((token, emitter));
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

    fn forms(&mut self, forms: &[Form], path: &NodePath) -> Written {
        for (index, form) in forms.iter().enumerate() {
            let at = path.child(index as u32);
            match form {
                Form::Claim(claim) => self.forms(&claim.value().forms, &at)?,
                Form::Clause(clause) => {
                    self.labels.clear();
                    self.clause(clause.value(), &at)?;
                }
                Form::Instance(instance) => {
                    self.labels.clear();
                    self.instance(instance.value(), &at)?;
                }
                Form::Choose(choose) => {
                    self.labels.clear();
                    self.choose(choose.value(), &at)?;
                }
                Form::RigidDet(rigid) => {
                    self.labels.clear();
                    self.rigid_det(rigid.value(), &at)?;
                }
                Form::Demonstrated(_) => return Err(no_form("a `DEMONSTRATED` form", &at)),
                Form::Alts(_) => return Err(no_form("an `ALTS` form", &at)),
            }
        }
        Ok(())
    }

    /// Takes the next relation slot for `relation`, with the columns
    /// `columns`, and emits it.
    fn declare(&mut self, relation: ProgramRelation, columns: Box<[ColumnName]>, path: &NodePath) -> Written {
        let slot = self.reserve(relation, columns);
        self.push(Token::Relation(slot), Emitter::Engine, path)
    }

    /// Takes the next relation slot for `relation`, with the columns
    /// `columns`, and gives it.
    fn reserve(&mut self, relation: ProgramRelation, columns: Box<[ColumnName]>) -> u32 {
        let slot = u32::try_from(self.declared.len()).expect("fewer than 2^32 relations");
        self.declared.insert(relation, Declared { slot, columns });
        slot
    }

    fn clause(&mut self, clause: &Clause, path: &NodePath) -> Written {
        let keyword = match clause.keyword {
            ClauseKeyword::Rule => Control::Rule,
            ClauseKeyword::Det => Control::Det,
            ClauseKeyword::DetOrRule => return Err(no_form("a `DET_OR_RULE` line", path)),
            ClauseKeyword::RuleOrDet => return Err(no_form("a `RULE_OR_DET` line", path)),
        };
        self.model(keyword, path)?;
        for proposer in clause.proposers.iter() {
            self.push(Token::Proposer(proposer.clone()), Emitter::Model, path)?;
        }
        self.body(clause.body.value(), &path.child(0))?;
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
                        self.model(Control::Or, path)?;
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
        let next = u32::try_from(self.labels.len()).expect("fewer than 2^32 labels");
        let slot = *self.labels.entry(id).or_insert(next);
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
            RelationRef::Declared(name) => self.declared_relation(&ProgramRelation::Declared(name.clone()), path)?,
            RelationRef::Output(output) => self.declared_relation(&ProgramRelation::Output(output.clone()), path)?,
            RelationRef::DefinedPort(_) => return Err(no_form("a read of an input port", path)),
        };
        let columns: Box<[ColumnName]> = match self.resolved.reads_lifted(path) {
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
                    SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => self.label(*label, path)?,
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
        let every: Vec<_> = component.inputs.iter().map(|input| &input.port.name).collect();
        let outputs: Vec<u32> = component
            .relation_ports(&every)
            .map(|port| {
                let output = OutputName { of: OutputOwner::Instance(instance.name.clone()), path: [OutputStep::Port(port.name.clone())].into() };
                let columns = port.columns.iter().map(|column| column.name.clone()).collect();
                self.reserve(ProgramRelation::Output(output), columns)
            })
            .collect();
        self.push(Token::Column(0), Emitter::Engine, path)?;
        match &instance.key {
            None => self.model(Control::Skip, path)?,
            Some(key) => {
                let key = key.value();
                let at = path.child(0);
                self.body(key.key.body.value(), &at.child(0))?;
                self.model(Control::End, &at)?;
                self.inputs(component, &key.inputs, |_| true, &at, 1)?;
            }
        }
        let written_in_key = |port: &InputPort| keyed.iter().any(|input| input.value().name == port.port.name);
        self.inputs(component, &instance.inputs, |port| !written_in_key(port), path, u32::from(instance.key.is_some()))?;
        for slot in outputs {
            self.push(Token::Relation(slot), Emitter::Engine, path)?;
        }
        Ok(())
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
                    self.model(Control::End, path)?;
                    child += 1;
                }
            }
        }
        for (index, part) in rigid.parts.iter().enumerate() {
            self.atom(part.value(), &path.child(child + index as u32))?;
        }
        self.model(Control::End, path)?;
        for (steps, columns) in rigid_outputs(rigid) {
            let output = OutputName { of: OutputOwner::RigidDet(rigid.name.clone()), path: steps };
            self.declare(ProgramRelation::Output(output), columns.names().cloned().collect(), path)?;
        }
        Ok(())
    }

    fn choose(&mut self, choose: &Choose, path: &NodePath) -> Written {
        self.model(Control::Choose, path)?;
        let rows = u32::from(choose.rows.is_some());
        self.push(Token::Column(0), Emitter::Engine, path)?;
        match &choose.rows {
            None => self.model(Control::Skip, path)?,
            Some(rows) => {
                self.body(rows.body.value(), &path.child(0))?;
                self.model(Control::End, path)?;
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
        let row_columns = choose.rows.iter().flat_map(|rows| rows.columns.iter());
        let columns = row_columns.chain(choose.candidate_columns.iter()).map(|column| column.name.clone()).collect();
        self.declare(ProgramRelation::Declared(choose.name.clone()), columns, path)
    }
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
