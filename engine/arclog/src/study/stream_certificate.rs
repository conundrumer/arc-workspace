//! Complete native stream-path proofs for checked representations.
use super::StudyProgram;
use crate::eval::read_coordinates::SourceColumn;
use crate::mutation::path_json;
use crate::program::{
    LabelUse,
    path::{NodePath, NodeRef, node_at},
};
use crate::registry::Registry;
use crate::stream::{Control, DecodeSettings, Token, Vocabulary, WrittenStream};
use serde_json::{Value, json};

fn path(v: &Value) -> Result<NodePath, String> {
    Ok(NodePath(
        v.as_array()
            .ok_or("scalar path is absent")?
            .iter()
            .map(|n| {
                n.as_u64()
                    .and_then(|v| u32::try_from(v).ok())
                    .map(crate::program::path::PathStep)
                    .ok_or("scalar path is invalid")
            })
            .collect::<Result<Vec<_>, _>>()?
            .into(),
    ))
}

/// A scalar emission is proved by the checker/resolver and this writer run,
/// rather than by the depth or spelling of its AST address.
fn scalar(
    program: &StudyProgram,
    registry: &Registry,
    written: &WrittenStream,
    index: usize,
) -> Result<Value, String> {
    let at = written.paths.get(index).ok_or("writer path index absent")?;
    let root = NodeRef::Program(program.program().value());
    let Some(NodeRef::Label(used)) = node_at(root, at) else {
        return Err("differing emission is not a native scalar label".into());
    };
    let native = program.typed_sites(registry)?;
    let arguments = native.json["arguments"]
        .as_array()
        .ok_or("native typed argument inventory absent")?;
    let rows = arguments
        .iter()
        .filter(|v| v["path"] == path_json(at))
        .collect::<Vec<_>>();
    let [argument] = rows.as_slice() else {
        return Err("differing scalar has no unique native typed argument".into());
    };
    let site = path(&argument["site_path"])?;
    let scope = path(&argument["scope_path"])?;
    let occurrence = (0..at.0.len())
        .rev()
        .map(|n| NodePath(at.0[..n].into()))
        .find(|p| node_at(root, p).and_then(|n| n.atom()).is_some())
        .ok_or("scalar has no enclosing native atom read")?;
    let (input, lifted, column, source) = super::render_correspondence::scalar_read_coordinates(
        program.checked(),
        at,
        &site,
        &occurrence,
    );
    let Some(SourceColumn::Position(header)) = source else {
        return Err("scalar requires unsupported or entry-axis read coordinates".into());
    };
    let scalar_column = column.ok_or("native scalar column is unresolved")?;
    let reads = written
        .tokens
        .iter()
        .enumerate()
        .filter(|(i, (token, _))| {
            written.paths.get(*i) == Some(&occurrence)
                && matches!(
                    token,
                    Token::Relation(_) | Token::Fact(_) | Token::Lib(_) | Token::Proposer(_)
                )
        })
        .map(|(i, _)| i)
        .collect::<Vec<_>>();
    let [read] = reads.as_slice() else {
        return Err("scalar atom has no unique native relation emission".into());
    };
    let forms = written
        .forms
        .iter()
        .filter(|f| f.tokens.contains(&index))
        .collect::<Vec<_>>();
    let [form] = forms.as_slice() else {
        return Err("scalar has no unique native writer form".into());
    };
    let (role, id) = match used {
        LabelUse::Fresh(id) => ("fresh", Some(id)),
        LabelUse::Join(id) => ("join", Some(id)),
        LabelUse::Key(id) => ("key", Some(id)),
        LabelUse::Zero => ("zero", None),
    };
    let slot = if let Some(id) = id {
        let slots = form
            .labels
            .iter()
            .enumerate()
            .filter(|(_, v)| *v == id)
            .map(|(n, _)| n as u32)
            .collect::<Vec<_>>();
        let [slot] = slots.as_slice() else {
            return Err("scalar label lacks a unique writer declaration slot".into());
        };
        Some(*slot)
    } else {
        None
    };
    let token = &written.tokens[index].0;
    let valid = match (used, token, slot) {
        (LabelUse::Zero, Token::Control(Control::Zero), None) => true,
        (LabelUse::Join(_), Token::Label(n), Some(slot)) => *n == slot,
        (LabelUse::Fresh(_), Token::Control(Control::Fresh), Some(slot))
        | (LabelUse::Key(_), Token::Control(Control::Key), Some(slot)) => {
            written
                .tokens
                .get(index + 1)
                .is_some_and(|(t, _)| *t == Token::Label(slot))
                && written.paths.get(index + 1) == Some(at)
        }
        (LabelUse::Fresh(_) | LabelUse::Key(_), Token::Label(n), Some(slot)) => *n == slot,
        _ => false,
    };
    if !valid {
        return Err("token is not the native scalar role/slot emission".into());
    }
    if role == "zero" && argument["literal"].is_null() {
        return Err("native zero lacks typed literal meaning".into());
    }
    Ok(
        json!({"argument":argument,"scope_path":path_json(&scope),"role":role,"label_slot":slot,
        "atom_path":path_json(&occurrence),"atom_token_index":read,"scalar_column":scalar_column,
        "header_column":header,"input":input,"lifted":lifted}),
    )
}

