//! The orientation algebra's values and relations: what each orientation
//! constant stands for in a frame, the D4 action on each orientation type,
//! and each relation of the algebra as its fact set, the tables of
//! [`super::tables`] and the relations computed from the D4 action: the
//! enumerations, `sym_member`, the group relations, `pose_difference`, and
//! the relation macros over orientation values alone.

use super::tables::OrientationTables;
use super::Algebra;
use crate::hash::StableHashMap;
use crate::registry::{LibName, Registry};
use crate::relations::RowSet;
use crate::terms::{Constant, OrientationConstant, OrientationType, ReachedMarginBound, Term, TermId};
use crate::types::ValueType;

/// An edge of a frame, in the order of a Box's margins (t, b, l, r).
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub enum Edge {
    Top,
    Bottom,
    Left,
    Right,
}

use Edge::{Bottom, Left, Right, Top};

impl Edge {
    pub const ALL: [Edge; 4] = [Top, Bottom, Left, Right];

    /// The edge across the frame from this one.
    pub fn opposite(self) -> Edge {
        match self {
            Top => Bottom,
            Bottom => Top,
            Left => Right,
            Right => Left,
        }
    }

    /// The next edge clockwise.
    fn clockwise(self) -> Edge {
        match self {
            Top => Right,
            Right => Bottom,
            Bottom => Left,
            Left => Top,
        }
    }

    fn bit(self) -> u8 {
        1 << self as u8
    }
}

/// A set of edges: those a Dir or a DiagDir points at.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Edges(u8);

impl Edges {
    pub fn of(edges: &[Edge]) -> Edges {
        Edges(edges.iter().fold(0, |bits, edge| bits | edge.bit()))
    }

    /// Whether `edge` is in the set.
    pub fn contains(self, edge: Edge) -> bool {
        self.0 & edge.bit() != 0
    }

    /// The edges outside the set.
    pub fn complement(self) -> Edges {
        Edges(!self.0 & 0b1111)
    }

    /// Each edge of the set.
    pub fn each(self) -> impl Iterator<Item = Edge> {
        Edge::ALL.into_iter().filter(move |&edge| self.contains(edge))
    }
}

/// An element of D4: the edge each edge of the frame goes to.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct D4Element([Edge; 4]);

impl D4Element {
    const IDENTITY: D4Element = D4Element(Edge::ALL);

    /// The edge `edge` goes to.
    pub fn image(self, edge: Edge) -> Edge {
        self.0[edge as usize]
    }

    fn image_of(self, edges: Edges) -> Edges {
        Edges(edges.each().fold(0, |bits, edge| bits | self.image(edge).bit()))
    }

    /// The element that applies `first`, then this one.
    fn after(self, first: D4Element) -> D4Element {
        D4Element(Edge::ALL.map(|edge| self.image(first.image(edge))))
    }

    fn inverse(self) -> D4Element {
        let mut inverse = Edge::ALL;
        for edge in Edge::ALL {
            inverse[self.image(edge) as usize] = edge;
        }
        D4Element(inverse)
    }

    /// Whether the element keeps the clockwise order of the edges.
    fn is_rotation(self) -> bool {
        self.image(Top.clockwise()) == self.image(Top).clockwise()
    }

    /// The element's place among the eight, from the image of the top edge
    /// and whether the element is a rotation, which together fix it.
    fn bit(self) -> u8 {
        1 << (2 * self.image(Top) as u8 + u8::from(self.is_rotation()))
    }
}

/// What an orientation constant stands for in a frame.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
enum Meaning {
    /// A Dir or a DiagDir: the edges it points at.
    Direction(Edges),
    /// An Axis or a DiagAxis: its two directions, each the bit of its
    /// edges' set.
    Axis(u16),
    Element(D4Element),
    Sense { clockwise: bool },
    /// A subgroup of D4: the bit of each member.
    Subgroup(u8),
}

