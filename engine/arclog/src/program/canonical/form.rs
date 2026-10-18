//! The byte encoding of a canonical form: the writer of its bytes, the tag
//! of each value's kind, the form of each node kind, and the name writers
//! through which a form names each relation and column it reads.

use std::hash::Hasher;

use super::*;
use crate::program::path::NodeRef;
use crate::hash::{StableHash, StableHasher};


/// A node kind that has a canonical form.
pub trait Canonical {
    /// Writes the value's canonical form into `out`, with each name the
    /// value reads written by `names`.
    ///
    /// The bytes written are equal for two values exactly where their
    /// canonical forms are equal.
    fn write_canonical(&self, out: &mut CanonicalWriter, search: &mut SearchBudget, names: &dyn NameWriter);

    /// Whether two values have equal canonical forms.
    fn canonical_eq(&self, other: &Self) -> bool;
}

/// How a canonical form writes each relation a node reads: as the file
/// writes it, [`AsWritten`], for a node's canonical hash, or, in the
/// resolver, as the resolved content the name stands for, for
/// [`crate::resolver::ResolvedContent`], in which a derived relation's
/// content is its clause.
pub trait NameWriter {
    /// Writes `relation` into `out`.
    fn write_name(&self, relation: &super::RelationRef, out: &mut CanonicalWriter);

    /// Writes `name`, the name that the form being written declares, into
    /// `out`: an `INIT`, `CHOOSE`, `RIGID_DET` or `DEMONSTRATED` form's.
    /// The resolver writes a mark that holds no name, so that the resolved
    /// content of a form holds no name of its own, as that of a clause
    /// holds no name of the relation it derives.
    fn write_own(&self, name: &super::DeclaredName, out: &mut CanonicalWriter);

    /// Writes a column of `relation` into `out`: a column that a site names,
    /// or that a clause gives the relation it derives. `column` is the
    /// column's path: its name, or, for a site on a field of a record, the
    /// record's column and then the field, as `[key, P]` for `(:P P2)` in
    /// `(:key (:P P2))`. For a [`SiteArg::NamedLabel`], the path is its
    /// site's path and then its name, as `[key, A]` for `A` in `(:key C A)`.
    /// The resolver writes its canonical position, as
    /// [`crate::resolver::ColumnPosition`] gives, so that names do not enter
    /// the resolved content. An instance input's head sites name columns of
    /// a lib port, which no [`super::RelationRef`] names, so they are written
    /// as the file writes them and never pass through this method.
    fn write_column(&self, relation: &super::RelationRef, column: &[super::ColumnName], out: &mut CanonicalWriter);
}

/// The relation whose columns a `DEMO_RULE` form's fields are: its
/// `&prediction` (`docs/arclog/arclog.md#demonstrated`).
pub(crate) fn prediction() -> RelationRef {
    RelationRef::Declared(RelationName(DeclaredName::Written(format!("{}prediction", crate::read::spelling::DECLARED_MARK).into())))
}


/// The writer of a canonical form: it keeps the bytes written, so that two
/// forms whose hashes match are compared by their bytes.
///
/// The encoding is self-delimiting: each value opens with a tag of its kind,
/// and each list and each string with its length, so two different values
/// never write the same bytes.
#[derive(Clone, Debug, Default)]
pub struct CanonicalWriter {
    pub(super) bytes: Vec<u8>,
}

impl CanonicalWriter {
    /// Writes `bytes` to the form.
    pub fn write(&mut self, bytes: &[u8]) {
        self.bytes.extend_from_slice(bytes);
    }

    /// The form written, with its hash under [`crate::hash::StableHasher`].
    pub fn finish(self) -> CanonicalForm {
        let mut hasher = StableHasher::new();
        hasher.write(&self.bytes);
        CanonicalForm { hash: hasher.finish128(), bytes: self.bytes.into() }
    }

    pub(super) fn tag(&mut self, tag: Tag) {
        self.bytes.push(tag as u8);
    }

    pub(super) fn byte(&mut self, byte: u8) {
        self.bytes.push(byte);
    }

    pub(super) fn int(&mut self, n: u32) {
        self.write(&n.to_le_bytes());
    }

