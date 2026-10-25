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
use arclog::layout::SourceFile;
use arclog::program::path::NodePath;
use arclog::program::{DeclaredName, OutputStep};
use arclog::read::read_arclog;
use arclog::eval::flows::SourceKind;
use arclog::resolver::{resolve, GraphNodeIndex};
use arclog::types::ValueType;
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

/// The checked program of the arclog file `arclog`.
fn checked_program(arclog: &str) -> arclog::check::CheckedProgram {
    let registry = Registry::get();
    let read = read_arclog(arclog, SourceFile::Arclog).expect("the program reads");
    let program = resolve(&read.value.0, None, &Default::default(), registry).value;
    check_program(program, &SolverClauses::default(), registry, &mut CheckCache::default()).expect("every check passes")
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
    assert_eq!(columns.tables.column_types[opening as usize], ["Box", "Dir", "Box", "Color"]);
    assert_eq!(sources(&columns, opening, 0), [(COPY, "ex_input".to_owned(), 1, 0, -1, "2.0.1".to_owned())]);
    assert_eq!(sources(&columns, opening, 2), [(COPY, "slot 1.box".to_owned(), 0, boxes as i32, -1, "2.0.0".to_owned())]);
    assert_eq!(
        sources(&columns, opening, 3),
        [(COPY, "ex_input".to_owned(), 2, 0, -1, "2.0.1".to_owned()), (COPY, "slot 0".to_owned(), 0, background as i32, 0, "2.0.2".to_owned())]
    );
    let distance = sources(&columns, opening, 1);
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

const TILING: &str = "(INIT &tiling Tiling
  (outer ((:P P_tile))
    (input (:P *P_tile)))
  (inner ((:P P_intile))
    (input (:P *P_intile))))
(RULE &cell
  (&tiling.cell (:P_outer *P_tile) (:P_inner *P_intile) (:P *P_grid)))
(RULE &output (input *P *Col))
";

#[test]
fn an_instance_output_is_computed_from_the_sources_of_its_input_ports() {
    let columns = columns_of(TILING, &[1, 2]);
    let cell = table_of(&columns, 0);
    for column in 0..3 {
        let found = sources(&columns, cell, column);
        assert!(!found.is_empty(), "column {column}");
        assert!(found.iter().all(|source| source.0 == COMPUTED && source.1 == "ex_input" && source.3 == 0), "column {column}: {found:?}");
        assert!(found.iter().any(|source| source.2 == 1), "column {column}: {found:?}");
    }
}

#[test]
fn a_read_of_an_input_port_copies_the_sources_of_the_ports_column() {
    let arclog = OPENING.replace("(RULE &output (input *P *Col))", "(RULE &seen (&box.cell *P))\n(RULE &output (input *P *Col))");
    let columns = columns_of(&arclog, &[1, 2]);
    let seen = table_of(&columns, 4);
    let found = sources(&columns, seen, 0);
    assert!(found.iter().any(|source| source.1 == "ex_input" && source.2 == 1 && source.3 == 0), "{found:?}");
    assert!(found.iter().all(|source| source.3 != -1), "{found:?}");
}

const ANCHOR: &str = "(DET &band_axis AxisDomain)
(RULE &anchor
  (&band_axis *A)
  (axis_of *D A))
(RULE &output (input *P *Col))
";

const FEED: &str = "(RULE &wall (input (:P *Q)))
(RULE &between (input (:P *X)))
(RULE &feed
  (input (:P *X))
  (neighbor (:P X) (:D *D) (:Q *B))
  (OR
    ((&wall *Q)
     (neighbor (:P Q) (:D D) (:Q *F)))
    ((&between (:X B))
     (= F B))))
(RULE &output (input *P *Col))
";

#[test]
fn a_column_flow_indexes_the_tables_columns_where_the_clause_writes_them_in_another_order() {
    let columns = columns_of(ANCHOR, &[1, 2]);
    let anchor = table_of(&columns, 1);
    let types = &columns.tables.column_types[anchor as usize];
    assert_eq!(types.len(), 2, "{types:?}");
    let mut copies = 0;
    for column in 0..2 {
        for (kind, _, source_column, source_table, det, _) in sources(&columns, anchor, column) {
            if kind != COPY || source_column < 0 || source_table < 0 {
                continue;
            }
            copies += 1;
            let source = if det >= 0 { &columns.tables.det_types[anchor as usize][det as usize] } else { &columns.tables.column_types[source_table as usize] };
            assert_eq!(types[column as usize], source[source_column as usize], "column {column} copies column {source_column} of table {source_table}");
        }
    }
    assert!(copies > 0);
}

/// A solver whose `&mark` takes the column order [Color, Box] where it is the
/// last form and [Box, Color] once the `DET`s it reads are widened by the
/// forms after it.
const REORDERED: &str = include_str!("column_flows/reordered_columns.arclog");

