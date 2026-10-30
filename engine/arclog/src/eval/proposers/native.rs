//! The native proposers: one function per proposer that the registry marks
//! `native`, chosen by the proposer's name, each over the grids of an
//! evidence. The type-domain proposers give the values of their columns' types
//! that `docs/engine/determination.md#proposers` gives; each other proposer
//! is the port of its component in `programs/proposers.dl`, whose
//! `propose` relation gives its rows.
//!
//! An example of the evidence is a train pair or an input alone. A claim of
//! a component that is uniform over a scope, its `Uniform` child, holds the
//! rows that every example of the scope holds, as [`uniform`] gives: the
//! scope is the inputs where the claim reads inputs alone, and the train
//! pairs where it reads outputs.

use crate::algebra::boxes::apply;
use crate::algebra::geometry::{self, Edge, Geometry};
use crate::hash::StableHashSet;
use crate::program::ColumnName;
use crate::registry::{ColumnType, Proposer, Registry};
use crate::relations::RowSet;
use crate::session::TaskSession;
use crate::task::Grid;
use crate::terms::{Color, Constant, Content, Margins, MemberSet, OrientationConstant, OrientationType, Term, TermId};
use crate::types::ValueType;

/// The grids of an evidence: each input, and each train pair, whose input
/// is the input of the same index.
pub(super) struct Grids<'t> {
    pub(super) inputs: Vec<&'t Grid>,
    pub(super) pairs: Vec<(&'t Grid, &'t Grid)>,
}

/// What a native proposer reads beside the grids: the registry, for the
/// proposer's columns and the orientation constants, and the task session,
/// whose intern table holds the Idents its rows hold.
pub(super) struct Context<'a> {
    pub(super) registry: &'a Registry,
    pub(super) session: &'a TaskSession,
}

type Row = Box<[TermId]>;
type Rows = StableHashSet<Row>;

/// The rows of the native proposer `name`, whose declaration is `proposer`,
/// over `grids`, or `None` where no function of this module ports it.
pub(super) fn rows(name: &str, proposer: &Proposer, grids: &Grids<'_>, context: &Context<'_>) -> Option<RowSet> {
    let axes = Axes::of(context.registry);
    let rows: Rows = match name {
        "AxisDomain" | "ColorDomain" | "D4Domain" | "DiagAxisDomain" | "DiagDirDomain" | "DirDomain" | "NumberDomain"
        | "SenseDomain" | "SymDomain" | "ColorColorDomain" | "DiagDirAxisDomain" | "NumberDirDomain" => {
            domain(proposer, grids, context.registry)
        }
        "DominantColor" => count_extreme_colors(grids, Extreme::High),
        "RarestColor" => count_extreme_colors(grids, Extreme::Low),
        "ScaleRatio" => last(&ratios(grids, &axes, Ratio::Scale)),
        "ScaleRatioAxis" => ratios(grids, &axes, Ratio::Scale),
        "DivisorRatio" => last(&ratios(grids, &axes, Ratio::Divisor)),
        "DivisorRatioAxis" => ratios(grids, &axes, Ratio::Divisor),
        "DimDiff" => last(&dim_diff(grids, &axes)),
        "TileCount" => last(&fit_claim(grids, &axes, Tiling::Any, |fit| fit.count)),
        "TileDim" => last(&fit_claim(grids, &axes, Tiling::Any, |fit| fit.dim)),
        "Period" => period(grids, &axes),
        "SepTileCount" => last(&fit_claim(grids, &axes, Tiling::Separated, |fit| fit.count)),
        "SepTileCountAxis" => sep_tile_count_axis(grids, &axes),
        "SepTileDim" => last(&fit_claim(grids, &axes, Tiling::Separated, |fit| fit.dim)),
        "SepThickness" => last(&fit_claim(grids, &axes, Tiling::Separated, |fit| fit.gap)),
        "CountRankAsc" => count_rank(grids, Extreme::Low),
        "CountRankDesc" => count_rank(grids, Extreme::High),
        "TileD4" => tile_d4(grids, context.registry),
        "PanelCombine" => panel_combine(grids, &axes, context.session),
        _ => return None,
    };
    let mut set = RowSet::empty(proposer.columns.len() as u16);
    for row in rows {
        set.insert(row);
    }
    Some(set)
}