    pub(crate) fn len(&mut self, n: usize) {
        self.int(u32::try_from(n).expect("a list of a node has fewer than 2^32 members"));
    }

    pub(super) fn flag(&mut self, flag: bool) {
        self.bytes.push(u8::from(flag));
    }

    pub(crate) fn text(&mut self, text: &str) {
        self.len(text.len());
        self.write(text.as_bytes());
    }

    /// Writes the bytes of a form written apart, with their length.
    pub(super) fn nested(&mut self, bytes: &[u8]) {
        self.len(bytes.len());
        self.write(bytes);
    }

    pub(super) fn option<T>(&mut self, value: Option<T>, write: impl FnOnce(&mut Self, T)) {
        match value {
            None => self.tag(Tag::None),
            Some(value) => {
                self.tag(Tag::Some);
                write(self, value);
            }
        }
    }

    pub(crate) fn declared(&mut self, name: &DeclaredName) {
        match name {
            DeclaredName::Written(text) => {
                self.tag(Tag::Written);
                self.text(text);
            }
            DeclaredName::Slot(slot) => {
                self.tag(Tag::Slot);
                self.int(*slot);
            }
        }
    }

    pub(crate) fn column(&mut self, name: &ColumnName) {
        match name {
            ColumnName::Written(text) => {
                self.tag(Tag::Written);
                self.text(text);
            }
            ColumnName::Slot(slot) => {
                self.tag(Tag::Slot);
                self.int(*slot);
            }
        }
    }

    /// Writes the path of an output after its owner, which tells apart
    /// the outputs of one node.
    pub(crate) fn output_path(&mut self, path: &[OutputStep]) {
        self.len(path.len());
        for step in path {
            match step {
                OutputStep::Port(port) => self.port_step(port),
                OutputStep::Part(part) => {
                    self.tag(Tag::PartStep);
                    self.declared(part);
                }
                OutputStep::Pose => self.tag(Tag::PoseStep),
            }
        }
    }

    /// Writes the port `port` as a step of an output's path names it.
    pub(crate) fn port_step(&mut self, PortName(port): &PortName) {
        self.tag(Tag::PortStep);
        self.text(port);
    }

    pub(super) fn column_path(&mut self, path: &[ColumnName]) {
        self.len(path.len());
        for name in path {
            self.column(name);
        }
    }
}

/// The tag of each kind of value a canonical form writes.
#[derive(Clone, Copy)]
#[repr(u8)]
pub(super) enum Tag {
    None,
    Some,
    Written,
    Slot,
    Fact,
    Lib,
    Declared,
    Output,
    DefinedPort,
    InstanceOwner,
    RigidDetOwner,
    PortStep,
    PartStep,
    PoseStep,
    Program,
    Claim,
    Clause,
    Instance,
    Choose,
    RigidDet,
    Demonstrated,
    Alts,
    Alt,
    AltForm,
    AltNested,
    Body,
    Atom,
    NotAtom,
    NotForm,
    Constraint,
    Or,
    If,
    All,
    Site,
    ArgLabel,
    ArgField,
    Fresh,
    Join,
    Key,
    Zero,
    KeyClause,
    KeyBody,
    Input,
    DemoRule,
    Param,
    Rows,
    Grids,
    Derivation,
    Integer,
    Orientation,
    List,
    Arcdata,
    AltsRecord,
    ApproximatedRecord,
    Concept,
    AltVerdict,
    Any,
    Other,
    Undefined,
    // The vertex colors and edge labels of a scope's graph.
    Root,
    Label,
    Member,
    Branch,
    Part,
    Head,
    One,
    Column,
    Form,
    ArgNamedLabel,
}

/// A canonical form, as its bytes and their hash.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct CanonicalForm {
    pub hash: StableHash,
    pub bytes: std::sync::Arc<[u8]>,
}

impl std::hash::Hash for CanonicalForm {
    /// Hashes `hash` alone, so a lookup hashes no bytes.
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.hash.hash(state);
    }
}

/// Each name as the file writes it.
#[derive(Clone, Copy, Debug, Default)]
pub struct AsWritten;