impl Meaning {
    fn under(self, g: D4Element) -> Meaning {
        let conjugate = |x: D4Element| g.after(x).after(g.inverse());
        match self {
            Meaning::Direction(edges) => Meaning::Direction(g.image_of(edges)),
            Meaning::Axis(directions) => Meaning::Axis(
                (0..16u8).filter(|&e| directions & (1 << e) != 0).fold(0, |bits, e| bits | 1 << g.image_of(Edges(e)).0),
            ),
            Meaning::Element(x) => Meaning::Element(conjugate(x)),
            Meaning::Sense { clockwise } => Meaning::Sense { clockwise: clockwise == g.is_rotation() },
            Meaning::Subgroup(members) => Meaning::Subgroup(
                ELEMENTS.iter().map(|&(_, x)| x).filter(|x| members & x.bit() != 0).fold(0, |bits, x| bits | conjugate(x).bit()),
            ),
        }
    }
}

/// The directions, each by the edges it points at.
const DIRECTIONS: [(&str, &[Edge]); 8] = [
    ("DIR_T", &[Top]),
    ("DIR_B", &[Bottom]),
    ("DIR_L", &[Left]),
    ("DIR_R", &[Right]),
    ("DIAG_TL", &[Top, Left]),
    ("DIAG_TR", &[Top, Right]),
    ("DIAG_BL", &[Bottom, Left]),
    ("DIAG_BR", &[Bottom, Right]),
];

/// The axes, each by its two directions.
const AXES: [(&str, [&str; 2]); 4] = [
    ("AXIS_V", ["DIR_T", "DIR_B"]),
    ("AXIS_H", ["DIR_L", "DIR_R"]),
    ("DAXIS_DG", ["DIAG_TL", "DIAG_BR"]),
    ("DAXIS_AD", ["DIAG_TR", "DIAG_BL"]),
];

/// The D4 elements, each by the images of the edges t, b, l and r, as
/// `programs/lib_functors.cpp`'s `box_apply` moves the margins.
const ELEMENTS: [(&str, D4Element); 8] = [
    ("D4_ID", D4Element::IDENTITY),
    ("D4_CW", D4Element([Right, Left, Top, Bottom])),
    ("D4_HT", D4Element([Bottom, Top, Right, Left])),
    ("D4_CC", D4Element([Left, Right, Bottom, Top])),
    ("D4_LR", D4Element([Top, Bottom, Right, Left])),
    ("D4_TB", D4Element([Bottom, Top, Left, Right])),
    ("D4_DG", D4Element([Left, Right, Top, Bottom])),
    ("D4_AD", D4Element([Right, Left, Bottom, Top])),
];

const SENSES: [(&str, bool); 2] = [("SENSE_CW", true), ("SENSE_CC", false)];

/// The subgroups of D4, each by elements that generate it.
const SUBGROUPS: [(&str, &[&str]); 10] = [
    ("SYM_1", &[]),
    ("SYM_LR", &["D4_LR"]),
    ("SYM_TB", &["D4_TB"]),
    ("SYM_HT", &["D4_HT"]),
    ("SYM_DG", &["D4_DG"]),
    ("SYM_AD", &["D4_AD"]),
    ("SYM_BOX", &["D4_LR", "D4_TB"]),
    ("SYM_X", &["D4_DG", "D4_AD"]),
    ("SYM_C4", &["D4_CW"]),
    ("SYM_D4", &["D4_CW", "D4_LR"]),
];

fn element_named(name: &str) -> D4Element {
    ELEMENTS.iter().find(|(n, _)| *n == name).map(|&(_, x)| x).expect("a D4 element of `ELEMENTS`")
}

/// The meaning of the constant written `name`, or `None` where none of the
/// lists above gives one.
fn meaning_of(name: &str) -> Option<Meaning> {
    let direction = |name: &str| DIRECTIONS.iter().find(|(n, _)| *n == name).map(|&(_, edges)| Edges::of(edges));
    if let Some(edges) = direction(name) {
        return Some(Meaning::Direction(edges));
    }
    if let Some((_, directions)) = AXES.iter().find(|(n, _)| *n == name) {
        let bit = |d: &str| 1u16 << direction(d).expect("a direction of `DIRECTIONS`").0;
        return Some(Meaning::Axis(bit(directions[0]) | bit(directions[1])));
    }
    if let Some(&(_, x)) = ELEMENTS.iter().find(|(n, _)| *n == name) {
        return Some(Meaning::Element(x));
    }
    if let Some(&(_, clockwise)) = SENSES.iter().find(|(n, _)| *n == name) {
        return Some(Meaning::Sense { clockwise });
    }
    let (_, generators) = SUBGROUPS.iter().find(|(n, _)| *n == name)?;
    let mut members = vec![D4Element::IDENTITY];
    let mut grown = true;
    while grown {
        grown = false;
        for &generator in generators.iter() {
            for x in members.clone() {
                let product = element_named(generator).after(x);
                if !members.contains(&product) {
                    members.push(product);
                    grown = true;
                }
            }
        }
    }
    Some(Meaning::Subgroup(members.iter().fold(0, |bits, x| bits | x.bit())))
}

