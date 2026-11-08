//! The replay of a solver, with the token mask computed before each step,
//! gives the same record under the measurement profile as under the default
//! settings, and the six search caps of the settings have the values that
//! the constants of the engine had before they were settings.

use arclog::decode::corpus::replay_solver;
use arclog::decode::replay::Stepped;
use arclog::decode::Decoder;
use arclog::eval::instance::Constructions;
use arclog::registry::Registry;
use arclog::program::canonical::{LabelingBound, SearchBudget};
use arclog::stream::{DecodeSettings, MEASURED_CAP};

const ARCLOG: &str = "\
;; measured

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

(OUT (&output ^P ^Col))
";

const ARCDATA: &str = "\
;; measured

(param &seed Color (2))
";

/// The steps of a replay and the tokens that the mask admitted, summed over the steps.
type Record = (usize, u64);

fn record(record: &mut Record, decoder: &Decoder<'_>, step: Stepped<'_>) {
    record.0 += 1;
    if let Some(masked) = &step.mask {
        let ids = u32::try_from(decoder.vocabulary().len()).expect("fewer than 2^32 tokens");
        record.1 += (0..ids).filter(|id| masked.mask.contains(*id)).count() as u64;
    }
}

#[test]
fn a_solver_replays_under_the_measurement_profile_as_under_the_default_settings() {
    let dir = std::env::temp_dir().join(format!("arclog-measurement-profile-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("a temporary directory");
    let pair = r#"{"input": [[1, 2, 1]], "output": [[2, 2, 1]]}"#;
    std::fs::write(dir.join("measured.arclog"), ARCLOG).expect("the arclog file");
    std::fs::write(dir.join("measured.arcdata"), ARCDATA).expect("the arcdata file");
    std::fs::write(dir.join("measured.json"), format!(r#"{{"train": [{pair}], "test": [{pair}]}}"#)).expect("the task file");
    let constructions = Constructions::new(Vec::new(), Registry::get()).expect("an empty table");
    let replay = |settings: &DecodeSettings| replay_solver::<Record>(&dir, &dir, "measured", false, &constructions, settings, true, &record);
    let default = replay(&DecodeSettings::default());
    let measured = replay(&DecodeSettings::measurement());
    std::fs::remove_dir_all(&dir).ok();
    let default = default.expect("the solver replays under the default settings");
    let measured = measured.expect("the solver replays under the measurement profile");
    assert_eq!(default.cases.len(), measured.cases.len());
    for (default, measured) in default.cases.iter().zip(&measured.cases) {
        assert_eq!(default.outcome, measured.outcome, "the record of the case {}", default.case);
        assert!(default.outcome.as_ref().is_ok_and(|(steps, admitted)| *steps > 0 && *admitted > 0), "{:?}", default.outcome);
    }
}

/// The six search caps of `settings`, by the name of the gauge each one caps.
fn search_caps(settings: &DecodeSettings) -> [(&'static str, u64); 6] {
    [
        ("projection_steps", settings.projection_step_cap),
        ("study_row_work", settings.study_row_work_cap),
        ("compared_rows", settings.compared_rows_cap),
        ("atom_states", settings.atom_state_cap),
        ("column_search_work", settings.column_search_work_cap),
        ("labeling_nodes", settings.labeling_node_cap),
    ]
}

#[test]
fn the_default_search_caps_are_the_constants_that_the_engine_had() {
    let expected: [(&str, u64); 6] = [("projection_steps", 4096), ("study_row_work", 1 << 28), ("compared_rows", 1 << 20), ("atom_states", 1 << 20), ("column_search_work", 1 << 28), ("labeling_nodes", 1000)];
    assert_eq!(search_caps(&DecodeSettings::default()), expected);
    assert_eq!(search_caps(&DecodeSettings::synthesis()), expected);
}

#[test]
fn the_measurement_profile_puts_each_search_cap_at_2_to_the_48() {
    assert_eq!(MEASURED_CAP, 1 << 48);
    let measured = DecodeSettings::measurement();
    for (gauge, cap) in search_caps(&measured) {
        assert_eq!(cap, 1 << 48, "the cap of {gauge}");
    }
}

#[test]
fn a_search_for_a_canonical_labeling_runs_under_the_cap_of_its_request() {
    // The cap is read from the thread's request, so the test runs on a thread of its own, which no request has begun on.
    std::thread::spawn(|| {
        assert_eq!(SearchBudget::new().cap, 1000);
        assert_eq!(LabelingBound::at_cap().cap, 1000);
        let settings = DecodeSettings { labeling_node_cap: 7, ..DecodeSettings::default() };
        let limits = settings.operation_limits();
        assert_eq!(limits.request.search_caps().labeling_nodes, 7);
        assert_eq!(limits.request.search_caps().column_search_work, 1 << 28);
        assert_eq!(SearchBudget::new().cap, 7);
        assert_eq!(LabelingBound::at_cap().cap, 7);
        let labeling = limits.request.gauges().each().into_iter().find(|(gauge, ..)| gauge.name() == "labeling_nodes").expect("the gauge labeling_nodes");
        assert_eq!(labeling.2, 7, "the cap that the gauge reports");
        let measured = DecodeSettings::measurement().operation_limits();
        assert_eq!(SearchBudget::new().cap, MEASURED_CAP);
        assert_eq!(measured.request.search_caps().column_search_work, MEASURED_CAP);
    })
    .join()
    .expect("the checks hold");
}