impl NameWriter for AsWritten {
    fn write_name(&self, relation: &super::RelationRef, out: &mut CanonicalWriter) {
        match relation {
            RelationRef::Fact(fact) => {
                out.tag(Tag::Fact);
                out.byte(*fact as u8);
            }
            RelationRef::Lib(crate::registry::LibName(name)) => {
                out.tag(Tag::Lib);
                out.text(name);
            }
            RelationRef::Declared(RelationName(name)) => {
                out.tag(Tag::Declared);
                out.declared(name);
            }
            RelationRef::Output(name) => {
                out.tag(Tag::Output);
                match &name.of {
                    OutputOwner::Instance(InstanceName(owner)) => {
                        out.tag(Tag::InstanceOwner);
                        out.declared(owner);
                    }
                    OutputOwner::RigidDet(RigidDetName(owner)) => {
                        out.tag(Tag::RigidDetOwner);
                        out.declared(owner);
                    }
                }
                out.output_path(&name.path);
            }
            RelationRef::DefinedPort(PortName(port)) => {
                out.tag(Tag::DefinedPort);
                out.text(port);
            }
        }
    }

    fn write_own(&self, name: &super::DeclaredName, out: &mut CanonicalWriter) {
        out.declared(name);
    }

    /// Writes `column` as given. The path of a [`SiteArg::NamedLabel`]
    /// holds its name whether or not its site reads a record, so a renaming
    /// of such a label changes the form, as [`canonical_hash`] gives.
    fn write_column(&self, _relation: &super::RelationRef, column: &[super::ColumnName], out: &mut CanonicalWriter) {
        out.column_path(column);
    }
}

/// The hash of the canonical form of `value`.
///
/// Two values whose forms are equal under a reorder and a renaming may still
/// hash apart in two cases. A body whose search reaches
/// [`SEARCH_NODE_CAP`] takes the least labeling the search has found, which
/// may differ between the two. A label that stands alone at a site on a
/// column of a type parameter, `(:v *Col)` against `(:v *X)` where `v` holds
/// no record, enters the form by its name, since the value does not tell it
/// from a partial read of the field of that name, `(:key *E)`; the resolved
/// content of the two is equal.
pub fn canonical_hash<T: Canonical>(value: &T) -> StableHash {
    form_of(value).0.hash
}

/// The canonical form of `value` under [`AsWritten`] with a new
/// [`SearchBudget`], and whether its search reached the cap.
pub(in crate::program) fn form_of<T: Canonical>(value: &T) -> (CanonicalForm, bool) {
    let mut search = SearchBudget::new();
    let mut out = CanonicalWriter::default();
    value.write_canonical(&mut out, &mut search, &AsWritten);
    (out.finish(), search.reached)
}

/// The canonical form of a form that is a label scope of its own, as
/// [`crate::program::LabelId`] gives scopes, under [`AsWritten`] with a new
/// [`SearchBudget`].
pub(crate) fn canonical_form(form: &Form) -> CanonicalForm {
    let mut search = SearchBudget::new();
    let mut out = CanonicalWriter::default();
    form_root(&mut Context::new(&mut search, &AsWritten), &mut out, form);
    out.finish()
}
impl LabelScope<'_> {

    /// Writes the part of the form that the scope's labels enter.
    pub(super) fn write(self, cx: &mut Context, out: &mut CanonicalWriter) {
        match self {
            LabelScope::Clause(clause) => clause.write_form(cx, out),
            LabelScope::Instance(instance) => instance.write_form(cx, out),
            LabelScope::Choose(choose) => choose.write_form(cx, out),
            LabelScope::RigidDet(rigid) => rigid.write_form(cx, out),
            LabelScope::DemonstratedKey(demonstrated) => demonstrated_key(cx, out, demonstrated),
            LabelScope::DemoRule(rule) => rule.write_form(cx, out),
            LabelScope::Body(body) => body.write_form(cx, out),
            LabelScope::Atom(atom) => atom.write_form(cx, out),
            LabelScope::KeyClause(key) => key.write_form(cx, out),
            LabelScope::InstanceInput(input) => input.write_form(cx, out),
        }
    }
}


/// The relation a clause or a `param` form names, as an atom reads it.
pub(crate) fn relation_of(relation: &ProgramRelation) -> RelationRef {
    match relation {
        ProgramRelation::Declared(name) => RelationRef::Declared(name.clone()),
        ProgramRelation::Output(name) => RelationRef::Output(name.clone()),
    }
}

