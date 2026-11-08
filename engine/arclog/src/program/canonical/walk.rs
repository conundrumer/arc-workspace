//! The one walk of the nodes of a label scope, from the scope's node to
//! each label use, which the graph of the scope (`graph`) and the form
//! writer (`form`) both take, so that the labeling search and the form it
//! ranks see the same nodes in the same order. Each sink takes from each
//! step of the walk what it builds: the graph a vertex or an edge, the form
//! writer its bytes.

use super::*;

/// A node that the walk opens below another, by an edge of a role and an
/// index.
#[derive(Clone, Copy)]
pub(super) enum Open<'a> {
    Clause(&'a Clause),
    Instance(&'a Instance),
    Choose(&'a Choose),
    RigidDet(&'a RigidDet),
    Out(&'a Out),
    DemoRule(&'a DemoRule),
    KeyClause,
    KeyBody,
    Input(&'a InstanceInput),
    /// A head site of an instance input.
    Head,
    Body,
    /// An atom; `member` where it stands as a conjunct of a body.
    Atom { atom: &'a Atom, negated: bool, member: bool },
    NotForm,
    Constraint(&'a Constraint),
    Or,
    If,
    All,
}

/// What takes the walk of a label scope's nodes.
pub(super) trait ScopeSink<'a> {
    /// The place of a node, under which the walk opens its children.
    type At: Copy;

    /// Sort named sites only for an explicit feature write. Production label
    /// ordering also determines existing callable table layouts.
    fn feature_sites(&self) -> bool;

    /// Opens `node` below the node at `at`, by an edge of `role` and
    /// `index`, and gives its place.
    fn open(&mut self, at: Self::At, role: Tag, index: usize, node: Open<'a>) -> Self::At;

    /// Runs `visit` on `child`, a child of `parent`, the node being walked.
    fn child(&mut self, parent: NodeRef<'a>, child: NodeRef<'a>, visit: impl FnOnce(&mut Self));

    /// Records the source index of each child in the current node's
    /// canonical order, without adding bytes to its form.
    fn children_order(&mut self, _source_indices: &[u32]) {}

    /// Runs `visit` on each of `members`, the whole list of the children of
    /// `parent`, which `node` gives as nodes, in the order the sink takes.
    /// The members at `repeats` repeat an earlier member, so they are not
    /// part of the form.
    fn members<T>(&mut self, at:Self::At, parent: NodeRef<'a>, members: &'a [T], pinned:&[usize], repeats:&[usize], node: impl Fn(&'a T) -> NodeRef<'a>, visit: impl Fn(&mut Self, Self::At, &'a T));

    /// The name of a field of the record at `port`, a column of a head
    /// site, which the walk writes in place of the field that `key` tells
    /// apart. A field is named by the labels of its record's first head,
    /// written or decoded, so a field stands by its order of first use among
    /// the head sites of the instance on that port.
    fn head_field(&mut self, port: &ColumnName, key: HeadKey) -> ColumnName;

    /// The length of a list that the walk visits next.
    fn len(&mut self, len: usize);

    /// Whether the walk visits an optional part next.
    fn option(&mut self, present: bool);

    /// Runs `visit`, the walk of the sites of `atom`, below the atom at `at`,
    /// as the sink takes the orders of the columns of its relation.
    fn atom_sites(&mut self, at: Self::At, atom: &'a Atom, visit: impl Fn(&mut Self, Self::At));

    /// The site at `path`, with `args` arguments, whose columns `relation`
    /// gives, or an instance input's head where it gives none.
    fn site(&mut self, at: Self::At, path: &[ColumnName], args: usize, relation: Option<&RelationRef>);

    /// The label use `label`, the argument at `index` of the site at `path`,
    /// with its name where it is a [`SiteArg::NamedLabel`].
    fn site_label(&mut self, at: Self::At, index: usize, path: &[ColumnName], named: Option<&ColumnName>, label: LabelUse, relation: Option<&RelationRef>);

    /// A field site, an argument of the site the walk visits.
    fn site_field(&mut self);

    /// The operand at `index` of a constraint: a label, or `0` where
    /// `label` is `None`.
    fn operand(&mut self, at: Self::At, index: usize, label: Option<ConstraintLabel>);

    /// Constraint operands in the normalized operator's direction.
    fn constraint(&mut self,at:Self::At,constraint:&Constraint);

    /// The `ONE` marks of the clause at `at`. A clause's marks are a set, and
    /// so are the labels of each mark, so neither order is part of the form.
    fn marks(&mut self, at: Self::At, ones: &'a [OneMark]);

    /// The labels of `columns`, each column of `relation`, or written as
    /// given where `relation` is `None`.
    /// `ordered` holds when the order of `columns` is part of the form, which matters only where `relation` is `None`.
    fn columns(&mut self, at: Self::At, columns: &'a [RelationColumn], relation: Option<&RelationRef>, ordered: bool);

    /// The parts of `choose` after its `from` body that no label enters.
    fn choose_from_inside_for(&mut self, choose: &'a Choose);

    /// The text of `rule`, which no label enters.
    fn rule_text(&mut self, rule: &'a DemoRule);

    /// A form of a `DEMO_RULE` that is a label scope of its own.
    fn own_scope(&mut self, form: &'a Form);
}

/// Walks `scope`, below the node at `root`.
pub(super) fn scope<'a, S: ScopeSink<'a>>(sink: &mut S, root: S::At, scope: LabelScope<'a>) {
    match scope {
        LabelScope::Clause(clause) => self::clause(sink, root, 0, clause),
        LabelScope::Instance(instance) => self::instance(sink, root, 0, instance),
        LabelScope::Choose(choose) => self::choose(sink, root, 0, choose),
        LabelScope::RigidDet(rigid) => rigid_det(sink, root, 0, rigid),
        LabelScope::Out(out) => self::out(sink, root, 0, out),
        LabelScope::DemonstratedKey(demonstrated) => demonstrated_key(sink, root, demonstrated),
        LabelScope::DemoRule(rule) => demo_rule(sink, root, rule),
        LabelScope::Body(body) => self::body(sink, root, Tag::Body, 0, body),
        LabelScope::Atom(atom) => self::atom(sink, root, Tag::Part, 0, atom, false, false),
        LabelScope::KeyClause(key) => key_clause(sink, root, key),
        LabelScope::InstanceInput(input) => self::input(sink, root, 0, input),
    }
}

pub(super) fn clause<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, clause: &'a Clause) {
    let derives = relation_of(&clause.derives);
    let at = sink.open(at, Tag::Form, index, Open::Clause(clause));
    let body = clause.body.value();
    sink.child(NodeRef::Clause(clause), NodeRef::Body(body), |sink| self::body(sink, at, Tag::Body, 0, body));
    sink.len(usize::from(clause.set));
    sink.marks(at, &clause.ones);
    sink.columns(at, &clause.columns, Some(&derives), true);
}

pub(super) fn body<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, role: Tag, index: usize, body: &'a Body) {
    body_order(sink, at, role, index, body, false);
}

/// CHOOSE selects its candidate source and pair from written reads. Without
/// resolved alias/IR identity, preserve these whole bodies conservatively.
fn body_order<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, role: Tag, index: usize, body: &'a Body, ordered: bool) {
    let at = sink.open(at, role, index, Open::Body);
    let pinned = if ordered { (0..body.conjuncts.len()).collect::<Vec<_>>() } else { Vec::new() };
    // A body is a conjunction, so a conjunct that repeats an earlier one
    // adds nothing to it.
    let repeats: Vec<usize> = if ordered { Vec::new() } else { (0..body.conjuncts.len()).filter(|&i| body.conjuncts[..i].iter().any(|earlier| same_conjunct(earlier, &body.conjuncts[i]))).collect() };
    sink.members(at,NodeRef::Body(body), &body.conjuncts, &pinned,&repeats,NodeRef::Conjunct, |sink, at,conjunct| self::conjunct(sink, at, conjunct));
}

/// The marks of `ones` less each that names the same labels as an earlier one.
pub(super) fn distinct_marks(ones: &[OneMark]) -> Vec<&OneMark> {
    let labels = |one: &OneMark| {
        let mut labels: Vec<u32> = one.key.iter().map(|label| label.0).collect();
        labels.sort();
        labels.dedup();
        labels
    };
    let mut seen = Vec::new();
    ones.iter().filter(|one| {
        let own = labels(one);
        let new = !seen.contains(&own);
        if new {
            seen.push(own);
        }
        new
    }).collect()
}

/// Whether `a` and `b` are the same atom, negated atom or constraint, with
/// the same labels: equal but for the order of an atom's sites, or of the
/// operands of a symmetric constraint.
fn same_conjunct(a: &Conjunct, b: &Conjunct) -> bool {
    let same_atom = |a: &Atom, b: &Atom| {
        let count = |sites: &[Site], site: &Site| sites.iter().filter(|own| *own == site).count();
        a.relation == b.relation && a.sites.len() == b.sites.len() && a.sites.iter().all(|site| count(&a.sites, site) == count(&b.sites, site))
    };
    match (a, b) {
        (Conjunct::Atom(a), Conjunct::Atom(b)) | (Conjunct::Not(Negated::Atom(a)), Conjunct::Not(Negated::Atom(b))) => same_atom(a.value(), b.value()),
        (Conjunct::Constraint(a), Conjunct::Constraint(b)) => {
            let (a_op, [a0, a1], symmetric) = normalized_constraint(a);
            let (b_op, [b0, b1], _) = normalized_constraint(b);
            a_op == b_op && ((a0, a1) == (b0, b1) || symmetric && (a0, a1) == (b1, b0))
        }
        _ => false,
    }
}

pub(super) fn conjunct<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, conjunct: &'a Conjunct) {
    let parent = NodeRef::Conjunct(conjunct);
    match conjunct {
        Conjunct::Atom(atom) => self::atom(sink, at, Tag::Member, 0, atom.value(), false, true),
        Conjunct::Not(Negated::Atom(atom)) => self::atom(sink, at, Tag::Member, 0, atom.value(), true, true),
        Conjunct::Not(Negated::Form(form)) => {
            let at = sink.open(at, Tag::Member, 0, Open::NotForm);
            sink.child(parent, NodeRef::Conjunct(form), |sink| self::conjunct(sink, at, form));
        }
        Conjunct::Constraint(constraint) => {
            let at = sink.open(at, Tag::Member, 0, Open::Constraint(constraint));
            sink.constraint(at,constraint);
        }
        Conjunct::Or(branches) => {
            let at = sink.open(at, Tag::Member, 0, Open::Or);
            // Branches are alternatives, so their order is not part of the form.
            sink.members(at,parent,&branches[..],&[],&[],|branch|NodeRef::Body(branch.value()),|sink,at,branch|self::body(sink,at,Tag::Branch,0,branch.value()));
        }
        Conjunct::If { test, then, otherwise } => {
            let at = sink.open(at, Tag::Member, 0, Open::If);
            for (index, part) in [test, then, otherwise].into_iter().enumerate() {
                sink.child(parent, NodeRef::Body(part.value()), |sink| self::body(sink, at, Tag::Part, index, part.value()));
            }
        }
        Conjunct::All { domain, body } => {
            let at = sink.open(at, Tag::Member, 0, Open::All);
            for (index, part) in [domain, body].into_iter().enumerate() {
                sink.child(parent, NodeRef::Body(part.value()), |sink| self::body(sink, at, Tag::Part, index, part.value()));
            }
        }
    }
}

pub(super) fn atom<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, role: Tag, index: usize, atom: &'a Atom, negated: bool, member: bool) {
    let at = sink.open(at, role, index, Open::Atom { atom, negated, member });
    // The sites of an atom are unordered: a site names its column, so the order they are written in scopes nothing
    // (`docs/arclog/arclog.md#sites`). The labels' canonical positions come from the graph, which no site order enters,
    // so sorting the sites changes the form and not the order of a relation's callable columns.
    sink.atom_sites(at, atom, |sink, at| sink.members(at,NodeRef::Atom(atom),&atom.sites,&[],&[],NodeRef::Site,|sink,at,site|self::site(sink,at,site,&[],Some(&atom.relation))));
}

/// Walks `site`, a site on the column `prefix` then its own column gives.
pub(super) fn site<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, site: &'a Site, prefix: &[ColumnName], relation: Option<&RelationRef>) {
    // On a head, the column of the site is a port's, and each name below it
    // is a field of the record the head projects.
    let head = relation.is_none();
    let port = prefix.first().unwrap_or(&site.column);
    let column = if head && !prefix.is_empty() { sink.head_field(port, HeadKey::Name(site.column.clone())) } else { site.column.clone() };
    let path = column_path(prefix, &column);
    sink.site(at, &path, site.value.args.len(), relation);
    // A head site of one label projects that label onto a column of no
    // record, or of a record of one field, so the label tells its field
    // apart, and the name it takes in a text or a decode does not.
    let one_label = head && prefix.is_empty() && match &site.value.args[..] {
        [SiteArg::NamedLabel { .. }] => true,
        [SiteArg::Field(field)] => matches!(&field.value.args[..], [SiteArg::Label(_)]),
        _ => false,
    };
    let named=|sink:&mut S,at,index,name:&ColumnName,label:LabelUse|{
        let name = match (head, one_label, label) {
            (true, true, LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)) => sink.head_field(port, HeadKey::Label(id)),
            (true, _, _) => sink.head_field(port, HeadKey::Name(name.clone())),
            (false, _, _) => name.clone(),
        };
        sink.site_label(at,index,&path,Some(&name),label,relation)
    };
    let visit=|sink:&mut S,at,arg:&'a SiteArg,index|match arg {
        SiteArg::Label(label)=>sink.site_label(at,index,&path,None,*label,relation),
        SiteArg::NamedLabel {name,label}=>named(sink,at,index,name,*label),
        // A field that holds one label is that label, named by the field: a
        // decode writes it as a named label, a text as a field.
        SiteArg::Field(field) if matches!(&field.value.args[..],[SiteArg::Label(_)])=>{
            let SiteArg::Label(label)=&field.value.args[0] else { unreachable!("the field holds one label") };
            named(sink,at,index,&field.column,*label)
        }
        SiteArg::Field(field)=>{sink.site_field();self::site(sink,at,field,&path,relation);},
    };
    let node = |arg:&'a SiteArg| match arg {
        SiteArg::Field(s)=>NodeRef::Site(s),
        SiteArg::Label(l)|SiteArg::NamedLabel {label:l,..}=>NodeRef::Label(l),
    };
    if sink.feature_sites() && site.value.args.iter().all(|arg|!matches!(arg,SiteArg::Label(_))) {
        sink.members(at,NodeRef::Site(site),&site.value.args,&[],&[],node,|sink,at,arg|visit(sink,at,arg,0));
    } else {
        for(index,arg)in site.value.args.iter().enumerate() {
            // Positional children are not sorted, but still enter their AST
            // path: a nested field may itself record a sorted child list.
            sink.child(NodeRef::Site(site),node(arg),|sink|visit(sink,at,arg,index));
        }
    }
}

pub(super) fn instance<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, instance: &'a Instance) {
    let at = sink.open(at, Tag::Form, index, Open::Instance(instance));
    let parent = NodeRef::Instance(instance);
    key_and_inputs(sink, at, parent, instance.key.as_ref(), &instance.inputs, false);
}

/// Walks the key clause where the form has one, then `inputs`, children of
/// `parent`, the node at `at`.
fn key_and_inputs<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, parent: NodeRef<'a>, key: Option<&'a Node<KeyClause>>, inputs: &'a [Node<InstanceInput>], value_first: bool) {
    sink.option(key.is_some());
    if let Some(key) = key {
        sink.child(parent, NodeRef::KeyClause(key.value()), |sink| key_clause_inputs(sink, at, key.value(), value_first));
    }
    self::inputs(sink, at, parent, inputs, value_first);
}

fn inputs<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, parent: NodeRef<'a>, inputs: &'a [Node<InstanceInput>], value_first: bool) {
    let mut indices: Vec<usize> = (0..inputs.len()).collect();
    if value_first {
        // Demonstrated inputs have fixed language roles. Keep the stream's
        // value-then-demonstration order, including for inputs inside a key.
        indices.sort_by_key(|&index| inputs[index].value().name.0.as_ref() != "value");
        let slots: Vec<u32> = inputs.iter().map(|input| child_step(parent, NodeRef::InstanceInput(input.value()))).collect();
        let mut children: Vec<u32> = (0..parent.children().len() as u32).collect();
        for (slot, &index) in slots.iter().zip(&indices) {
            children[*slot as usize] = slots[index];
        }
        sink.children_order(&children);
    }
    sink.len(inputs.len());
    for (index, source) in indices.into_iter().enumerate() {
        let input = &inputs[source];
        sink.child(parent, NodeRef::InstanceInput(input.value()), |sink| self::input(sink, at, index, input.value()));
    }
}

pub(super) fn key_clause<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, key: &'a KeyClause) {
    key_clause_inputs(sink, at, key, false);
}

fn key_clause_inputs<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, key: &'a KeyClause, value_first: bool) {
    let at = sink.open(at, Tag::KeyClause, 0, Open::KeyClause);
    let parent = NodeRef::KeyClause(key);
    // A key is a record of its `^` labels, which a site reads by field name, so the order of its columns is not part of the form.
    key_body(sink, at, parent, Tag::Key, &key.key, false);
    inputs(sink, at, parent, &key.inputs, value_first);
}

/// Walks `key`, whose body is a child of `parent`, the node at `at`.
pub(super) fn key_body<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, parent: NodeRef<'a>, role: Tag, key: &'a KeyBody, ordered: bool) {
    let at = sink.open(at, role, 0, Open::KeyBody);
    let body = key.body.value();
    sink.child(parent, NodeRef::Body(body), |sink| self::body(sink, at, Tag::Body, 0, body));
    sink.columns(at, &key.columns, None, ordered);
}

pub(super) fn input<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, input: &'a InstanceInput) {
    let at = sink.open(at, Tag::Input, index, Open::Input(input));
    sink.len(input.head.len());
    if sink.feature_sites() {
        // The head sites name their columns, so the order they are written in scopes nothing.
        sink.members(at, NodeRef::InstanceInput(input), &input.head, &[], &[], |site| NodeRef::Site(site), |sink, at, site| {
            let head = sink.open(at, Tag::Head, 0, Open::Head);
            self::site(sink, head, site, &[], None)
        });
    } else {
    for (index, site) in input.head.iter().enumerate() {
        let head = sink.open(at, Tag::Head, index, Open::Head);
        // A head site owns its own children, not the input's BODY/sibling
        // sites. Keep every recorded list anchored at that actual node.
        sink.child(NodeRef::InstanceInput(input),NodeRef::Site(site),|sink|self::site(sink, head, site, &[], None));
    }
    }
    let body = input.body.value();
    sink.child(NodeRef::InstanceInput(input), NodeRef::Body(body), |sink| self::body(sink, at, Tag::Body, 0, body));
}

pub(super) fn choose<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, choose: &'a Choose) {
    let at = sink.open(at, Tag::Form, index, Open::Choose(choose));
    let parent = NodeRef::Choose(choose);
    sink.option(choose.rows.is_some());
    if let Some(rows) = &choose.rows {
        key_body(sink, at, parent, Tag::Key, rows, true);
    }
    sink.columns(at, &choose.candidate_columns, Some(&RelationRef::Declared(choose.name.clone())), true);
    let from = choose.from.value();
    sink.child(parent, NodeRef::Body(from), |sink| body_order(sink, at, Tag::Body, 0, from, true));
    sink.choose_from_inside_for(choose);
    sink.len(choose.never.len());
    for (index, never) in choose.never.iter().enumerate() {
        sink.child(parent, NodeRef::Body(never.value()), |sink| {
            body_order(sink, at, Tag::Part, index, never.value(), true);
        });
    }
}

