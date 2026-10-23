//! The static types of columns and labels, and their lattice: `C4` under
//! `D4`, `Dir` and `DiagDir` under `Dir8`, `Axis` and `DiagAxis` under
//! `Axis4`, and `Position` and `Offset` as `Box`. A Pose type is below and
//! above no other type. The types of a checked program, which the check
//! hands on, are in the module `program_types`.

mod program_types;

pub use program_types::{FormRelation, FormTypes, GraphRelation, ProgramTypes};

/// One `RIGID_DET` assembly of a case program, which has its own Pose type:
/// its form, by the form's name and canonical form, and, for a keyed form,
/// its key row, by the labels that a read gives at the key's columns. It
/// compares as a key of canonical parts does ([`crate::program`]).
///
/// The form's name and canonical form stay the same in every case that holds
/// the form, so the cases that share a form that reads a pose share its types
/// and its check, whatever alts come before it, and two forms of one name
/// with different parts, in two programs of one task session, take two types.
/// Two pose reads meet only where they read the same key labels
/// (`docs/arclog/rigid.md#form`). The key row is named as [`KeyRow`] gives.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct AssemblyId {
    pub name: crate::program::RigidDetName,
    pub canonical_form: crate::program::canonical::CanonicalForm,
    /// The key row, or [`KeyRow::Unkeyed`] for a form with no key.
    pub key: KeyRow,
}

/// How a Pose type names its key row: in a scope, by the labels a read gives
/// at the key's columns; at a column of a derived relation or an instance's
/// input, by the positions of the relation's columns that hold the key. A
/// read of the relation maps the positions to the labels at them
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
    /// A record bound to a type parameter (`docs/arclog/arclog.md#instance`),
    /// each field by the column name of its site or of its key column: the
    /// name written, or, in a decoded program, the slot. The engine has no
    /// record values, so each field takes a column of its own.
    Record(Box<[(crate::program::ColumnName, ValueType)]>),
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

    /// The orientation types whose constants are the values of the type:
    /// its own, or the types a union such as `Dir8` unites, and `D4` for
    /// `C4`, whose constants are D4's. `None` for every other type, a Pose
    /// type among them.
    pub fn orientation_types(&self) -> Option<&'static [crate::terms::OrientationType]> {
        use crate::terms::OrientationType;
        Some(match self {
            ValueType::C4 | ValueType::D4 => &[OrientationType::D4],
            ValueType::Dir => &[OrientationType::Dir],
            ValueType::DiagDir => &[OrientationType::DiagDir],
            ValueType::Dir8 => &[OrientationType::Dir, OrientationType::DiagDir],
            ValueType::Axis => &[OrientationType::Axis],
            ValueType::DiagAxis => &[OrientationType::DiagAxis],
            ValueType::Axis4 => &[OrientationType::Axis, OrientationType::DiagAxis],
            ValueType::Sym => &[OrientationType::Sym],
            ValueType::Sense => &[OrientationType::Sense],
            ValueType::Number
            | ValueType::Color
            | ValueType::Example
            | ValueType::Unit
            | ValueType::Box
            | ValueType::Ident
            | ValueType::Pose(_)
            | ValueType::Record(_) => return None,
        })
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
/// fault of that type. `body` is the list of the label's scope, as
/// `scope_list` gives it.
///
/// The type is the meet, as [`ValueType::meet`] gives it, of the types of
/// every site of the label, at any depth, and a join, as [`ValueType::join`]
/// gives it, comes only between alternatives. A constraint over two labels
/// gives each the sites of the other in the list that holds the constraint
/// and in the lists nested in it, and, for a constraint in an `IF`'s test or
/// in an `ALL`'s domain, in that form's then or body as well; `0` gives no
/// type. A negated atom's sites count as a positive atom's, and a `NOT` of a
/// form gives what that form gives. An `OR` gives the join of the types its
/// branches give, and an `ALL` the meet of its domain's and its body's types.
/// An `IF` gives the meet of its test's type with the join of its then and
/// else lists' types, or, where the label is fresh in the test, the meet of
/// its test's and its then's types (`docs/arclog/arclog.md#conditional`). A
/// branch of an `OR` that holds no label equal to the label takes no part in
/// the `OR`'s join, and a branch that holds one and gives the label no type
/// gives that join none. A then or an else list that gives the label no
/// type gives the `IF`'s join none. In a list nested in `body`, a label
/// that the list's constraints make equal to the label, and that the
/// constraints of the lists around the list do not, gives the label in the
/// list as well the type that its own sites in the lists around the list
/// give it, outside the conjunct that holds the list.
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
    label_type_keyed(body, label, site_type, None)
}