/// The scope of a form that is a label scope of its own, as
/// [`crate::program::LabelId`] gives scopes, where its own content holds
/// labels.
pub(crate) fn form_scope(form: &Form) -> Option<LabelScope<'_>> {
    match form {
        Form::Claim(claim) => claim.value().scope(),
        Form::Clause(clause) => clause.value().scope(),
        Form::Instance(instance) => instance.value().scope(),
        Form::Choose(choose) => choose.value().scope(),
        Form::RigidDet(rigid) => rigid.value().scope(),
        Form::Demonstrated(demonstrated) => demonstrated.value().scope(),
        Form::Alts(alts) => alts.value().scope(),
    }
}

/// Whether `form`, a form of a `DEMO_RULE`, stands in the rule's label
/// scope.
pub(crate) fn shares_rule_scope(form: &Form) -> bool {
    match form {
        Form::Clause(_) | Form::Instance(_) | Form::Choose(_) | Form::RigidDet(_) => true,
        Form::Claim(_) | Form::Demonstrated(_) | Form::Alts(_) => false,
    }
}

/// Writes a form that is a label scope of its own, as
/// [`crate::program::LabelId`] gives scopes.
pub(super) fn form_root(cx: &mut Context, out: &mut CanonicalWriter, form: &Form) {
    let labels = form_scope(form).map(|scope| cx.labeling(scope).0);
    form_with(cx, out, form, labels);
}

/// Writes `form` with `labels`, or with the labels of the scope it stands
/// in where `labels` is `None`.
pub(super) fn form_with(cx: &mut Context, out: &mut CanonicalWriter, form: &Form, labels: Option<Labels>) {
    let mut write = |cx: &mut Context| match form {
        Form::Claim(claim) => claim.value().write_form(cx, out),
        Form::Clause(clause) => clause.value().write_form(cx, out),
        Form::Instance(instance) => instance.value().write_form(cx, out),
        Form::Choose(choose) => choose.value().write_form(cx, out),
        Form::RigidDet(rigid) => rigid.value().write_form(cx, out),
        Form::Demonstrated(demonstrated) => demonstrated.value().write_form(cx, out),
        Form::Alts(alts) => alts.value().write_form(cx, out),
    };
    match labels {
        Some(labels) => cx.with_labels(labels, write),
        None => write(cx),
    }
}

/// Writes `forms`, each a label scope of its own, as
/// [`crate::program::LabelId`] gives scopes.
pub(super) fn forms_root(cx: &mut Context, out: &mut CanonicalWriter, parent: NodeRef, forms: &[Form]) {
    out.len(forms.len());
    for form in forms.iter() {
        cx.child(parent, NodeRef::from(form), |cx| form_root(cx, out, form));
    }
}

pub(super) fn demonstrated_key(cx: &mut Context, out: &mut CanonicalWriter, demonstrated: &Demonstrated) {
    let parent = NodeRef::Demonstrated(demonstrated);
    out.option(demonstrated.key.as_ref(), |out, key| cx.child(parent, NodeRef::KeyClause(key.value()), |cx| key.value().write_form(cx, out)));
    out.len(demonstrated.inputs.len());
    for input in demonstrated.inputs.iter() {
        cx.child(parent, NodeRef::InstanceInput(input.value()), |cx| input.value().write_form(cx, out));
    }
}

pub(super) fn label_use(cx: &Context, out: &mut CanonicalWriter, label: LabelUse) {
    match label {
        LabelUse::Fresh(id) => {
            out.tag(Tag::Fresh);
            cx.label(out, id);
        }
        LabelUse::Join(id) => {
            out.tag(Tag::Join);
            cx.label(out, id);
        }
        LabelUse::Key(id) => {
            out.tag(Tag::Key);
            cx.label(out, id);
        }
        LabelUse::Zero => out.tag(Tag::Zero),
    }
}

pub(super) fn constraint_label(cx: &Context, out: &mut CanonicalWriter, label: ConstraintLabel) {
    out.flag(label.fresh);
    cx.label(out, label.label);
}