pub(super) fn rigid_det<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, rigid: &'a RigidDet) {
    let at = sink.open(at, Tag::Form, index, Open::RigidDet(rigid));
    let parent = NodeRef::RigidDet(rigid);
    for (key, role) in [(&rigid.key, Tag::Key), (&rigid.instance, Tag::Instance)] {
        sink.option(key.is_some());
        if let Some(key) = key {
            key_body(sink, at, parent, role, key, true);
        }
    }
    sink.len(rigid.parts.len());
    for (index, part) in rigid.parts.iter().enumerate() {
        sink.child(parent, NodeRef::Atom(part.value()), |sink| self::atom(sink, at, Tag::Part, index, part.value(), false, false));
    }
}

pub(super) fn out<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, out: &'a Out) {
    let at = sink.open(at, Tag::Form, index, Open::Out(out));
    key_body(sink, at, NodeRef::Out(out), Tag::Key, &out.key, true);
}

/// Walks the key clause and the inputs of `demonstrated`, below the node
/// at `at`.
pub(super) fn demonstrated_key<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, demonstrated: &'a Demonstrated) {
    key_and_inputs(sink, at, NodeRef::Demonstrated(demonstrated), demonstrated.key.as_ref(), &demonstrated.inputs, false);
}

pub(super) fn demo_rule<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, rule: &'a DemoRule) {
    let at = sink.open(at, Tag::DemoRule, 0, Open::DemoRule(rule));
    sink.columns(at, &rule.fields, Some(&prediction()), true);
    sink.rule_text(rule);
    sink.len(rule.forms.len());
    for (index, form) in rule.forms.iter().enumerate() {
        sink.child(NodeRef::DemoRule(rule), NodeRef::from(form), |sink| match form {
            _ if !shares_rule_scope(rule, index) => sink.own_scope(form),
            Form::Clause(clause) => self::clause(sink, at, index, clause.value()),
            Form::Instance(instance) => self::instance(sink, at, index, instance.value()),
            Form::Choose(choose) => self::choose(sink, at, index, choose.value()),
            Form::RigidDet(rigid) => rigid_det(sink, at, index, rigid.value()),
            Form::Claim(_) | Form::Demonstrated(_) | Form::Alts(_) | Form::Out(_) => unreachable!("`shares_rule_scope` holds of none of these"),
        });
    }
}

