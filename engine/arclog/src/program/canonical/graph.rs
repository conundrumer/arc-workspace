//! The graph of a label scope, which the labeling search refines: its
//! vertices and labeled edges, and their 1-dimensional Weisfeiler–Leman
//! color refinement.

use super::*;


/// The graph of a scope, as [`canonical_labeling`] refines it: a vertex per
/// atom, colored by its relation and its negation; a vertex per label; a
/// vertex per `0`; a vertex per `OR`, branch, `IF` part, `ALL` part, `NOT`
/// group, constraint and head site; and edges labeled by their role, an
/// atom's edge to a label by its column path as the name writer writes it.
pub(super) struct GraphBuilder<'n> {
    pub(super) names: &'n dyn NameWriter,
    pub(super) colors: Vec<Vec<u8>>,
    pub(super) edges: Vec<(usize, usize, Vec<u8>)>,
    pub(super) labels: StableHashMap<LabelId, usize>,
}

impl<'n> GraphBuilder<'n> {
    pub(super) fn new(names: &'n dyn NameWriter) -> Self {
        GraphBuilder { names, colors: Vec::new(), edges: Vec::new(), labels: StableHashMap::default() }
    }

    pub(super) fn vertex(&mut self, tag: Tag, color: impl FnOnce(&mut CanonicalWriter)) -> usize {
        let mut out = CanonicalWriter::default();
        out.tag(tag);
        color(&mut out);
        self.colors.push(out.bytes);
        self.colors.len() - 1
    }

    pub(super) fn label(&mut self, label: LabelId) -> usize {
        if let Some(&vertex) = self.labels.get(&label) {
            return vertex;
        }
        let vertex = self.vertex(Tag::Label, |_| {});
        self.labels.insert(label, vertex);
        vertex
    }

    pub(super) fn edge(&mut self, from: usize, to: usize, tag: Tag, label: impl FnOnce(&mut CanonicalWriter)) {
        let mut out = CanonicalWriter::default();
        out.tag(tag);
        label(&mut out);
        self.edges.push((from, to, out.bytes));
    }

    /// A vertex of `tag` under `parent`, by an edge of `role` and `index`.
    pub(super) fn child(&mut self, parent: usize, role: Tag, index: usize, tag: Tag, color: impl FnOnce(&mut CanonicalWriter)) -> usize {
        let vertex = self.vertex(tag, color);
        self.edge(parent, vertex, role, |out| out.len(index));
        vertex
    }

    pub(super) fn label_use(&mut self, from: usize, label: LabelUse, edge: impl FnOnce(&mut CanonicalWriter)) {
        let (to, mark) = match label {
            LabelUse::Fresh(id) => (self.label(id), Tag::Fresh),
            LabelUse::Join(id) => (self.label(id), Tag::Join),
            LabelUse::Key(id) => (self.label(id), Tag::Key),
            LabelUse::Zero => (self.vertex(Tag::Zero, |_| {}), Tag::Zero),
        };
        self.edge(from, to, mark, edge);
    }

    pub(super) fn body(&mut self, body: &Body, parent: usize, role: Tag, index: usize) {
        let vertex = self.child(parent, role, index, Tag::Body, |_| {});
        for conjunct in body.conjuncts.iter() {
            self.conjunct(conjunct, vertex);
        }
    }

