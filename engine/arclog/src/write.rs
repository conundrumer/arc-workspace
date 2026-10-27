//! The writer of arclog and arcdata files. Reading a file of the corpus and
//! writing it again gives the same bytes.
//!
//! [`write_solver`] stays `todo!()` for a later stage.

#![allow(unused_variables, dead_code)]

mod arcdata;
mod arclog;

pub(crate) use arclog::{declared, output_name, relation_ref};

use crate::layout::Layout;
use crate::program::{Arcdata, Node, Program};
use crate::registry::Registry;
use crate::solver::Solver;
use crate::terms::InternTable;

/// The text of a solver's two files.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct SolverText {
    pub arclog: String,
    pub arcdata: String,
}

/// The text of the arclog file that `program` and `layout`, as
/// [`crate::read::read_arclog`] reads them, give: each token at the place
/// its node's layout gives, each comment of the layout, and each site the
/// layout elides as its bare label. A token whose node has no layout stands
/// one space after the token before it. Each name and column of `program`
/// is written as a file writes it, and each label is named in the layout of
/// its scope, a form that an `ALT` gave to a `DEMO_RULE` form a scope of its
/// own; a slot of a decode is a fault.
pub fn write_arclog(program: &Node<Program>, layout: &Layout) -> String {
    arclog::write(program.value(), layout)
}

/// The text of the arcdata file that `arcdata` and `layout`, as
/// [`crate::read::read_arcdata`] reads them, give, as [`write_arclog`]
/// writes the arclog file: each token at the place its node's layout gives,
/// and each comment of the layout whose place is in
/// [`crate::layout::SourceFile::Arcdata`]. A value read from the file is
/// written as the file wrote it.
pub fn write_arcdata(arcdata: &Node<Arcdata>, layout: &Layout) -> String {
    arcdata::write(arcdata.value(), layout)
}

/// The two files of `solver`, laid out as the converter lays out each form,
/// with the comments, strings and label names of its layout.
pub fn write_solver(solver: &Solver) -> SolverText {
    todo!()
}

/// A synthesized program as an arclog file, in the program form and the
/// s-expression layout, with names in place of token ids, and a relation slot
/// written by its index. A column named by its slot is written by the name
/// its label takes, as the next paragraph gives. That name takes the spelling
/// of a fixed-type column (`docs/arclog/arclog.md#sites`), so the reader
/// reads a site on that column as a site on a fixed-type column, and no type
/// parameter's column is so spelled.
///
/// A label that a [`crate::program::SiteArg::NamedLabel`] holds takes that
/// argument's `name`, so the file reads that field at that site. Each name
/// so taken is reserved in its scope, as [`crate::program::LabelId`] gives
/// a scope, before any other label is named. Each other label takes the
/// name of the column or field of the site that makes it, PascalCase, in the
/// order of the labels' ids, which a decode gives in the order of the labels'
/// makes, with the
/// least digit suffix that gives a name no other label of its scope holds
/// or has reserved: in `(:a *A2) (:key *A)`, where the site at `:key` holds a
/// `NamedLabel { name: A }` and the label at `:a` is another label made at
/// `:a`, the label at `:key` is written `A` and the label at
/// `:a` is written `A2`.
///
/// Two labels take one name only where [`Node::apply`](crate::program::Node::apply)
/// gives them one, so the file reads back to the same labels:
/// `(OR ((r (:key *X))) ((s (:key *X))))` is written with `X` at each site,
/// and reads back as two labels.
///
/// A relation slot `n` is written `&rn`. The writer prints each form a decode
/// builds, `RULE`, `DET`, `INIT`, `CHOOSE`, `RIGID_DET` and `OUT`, and refuses
/// a record site. It writes a site of an `OUT` form that is a column of one
/// label as `^<column>`, with the column's name whatever the other labels of
/// the form are named, since no label of an `OUT` is read again.
pub fn write_synthesized(program: &Node<Program>, registry: &Registry) -> String {
    synthesized::write(program, registry)
}