/// The labels of the scope of `form`, in order of their ids, where `form`
/// holds no label scope within it: a clause, an `INIT`, a `CHOOSE`, a
/// `RIGID_DET` or an `OUT` form. They are the labels that
/// [`form_scope_labels`] gives, with no labeling of the scope, for a reader
/// to whom their order is no part of what it reads.
pub(crate) fn one_scope_labels(form: &Form) -> Option<Vec<LabelId>> {
    if !matches!(form, Form::Clause(_) | Form::Instance(_) | Form::Choose(_) | Form::RigidDet(_) | Form::Out(_)) {
        return None;
    }
    let mut sink = LabelSink::default();
    scope(&mut sink, (), form_scope(form).expect("a form of one scope has its scope"));
    sink.labels.sort_unstable_by_key(|label| label.0);
    sink.labels.dedup();
    Some(sink.labels)
}

/// Takes from the walk of a scope each label that it visits.
#[derive(Default)]
struct LabelSink {
    labels: Vec<LabelId>,
}

impl<'a> ScopeSink<'a> for LabelSink {
    type At = ();

    fn feature_sites(&self) -> bool {
        false
    }

    fn open(&mut self, _at: (), _role: Tag, _index: usize, _node: Open<'a>) {}

    fn child(&mut self, _parent: NodeRef<'a>, _child: NodeRef<'a>, visit: impl FnOnce(&mut Self)) {
        visit(self);
    }

    fn members<T>(&mut self, at: (), _parent: NodeRef<'a>, members: &'a [T], _pinned: &[usize], repeats: &[usize], _node: impl Fn(&'a T) -> NodeRef<'a>, visit: impl Fn(&mut Self, (), &'a T)) {
        for (_, member) in members.iter().enumerate().filter(|(index, _)| !repeats.contains(index)) {
            visit(self, at, member);
        }
    }

    fn head_field(&mut self, port: &ColumnName, _key: HeadKey) -> ColumnName {
        port.clone()
    }

    fn len(&mut self, _len: usize) {}

    fn option(&mut self, _present: bool) {}

    fn atom_sites(&mut self, at: (), _atom: &'a Atom, visit: impl Fn(&mut Self, ())) {
        visit(self, at);
    }

    fn site(&mut self, _at: (), _path: &[ColumnName], _args: usize, _relation: Option<&RelationRef>) {}

    fn site_label(&mut self, _at: (), _index: usize, _path: &[ColumnName], _named: Option<&ColumnName>, label: LabelUse, _relation: Option<&RelationRef>) {
        match label {
            LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id) => self.labels.push(id),
            LabelUse::Zero => {}
        }
    }

    fn site_field(&mut self) {}

    fn operand(&mut self, _at: (), _index: usize, label: Option<ConstraintLabel>) {
        self.labels.extend(label.map(|label| label.label));
    }

    fn constraint(&mut self, at: (), constraint: &Constraint) {
        let (_, operands, _) = normalized_constraint(constraint);
        for label in operands {
            self.operand(at, 0, label);
        }
    }

    fn marks(&mut self, _at: (), ones: &'a [OneMark]) {
        self.labels.extend(ones.iter().flat_map(|one| one.key.iter().copied()));
    }

    fn columns(&mut self, _at: (), columns: &'a [RelationColumn], _relation: Option<&RelationRef>, _ordered: bool) {
        self.labels.extend(columns.iter().map(|column| column.label));
    }

    fn choose_from_inside_for(&mut self, _choose: &'a Choose) {}

    fn rule_text(&mut self, _rule: &'a DemoRule) {}

    fn own_scope(&mut self, _form: &'a Form) {}
}
