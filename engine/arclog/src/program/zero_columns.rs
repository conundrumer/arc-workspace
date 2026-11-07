//! The zero-column lowering of a case program, the program that
//! [`crate::solver::Case::program_alone`] gives: each column that is `0` in
//! every clause of its relation is dropped, as
//! `docs/engine/arclog-expansion.md#zero-columns` gives the rule.
//!
//! For a relation with one clause, a column is `0` in every clause where
//! its clause makes it `0`. An instance or demonstration catalog
//! counts as a relation whose columns are the `^` labels of its key, and the
//! reads of its outputs read it at their key site, `(:key ...)`, one field
//! for each key column.
//!
//! A label is `0` in a body where a positive atom at its top level, or each
//! branch of an `OR` at its top level, has a site of the label on a dropped
//! column, or where it is the label of a head column that `(= *X 0)` makes.
//! A head column whose label is `0` drops in turn, so the lowering runs to a
//! fixed point. A column stays, with its `(= *X 0)`, where its rewrite would
//! put `0` where it may not stand.

use std::sync::Arc;

use super::path::NodeRef;
use super::*;
use crate::hash::{StableHashMap, StableHashSet};
use crate::registry::Registry;
use crate::resolver::registry_columns::{component, typed_columns};
use crate::types::{each_site_label, use_label, ValueType};

/// The forms of a case program with each column that is `0` in every clause
/// of its relation dropped, or `None` where the case drops none. The forms
/// keep their places, so a path of the forms names the same form after.
pub(crate) fn lower(forms: &[Form], registry: &Registry) -> Option<Vec<Form>> {
    if !forms.iter().any(makes_zero) {
        return None;
    }
    let mut lowering = Lowering::new(forms, registry);
    loop {
        let zeros = lowering.settle(forms);
        if lowering.dropped.is_empty() {
            return None;
        }
        let (lowered, mut refused) = lowering.rewrite(forms, &zeros);
        refused.extend(lowering.stranded(forms, &zeros));
        if refused.is_empty() {
            return Some(lowered);
        }
        let before = lowering.kept.len();
        lowering.kept.extend(refused);
        if lowering.kept.len() == before {
            return None;
        }
        lowering.dropped.clear();
    }
}

/// Whether the form is a clause with `(= *X 0)` at the top level of its body.
fn makes_zero(form: &Form) -> bool {
    let Form::Clause(clause) = form else { return false };
    clause.value().body.value().conjuncts.iter().any(|conjunct| zero_made(conjunct).is_some())
}

/// The label that `conjunct` makes `0`, where it is `(= *X 0)`.
fn zero_made(conjunct: &Conjunct) -> Option<LabelId> {
    match conjunct {
        Conjunct::Constraint(Constraint { op: ConstraintOp::Eq, first, second: Operand::Zero }) if first.fresh => Some(first.label),
        _ => None,
    }
}

/// The owner of a column that may drop.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
enum Owner {
    /// A relation that a clause of the program derives.
    Relation(RelationName),
    /// The key of an instance.
    Key(InstanceName),
    /// A relation whose columns never drop: a clause of a port.
    Opaque,
}

/// A column of a relation or of an instance's key.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
struct Column {
    owner: Owner,
    name: ColumnName,
}

/// The labels that are `0` in a body, each with the dropped columns that
/// make it so.
#[derive(Default)]
struct Zeros(StableHashMap<LabelId, Vec<Column>>);

impl Zeros {
    fn add(&mut self, label: LabelId, cause: Column) {
        let causes = self.0.entry(label).or_default();
        if !causes.contains(&cause) {
            causes.push(cause);
        }
    }

    fn holds(&self, label: LabelId) -> bool {
        self.0.contains_key(&label)
    }

    fn causes(&self, label: LabelId) -> &[Column] {
        self.0.get(&label).map_or(&[], Vec::as_slice)
    }

    /// The labels that each of `all` holds, with the causes of every one.
    fn common(mut all: impl Iterator<Item = Zeros>) -> Zeros {
        let Some(mut common) = all.next() else { return Zeros::default() };
        for next in all {
            common.0.retain(|label, causes| {
                let Some(more) = next.0.get(label) else { return false };
                let new: Vec<Column> = more.iter().filter(|cause| !causes.contains(cause)).cloned().collect();
                causes.extend(new);
                true
            });
        }
        common
    }
}