    pub(super) fn conjunct(&mut self, conjunct: &Conjunct, body: usize) {
        match conjunct {
            Conjunct::Atom(atom) => self.atom(atom.value(), false, body, Tag::Member, 0),
            Conjunct::Not(Negated::Atom(atom)) => self.atom(atom.value(), true, body, Tag::Member, 0),
            Conjunct::Not(Negated::Form(form)) => {
                let vertex = self.child(body, Tag::Member, 0, Tag::NotForm, |_| {});
                self.conjunct(form, vertex);
            }
            Conjunct::Constraint(constraint) => {
                let vertex = self.child(body, Tag::Member, 0, Tag::Constraint, |out| out.byte(constraint.op as u8));
                let first = constraint.first;
                let to = self.label(first.label);
                self.edge(vertex, to, Tag::Part, |out| {
                    out.len(0);
                    out.flag(first.fresh);
                });
                match constraint.second {
                    Operand::Label(second) => {
                        let to = self.label(second.label);
                        self.edge(vertex, to, Tag::Part, |out| {
                            out.len(1);
                            out.flag(second.fresh);
                        });
                    }
                    Operand::Zero => {
                        let zero = self.vertex(Tag::Zero, |_| {});
                        self.edge(vertex, zero, Tag::Part, |out| out.len(1));
                    }
                }
            }
            Conjunct::Or(branches) => {
                let vertex = self.child(body, Tag::Member, 0, Tag::Or, |_| {});
                for branch in branches.iter() {
                    self.body(branch.value(), vertex, Tag::Branch, 0);
                }
            }
            Conjunct::If { test, then, otherwise } => {
                let vertex = self.child(body, Tag::Member, 0, Tag::If, |_| {});
                for (index, part) in [test, then, otherwise].into_iter().enumerate() {
                    self.body(part.value(), vertex, Tag::Part, index);
                }
            }
            Conjunct::All { domain, body: each } => {
                let vertex = self.child(body, Tag::Member, 0, Tag::All, |_| {});
                for (index, part) in [domain, each].into_iter().enumerate() {
                    self.body(part.value(), vertex, Tag::Part, index);
                }
            }
        }
    }

    pub(super) fn atom(&mut self, atom: &Atom, negated: bool, parent: usize, role: Tag, index: usize) {
        let names = self.names;
        let vertex = self.child(parent, role, index, Tag::Atom, |out| {
            out.flag(negated);
            names.write_name(&atom.relation, out);
        });
        for site in atom.sites.iter() {
            self.site(vertex, site, &[], &|out, path| names.write_column(&atom.relation, path, out));
        }
    }

    /// The edges from `from` to the labels of `site`, each labeled by its
    /// column path as `column` writes it and its index among the site's
    /// arguments. The path of a [`SiteArg::NamedLabel`] ends with its name.
    pub(super) fn site(&mut self, from: usize, site: &Site, prefix: &[ColumnName], column: &dyn Fn(&mut CanonicalWriter, &[ColumnName])) {
        let path = column_path(prefix, &site.column);
        for (index, arg) in site.value.args.iter().enumerate() {
            match arg {
                SiteArg::Label(label) => self.label_use(from, *label, |out| {
                    column(out, &path);
                    out.len(index);
                }),
                SiteArg::NamedLabel { name, label } => self.label_use(from, *label, |out| {
                    column(out, &column_path(&path, name));
                    out.len(index);
                }),
                SiteArg::Field(field) => self.site(from, field, &path, column),
            }
        }
    }

    pub(super) fn input(&mut self, input: &InstanceInput, parent: usize, index: usize) {
        let vertex = self.child(parent, Tag::Input, index, Tag::Input, |out| out.text(&input.name.0));
        for (index, site) in input.head.iter().enumerate() {
            let head = self.child(vertex, Tag::Head, index, Tag::Head, |_| {});
            self.site(head, site, &[], &|out, path| out.column_path(path));
        }
        self.body(input.body.value(), vertex, Tag::Body, 0);
    }

    pub(super) fn key_body(&mut self, key: &KeyBody, parent: usize, role: Tag) {
        let vertex = self.child(parent, role, 0, Tag::KeyBody, |_| {});
        self.body(key.body.value(), vertex, Tag::Body, 0);
        self.columns(vertex, &key.columns, |out, name| out.column(name));
    }

    pub(super) fn key_clause(&mut self, key: &KeyClause, parent: usize) {
        let vertex = self.child(parent, Tag::KeyClause, 0, Tag::KeyClause, |_| {});
        self.key_body(&key.key, vertex, Tag::Key);
        for (index, input) in key.inputs.iter().enumerate() {
            self.input(input.value(), vertex, index);
        }
    }

    /// Edges from `from` to the labels of `columns`, each labeled by its
    /// name as `name` writes it.
    pub(super) fn columns(&mut self, from: usize, columns: &[RelationColumn], name: impl Fn(&mut CanonicalWriter, &ColumnName)) {
        for column in columns {
            let to = self.label(column.label);
            self.edge(from, to, Tag::Column, |out| name(out, &column.name));
        }
    }