/// `prefix` followed by `column`: the column path of a site on `column`
/// within the site whose path is `prefix`, or of a
/// [`SiteArg::NamedLabel`] whose name is `column`.
pub(super) fn column_path(prefix: &[ColumnName], column: &ColumnName) -> Vec<ColumnName> {
    prefix.iter().chain(std::iter::once(column)).cloned().collect()
}

/// Writes `site`, with each column path as `column` writes it.
pub(super) fn site(cx: &Context, out: &mut CanonicalWriter, site_: &Site, prefix: &[ColumnName], column: &dyn Fn(&mut CanonicalWriter, &[ColumnName])) {
    let path = column_path(prefix, &site_.column);
    out.tag(Tag::Site);
    column(out, &path);
    out.len(site_.value.args.len());
    for arg in site_.value.args.iter() {
        match arg {
            SiteArg::Label(label) => {
                out.tag(Tag::ArgLabel);
                label_use(cx, out, *label);
            }
            SiteArg::NamedLabel { name, label } => {
                out.tag(Tag::ArgNamedLabel);
                column(out, &column_path(&path, name));
                label_use(cx, out, *label);
            }
            SiteArg::Field(field) => {
                out.tag(Tag::ArgField);
                site(cx, out, field, &path, column);
            }
        }
    }
}

/// Writes a key body, whose body is a child of `parent`, the node being
/// written.
pub(super) fn key_body(cx: &mut Context, out: &mut CanonicalWriter, parent: NodeRef, key: &KeyBody) {
    out.tag(Tag::KeyBody);
    cx.child(parent, NodeRef::Body(key.body.value()), |cx| key.body.value().write_form(cx, out));
    cx.columns(out, &key.columns, |out, name| out.column(name));
}

pub(super) fn data_value(out: &mut CanonicalWriter, value: &DataValue) {
    match value {
        DataValue::Integer(n) => {
            out.tag(Tag::Integer);
            out.write(&n.to_le_bytes());
        }
        DataValue::Orientation(name) => {
            out.tag(Tag::Orientation);
            out.text(name);
        }
        DataValue::List(values) => {
            out.tag(Tag::List);
            out.len(values.len());
            for value in values.iter() {
                data_value(out, value);
            }
        }
    }
}

pub(super) fn grid(out: &mut CanonicalWriter, grid: &Grid) {
    out.len(grid.rows.len());
    for row in grid.rows.iter() {
        out.len(row.len());
        for cell in row.iter() {
            out.option(cell.as_ref(), data_value);
        }
    }
    out.option(grid.anchor, |out, anchor| {
        out.int(anchor.row);
        out.int(anchor.column);
    });
}

pub(super) fn param_value(cx: &Context, out: &mut CanonicalWriter, value: &ParamValue) {
    match value {
        ParamValue::Rows(rows) => {
            out.tag(Tag::Rows);
            out.len(rows.len());
            for row in rows.iter() {
                out.len(row.len());
                for value in row.iter() {
                    data_value(out, value);
                }
            }
        }
        ParamValue::Grids(grids) => {
            out.tag(Tag::Grids);
            out.len(grids.len());
            for rows in grids.iter() {
                out.len(rows.before.len());
                for value in rows.before.iter() {
                    data_value(out, value);
                }
                grid(out, &rows.grid);
            }
        }
        ParamValue::Derivation { derivation, rows } => {
            out.tag(Tag::Derivation);
            cx.names.write_name(&RelationRef::Lib(derivation.clone()), out);
            out.len(rows.len());
            for row in rows.iter() {
                out.len(row.len());
                for field in row.iter() {
                    out.column(&field.column);
                    data_value(out, &field.value);
                }
            }
        }
    }
}

pub(super) fn alts_names(out: &mut CanonicalWriter, names: &[AltsName]) {
    out.len(names.len());
    for name in names {
        out.text(&name.0);
    }
}