/// The zeros of a form's bodies: of its clause's body or of its key body,
/// and of each of its inputs in the order `written_inputs` gives.
#[derive(Default)]
struct FormZeros {
    body: Zeros,
    inputs: Vec<Zeros>,
}

/// What a site of an atom is to the lowering.
enum Dropped {
    /// The site is on a dropped column.
    Whole(Column),
    /// The site is the key site of a read of an instance's output; the
    /// arguments, by index, that are fields of a dropped key column.
    Fields(Vec<(usize, Column)>),
    No,
}

struct Lowering<'r> {
    registry: &'r Registry,
    /// The columns the lowering drops.
    dropped: StableHashSet<Column>,
    /// The columns that stay.
    kept: StableHashSet<Column>,
    /// The relations of more than one clause, and the instances whose key
    /// fills an input: every column of one stays.
    pinned: StableHashSet<Owner>,
    /// The key columns of each keyed instance.
    keys: StableHashMap<InstanceName, Vec<ColumnName>>,
    /// The relations left with no column and no atom.
    bare: StableHashSet<RelationName>,
}

impl<'r> Lowering<'r> {
    fn new(forms: &[Form], registry: &'r Registry) -> Self {
        let mut pinned = StableHashSet::default();
        let mut keys = StableHashMap::default();
        let mut clauses: StableHashMap<&RelationName, usize> = StableHashMap::default();
        for form in forms {
            match form {
                Form::Clause(clause) => {
                    if let ProgramRelation::Declared(name) = &clause.value().derives {
                        *clauses.entry(name).or_default() += 1;
                    }
                }
                Form::Instance(instance) => {
                    let instance = instance.value();
                    let Some(key) = &instance.key else { continue };
                    keys.insert(instance.name.clone(), key.value().key.columns.iter().map(|column| column.name.clone()).collect());
                    if fills_from_key(instance, registry) {
                        pinned.insert(Owner::Key(instance.name.clone()));
                    }
                }
                _ => {}
            }
        }
        pinned.extend(clauses.into_iter().filter(|(_, count)| *count > 1).map(|(name, _)| Owner::Relation(name.clone())));
        Lowering { registry, dropped: StableHashSet::default(), kept: StableHashSet::default(), pinned, keys, bare: StableHashSet::default() }
    }

    fn droppable(&self, column: &Column) -> bool {
        column.owner != Owner::Opaque && !self.pinned.contains(&column.owner) && !self.kept.contains(column)
    }

    /// The columns of the relation or key that `form` gives, each with its
    /// label.
    fn heads(&self, form: &Form) -> Vec<(Column, LabelId)> {
        match form {
            Form::Clause(clause) => {
                let clause = clause.value();
                let owner = match &clause.derives {
                    ProgramRelation::Declared(name) => Owner::Relation(name.clone()),
                    ProgramRelation::Output(_) => Owner::Opaque,
                };
                clause.columns.iter().map(|column| (Column { owner: owner.clone(), name: column.name.clone() }, column.label)).collect()
            }
            Form::Instance(instance) => {
                let instance = instance.value();
                let columns = instance.key.iter().flat_map(|key| key.value().key.columns.iter());
                columns.map(|column| (Column { owner: Owner::Key(instance.name.clone()), name: column.name.clone() }, column.label)).collect()
            }
            _ => Vec::new(),
        }
    }

    /// The dropped columns, to a fixed point, with the zeros of each form
    /// that they give.
    fn settle(&mut self, forms: &[Form]) -> Vec<FormZeros> {
        loop {
            let zeros: Vec<FormZeros> = forms.iter().map(|form| self.zeros_of(form)).collect();
            let mut grew = false;
            for (form, zeros) in forms.iter().zip(&zeros) {
                for (column, label) in self.heads(form) {
                    if zeros.body.holds(label) && self.droppable(&column) && self.dropped.insert(column) {
                        grew = true;
                    }
                }
            }
            if !grew {
                self.bare = forms.iter().zip(&zeros).filter_map(|(form, zeros)| self.true_relation(form, zeros)).collect();
                return zeros;
            }
        }
    }

