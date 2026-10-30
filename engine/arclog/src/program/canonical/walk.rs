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
    /// A `ONE` mark of a clause.
    One(&'a OneMark),
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

    /// Runs `visit` on each of `members`, the whole list of the children of
    /// `parent`, which `node` gives as nodes, in the order the sink takes.
    fn members<T>(&mut self, at:Self::At, parent: NodeRef<'a>, members: &'a [T], pinned:&[usize], node: impl Fn(&'a T) -> NodeRef<'a>, visit: impl Fn(&mut Self, Self::At, &'a T));

    /// The length of a list that the walk visits next.
    fn len(&mut self, len: usize);

    /// Whether the walk visits an optional part next.
    fn option(&mut self, present: bool);

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

    /// The label at `index` of a `ONE` mark.
    fn one_label(&mut self, at: Self::At, index: usize, label: LabelId);

    /// The labels of `columns`, each column of `relation`, or written as
    /// given where `relation` is `None`.
    fn columns(&mut self, at: Self::At, columns: &'a [RelationColumn], relation: Option<&RelationRef>);

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
    sink.len(clause.ones.len());
    for (index, one) in clause.ones.iter().enumerate() {
        let mark = sink.open(at, Tag::One, index, Open::One(one));
        for (index, label) in one.key.iter().enumerate() {
            sink.one_label(mark, index, *label);
        }
    }
    sink.columns(at, &clause.columns, Some(&derives));
}

pub(super) fn body<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, role: Tag, index: usize, body: &'a Body) {
    body_order(sink, at, role, index, body, false);
}

/// CHOOSE selects its candidate source and pair from written reads. Without
/// resolved alias/IR identity, preserve these whole bodies conservatively.
fn body_order<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, role: Tag, index: usize, body: &'a Body, ordered: bool) {
    let at = sink.open(at, role, index, Open::Body);
    let pinned = if ordered { (0..body.conjuncts.len()).collect::<Vec<_>>() } else { Vec::new() };
    sink.members(at,NodeRef::Body(body), &body.conjuncts, &pinned,NodeRef::Conjunct, |sink, at,conjunct| self::conjunct(sink, at, conjunct));
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
            sink.len(branches.len());
            for(index,branch)in branches.iter().enumerate() {
                sink.child(parent,NodeRef::Body(branch.value()),|sink|self::body(sink,at,Tag::Branch,index,branch.value()));
            }
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
    if sink.feature_sites() {
        sink.members(at,NodeRef::Atom(atom),&atom.sites,&[],NodeRef::Site,|sink,at,site|self::site(sink,at,site,&[],Some(&atom.relation)));
    } else {
        sink.len(atom.sites.len());
        for site in atom.sites.iter() {
            sink.child(NodeRef::Atom(atom),NodeRef::Site(site),|sink|self::site(sink,at,site,&[],Some(&atom.relation)));
        }
    }
}

/// Walks `site`, a site on the column `prefix` then its own column gives.
pub(super) fn site<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, site: &'a Site, prefix: &[ColumnName], relation: Option<&RelationRef>) {
    let path = column_path(prefix, &site.column);
    sink.site(at, &path, site.value.args.len(), relation);
    let visit=|sink:&mut S,at,arg:&'a SiteArg,index|match arg {
        SiteArg::Label(label)=>sink.site_label(at,index,&path,None,*label,relation),
        SiteArg::NamedLabel {name,label}=>sink.site_label(at,index,&path,Some(name),*label,relation),
        SiteArg::Field(field)=>{sink.site_field();self::site(sink,at,field,&path,relation);},
    };
    let node = |arg:&'a SiteArg| match arg {
        SiteArg::Field(s)=>NodeRef::Site(s),
        SiteArg::Label(l)|SiteArg::NamedLabel {label:l,..}=>NodeRef::Label(l),
    };
    if sink.feature_sites() && site.value.args.iter().all(|arg|!matches!(arg,SiteArg::Label(_))) {
        sink.members(at,NodeRef::Site(site),&site.value.args,&[],node,|sink,at,arg|visit(sink,at,arg,0));
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
    key_and_inputs(sink, at, parent, instance.key.as_ref(), &instance.inputs);
}