/// The rows that each set of `holds` holds: the claim of a `Uniform` child
/// over a scope of one set per example, none where the scope is empty.
fn uniform(holds: Vec<Rows>) -> Rows {
    let mut sets = holds.into_iter();
    let Some(first) = sets.next() else { return Rows::default() };
    sets.fold(first, |kept, set| kept.into_iter().filter(|row| set.contains(row)).collect())
}

/// The last column of each row: the value of a claim, with its claim
/// parameter dropped.
fn last(rows: &Rows) -> Rows {
    rows.iter().map(|row| Box::from(&row[row.len() - 1..])).collect()
}

fn number(n: i32) -> TermId {
    Term::encode_number(n)
}

fn count(n: usize) -> TermId {
    Term::encode_count(n)
}

fn color(color: Color) -> TermId {
    Term::Constant(Constant::Color(color)).encode().expect("a color's term id")
}

fn orientation(constant: OrientationConstant) -> TermId {
    Term::Constant(Constant::Orientation(constant)).encode().expect("a constant's term id")
}

fn position(margins: Margins) -> TermId {
    Term::Box(margins).encode().expect("a cell's margins lie within a byte")
}

fn height(grid: &Grid) -> usize {
    grid.rows().len()
}

fn width(grid: &Grid) -> usize {
    grid.rows()[0].len()
}

/// Each cell of `grid`: its row, its column and its color.
fn cells(grid: &Grid) -> impl Iterator<Item = (usize, usize, Color)> + '_ {
    grid.rows().iter().enumerate().flat_map(|(r, row)| row.iter().enumerate().map(move |(c, &color)| (r, c, color)))
}

/// An axis of a frame, with the term id of its constant.
#[derive(Clone, Copy)]
struct Axis {
    vertical: bool,
    term: TermId,
}

impl Axis {
    fn extent(self, grid: &Grid) -> usize {
        if self.vertical { height(grid) } else { width(grid) }
    }

    /// The line across this axis at index `index` along it: a row for the
    /// vertical axis, a column for the horizontal one.
    fn line(self, grid: &Grid, index: usize) -> Vec<Color> {
        if self.vertical { grid.rows()[index].to_vec() } else { grid.rows().iter().map(|row| row[index]).collect() }
    }

    /// The position of a frame of `count` cells along this axis and one
    /// across it, of its cell at `index`.
    fn place(self, index: usize, count: usize) -> Margins {
        let (near, far) = (index as i32, (count - 1 - index) as i32);
        if self.vertical {
            Margins { top: near, bottom: far, left: 0, right: 0 }
        } else {
            Margins { top: 0, bottom: 0, left: near, right: far }
        }
    }
}

/// The two axes, vertical first, by the registry's constants.
struct Axes([Axis; 2]);

impl Axes {
    fn of(registry: &Registry) -> Axes {
        let term = |name: &str| orientation(registry.orientation_constant(name).expect("the registry declares the axis constants"));
        Axes([Axis { vertical: true, term: term("AXIS_V") }, Axis { vertical: false, term: term("AXIS_H") }])
    }

    fn each(&self) -> impl Iterator<Item = Axis> + '_ {
        self.0.iter().copied()
    }

    fn perpendicular(&self, axis: Axis) -> Axis {
        self.0[usize::from(axis.vertical)]
    }
}

