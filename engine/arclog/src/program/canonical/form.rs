//! The byte encoding of a canonical form: the writer of its bytes, the tag
//! of each value's kind, the form of each node kind, and the name writers
//! through which a form writes each relation and column it reads.

use std::hash::Hasher;

use super::*;
use super::walk::{self, Open, ScopeSink};
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

    /// Writes into `out` the form of `name`, the name that the form being
    /// written declares: an `INIT`, `CHOOSE`, `RIGID_DET` or `DEMONSTRATED`
    /// form's.
    fn write_own(&self, name: &super::DeclaredName, out: &mut CanonicalWriter);

    /// Writes a column of `relation` into `out`: a column of a site, or a
    /// column that a clause gives the relation it derives. `column` is the
    /// column's path: its name, or, for a site on a field of a record, the
    /// record's column and then the field, as `[key, P]` for `(:P P2)` in
    /// `(:key (:P P2))`. For a [`SiteArg::NamedLabel`], the path is its
    /// site's path and then its name, as `[key, A]` for `A` in `(:key C A)`.
    /// An instance input's head sites stand on columns of a lib port, which
    /// no [`super::RelationRef`] refers to, so they are written as the file
    /// writes them and never pass through this method.
    fn write_column(&self, relation: &super::RelationRef, column: &[super::ColumnName], out: &mut CanonicalWriter);

    /// The count of the other orders of the columns of `relation` under
    /// which its content is the same, as a symmetry of the clause that
    /// derives it gives them. A read of `relation` reads the same rows in
    /// each of those orders.
    fn column_orders(&self, _relation: &super::RelationRef) -> usize {
        0
    }

    /// Writes a column of `relation` as [`NameWriter::write_column`] does,
    /// at its position in the order `order` of the columns of `relation`:
    /// `0` for the order of its rows, and from `1` each order that
    /// [`NameWriter::column_orders`] counts.
    fn write_column_in(&self, relation: &super::RelationRef, column: &[super::ColumnName], _order: usize, out: &mut CanonicalWriter) {
        self.write_column(relation, column, out);
    }

    /// Whether the forms written through this writer have the order of their
    /// named sites and head sites outside them, as a write for features has
    /// them. A write under such a writer is kept in no cache of a form's
    /// writes.
    fn feature_sites(&self) -> bool {
        false
    }

    /// Called where the search for a canonical labeling under this writer
    /// passes [`SEARCH_NODE_CAP`], so that a writer which hands out the
    /// content it writes can refuse it ([`LabelingBound`]).
    fn labeling_bound_reached(&self) {}
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

    /// Writes a declared name or a column name.
    pub(crate) fn name<'n>(&mut self, name: impl Into<NameRef<'n>>) {
        match name.into() {
            NameRef::Written(text) => {
                self.tag(Tag::Written);
                self.text(text);
            }
            NameRef::Slot(slot) => {
                self.tag(Tag::Slot);
                self.int(slot);
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
                    self.name(part);
                }
                OutputStep::Pose => self.tag(Tag::PoseStep),
            }
        }
    }

    /// Writes the port `port` as a step of an output's path.
    pub(crate) fn port_step(&mut self, PortName(port): &PortName) {
        self.tag(Tag::PortStep);
        self.text(port);
    }

    pub(super) fn column_path(&mut self, path: &[ColumnName]) {
        self.len(path.len());
        for name in path {
            self.name(name);
        }
    }
}

/// A [`DeclaredName`] or a [`ColumnName`], borrowed: its text as the file
/// writes it, or its slot.
#[derive(Clone, Copy)]
pub(crate) enum NameRef<'n> {
    Written(&'n str),
    Slot(u32),
}

impl<'n> From<&'n DeclaredName> for NameRef<'n> {
    fn from(name: &'n DeclaredName) -> Self {
        match name {
            DeclaredName::Written(text) => NameRef::Written(text),
            DeclaredName::Slot(slot) => NameRef::Slot(*slot),
        }
    }
}