    /// The name of the relation `form` derives where every column of the
    /// relation drops, at least one does, and no conjunct but a `(= *X 0)`
    /// that a dropped column made stays.
    fn true_relation(&self, form: &Form, zeros: &FormZeros) -> Option<RelationName> {
        let Form::Clause(clause) = form else { return None };
        let clause = clause.value();
        let ProgramRelation::Declared(name) = &clause.derives else { return None };
        let columns = self.heads(form);
        let drops_all = !columns.is_empty() && columns.iter().all(|(column, _)| self.dropped.contains(column));
        let only_zeros = clause.body.value().conjuncts.iter().all(|conjunct| zero_made(conjunct).is_some_and(|label| zeros.body.holds(label)));
        (drops_all && only_zeros).then(|| name.clone())
    }

    /// The labels that are `0` in each body of `form`, given the columns
    /// dropped so far.
    fn zeros_of(&self, form: &Form) -> FormZeros {
        match form {
            Form::Clause(clause) => {
                let clause = clause.value();
                let own = self.heads(form).into_iter().filter(|(column, _)| self.droppable(column)).map(|(column, label)| (label, column)).collect();
                FormZeros { body: self.forced(clause.body.value(), &own), inputs: Vec::new() }
            }
            Form::Instance(instance) => self.key_zeros(instance.value().key.as_ref(), &instance.value().inputs),
            _ => FormZeros::default(),
        }
    }

    /// The zeros of a key and its inputs, with key labels shared only by
    /// the inputs inside the key clause.
    fn key_zeros(&self, key: Option<&Node<KeyClause>>, inputs: &[Node<InstanceInput>]) -> FormZeros {
        let none = StableHashMap::default();
        let mut zeros = Zeros::default();
        let mut key_labels = StableHashSet::default();
        if let Some(clause) = key {
            zeros = self.forced(clause.value().key.body.value(), &none);
            crate::safety::each_label_use(clause.value().key.body.value(), &mut |use_| key_labels.extend(use_label(use_)));
        }
        let keyed = key.into_iter().flat_map(|clause| clause.value().inputs.iter()).map(|input| {
            let mut own = self.forced(input.value().body.value(), &none);
            own.0.retain(|label, _| !key_labels.contains(label));
            for (label, causes) in &zeros.0 {
                own.0.insert(*label, causes.clone());
            }
            own
        });
        let others = inputs.iter().map(|input| self.forced(input.value().body.value(), &none));
        let inputs = keyed.chain(others).collect();
        FormZeros { body: zeros, inputs }
    }

    /// The labels that `body` makes `0`: those at a dropped column of a
    /// positive atom at its top level, those that each branch of an `OR` at
    /// its top level makes `0`, and those that `(= *X 0)` makes for a column
    /// in `own`, by its label.
    fn forced(&self, body: &Body, own: &StableHashMap<LabelId, Column>) -> Zeros {
        let mut zeros = Zeros::default();
        for conjunct in body.conjuncts.iter() {
            match conjunct {
                Conjunct::Atom(atom) => self.each_dropped_label(atom.value(), &mut |label, column| zeros.add(label, column)),
                Conjunct::Or(branches) => {
                    let none = StableHashMap::default();
                    for (label, causes) in Zeros::common(branches.iter().map(|branch| self.forced(branch.value(), &none))).0 {
                        for cause in causes {
                            zeros.add(label, cause);
                        }
                    }
                }
                _ => {
                    if let Some((label, column)) = zero_made(conjunct).and_then(|label| Some((label, own.get(&label)?))) {
                        zeros.add(label, column.clone());
                    }
                }
            }
        }
        zeros
    }

    /// Calls `visit` on each label at a dropped column of `atom`, with the column.
    fn each_dropped_label(&self, atom: &Atom, visit: &mut dyn FnMut(LabelId, Column)) {
        for site in atom.sites.iter() {
            match self.dropped_parts(atom, site) {
                Dropped::Whole(column) => labels_of_site(site).into_iter().filter_map(use_label).for_each(|label| visit(label, column.clone())),
                Dropped::Fields(fields) => {
                    for (index, column) in fields {
                        labels_of_arg(&site.value.args[index]).into_iter().filter_map(use_label).for_each(|label| visit(label, column.clone()));
                    }
                }
                Dropped::No => {}
            }
        }
    }