/// The orientation constants of the registry with their meanings, and the
/// constants of each orientation column type.
#[derive(Debug)]
pub struct Geometry {
    meanings: StableHashMap<TermId, (OrientationType, Meaning)>,
    constants: StableHashMap<(OrientationType, Meaning), TermId>,
    domains: StableHashMap<ValueType, Box<[TermId]>>,
}

fn term_id(constant: OrientationConstant) -> TermId {
    Term::Constant(Constant::Orientation(constant)).encode().expect("a constant's term id")
}

impl Geometry {
    /// The geometry of [`Registry::get`], built on first use.
    pub fn get() -> &'static Geometry {
        static GEOMETRY: std::sync::OnceLock<Geometry> = std::sync::OnceLock::new();
        GEOMETRY.get_or_init(|| Geometry::of(Registry::get()))
    }

    /// The geometry of `registry`'s constants. A constant that the lists of
    /// this module give no meaning is a fault of the engine's build, so this
    /// panics on one.
    pub fn of(registry: &Registry) -> Geometry {
        use OrientationType as O;
        let types = [O::Dir, O::DiagDir, O::Axis, O::DiagAxis, O::D4, O::Sym, O::Sense];
        let mut geometry =
            Geometry { meanings: StableHashMap::default(), constants: StableHashMap::default(), domains: StableHashMap::default() };
        for ty in types {
            for constant in registry.constants_of(ty).each() {
                let name = registry.constant_name(constant);
                let meaning = meaning_of(name).unwrap_or_else(|| panic!("no meaning of the orientation constant {name}"));
                geometry.meanings.insert(term_id(constant), (ty, meaning));
                geometry.constants.insert((ty, meaning), term_id(constant));
            }
        }
        let union = |of: &[O]| -> Box<[TermId]> { of.iter().flat_map(|&ty| registry.constants_of(ty).each()).map(term_id).collect() };
        let domains = [
            (ValueType::Dir, union(&[O::Dir])),
            (ValueType::DiagDir, union(&[O::DiagDir])),
            (ValueType::Dir8, union(&[O::Dir, O::DiagDir])),
            (ValueType::Axis, union(&[O::Axis])),
            (ValueType::DiagAxis, union(&[O::DiagAxis])),
            (ValueType::Axis4, union(&[O::Axis, O::DiagAxis])),
            (ValueType::D4, union(&[O::D4])),
            (ValueType::C4, registry.c4_constants().each().map(term_id).collect()),
            (ValueType::Sym, union(&[O::Sym])),
            (ValueType::Sense, union(&[O::Sense])),
        ];
        geometry.domains.extend(domains);
        geometry
    }

    /// The constants of `ty`, an orientation type or a Pose type, whose
    /// constants are D4's.
    pub fn domain(&self, ty: &ValueType) -> &[TermId] {
        let ty = if matches!(ty, ValueType::Pose(_)) { &ValueType::D4 } else { ty };
        self.domains.get(ty).unwrap_or_else(|| panic!("{ty:?} is no orientation type"))
    }

    /// The values of a column of type `ty`: `bound` where it is given, and
    /// otherwise each constant of `ty`.
    pub fn each(&self, bound: Option<TermId>, ty: &ValueType) -> impl Iterator<Item = TermId> + '_ {
        let all = if bound.is_some() { &[][..] } else { self.domain(ty) };
        bound.into_iter().chain(all.iter().copied())
    }

    fn meaning(&self, value: TermId) -> (OrientationType, Meaning) {
        *self.meanings.get(&value).expect("an orientation constant")
    }

    fn constant(&self, ty: OrientationType, meaning: Meaning) -> Option<TermId> {
        self.constants.get(&(ty, meaning)).copied()
    }

    /// The edges the Dir or DiagDir `value` points at.
    pub fn edges(&self, value: TermId) -> Edges {
        match self.meaning(value).1 {
            Meaning::Direction(edges) => edges,
            meaning => panic!("{meaning:?} is no direction"),
        }
    }

    /// The edge the Dir `value` points at.
    pub fn edge(&self, value: TermId) -> Edge {
        self.edges(value).each().next().expect("a Dir's edge")
    }

    /// The edge of the DiagDir `corner` on the Axis `axis`, where `on`, and
    /// otherwise its edge on the other axis.
    pub fn corner_edge(&self, corner: TermId, axis: TermId, on: bool) -> Edge {
        let edge = self.edges(corner).each().find(|&e| self.axis_edges(axis).contains(e) == on);
        edge.expect("a corner's edge on each axis")
    }

    /// The directions of the Axis or DiagAxis `value`, each by its edges.
    fn axis_directions(&self, value: TermId) -> impl Iterator<Item = Edges> {
        let directions = match self.meaning(value).1 {
            Meaning::Axis(directions) => directions,
            meaning => panic!("{meaning:?} is no axis"),
        };
        (0..16u8).filter(move |&e| directions & (1 << e) != 0).map(Edges)
    }

    /// The edges the directions of the Axis `value` point at.
    pub fn axis_edges(&self, value: TermId) -> Edges {
        Edges(self.axis_directions(value).fold(0, |bits, edges| bits | edges.0))
    }

    /// The directions of the axis perpendicular to the Axis or DiagAxis
    /// `value`, each by its edges.
    pub fn perpendicular_directions(&self, value: TermId) -> Vec<Edges> {
        let on: Vec<Edges> = self.axis_directions(value).collect();
        let kind = on[0].each().count();
        let directions = self.domain(&ValueType::Dir8).iter().map(|&d| self.edges(d));
        directions.filter(|e| e.each().count() == kind && !on.contains(e)).collect()
    }

    /// The D4 element `value` stands for.
    pub fn element(&self, value: TermId) -> D4Element {
        match self.meaning(value).1 {
            Meaning::Element(x) => x,
            meaning => panic!("{meaning:?} is no D4 element"),
        }
    }

    /// The Dir or DiagDir that points at `edges`, where the registry has one.
    pub fn direction(&self, edges: Edges) -> Option<TermId> {
        let ty = if edges.each().count() == 1 { OrientationType::Dir } else { OrientationType::DiagDir };
        self.constant(ty, Meaning::Direction(edges))
    }

    /// The image of `value` under `g`.
    pub fn under(&self, g: D4Element, value: TermId) -> TermId {
        let (ty, meaning) = self.meaning(value);
        self.constant(ty, meaning.under(g)).expect("the image of each constant is a constant of its type")
    }

    fn element_constant(&self, x: D4Element) -> TermId {
        self.constant(OrientationType::D4, Meaning::Element(x)).expect("each D4 element is a constant")
    }
}