/// A type-domain proposer: the product of the domains of its columns' types,
/// each as `docs/engine/determination.md#proposers` gives it.
fn domain(proposer: &Proposer, grids: &Grids<'_>, registry: &Registry) -> Rows {
    let all = || grids.inputs.iter().copied().chain(grids.pairs.iter().map(|(_, output)| *output));
    let columns: Vec<Vec<TermId>> = proposer
        .columns
        .iter()
        .map(|column| match &column.ty {
            ColumnType::Fixed(ValueType::Color) => {
                let colors: StableHashSet<TermId> = all().flat_map(|grid| cells(grid).map(|(_, _, c)| color(c))).collect();
                colors.into_iter().collect()
            }
            ColumnType::Fixed(ValueType::Int | ValueType::Nat) => {
                let largest = all().map(|grid| height(grid).max(width(grid))).max();
                largest.map_or_else(Vec::new, |largest| (0..=largest).map(count).collect())
            }
            ColumnType::Fixed(ty) => geometry::domain(registry, ty).expect("a type-domain proposer's column of an orientation type"),
            other => panic!("a type-domain proposer's column of the type {other:?}"),
        })
        .collect();
    columns.iter().fold(std::iter::once(Vec::new()).collect::<Vec<Vec<TermId>>>(), |rows, values| {
        rows.iter().flat_map(|row| values.iter().map(move |&value| row.iter().copied().chain([value]).collect())).collect()
    })
    .into_iter()
    .map(Vec::into_boxed_slice)
    .collect()
}

/// The end of an order that a proposer reads.
#[derive(Clone, Copy, PartialEq)]
enum Extreme {
    High,
    Low,
}

/// The cell count of each color of `grid`.
fn color_counts(grid: &Grid) -> Vec<(Color, usize)> {
    let mut counts: Vec<(Color, usize)> = Vec::new();
    for (_, _, c) in cells(grid) {
        match counts.iter_mut().find(|(other, _)| *other == c) {
            Some((_, n)) => *n += 1,
            None => counts.push((c, 1)),
        }
    }
    counts
}

/// `DominantColor` and `RarestColor`: each color whose cell count is the
/// `extreme` of its input's color counts, in every input.
fn count_extreme_colors(grids: &Grids<'_>, extreme: Extreme) -> Rows {
    let holds = grids.inputs.iter().map(|grid| {
        let counts = color_counts(grid);
        let counts_of = counts.iter().map(|(_, n)| *n);
        let at = if extreme == Extreme::High { counts_of.max() } else { counts_of.min() };
        counts.iter().filter(|(_, n)| Some(*n) == at).map(|(c, _)| Box::from([color(*c)])).collect()
    });
    uniform(holds.collect())
}

/// `CountRankAsc` and `CountRankDesc`: each color with its rank in its
/// input, the count of the colors whose cell count lies toward `extreme`
/// of its own, in every input.
fn count_rank(grids: &Grids<'_>, before: Extreme) -> Rows {
    let holds = grids.inputs.iter().map(|grid| {
        let counts = color_counts(grid);
        let precedes = |n2: usize, n: usize| if before == Extreme::Low { n2 < n } else { n2 > n };
        counts
            .iter()
            .map(|&(c, n)| Box::from([color(c), count(counts.iter().filter(|&&(_, n2)| precedes(n2, n)).count())]))
            .collect()
    });
    uniform(holds.collect())
}

/// Which of a pair's two extents divides the other.
#[derive(Clone, Copy, PartialEq)]
enum Ratio {
    /// The output's extent is a whole number of times the input's.
    Scale,
    /// The input's extent is a whole number of times the output's.
    Divisor,
}

/// The claim of `ScaleRatioClaim` or `DivisorRatioClaim`: each axis with
/// the whole number of times one extent of every pair is the other.
fn ratios(grids: &Grids<'_>, axes: &Axes, ratio: Ratio) -> Rows {
    let holds = grids.pairs.iter().map(|(input, output)| {
        axes.each()
            .filter_map(|axis| {
                let (of, by) = match ratio {
                    Ratio::Scale => (axis.extent(output), axis.extent(input)),
                    Ratio::Divisor => (axis.extent(input), axis.extent(output)),
                };
                (of % by == 0).then(|| Box::from([axis.term, count(of / by)]))
            })
            .collect()
    });
    uniform(holds.collect())
}

/// The claim of `DimDiff`: each axis with the difference, where positive,
/// of every pair's two extents on it.
fn dim_diff(grids: &Grids<'_>, axes: &Axes) -> Rows {
    let holds = grids.pairs.iter().map(|(input, output)| {
        axes.each()
            .filter_map(|axis| {
                let (i, o) = (axis.extent(input), axis.extent(output));
                (i != o).then(|| Box::from([axis.term, count(i.abs_diff(o))]))
            })
            .collect()
    });
    uniform(holds.collect())
}

