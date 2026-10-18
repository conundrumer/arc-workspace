//! The static types of columns and labels, and their lattice: `C4` under
//! `D4`, `Dir` and `DiagDir` under `Dir8`, `Axis` and `DiagAxis` under
//! `Axis4`, and `Position` and `Offset` as `Box`. A Pose type is below and
//! above no other type.

/// One `RIGID_DET` assembly of a case program, which has its own Pose type:
/// its form, by the form's name and canonical form, and, for a keyed form,
/// its key row, by the labels that a read gives at the key's columns. It
/// compares as a key of canonical parts does ([`crate::program`]).
///
/// The form's name and canonical form stay the same in every case that
/// holds the form, so the cases that share a form that reads a pose share
/// its types and its check, whatever alts come before it, and two forms of
/// one name with different parts, in two programs of one task session, take
/// two types. Each key row is an assembly of its own, aligned and posed on its
/// own (`docs/arclog/rigid.md#form`), so two pose reads meet only where they
/// read the same key labels. The key row is named as [`KeyRow`] gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct AssemblyId {
    pub name: crate::program::RigidDetName,
    pub canonical_form: crate::program::canonical::CanonicalForm,
    /// The key row, or [`KeyRow::Unkeyed`] for a form with no key.
    pub key: KeyRow,
}

/// How a Pose type names its key row: in a scope, by the labels a read
/// gives at the key's columns; at a column of a derived relation or an
/// instance's input, by the positions of the relation's columns that hold
/// the key. A read of the relation maps the positions to the labels at
/// them, so a Pose type passes through a relation
/// (`docs/arclog/rigid.md#the-pose`).
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum KeyRow {
    Unkeyed,
    /// The labels at the key's columns, in the key's order, local to the
    /// scope of the reads, as [`crate::program::LabelId`] gives.
    Labels(Box<[crate::program::LabelId]>),
    /// The positions of the relation's columns that hold the key, in the
    /// key's order.
    Columns(Box<[u16]>),
}

/// The type of a column or a label, which the type check infers for each
/// label over the lattice of the types.
///
/// `Position` and `Offset` are the type `Box`, so neither has a variant of
/// its own.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub enum ValueType {
    Number,
    Color,
    Example,
    Unit,
    Box,
    Ident,
    C4,
    D4,
    Dir,
    DiagDir,
    Dir8,
    Axis,
    DiagAxis,
    Axis4,
    Sym,
    Sense,
    /// The Pose type of one `RIGID_DET` assembly.
    Pose(AssemblyId),
    /// A record bound to a type parameter: by a projection of several sites,
    /// one field per site, or, for `Key`, by the key clause, one field per
    /// `^` label, as `docs/arclog/arclog.md#instance` gives. The engine has no
    /// record values, so each field takes a column of its own.
    Record(Box<[(FieldName, ValueType)]>),
}

/// The name of a record's field, PascalCase, as
/// `docs/arclog/arclog.md#sites` gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct FieldName(pub Box<str>);

impl FieldName {
    /// The field that a site's head or an elided site's label names, or
    /// `None` for a column that holds a slot in place of a written name.
    pub fn of(column: &crate::program::ColumnName) -> Option<FieldName> {
        match column {
            crate::program::ColumnName::Written(name) => Some(FieldName(name.clone())),
            crate::program::ColumnName::Slot(_) => None,
        }
    }
}

/// The result of the meet of two types.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum Meet {
    /// The greatest type below both.
    Type(ValueType),
    /// No type is below both, so a label of both types holds no value.
    Empty,
}

impl ValueType {
    /// The meet of two types: the type of a label with both types' sites.
    pub fn meet(&self, other: &ValueType) -> Meet {
        if self.is_below(other) {
            return Meet::Type(self.clone());
        }
        if other.is_below(self) {
            return Meet::Type(other.clone());
        }
        Meet::Empty
    }

    /// The join of two types: the type of a label that an `OR` or an `IF`
    /// exports from branches of these types, or `None` where no type is above
    /// both.
    pub fn join(&self, other: &ValueType) -> Option<ValueType> {
        if self.is_below(other) {
            return Some(other.clone());
        }
        if other.is_below(self) {
            return Some(self.clone());
        }
        match (self.parent(), other.parent()) {
            (Some(a), Some(b)) if a == b => Some(a),
            _ => None,
        }
    }