/// The numbers a writer gives the Idents it writes, private to the crate's
/// writers, since a number is an order of encodings.
///
/// The Idents are numbered by the order of their contents' encodings, which
/// `TermId::encoding` gives, from the inside out. A value read from a file
/// is written as it was read, and the other Idents of that type in the file
/// are numbered after the largest such value.
#[derive(Clone, Debug, Default)]
pub struct IdentNumbering {
    numbers: crate::hash::StableHashMap<crate::terms::Ident, u32>,
}

impl IdentNumbering {
    /// The numbering of `idents`, the Idents one file writes.
    pub fn new(idents: &[crate::terms::Ident], table: &InternTable) -> Self {
        todo!()
    }

    /// The number written for `ident`.
    pub(crate) fn number(&self, ident: crate::terms::Ident) -> u32 {
        todo!()
    }
}

/// Marks in `layout` each site of the atoms of `out`, the `OUT` form at
/// `form`, that is a column of one label, as written elided: `^<column>`.
pub(crate) fn elide_out_sites(out: &crate::program::Out, form: &crate::program::path::NodePath, layout: &mut Layout) {
    use crate::layout::SourceFile;
    use crate::program::SiteArg;
    let body = form.child(crate::program::Out::BODY);
    for (index, conjunct) in out.key.body.value().conjuncts.iter().enumerate() {
        let Some(atom) = conjunct.atom() else { continue };
        let elided = atom.value().sites.iter().enumerate().filter(|(_, site)| matches!(&site.value.args[..], [SiteArg::Label(_)])).map(|(at, _)| at as u32);
        layout.nodes.entry((SourceFile::Arclog, body.child(index as u32))).or_default().elided_sites = elided.collect();
    }
}

/// The program form of a decoded program: its slots named, its labels named
/// in the scope of each form, and the program written with that layout.
mod synthesized {
    use std::sync::Arc;

    use crate::hash::StableHashMap;
    use crate::layout::{Layout, NodeLayout, SourceFile, SourcePlace};
    use crate::program::path::NodePath;
    use crate::program::*;
    use crate::registry::Registry;
    use crate::resolver::form_columns::rigid_outputs;
    use crate::resolver::registry_columns::{component, proposer_columns};
    use crate::trace::label_names::label_name;

    pub(super) fn write(program: &Node<Program>, registry: &Registry) -> String {
        let mut synth = Synthesizer { registry, columns: StableHashMap::default() };
        let mut forms = Vec::new();
        let mut layout = Layout::default();
        for (index, form) in program.value().forms.iter().enumerate() {
            let names = synth.label_names(form);
            let lookup = Names(&names);
            forms.push(synth.form(form, &lookup));
            let place = SourcePlace { file: SourceFile::Arclog, start: 0, end: 0, line: index as u32 + 1, column: 1 };
            let node = NodeLayout { tokens: Box::new([place]), label_names: names.into(), ..NodeLayout::default() };
            layout.nodes.insert((SourceFile::Arclog, NodePath::top(index as u32)), node);
            if let Form::Out(out) = &forms[index] {
                super::elide_out_sites(out.value(), &NodePath::top(index as u32), &mut layout);
            }
        }
        super::write_arclog(&Node::new(Program { forms: forms.into() }), &layout)
    }

