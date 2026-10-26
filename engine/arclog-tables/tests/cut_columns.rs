//! The columns of a stream cut after a prefix that it shares with its base
//! stream, replayed in one prefix tree with the base, give the tables of the
//! columns of the whole stream: the base's tables numbered below the cut, then
//! the cut columns' own tables.

use arclog::decode::corpus::{read_task_files, replay_prefix_tree};
use arclog::eval::instance::Constructions;
use arclog::registry::Registry;
use arclog::stream::corpus::{solver_streams, token_ids, WantedCases};
use arclog::stream::{DecodeSettings, Emitter, Vocabulary};
use arclog_tables::columns::{case_columns, cut_case_columns, CaseColumns};
use arclog_tables::tables::{evidence_tables, step_tables, Points, Table};

const ARCLOG: &str = "\
;; tie

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
    (= *K 0)))

(RULE &taken
  (&state.take (:item *P)))

(RULE &output
  (OR ((input *P *Col)
       (NOT (&taken P)))
      ((&taken P)
       (&seed (:C Col)))))
";

/// The program of `ARCLOG` but for its `&taken` clause, which gives a stream
/// that branches from the stream of `ARCLOG` after the clauses before it.
const OTHER: &str = "\
;; tie

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
    (= *K 0)))

(RULE &taken
  (&state.take (:item *P))
  (&seed_cell P))

(RULE &output
  (OR ((input *P *Col)
       (NOT (&taken P)))
      ((&taken P)
       (&seed (:C Col)))))
";

const ARCDATA: &str = "\
;; tie

(param &seed Color (2))
";

/// The rows of the tables numbered from `first` in `columns`, one text for
/// each table: its own columns, its flows, its entries with the cells of
/// their runs and the runs of their assignments, and its projections with the
/// cells of their rows at each entry. A row that names an entry or a projection
/// names it by its place among the table's, so the text of a table does not depend
/// on the tables before it but by the numbers of the tables it names.
fn views(columns: &CaseColumns, first: u32) -> Vec<String> {
    let t = &columns.tables;
    let cells = |offset: u64, rows: u64, width: u32| -> Vec<i32> { columns.values[offset as usize..offset as usize + (rows * u64::from(width)) as usize].to_vec() };
    (0..t.token.len())
        .map(|i| {
            let number = first + i as u32;
            let own = format!(
                "{} {} {} {} {} {} {:?} {:?} {:?} {} {:?} {:?} {:?} {:?} {} {:?} {:?} {:?} {} {:?} {} {}",
                t.token[i], t.form[i], t.point[i], t.conjuncts[i], t.sites[i], t.relation[i], t.fact[i], t.column_names[i], t.column_types[i], t.width[i], t.det_relations[i], t.det_types[i], t.det_widths[i], t.det_columns[i],
                t.projections[i], t.projections_stop.bound[i], t.projections_stop.form[i], t.fault[i], t.depth[i], t.keys[i], t.output_position[i], t.output_color[i]
            );
            let f = &columns.flows;
            let flows: Vec<String> = (0..f.table.len())
                .filter(|&j| f.table[j] == number)
                .map(|j| format!("{} {} {} {} {} {} {} {} {}", f.table[j], f.column[j], f.kind[j], f.source_table[j], f.source_relation[j], f.source_column[j], f.det[j], f.atom[j], f.occurrence[j]))
                .collect();
            let e = &columns.entries;
            let entries: Vec<usize> = (0..e.table.len()).filter(|&j| e.table[j] == number).collect();
            let shown: Vec<String> = entries
                .iter()
                .map(|&j| {
                    let runs: Vec<String> = (0..columns.assigned.entry.len())
                        .filter(|&a| columns.assigned.entry[a] as usize == j)
                        .map(|a| {
                            let a_det = columns.assigned.det[a] as usize;
                            format!("{} {:?}", a_det, cells(columns.assigned.offset[a], columns.assigned.rows[a], t.det_widths[i][a_det]))
                        })
                        .collect();
                    let rows = if e.kind[j] == 0 { cells(e.offset[j], e.rows[j], t.width[i]) } else { Vec::new() };
                    format!("{} {} {} {} {} {:?} {:?} {:?} {:?} {:?} {:?}", e.example_kind[j], e.example_index[j], e.model[j], e.kind[j], e.rows[j], e.stop.bound[j], e.stop.form[j], e.value_stop.bound[j], e.value_stop.form[j], e.fault[j], (rows, runs))
                })
                .collect();
            let p = &columns.projections;
            let projections: Vec<String> = (0..p.table.len())
                .filter(|&j| p.table[j] == number)
                .map(|j| {
                    let rows: Vec<String> = (0..columns.projection_rows.projection.len())
                        .filter(|&r| columns.projection_rows.projection[r] as usize == j)
                        .map(|r| {
                            let q = &columns.projection_rows;
                            let at = entries.iter().position(|&x| x == q.entry[r] as usize).expect("an entry of the projection's table");
                            format!("{at} {} {} {:?}", q.defined[r], q.rows[r], if q.defined[r] == 1 { cells(q.offset[r], q.rows[r], p.width[j]) } else { Vec::new() })
                        })
                        .collect();
                    format!("{:?} {} {:?}", p.columns[j], p.width[j], rows)
                })
                .collect();
            format!("{own}\n{flows:?}\n{shown:?}\n{projections:?}")
        })
        .collect()
}