    /// Whether the type equals `other` or stands under it.
    fn is_below(&self, other: &ValueType) -> bool {
        self == other || self.parent().as_ref() == Some(other)
    }

    /// The type the type stands directly under, where it stands under one.
    fn parent(&self) -> Option<ValueType> {
        match self {
            ValueType::C4 => Some(ValueType::D4),
            ValueType::Dir | ValueType::DiagDir => Some(ValueType::Dir8),
            ValueType::Axis | ValueType::DiagAxis => Some(ValueType::Axis4),
            _ => None,
        }
    }

    /// Whether `<`, `<=`, `>` and `>=` may compare values of the type: true
    /// for `number` alone.
    pub fn admits_order(&self) -> bool {
        *self == ValueType::Number
    }
}

/// A fault of the type of one label in a body.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum LabelFault {
    /// Two sites give the label types with an empty meet.
    EmptyMeet(ValueType, ValueType),
    /// Two branches give the label types with no join.
    NoJoin(ValueType, ValueType),
}

/// The text of `fault` of a label, for a diagnostic that names the label
/// before it.
pub(crate) fn label_fault_message(fault: LabelFault) -> String {
    match fault {
        LabelFault::EmptyMeet(a, b) => format!("stands at sites of the types {a:?} and {b:?}, whose meet is empty"),
        LabelFault::NoJoin(a, b) => format!("takes the types {a:?} and {b:?} from two branches, which have no join"),
    }
}

/// The type that `body` gives `label`, `None` where it gives none, or the
/// fault of that type. `body` is the list of the label's scope, as the doc
/// of [`crate::check::CheckId::Types`] gives it.
///
/// The type is the meet, as [`ValueType::meet`] gives it, of the types of
/// every site of the label, at any depth, and a join, as [`ValueType::join`]
/// gives it, comes only between alternatives. A constraint over two labels,
/// at any depth, gives each the sites of the other, and `0` gives no type.
/// A negated atom's sites count as a positive atom's, and a `NOT` of a form
/// gives what that form gives. An `OR` gives the join of the types its
/// branches give, and an `ALL` the meet of its domain's and its body's
/// types. An `IF` gives the meet of its test's type with the join of its
/// then and else lists' types, or, where the label is fresh in the test,
/// the meet of its test's and its then's types, since such a label is
/// local to the test and the then (`docs/arclog/arclog.md#conditional`). A
/// branch that gives the label no type gives the `OR` or the `IF`'s join
/// none.
///
/// A site is one label at an atom's site, at any depth of the site: a bare
/// label at the site's column, a bare label at a column of a type
/// parameter, which names its field, or a label at a site on a record's
/// field, `*A1` of `(:key (:C C) (:A *A1))`. The site has the type that
/// `site_type` gives the atom and the site's column path: the site's column,
/// then the field of each nested site, then, for a bare label at a column
/// of a type parameter, the name it holds.
pub fn label_type(
    body: &crate::program::Body,
    label: crate::program::LabelId,
    site_type: &dyn Fn(&crate::program::Atom, &[crate::program::ColumnName]) -> Option<ValueType>,
) -> Result<Option<ValueType>, LabelFault> {
    LabelWalk { label, class: equal_labels(body, label), site_type }.body_type(body)
}