#[test]
fn a_copy_flow_names_the_column_of_its_source_table_in_the_order_the_table_was_exported_with() {
    let columns = columns_of(REORDERED, &[3, 3]);
    let mut copies = 0;
    for table in 0..columns.tables.relation.len() as u32 {
        let types = &columns.tables.column_types[table as usize];
        for column in 0..types.len() as u32 {
            for (kind, _, source_column, source_table, det, _) in sources(&columns, table, column) {
                if kind != COPY || source_column < 0 || source_table < 0 || det >= 0 {
                    continue;
                }
                copies += 1;
                let source = &columns.tables.column_types[source_table as usize];
                assert_eq!(types[column as usize], source[source_column as usize], "column {column} of table {table} copies column {source_column} of table {source_table}");
            }
        }
    }
    assert!(copies > 0);
}

const PROPAGATION: &str = "(RULE &seed (dir_elem (:D *Delta)))
(RULE &halt (dir_elem (:D *Delta)) (dir_elem (:D *Delta2)))
(INIT &journey Propagation
  (source ((:n N)) (&seed (:Delta *N)))
  (edge ((:a N) (:b N2)) (&halt (:Delta *N) (:Delta2 *N2))))
(RULE &seen (&journey.edge (:a *A) (:b *B)))
(RULE &output (input *P *Col))
";

#[test]
fn an_input_port_takes_the_sources_of_its_own_head_sites_and_an_output_those_of_every_site() {
    let columns = columns_of(PROPAGATION, &[1, 2]);
    let (seen, reached) = (table_of(&columns, 6), table_of(&columns, 2));
    let atom_in = |found: &[Found], prefix: &str| found.iter().all(|source| source.5.starts_with(prefix));
    for column in 0..2 {
        let found = sources(&columns, seen, column);
        assert!(!found.is_empty() && atom_in(&found, "2.1."), "column {column}: {found:?}");
    }
    let edge = table_of(&columns, 1) as i32;
    let found = sources(&columns, reached, 0);
    assert!(found.iter().any(|source| source.5.starts_with("2.1.")), "{found:?}");
    assert!(found.iter().any(|source| source.3 == edge), "{found:?}");
    let depth = |table: u32| columns.tables.depth[table as usize];
    for table in [seen, reached] {
        for column in 0..2 {
            for source in sources(&columns, table, column) {
                assert!(source.3 < 0 || source.3 as u32 == table || depth(table) > depth(source.3 as u32), "table {table}: {source:?}");
            }
        }
    }
}

/// A keyed `Propagation` that writes no `source`, whose key is `key`.
fn unsourced(key: &str) -> String {
    format!(
        "(RULE &seed (dir_elem (:D *Delta)))
(RULE &halt (dir_elem (:D *Delta)) (dir_elem (:D *Delta2)))
(INIT &journey Propagation
  (key (({key})))
  (edge ((:a N) (:b N2)) (&halt (:Delta *N) (:Delta2 *N2))))
(RULE &output (input *P *Col))
"
    )
}

/// The atoms that the sources of column `column` of `reached` name.
fn reached_atoms(arclog: &str, column: u32) -> Vec<String> {
    let columns = columns_of(arclog, &[1, 2]);
    let mut atoms: Vec<String> = sources(&columns, table_of(&columns, 2), column).into_iter().map(|source| source.5).collect();
    atoms.sort_unstable();
    atoms.dedup();
    atoms
}

#[test]
fn a_column_the_key_fills_into_an_unwritten_input_takes_the_key_position_that_the_fill_gives() {
    let one = reached_atoms(&unsourced("&seed (:Delta ^K)"), 1);
    let two = reached_atoms(&unsourced("&halt (:Delta ^K) (:Delta2 ^K2)"), 2);
    assert_eq!(one, ["2.0.0.0", "2.1.2.0"], "the key's atom beside the edge's");
    assert_eq!(two, ["2.1.2.0"], "the edge's atom alone");
}

/// A keyed `Propagation` whose `edge` body is an `OR` of a branch that binds
/// `N2` at a program atom and a branch that gives it `second`.
fn equated(second: &str) -> String {
    format!(
        "(RULE &seed (dir_elem (:D *Delta)))
(RULE &halt (dir_elem (:D *Delta)) (dir_elem (:D *Delta2)))
(INIT &journey Propagation
  (key ((&seed (:Delta ^K)))
    (edge ((:a N) (:b N2))
      (&halt (:Delta *N) (:Delta2 *Other))
      (OR ((&halt (:Delta2 *N2)) (&seed (:Delta K))) (({second})))))
  (source ((:n S)) (&halt (:Delta *S) (:Delta2 *Z))))
(RULE &output (input *P *Col))
"
    )
}

#[test]
fn a_label_equal_to_a_key_label_takes_the_key_sources_where_the_alternative_binds_it_at_no_program_atom() {
    let seed = |atoms: Vec<String>| atoms.iter().any(|atom| atom == "2.0.0.0");
    let program = reached_atoms(&equated("= N2 K"), 1);
    assert!(seed(program.clone()), "the key's atom beside the branch's: {program:?}");
    let lib = reached_atoms(&equated("dir8_elem (:D N2)"), 1);
    assert!(!seed(lib.clone()), "no key source where a lib atom binds the label: {lib:?}");
}

