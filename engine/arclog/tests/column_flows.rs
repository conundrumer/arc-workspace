//! The sources, the depth, the keys and the grid columns of the tables of a
//! decode, as the flat columns of a case give them.

use std::sync::Arc;

use arclog::check::{check_program, CheckCache, SolverClauses};
use arclog::decode::columns::{case_columns, CaseColumns};
use arclog::decode::{evidence_tables, Decoder, Points, Table};
use arclog::eval::instance::Constructions;
use arclog::eval::Caps;
use arclog::judge::candidates::{PairCandidates, Section, World};
use arclog::read::read_solver;
use arclog::registry::Registry;
use arclog::resolver::{resolve, SourceKind};
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::{token_stream, DecodeSettings, Emitter, Vocabulary};
use arclog::task::{Grid, JudgedPair, JudgedTask, Task, TrainPair};
use arclog::terms::Color;

fn grid(colors: &[u8]) -> Grid {
    let rows: Box<[Box<[Color]>]> = Box::new([colors.iter().map(|&digit| Color::from_digit(digit).expect("a color")).collect()]);
    Grid::from_rows(rows).expect("a grid")
}

/// The columns of the tables that a decode of `arclog` gives, on a task of
/// one train pair whose output is `output`.
fn columns_of(arclog: &str, output: &[u8]) -> CaseColumns {
    let registry = Registry::get();
    let solver = read_solver("flows", arclog, "", &|_| None).expect("the file reads").value;
    let program = resolve(&solver.concept_case().program, None, &solver.derived_relations(), registry).value;
    let checked = check_program(program, &SolverClauses::of(&solver, registry), registry, &mut CheckCache::default()).expect("every check passes");
    let tokens: Vec<_> = token_stream(&checked, &Vocabulary::new(registry, &DecodeSettings::default())).expect("a stream").into_iter().filter(|(_, emitter)| *emitter == Emitter::Model).map(|(token, _)| token).collect();
    let task = Task { train: Box::new([TrainPair { input: grid(&[1, 2]), output: grid(output) }]), test: Box::new([]) };
    let judged = JudgedTask { train: Box::new([JudgedPair { output: grid(output), alt: None }]), test: Box::new([]) };
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let session = TaskSession::new(SessionBound { bytes: 1 << 26 }, Caps::CORPUS);
    let settings = DecodeSettings { caps: Caps::CORPUS, ..DecodeSettings::default() };
    let train: Arc<[PairCandidates<'_>]> = judged.train.iter().map(|pair| PairCandidates::of(pair, Section::Train, World::Closed)).collect();
    let mut decoder = Decoder::new(&task, &session, registry, &constructions, &settings).judging(train);
    let mut tables: Vec<(usize, Table)> = Vec::new();
    for (index, token) in tokens.into_iter().enumerate() {
        decoder.step(token).expect("the program steps");
        tables.extend(decoder.tables(Points::Relations).into_iter().map(|table| (index, table)));
    }
    case_columns(&evidence_tables(&task, registry), &tables, 1)
}

/// A source of a column: its kind, the relation read, the column of it, its
/// table, its `DET` and its atom.
type Found = (u8, String, i32, i32, i32, String);

/// The sources of column `column` of the table at row `table`, in order.
fn sources(columns: &CaseColumns, table: u32, column: u32) -> Vec<Found> {
    let flows = &columns.flows;
    (0..flows.table.len())
        .filter(|&row| flows.table[row] == table && flows.column[row] == column)
        .map(|row| (flows.kind[row], flows.source_relation[row].clone(), flows.source_column[row], flows.source_table[row], flows.det[row], flows.atom[row].clone()))
        .collect()
}

/// The row of the table of the relation of `slot`.
fn table_of(columns: &CaseColumns, slot: i32) -> u32 {
    columns.tables.relation.iter().position(|&relation| relation == slot).expect("a table of the slot") as u32
}

const COPY: u8 = SourceKind::Copy as u8;
const COMPUTED: u8 = SourceKind::Computed as u8;

const OPENING: &str = "(DET &background ColorDomain)
(INIT &box BoundingBox
  (cell (P)
    (input *P *Col)
    (NOT (&background (:C Col)))))
(RULE &opening
  (&box.box *B)
  (input *P *Col)
  (&background (:C Col))
  (inside (:A P) B)
  (same_dist *D (:P1 P) (:P2 B)))
(RULE &output (input *P *Col))
";

#[test]
fn a_column_gives_each_source_with_its_atom_and_its_det() {
    let columns = columns_of(OPENING, &[1, 2]);
    let (background, boxes, opening, output) = (table_of(&columns, 0), table_of(&columns, 1), table_of(&columns, 3), table_of(&columns, 4));
    assert_eq!(columns.tables.det_relations[opening as usize], ["slot 0"]);
    let box_ = sources(&columns, opening, 0);
    assert_eq!(box_, [(COPY, "slot 1.box".to_owned(), 0, boxes as i32, -1, "2.0.0".to_owned())]);
    assert_eq!(sources(&columns, opening, 1), [(COPY, "ex_input".to_owned(), 1, 0, -1, "2.0.1".to_owned())]);
    assert_eq!(
        sources(&columns, opening, 2),
        [(COPY, "ex_input".to_owned(), 2, 0, -1, "2.0.1".to_owned()), (COPY, "slot 0".to_owned(), 0, background as i32, 0, "2.0.2".to_owned())]
    );
    let distance = sources(&columns, opening, 3);
    assert!(distance.iter().all(|source| source.0 == COMPUTED), "{distance:?}");
    assert!(distance.iter().any(|source| source.1 == "ex_input" && source.2 == 1), "{distance:?}");
    assert!(distance.iter().any(|source| source.1 == "slot 1.box" && source.2 == 0 && source.3 == boxes as i32), "{distance:?}");
    assert_eq!(sources(&columns, background, 0), [(SourceKind::LibName as u8, "ColorDomain".to_owned(), -1, -1, -1, String::new())]);
    assert_eq!(sources(&columns, output, 0), [(COPY, "ex_input".to_owned(), 1, 0, -1, "3.0.0".to_owned())]);
}

#[test]
fn a_table_gives_its_depth_and_the_grid_columns_of_the_output() {
    let columns = columns_of(OPENING, &[1, 2]);
    let tables = &columns.tables;
    let depth = |slot| tables.depth[table_of(&columns, slot) as usize];
    assert_eq!(&tables.depth[..2], [0, 0], "the evidence tables");
    assert_eq!(depth(3), 1 + depth(1).max(depth(0)));
    let grids: Vec<(i32, i32)> = tables.output_position.iter().copied().zip(tables.output_color.iter().copied()).collect();
    assert_eq!(grids[table_of(&columns, 4) as usize], (0, 1));
    assert_eq!(grids.iter().filter(|&&grid| grid != (-1, -1)).count(), 1, "only the output relation gives grid columns");
}

#[test]
fn a_one_mark_and_a_choose_give_keys_and_the_evidence_tables_give_e_and_p() {
    let one = columns_of("(RULE &cell (input *P *Col) (ONE P))\n(RULE &output (input *P *Col))\n", &[3, 3]);
    assert_eq!(one.tables.keys[0], [vec![0, 1]]);
    assert_eq!(one.tables.keys[1], [vec![0, 1]]);
    assert_eq!(one.tables.keys[table_of(&one, 0) as usize], [vec![0]]);
    let any = columns_of("(RULE &cell (input *P *Col) (ONE))\n(RULE &output (input *P *Col))\n", &[3, 3]);
    assert_eq!(any.tables.keys[table_of(&any, 0) as usize], [Vec::<u32>::new()]);
    let choose = columns_of("(RULE &bg (input (:Col *C)))\n(RULE &fg (input *P *Col))\n(CHOOSE &pick (for ((&fg ^P)) (from (&fg P *Col))) (never (&fg *P *Col) (&fg (:P *P2) Col) (!= P P2) (&bg (:C Col))))\n(RULE &output (input *P *Col))\n", &[3, 3]);
    assert_eq!(choose.tables.keys[table_of(&choose, 2) as usize], [vec![0]]);
    assert!(choose.tables.keys[table_of(&choose, 1) as usize].is_empty(), "a clause with no mark has no key");
}