/// The list of the scope of `label`, a label of `list` that is no head
/// label: the innermost list that holds each of its sites, or, where that
/// list is an `IF`'s test or a list of an `ALL`, or where its sites stand in
/// both the test and the then of an `IF`, the list that holds that form,
/// since a label fresh there is local to the form.
pub(crate) fn scope_list(list: &crate::program::Body, label: crate::program::LabelId) -> &crate::program::Body {
    let holds = |conjunct: &crate::program::Conjunct| {
        let mut labels = crate::hash::StableHashSet::default();
        crate::grounding::conjunct_labels(conjunct, &mut labels);
        labels.contains(&label)
    };
    let mut holders = list.conjuncts.iter().filter(|conjunct| holds(conjunct));
    let (Some(conjunct), None) = (holders.next(), holders.next()) else { return list };
    let mut own = Vec::new();
    crate::grounding::own_labels(conjunct, &mut own);
    if own.contains(&label) {
        return list;
    }
    use crate::program::{Conjunct, Negated};
    let mut form = conjunct;
    while let Conjunct::Not(Negated::Form(inner)) = form {
        form = inner;
    }
    // Each part of the form, with whether a label that stands only in it
    // takes it as its scope.
    let parts: Vec<(&crate::program::Body, bool)> = match form {
        Conjunct::Or(branches) => branches.iter().map(|branch| (branch.value(), true)).collect(),
        Conjunct::If { test, then, otherwise } => vec![(test.value(), false), (then.value(), true), (otherwise.value(), true)],
        Conjunct::All { domain, body } => vec![(domain.value(), false), (body.value(), false)],
        Conjunct::Atom(_) | Conjunct::Not(_) | Conjunct::Constraint(_) => Vec::new(),
    };
    let mut holding = parts.into_iter().filter(|(part, _)| crate::grounding::body_labels(part).contains(&label));
    match (holding.next(), holding.next()) {
        (Some((part, true)), None) => scope_list(part, label),
        _ => list,
    }
}

/// The walk of [`label_type`] over the labels of `class`, the class of
/// `label`, the label asked.
struct LabelWalk<'a> {
    label: crate::program::LabelId,
    class: Vec<crate::program::LabelId>,
    site_type: &'a dyn Fn(&crate::program::Atom, &[crate::program::ColumnName]) -> Option<ValueType>,
}

impl LabelWalk<'_> {
    fn body_type(&self, body: &crate::program::Body) -> Result<Option<ValueType>, LabelFault> {
        let mut ty = None;
        for conjunct in body.conjuncts.iter() {
            ty = meet(ty, self.conjunct_type(conjunct)?)?;
        }
        Ok(ty)
    }

    fn conjunct_type(&self, conjunct: &crate::program::Conjunct) -> Result<Option<ValueType>, LabelFault> {
        use crate::program::{Conjunct, Negated};
        match conjunct {
            Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => {
                let atom = atom.value();
                let mut ty = None;
                for site in atom.sites.iter() {
                    let mut path = Vec::new();
                    let mut fault = None;
                    each_site_label(site, &mut path, &mut |use_, path| {
                        if fault.is_some() || !use_label(use_).is_some_and(|l| self.class.contains(&l)) {
                            return;
                        }
                        match meet(ty.take(), (self.site_type)(atom, path)) {
                            Ok(met) => ty = met,
                            Err(err) => fault = Some(err),
                        }
                    });
                    if let Some(err) = fault {
                        return Err(err);
                    }
                }
                Ok(ty)
            }
            Conjunct::Not(Negated::Form(form)) => self.conjunct_type(form),
            Conjunct::Or(branches) => join_branches(branches.iter().map(|branch| self.body_type(branch.value()))),
            Conjunct::If { test, then, otherwise } => {
                let test_type = self.body_type(test.value())?;
                if self.fresh_in(test.value()) {
                    return meet(test_type, self.body_type(then.value())?);
                }
                let branches = [then, otherwise].into_iter().map(|branch| self.body_type(branch.value()));
                meet(test_type, join_branches(branches)?)
            }
            Conjunct::All { domain, body } => meet(self.body_type(domain.value())?, self.body_type(body.value())?),
            Conjunct::Constraint(_) => Ok(None),
        }
    }

    /// Whether the label asked is fresh at a site or a constraint of
    /// `body`, at any depth.
    fn fresh_in(&self, body: &crate::program::Body) -> bool {
        use crate::program::{Conjunct, LabelUse, Negated, Operand};
        let mut fresh = false;
        each_conjunct(body, &mut |conjunct| match conjunct {
            Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => {
                for site in atom.value().sites.iter() {
                    each_site_label(site, &mut Vec::new(), &mut |use_, _| {
                        fresh |= use_ == LabelUse::Fresh(self.label);
                    });
                }
            }
            Conjunct::Constraint(c) => {
                let second = match c.second {
                    Operand::Label(label) => Some(label),
                    Operand::Zero => None,
                };
                for label in std::iter::once(c.first).chain(second) {
                    fresh |= label.fresh && label.label == self.label;
                }
            }
            _ => {}
        });
        fresh
    }
}