pub(super) fn witnesses(cx: &Context, out: &mut CanonicalWriter, witnesses: &[Witness]) {
    out.len(witnesses.len());
    for witness in witnesses {
        out.text(&witness.id);
        out.byte(witness.plausibility as u8);
        match &witness.verdict {
            Verdict::Concept => out.tag(Tag::Concept),
            Verdict::Alt(name) => {
                out.tag(Tag::AltVerdict);
                out.text(&name.0);
            }
            Verdict::Any => out.tag(Tag::Any),
            Verdict::Other => out.tag(Tag::Other),
        }
        out.option(witness.body.as_ref(), |out, body| {
            out.len(body.relaxed.len());
            for slug in body.relaxed.iter() {
                out.text(&slug.0);
            }
            out.text(&body.separates.0);
            out.len(body.assigns.len());
            for (relation, value) in body.assigns.iter() {
                cx.names.write_name(&relation_of(relation), out);
                param_value(cx, out, value);
            }
            grid(out, &body.input);
            out.len(body.outputs.len());
            for output in body.outputs.iter() {
                out.len(output.names.len());
                for name in output.names.iter() {
                    out.len(name.len());
                    for case in name.iter() {
                        match case {
                            CaseRef::Concept => out.tag(Tag::Concept),
                            CaseRef::Alt(name) => {
                                out.tag(Tag::AltVerdict);
                                out.text(&name.0);
                            }
                        }
                    }
                }
                match &output.value {
                    OutputValue::Undefined => out.tag(Tag::Undefined),
                    OutputValue::Grids(grids) => {
                        out.tag(Tag::Grids);
                        out.len(grids.len());
                        for g in grids.iter() {
                            grid(out, g);
                        }
                    }
                }
            }
        });
    }
}

pub(super) fn alt_record(cx: &Context, out: &mut CanonicalWriter, record: &AltRecord) {
    out.text(&record.name.0);
    witnesses(cx, out, &record.witnesses);
    out.len(record.nested.len());
    for nested in record.nested.iter() {
        alt_record(cx, out, nested);
    }
}

/// The form of a node kind, written with the labels the writer holds.
pub(super) trait WriteForm {
    /// The scope of the labels the kind's own form holds, where the kind
    /// stands as a scope or as a node whose hash is taken apart from its
    /// scope.
    fn scope(&self) -> Option<LabelScope<'_>> {
        None
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter);
}

impl WriteForm for Demonstrated {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::DemonstratedKey(self))
    }

    /// Writes the form, with the key clause and the inputs under the labels
    /// the writer holds, and each `DEMO_RULE` form under its own.
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Demonstrated);
        cx.names.write_own(&self.name.0, out);
        demonstrated_key(cx, out, self);
        out.len(self.rules.len());
        for rule in self.rules.iter() {
            let rule = rule.value();
            cx.child(NodeRef::Demonstrated(self), NodeRef::DemoRule(rule), |cx| cx.in_scope(LabelScope::DemoRule(rule), |cx| rule.write_form(cx, out)));
        }
    }
}

impl WriteForm for Program {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Program);
        forms_root(cx, out, NodeRef::Program(self), &self.forms);
    }
}

impl WriteForm for Claim {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Claim);
        out.byte(self.kind as u8);
        out.text(&self.slug.0);
        out.text(&self.text.0);
        out.option(self.approximated.as_ref(), |out, text| out.text(&text.0));
        forms_root(cx, out, NodeRef::Claim(self), &self.forms);
    }
}

impl WriteForm for Clause {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Clause(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        let derives = relation_of(&self.derives);
        out.tag(Tag::Clause);
        out.byte(self.keyword as u8);
        cx.names.write_name(&derives, out);
        out.option(self.gloss.as_ref(), |out, text| out.text(&text.0));
        out.len(self.proposers.len());
        for proposer in self.proposers.iter() {
            cx.names.write_name(&RelationRef::Lib(proposer.clone()), out);
        }
        cx.child(NodeRef::Clause(self), NodeRef::Body(self.body.value()), |cx| self.body.value().write_form(cx, out));
        out.len(self.ones.len());
        for one in self.ones.iter() {
            out.len(one.key.len());
            for label in one.key.iter() {
                cx.label(out, *label);
            }
        }
        let names = cx.names;
        cx.columns(out, &self.columns, |out, name| names.write_column(&derives, std::slice::from_ref(name), out));
    }
}

impl WriteForm for Body {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Body(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Body);
        cx.sorted(out, NodeRef::Body(self), &self.conjuncts, NodeRef::Conjunct, |cx, out, conjunct| write_conjunct(cx, out, conjunct));
    }
}

