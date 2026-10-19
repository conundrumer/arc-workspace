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
    pub(super) fn vertex_under(&mut self, parent: usize, role: Tag, index: usize, tag: Tag, color: impl FnOnce(&mut CanonicalWriter)) -> usize {
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

    fn open(&mut self, at: usize, role: Tag, index: usize, node: Open<'a>) -> usize {
        let names = self.names;
        match node {
            Open::Clause(clause) => self.vertex_under(at, role, index, Tag::Clause, |out| out.byte(clause.keyword as u8)),
            Open::Instance(_) => self.vertex_under(at, role, index, Tag::Instance, |_| {}),
            Open::Choose(choose) => self.vertex_under(at, role, index, Tag::Choose, |out| out.flag(choose.from_inside_for)),
            Open::RigidDet(_) => self.vertex_under(at, role, index, Tag::RigidDet, |_| {}),
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
            Open::Constraint(constraint) => self.vertex_under(at, role, index, Tag::Constraint, |out| out.byte(constraint.op as u8)),
            Open::Or => self.vertex_under(at, role, index, Tag::Or, |_| {}),
            Open::If => self.vertex_under(at, role, index, Tag::If, |_| {}),
            Open::All => self.vertex_under(at, role, index, Tag::All, |_| {}),
            Open::One(_) => self.vertex_under(at, role, index, Tag::One, |_| {}),
        }
    }

    fn child(&mut self, _parent: NodeRef<'a>, _child: NodeRef<'a>, visit: impl FnOnce(&mut Self)) {
        visit(self);
    }

    fn members<T>(&mut self, _parent: NodeRef<'a>, members: &'a [T], _node: impl Fn(&'a T) -> NodeRef<'a>, visit: impl Fn(&mut Self, &'a T)) {
        for member in members {
            visit(self, member);
        }
    }

    fn len(&mut self, _len: usize) {}

    fn option(&mut self, _present: bool) {}

    fn site(&mut self, _at: usize, _path: &[ColumnName], _args: usize, _relation: Option<&RelationRef>) {}

    /// An edge to the label, labeled by its column path as the name writer
    /// writes it and its index among the site's arguments. The path of a
    /// [`SiteArg::NamedLabel`] ends with its name.
    fn site_label(&mut self, at: usize, index: usize, path: &[ColumnName], named: Option<&ColumnName>, label: LabelUse, relation: Option<&RelationRef>) {
        let names = self.names;
        let path = match named {
            Some(name) => column_path(path, name),
            None => path.to_vec(),
        };
        self.label_use(at, label, |out| {
            site_column(names, relation, &path, out);
            out.len(index);
        });
    }

    fn site_field(&mut self) {}

    fn operand(&mut self, at: usize, index: usize, label: Option<ConstraintLabel>) {
        match label {
            Some(label) => {
                let to = self.label(label.label);
                self.edge(at, to, Tag::Part, |out| {
                    out.len(index);
                    out.flag(label.fresh);
                });
            }
            None => {
                let zero = self.vertex(Tag::Zero, |_| {});
                self.edge(at, zero, Tag::Part, |out| out.len(index));
            }
        }
    }

    fn one_label(&mut self, at: usize, index: usize, label: LabelId) {
        let to = self.label(label);
        self.edge(at, to, Tag::Part, |out| out.len(index));
    }

    /// An edge to the label of each column, labeled by the column's name as
    /// the name writer writes it.
    fn columns(&mut self, at: usize, columns: &'a [RelationColumn], relation: Option<&RelationRef>) {
        let names = self.names;
        for column in columns {
            let to = self.label(column.label);
            self.edge(at, to, Tag::Column, |out| relation_column(names, relation, &column.name, out));
        }
    }

    fn choose_from_inside_for(&mut self, _choose: &'a Choose) {}

    fn rule_text(&mut self, _rule: &'a DemoRule) {}

    /// A form of a scope of its own reads no label of the rule.
    fn own_scope(&mut self, _form: &'a Form) {}
}
