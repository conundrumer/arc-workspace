//! The replay of a solver, with the token mask computed before each step,
//! gives the same record under the measurement profile as under the default
//! settings.

use arclog::decode::corpus::replay_solver;
use arclog::decode::replay::Stepped;
use arclog::decode::Decoder;
use arclog::eval::instance::Constructions;
use arclog::registry::Registry;
use arclog::stream::DecodeSettings;

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
