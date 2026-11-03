//! The graph of a label scope, which the labeling search refines: its
//! vertices and labeled edges, and their 1-dimensional Weisfeiler–Leman
//! color refinement.

use super::*;
use super::walk::{Open, ScopeSink};


/// The graph of a scope, as [`canonical_labeling`] refines it: a vertex per
/// atom, colored by its relation and its negation; a vertex per label; a
/// vertex per `0`; a vertex per `OR`, branch, `IF` part, `ALL` part, `NOT`
/// group, constraint and head site; and edges labeled by their role, an
/// atom's edge to a label by its column path as the name writer writes it.
pub(super) struct GraphBuilder<'n> {
    pub(super) names: &'n dyn NameWriter,
    feature_sites: bool,
    pub(super) colors: Vec<Vec<u8>>,
    pub(super) edges: Vec<(usize, usize, Vec<u8>)>,
    pub(super) labels: StableHashMap<LabelId, usize>,
    head_fields: HeadFields,
}

impl<'n> GraphBuilder<'n> {
    pub(super) fn new(names: &'n dyn NameWriter, feature_sites: bool) -> Self {
        GraphBuilder { names, feature_sites, colors: Vec::new(), edges: Vec::new(), labels: StableHashMap::default(), head_fields: HeadFields::default() }
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
    pub(super) fn vertex_under(&mut self, parent: usize, role: Tag, index: usize, tag: Tag, color: impl FnOnce(&mut CanonicalWriter)) -> usize {
        let vertex = self.vertex(tag, color);
        self.edge(parent, vertex, role, |out| out.len(index));
        vertex
    }

    pub(super) fn label_use(&mut self, from: usize, label: LabelUse, edge: impl FnOnce(&mut CanonicalWriter)) {
        let (to, mark) = match label {
            LabelUse::Fresh(id) | LabelUse::Join(id) => (self.label(id), Tag::Join),
            // As in `form::label_use`, the `^` moves with a reorder, so it is not part of the form: the key's columns hold it.
            LabelUse::Key(id) => (self.label(id), Tag::Join),
            LabelUse::Zero => (self.vertex(Tag::Zero, |_| {}), Tag::Zero),
        };
        self.edge(from, to, mark, edge);
    }

    /// The graph as numbers: each vertex's initial color, as its rank among
    /// the colors, and each vertex's edges, by the rank of their labels.
    pub(super) fn colored(self) -> ColoredGraph {
        let initial = ranks(self.colors.len(), |vertex| &self.colors[vertex]).0;
        let edge_ranks = ranks(self.edges.len(), |edge| &self.edges[edge].2).0;
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

/// The rank of each of `len` values, the value of index `i` being
/// `value(i)`, among the distinct values, and the number of distinct
/// values.
pub(super) fn ranks<T: Ord>(len: usize, value: impl Fn(usize) -> T) -> (Vec<u32>, u32) {
    let mut order: Vec<usize> = (0..len).collect();
    order.sort_unstable_by(|&a, &b| value(a).cmp(&value(b)));
    let mut ranks = vec![0; len];
    let mut rank = 0;
    for (index, &at) in order.iter().enumerate() {
        if index > 0 && value(at) != value(order[index - 1]) {
            rank += 1;
        }
        ranks[at] = rank;
    }
    (ranks, if len == 0 { 0 } else { rank + 1 })
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
    ///
    /// A vertex's new color is the rank of its signature among the distinct
    /// signatures, a signature being its color and the sorted list of its
    /// edges' labels, directions and far ends' colors. The signatures of a
    /// round stand in one buffer, at the span of each vertex's edges.
    pub(super) fn refine(&self, colors: &mut Vec<u32>) {
        let mut spans = Vec::with_capacity(self.edges.len());
        let mut start = 0;
        for edges in &self.edges {
            spans.push(start..start + edges.len());
            start += edges.len();
        }
        let mut around: Vec<(u32, bool, u32)> = Vec::with_capacity(start);
        let mut count = colors.iter().max().map_or(0, |c| c + 1);
        loop {
            around.clear();
            for (edges, span) in self.edges.iter().zip(&spans) {
                around.extend(edges.iter().map(|(label, inward, other)| (*label, *inward, colors[*other])));
                around[span.clone()].sort_unstable();
            }
            let (refined, refined_count) = ranks(colors.len(), |vertex| (colors[vertex], &around[spans[vertex].clone()]));
            *colors = refined;
            if refined_count == count {
                return;
            }
            count = refined_count;
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

/// The graph takes from the walk a vertex for each node it opens, under the
/// vertex of its parent, and an edge to a label for each label use.
impl<'a> ScopeSink<'a> for GraphBuilder<'_> {
    type At = usize;

    fn feature_sites(&self) -> bool { self.feature_sites }

    fn open(&mut self, at: usize, role: Tag, index: usize, node: Open<'a>) -> usize {
        let names = self.names;
        match node {
            Open::Clause(clause) => self.vertex_under(at, role, index, Tag::Clause, |out| out.byte(clause.keyword as u8)),
            Open::Instance(_) => {
                self.head_fields = HeadFields::default();
                self.vertex_under(at, role, index, Tag::Instance, |_| {})
            }
            Open::Choose(choose) => self.vertex_under(at, role, index, Tag::Choose, |out| out.flag(choose.from_inside_for)),
            Open::RigidDet(_) => self.vertex_under(at, role, index, Tag::RigidDet, |_| {}),
            Open::Out(_) => self.vertex_under(at, role, index, Tag::Out, |_| {}),
            // The fields and the forms of a rule stand at the vertex of its form.
            Open::DemoRule(_) => at,
            Open::KeyClause => self.vertex_under(at, role, index, Tag::KeyClause, |_| {}),
            Open::KeyBody => self.vertex_under(at, role, index, Tag::KeyBody, |_| {}),
            Open::Input(input) => self.vertex_under(at, role, index, Tag::Input, |out| out.text(&input.name.0)),
            Open::Head => self.vertex_under(at, role, index, Tag::Head, |_| {}),
            Open::Body => self.vertex_under(at, role, index, Tag::Body, |_| {}),
            Open::Atom { atom, negated, .. } => self.vertex_under(at, role, index, Tag::Atom, |out| {
                out.flag(negated);
                names.write_name(&atom.relation, out);
            }),
            Open::NotForm => self.vertex_under(at, role, index, Tag::NotForm, |_| {}),
            Open::Constraint(constraint) => self.vertex_under(at, role, index, Tag::Constraint, |out| out.byte(normalized_constraint(constraint).0 as u8)),
            Open::Or => self.vertex_under(at, role, index, Tag::Or, |_| {}),
            Open::If => self.vertex_under(at, role, index, Tag::If, |_| {}),
            Open::All => self.vertex_under(at, role, index, Tag::All, |_| {}),
        }
    }

    fn child(&mut self, _parent: NodeRef<'a>, _child: NodeRef<'a>, visit: impl FnOnce(&mut Self)) {
        visit(self);
    }

    fn members<T>(&mut self,at:usize,_parent: NodeRef<'a>, members: &'a [T],pinned:&[usize],repeats:&[usize], _node: impl Fn(&'a T) -> NodeRef<'a>, visit: impl Fn(&mut Self,usize, &'a T)) {
        for (index,member) in members.iter().enumerate().filter(|(index,_)|!repeats.contains(index)) {
            let at=match pinned.iter().position(|i|*i==index) {
                Some(rank)=>self.vertex_under(at,Tag::Part,rank,Tag::Part,|_|{}),None=>at,
            };
            visit(self,at,member);
        }
    }

    fn head_field(&mut self, port: &ColumnName, key: HeadKey) -> ColumnName {
        head_field(&mut self.head_fields, port, key)
    }

    fn len(&mut self, _len: usize) {}

    fn option(&mut self, _present: bool) {}

    fn atom_sites(&mut self, at: usize, _atom: &'a Atom, visit: impl Fn(&mut Self, usize)) {
        visit(self, at);
    }

    fn site(&mut self, _at: usize, _path: &[ColumnName], _args: usize, _relation: Option<&RelationRef>) {}

    /// An edge to the label, labeled by its column path as the name writer
    /// writes it, in the order of the columns of `relation` in which it
    /// writes the least bytes, and by its index among the site's arguments.
    /// So the graph is the same in each order of the columns that
    /// [`NameWriter::column_orders`] counts, and the form writer chooses the
    /// order at each atom. The path of a [`SiteArg::NamedLabel`] ends with
    /// its name.
    fn site_label(&mut self, at: usize, index: usize, path: &[ColumnName], named: Option<&ColumnName>, label: LabelUse, relation: Option<&RelationRef>) {
        let names = self.names;
        let feature_sites = self.feature_sites;
        let path = match named {
            Some(name) => column_path(path, name),
            None => path.to_vec(),
        };
        self.label_use(at, label, |out| {
            let orders = relation.map_or(0, |relation| names.column_orders(relation));
            let least = (0..=orders).map(|order| {
                let mut column = CanonicalWriter::default();
                site_column(names, relation, &path, order, &mut column);
                column.bytes
            }).min().expect("an order of the columns");
            out.write(&least);
            out.len(if feature_sites && named.is_some(){0}else{index});
        });
    }

    fn site_field(&mut self) {}

    fn operand(&mut self, at: usize, index: usize, label: Option<ConstraintLabel>) {
        match label {
            Some(label) => {
                let to = self.label(label.label);
                self.edge(at, to, Tag::Part, |out| out.len(index));
            }
            None => {
                let zero = self.vertex(Tag::Zero, |_| {});
                self.edge(at, zero, Tag::Part, |out| out.len(index));
            }
        }
    }

    fn constraint(&mut self,at:usize,constraint:&Constraint) {
        let (_,operands,symmetric)=normalized_constraint(constraint);
        for(i,label)in operands.into_iter().enumerate(){self.operand(at,if symmetric {0}else{i},label);}
    }

    /// A vertex for each distinct mark, with an edge to each of its labels,
    /// and no index on either.
    fn marks(&mut self, at: usize, ones: &'a [OneMark]) {
        for one in super::walk::distinct_marks(ones) {
            let mark = self.vertex_under(at, Tag::One, 0, Tag::One, |_| {});
            for label in one.key.iter() {
                let to = self.label(*label);
                self.edge(mark, to, Tag::Part, |out| out.len(0));
            }
        }
    }

    /// An edge to the label of each column, labeled by the column's name as
    /// the name writer writes it.
    fn columns(&mut self, at: usize, columns: &'a [RelationColumn], relation: Option<&RelationRef>, ordered: bool) {
        let names = self.names;
        for (index,column) in columns.iter().enumerate() {
            let to = self.label(column.label);
            self.edge(at, to, Tag::Column, |out| {relation_column(names, relation, &column.name, out);if relation.is_none() && ordered {out.len(index);}});
        }
    }

    fn choose_from_inside_for(&mut self, _choose: &'a Choose) {}

    fn rule_text(&mut self, _rule: &'a DemoRule) {}

    /// A form of a scope of its own reads no label of the rule.
    fn own_scope(&mut self, _form: &'a Form) {}
}
