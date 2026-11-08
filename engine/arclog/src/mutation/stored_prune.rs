//! Static classification of authenticated stored source, not sampler replay.
use super::*;
use crate::study::render_correspondence::trace_paths;

/// Match a recorded edit's addresses to the stored decoder representation.
/// The temporary edited AST is an address certificate, never an executable
/// ValidMutant and never the source of classifier types or conclusions.
fn site_bridge(
    origin: &StudyProgram,
    stored: &StudyProgram,
    identity: &Value,
    registry: &Registry,
    settings: &DecodeSettings,
) -> Result<Vec<(NodePath, NodePath)>, String> {
    let (candidate,selected)=if identity::is_body_edit(identity) {
        let (candidate,at)=identity::metadata_body(origin,identity,registry)?;
        (candidate,vec![(at.clone(),at)])
    } else {
        let edits=identity::metadata_edits(origin,identity)?;
        let ast=edit::apply(origin.program(),&edits)?;
        let candidate=StudyProgram::from_program(ast,edit::layout(origin.layout(),&edits),registry)?;
        let selected=edits.iter().filter(|e|e.replacement.is_some()).map(|e|
            edit::mapped(&e.at,&edits).map(|after|(e.at.clone(),after))
                .ok_or_else(||"surviving recorded edit has no path".to_string())).collect::<Result<Vec<_>,_>>()?;
        (candidate,selected)
    };
    let a = candidate.written_stream(registry, settings).map_err(|e| e.message.to_string())?;
    let b = stored.written_stream(registry, settings).map_err(|e| e.message.to_string())?;
    if a.tokens != b.tokens {
        return Err("recorded edit and stored program emit different native tokens/emitters".into());
    }
    // Different AST paths are expected for named/record wrappers. Pair only
    // uniquely matching node kinds and native writer-token coverage.
    let map = trace_paths(candidate.checked(), stored.checked(), &a, &b);
    let mut sites = Vec::new();
    for (before,at) in selected {
        let found:Vec<_>=map.iter().filter(|(_,path)|**path==at).map(|(after,_)|after.clone()).collect();
        let [after]=found.as_slice() else {
            return Err(format!("recorded site {before:?} has {} stored node correspondences",found.len()));
        };
        sites.push((before,after.clone()));
    }
    Ok(sites)
}

impl StudyProgram {
    /// Classify the actual saved program. Historical edit data selects sites;
    /// current generator alternatives and held-value execution admission are
    /// deliberately absent. Those checks remain on their original APIs.
    pub fn stored_static_prune_json(
        &self,
        gold: &StudyProgram,
        identity: &Value,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<Value, String> {
        // Canonical decoder syntax comes only from the checked stored source.
        // This also makes named scalar fields use the sampler's native syntax.
        let stored = self.decode_source(registry, settings).map_err(|e| format!("stored_decode: {e}"))?;
        let decoded_gold = gold.decode_source(registry, settings).map_err(|e| format!("gold_decode: {e}"))?;
        let mut accepted = Vec::new();
        let mut reasons = Vec::new();
        for (name, origin) in [("native_decode", &decoded_gold), ("parsed", gold)] {
            match site_bridge(origin, &stored, identity, registry, settings) {
                Ok(sites) => accepted.push(sites),
                Err(error) => reasons.push(format!("{name}: {error}")),
            }
        }
        let Some(sites) = accepted.first() else {
            return Err(format!("changed_site_mapping: {}", reasons.join("; ")));
        };
        if accepted.iter().any(|other| other != sites) {
            return Err("changed_site_mapping: source representations give different changed-site correspondences".into());
        }
        let selected: Vec<_> = sites.iter().map(|(_, at)| at.clone()).collect();
        let matches = crate::check::static_prune::matches_at(stored.checked(), registry, &selected)
            .map_err(|e| format!("stored_classifier: {e}"))?;
        let mut report = crate::check::static_prune::report(&matches);
        for (row, found) in report["matches"].as_array_mut().unwrap().iter_mut().zip(&matches) {
            row["original_atom_paths"] = json!(sites.iter().filter(|(_, at)|
                found.path.0.starts_with(&at.0) || at.0.starts_with(&found.path.0))
                .map(|(before, _)| path_json(before)).collect::<Vec<_>>());
        }
        if identity::is_body_edit(identity) {
            report["edit_unit"]="body".into();
            report["original_body_path"]=identity["body"].clone();
        }
        report["acquisition_schema"] = "arclog-stored-static-prune-v2".into();
        report["classification_representation"] = "native decode of checked stored mutant source".into();
        report["changed_sites"] = json!(sites.iter().map(|(before, after)| json!({
            "original_atom_path":path_json(before),"stored_atom_path":path_json(after)
        })).collect::<Vec<_>>());
        report["scope"] = "surviving recorded edited sites; classifier bindings/types are exclusively from stored program".into();
        Ok(report)
    }
}