    struct Names<'n>(&'n [(LabelId, Box<str>)]);

    impl Names<'_> {
        fn get(&self, label: LabelId) -> &str {
            self.0.iter().find(|(id, _)| *id == label).map(|(_, name)| &**name).expect("every label of the form is named")
        }
    }

    struct Synthesizer<'r> {
        registry: &'r Registry,
        /// The written names of the columns of each relation a form before
        /// the current one declares, by the position of the column.
        columns: StableHashMap<ProgramRelation, Vec<String>>,
    }

    fn slot_text(slot: u32) -> String {
        format!("&r{slot}")
    }

    fn declared(name: &DeclaredName) -> DeclaredName {
        match name {
            DeclaredName::Written(text) => DeclaredName::Written(text.clone()),
            DeclaredName::Slot(slot) => DeclaredName::Written(slot_text(*slot).into()),
        }
    }

    fn output(name: &OutputName) -> OutputName {
        let of = match &name.of {
            OutputOwner::Instance(InstanceName(owner)) => OutputOwner::Instance(InstanceName(declared(owner))),
            OutputOwner::RigidDet(RigidDetName(owner)) => OutputOwner::RigidDet(RigidDetName(declared(owner))),
        };
        let path = name.path.iter().map(|step| match step {
            OutputStep::Part(part) => OutputStep::Part(declared(part)),
            other => other.clone(),
        });
        OutputName { of, path: path.collect() }
    }

    fn program_relation(relation: &ProgramRelation) -> ProgramRelation {
        match relation {
            ProgramRelation::Declared(RelationName(name)) => ProgramRelation::Declared(RelationName(declared(name))),
            ProgramRelation::Output(name) => ProgramRelation::Output(output(name)),
        }
    }

    fn relation_ref(relation: &RelationRef) -> RelationRef {
        match relation {
            RelationRef::Declared(RelationName(name)) => RelationRef::Declared(RelationName(declared(name))),
            RelationRef::Output(name) => RelationRef::Output(output(name)),
            other => other.clone(),
        }
    }

    /// The relation an atom reads, as a key of the declared columns.
    fn read_relation(relation: &RelationRef) -> Option<ProgramRelation> {
        match relation {
            RelationRef::Declared(name) => Some(ProgramRelation::Declared(name.clone())),
            RelationRef::Output(name) => Some(ProgramRelation::Output(name.clone())),
            RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => None,
        }
    }

    /// `columns`, each named as its label is in the form.
    fn named_columns(columns: &[RelationColumn], names: &Names) -> Arc<[RelationColumn]> {
        columns.iter().map(|column| RelationColumn { name: ColumnName::Written(names.get(column.label).into()), label: column.label }).collect()
    }

    fn written(column: &ColumnName) -> Option<&str> {
        match column {
            ColumnName::Written(text) => Some(text),
            ColumnName::Slot(_) => None,
        }
    }

    impl Synthesizer<'_> {
        /// The text of `column` of a site on `relation`.
        fn column_text(&self, relation: Option<&RelationRef>, column: &ColumnName) -> String {
            match column {
                ColumnName::Written(text) => text.to_string(),
                ColumnName::Slot(slot) => {
                    let names = relation.and_then(read_relation).and_then(|relation| self.columns.get(&relation));
                    names.and_then(|names| names.get(*slot as usize)).cloned().unwrap_or_else(|| panic!("a column slot {slot} of a relation whose columns no form before declares, or of a record: {relation:?} {:?}", relation.and_then(read_relation).and_then(|r| self.columns.get(&r))))
                }
            }
        }

        /// The name of each label of `form`: the reserved names, then the
        /// other labels in the order of their ids. A label of an `OUT` form
        /// takes the name of the column of its site whatever other label
        /// takes it, since the form writes each such site as `^<column>`.
        fn label_names(&self, form: &Form) -> Vec<(LabelId, Box<str>)> {
            let mut uses = Uses::default();
            self.form_uses(form, &mut uses);
            if matches!(form, Form::Out(_)) {
                let made = uses.made.iter().filter(|(label, _)| !uses.reserved.iter().any(|(id, _)| id == label));
                return uses.reserved.iter().cloned().chain(made.map(|(label, column)| (*label, column.as_str().into()))).collect();
            }
            let reserved: Vec<&str> = uses.reserved.iter().map(|(_, name)| &**name).collect();
            let mut names: Vec<(LabelId, Box<str>)> = uses.reserved.iter().cloned().collect();
            names.dedup_by_key(|(id, _)| *id);
            uses.made.sort_by_key(|(label, _)| label.0);
            for (label, base) in &uses.made {
                if names.iter().any(|(id, _)| id == label) {
                    continue;
                }
                let taken = |name: &str| names.iter().any(|(_, held)| &**held == name) || reserved.contains(&name);
                names.push((*label, label_name(base, taken).into()));
            }
            names
        }

        fn form_uses(&self, form: &Form, uses: &mut Uses) {
            match form {
                Form::Clause(clause) => self.body_uses(clause.value().body.value(), uses),
                Form::Instance(instance) => {
                    let instance = instance.value();
                    if let Some(key) = &instance.key {
                        self.body_uses(key.value().key.body.value(), uses);
                        key.value().inputs.iter().for_each(|input| self.input_uses(input.value(), uses));
                    }
                    instance.inputs.iter().for_each(|input| self.input_uses(input.value(), uses));
                }
                Form::Choose(choose) => {
                    let choose = choose.value();
                    choose.rows.iter().for_each(|rows| self.body_uses(rows.body.value(), uses));
                    self.body_uses(choose.from.value(), uses);
                    choose.never.iter().for_each(|never| self.body_uses(never.value(), uses));
                }
                Form::RigidDet(rigid) => {
                    let rigid = rigid.value();
                    rigid.key.iter().chain(rigid.instance.iter()).for_each(|clause| self.body_uses(clause.body.value(), uses));
                    for part in rigid.parts.iter() {
                        let part = part.value();
                        part.sites.iter().for_each(|site| self.site_uses(Some(&part.relation), site, uses));
                    }
                }
                Form::Out(out) => self.body_uses(out.value().key.body.value(), uses),
                _ => panic!("write_synthesized writes the forms a decode builds: RULE, DET, INIT, CHOOSE, RIGID_DET and OUT"),
            }
        }

        /// The uses of an input: its body, then its head.
        fn input_uses(&self, input: &InstanceInput, uses: &mut Uses) {
            self.body_uses(input.body.value(), uses);
            input.head.iter().for_each(|site| self.site_uses(None, site, uses));
        }

        fn body_uses(&self, body: &Body, uses: &mut Uses) {
            body.conjuncts.iter().for_each(|conjunct| self.conjunct_uses(conjunct, uses));
        }

        fn conjunct_uses(&self, conjunct: &Conjunct, uses: &mut Uses) {
            match conjunct {
                Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => atom.value().sites.iter().for_each(|site| self.site_uses(Some(&atom.value().relation), site, uses)),
                Conjunct::Not(Negated::Form(inner)) => self.conjunct_uses(inner, uses),
                Conjunct::Constraint(constraint) => {
                    for operand in [Some(constraint.first), constraint_second(constraint)].into_iter().flatten() {
                        if operand.fresh {
                            uses.made.push((operand.label, "V".to_owned()));
                        }
                    }
                }
                Conjunct::Or(branches) => branches.iter().for_each(|branch| self.body_uses(branch.value(), uses)),
                Conjunct::If { test, then, otherwise } => [test, then, otherwise].into_iter().for_each(|body| self.body_uses(body.value(), uses)),
                Conjunct::All { domain, body } => [domain, body].into_iter().for_each(|body| self.body_uses(body.value(), uses)),
            }
        }

        fn site_uses(&self, relation: Option<&RelationRef>, site: &Site, uses: &mut Uses) {
            let column = self.column_text(relation, &site.column);
            for arg in site.value.args.iter() {
                match arg {
                    SiteArg::Label(LabelUse::Fresh(id) | LabelUse::Key(id)) => uses.made.push((*id, column.clone())),
                    SiteArg::Label(LabelUse::Join(_) | LabelUse::Zero) => {}
                    SiteArg::NamedLabel { name, label: label @ (LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)) } => match written(name) {
                        Some(name) => uses.reserved.push((*id, name.into())),
                        None if matches!(label, LabelUse::Join(_)) => {}
                        None => uses.made.push((*id, column.clone())),
                    },
                    SiteArg::NamedLabel { label: LabelUse::Zero, .. } => {}
                    SiteArg::Field(_) => panic!("write_synthesized writes no record site"),
                }
            }
        }

        fn form(&mut self, form: &Form, names: &Names) -> Form {
            match form {
                Form::Clause(clause) => Form::Clause(Node::new(self.clause(clause.value(), names))),
                Form::Instance(instance) => Form::Instance(Node::new(self.instance(instance.value(), names))),
                Form::Choose(choose) => Form::Choose(Node::new(self.choose(choose.value(), names))),
                Form::RigidDet(rigid) => Form::RigidDet(Node::new(self.rigid_det(rigid.value(), names))),
                Form::Out(out) => Form::Out(Node::new(Out { key: self.key_body(&out.value().key, names) })),
                _ => panic!("write_synthesized writes the forms a decode builds: RULE, DET, INIT, CHOOSE, RIGID_DET and OUT"),
            }
        }

        fn clause(&mut self, clause: &Clause, names: &Names) -> Clause {
            let columns = named_columns(&clause.columns, names);
            let derived: Vec<String> = match (columns.is_empty(), clause.proposers.first()) {
                (true, Some(proposer)) => proposer_columns(self.registry, proposer).map_or_else(Vec::new, |columns| columns.iter().filter_map(|column| written(column).map(str::to_owned)).collect()),
                _ => columns.iter().filter_map(|column| written(&column.name).map(str::to_owned)).collect(),
            };
            self.columns.insert(clause.derives.clone(), derived);
            Clause { derives: program_relation(&clause.derives), body: self.body(&clause.body, names), columns, ..clause.clone() }
        }

        fn instance(&mut self, instance: &Instance, names: &Names) -> Instance {
            let component_ports = component(self.registry, &instance.component).expect("the lib names the component");
            let written_inputs: Vec<_> = component_ports.inputs.iter().map(|input| &input.port.name).collect();
            for port in component_ports.relation_ports(&written_inputs) {
                let name = OutputName { of: OutputOwner::Instance(instance.name.clone()), path: Arc::from([OutputStep::Port(port.name.clone())]) };
                self.columns.insert(ProgramRelation::Output(name), port.columns.iter().filter_map(|column| written(&column.name).map(str::to_owned)).collect());
            }
            let key = instance.key.as_ref().map(|key| {
                let value = key.value();
                let inputs = value.inputs.iter().map(|input| Node::new(self.input(input.value(), names))).collect();
                Node::new(KeyClause { key: self.key_body(&value.key, names), inputs })
            });
            let inputs = instance.inputs.iter().map(|input| Node::new(self.input(input.value(), names))).collect();
            Instance { name: InstanceName(declared(&instance.name.0)), component: instance.component.clone(), key, inputs }
        }

        fn choose(&mut self, choose: &Choose, names: &Names) -> Choose {
            let rows = choose.rows.as_ref().map(|rows| self.key_body(rows, names));
            let candidate_columns = named_columns(&choose.candidate_columns, names);
            let row_columns = rows.iter().flat_map(|rows| rows.columns.iter());
            let written_columns = row_columns.chain(candidate_columns.iter()).filter_map(|column| written(&column.name).map(str::to_owned)).collect();
            self.columns.insert(ProgramRelation::Declared(choose.name.clone()), written_columns);
            let never = choose.never.iter().map(|never| self.body(never, names)).collect();
            Choose { name: RelationName(declared(&choose.name.0)), rows, candidate_columns, from: self.body(&choose.from, names), from_inside_for: choose.from_inside_for, never }
        }

        fn rigid_det(&mut self, rigid: &RigidDet, names: &Names) -> RigidDet {
            let name = RigidDetName(declared(&rigid.name.0));
            let key = rigid.key.as_ref().map(|key| self.key_body(key, names));
            let instance = rigid.instance.as_ref().map(|instance| self.key_body(instance, names));
            let parts = rigid.parts.iter().map(|part| self.atom(part, names)).collect();
            let value = RigidDet { name, key, instance, parts };
            // The outputs of `rigid` hold the paths as the later sites name
            // them, and those of `value` the columns as written. A later site
            // names an output column by the slot that the decoder named it
            // with, which is not its position.
            for ((path, columns), (_, written_columns)) in rigid_outputs(rigid).into_iter().zip(rigid_outputs(&value)) {
                let output = OutputName { of: OutputOwner::RigidDet(rigid.name.clone()), path };
                let mut texts: Vec<String> = Vec::new();
                for (column, text) in columns.names().zip(written_columns.names()) {
                    let ColumnName::Slot(slot) = column else { continue };
                    texts.resize(texts.len().max(*slot as usize + 1), String::new());
                    texts[*slot as usize] = written(text).map(str::to_owned).unwrap_or_default();
                }
                self.columns.insert(ProgramRelation::Output(output), texts);
            }
            value
        }

        fn key_body(&self, key: &KeyBody, names: &Names) -> KeyBody {
            KeyBody { body: self.body(&key.body, names), columns: named_columns(&key.columns, names) }
        }

        fn input(&self, input: &InstanceInput, names: &Names) -> InstanceInput {
            InstanceInput { name: input.name.clone(), head: input.head.iter().map(|site| self.site(None, site, names)).collect(), body: self.body(&input.body, names) }
        }

        fn body(&self, body: &Node<Body>, names: &Names) -> Node<Body> {
            Node::new(Body { conjuncts: body.value().conjuncts.iter().map(|conjunct| self.conjunct(conjunct, names)).collect() })
        }

        fn conjunct(&self, conjunct: &Conjunct, names: &Names) -> Conjunct {
            let bodies = |bodies: &[Node<Body>]| -> Arc<[Node<Body>]> { bodies.iter().map(|body| self.body(body, names)).collect() };
            match conjunct {
                Conjunct::Atom(atom) => Conjunct::Atom(self.atom(atom, names)),
                Conjunct::Not(Negated::Atom(atom)) => Conjunct::Not(Negated::Atom(self.atom(atom, names))),
                Conjunct::Not(Negated::Form(inner)) => Conjunct::Not(Negated::Form(Arc::new(self.conjunct(inner, names)))),
                Conjunct::Constraint(constraint) => Conjunct::Constraint(*constraint),
                Conjunct::Or(branches) => Conjunct::Or(bodies(branches)),
                Conjunct::If { test, then, otherwise } => Conjunct::If { test: self.body(test, names), then: self.body(then, names), otherwise: self.body(otherwise, names) },
                Conjunct::All { domain, body } => Conjunct::All { domain: self.body(domain, names), body: self.body(body, names) },
            }
        }

        fn atom(&self, atom: &Node<Atom>, names: &Names) -> Node<Atom> {
            let atom = atom.value();
            Node::new(Atom { relation: relation_ref(&atom.relation), sites: atom.sites.iter().map(|site| self.site(Some(&atom.relation), site, names)).collect() })
        }

        fn site(&self, relation: Option<&RelationRef>, site: &Site, names: &Names) -> Site {
            let args = site.value.args.iter().map(|arg| match arg {
                SiteArg::NamedLabel { name: ColumnName::Slot(_), label: label @ (LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)) } => SiteArg::NamedLabel { name: ColumnName::Written(names.get(*id).into()), label: *label },
                other => other.clone(),
            });
            Site { column: ColumnName::Written(self.column_text(relation, &site.column).into()), value: SiteValue { args: args.collect() } }
        }
    }

    /// The labels of one form, collected in any order.
    #[derive(Default)]
    struct Uses {
        /// The labels a `NamedLabel` names, with the names, which no other
        /// label of the scope takes.
        reserved: Vec<(LabelId, Box<str>)>,
        /// Each label with the column of the site that makes it.
        made: Vec<(LabelId, String)>,
    }
}