    pub(super) fn clause(&mut self, clause: &Clause, parent: usize, index: usize) {
        let names = self.names;
        let derives = relation_of(&clause.derives);
        let vertex = self.child(parent, Tag::Form, index, Tag::Clause, |out| out.byte(clause.keyword as u8));
        self.body(clause.body.value(), vertex, Tag::Body, 0);
        for (index, one) in clause.ones.iter().enumerate() {
            let mark = self.child(vertex, Tag::One, index, Tag::One, |_| {});
            for (index, label) in one.key.iter().enumerate() {
                let to = self.label(*label);
                self.edge(mark, to, Tag::Part, |out| out.len(index));
            }
        }
        self.columns(vertex, &clause.columns, |out, name| names.write_column(&derives, std::slice::from_ref(name), out));
    }

    pub(super) fn instance(&mut self, instance: &Instance, parent: usize, index: usize) {
        let vertex = self.child(parent, Tag::Form, index, Tag::Instance, |_| {});
        if let Some(key) = &instance.key {
            self.key_clause(key.value(), vertex);
        }
        for (index, input) in instance.inputs.iter().enumerate() {
            self.input(input.value(), vertex, index);
        }
    }

    pub(super) fn choose(&mut self, choose: &Choose, parent: usize, index: usize) {
        let names = self.names;
        let relation = RelationRef::Declared(choose.name.clone());
        let vertex = self.child(parent, Tag::Form, index, Tag::Choose, |out| out.flag(choose.from_inside_for));
        if let Some(rows) = &choose.rows {
            self.key_body(rows, vertex, Tag::Key);
        }
        self.columns(vertex, &choose.candidate_columns, |out, name| names.write_column(&relation, std::slice::from_ref(name), out));
        self.body(choose.from.value(), vertex, Tag::Body, 0);
        for (index, never) in choose.never.iter().enumerate() {
            self.body(never.value(), vertex, Tag::Part, index);
        }
    }

    pub(super) fn rigid_det(&mut self, rigid: &RigidDet, parent: usize, index: usize) {
        let vertex = self.child(parent, Tag::Form, index, Tag::RigidDet, |_| {});
        if let Some(key) = &rigid.key {
            self.key_body(key, vertex, Tag::Key);
        }
        if let Some(instance) = &rigid.instance {
            self.key_body(instance, vertex, Tag::Instance);
        }
        for (index, part) in rigid.parts.iter().enumerate() {
            self.atom(part.value(), false, vertex, Tag::Part, index);
        }
    }

    pub(super) fn demonstrated_key(&mut self, demonstrated: &Demonstrated, parent: usize) {
        if let Some(key) = &demonstrated.key {
            self.key_clause(key.value(), parent);
        }
        for (index, input) in demonstrated.inputs.iter().enumerate() {
            self.input(input.value(), parent, index);
        }
    }

    pub(super) fn demo_rule(&mut self, rule: &DemoRule, parent: usize) {
        let names = self.names;
        let prediction = prediction();
        self.columns(parent, &rule.fields, |out, name| names.write_column(&prediction, std::slice::from_ref(name), out));
        // A form of a scope of its own reads no label of the rule.
        for (index, form) in rule.forms.iter().enumerate().filter(|(_, form)| shares_rule_scope(form)) {
            match form {
                Form::Clause(clause) => self.clause(clause.value(), parent, index),
                Form::Instance(instance) => self.instance(instance.value(), parent, index),
                Form::Choose(choose) => self.choose(choose.value(), parent, index),
                Form::RigidDet(rigid) => self.rigid_det(rigid.value(), parent, index),
                Form::Claim(_) | Form::Demonstrated(_) | Form::Alts(_) => {}
            }
        }
    }