pub(super) fn write_conjunct(cx: &mut Context, out: &mut CanonicalWriter, conjunct: &Conjunct) {
    match conjunct {
        Conjunct::Atom(atom) => {
            out.tag(Tag::Atom);
            atom.value().write_form(cx, out);
        }
        Conjunct::Not(Negated::Atom(atom)) => {
            out.tag(Tag::NotAtom);
            atom.value().write_form(cx, out);
        }
        Conjunct::Not(Negated::Form(form)) => {
            out.tag(Tag::NotForm);
            cx.child(NodeRef::Conjunct(conjunct), NodeRef::Conjunct(form), |cx| write_conjunct(cx, out, form));
        }
        Conjunct::Constraint(constraint) => {
            out.tag(Tag::Constraint);
            out.byte(constraint.op as u8);
            constraint_label(cx, out, constraint.first);
            match constraint.second {
                Operand::Label(label) => {
                    out.tag(Tag::ArgLabel);
                    constraint_label(cx, out, label);
                }
                Operand::Zero => out.tag(Tag::Zero),
            }
        }
        Conjunct::Or(branches) => {
            out.tag(Tag::Or);
            cx.sorted(out, NodeRef::Conjunct(conjunct), branches, |branch| NodeRef::Body(branch.value()), |cx, out, branch| branch.value().write_form(cx, out));
        }
        Conjunct::If { test, then, otherwise } => {
            out.tag(Tag::If);
            for part in [test, then, otherwise] {
                cx.child(NodeRef::Conjunct(conjunct), NodeRef::Body(part.value()), |cx| part.value().write_form(cx, out));
            }
        }
        Conjunct::All { domain, body } => {
            out.tag(Tag::All);
            for part in [domain, body] {
                cx.child(NodeRef::Conjunct(conjunct), NodeRef::Body(part.value()), |cx| part.value().write_form(cx, out));
            }
        }
    }
}

impl WriteForm for Atom {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Atom(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        let names = cx.names;
        names.write_name(&self.relation, out);
        out.len(self.sites.len());
        for s in self.sites.iter() {
            site(cx, out, s, &[], &|out, path| names.write_column(&self.relation, path, out));
        }
    }
}

impl WriteForm for Instance {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Instance(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Instance);
        cx.names.write_own(&self.name.0, out);
        cx.names.write_name(&RelationRef::Lib(self.component.clone()), out);
        let parent = NodeRef::Instance(self);
        out.option(self.key.as_ref(), |out, key| cx.child(parent, NodeRef::KeyClause(key.value()), |cx| key.value().write_form(cx, out)));
        out.len(self.inputs.len());
        for input in self.inputs.iter() {
            cx.child(parent, NodeRef::InstanceInput(input.value()), |cx| input.value().write_form(cx, out));
        }
    }
}

impl WriteForm for KeyClause {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::KeyClause(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::KeyClause);
        let parent = NodeRef::KeyClause(self);
        key_body(cx, out, parent, &self.key);
        out.len(self.inputs.len());
        for input in self.inputs.iter() {
            cx.child(parent, NodeRef::InstanceInput(input.value()), |cx| input.value().write_form(cx, out));
        }
    }
}

impl WriteForm for InstanceInput {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::InstanceInput(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Input);
        out.text(&self.name.0);
        out.len(self.head.len());
        for head in self.head.iter() {
            site(cx, out, head, &[], &|out, path| out.column_path(path));
        }
        cx.child(NodeRef::InstanceInput(self), NodeRef::Body(self.body.value()), |cx| self.body.value().write_form(cx, out));
    }
}

impl WriteForm for Choose {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Choose(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Choose);
        cx.names.write_own(&self.name.0, out);
        let parent = NodeRef::Choose(self);
        out.option(self.rows.as_ref(), |out, rows| key_body(cx, out, parent, rows));
        let relation = RelationRef::Declared(self.name.clone());
        let names = cx.names;
        cx.columns(out, &self.candidate_columns, |out, name| names.write_column(&relation, std::slice::from_ref(name), out));
        cx.child(parent, NodeRef::Body(self.from.value()), |cx| self.from.value().write_form(cx, out));
        out.flag(self.from_inside_for);
        out.len(self.never.len());
        for never in self.never.iter() {
            cx.child(parent, NodeRef::Body(never.value()), |cx| never.value().write_form(cx, out));
        }
    }
}