    /// What `site` of `atom` is, given the columns dropped so far.
    fn dropped_parts(&self, atom: &Atom, site: &Site) -> Dropped {
        match &atom.relation {
            RelationRef::Declared(name) => {
                let column = Column { owner: Owner::Relation(name.clone()), name: site.column.clone() };
                if self.dropped.contains(&column) { Dropped::Whole(column) } else { Dropped::No }
            }
            RelationRef::Output(OutputName { of: OutputOwner::Instance(instance), .. }) if site.column == crate::resolver::columns::key() => {
                self.dropped_key_parts(instance, site)
            }
            _ => Dropped::No,
        }
    }

    fn dropped_key_parts(&self, instance: &InstanceName, site: &Site) -> Dropped {
        let fields: Vec<(usize, Column)> = site.value.args.iter().enumerate().filter_map(|(index, arg)| {
            let column = Column { owner: Owner::Key(instance.clone()), name: arg_field(arg)?.clone() };
            self.dropped.contains(&column).then_some((index, column))
        }).collect();
        if fields.is_empty() { Dropped::No } else { Dropped::Fields(fields) }
    }

    /// The columns that make `0` the label of a head column that stays: they
    /// stay too, since the head column would have no site.
    fn stranded(&self, forms: &[Form], zeros: &[FormZeros]) -> Vec<Column> {
        let mut refused = Vec::new();
        for (form, zeros) in forms.iter().zip(zeros) {
            for (column, label) in self.heads(form) {
                if zeros.body.holds(label) && !self.dropped.contains(&column) {
                    refused.extend(zeros.body.causes(label).iter().cloned());
                }
            }
        }
        refused
    }

    /// The forms with the dropped columns left out, and the columns that
    /// must stay since a read of them cannot be rewritten.
    fn rewrite(&self, forms: &[Form], zeros: &[FormZeros]) -> (Vec<Form>, Vec<Column>) {
        let mut refused = Vec::new();
        let none = Zeros::default();
        let lowered = forms
            .iter()
            .zip(zeros)
            .map(|(form, zeros)| match form {
                Form::Clause(clause) => self.clause(form, clause, zeros, &mut refused),
                Form::Instance(instance) => self.instance(form, instance, zeros, &mut refused),
                other => {
                    let mut pass = Pass::new(self, &none);
                    each_atom(NodeRef::from(other), &mut |atom| {
                        pass.atom_value(atom);
                    });
                    refused.extend(pass.refused);
                    other.clone()
                }
            })
            .collect();
        (lowered, refused)
    }

    fn clause(&self, form: &Form, clause: &Node<Clause>, zeros: &FormZeros, refused: &mut Vec<Column>) -> Form {
        let value = clause.value();
        let mut pass = Pass::new(self, &zeros.body);
        let body = pass.body(&value.body, true);
        for one in value.ones.iter() {
            one.key.iter().for_each(|label| pass.forbid(*label));
        }
        let heads = self.heads(form);
        let columns: Vec<RelationColumn> = value.columns.iter().zip(&heads).filter(|(_, (column, _))| !self.dropped.contains(column)).map(|(column, _)| column.clone()).collect();
        refused.extend(pass.refused);
        if !pass.changed && columns.len() == value.columns.len() {
            return form.clone();
        }
        Form::Clause(Node::new(Clause { body, columns: columns.into(), ..value.clone() }))
    }

    fn instance(&self, form: &Form, instance: &Node<Instance>, zeros: &FormZeros, refused: &mut Vec<Column>) -> Form {
        let value = instance.value();
        let mut input_zeros = zeros.inputs.iter();
        let key = value.key.as_ref().map(|clause| self.key_clause(&value.name, clause, zeros, &mut input_zeros, refused));
        let inputs = self.inputs(&value.inputs, &mut input_zeros, refused);
        if key.as_ref().is_none_or(|key| key.is_none()) && inputs.is_none() {
            return form.clone();
        }
        let mut key = match key {
            Some(Some(lowered)) => Some(lowered),
            _ => value.key.clone(),
        };
        let mut inputs = inputs.unwrap_or_else(|| value.inputs.clone());
        // A key of no column holds for the one key of no column, so no input reads a key label, and each stands after the key clause.
        if let Some(clause) = key.as_ref().filter(|clause| clause.value().key.columns.is_empty() && !clause.value().inputs.is_empty()) {
            let mut moved: Vec<Node<InstanceInput>> = clause.value().inputs.iter().chain(inputs.iter()).cloned().collect();
            let declared = component(self.registry, &value.component);
            moved.sort_by_key(|input| declared.and_then(|component| component.inputs.iter().position(|own| own.port.name == input.value().name)));
            inputs = moved.into();
            key = Some(Node::new(KeyClause { key: clause.value().key.clone(), inputs: Arc::new([]) }));
        }
        Form::Instance(Node::new(Instance { name: value.name.clone(), component: value.component.clone(), key, inputs }))
    }