    /// The graph as numbers: each vertex's initial color, as its rank among
    /// the colors, and each vertex's edges, by the rank of their labels.
    pub(super) fn colored(self) -> ColoredGraph {
        let initial = ranks(&self.colors);
        let edge_labels: Vec<Vec<u8>> = self.edges.iter().map(|(_, _, label)| label.clone()).collect();
        let edge_ranks = ranks(&edge_labels);
        let mut edges = vec![Vec::new(); self.colors.len()];
        for ((from, to, _), rank) in self.edges.iter().zip(edge_ranks) {
            edges[*from].push((rank, false, *to));
            edges[*to].push((rank, true, *from));
        }
        let mut labels: Vec<(LabelId, usize)> = self.labels.into_iter().collect();
        labels.sort_by_key(|(_, vertex)| *vertex);
        ColoredGraph { initial, edges, labels }
    }
}

/// The rank of each value among the distinct values of `values`.
pub(super) fn ranks<T: Ord + Clone>(values: &[T]) -> Vec<u32> {
    let mut distinct = values.to_vec();
    distinct.sort();
    distinct.dedup();
    values.iter().map(|v| distinct.binary_search(v).expect("a value of the list") as u32).collect()
}

/// A scope's graph as numbers, which the search refines.
pub(super) struct ColoredGraph {
    pub(super) initial: Vec<u32>,
    /// Each vertex's edges: the edge label's rank, whether the edge comes
    /// into the vertex, and the vertex at its other end.
    pub(super) edges: Vec<Vec<(u32, bool, usize)>>,
    /// Each label and its vertex.
    pub(super) labels: Vec<(LabelId, usize)>,
}

impl ColoredGraph {
    /// 1-dimensional Weisfeiler–Leman refinement of `colors`, to its fixed
    /// point. Each new color keeps the order of the old ones.
    pub(super) fn refine(&self, colors: &mut Vec<u32>) {
        let mut count = colors.iter().max().map_or(0, |c| c + 1);
        loop {
            let signatures: Vec<(u32, Vec<(u32, bool, u32)>)> = (0..colors.len())
                .map(|vertex| {
                    let mut around: Vec<(u32, bool, u32)> =
                        self.edges[vertex].iter().map(|(label, inward, other)| (*label, *inward, colors[*other])).collect();
                    around.sort();
                    (colors[vertex], around)
                })
                .collect();
            *colors = ranks(&signatures);
            let refined = colors.iter().max().map_or(0, |c| c + 1);
            if refined == count {
                return;
            }
            count = refined;
        }
    }

    /// The vertices of the first largest cell of labels that is not a
    /// singleton, or `None` where each label has a color of its own.
    pub(super) fn target_cell(&self, colors: &[u32]) -> Option<Vec<usize>> {
        let mut cells: std::collections::BTreeMap<u32, Vec<usize>> = std::collections::BTreeMap::new();
        for (_, vertex) in &self.labels {
            cells.entry(colors[*vertex]).or_default().push(*vertex);
        }
        let largest = cells.values().map(Vec::len).max().filter(|&size| size > 1)?;
        cells.into_values().find(|cell| cell.len() == largest)
    }

    /// The labels' positions at a leaf, in the order of their colors.
    pub(super) fn leaf_labels(&self, colors: &[u32]) -> Labels {
        let mut ordered: Vec<(u32, LabelId)> = self.labels.iter().map(|(label, vertex)| (colors[*vertex], *label)).collect();
        ordered.sort_by_key(|(color, _)| *color);
        ordered.into_iter().enumerate().map(|(position, (_, label))| (label, position as u32)).collect()
    }
}

impl LabelScope<'_> {
    pub(super) fn graph(self, graph: &mut GraphBuilder, root: usize) {
        match self {
            LabelScope::Clause(clause) => graph.clause(clause, root, 0),
            LabelScope::Instance(instance) => graph.instance(instance, root, 0),
            LabelScope::Choose(choose) => graph.choose(choose, root, 0),
            LabelScope::RigidDet(rigid) => graph.rigid_det(rigid, root, 0),
            LabelScope::DemonstratedKey(demonstrated) => graph.demonstrated_key(demonstrated, root),
            LabelScope::DemoRule(rule) => graph.demo_rule(rule, root),
            LabelScope::Body(body) => graph.body(body, root, Tag::Body, 0),
            LabelScope::Atom(atom) => graph.atom(atom, false, root, Tag::Part, 0),
            LabelScope::KeyClause(key) => graph.key_clause(key, root),
            LabelScope::InstanceInput(input) => graph.input(input, root, 0),
        }
    }
}