impl<'n> From<&'n ColumnName> for NameRef<'n> {
    fn from(name: &'n ColumnName) -> Self {
        match name {
            ColumnName::Written(text) => NameRef::Written(text),
            ColumnName::Slot(slot) => NameRef::Slot(*slot),
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
    Out,
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
                match fact {
                    FactRelation::Input => out.byte(0),
                    FactRelation::ExInput => out.byte(1),
                    FactRelation::ExOutput => out.byte(2),
                    FactRelation::Output => out.byte(3),
                    FactRelation::Program(program) => {
                        out.byte(4);
                        out.text(program.name());
                    }
                    FactRelation::Name(name) => {
                        out.byte(5);
                        out.text(&name.text());
                    }
                    FactRelation::Stored(name) => {
                        out.byte(6);
                        out.text(&name.text());
                    }
                }
            }
            RelationRef::Lib(crate::registry::LibName(name)) => {
                out.tag(Tag::Lib);
                out.text(name);
            }
            RelationRef::Declared(RelationName(name)) => {
                out.tag(Tag::Declared);
                out.name(name);
            }
            RelationRef::Output(name) => {
                out.tag(Tag::Output);
                match &name.of {
                    OutputOwner::Instance(InstanceName(owner)) => {
                        out.tag(Tag::InstanceOwner);
                        out.name(owner);
                    }
                    OutputOwner::RigidDet(RigidDetName(owner)) => {
                        out.tag(Tag::RigidDetOwner);
                        out.name(owner);
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
        out.name(name);
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
/// hash apart in two cases. A value whose search passes
/// [`SEARCH_NODE_CAP`] ends with a labeling that may differ between the two;
/// the checks refuse such a value ([`LabelingBound`]), so no caller gets its
/// hash. A label that stands alone at a site on a
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
        cx.walk_into(out, |cx| walk::scope(cx, (), self));
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
        Form::Out(out) => out.value().scope(),
        Form::Demonstrated(demonstrated) => demonstrated.value().scope(),
        Form::Alts(alts) => alts.value().scope(),
    }
}

/// The labels of `scope`, in the order of their canonical labeling with
/// each name as the file writes it.
pub(crate) fn scope_labels(scope: LabelScope<'_>) -> Box<[LabelId]> {
    canonical_labeling(scope, &AsWritten, &mut SearchBudget::new()).positions.iter().map(|(label, _)| *label).collect()
}

/// The labels of the scope of `form`, as [`form_scope`] gives it, as
/// [`scope_labels`] gives them.
pub(crate) fn form_scope_labels(form: &Form) -> &[LabelId] {
    crate::eval::once_noted(&cache(form).scope_labels, || super::order::CanonicalOrder::root_labels(form))
}

/// Whether `form` is a `RIGID_DET` form or holds one, at any depth, as a
/// `DEMONSTRATED` form's rule does.
pub(crate) fn holds_rigid_det(form: &Form) -> bool {
    fn holds(node: NodeRef<'_>) -> bool {
        matches!(node, NodeRef::RigidDet(_)) || node.children().into_iter().any(holds)
    }
    *cache(form).holds_rigid_det.get_or_init(|| holds(NodeRef::from(form)))
}

/// What the node of `form` keeps.
pub(super) fn cache(form: &Form) -> &FormCache {
    let cache = match form {
        Form::Claim(node) => &node.shared.cache,
        Form::Clause(node) => &node.shared.cache,
        Form::Instance(node) => &node.shared.cache,
        Form::Choose(node) => &node.shared.cache,
        Form::RigidDet(node) => &node.shared.cache,
        Form::Out(node) => &node.shared.cache,
        Form::Demonstrated(node) => &node.shared.cache,
        Form::Alts(node) => &node.shared.cache,
    };
    cache.get_or_init(Box::default)
}

/// Whether the form at `index` of `rule` stands in the rule's label scope:
/// a clause, `INIT`, `CHOOSE` or `RIGID_DET` form that no `ALT` gave it.
pub(crate) fn shares_rule_scope(rule: &DemoRule, index: usize) -> bool {
    let kind = match &rule.forms[index] {
        Form::Clause(_) | Form::Instance(_) | Form::Choose(_) | Form::RigidDet(_) => true,
        Form::Claim(_) | Form::Demonstrated(_) | Form::Alts(_) | Form::Out(_) => false,
    };
    kind && !rule.forms.from_alt(index)
}

/// Whether `child`, the child at `index` of `parent` as
/// [`NodeRef::children`] gives it, is a label scope of its own, as
/// [`crate::program::LabelId`] gives scopes: each form of a program, a
/// claim or an `ALT` block, a `DEMO_RULE` form of a
/// `DEMONSTRATED` form, and a form of a `DEMO_RULE` form that does not
/// share the rule's scope, as `shares_rule_scope` gives.
pub fn opens_scope(parent: NodeRef<'_>, index: usize, child: NodeRef<'_>) -> bool {
    match parent {
        NodeRef::Program(_) | NodeRef::Claim(_) | NodeRef::Alt(_) => !matches!(child, NodeRef::Alt(_)),
        NodeRef::Demonstrated(_) => matches!(child, NodeRef::DemoRule(_)),
        NodeRef::DemoRule(rule) => !shares_rule_scope(rule, index),
        _ => false,
    }
}

/// Writes a form that is a label scope of its own, as
/// [`crate::program::LabelId`] gives scopes.
pub(super) fn form_root(cx: &mut Context, out: &mut CanonicalWriter, form: &Form) {
    let labels = form_scope(form).map(|scope| cx.recorded_labeling(scope));
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
        Form::Out(form) => form.value().write_form(cx, out),
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

pub(super) fn label_use(cx: &Context, out: &mut CanonicalWriter, label: LabelUse) {
    match label {
        // The `*` stands at the first site in written order, so it moves with
        // a reorder and is not part of the form.
        LabelUse::Fresh(id) | LabelUse::Join(id) => {
            out.tag(Tag::Join);
            cx.label(out, id);
        }
        // The `^` stands at the first site in written order too, so it moves with a reorder of sites, atoms or
        // branches. The key's columns, which the form writes with the labels' positions, hold which labels are the key's.
        LabelUse::Key(id) => {
            out.tag(Tag::Join);
            cx.label(out, id);
        }
        LabelUse::Zero => out.tag(Tag::Zero),
    }
}

/// Normalize converse comparisons; equality and inequality are symmetric,
/// whichever operand the `*` stands on.
pub(crate) fn normalized_constraint(c:&Constraint)->(ConstraintOp,[Option<ConstraintLabel>;2],bool) {
    let operands=[Some(c.first),constraint_second(c)];
    match c.op {
        ConstraintOp::Gt=>(ConstraintOp::Lt,[operands[1],operands[0]],false),
        ConstraintOp::Ge=>(ConstraintOp::Le,[operands[1],operands[0]],false),
        op=>(op,operands,matches!(op,ConstraintOp::Eq|ConstraintOp::Ne)),
    }
}

pub(super) fn constraint_label(cx: &Context, out: &mut CanonicalWriter, label: ConstraintLabel) {
    cx.label(out, label.label);
}

/// `prefix` followed by `column`: the column path of a site on `column`
/// within the site whose path is `prefix`, or of a
/// [`SiteArg::NamedLabel`] whose name is `column`.
pub(super) fn column_path(prefix: &[ColumnName], column: &ColumnName) -> Vec<ColumnName> {
    prefix.iter().chain(std::iter::once(column)).cloned().collect()
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
        cx.walk_into(out, |cx| walk::demonstrated_key(cx, (), self));
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
        cx.walk_into(out, |cx| walk::clause(cx, (), 0, self));
    }
}

impl WriteForm for Body {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Body(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::body(cx, (), Tag::Body, 0, self));
    }
}

impl WriteForm for Atom {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Atom(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::atom(cx, (), Tag::Part, 0, self, false, false));
    }
}