/// Visits each label use at `site`, at any depth of the site, with its
/// column path, as [`label_type`] gives it, after `path`.
pub fn each_site_label(
    site: &crate::program::Site,
    path: &mut Vec<crate::program::ColumnName>,
    visit: &mut dyn FnMut(crate::program::LabelUse, &[crate::program::ColumnName]),
) {
    use crate::program::SiteArg;
    path.push(site.column.clone());
    for arg in site.value.args.iter() {
        match arg {
            SiteArg::Label(use_) => visit(*use_, path),
            SiteArg::NamedLabel { name, label } => {
                path.push(name.clone());
                visit(*label, path);
                path.pop();
            }
            SiteArg::Field(field) => each_site_label(field, path, visit),
        }
    }
    path.pop();
}

/// The label of a label use, where it has one.
pub fn use_label(use_: crate::program::LabelUse) -> Option<crate::program::LabelId> {
    use crate::program::LabelUse;
    match use_ {
        LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label) => Some(label),
        LabelUse::Zero => None,
    }
}

/// The meet of two types of one label, either of which may be absent.
pub(crate) fn meet(a: Option<ValueType>, b: Option<ValueType>) -> Result<Option<ValueType>, LabelFault> {
    match (a, b) {
        (Some(a), Some(b)) => match a.meet(&b) {
            Meet::Type(ty) => Ok(Some(ty)),
            Meet::Empty => Err(LabelFault::EmptyMeet(a, b)),
        },
        (a, b) => Ok(a.or(b)),
    }
}

/// The join of the types that branches give one label, or `None` where a
/// branch gives it none.
fn join_branches(
    branches: impl Iterator<Item = Result<Option<ValueType>, LabelFault>>,
) -> Result<Option<ValueType>, LabelFault> {
    let mut joined: Option<ValueType> = None;
    for branch in branches {
        let Some(ty) = branch? else { return Ok(None) };
        joined = Some(match joined {
            None => ty,
            Some(prev) => prev.join(&ty).ok_or_else(|| LabelFault::NoJoin(prev.clone(), ty.clone()))?,
        });
    }
    Ok(joined)
}

/// `label` and each label that a constraint of `body`, at any depth, makes
/// equal to it, directly or through other labels.
fn equal_labels(body: &crate::program::Body, label: crate::program::LabelId) -> Vec<crate::program::LabelId> {
    use crate::program::{constraint_second, Conjunct};
    let mut pairs = Vec::new();
    each_conjunct(body, &mut |conjunct| {
        if let Conjunct::Constraint(k) = conjunct {
            if let Some(second) = constraint_second(k) {
                pairs.push((k.first.label, second.label));
            }
        }
    });
    let mut class = vec![label];
    let mut grown = true;
    while grown {
        grown = false;
        for &(a, b) in &pairs {
            for (x, y) in [(a, b), (b, a)] {
                if class.contains(&x) && !class.contains(&y) {
                    class.push(y);
                    grown = true;
                }
            }
        }
    }
    class
}

/// Visits each conjunct of `body` at any depth, a conjunct inside a `NOT`
/// included.
pub fn each_conjunct(body: &crate::program::Body, visit: &mut dyn FnMut(&crate::program::Conjunct)) {
    use crate::program::{Conjunct, Negated};
    fn conjunct(c: &Conjunct, visit: &mut dyn FnMut(&Conjunct)) {
        visit(c);
        match c {
            Conjunct::Atom(_) | Conjunct::Not(Negated::Atom(_)) | Conjunct::Constraint(_) => {}
            Conjunct::Not(Negated::Form(form)) => conjunct(form, visit),
            Conjunct::Or(branches) => branches.iter().for_each(|b| each_conjunct(b.value(), visit)),
            Conjunct::If { test, then, otherwise } => [test, then, otherwise].into_iter().for_each(|b| each_conjunct(b.value(), visit)),
            Conjunct::All { domain, body } => [domain, body].into_iter().for_each(|b| each_conjunct(b.value(), visit)),
        }
    }
    for c in body.conjuncts.iter() {
        conjunct(c, visit);
    }
}