/// A relation of the orientation algebra: its fact set.
#[derive(Debug)]
pub struct OrientationRelation {
    name: &'static str,
    rows: RowSet,
}

impl OrientationRelation {
    /// Each relation of the orientation algebra, by its registry name: each
    /// table of [`OrientationTables::get`], and each relation this module
    /// computes.
    pub fn all() -> impl Iterator<Item = (&'static LibName, &'static OrientationRelation)> {
        static RELATIONS: std::sync::OnceLock<StableHashMap<LibName, OrientationRelation>> = std::sync::OnceLock::new();
        RELATIONS
            .get_or_init(|| {
                let tables = OrientationTables::get();
                let computed = computed_relations(Registry::get(), Geometry::get());
                let read = tables.names().map(|name| (name.clone(), tables.rows(name).expect("a table's rows").clone()));
                computed
                    .into_iter()
                    .chain(read)
                    .map(|(name, rows)| {
                        let leaked: &'static str = Box::leak(name.0.clone());
                        (name, OrientationRelation { name: leaked, rows })
                    })
                    .collect()
            })
            .iter()
    }
}

impl Algebra for OrientationRelation {
    fn name(&self) -> &'static str {
        self.name
    }

    /// Each row of the fact set that agrees with `bound`. A fact set holds no
    /// Box, so this never reaches the margin bound.
    fn evaluate(
        &self,
        bound: &[Option<TermId>],
        _registry: &Registry,
        emit: &mut dyn FnMut(&[TermId]),
    ) -> Result<(), ReachedMarginBound> {
        for row in self.rows.rows() {
            if bound.iter().zip(row).all(|(b, value)| b.is_none_or(|b| b == *value)) {
                emit(row);
            }
        }
        Ok(())
    }
}