impl StudyProgram {
    /// Exact arrays are retained even when different native record wrappers
    /// require a scalar-emission proof instead of identical raw AST paths.
    pub fn representation_certificate(
        &self,
        source: &StudyProgram,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<Value, String> {
        let current = self.decode_stream(registry, settings)?;
        let before = source.decode_stream(registry, settings)?;
        let a = self
            .written_stream(registry, settings)
            .map_err(|e| e.message.to_string())?;
        let b = source
            .written_stream(registry, settings)
            .map_err(|e| e.message.to_string())?;
        let ids_equal = current.ids == before.ids;
        let model_equal = current.model == before.model;
        let lengths_equal = current.ids.len() == before.ids.len()
            && current.ids.len() == current.model.len()
            && current.ids.len() == current.paths.len()
            && before.ids.len() == before.model.len()
            && before.ids.len() == before.paths.len();
        let tokens_equal = a.tokens == b.tokens;
        let map = if current.paths != before.paths {
            super::render_correspondence::trace_paths(source.checked(), self.checked(), &b, &a)
        } else {
            Default::default()
        };
        let mut differences = Vec::new();
        let mut unproven = Vec::new();
        if !(ids_equal && model_equal && lengths_equal && tokens_equal) {
            unproven.push(json!({"stage":"stream_identity","reason":"native ids, emitters or lengths differ"}));
        }
        for (index, (at, old)) in current.paths.iter().zip(&before.paths).enumerate() {
            if at == old {
                continue;
            }
            let proof = (|| {
                if !(ids_equal && model_equal && lengths_equal && tokens_equal) {
                    return Err("stream identity differs".to_string());
                }
                let now = scalar(self, registry, &a, index)?;
                let prior = scalar(source, registry, &b, index)?;
                let scope = path(&now["scope_path"])?;
                let prior_scope = path(&prior["scope_path"])?;
                if map.get(&scope) != Some(&prior_scope) {
                    return Err(
                        "native scalar scopes lack a unique writer-trace correspondence".into(),
                    );
                }
                for key in [
                    "role",
                    "label_slot",
                    "atom_token_index",
                    "scalar_column",
                    "header_column",
                    "input",
                    "lifted",
                ] {
                    if now[key] != prior[key] {
                        return Err(format!("native scalar {key} differs"));
                    }
                }
                if now["argument"]["type_identity"] != prior["argument"]["type_identity"]
                    || now["argument"]["literal"] != prior["argument"]["literal"]
                {
                    return Err("native scalar physical type or literal meaning differs".into());
                }
                Ok(json!({"current":now,"source":prior}))
            })();
            let (status, proof) = match proof {
                Ok(v) => ("complete", v),
                Err(reason) => {
                    unproven.push(json!({"stage":"scalar_path","index":index,"reason":reason}));
                    ("unsupported", Value::Null)
                }
            };
            differences.push(json!({"index":index,"token_id":current.ids.get(index),"model":current.model.get(index),
                "current_path":path_json(at),"source_path":path_json(old),"status":status,"proof":proof}));
        }
        let vocabulary = Vocabulary::new(registry, settings);
        Ok(
            json!({"schema":"arclog-study-stream-path-certificate-v1","status":if unproven.is_empty(){"complete"}else{"unsupported"},
            "current_program_sexp":self.sexp(registry),"source_program_sexp":source.sexp(registry),
            "vocabulary":{"tokens":(0..vocabulary.len()).map(|n|vocabulary.token(n as u32).map(|t|format!("{t:?}"))).collect::<Vec<_>>(),"settings":format!("{settings:?}")},
            "current_stream":{"ids":current.ids,"model":current.model,"paths":current.paths.iter().map(path_json).collect::<Vec<_>>()},
            "source_stream":{"ids":before.ids,"model":before.model,"paths":before.paths.iter().map(path_json).collect::<Vec<_>>()},
            "ids_equal":ids_equal,"model_equal":model_equal,"paths_equal":current.paths==before.paths,"lengths_equal":lengths_equal,
            "differences":differences,"unproven":unproven}),
        )
    }
}