    /// The key clause of the instance `name` after the rewrite, or `None`
    /// where it is as it was.
    fn key_clause(&self, name: &InstanceName, clause: &Node<KeyClause>, zeros: &FormZeros, input_zeros: &mut std::slice::Iter<'_, Zeros>, refused: &mut Vec<Column>) -> Option<Node<KeyClause>> {
        let value = clause.value();
        let mut pass = Pass::new(self, &zeros.body);
        let body = pass.body(&value.key.body, false);
        refused.extend(pass.refused);
        let columns: Vec<RelationColumn> =
            value.key.columns.iter().filter(|column| !self.dropped.contains(&Column { owner: Owner::Key(name.clone()), name: column.name.clone() })).cloned().collect();
        let inputs = self.inputs(&value.inputs, input_zeros, refused);
        if !pass.changed && columns.len() == value.key.columns.len() && inputs.is_none() {
            return None;
        }
        Some(Node::new(KeyClause { key: KeyBody { body, columns: columns.into() }, inputs: inputs.unwrap_or_else(|| value.inputs.clone()) }))
    }

    /// The inputs `inputs` after the rewrite, each with the next of
    /// `input_zeros`, or `None` where none changes.
    fn inputs(&self, inputs: &[Node<InstanceInput>], input_zeros: &mut std::slice::Iter<'_, Zeros>, refused: &mut Vec<Column>) -> Option<Arc<[Node<InstanceInput>]>> {
        let lowered: Vec<Option<Node<InstanceInput>>> = inputs.iter().map(|input| self.input(input, input_zeros.next().expect("the zeros of an input"), refused)).collect();
        lowered.iter().any(Option::is_some).then(|| inputs.iter().zip(lowered).map(|(old, new)| new.unwrap_or_else(|| old.clone())).collect())
    }

    fn input(&self, input: &Node<InstanceInput>, zeros: &Zeros, refused: &mut Vec<Column>) -> Option<Node<InstanceInput>> {
        let mut pass = Pass::new(self, zeros);
        for site in input.value().head.iter() {
            labels_of_site(site).into_iter().filter_map(use_label).for_each(|label| pass.forbid(label));
        }
        let body = pass.body(&input.value().body, false);
        refused.extend(pass.refused);
        pass.changed.then(|| Node::new(InstanceInput { body, ..input.value().clone() }))
    }
}

/// Whether `instance` leaves unwritten an input that the engine fills from
/// the key.
fn fills_from_key(instance: &Instance, registry: &Registry) -> bool {
    let Some(component) = component(registry, &instance.component) else { return false };
    let written: Vec<&InstanceInput> = written_inputs(instance.key.as_ref(), &instance.inputs).collect();
    component.inputs.iter().any(|own| own.from_key && written.iter().all(|input| input.name != own.port.name))
}

/// The field of a key that an argument of a key site reads.
fn arg_field(arg: &SiteArg) -> Option<&ColumnName> {
    match arg {
        SiteArg::NamedLabel { name, .. } => Some(name),
        SiteArg::Field(field) => Some(&field.column),
        SiteArg::Label(_) => None,
    }
}

/// The label uses of an argument of a site.
fn labels_of_arg(arg: &SiteArg) -> Vec<LabelUse> {
    match arg {
        SiteArg::Label(use_) | SiteArg::NamedLabel { label: use_, .. } => vec![*use_],
        SiteArg::Field(field) => labels_of_site(field),
    }
}

/// The label uses of a site, at any depth.
fn labels_of_site(site: &Site) -> Vec<LabelUse> {
    let mut uses = Vec::new();
    each_site_label(site, &mut Vec::new(), &mut |use_, _| uses.push(use_));
    uses
}

/// Calls `visit` on each atom below `node`.
fn each_atom<'a>(node: NodeRef<'a>, visit: &mut dyn FnMut(&'a Atom)) {
    if let Some(atom) = node.atom() {
        visit(atom);
    }
    for child in node.children() {
        each_atom(child, visit);
    }
}