/// The relations of the orientation algebra that the D4 action gives, each
/// as its fact set, by its registry name.
fn computed_relations(registry: &Registry, geometry: &Geometry) -> Vec<(LibName, RowSet)> {
    let column_type = |name: &str, column: usize| -> ValueType {
        let declared = super::declaration(registry, name);
        declared.columns[column].ty.fixed().cloned().expect("a column of a fixed type")
    };
    let rows = |arity: u16, rows: Vec<Vec<TermId>>| {
        let mut set = RowSet::empty(arity);
        for row in rows {
            set.insert(row.into());
        }
        set
    };
    let elements = || geometry.domain(&ValueType::D4).iter().map(|&t| (t, geometry.element(t)));
    let mut relations = Vec::new();
    let enumerations = [
        "dir_elem",
        "axis_elem",
        "diag_dir_elem",
        "diag_axis_elem",
        "d4_elem",
        "c4_elem",
        "sense_elem",
        "sym_elem",
        "dir8_elem",
        "axis4_elem",
    ];
    for name in enumerations {
        let domain = geometry.domain(&column_type(name, 0));
        relations.push((name, rows(1, domain.iter().map(|&value| vec![value]).collect())));
    }
    let mut sym_member = Vec::new();
    for &s in geometry.domain(&ValueType::Sym) {
        let Meaning::Subgroup(members) = geometry.meaning(s).1 else { unreachable!("a Sym constant") };
        sym_member.extend(elements().filter(|(_, x)| members & x.bit() != 0).map(|(t, _)| vec![s, t]));
    }
    relations.push(("sym_member", rows(2, sym_member)));
    let mut compose = Vec::new();
    for (a, x) in elements() {
        for (b, y) in elements() {
            compose.push(vec![a, b, geometry.element_constant(x.after(y))]);
        }
    }
    relations.push(("d4_compose", rows(3, compose)));
    // The element that takes the placement at pose a onto the placement at
    // pose b, `docs/arclog/rigid.md#the-pose`: b is it after a.
    let mut difference = Vec::new();
    for (a, x) in elements() {
        for (b, y) in elements() {
            difference.push(vec![a, b, geometry.element_constant(y.after(x.inverse()))]);
        }
    }
    relations.push(("pose_difference", rows(3, difference)));
    relations.push(("d4_inverse", rows(2, elements().map(|(t, x)| vec![t, geometry.element_constant(x.inverse())]).collect())));
    relations.push(("d4_identity", rows(1, vec![vec![geometry.element_constant(D4Element::IDENTITY)]])));
    let dirs = geometry.domain(&ValueType::Dir);
    let mut perp_dir = Vec::new();
    for &d in dirs {
        for &d2 in dirs {
            if geometry.edge(d2) != geometry.edge(d) && geometry.edge(d2) != geometry.edge(d).opposite() {
                perp_dir.push(vec![d, d2]);
            }
        }
    }
    relations.push(("perp_dir", rows(2, perp_dir)));
    let mut diag_dirs = Vec::new();
    for &diag in geometry.domain(&ValueType::DiagDir) {
        for &a in geometry.domain(&ValueType::Axis) {
            let on_axis = |on: bool| {
                geometry.direction(Edges::of(&[geometry.corner_edge(diag, a, on)])).expect("a Dir of each edge")
            };
            diag_dirs.push(vec![diag, a, on_axis(true), on_axis(false)]);
        }
    }
    relations.push(("diag_dirs", rows(4, diag_dirs)));
    for (name, ty) in [("apply_dir", ValueType::Dir), ("apply_diag_dir", ValueType::DiagDir), ("apply_dir8", ValueType::Dir8)] {
        let mut applied = Vec::new();
        for (t, x) in elements() {
            for &d in geometry.domain(&ty) {
                applied.push(vec![t, d, geometry.under(x, d)]);
            }
        }
        relations.push((name, rows(3, applied)));
    }
    relations.into_iter().map(|(name, rows)| (LibName(name.into()), rows)).collect()
}
