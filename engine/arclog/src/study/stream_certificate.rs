//! Complete native stream-path proofs for checked representations.
use super::StudyProgram;
use crate::eval::read_coordinates::SourceColumn;
use crate::mutation::path_json;
use crate::program::{
    LabelUse,
    path::{NodePath, NodeRef, node_at},
};
use crate::registry::Registry;
use crate::stream::{Control, DecodeSettings, Emitter, Token, Vocabulary, WrittenStream};
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
    let occurrence = (0..at.0.len())
        .rev()
        .map(|n| NodePath(at.0[..n].into()))
        .find(|p| node_at(root, p).and_then(|n| n.atom()).is_some());
    let coordinates = if let Some(occurrence) = occurrence {
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
        json!({"binding_kind":"atom_read","binding_path":path_json(&occurrence),
            "atom_path":path_json(&occurrence),"atom_token_index":read,"scalar_column":scalar_column,
            "header_column":header,"input":input,"lifted":lifted,"header_binding":null})
    } else {
        header_coordinates(program, registry, written, index, at, argument, form)?
    };
    let mut proof =
        json!({"argument":argument,"scope_path":path_json(&scope),"role":role,"label_slot":slot});
    proof
        .as_object_mut()
        .ok_or("scalar proof is not an object")?
        .extend(
            coordinates
                .as_object()
                .ok_or("scalar coordinates are not an object")?
                .clone(),
        );
    Ok(proof)
}

/// INIT heads are bindings, not atom reads. Resolve their fields through the
/// same native port projection used by body/table metadata, then authenticate
/// the port and logical-column emissions of this exact writer run.
fn header_coordinates(
    program: &StudyProgram,
    registry: &Registry,
    written: &WrittenStream,
    index: usize,
    at: &NodePath,
    argument: &Value,
    form: &crate::stream::write::WrittenForm,
) -> Result<Value, String> {
    let root = NodeRef::Program(program.program().value());
    let input_at = (0..at.0.len())
        .rev()
        .map(|n| NodePath(at.0[..n].into()))
        .find(|p| matches!(node_at(root, p), Some(NodeRef::InstanceInput(_))))
        .ok_or("scalar has neither an enclosing atom nor an INIT input header")?;
    let Some(NodeRef::InstanceInput(input)) = node_at(root, &input_at) else {
        return Err("native INIT input is absent".into());
    };
    let head_index =
        at.0.get(input_at.0.len())
            .ok_or("INIT scalar has no head site")?
            .0 as usize;
    let head = input
        .head
        .get(head_index)
        .ok_or("INIT scalar is outside its header")?;
    let owner = NodePath(at.0.iter().take(1).copied().collect());
    let Some(NodeRef::Instance(instance)) = node_at(root, &owner) else {
        return Err("INIT header has no instance owner".into());
    };
    let Some(crate::registry::LibEntry::Component(component)) = registry.entry(&instance.component)
    else {
        return Err("INIT header component is absent".into());
    };
    let port = component
        .inputs
        .iter()
        .position(|p| p.port.name == input.name)
        .ok_or("INIT header port is absent")?;
    let (labels, types, key, columns) = crate::eval::init_form::render_metadata::input_projection(
        program.checked(),
        &owner,
        input,
        registry,
    )?;
    let column_path = argument["column_path"]
        .as_array()
        .ok_or("INIT typed field path is absent")?;
    if column_path.first() != Some(&super::render::column(&head.column)) {
        return Err("INIT typed field is outside its head column".into());
    }
    let found = columns
        .iter()
        .filter(|c| !c.key && super::render::column(&c.name) == column_path[0])
        .collect::<Vec<_>>();
    let [logical] = found.as_slice() else {
        return Err("INIT header has no unique logical port column".into());
    };
    let field = match &logical.fields {
        None if column_path.len() == 1 && logical.width == 1 => 0,
        Some(fields) if column_path.len() == 2 => fields
            .iter()
            .position(|f| super::render::column(f) == column_path[1])
            .ok_or("INIT header field is absent from native binding")?,
        _ => return Err("INIT header scalar field shape is unsupported".into()),
    };
    if field >= logical.width {
        return Err("INIT header field exceeds its native width".into());
    }
    let physical = logical.row_start + field;
    let label = labels
        .get(physical)
        .ok_or("INIT header physical column is absent")?;
    if label.map(|v| json!(v.0)) != Some(argument["label_id"].clone()) {
        return Err("INIT header scalar label differs from native projection".into());
    }
    let ty = types
        .get(physical)
        .ok_or("INIT header physical type is absent")?;
    let container = NodePath(input_at.0[..input_at.0.len() - 1].into());
    let emission = |path: &NodePath, column: u32| -> Result<usize, String> {
        let positions = written
            .tokens
            .iter()
            .enumerate()
            .filter(|(i, (token, emitter))| {
                *emitter == Emitter::Engine
                    && *token == Token::Column(column)
                    && written.paths.get(*i) == Some(path)
            })
            .map(|(i, _)| i)
            .collect::<Vec<_>>();
        let [position] = positions.as_slice() else {
            return Err("INIT header has no unique engine column emission".into());
        };
        if !form.tokens.contains(position) || *position >= index {
            return Err("INIT header engine column does not precede its scalar".into());
        }
        Ok(*position)
    };
    let port_token = emission(&container, 1 + port as u32)?;
    let column_token = emission(&input_at, logical.ordinal as u32)?;
    if port_token >= column_token {
        return Err("INIT header port/column writer order differs".into());
    }
    let key_slots = key
        .iter()
        .map(|id| {
            let slots = form
                .labels
                .iter()
                .enumerate()
                .filter(|(_, v)| *v == id)
                .map(|(i, _)| i)
                .collect::<Vec<_>>();
            match slots.as_slice() {
                [slot] => Ok(*slot),
                _ => Err("INIT group key has no unique writer label slot".to_string()),
            }
        })
        .collect::<Result<Vec<_>, _>>()?;
    Ok(
        json!({"binding_kind":"init_header","binding_path":path_json(&input_at),
        "atom_path":null,"atom_token_index":null,"scalar_column":physical,"header_column":key.len()+physical,
        "input":false,"lifted":false,"header_binding":{"component":instance.component.0,"port":input.name.0,
            "port_index":port,"port_token_index":port_token,"logical_column":logical.ordinal,
            "logical_column_name":super::render::column(&logical.name),"logical_column_token_index":column_token,
            "field":logical.fields.as_ref().and_then(|v|v.get(field)).map(super::render::column),
            "physical_type":super::render_correspondence::type_json(ty),"group_key_label_slots":key_slots}}),
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
                if now["binding_kind"] == "init_header" {
                    let binding = path(&now["binding_path"])?;
                    let prior_binding = path(&prior["binding_path"])?;
                    if map.get(&binding) != Some(&prior_binding) {
                        return Err(
                            "native INIT headers lack a unique writer-trace correspondence".into(),
                        );
                    }
                }
                for key in [
                    "binding_kind",
                    "header_binding",
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
