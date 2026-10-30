//! Rehydrate a stored exact edit identity. No RNG, domain search or repair.
use super::*;

fn text(v: &Value) -> Result<&str, String> {
    v.as_str().ok_or_else(|| "identity: expected string".into())
}
fn integer(v: &Value) -> Result<u32, String> {
    v.as_u64()
        .and_then(|v| v.try_into().ok())
        .ok_or_else(|| "identity: expected u32".into())
}
fn array(v: &Value) -> Result<&[Value], String> {
    v.as_array()
        .map(Vec::as_slice)
        .ok_or_else(|| "identity: expected array".into())
}
fn path(v: &Value) -> Result<NodePath, String> {
    Ok(NodePath(
        array(v)?
            .iter()
            .map(|v| integer(v).map(crate::program::path::PathStep))
            .collect::<Result<Vec<_>, _>>()?
            .into(),
    ))
}
fn name(v: &Value) -> Result<DeclaredName, String> {
    Ok(if let Some(n) = v.get("name") {
        DeclaredName::Written(text(n)?.into())
    } else {
        DeclaredName::Slot(integer(&v["slot"])?)
    })
}
fn column(v: &Value) -> Result<ColumnName, String> {
    Ok(if let Some(n) = v.get("name") {
        ColumnName::Written(text(n)?.into())
    } else {
        ColumnName::Slot(integer(&v["slot"])?)
    })
}
fn label(v: &Value) -> Result<LabelUse, String> {
    for (key, kind) in [("fresh", 0), ("join", 1), ("key", 2)] {
        if let Some(n) = v.get(key) {
            let n = LabelId(integer(n)?);
            return Ok(match kind {
                0 => LabelUse::Fresh(n),
                1 => LabelUse::Join(n),
                _ => LabelUse::Key(n),
            });
        }
    }
    if v["zero"] == true {
        Ok(LabelUse::Zero)
    } else {
        Err("identity: invalid label use".into())
    }
}
fn site(v: &Value) -> Result<Site, String> {
    let args = array(&v["args"])?
        .iter()
        .map(|a| {
            if let Some(s) = a.get("site") {
                Ok(SiteArg::Field(site(s)?))
            } else if let Some(c) = a.get("field") {
                Ok(SiteArg::NamedLabel {
                    name: column(c)?,
                    label: label(&a["label"])?,
                })
            } else {
                Ok(SiteArg::Label(label(a)?))
            }
        })
        .collect::<Result<Vec<_>, String>>()?;
    // Empty record/Unit sites are legitimate inside a serialized whole block.
    // The canonical native checker still authenticates their declared schema.
    Ok(Site {
        column: column(&v["column"])?,
        value: SiteValue { args: args.into() },
    })
}
fn relation(v: &Value) -> Result<RelationRef, String> {
    if let Some(f) = v.get("fact") {
        return Ok(RelationRef::Fact(match text(f)? {
            "Input" => FactRelation::Input,
            "ExInput" => FactRelation::ExInput,
            "ExOutput" => FactRelation::ExOutput,
            _ => return Err("identity: unknown fact".into()),
        }));
    }
    if let Some(n) = v.get("lib") {
        return Ok(RelationRef::Lib(crate::registry::LibName(text(n)?.into())));
    }
    if let Some(n) = v.get("declared") {
        return Ok(RelationRef::Declared(RelationName(name(n)?)));
    }
    if let Some(n) = v.get("input_port") {
        return Ok(RelationRef::DefinedPort(PortName(text(n)?.into())));
    }
    let owner = &v["owner"];
    let of = if let Some(n) = owner.get("instance") {
        OutputOwner::Instance(InstanceName(name(n)?))
    } else {
        OutputOwner::RigidDet(RigidDetName(name(&owner["rigid"])?))
    };
    let steps = array(&v["path"])?
        .iter()
        .map(|s| {
            Ok(if let Some(n) = s.get("port") {
                OutputStep::Port(PortName(text(n)?.into()))
            } else if let Some(n) = s.get("part") {
                OutputStep::Part(name(n)?)
            } else if s["pose"] == true {
                OutputStep::Pose
            } else {
                return Err("identity: invalid output step".into());
            })
        })
        .collect::<Result<Vec<_>, String>>()?;
    Ok(RelationRef::Output(OutputName {
        of,
        path: steps.into(),
    }))
}
fn constraint_label(v: &Value) -> Result<ConstraintLabel, String> {
    Ok(ConstraintLabel {
        label: LabelId(integer(&v["label"])?),
        fresh: v["fresh"]
            .as_bool()
            .ok_or_else(|| "identity: expected fresh boolean".to_string())?,
    })
}
fn body(v:&Value)->Result<Node<Body>,String> {
    Ok(Node::new(Body{conjuncts:array(v)?.iter().map(conjunct).collect::<Result<Vec<_>,_>>()?.into()}))
}
fn conjunct(v: &Value) -> Result<Conjunct, String> {
    Ok(match text(&v["node"])? {
        "atom" | "not_atom" => {
            let atom = Node::new(Atom {
                relation: relation(&v["relation"])?,
                sites: array(&v["sites"])?
                    .iter()
                    .map(site)
                    .collect::<Result<Vec<_>, _>>()?
                    .into(),
            });
            if v["node"] == "atom" {
                Conjunct::Atom(atom)
            } else {
                Conjunct::Not(Negated::Atom(atom))
            }
        }
        "comparison" => Conjunct::Constraint(Constraint {
            op: match text(&v["op"])? {
                "Eq" => ConstraintOp::Eq,
                "Ne" => ConstraintOp::Ne,
                "Lt" => ConstraintOp::Lt,
                "Le" => ConstraintOp::Le,
                "Gt" => ConstraintOp::Gt,
                "Ge" => ConstraintOp::Ge,
                _ => return Err("identity: invalid comparison".into()),
            },
            first: constraint_label(&v["first"])?,
            second: if v["second"]["zero"] == true {
                Operand::Zero
            } else {
                Operand::Label(constraint_label(&v["second"])?)
            },
        }),
        "or"=> {
            let branches=array(&v["branches"])?;
            if branches.is_empty() {return Err("identity: empty OR".into())}
            Conjunct::Or(branches.iter().map(body).collect::<Result<Vec<_>,_>>()?.into())
        },
        "if"=>Conjunct::If{test:body(&v["test"])?,then:body(&v["then"])?,otherwise:body(&v["otherwise"])?},
        "all"=>Conjunct::All{domain:body(&v["domain"])?,body:body(&v["body"])?},
        "not_form"=>Conjunct::Not(Negated::Form(Arc::new(conjunct(&v["inner"])?))),
        _ => return Err("identity: unknown conjunct kind".into()),
    })
}