/// Walks the key clause where the form has one, then `inputs`, children of
/// `parent`, the node at `at`.
fn key_and_inputs<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, parent: NodeRef<'a>, key: Option<&'a Node<KeyClause>>, inputs: &'a [Node<InstanceInput>]) {
    sink.option(key.is_some());
    if let Some(key) = key {
        sink.child(parent, NodeRef::KeyClause(key.value()), |sink| key_clause(sink, at, key.value()));
    }
    self::inputs(sink, at, parent, inputs);
}

fn inputs<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, parent: NodeRef<'a>, inputs: &'a [Node<InstanceInput>]) {
    sink.len(inputs.len());
    for (index, input) in inputs.iter().enumerate() {
        sink.child(parent, NodeRef::InstanceInput(input.value()), |sink| self::input(sink, at, index, input.value()));
    }
}

pub(super) fn key_clause<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, key: &'a KeyClause) {
    let at = sink.open(at, Tag::KeyClause, 0, Open::KeyClause);
    let parent = NodeRef::KeyClause(key);
    key_body(sink, at, parent, Tag::Key, &key.key);
    inputs(sink, at, parent, &key.inputs);
}

/// Walks `key`, whose body is a child of `parent`, the node at `at`.
pub(super) fn key_body<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, parent: NodeRef<'a>, role: Tag, key: &'a KeyBody) {
    let at = sink.open(at, role, 0, Open::KeyBody);
    let body = key.body.value();
    sink.child(parent, NodeRef::Body(body), |sink| self::body(sink, at, Tag::Body, 0, body));
    sink.columns(at, &key.columns, None);
}

pub(super) fn input<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, input: &'a InstanceInput) {
    let at = sink.open(at, Tag::Input, index, Open::Input(input));
    sink.len(input.head.len());
    for (index, site) in input.head.iter().enumerate() {
        let head = sink.open(at, Tag::Head, index, Open::Head);
        // A head site owns its own children, not the input's BODY/sibling
        // sites. Keep every recorded list anchored at that actual node.
        sink.child(NodeRef::InstanceInput(input),NodeRef::Site(site),|sink|self::site(sink, head, site, &[], None));
    }
    let body = input.body.value();
    sink.child(NodeRef::InstanceInput(input), NodeRef::Body(body), |sink| self::body(sink, at, Tag::Body, 0, body));
}

pub(super) fn choose<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, choose: &'a Choose) {
    let at = sink.open(at, Tag::Form, index, Open::Choose(choose));
    let parent = NodeRef::Choose(choose);
    sink.option(choose.rows.is_some());
    if let Some(rows) = &choose.rows {
        key_body(sink, at, parent, Tag::Key, rows);
    }
    sink.columns(at, &choose.candidate_columns, Some(&RelationRef::Declared(choose.name.clone())));
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
            key_body(sink, at, parent, role, key);
        }
    }
    sink.len(rigid.parts.len());
    for (index, part) in rigid.parts.iter().enumerate() {
        sink.child(parent, NodeRef::Atom(part.value()), |sink| self::atom(sink, at, Tag::Part, index, part.value(), false, false));
    }
}

pub(super) fn out<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, index: usize, out: &'a Out) {
    let at = sink.open(at, Tag::Form, index, Open::Out(out));
    key_body(sink, at, NodeRef::Out(out), Tag::Key, &out.key);
}

/// Walks the key clause and the inputs of `demonstrated`, below the node
/// at `at`.
pub(super) fn demonstrated_key<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, demonstrated: &'a Demonstrated) {
    key_and_inputs(sink, at, NodeRef::Demonstrated(demonstrated), demonstrated.key.as_ref(), &demonstrated.inputs);
}

pub(super) fn demo_rule<'a, S: ScopeSink<'a>>(sink: &mut S, at: S::At, rule: &'a DemoRule) {
    let at = sink.open(at, Tag::DemoRule, 0, Open::DemoRule(rule));
    sink.columns(at, &rule.fields, Some(&prediction()));
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
