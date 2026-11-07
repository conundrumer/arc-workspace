//! Complete clause-body views for the study's native table evaluator.
//! A view retains the exact body (including its final constraint/NOT) and
//! its binding context. Decoder partial-body approximations are unsuitable.
use crate::check::{CheckCache, CheckedProgram, SolverClauses, check_shared_program};
use crate::program::path::{NodePath, NodeRef, node_at};
use crate::program::*;
use crate::registry::Registry;
use crate::stream::{DecodeSettings, Vocabulary, written_stream};
use crate::study::{StudyProgram, diagnostics_text};
use std::sync::Arc;

pub fn checked_body(
    program: &StudyProgram,
    at: &NodePath,
    settings: &DecodeSettings,
    registry: &Registry,
) -> Result<CheckedProgram, String> {
    checked_body_cached(program,at,settings,registry,&mut CheckCache::default())
}

pub fn checked_body_cached(
    program:&StudyProgram,at:&NodePath,settings:&DecodeSettings,registry:&Registry,cache:&mut CheckCache,
)->Result<CheckedProgram,String> {
    let vocabulary = Vocabulary::new(registry, settings);
    let written = written_stream(program.checked(), &vocabulary).map_err(|d| diagnostics_text(&[d]))?;
    checked_body_from_written(program,at,registry,cache,&written)
}

/// Construct a body view using the source program's once-written ordering.
pub fn checked_body_from_written(
    program:&StudyProgram,at:&NodePath,registry:&Registry,cache:&mut CheckCache,written:&crate::stream::WrittenStream,
)->Result<CheckedProgram,String> {
    let top = at.0.first().ok_or("body path has no form")?.0 as usize;
    let form = program
        .program()
        .value()
        .forms
        .get(top)
        .ok_or("body form is absent")?;
    let relative = NodePath(at.0[1..].into());
    let Some(NodeRef::Body(body)) = node_at(NodeRef::from(form), &relative) else {
        return Err("path is not a clause body".into());
    };
    let mut before = Vec::new();
    match form {
        Form::Instance(instance) => {
            if let Some(key) = &instance.value().key {
                let key = key.value();
                // Keyed inputs are children of the key, after its body.
                if relative.0.len() > 2 && relative.0[0].0 == 0 && relative.0[1].0 > 0 {
                    before.extend(key.key.body.value().conjuncts.iter().map(unkeyed));
                }
            }
        }
        Form::Choose(choose) => {
            let choose = choose.value();
            let part = choose
                .parts()
                .nth(relative.0[0].0 as usize)
                .ok_or("CHOOSE part is absent")?;
            if matches!(part, ChoosePart::From) && choose.from_inside_for
                || matches!(part, ChoosePart::Never(_))
            {
                if let Some(rows) = &choose.rows {
                    before.extend(rows.body.value().conjuncts.iter().map(unkeyed));
                }
            }
            if matches!(part, ChoosePart::Never(_)) {
                before.extend(choose.from.value().conjuncts.iter().cloned());
            }
        }
        Form::RigidDet(rigid) => {
            if rigid.value().instance.is_some()
                && relative.0[0].0 == rigid.value().position(RigidDetPart::Instance)
            {
                if let Some(key) = &rigid.value().key {
                    before.extend(key.body.value().conjuncts.iter().map(unkeyed));
                }
            }
        }
        _ => {}
    }
    before.extend(body.conjuncts.iter().map(unkeyed));
    let body = Body {
        conjuncts: before.into(),
    };
    let mut columns =
        crate::read::columns::slot_columns(crate::read::columns::made_labels(&body), 0);
    let keyword = match form {
        Form::Clause(c) => c.value().keyword,
        _ => match program
            .checked()
            .program
            .form_side(&NodePath::top(top as u32))
        {
            Some(crate::resolver::Side::TaskWide) => ClauseKeyword::Det,
            Some(crate::resolver::Side::PerInput) => ClauseKeyword::Rule,
            None => return Err("clause owner has no checked evaluation side".into()),
        },
    };
    let proposers = match form {
        Form::Clause(c) if body.conjuncts.is_empty() => {
            columns = c.value().columns.clone();
            c.value().proposers.clone()
        }
        _ => Arc::from([]),
    };
    let mut forms = Vec::new();
    for f in &written.forms {
        if f.path == NodePath::top(top as u32) {
            break;
        }
        let Some(
            NodeRef::Clause(_) | NodeRef::Instance(_) | NodeRef::Choose(_) | NodeRef::RigidDet(_),
        ) = node_at(NodeRef::Program(program.program().value()), &f.path)
        else {
            return Err("unsupported form in clause's dependency prefix".into());
        };
        forms.push(program.program().value().forms[f.path.0[0].0 as usize].clone());
    }
    let mut fresh = 0;
    let name = loop {
        let name = ProgramRelation::Declared(RelationName(DeclaredName::Written(
            format!("__study_body_{fresh}").into(),
        )));
        if !written.relations.contains(&name) {
            break name;
        }
        fresh += 1;
    };
    forms.push(Form::Clause(Node::new(Clause {
        keyword,
        derives: name,
        gloss: None,
        proposers,
        body: Node::new(body),
        ones: Arc::from([]),
        set: false,
        columns,
    })));
    let ast = Node::new(Program {
        forms: forms.into(),
    });
    let resolved = crate::resolver::resolve(
        &ast,
        None,
        &crate::resolver::SolverScope::default(),
        registry,
    );
    if resolved
        .diagnostics
        .iter()
        .any(|d| d.severity == crate::diagnostic::Severity::Error)
    {
        return Err(diagnostics_text(&resolved.diagnostics));
    }
    let resolved = Arc::new(resolved.value);
    let clauses = SolverClauses::of_shared_program(Arc::clone(&resolved));
    check_shared_program(resolved, &clauses, registry, cache)
        .map_err(|d| diagnostics_text(&d))
}