/// The types the type check infers for the labels of one label scope of a
/// form, which the check cache keeps beside the form's type check, so that
/// the cases that share a form share its types. In the check cache a label
/// is its canonical position in its scope, as `LabelId(position)`, and a key
/// row's labels are the same. [`ProgramTypes`] holds the scope's own labels.
#[derive(Clone, Debug, Default)]
pub struct FormTypes {
    labels: crate::hash::StableHashMap<crate::program::LabelId, ValueType>,
}

impl FormTypes {
    /// The type of `label`, or `None` where the form has no such label.
    pub fn label(&self, label: crate::program::LabelId) -> Option<&ValueType> {
        self.labels.get(&label)
    }

    /// Each label with its type.
    pub fn labels(&self) -> impl Iterator<Item = (crate::program::LabelId, &ValueType)> + '_ {
        self.labels.iter().map(|(label, ty)| (*label, ty))
    }
}

impl FromIterator<(crate::program::LabelId, ValueType)> for FormTypes {
    fn from_iter<I: IntoIterator<Item = (crate::program::LabelId, ValueType)>>(labels: I) -> Self {
        FormTypes { labels: labels.into_iter().collect() }
    }
}

/// A relation of a case program: the node of the dependency graph that holds
/// it, and, for an output of a node with several, such as an instance, a
/// `RIGID_DET` form or a recursive instance, the output's path. Two
/// relations of one name in two name scopes are two nodes.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct GraphRelation {
    pub node: crate::resolver::GraphNodeIndex,
    pub output: Option<std::sync::Arc<[crate::program::OutputStep]>>,
}

/// The types the type check infers for a checked case program: the type of
/// each label of each clause, and the type of each column of each relation.
/// The types are static: a row has no type tag.
///
/// `0` takes the type of the label or the column it stands at, so it has no
/// entry of its own.
#[derive(Clone, Debug, Default)]
pub struct ProgramTypes {
    forms: crate::hash::StableHashMap<crate::program::path::NodePath, std::sync::Arc<FormTypes>>,
    columns: crate::hash::StableHashMap<GraphRelation, Box<[ValueType]>>,
    /// The nodes whose relations have an Example column.
    example_nodes: crate::hash::StableHashSet<crate::resolver::GraphNodeIndex>,
}

impl ProgramTypes {
    /// The types of the labels of the label scope whose form stands at
    /// `form`, a path of the program, as [`crate::program::LabelId`] gives
    /// scopes: a top-level form's own scope, each form of a claim or an
    /// `ALT`, a `DEMONSTRATED` form's key clause and inputs, and each
    /// `DEMO_RULE` form, at any depth.
    pub fn form(&self, form: &crate::program::path::NodePath) -> Option<&FormTypes> {
        self.forms.get(form).map(|types| &**types)
    }

    /// Sets the types of the labels of the scope at `form`.
    pub(crate) fn insert_form(&mut self, form: crate::program::path::NodePath, types: std::sync::Arc<FormTypes>) {
        self.forms.insert(form, types);
    }

    /// The type of each column of `relation`, one per column, a record's
    /// fields each a column of its own.
    pub fn columns(&self, relation: &GraphRelation) -> Option<&[ValueType]> {
        self.columns.get(relation).map(|columns| &columns[..])
    }

    /// Whether `relation` has an Example column, as the checker decides it
    /// by [`crate::check::reads::example_relations`].
    pub fn has_example_column(&self, relation: &GraphRelation) -> bool {
        self.example_nodes.contains(&relation.node)
    }

    /// Sets the nodes whose relations have an Example column.
    pub(crate) fn set_example_nodes(&mut self, nodes: crate::hash::StableHashSet<crate::resolver::GraphNodeIndex>) {
        self.example_nodes = nodes;
    }
}