/// [`label_type`] for a label of an `INIT` form's input, where `key` is the
/// body of the form's key clause. The key clause is a list around the
/// input's body: a label that a constraint makes equal to a label of the
/// key clause takes the type that the key clause's sites give that label
/// (`docs/arclog/arclog.md#instance`).
pub fn label_type_keyed(
    body: &crate::program::Body,
    label: crate::program::LabelId,
    site_type: &dyn Fn(&crate::program::Atom, &[crate::program::ColumnName]) -> Option<ValueType>,
    key: Option<&crate::program::Body>,
) -> Result<Option<ValueType>, LabelFault> {
    LabelWalk { label, site_type, asked: vec![label], key }.body_type(body, &[], None)
}

/// The list of the scope of `label`, a label of `list` that is no head
/// label: the innermost list that holds each of its sites, or, where that
/// list is an `IF`'s test or a list of an `ALL`, or where its sites stand in
/// both the test and the then of an `IF`, the list that holds that form,
/// since a label fresh there is local to the form.
pub(crate) fn scope_list(list: &crate::program::Body, label: crate::program::LabelId) -> &crate::program::Body {
    let holds = |conjunct: &crate::program::Conjunct| {
        let mut labels = crate::hash::StableHashSet::default();
        crate::safety::conjunct_labels(conjunct, &mut labels);
        labels.contains(&label)
    };
    let mut holders = list.conjuncts.iter().filter(|conjunct| holds(conjunct));
    let (Some(conjunct), None) = (holders.next(), holders.next()) else { return list };
    let mut own = Vec::new();
    crate::safety::own_labels(conjunct, &mut own);
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
    let mut holding = parts.into_iter().filter(|(part, _)| crate::safety::body_labels(part).contains(&label));
    match (holding.next(), holding.next()) {
        (Some((part, true)), None) => scope_list(part, label),
        _ => list,
    }
}

/// The walk of [`label_type`] for `label`, the label asked. `asked` holds
/// `label` and each label whose walk holds this one, whose types the walk
/// does not take from the lists around a list.
struct LabelWalk<'a> {
    label: crate::program::LabelId,
    site_type: &'a dyn Fn(&crate::program::Atom, &[crate::program::ColumnName]) -> Option<ValueType>,
    asked: Vec<crate::program::LabelId>,
    /// The body of the key clause of the `INIT` form, a list around every
    /// input's body.
    key: Option<&'a crate::program::Body>,
}

/// A list around the list a walk is in: the list, the pairs of labels that
/// its constraints and those around it make equal there, the index of its
/// conjunct that holds the inner list, and the list around it.
struct Around<'b> {
    list: &'b crate::program::Body,
    pairs: &'b [LabelPair],
    holder: usize,
    outer: Option<&'b Around<'b>>,
}