/// A tiling that fits an axis of an input: `count` tiles of extent `dim`,
/// with a gap of `gap` between each two, as `TileFits` gives them.
#[derive(Clone, Copy)]
struct Fit {
    count: usize,
    dim: usize,
    gap: usize,
}

/// The tilings a proposer reads: those of `TileFits`, or those of
/// `SepFits`, whose gap is positive and whose every line of more than one
/// color lies in a tile.
#[derive(Clone, Copy, PartialEq)]
enum Tiling {
    Any,
    Separated,
}

/// The tilings of `tiling` that fit `axis` of `grid`, over counts 2 to 8
/// and gaps 0 to 3.
fn fits(grid: &Grid, axis: Axis, tiling: Tiling) -> Vec<Fit> {
    let extent = axis.extent(grid);
    let all = (2..=8).flat_map(|count| (0..=3).map(move |gap| (count, gap))).filter_map(|(count, gap)| {
        let rest = extent.checked_sub((count - 1) * gap).filter(|&rest| rest > 0)?;
        (rest % count == 0).then_some(Fit { count, dim: rest / count, gap })
    });
    match tiling {
        Tiling::Any => all.collect(),
        Tiling::Separated => {
            let multi: Vec<usize> = (0..extent)
                .filter(|&index| {
                    let line = axis.line(grid, index);
                    line.iter().any(|&c| c != line[0])
                })
                .collect();
            all.filter(|fit| fit.gap > 0 && multi.iter().all(|&index| index % (fit.dim + fit.gap) < fit.dim)).collect()
        }
    }
}

/// The claim over the tilings of `tiling`: each axis with the `field` of
/// a tiling that fits it, in every input.
fn fit_claim(grids: &Grids<'_>, axes: &Axes, tiling: Tiling, field: fn(&Fit) -> usize) -> Rows {
    uniform(fit_holds(grids, axes, tiling, field))
}

fn fit_holds(grids: &Grids<'_>, axes: &Axes, tiling: Tiling, field: fn(&Fit) -> usize) -> Vec<Rows> {
    let holds = grids.inputs.iter().map(|grid| {
        axes.each().flat_map(|axis| fits(grid, axis, tiling).into_iter().map(move |fit| Box::from([axis.term, count(field(&fit))]))).collect()
    });
    holds.collect()
}

/// `SepTileCountAxis`: the claim of `SepTileCount` with its axis, and, for
/// the axis across a claimed one, a count of 1 where no input has a
/// separated tiling on it.
fn sep_tile_count_axis(grids: &Grids<'_>, axes: &Axes) -> Rows {
    let holds = fit_holds(grids, axes, Tiling::Separated, |fit| fit.count);
    let held_on = |axis: Axis| holds.iter().any(|rows| rows.iter().any(|row| row[0] == axis.term));
    let mut rows = uniform(holds.clone());
    let across: Vec<Axis> = axes.each().filter(|&axis| rows.iter().any(|row| row[0] == axis.term)).map(|axis| axes.perpendicular(axis)).collect();
    for axis in across {
        if !held_on(axis) {
            rows.insert(Box::from([axis.term, count(1)]));
        }
    }
    rows
}

/// `Period`: on each axis, the least shift under which every input repeats
/// along it, where both cells exist.
fn period(grids: &Grids<'_>, axes: &Axes) -> Rows {
    let holds = grids.inputs.iter().map(|grid| {
        let cell = |r: usize, c: usize| grid.rows()[r][c];
        axes.each()
            .flat_map(|axis| {
                let extent = axis.extent(grid);
                (1..extent).filter(move |&k| {
                    cells(grid).all(|(r, c, color)| {
                        let (r2, c2) = if axis.vertical { (r + k, c) } else { (r, c + k) };
                        r2 >= height(grid) || c2 >= width(grid) || cell(r2, c2) == color
                    })
                })
                .map(move |k| Box::from([axis.term, count(k)]))
            })
            .collect()
    });
    let uniform = uniform(holds.collect());
    axes.each()
        .filter_map(|axis| {
            uniform.iter().filter(|row| row[0] == axis.term).map(|row| Term::decode_number(row[1])).min().map(|k| Box::from([number(k)]))
        })
        .collect()
}

