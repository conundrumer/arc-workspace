//! The writer of an arclog file from its program and its layout. It walks
//! the nodes in the order the reader of `engine/arclog/src/read/arclog.rs`
//! reads them, and writes each token at the place its node's layout gives.
//! It holds the token output, [`Out`], through which each writer of the
//! module `write` writes its tokens, spaces and comments.

use crate::layout::{Comment, Layout, NodeLayout, SourceFile, SourcePlace};
use crate::program::path::NodePath;
use crate::program::*;
use crate::read::spelling::{self as sp, spelling};

/// The text written so far, with the line and column after it: the token
/// output of each writer of the module `write`.
pub(super) struct Out<'l> {
    text: String,
    line: u32,
    column: u32,
    /// The comments of the file not yet written, in source order.
    comments: Vec<&'l Comment>,
    after_open: bool,
}

impl<'l> Out<'l> {
    /// The output of `file`, which writes each comment of `layout` in it.
    pub(super) fn new(layout: &'l Layout, file: SourceFile) -> Self {
        let mut comments: Vec<&Comment> = layout.comments.iter().filter(|c| c.place.file == file).collect();
        comments.sort_by_key(|c| c.place.start);
        Out { text: String::new(), line: 1, column: 1, comments, after_open: false }
    }

    /// The text, ended at `end`, the place of the file's end, after each
    /// comment not yet written, or, where the layout gives no end, with a
    /// newline after them.
    pub(super) fn finish(mut self, end: Option<SourcePlace>, file: SourceFile) -> String {
        match end {
            Some(end) => {
                self.comments_before(SourcePlace { line: u32::MAX, ..end });
                self.move_to(end);
            }
            None => {
                self.comments_before(SourcePlace { file, start: 0, end: 0, line: u32::MAX, column: 0 });
                self.text.push('\n');
            }
        }
        self.text
    }

    /// Writes the next token of `tokens` as `text`.
    pub(super) fn next_token(&mut self, tokens: &mut Tokens, text: &str) {
        let place = tokens.places.get(tokens.next).copied();
        tokens.next += 1;
        self.token(place, text);
    }

    /// Moves to `place`: a newline per line it lies below, then a space per
    /// column it lies to the right.
    fn move_to(&mut self, place: SourcePlace) -> bool {
        if place.line > self.line {
            self.text.extend(std::iter::repeat_n('\n', (place.line - self.line) as usize));
            self.text.extend(std::iter::repeat_n(' ', place.column.saturating_sub(1) as usize));
        } else if place.line == self.line && place.column >= self.column {
            self.text.extend(std::iter::repeat_n(' ', (place.column - self.column) as usize));
        } else {
            return false;
        }
        self.line = place.line;
        self.column = place.column;
        true
    }

    /// Writes each comment that stands before `place`.
    fn comments_before(&mut self, place: SourcePlace) {
        while let Some(comment) = self.comments.first().copied() {
            if (comment.place.line, comment.place.column) >= (place.line, place.column) {
                break;
            }
            self.comments.remove(0);
            self.move_to(comment.place);
            self.put(&comment.text);
        }
    }

    fn put(&mut self, text: &str) {
        self.text.push_str(text);
        (self.line, self.column) = crate::read::line_column_after(text, self.line, self.column);
    }

    /// Writes `text` at `place`, or, where the layout gives no place, one
    /// space after the token before it, none after a `(` and none before a
    /// `)`.
    fn token(&mut self, place: Option<SourcePlace>, text: &str) {
        let placed = match place {
            Some(place) => {
                self.comments_before(place);
                self.move_to(place)
            }
            None => false,
        };
        if !placed && !self.text.is_empty() && !self.after_open && text != ")" {
            self.put(" ");
        }
        self.put(text);
        self.after_open = text == "(";
    }
}

/// The tokens of one node, each written at its place in the node's layout.
pub(super) struct Tokens<'l> {
    places: &'l [SourcePlace],
    next: usize,
}

impl<'l> Tokens<'l> {
    /// The tokens of the node at `path` of `file`, none where the layout
    /// holds no such node.
    pub(super) fn of(layout: &'l Layout, file: SourceFile, path: &NodePath) -> Self {
        Tokens { places: layout.node(file, path).map_or(&[], |n| &n.tokens), next: 0 }
    }