impl WriteForm for Instance {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Instance(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::instance(cx, (), 0, self));
    }
}

impl WriteForm for KeyClause {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::KeyClause(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::key_clause(cx, (), self));
    }
}

impl WriteForm for InstanceInput {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::InstanceInput(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::input(cx, (), 0, self));
    }
}

impl WriteForm for Choose {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Choose(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::choose(cx, (), 0, self));
    }
}

impl WriteForm for RigidDet {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::RigidDet(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::rigid_det(cx, (), 0, self));
    }
}

impl WriteForm for Out {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::Out(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::out(cx, (), 0, self));
    }
}

impl WriteForm for DemoRule {
    fn scope(&self) -> Option<LabelScope<'_>> {
        Some(LabelScope::DemoRule(self))
    }

    fn write_form(&self, cx: &mut Context, out: &mut CanonicalWriter) {
        cx.walk_into(out, |cx| walk::demo_rule(cx, (), self));
    }
}

/// The form writer takes from the walk the bytes of each node, into the
/// bytes of the node being written.
impl<'a> ScopeSink<'a> for Context<'_> {
    type At = ();

    fn feature_sites(&self) -> bool { self.feature_sites }

    fn open(&mut self, _at: (), _role: Tag, _index: usize, node: Open<'a>) {
        let names = self.names;
        let out = &mut self.out;
        match node {
            Open::Clause(clause) => {
                out.tag(Tag::Clause);
                out.byte(clause.keyword as u8);
                names.write_name(&relation_of(&clause.derives), out);
                out.option(clause.gloss.as_ref(), |out, text| out.text(&text.0));
                out.len(clause.proposers.len());
                for proposer in clause.proposers.iter() {
                    names.write_name(&RelationRef::Lib(proposer.clone()), out);
                }
            }
            Open::Instance(instance) => {
                self.head_fields = HeadFields::default();
                out.tag(Tag::Instance);
                names.write_own(&instance.name.0, out);
                names.write_name(&RelationRef::Lib(instance.component.clone()), out);
            }
            Open::Choose(choose) => {
                out.tag(Tag::Choose);
                names.write_own(&choose.name.0, out);
            }
            Open::RigidDet(rigid) => {
                out.tag(Tag::RigidDet);
                names.write_own(&rigid.name.0, out);
            }
            Open::Out(_) => out.tag(Tag::Out),
            Open::DemoRule(rule) => {
                out.tag(Tag::DemoRule);
                out.text(&rule.name.0);
            }
            Open::KeyClause => out.tag(Tag::KeyClause),
            Open::KeyBody => out.tag(Tag::KeyBody),
            Open::Input(input) => {
                out.tag(Tag::Input);
                out.text(&input.name.0);
            }
            Open::Head => {}
            Open::Body => out.tag(Tag::Body),
            Open::Atom { atom, negated, member } => {
                if member {
                    out.tag(if negated { Tag::NotAtom } else { Tag::Atom });
                }
                names.write_name(&atom.relation, out);
            }
            Open::NotForm => out.tag(Tag::NotForm),
            Open::Constraint(constraint) => {
                out.tag(Tag::Constraint);
                out.byte(normalized_constraint(constraint).0 as u8);
            }
            Open::Or => out.tag(Tag::Or),
            Open::If => out.tag(Tag::If),
            Open::All => out.tag(Tag::All),
        }
    }

    fn child(&mut self, parent: NodeRef<'a>, child: NodeRef<'a>, visit: impl FnOnce(&mut Self)) {
        Context::child(self, parent, child, visit);
    }

    fn children_order(&mut self, source_indices: &[u32]) {
        if let Some(order) = &mut self.order {
            order.lists.insert(NodePath(self.path.clone().into()), source_indices.into());
        }
    }

    /// Writes `members` sorted by the bytes of their forms, less those at
    /// `repeats`, and records the order of all of them.
    ///
    /// The recorded order maps each canonical position to a member's index
    /// in `members`, and [`CanonicalOrder`] reads a step at `parent` as a
    /// position in that list, so `members` must be the whole list of the
    /// children of `parent`, in order.
    ///
    /// # Panics
    ///
    /// Where the write records a [`CanonicalOrder`] and a member's index
    /// among the children of `parent` is not its index in `members`, or
    /// `members` does not hold every child of `parent`, a fault of the path
    /// table or of the form writer.
    fn members<T>(&mut self,_at:(), parent: NodeRef<'a>, members: &'a [T], pinned:&[usize],repeats:&[usize],node: impl Fn(&'a T) -> NodeRef<'a>, visit: impl Fn(&mut Self, (), &'a T)) {
        let mut forms: Vec<(usize,Vec<u8>, u32)> = Vec::with_capacity(members.len());
        for (member, index) in members.iter().zip(0u32..) {
            let outer = std::mem::take(&mut self.out);
            let step = || {
                let step = child_step(parent, node(member));
                assert_eq!(step, index, "{CHILD_FAULT}");
                step
            };
            self.at_step(step, |cx| visit(cx, (),member));
            forms.push((pinned.iter().position(|i|*i==index as usize).unwrap_or(pinned.len()),std::mem::replace(&mut self.out, outer).bytes, index));
        }
        forms.sort();
        if let Some(order) = &mut self.order {
            // The members are the first children of `parent`; the children after them stay in place.
            let children = parent.children().len();
            assert!(members.len() <= children, "{CHILD_FAULT}");
            order.lists.insert(NodePath(self.path.clone().into()), forms.iter().map(|(_,_, index)| *index).chain(members.len() as u32..children as u32).collect());
            order.repeats |= !repeats.is_empty();
        }
        let written = || forms.iter().filter(|(_, _, index)| !repeats.contains(&(*index as usize)));
        self.out.len(written().count());
        for (_,bytes, _) in written() {
            self.out.nested(bytes);
        }
    }

    fn head_field(&mut self, port: &ColumnName, key: HeadKey) -> ColumnName {
        head_field(&mut self.head_fields, port, key)
    }

    fn len(&mut self, len: usize) {
        self.out.len(len);
    }

    fn option(&mut self, present: bool) {
        self.out.tag(if present { Tag::Some } else { Tag::None });
    }

    /// Writes the sites in each order of the columns of the relation, and
    /// keeps the least bytes, so that the order of its rows, which a symmetry
    /// of its clause leaves open, is not part of the form.
    fn atom_sites(&mut self, at: (), atom: &'a Atom, visit: impl Fn(&mut Self, ())) {
        let orders = self.names.column_orders(&atom.relation);
        if orders == 0 {
            return visit(self, at);
        }
        let recorded = self.order.take();
        let outer = std::mem::take(&mut self.out);
        let mut least: Option<(Vec<u8>, usize)> = None;
        for order in 0..=orders {
            self.column_order = order;
            visit(self, at);
            let bytes = std::mem::take(&mut self.out).bytes;
            if least.as_ref().is_none_or(|(form, _)| bytes < *form) {
                least = Some((bytes, order));
            }
        }
        self.out = outer;
        self.order = recorded;
        self.column_order = least.expect("an order of the columns").1;
        visit(self, at);
        self.column_order = 0;
    }

    fn site(&mut self, _at: (), path: &[ColumnName], args: usize, relation: Option<&RelationRef>) {
        self.out.tag(Tag::Site);
        site_column(self.names, relation, path, self.column_order, &mut self.out);
        self.out.len(args);
    }

    fn site_label(&mut self, _at: (), _index: usize, path: &[ColumnName], named: Option<&ColumnName>, label: LabelUse, relation: Option<&RelationRef>) {
        match named {
            Some(name) => {
                self.out.tag(Tag::ArgNamedLabel);
                site_column(self.names, relation, &column_path(path, name), self.column_order, &mut self.out);
            }
            None => self.out.tag(Tag::ArgLabel),
        }
        let mut out = std::mem::take(&mut self.out);
        label_use(self, &mut out, label);
        self.out = out;
    }

    fn site_field(&mut self) {
        self.out.tag(Tag::ArgField);
    }

    fn operand(&mut self, _at: (), index: usize, label: Option<ConstraintLabel>) {
        let mut out = std::mem::take(&mut self.out);
        match (index, label) {
            (0, Some(label)) => constraint_label(self, &mut out, label),
            (_, Some(label)) => {
                out.tag(Tag::ArgLabel);
                constraint_label(self, &mut out, label);
            }
            (_, None) => out.tag(Tag::Zero),
        }
        self.out = out;
    }

    fn constraint(&mut self,at:(),constraint:&Constraint) {
        let (_,mut operands,symmetric)=normalized_constraint(constraint);
        if symmetric {operands.sort_by_key(|v|v.map(|l|self.position(l.label)));}
        for(i,label)in operands.into_iter().enumerate(){self.operand(at,i,label);}
    }

    /// Writes the distinct marks sorted by their bytes, each as its labels
    /// sorted by their bytes.
    fn marks(&mut self, _at: (), ones: &'a [OneMark]) {
        let mut marks: Vec<Vec<u8>> = Vec::new();
        for one in super::walk::distinct_marks(ones) {
            let mut labels: Vec<Vec<u8>> = one.key.iter().map(|label| {
                let mut out = CanonicalWriter::default();
                self.label(&mut out, *label);
                out.bytes
            }).collect();
            labels.sort();
            labels.dedup();
            let mut out = CanonicalWriter::default();
            out.len(labels.len());
            for bytes in &labels {
                out.nested(bytes);
            }
            marks.push(out.bytes);
        }
        marks.sort();
        self.out.len(marks.len());
        for bytes in &marks {
            self.out.nested(bytes);
        }
    }

    fn columns(&mut self, _at: (), columns: &'a [RelationColumn], relation: Option<&RelationRef>, ordered: bool) {
        let names = self.names;
        let mut out = std::mem::take(&mut self.out);
        Context::columns(self, &mut out, columns, relation.is_none() && ordered,|out, name| relation_column(names, relation, name, out));
        self.out = out;
    }

    fn choose_from_inside_for(&mut self, choose: &'a Choose) {
        self.out.flag(choose.from_inside_for);
    }

    fn rule_text(&mut self, rule: &'a DemoRule) {
        self.out.option(rule.text.as_ref(), |out, text| out.text(&text.0));
    }

    fn own_scope(&mut self, form: &'a Form) {
        let mut out = std::mem::take(&mut self.out);
        form_root(self, &mut out, form);
        self.out = out;
    }
}

/// Writes the column path `path` of a site on `relation` through `names`,
/// in the order `order` of its columns, or as given at an instance input's
/// head, where `relation` is `None`.
pub(super) fn site_column(names: &dyn NameWriter, relation: Option<&RelationRef>, path: &[ColumnName], order: usize, out: &mut CanonicalWriter) {
    match relation {
        Some(relation) => names.write_column_in(relation, path, order, out),
        None => out.column_path(path),
    }
}

/// The fields of the head sites of an instance, by the port column whose
/// record has them, in order of first use.
#[derive(Default)]
pub(super) struct HeadFields(Vec<(ColumnName, Vec<HeadKey>)>);

/// What tells a field of a head site apart from the others on its port.
#[derive(Clone, PartialEq)]
pub(super) enum HeadKey {
    /// A field of a record, by its name.
    Name(ColumnName),
    /// The label of a head site of one label, which projects that label
    /// onto a column of no record, or of a record of one field. Each input
    /// is a body of its own, whose labels are its own, so a head site of one
    /// label is a field of its own unless it projects a label that another
    /// head site projects, a key's label. The name of the label is no part
    /// of the form: a text writes it and a decode gives the label's slot.
    Label(LabelId),
}

/// The slot name of `key`, a field of the record at `port`, a column of a
/// head site: its order of first use in `fields`. The names of the fields
/// come from the labels of the record's first head, which a text keeps and a
/// decode gives as slots.
pub(super) fn head_field(fields: &mut HeadFields, port: &ColumnName, key: HeadKey) -> ColumnName {
    let at = fields.0.iter().position(|(other, _)| other == port).unwrap_or_else(|| {
        fields.0.push((port.clone(), Vec::new()));
        fields.0.len() - 1
    });
    let keys = &mut fields.0[at].1;
    let index = keys.iter().position(|field| *field == key).unwrap_or_else(|| {
        keys.push(key);
        keys.len() - 1
    });
    ColumnName::Slot(index as u32)
}

/// Writes `name`, a column of `relation`, through `names`. A key body's
/// column, where `relation` is `None`, stands by its position, and its name,
/// written or a slot, is not part of the form.
pub(super) fn relation_column(names: &dyn NameWriter, relation: Option<&RelationRef>, name: &ColumnName, out: &mut CanonicalWriter) {
    if let Some(relation) = relation {
        names.write_column(relation, std::slice::from_ref(name), out);
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