impl LabelWalk<'_> {
    /// The type of `body`, where `outer` holds the pairs of labels that the
    /// constraints of the lists around `body` make equal there, and
    /// `around` the list around `body`, none for the list of the label's
    /// scope.
    fn body_type(
        &self,
        body: &crate::program::Body,
        outer: &[LabelPair],
        around: Option<&Around<'_>>,
    ) -> Result<Option<ValueType>, LabelFault> {
        let pairs = with_constraints(outer, body);
        let class = equal_labels(&pairs, self.label);
        let mut ty = self.list_type(body, &pairs, &class, around, None)?;
        let before = equal_labels(outer, self.label);
        for &other in class.iter().filter(|label| !before.contains(label) && !self.asked.contains(label)) {
            if let Some(around) = around {
                ty = meet(ty, self.around_type(other, around)?)?;
            }
            ty = meet(ty, self.key_type(other)?)?;
        }
        Ok(ty)
    }

    /// The type that the sites of `other` give it in the key clause.
    fn key_type(&self, other: crate::program::LabelId) -> Result<Option<ValueType>, LabelFault> {
        let Some(key) = self.key else { return Ok(None) };
        let asked = self.asked.iter().copied().chain(std::iter::once(other)).collect();
        let walk = LabelWalk { label: other, site_type: self.site_type, asked, key: None };
        walk.list_type(key, &[], &[other], None, None)
    }

    /// The type that the sites of `other` give it in `around` and the lists
    /// around it, outside the conjunct of each that holds the inner list.
    fn around_type(&self, other: crate::program::LabelId, around: &Around<'_>) -> Result<Option<ValueType>, LabelFault> {
        let asked = self.asked.iter().copied().chain(std::iter::once(other)).collect();
        let walk = LabelWalk { label: other, site_type: self.site_type, asked, key: self.key };
        let mut ty = None;
        let mut frame = Some(around);
        while let Some(list) = frame {
            let class = equal_labels(list.pairs, other);
            ty = meet(ty, walk.list_type(list.list, list.pairs, &class, list.outer, Some(list.holder))?)?;
            frame = list.outer;
        }
        Ok(ty)
    }

    /// The meet of the types of the conjuncts of `list`, other than the one
    /// at `skip`, where `pairs` and `class` are as [`LabelWalk::conjunct_type`]
    /// takes them, and `outer` is the list around `list`.
    fn list_type(
        &self,
        list: &crate::program::Body,
        pairs: &[LabelPair],
        class: &[crate::program::LabelId],
        outer: Option<&Around<'_>>,
        skip: Option<usize>,
    ) -> Result<Option<ValueType>, LabelFault> {
        let mut ty = None;
        for (holder, conjunct) in list.conjuncts.iter().enumerate().filter(|(index, _)| Some(*index) != skip) {
            let here = Around { list, pairs, holder, outer };
            ty = meet(ty, self.conjunct_type(conjunct, pairs, class, &here)?)?;
        }
        Ok(ty)
    }

    /// The type of `conjunct`, a conjunct of a list whose constraints and
    /// those around it give `pairs`, and the class of the label asked there.
    /// `here` is that list, with `conjunct` as the holder of the lists
    /// nested in it.
    fn conjunct_type(
        &self,
        conjunct: &crate::program::Conjunct,
        pairs: &[LabelPair],
        class: &[crate::program::LabelId],
        here: &Around<'_>,
    ) -> Result<Option<ValueType>, LabelFault> {
        use crate::program::{Conjunct, Negated};
        match conjunct {
            Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => {
                let atom = atom.value();
                let mut ty = None;
                for site in atom.sites.iter() {
                    let mut path = Vec::new();
                    let mut fault = None;
                    each_site_label(site, &mut path, &mut |use_, path| {
                        if fault.is_some() || !use_label(use_).is_some_and(|l| class.contains(&l)) {
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
            Conjunct::Not(Negated::Form(form)) => self.conjunct_type(form, pairs, class, here),
            Conjunct::Or(branches) => {
                let holds = |branch: &crate::program::Body| {
                    let labels = crate::safety::body_labels(branch);
                    class.iter().any(|label| labels.contains(label))
                };
                let holding = branches.iter().filter(|branch| holds(branch.value()) && !makes_only_by_zero(branch.value(), class));
                join_branches(holding.map(|branch| self.body_type(branch.value(), pairs, Some(here))))
            }
            Conjunct::If { test, then, otherwise } => {
                let test_type = self.body_type(test.value(), pairs, Some(here))?;
                let then_type = self.body_type(then.value(), &with_constraints(pairs, test.value()), Some(here))?;
                if self.fresh_in(test.value()) {
                    return meet(test_type, then_type);
                }
                let otherwise_type = (!makes_only_by_zero(otherwise.value(), class)).then(|| self.body_type(otherwise.value(), pairs, Some(here)));
                meet(test_type, join_branches([Ok(then_type)].into_iter().chain(otherwise_type))?)
            }
            Conjunct::All { domain, body } => {
                let domain_type = self.body_type(domain.value(), pairs, Some(here))?;
                meet(domain_type, self.body_type(body.value(), &with_constraints(pairs, domain.value()), Some(here))?)
            }
            Conjunct::Constraint(_) => Ok(None),
        }
    }

    /// Whether the label asked is fresh at a site or a constraint of
    /// `body`, at any depth.
    fn fresh_in(&self, body: &crate::program::Body) -> bool {
        use crate::program::{Conjunct, LabelUse, Operand};
        let mut fresh = false;
        each_conjunct(body, &mut |conjunct| match conjunct {
            Conjunct::Constraint(c) => {
                let second = match c.second {
                    Operand::Label(label) => Some(label),
                    Operand::Zero => None,
                };
                for label in std::iter::once(c.first).chain(second) {
                    fresh |= label.fresh && label.label == self.label;
                }
            }
            _ => {
                if let Some(atom) = conjunct.atom() {
                    for site in atom.value().sites.iter() {
                        each_site_label(site, &mut Vec::new(), &mut |use_, _| {
                            fresh |= use_ == LabelUse::Fresh(self.label);
                        });
                    }
                }
            }
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

/// Whether `branch` makes the label of `class` only by a `(= X 0)`, with
/// the label at no site of an atom in `branch`: such a branch adds no
/// type to the label, as a clause whose head label only `(= *X 0)` gives a
/// type adds none.
fn makes_only_by_zero(branch: &crate::program::Body, class: &[crate::program::LabelId]) -> bool {
    let ZeroMade { zeroed, at_sites } = ZeroMade::of(branch);
    zeroed.iter().any(|(label, _)| class.contains(label)) && !at_sites.iter().any(|label| class.contains(label))
}

/// The labels that a body makes by `(= X 0)`, each with whether the
/// constraint makes it fresh, and the labels that stand at a site of an
/// atom of the body, at any depth.
pub(crate) struct ZeroMade {
    pub zeroed: Vec<(crate::program::LabelId, bool)>,
    pub at_sites: Vec<crate::program::LabelId>,
}

impl ZeroMade {
    pub(crate) fn of(body: &crate::program::Body) -> Self {
        use crate::program::{Conjunct, Constraint, ConstraintOp, Operand};
        let mut made = ZeroMade { zeroed: Vec::new(), at_sites: Vec::new() };
        each_conjunct(body, &mut |conjunct| match conjunct {
            Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second: Operand::Zero }) => made.zeroed.push((first.label, first.fresh)),
            _ => {
                if let Some(atom) = conjunct.atom() {
                    for site in atom.value().sites.iter() {
                        each_site_label(site, &mut Vec::new(), &mut |use_, _| made.at_sites.extend(use_label(use_)));
                    }
                }
            }
        });
        made
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

/// Two labels that a constraint makes equal.
type LabelPair = (crate::program::LabelId, crate::program::LabelId);

/// `outer` and the pairs of labels of each constraint of `list` itself, a
/// constraint under a `NOT` included, and no constraint of a list nested in
/// `list`.
fn with_constraints(outer: &[LabelPair], list: &crate::program::Body) -> Vec<LabelPair> {
    use crate::program::{constraint_second, Conjunct, Negated};
    let mut pairs = outer.to_vec();
    for conjunct in list.conjuncts.iter() {
        let mut conjunct = conjunct;
        while let Conjunct::Not(Negated::Form(inner)) = conjunct {
            conjunct = inner;
        }
        if let Conjunct::Constraint(k) = conjunct {
            if let Some(second) = constraint_second(k) {
                pairs.push((k.first.label, second.label));
            }
        }
    }
    pairs
}

/// `label` and each label that `pairs` make equal to it, directly or
/// through other labels.
fn equal_labels(pairs: &[LabelPair], label: crate::program::LabelId) -> Vec<crate::program::LabelId> {
    let mut class = vec![label];
    let mut grown = true;
    while grown {
        grown = false;
        for &(a, b) in pairs {
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

/// Visits each atom of `body` at any depth, a negated atom included.
pub fn each_atom(body: &crate::program::Body, visit: &mut dyn FnMut(&crate::program::Atom)) {
    each_conjunct(body, &mut |conjunct| {
        if let Some(atom) = conjunct.atom() {
            visit(atom.value());
        }
    });
}