    /// The place of the node's first token, where its layout gives one.
    pub(super) fn first(&self) -> Option<SourcePlace> {
        self.places.first().copied()
    }
}

/// The labels of one scope by their names.
struct Names<'l>(&'l [(LabelId, Box<str>)]);

impl Names<'_> {
    fn name(&self, label: LabelId) -> &str {
        self.0
            .iter()
            .find(|(id, _)| *id == label)
            .map(|(_, name)| &**name)
            .expect("the layout of a label's scope names the label")
    }
}

struct Writer<'l> {
    layout: &'l Layout,
    out: Out<'l>,
}

fn declared(name: &DeclaredName) -> &str {
    match name {
        DeclaredName::Written(text) => text,
        DeclaredName::Slot(_) => panic!("the arclog writer writes names as a file writes them, and a slot has none"),
    }
}

fn column(name: &ColumnName) -> &str {
    match name {
        ColumnName::Written(text) => text,
        ColumnName::Slot(_) => panic!("the arclog writer writes columns as a file writes them, and a slot has none"),
    }
}

fn output_name(name: &OutputName) -> String {
    let mut text = match &name.of {
        OutputOwner::Instance(InstanceName(owner)) | OutputOwner::RigidDet(RigidDetName(owner)) => declared(owner).to_owned(),
    };
    for step in name.path.iter() {
        text.push('.');
        match step {
            OutputStep::Port(PortName(port)) => text.push_str(port),
            OutputStep::Part(part) => text.push_str(declared(part).trim_start_matches(sp::DECLARED_MARK)),
            OutputStep::Pose => text.push_str(sp::POSE),
        }
    }
    text
}

pub(super) fn program_relation(relation: &ProgramRelation) -> String {
    match relation {
        ProgramRelation::Declared(RelationName(name)) => declared(name).to_owned(),
        ProgramRelation::Output(name) => output_name(name),
    }
}

fn relation_ref(relation: &RelationRef) -> String {
    match relation {
        RelationRef::Fact(fact) => spelling(sp::FACT_RELATIONS, fact).to_owned(),
        RelationRef::Lib(crate::registry::LibName(name)) => name.to_string(),
        RelationRef::Declared(RelationName(name)) => declared(name).to_owned(),
        RelationRef::Output(name) => output_name(name),
        RelationRef::DefinedPort(PortName(port)) => format!("{}{port}", sp::SELF_PREFIX),
    }
}

pub(super) fn quoted(text: &str) -> String {
    format!("\"{}\"", text.replace('\\', "\\\\").replace('"', "\\\""))
}

fn label_use(label: LabelUse, names: &Names) -> String {
    match label {
        LabelUse::Fresh(id) => format!("{}{}", sp::FRESH_MARK, names.name(id)),
        LabelUse::Join(id) => names.name(id).to_owned(),
        LabelUse::Key(id) => format!("{}{}", sp::KEY_MARK, names.name(id)),
        LabelUse::Zero => sp::ZERO.to_owned(),
    }
}

fn constraint_label(label: ConstraintLabel, names: &Names) -> String {
    label_use(if label.fresh { LabelUse::Fresh(label.label) } else { LabelUse::Join(label.label) }, names)
}