/// The rewrite of one body: the labels `zeros` holds read `0`, each dropped
/// site goes, and `refused` gets the columns that must stay.
struct Pass<'a> {
    lowering: &'a Lowering<'a>,
    zeros: &'a Zeros,
    refused: Vec<Column>,
    changed: bool,
}

impl<'a> Pass<'a> {
    fn new(lowering: &'a Lowering<'a>, zeros: &'a Zeros) -> Self {
        Pass { lowering, zeros, refused: Vec::new(), changed: false }
    }

    /// Refuses the label `label`, which is `0` where `0` may not stand: the
    /// columns that make it `0` stay.
    fn forbid(&mut self, label: LabelId) {
        self.refused.extend(self.zeros.causes(label).iter().cloned());
    }

    /// Runs `f`, and gives whether it changed something.
    fn tracked<T>(&mut self, f: impl FnOnce(&mut Self) -> T) -> (T, bool) {
        let before = std::mem::replace(&mut self.changed, false);
        let value = f(self);
        let changed = std::mem::replace(&mut self.changed, before);
        self.changed |= changed;
        (value, changed)
    }

    /// `body` with its zeros read as `0`. `clause_top` holds for the body
    /// of a clause, which may be left with no conjunct.
    fn body(&mut self, body: &Node<Body>, clause_top: bool) -> Node<Body> {
        let (lowered, changed) = self.tracked(|pass| {
            let lowered: Vec<Option<Conjunct>> = body.value().conjuncts.iter().map(|conjunct| pass.conjunct(conjunct, clause_top)).collect();
            pass.changed |= lowered.iter().any(Option::is_none);
            lowered.into_iter().flatten().collect::<Vec<Conjunct>>()
        });
        if !changed {
            return body.clone();
        }
        let is_true_read = |conjunct: &Conjunct| matches!(conjunct, Conjunct::Atom(atom) if self.is_true_read(atom.value()));
        let without: Vec<Conjunct> = lowered.iter().filter(|conjunct| !is_true_read(conjunct)).cloned().collect();
        let conjuncts = if without.is_empty() && !clause_top { lowered } else { without };
        Node::new(Body { conjuncts: conjuncts.into() })
    }

    /// Whether `atom` reads a relation that is true, with no site.
    fn is_true_read(&self, atom: &Atom) -> bool {
        matches!(&atom.relation, RelationRef::Declared(name) if self.lowering.bare.contains(name)) && atom.sites.is_empty()
    }

    fn conjunct(&mut self, conjunct: &Conjunct, clause_top: bool) -> Option<Conjunct> {
        Some(match conjunct {
            Conjunct::Atom(atom) => Conjunct::Atom(self.atom(atom)),
            Conjunct::Not(Negated::Atom(atom)) => Conjunct::Not(Negated::Atom(self.atom(atom))),
            Conjunct::Not(Negated::Form(inner)) => {
                let (lowered, changed) = self.tracked(|pass| pass.conjunct(inner, false));
                match lowered {
                    Some(lowered) if changed => Conjunct::Not(Negated::Form(Arc::new(lowered))),
                    _ => conjunct.clone(),
                }
            }
            Conjunct::Constraint(constraint) => Conjunct::Constraint(self.constraint(constraint, clause_top)?),
            Conjunct::Or(branches) => Conjunct::Or(branches.iter().map(|branch| self.body(branch, false)).collect()),
            Conjunct::If { test, then, otherwise } => {
                Conjunct::If { test: self.body(test, false), then: self.body(then, false), otherwise: self.body(otherwise, false) }
            }
            Conjunct::All { domain, body } => Conjunct::All { domain: self.body(domain, false), body: self.body(body, false) },
        })
    }

    /// `constraint` with its zero labels read as `0`, or `None` for the
    /// `(= *X 0)` at the top level of a body that a dropped column made.
    fn constraint(&mut self, constraint: &Constraint, clause_top: bool) -> Option<Constraint> {
        let first_zero = self.zeros.holds(constraint.first.label);
        if clause_top && first_zero && zero_made(&Conjunct::Constraint(*constraint)).is_some() {
            return None;
        }
        if first_zero {
            self.forbid(constraint.first.label);
        }
        let second = match constraint.second {
            Operand::Label(second) if self.zeros.holds(second.label) => {
                if second.fresh {
                    self.forbid(second.label);
                    constraint.second
                } else {
                    self.changed = true;
                    Operand::Zero
                }
            }
            other => other,
        };
        Some(Constraint { second, ..*constraint })
    }