impl WriteForm for RigidDet {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::RigidDet(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::RigidDet);
        cx.names.write_own(&self.name.0, out);
        let parent = NodeRef::RigidDet(self);
        out.option(self.key.as_ref(), |out, key| key_body(cx, out, parent, key));
        out.option(self.instance.as_ref(), |out, instance| key_body(cx, out, parent, instance));
        out.len(self.parts.len());
        for part in self.parts.iter() {
            cx.child(parent, NodeRef::Atom(part.value()), |cx| part.value().write_form(cx, out));
        }
    }
}

impl WriteForm for DemoRule {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::DemoRule(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::DemoRule);
        out.text(&self.name.0);
        let names = cx.names;
        let prediction = prediction();
        cx.columns(out, &self.fields, |out, name| names.write_column(&prediction, std::slice::from_ref(name), out));
        out.option(self.text.as_ref(), |out, text| out.text(&text.0));
        out.len(self.forms.len());
        for form in self.forms.iter() {
            cx.child(NodeRef::DemoRule(self), NodeRef::from(form), |cx| {
                if shares_rule_scope(form) {
                    form_with(cx, out, form, None)
                } else {
                    form_root(cx, out, form)
                }
            });
        }
    }
}

impl WriteForm for Alts {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Alts);
        out.text(&self.name.0);
        out.text(&self.gloss.0);
        out.text(&self.concept.0);
        out.len(self.alts.len());
        for alt in self.alts.iter() {
            cx.child(NodeRef::Alts(self), NodeRef::Alt(alt.value()), |cx| alt.value().write_form(cx, out));
        }
    }
}

impl WriteForm for Alt {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Alt);
        out.text(&self.name.0);
        out.len(self.items.len());
        for item in self.items.iter() {
            cx.child(NodeRef::Alt(self), NodeRef::from(item), |cx| match item {
                AltItem::Form(form) => {
                    out.tag(Tag::AltForm);
                    form_root(cx, out, form);
                }
                AltItem::Alt(alt) => {
                    out.tag(Tag::AltNested);
                    alt.value().write_form(cx, out);
                }
            });
        }
    }
}

impl WriteForm for Param {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Param);
        cx.names.write_name(&relation_of(&self.name), out);
        out.len(self.columns.len());
        for column in self.columns.iter() {
            out.byte(*column as u8);
        }
        param_value(cx, out, &self.value);
    }
}

impl WriteForm for Arcdata {
    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        out.tag(Tag::Arcdata);
        out.option(self.representative.as_ref(), |out, representative| {
            out.text(&representative.task_id);
            out.option(representative.case.as_ref(), |out, names| alts_names(out, names));
        });
        out.len(self.params.len());
        for param in self.params.iter() {
            param.value().write_form(cx, out);
        }
        out.len(self.excludes.len());
        for exclude in self.excludes.iter() {
            alts_names(out, &exclude.combination);
            out.option(exclude.reason.as_ref(), |out, text| out.text(&text.0));
        }
        out.len(self.witness_records.len());
        for record in self.witness_records.iter() {
            match record {
                WitnessRecord::Alts { name, alts } => {
                    out.tag(Tag::AltsRecord);
                    out.text(&name.0);
                    out.len(alts.len());
                    for alt in alts.iter() {
                        alt_record(cx, out, alt);
                    }
                }
                WitnessRecord::Approximated { claim, witnesses: list } => {
                    out.tag(Tag::ApproximatedRecord);
                    out.text(&claim.0);
                    witnesses(cx, out, list);
                }
            }
        }
    }
}

impl<T: WriteForm> Canonical for T {
    fn write_canonical(&self, out: &mut CanonicalWriter, search: &mut SearchBudget, names: &dyn NameWriter) {
        let mut cx = Context::new(search, names);
        if let Some(scope) = self.scope() {
            cx.labels = cx.labeling(scope).0;
        }
        self.write_form(&mut cx, out);
    }

    fn canonical_eq(&self, other: &Self) -> bool {
        form_of(self).0.bytes == form_of(other).0.bytes
    }
}