#[test]
fn a_cut_stream_gives_the_tables_of_the_whole_stream_after_its_base_prefix() {
    let dir = std::env::temp_dir().join(format!("arclog-cut-columns-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("a temporary directory");
    let pair = r#"{"input": [[1, 2, 1]], "output": [[2, 2, 1]]}"#;
    for (id, arclog) in [("tie", ARCLOG), ("other", OTHER)] {
        std::fs::write(dir.join(format!("{id}.arclog")), arclog).expect("the arclog file");
        std::fs::write(dir.join(format!("{id}.arcdata")), ARCDATA).expect("the arcdata file");
    }
    std::fs::write(dir.join("tie.json"), format!(r#"{{"train": [{pair}], "test": [{pair}]}}"#)).expect("the task file");
    let registry = Registry::get();
    let settings = DecodeSettings::default();
    let vocabulary = Vocabulary::new(registry, &settings);
    let stream_of = |id: &str| {
        let cases = solver_streams(&dir, id, WantedCases::Concept, &vocabulary).expect("the solver's streams");
        token_ids(&cases[0].stream.as_ref().expect("a stream").tokens, &vocabulary)
    };
    let (task, judged) = read_task_files(&dir, "tie").expect("the task reads");
    let (whole, other) = (stream_of("tie"), stream_of("other"));
    std::fs::remove_dir_all(&dir).ok();
    let shared = whole.iter().zip(&other).take_while(|(x, y)| x == y).count();
    assert!(shared < whole.len() && shared < other.len(), "the streams branch");

    // The base, a stream that branches from it, a prefix of it, and a copy of it.
    let streams: Vec<Vec<(u32, Emitter)>> = vec![whole.clone(), other, whole[..shared + 3].to_vec(), whole.clone()];
    let constructions = Constructions::new(Vec::new(), registry).expect("an empty table");
    let record = |tables: &mut Vec<(usize, Table)>, decoder: &arclog::decode::Decoder<'_>, stepped: arclog::decode::replay::Stepped<'_>| {
        tables.extend(step_tables(decoder, Points::All).into_iter().map(|table| (stepped.index, table)));
    };
    let replayed = replay_prefix_tree(&task, &judged, &streams, &constructions, &settings, false, &record);
    let evidence = evidence_tables(&task, registry);
    let train = task.train.len();
    let full: Vec<CaseColumns> = replayed.iter().map(|out| case_columns(&evidence, &out.record, train)).collect();
    let base = views(&full[0], 0);
    assert!(base.len() > evidence.len() + 3, "the base has tables of its own");

    for index in 1..streams.len() {
        let tokens = streams[index].iter().zip(&streams[0]).take_while(|(x, y)| x == y).count();
        let (cut, k) = cut_case_columns(&evidence, &replayed[index].record, tokens, train);
        let whole_views = views(&full[index], 0);
        let k = k as usize;
        // The count is the evidence tables and each table whose token is below the prefix.
        let expected = evidence.len() + replayed[index].record.iter().filter(|(token, _)| *token < tokens).count();
        assert_eq!(k, expected, "stream {index}");
        assert_eq!(views(&cut, k as u32), whole_views[k..], "stream {index}: the cut columns' own tables");
        assert_eq!(base[..k], whole_views[..k], "stream {index}: the base's tables below the cut");
        assert_eq!(cut.copies.detail, full[index].copies.detail);
        assert!(cut.values.len() <= full[index].values.len());
        assert_eq!(cut.tables.token.len() + k, full[index].tables.token.len());
    }
    // The stream that branches holds tables of its own, past those of the prefix it shares.
    let (branching, k) = cut_case_columns(&evidence, &replayed[1].record, shared, train);
    assert!(k as usize > evidence.len() && !branching.tables.token.is_empty(), "the branching stream has tables before and after its cut");
    // The copy of the base holds no table of its own.
    let (copy, k) = cut_case_columns(&evidence, &replayed[3].record, streams[3].len(), train);
    assert!(copy.tables.token.is_empty() && copy.entries.table.is_empty() && copy.values.is_empty());
    assert_eq!(k as usize, full[3].tables.token.len());
}