    fn atom(&mut self, atom: &Node<Atom>) -> Node<Atom> {
        let (sites, changed) = self.tracked(|pass| pass.atom_value(atom.value()));
        if changed { Node::new(Atom { relation: atom.value().relation.clone(), sites: sites.into() }) } else { atom.clone() }
    }

    /// The sites of `atom` after the rewrite.
    fn atom_value(&mut self, atom: &Atom) -> Vec<Site> {
        atom.sites.iter().filter_map(|site| self.site(atom, site)).collect()
    }

    fn site(&mut self, atom: &Atom, site: &Site) -> Option<Site> {
        self.unreadable_key(atom, site);
        match self.lowering.dropped_parts(atom, site) {
            Dropped::Whole(column) => {
                self.must_be_zero(&column, labels_of_site(site));
                self.changed = true;
                None
            }
            Dropped::Fields(fields) => {
                let mut args = Vec::new();
                for (index, arg) in site.value.args.iter().enumerate() {
                    match fields.iter().find(|(at, _)| *at == index) {
                        Some((_, column)) => self.must_be_zero(column, labels_of_arg(arg)),
                        None => args.push(self.arg(atom, site, arg)),
                    }
                }
                self.changed = true;
                (!args.is_empty()).then(|| Site { column: site.column.clone(), value: SiteValue { args: args.into() } })
            }
            Dropped::No => {
                let args: Vec<SiteArg> = site.value.args.iter().map(|arg| self.arg(atom, site, arg)).collect();
                Some(Site { column: site.column.clone(), value: SiteValue { args: args.into() } })
            }
        }
    }

    /// A key site of a read of a keyed instance's output with an argument
    /// that names no field cannot be rewritten: the instance's key stays.
    fn unreadable_key(&mut self, atom: &Atom, site: &Site) {
        let instance = match &atom.relation {
            RelationRef::Output(OutputName { of: OutputOwner::Instance(instance), .. }) => instance.clone(),
            _ => return,
        };
        if site.column == crate::resolver::columns::key() && site.value.args.iter().any(|arg| arg_field(arg).is_none() && labels_of_arg(arg) != [LabelUse::Zero]) {
            let columns = self.lowering.keys.get(&instance).into_iter().flatten();
            self.refused.extend(columns.map(|name| Column { owner: Owner::Key(instance.clone()), name: name.clone() }));
        }
    }

    /// `arg` of `site` with its zero labels read as `0` where `0` may stand.
    fn arg(&mut self, atom: &Atom, site: &Site, arg: &SiteArg) -> SiteArg {
        let labels: Vec<LabelId> = labels_of_arg(arg).into_iter().filter_map(use_label).filter(|label| self.zeros.holds(*label)).collect();
        if labels.is_empty() {
            return arg.clone();
        }
        match arg {
            SiteArg::Label(_) if self.zero_stands(atom, site) => {
                self.changed = true;
                SiteArg::Label(LabelUse::Zero)
            }
            _ => {
                labels.into_iter().for_each(|label| self.forbid(label));
                arg.clone()
            }
        }
    }

    /// Whether `0` stands at `site` of `atom`: it is a site on a column of
    /// a fact or a lib relation whose type is a number or a Box.
    fn zero_stands(&self, atom: &Atom, site: &Site) -> bool {
        let Some(columns) = typed_columns(self.lowering.registry, &atom.relation) else { return false };
        let ty = columns.iter().find(|column| column.name == site.column).and_then(|column| column.ty.fixed());
        site.value.args.len() == 1 && ty.is_some_and(ValueType::has_zero)
    }

    /// The site on the dropped column `column` holds only `0`s: each of its
    /// labels is `0` in the body or is `0`; otherwise the column stays.
    fn must_be_zero(&mut self, column: &Column, labels: Vec<LabelUse>) {
        let zero = labels.into_iter().filter_map(use_label).all(|label| self.zeros.holds(label));
        if !zero {
            self.refused.push(column.clone());
        }
    }
}
