//! The static types of columns and labels, and their lattice: `C4` under
//! `D4`, `Dir` and `DiagDir` under `Dir8`, `Axis` and `DiagAxis` under
//! `Axis4`, and `Position` and `Offset` as `Box`. A Pose type is below and
//! above no other type.
//!
//! The checker stage writes the bodies.

#![allow(unused_variables, dead_code)]

/// One `RIGID_DET` assembly of a case program, which has its own Pose type:
/// its form, by the form's name and canonical form, and, for a keyed form,
/// its key row, by the labels that a read gives at the key's columns. Two
/// ids are equal where their names, canonical forms and key rows are, so two
/// forms whose hashes collide take two types.
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
        todo!()
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

/// The type that `body` gives `label`, `None` where it gives none, or the
/// fault of that type.
///
/// The type is the meet, as [`ValueType::meet`] gives it, of the types of
/// every site of the label, at any depth, and a join, as [`ValueType::join`]
/// gives it, comes only between alternatives. A constraint over two labels,
/// at any depth, gives each the sites of the other, and `0` gives no type.
/// A negated atom's sites count as a positive atom's, and a `NOT` of a form
/// gives what that form gives. An `OR` gives the join of the types its
/// branches give, an `IF` the meet of its test's type with the join of its
/// then and else lists' types, and an `ALL` the meet of its domain's and its
/// body's types. A branch that gives the label no type gives the `OR` or the
/// `IF`'s join none. A site is one label at an atom's column, and has the
/// type that `site_type` gives that atom and column.
pub fn label_type(
    body: &crate::program::Body,
    label: crate::program::LabelId,
    site_type: &dyn Fn(&crate::program::Atom, &crate::program::ColumnName) -> Option<ValueType>,
) -> Result<Option<ValueType>, LabelFault> {
    LabelWalk { class: equal_labels(body, label), site_type }.body_type(body)
}

/// The walk of [`label_type`] over the labels of `class`.
struct LabelWalk<'a> {
    class: Vec<crate::program::LabelId>,
    site_type: &'a dyn Fn(&crate::program::Atom, &crate::program::ColumnName) -> Option<ValueType>,
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
                for site in atom.sites.iter().filter(|site| site_label(site).is_some_and(|l| self.class.contains(&l))) {
                    ty = meet(ty, (self.site_type)(atom, &site.column))?;
                }
                Ok(ty)
            }
            Conjunct::Not(Negated::Form(form)) => self.conjunct_type(form),
            Conjunct::Or(branches) => join_branches(branches.iter().map(|branch| self.body_type(branch.value()))),
            Conjunct::If { test, then, otherwise } => {
                let branches = [then, otherwise].into_iter().map(|branch| self.body_type(branch.value()));
                meet(self.body_type(test.value())?, join_branches(branches)?)
            }
            Conjunct::All { domain, body } => meet(self.body_type(domain.value())?, self.body_type(body.value())?),
            Conjunct::Constraint(_) => Ok(None),
        }
    }
}

/// The one label that `site` holds, where it holds one label and no field.
fn site_label(site: &crate::program::Site) -> Option<crate::program::LabelId> {
    use crate::program::{LabelUse, SiteArg};
    match &site.value.args[..] {
        [SiteArg::Label(LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label))] => Some(*label),
        _ => None,
    }
}

/// The meet of two types of one label, either of which may be absent.
fn meet(a: Option<ValueType>, b: Option<ValueType>) -> Result<Option<ValueType>, LabelFault> {
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
    use crate::program::{Conjunct, Constraint, Operand};
    let mut pairs = Vec::new();
    each_conjunct(body, &mut |conjunct| {
        if let Conjunct::Constraint(Constraint { first, second: Operand::Label(second), .. }) = conjunct {
            pairs.push((first.label, second.label));
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

/// The types the type check infers for the labels of one form, which the
/// check cache keeps beside the form's type check, so that the cases that
/// share a form share its types. In the check cache a label is its canonical
/// position, as `LabelId(position)`, and a key row's labels are the same.
/// [`ProgramTypes`] holds the form's own labels.
#[derive(Clone, Debug, Default)]
pub struct FormTypes {
    labels: crate::hash::StableHashMap<crate::program::LabelId, ValueType>,
}

impl FormTypes {
    /// The type of `label`, or `None` where the form has no such label.
    pub fn label(&self, label: crate::program::LabelId) -> Option<&ValueType> {
        todo!()
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
}

impl ProgramTypes {
    /// The types of the labels of the scope at `form`, a form of the program
    /// or a `DEMO_RULE`, as [`crate::program::LabelId`] gives scopes.
    pub fn form(&self, form: &crate::program::path::NodePath) -> Option<&FormTypes> {
        todo!()
    }

    /// The type of each column of `relation`, one per column, a record's
    /// fields each a column of its own.
    pub fn columns(&self, relation: &GraphRelation) -> Option<&[ValueType]> {
        todo!()
    }
}