pub(crate) fn unkeyed(conjunct: &Conjunct) -> Conjunct {
    fn site(s: &Site) -> Site {
        Site {
            column: s.column.clone(),
            value: SiteValue {
                args: s
                    .value
                    .args
                    .iter()
                    .map(|a| match a {
                        SiteArg::Label(l) => SiteArg::Label(label(*l)),
                        SiteArg::NamedLabel { name, label: l } => SiteArg::NamedLabel {
                            name: name.clone(),
                            label: label(*l),
                        },
                        SiteArg::Field(s) => SiteArg::Field(site(s)),
                    })
                    .collect(),
            },
        }
    }
    fn label(l: LabelUse) -> LabelUse {
        match l {
            LabelUse::Key(l) => LabelUse::Fresh(l),
            l => l,
        }
    }
    fn atom(a: &Node<Atom>) -> Node<Atom> {
        Node::new(Atom {
            relation: a.value().relation.clone(),
            sites: a.value().sites.iter().map(site).collect(),
        })
    }
    let body = |b: &Node<Body>| {
        Node::new(Body {
            conjuncts: b.value().conjuncts.iter().map(unkeyed).collect(),
        })
    };
    match conjunct {
        Conjunct::Atom(a) => Conjunct::Atom(atom(a)),
        Conjunct::Not(Negated::Atom(a)) => Conjunct::Not(Negated::Atom(atom(a))),
        Conjunct::Not(Negated::Form(f)) => Conjunct::Not(Negated::Form(Arc::new(unkeyed(f)))),
        Conjunct::Constraint(c) => Conjunct::Constraint(*c),
        Conjunct::Or(bs) => Conjunct::Or(bs.iter().map(body).collect()),
        Conjunct::If {
            test,
            then,
            otherwise,
        } => Conjunct::If {
            test: body(test),
            then: body(then),
            otherwise: body(otherwise),
        },
        Conjunct::All { domain, body: b } => Conjunct::All {
            domain: body(domain),
            body: body(b),
        },
    }
}