impl StudyProgram {
    pub fn construct_identity(
        &self,
        identity: &Value,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<ValidMutant, String> {
        let original = self.construct_identity_at_source(identity, registry, settings);
        if original.is_ok() || self.layout().is_none() {
            return original;
        }
        // A stored decode sexp spells anonymous slots as engine names. Reading
        // that display text creates written names/field wrappers, not the
        // original decode AST. Recover the decode AST through the engine's own
        // stream grammar/binder, never by guessing names or remapping JSON.
        let decoded=self.decode_source(registry,settings)?;
        decoded.construct_identity_at_source(identity,registry,settings)
            .map_err(|e|format!("stored identity failed on both source AST and its native decode AST: {e}; source: {}",original.unwrap_err()))
    }

    pub(super) fn construct_identity_at_source(
        &self,
        identity: &Value,
        registry: &Registry,
        settings: &DecodeSettings,
    ) -> Result<ValidMutant, String> {
        let point = self
            .mutation_points()
            .into_iter()
            .find(|p| {
                Some(path_json(&p.body)) == identity.get("body").cloned()
                    && Some(path_json(&p.clause)) == identity.get("clause").cloned()
            })
            .ok_or_else(|| "identity: mutation point does not belong to gold".to_string())?;
        let source = &identity["source"];
        let origin = Source {
            revision: text(&source["revision"])?.into(),
            task: text(&source["task"])?.into(),
            case: text(&source["case"])?.into(),
        };
        if origin.revision.is_empty() || origin.task.is_empty() || origin.case.is_empty() {
            return Err("identity: source fields must be nonempty".into());
        }
        let mut edits = Vec::new();
        let mut unique = BTreeSet::new();
        for e in array(&identity["edits"])? {
            let at = path(&e["at"])?;
            let block=blocks::is_site(self,&point,&at) && e["kind"]=="block";
            if (!point.atoms.contains(&at) && !block) || !unique.insert(at.clone()) {
                return Err("identity: repeated or non-atom edit path".into());
            }
            let replacement = if e["replacement"].is_null() {
                None
            } else {
                Some(conjunct(&e["replacement"])?)
            };
            let expected = text(&e["kind"])?;
            // Check this stored primitive at the original site; never enumerate
            // K-edit assignments or draw a replacement for it.
            let choices=if expected=="block" {
                blocks::alternatives(self,&at,registry,&mut DrawStats::default())?
            } else if expected.starts_with("typed_") {
                typed::additions(self,&at,registry,&mut DrawStats::default())?
            } else {alternatives(self, &at, "mixed", registry, true)?};
            let choice = choices.into_iter()
                .find(|(c, kind)| {
                    let kind = if kind.starts_with("argument_") {
                        "argument"
                    } else if kind.starts_with("block_") {"block"} else {
                        *kind
                    };
                    kind == expected
                        && c.as_ref().map(conjunct_json) == replacement.as_ref().map(conjunct_json)
                })
                .ok_or_else(|| {
                    format!("identity: replacement is not a legal original-site choice at {at:?}")
                })?;
            let kind = match expected {
                "argument" => "argument",
                "relation" => "relation",
                "comparison" => "comparison",
                "delete" => "delete",
                "typed_interface" => "typed_interface",
                "typed_equality" => "typed_equality",
                "block" => "block",
                _ => return Err("identity: unknown edit kind".into()),
            };
            edits.push(AtomEdit {
                at,
                replacement: choice.0,
                kind,
                choice_kind: choice.1,
            });
        }
        if edits.is_empty() {
            return Err("identity: K must be positive".into());
        }
        edits.sort_by(|a, b| a.at.cmp(&b.at));
        let ast = edit::apply(self.program(), &edits)?;
        if !declared_in_scopes(NodeRef::Program(ast.value())) {
            return Err("identity: deleted declaration still used".into());
        }
        let top = point.body.0[0].0 as usize;
        if !named_bindings_hold(&ast.value().forms[top], &NodePath::top(top as u32), self.layout()) {
            return Err("identity: edit would shadow an unchanged gold name".into());
        }
        let certified =
            StudyProgram::from_program(ast, edit::layout(self.layout(), &edits), registry)?
                .preserve_gold_names(self, registry);
        self.checked().check_held_det_interfaces(certified.checked()).map_err(|e| e.to_string())?;
        certified.decode_stream(registry, settings)?;
        let mut names_cache = CheckCache::over(self.mutation_check_base(registry)?);
        certified.check_preserved_name_binding(registry, settings, &mut names_cache)?;
        let spec = MutationSpec {
            source: Arc::clone(self.checked()),
            point,
            origin,
            edits,
            certified,
        };
        if spec.identity() != *identity {
            return Err("identity: unknown/noncanonical fields or edit order".into());
        }
        Ok(ValidMutant { spec })
    }
}


/// Decode historical edit addresses/payloads for metadata only. This never
/// admits a new mutation or consults the current sampler's choice domain.
pub(super) fn metadata_edits(program: &StudyProgram, identity: &Value) -> Result<Vec<AtomEdit>, String> {
    let point=program.mutation_points().into_iter().find(|p|
        Some(path_json(&p.body))==identity.get("body").cloned()
        && Some(path_json(&p.clause))==identity.get("clause").cloned())
        .ok_or("recorded edit body/clause is absent from this source representation")?;
    let mut edits=Vec::new();let mut seen=BTreeSet::new();
    for e in array(&identity["edits"])? {
        let at=path(&e["at"])?;
        if (!point.atoms.contains(&at)&&!blocks::is_site(program,&point,&at))||!seen.insert(at.clone()) {
            return Err(format!("recorded edit has repeated/non-atom address {at:?}"));
        }
        let replacement=if e["replacement"].is_null(){None}else{Some(conjunct(&e["replacement"]) ?)};
        edits.push(AtomEdit{at,replacement,kind:"metadata",choice_kind:"recorded"});
    }
    if edits.is_empty(){return Err("recorded edit list is empty".into())}
    edits.sort_by(|a,b|a.at.cmp(&b.at));Ok(edits)
}