/// `TileD4`: each tile of an arrangement of copies of the input that every
/// pair's output is, with each D4 transform of the input that gives that
/// tile in every pair.
fn tile_d4(grids: &Grids<'_>, registry: &Registry) -> Rows {
    let geometry = Geometry::get();
    let transforms: Vec<(TermId, geometry::D4Element)> = registry
        .constants_of(OrientationType::D4)
        .each()
        .map(|constant| (orientation(constant), geometry.element(orientation(constant))))
        .collect();
    let holds = grids.pairs.iter().map(|(input, output)| {
        let (hi, wi, ho, wo) = (height(input), width(input), height(output), width(output));
        let mut rows = Rows::default();
        if ho % hi != 0 || wo % wi != 0 || ho * wo == hi * wi {
            return rows;
        }
        let (nv, nh) = (ho / hi, wo / wi);
        for (tr, tc) in (0..nv).flat_map(|tr| (0..nh).map(move |tc| (tr, tc))) {
            let tile = Margins { top: tr as i32, bottom: (nv - 1 - tr) as i32, left: tc as i32, right: (nh - 1 - tc) as i32 };
            for &(term, element) in &transforms {
                let swaps = matches!(element.image(Edge::Top), Edge::Left | Edge::Right);
                if swaps && hi != wi {
                    continue;
                }
                let gives = cells(input).all(|(r, c, color)| {
                    let at = crate::task::cell_position(r, c, hi, wi);
                    let image = apply(element, at);
                    let (r2, c2) = (tr * hi + image.top as usize, tc * wi + image.left as usize);
                    output.rows()[r2][c2] == color
                });
                if gives {
                    rows.insert(Box::from([position(tile), term]));
                }
            }
        }
        rows
    });
    uniform(holds.collect())
}

/// `PanelCombine`: each pair whose input is two panels along an axis, each
/// of the output's frame, gives for each output cell an entry of the two
/// panel cells aligned with it and its own color. An entry is one Ident,
/// the set of its panels, each with its place in the arrangement's frame,
/// its cell's color and the entry's output color; it has one row for each
/// panel.
fn panel_combine(grids: &Grids<'_>, axes: &Axes, session: &TaskSession) -> Rows {
    let mut entries: StableHashSet<(bool, Color, Color, Color)> = StableHashSet::default();
    for (input, output) in &grids.pairs {
        for axis in axes.each() {
            let across = axes.perpendicular(axis);
            let (di, d) = (axis.extent(input), axis.extent(output));
            if across.extent(input) != across.extent(output) || di < 2 * d {
                continue;
            }
            let gap = di - 2 * d;
            for (r, c, out) in cells(output) {
                let (panel0, panel1) = if axis.vertical { ((r, c), (r + d + gap, c)) } else { ((r, c), (r, c + d + gap)) };
                let at = |(r, c): (usize, usize)| input.rows()[r][c];
                entries.insert((axis.vertical, at(panel0), at(panel1), out));
            }
        }
    }
    let member = ValueType::Record(Box::new([
        (ColumnName::Written("P".into()), ValueType::Position),
        (ColumnName::Written("C".into()), ValueType::Color),
        (ColumnName::Written("C_out".into()), ValueType::Color),
    ]));
    let mut table = session.intern.write().expect("an intern table that no panic poisoned");
    let mut rows = Rows::default();
    for (vertical, c1, c2, out) in entries {
        let axis = axes.each().find(|axis| axis.vertical == vertical).expect("the axis of the entry");
        let panels = [(position(axis.place(0, 2)), color(c1)), (position(axis.place(1, 2)), color(c2))];
        let members = panels.iter().map(|&(place, c)| Box::from([place, c, color(out)]));
        let ident = table.intern(Content::Set(MemberSet::new(member.clone(), members)));
        let id = Term::Ident(ident).encode().expect("an Ident's term id");
        for (place, c) in panels {
            rows.insert(Box::from([id, color(out), place, c]));
        }
    }
    rows
}