impl<'l> Writer<'l> {
    fn node(&self, path: &NodePath) -> Option<&'l NodeLayout> {
        self.layout.node(SourceFile::Arclog, path)
    }

    fn tokens(&self, path: &NodePath) -> Tokens<'l> {
        Tokens::of(self.layout, SourceFile::Arclog, path)
    }

    fn put(&mut self, tokens: &mut Tokens, text: &str) {
        self.out.next_token(tokens, text);
    }

    fn names(&self, path: &NodePath) -> Names<'l> {
        Names(self.node(path).map_or(&[], |n| &n.label_names))
    }

    fn program(&mut self, program: &Program) {
        let root = NodePath::default();
        self.forms(&program.forms, &root, 0, None);
    }

    fn forms(&mut self, forms: &[Form], parent: &NodePath, first: u32, scope: Option<&Names>) {
        for (index, form) in forms.iter().enumerate() {
            self.form(form, &parent.child(first + index as u32), scope);
        }
    }

    fn form(&mut self, form: &Form, path: &NodePath, scope: Option<&Names>) {
        let own = self.names(path);
        let names = scope.unwrap_or(&own);
        let mut t = self.tokens(path);
        match form {
            Form::Claim(claim) => return self.claim(claim.value(), path),
            Form::Alts(alts) => return self.alts(alts.value(), path),
            _ => self.put(&mut t, "("),
        }
        match form {
            Form::Clause(clause) => self.clause(clause.value(), path, names, &mut t),
            Form::Instance(instance) => self.instance(instance.value(), path, names, &mut t),
            Form::Choose(choose) => self.choose(choose.value(), path, names, &mut t),
            Form::RigidDet(rigid) => self.rigid_det(rigid.value(), path, names, &mut t),
            Form::Demonstrated(demonstrated) => self.demonstrated(demonstrated.value(), path, names, &mut t),
            Form::Claim(_) | Form::Alts(_) => unreachable!("a claim and an `ALTS` form are written above"),
        }
        self.put(&mut t, ")");
    }

    fn claim(&mut self, claim: &Claim, path: &NodePath) {
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        self.put(&mut t, spelling(sp::CLAIM_KINDS, &claim.kind));
        self.put(&mut t, &claim.slug.0);
        self.put(&mut t, &quoted(&claim.text.0));
        if let Some(rule) = &claim.approximated {
            self.put(&mut t, "(");
            self.put(&mut t, sp::APPROXIMATED);
            self.put(&mut t, &quoted(&rule.0));
            self.put(&mut t, ")");
        }
        self.forms(&claim.forms, path, 0, None);
        self.put(&mut t, ")");
    }

    fn alts(&mut self, alts: &Alts, path: &NodePath) {
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        self.put(&mut t, sp::ALTS);
        self.put(&mut t, &alts.name.0);
        self.put(&mut t, &quoted(&alts.gloss.0));
        self.put(&mut t, &alts.concept.0);
        for (index, alt) in alts.alts.iter().enumerate() {
            self.alt(alt.value(), &path.child(index as u32));
        }
        self.put(&mut t, ")");
    }

    fn alt(&mut self, alt: &Alt, path: &NodePath) {
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        self.put(&mut t, sp::ALT);
        self.put(&mut t, &alt.name.0);
        for (index, item) in alt.items.iter().enumerate() {
            let child = path.child(index as u32);
            match item {
                AltItem::Form(form) => self.form(form, &child, None),
                AltItem::Alt(alt) => self.alt(alt.value(), &child),
            }
        }
        self.put(&mut t, ")");
    }

    fn clause(&mut self, clause: &Clause, path: &NodePath, names: &Names, t: &mut Tokens) {
        self.put(t, spelling(sp::CLAUSE_KEYWORDS, &clause.keyword));
        self.put(t, &program_relation(&clause.derives));
        if let Some(gloss) = &clause.gloss {
            self.put(t, &quoted(&gloss.0));
        }
        for proposer in clause.proposers.iter() {
            self.put(t, &proposer.0);
        }
        self.conjuncts(clause.body.value(), &path.child(0), names);
        for mark in clause.ones.iter() {
            self.put(t, "(");
            self.put(t, sp::ONE);
            for label in mark.key.iter() {
                self.put(t, names.name(*label));
            }
            self.put(t, ")");
        }
    }

    /// The conjuncts of a body that is not a list of its own.
    fn conjuncts(&mut self, body: &Body, path: &NodePath, names: &Names) {
        for (index, conjunct) in body.conjuncts.iter().enumerate() {
            self.conjunct(conjunct, &path.child(index as u32), names);
        }
    }

    /// A body written as one list of conjuncts.
    fn body_list(&mut self, body: &Body, path: &NodePath, names: &Names) {
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        self.conjuncts(body, path, names);
        self.put(&mut t, ")");
    }

    fn conjunct(&mut self, conjunct: &Conjunct, path: &NodePath, names: &Names) {
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        match conjunct {
            Conjunct::Atom(atom) => self.atom(atom.value(), path, names, &mut t),
            Conjunct::Not(negated) => {
                self.put(&mut t, sp::NOT);
                match negated {
                    Negated::Atom(atom) => {
                        self.put(&mut t, "(");
                        self.atom(atom.value(), path, names, &mut t);
                        self.put(&mut t, ")");
                    }
                    Negated::Form(form) => self.conjunct(form, &path.child(0), names),
                }
            }
            Conjunct::Constraint(constraint) => {
                self.put(&mut t, spelling(sp::CONSTRAINT_OPS, &constraint.op));
                self.put(&mut t, &constraint_label(constraint.first, names));
                let second = match constraint.second {
                    Operand::Label(label) => constraint_label(label, names),
                    Operand::Zero => sp::ZERO.to_owned(),
                };
                self.put(&mut t, &second);
            }
            Conjunct::Or(branches) => {
                self.put(&mut t, sp::OR);
                for (index, branch) in branches.iter().enumerate() {
                    self.body_list(branch.value(), &path.child(index as u32), names);
                }
            }
            Conjunct::If { test, then, otherwise } => {
                self.put(&mut t, sp::IF);
                for (index, body) in [test, then, otherwise].into_iter().enumerate() {
                    self.body_list(body.value(), &path.child(index as u32), names);
                }
            }
            Conjunct::All { domain, body } => {
                self.put(&mut t, sp::ALL);
                for (index, body) in [domain, body].into_iter().enumerate() {
                    self.body_list(body.value(), &path.child(index as u32), names);
                }
            }
        }
        self.put(&mut t, ")");
    }

    /// An atom's relation and its sites, the sites as the children of
    /// `path`, whose layout gives which the file elides.
    fn atom(&mut self, atom: &Atom, path: &NodePath, names: &Names, t: &mut Tokens) {
        self.put(t, &relation_ref(&atom.relation));
        self.sites(&atom.sites, path, names);
    }

    fn sites(&mut self, sites: &[Site], path: &NodePath, names: &Names) {
        let elided = self.node(path).map_or(&[][..], |n| &n.elided_sites);
        for (index, site) in sites.iter().enumerate() {
            self.site(site, &path.child(index as u32), names, elided.contains(&(index as u32)));
        }
    }

    fn site(&mut self, site: &Site, path: &NodePath, names: &Names, elided: bool) {
        let mut t = self.tokens(path);
        if elided {
            match &site.value.args[..] {
                [SiteArg::Label(label)] => return self.put(&mut t, &label_use(*label, names)),
                _ => panic!("the layout elides only a site of one label"),
            }
        }
        self.put(&mut t, "(");
        self.put(&mut t, &format!("{}{}", sp::COLUMN_MARK, column(&site.column)));
        for (index, arg) in site.value.args.iter().enumerate() {
            match arg {
                SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => self.put(&mut t, &label_use(*label, names)),
                SiteArg::Field(field) => self.site(field, &path.child(index as u32), names, false),
            }
        }
        self.put(&mut t, ")");
    }

    fn input(&mut self, input: &InstanceInput, path: &NodePath, names: &Names) {
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        self.put(&mut t, &input.name.0);
        self.put(&mut t, "(");
        self.sites(&input.head, path, names);
        self.put(&mut t, ")");
        self.conjuncts(input.body.value(), &path.child(input.head.len() as u32), names);
        self.put(&mut t, ")");
    }

    fn key_clause(&mut self, clause: &KeyClause, path: &NodePath, names: &Names) {
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        self.put(&mut t, sp::KEY);
        self.body_list(clause.key.body.value(), &path.child(0), names);
        for (index, input) in clause.inputs.iter().enumerate() {
            self.input(input.value(), &path.child(1 + index as u32), names);
        }
        self.put(&mut t, ")");
    }

    fn instance(&mut self, instance: &Instance, path: &NodePath, names: &Names, t: &mut Tokens) {
        self.put(t, sp::INIT);
        self.put(t, declared(&instance.name.0));
        self.put(t, &instance.component.0);
        if let Some(key) = &instance.key {
            self.key_clause(key.value(), &path.child(0), names);
        }
        let first = u32::from(instance.key.is_some());
        for (index, input) in instance.inputs.iter().enumerate() {
            self.input(input.value(), &path.child(first + index as u32), names);
        }
    }

    fn choose(&mut self, choose: &Choose, path: &NodePath, names: &Names, t: &mut Tokens) {
        self.put(t, sp::CHOOSE);
        self.put(t, declared(&choose.name.0));
        let mut next = 0;
        if let Some(rows) = &choose.rows {
            self.put(t, "(");
            self.put(t, sp::FOR);
            self.body_list(rows.body.value(), &path.child(next), names);
            next += 1;
        }
        let from_clause = |writer: &mut Self, t: &mut Tokens, next: u32| {
            writer.put(t, "(");
            writer.put(t, sp::FROM);
            writer.conjuncts(choose.from.value(), &path.child(next), names);
            writer.put(t, ")");
        };
        if choose.rows.is_some() {
            if choose.from_inside_for {
                from_clause(self, t, next);
                next += 1;
            }
            self.put(t, ")");
        }
        if !(choose.rows.is_some() && choose.from_inside_for) {
            from_clause(self, t, next);
            next += 1;
        }
        for never in choose.never.iter() {
            self.put(t, "(");
            self.put(t, sp::NEVER);
            self.conjuncts(never.value(), &path.child(next), names);
            next += 1;
            self.put(t, ")");
        }
    }

    fn rigid_det(&mut self, rigid: &RigidDet, path: &NodePath, names: &Names, t: &mut Tokens) {
        self.put(t, sp::RIGID_DET);
        self.put(t, declared(&rigid.name.0));
        let mut next = 0;
        let mut open = 0;
        for (head, clause) in [(sp::KEY, &rigid.key), (sp::INSTANCE, &rigid.instance)] {
            if let Some(clause) = clause {
                self.put(t, "(");
                self.put(t, head);
                self.body_list(clause.body.value(), &path.child(next), names);
                next += 1;
                open += 1;
            }
        }
        for (index, part) in rigid.parts.iter().enumerate() {
            let child = path.child(next + index as u32);
            let mut part_tokens = self.tokens(&child);
            self.put(&mut part_tokens, "(");
            self.atom(part.value(), &child, names, &mut part_tokens);
            self.put(&mut part_tokens, ")");
        }
        for _ in 0..open {
            self.put(t, ")");
        }
    }

    fn demonstrated(&mut self, demonstrated: &Demonstrated, path: &NodePath, names: &Names, t: &mut Tokens) {
        self.put(t, sp::DEMONSTRATED);
        self.put(t, declared(&demonstrated.name.0));
        if let Some(key) = &demonstrated.key {
            self.key_clause(key.value(), &path.child(0), names);
        }
        let mut next = u32::from(demonstrated.key.is_some());
        for input in demonstrated.inputs.iter() {
            self.input(input.value(), &path.child(next), names);
            next += 1;
        }
        for rule in demonstrated.rules.iter() {
            self.demo_rule(rule.value(), &path.child(next));
            next += 1;
        }
    }

    fn demo_rule(&mut self, rule: &DemoRule, path: &NodePath) {
        let names = self.names(path);
        let mut t = self.tokens(path);
        self.put(&mut t, "(");
        self.put(&mut t, sp::DEMO_RULE);
        if rule.fields.is_empty() {
            self.put(&mut t, &rule.name.0);
        } else {
            self.put(&mut t, "(");
            self.put(&mut t, &rule.name.0);
            for field in rule.fields.iter() {
                self.put(&mut t, &label_use(LabelUse::Fresh(field.label), &names));
            }
            self.put(&mut t, ")");
        }
        if let Some(text) = &rule.text {
            self.put(&mut t, &quoted(&text.0));
        }
        self.forms(&rule.forms, path, 0, Some(&names));
        self.put(&mut t, ")");
    }
}

pub(super) fn write(program: &Program, layout: &Layout) -> String {
    let mut writer = Writer { layout, out: Out::new(layout, SourceFile::Arclog) };
    writer.program(program);
    let end = writer.tokens(&NodePath::default()).first();
    writer.out.finish(end, SourceFile::Arclog)
}
