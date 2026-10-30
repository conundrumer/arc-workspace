//! Checked normalization provenance. This exports source correspondence only;
//! it makes no evaluation, held-choice, model-family or table reuse assertion.
use super::{StudyProgram, render_correspondence};
use crate::mutation::edit::{AtomEdit, source_paths};
use crate::registry::Registry;
use crate::stream::{DecodeSettings, Vocabulary};
use serde_json::{Value, json};

fn identity(program: &StudyProgram, registry: &Registry, settings: &DecodeSettings) -> Value {
    let stream = match program.decode_stream(registry, settings) {
        Ok(stream) => json!({"status":"complete","ids":stream.ids,"model":stream.model,
            "paths":stream.paths.iter().map(crate::mutation::path_json).collect::<Vec<_>>()}),
        Err(reason) => json!({"status":"unsupported","reason":reason}),
    };
    json!({"program_sexp":program.sexp(registry),"stream":stream})
}

fn correspondence(program: &StudyProgram, source: &StudyProgram, registry: &Registry,
    settings: &DecodeSettings, current: &Value, original: &Value, paths: Option<&Value>) -> Value {
    let gold=paths.map(|_|source.checked().as_ref());
    match render_correspondence::export(program,source,registry,settings,current,original,gold,paths) {
        Ok(mut value) => {
            // The shared edit mapper also serves ValidMutant. This report
            // describes normalization and does not grant mutation admission.
            if paths.is_some() {
                value["representation"]="normalized_gold".into();
                value["source_bridge_status"]="native_atomic_edit".into();
            }
            json!({"status":"complete","value":value})
        }
        Err(reason) => json!({"status":"unsupported","reason":reason}),
    }
}

/// Reuse the actual normalized handle and editor trace before they go out of
/// scope. Full checked exports retain both physical layouts and header/site
/// descriptors; local unsupported correspondence is never inferred in Python.
pub fn provenance(original: &StudyProgram, normalized: &StudyProgram, edits: &[AtomEdit],
    registry: &Registry, settings: &DecodeSettings) -> Value {
    let paths=source_paths(original.program(),edits);
    let nodes=paths.as_array().into_iter().flatten().map(|row| {
        let mut row=row.clone();
        row["address_status"]=if row["after_path"].is_null(){"deleted"}
            else if row["before_path"]==row["after_path"]{"unchanged"}else{"moved"}.into();
        row
    }).collect::<Vec<_>>();
    let descriptors=match (original.render_json(registry),normalized.render_json(registry)) {
        (Ok(before),Ok(after)) => {
            let original_map=correspondence(original,original,registry,settings,&before,&before,None);
            let normalized_map=correspondence(normalized,normalized,registry,settings,&after,&after,None);
            let source_map=correspondence(normalized,original,registry,settings,&after,&before,Some(&paths));
            json!({"status":"complete","original":{"export":before,"correspondence":original_map},
                "normalized":{"export":after,"correspondence":normalized_map},
                "normalized_to_original":source_map,
                "coverage":"exports enumerate native BODY/header domains; each local mapping status remains authoritative; no CaseTables snapshot binding or per-row extents"})
        }
        (Err(reason),_)|(_,Err(reason)) => json!({"status":"unsupported","reason":reason}),
    };
    let vocabulary=Vocabulary::new(registry,settings);
    json!({"schema":"arclog-study-normalization-provenance-v1","status":"complete",
        "original":identity(original,registry,settings),"normalized":identity(normalized,registry,settings),
        "settings":format!("{settings:?}"),
        "vocabulary":(0..vocabulary.len()).map(|id|vocabulary.token(id as u32).map(|t|format!("{t:?}"))).collect::<Vec<_>>(),
        "nodes":nodes,"descriptors":descriptors,
        "checks":{"no_fresh_label_deletion":true,"original_interfaces":true,"whole_program_check":true},
        "authority":{"source_correspondence":true,"mutation_admission":false,
            "evaluation_equivalence":false,"held_equivalence":false,"model_family_equivalence":false,
            "out_equivalence":false,"table_reuse":false},
        "node_contract":"preserved identifies an editor node, not unchanged subtree content; address_status distinguishes movement; deleted nodes have no target",
        "identity_contract":"exact checked writer, full emitted stream, vocabulary and settings; scoped IDs belong to these exports; unsupported fields grant no correspondence"})
}