#[test]
fn a_label_bound_in_one_branch_of_an_or_gets_the_sources_of_the_other_branch() {
    let columns = columns_of(FEED, &[1, 2]);
    let (between, feed) = (table_of(&columns, 1), table_of(&columns, 2));
    let has_copy = |found: &[Found]| found.iter().any(|source| source.0 == COPY && source.3 == between as i32);
    let has_computed = |found: &[Found]| found.iter().any(|source| source.0 == COMPUTED);
    let bound = sources(&columns, feed, 2);
    assert!(has_copy(&bound) && has_computed(&bound), "{bound:?}");
    let fed = sources(&columns, feed, 3);
    assert!(has_copy(&fed) && has_computed(&fed), "{fed:?}");
}

#[test]
fn a_part_column_of_a_rigid_det_is_computed_where_a_pose_moves_its_type_and_a_copy_otherwise() {
    let registry = Registry::get();
    let program = checked_program("(RULE &cell (input *P *Col))\n(RIGID_DET &piece (&cell *P *Col))\n");
    let form = NodePath::default().child(1);
    let node = (0..program.program.graph.nodes.len() as u32).map(GraphNodeIndex).find(|node| *program.program.form_of(*node) == form).expect("the node of the `RIGID_DET` form");
    let part = [OutputStep::Part(DeclaredName::Written("&cell".into()))];
    let flows = program.column_flows(node, Some(&part), &[ValueType::Number, ValueType::Box, ValueType::Color], registry);
    let kinds = |column: usize| flows[column].iter().map(|source| source.kind).collect::<Vec<_>>();
    assert_eq!(kinds(1), [SourceKind::Computed], "{flows:?}");
    assert_eq!(kinds(2), [SourceKind::Copy], "{flows:?}");
    assert!(flows[1..].iter().all(|sources| sources.iter().all(|source| source.relation.is_some())), "{flows:?}");
}

const UNFOLD: &str = "\
(DET &seed RarestColor)
(RULE &seed_cell
  (input *P *Col)
  (&seed (:C Col)))
(INIT &state Unfold
  (start ((:t P))
    (&seed_cell *P))
  (initial_untaken ((:item P))
    (input *P)
    (NOT (&seed_cell P)))
  (score ((:t P) (:item X) (:S K))
    (&seed_cell *P)
    (input (:P *X))
    (NOT (&seed_cell (:P X)))
    (= *K 0))
  (step ((:t P) (:t2 P2))
    (&seed_cell *P)
    (input (:P *P2))
    (&state.untaken (:t P) (:item P2))))
(RULE &taken
  (&state.take (:item *P)))
(RULE &output (input *P *Col))
";

#[test]
fn an_output_of_an_instance_that_reads_its_own_outputs_has_no_flow_from_them() {
    let columns = columns_of(UNFOLD, &[1, 2]);
    let flows = &columns.flows;
    let outputs: Vec<u32> = (2..=5).map(|slot| table_of(&columns, slot)).collect();
    for row in (0..flows.table.len()).filter(|&row| outputs.contains(&flows.table[row])) {
        assert!(!flows.source_relation[row].starts_with("slot 2."), "table {}: {:?}", flows.table[row], flows.source_relation[row]);
    }
    for &table in &outputs {
        assert!(!sources(&columns, table, 0).is_empty(), "table {table}");
    }
}

#[test]
fn a_label_that_the_test_of_an_if_binds_gets_the_copy_of_the_test_atom() {
    let columns = columns_of(
        "(DET &fill ColorDomain)
(RULE &marked (input *P))
(RULE &output
  (input *P (:Col *C_in))
  (IF ((&marked P))
      ((&fill (:C *Col)))
      ((= Col C_in))))
",
        &[1, 2],
    );
    let output = table_of(&columns, 2);
    let atoms: Vec<String> = sources(&columns, output, 0).into_iter().map(|source| source.5).collect();
    assert!(atoms.contains(&"2.0.1.0.0".to_owned()), "the atom in the test of the `IF`: {atoms:?}");
}

#[test]
fn the_pose_output_of_a_rigid_det_reads_the_atoms_of_its_instance_clause_and_no_part() {
    let program = checked_program("(RULE &seed (input *P))\n(RULE &cell (input *P *Col))\n(RIGID_DET &piece (instance ((&seed ^P)) (&cell P *Col)))\n");
    let registry = Registry::get();
    let form = NodePath::default().child(2);
    let node = (0..program.program.graph.nodes.len() as u32).map(GraphNodeIndex).find(|node| *program.program.form_of(*node) == form).expect("the node of the `RIGID_DET` form");
    let flows = program.column_flows(node, Some(&[OutputStep::Pose]), &[ValueType::Number, ValueType::D4], registry);
    let atoms: Vec<&NodePath> = flows[0].iter().map(|source| &source.atom).collect();
    assert_eq!(atoms, [&form.child(0).child(0)], "the instance clause's atom, where the part's atom is at 2.1: {flows:?}");
}
