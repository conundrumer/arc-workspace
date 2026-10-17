//! The syntax tree holds each of these kinds of form of the corpus,
//! `work/arclog/gen/`: a nested `ALT`, a parameter of several grids, a
//! solver with a `representative` line, a `DEMONSTRATED` form, and a
//! `RIGID_DET` form whose parts are keyed. Each test builds by hand the tree
//! of one solver's form of that kind, from the public constructors, so a
//! kind the node types cannot hold fails to compile. The trees follow the
//! corpus as it stands, its reads of Quotient's `representative` included,
//! which the next conversion of the corpus replaces; a read of any output
//! is an `OutputName`, so the kinds these trees hold stay the same.
//!
//! A `Solver` tree holds what the reader reads from a solver's `.arclog`
//! and `.arcdata` files: the claims, the tree of alts, the arcdata records,
//! and `cases()`. No test reads the corpus: each names its solver's task
//! id.
//!
//! TODO: The reader stage deletes this file once its round-trip check over
//! `work/arclog/gen/` passes, since that check covers these forms.

use std::sync::Arc;

use arclog::layout::Layout;
use arclog::program::*;
use arclog::registry::LibName;
use arclog::solver::Solver;

fn site(column: &str, value: LabelUse) -> Site {
    Site { column: ColumnName::Written(column.into()), value: SiteValue::Label(value) }
}

fn fresh(column: &str, label: LabelId) -> Site {
    site(column, LabelUse::Fresh(label))
}

fn join(column: &str, label: LabelId) -> Site {
    site(column, LabelUse::Join(label))
}

fn key(column: &str, label: LabelId) -> Site {
    site(column, LabelUse::Key(label))
}

fn fields(column: &str, sites: Vec<Site>) -> Site {
    Site { column: ColumnName::Written(column.into()), value: SiteValue::Fields(sites.into()) }
}

fn derived(name: &str) -> RelationRef {
    RelationRef::Declared(relation_name(name))
}

fn written(name: &str) -> DeclaredName {
    DeclaredName::Written(name.into())
}

fn relation_name(name: &str) -> RelationName {
    RelationName(written(name))
}

fn output_name(of: OutputOwner, path: &[&str]) -> OutputName {
    OutputName {
        of,
        path: path.iter().map(|p| OutputStep::Port(PortName((*p).into()))).collect(),
    }
}

fn output(instance: &str, port: &str) -> RelationRef {
    RelationRef::Output(output_name(OutputOwner::Instance(InstanceName(written(instance))), &[port]))
}

fn rigid_output(form: &str, part: &str) -> OutputName {
    OutputName {
        of: OutputOwner::RigidDet(RigidDetName(written(form))),
        path: Arc::from([OutputStep::Part(written(&format!("&{part}")))]),
    }
}

fn lib(name: &str) -> RelationRef {
    RelationRef::Lib(LibName(name.into()))
}

fn atom(relation: RelationRef, sites: Vec<Site>) -> Conjunct {
    Conjunct::Atom(Node::new(Atom { relation, sites: sites.into() }))
}

fn not(relation: RelationRef, sites: Vec<Site>) -> Conjunct {
    Conjunct::Not(Negated::Atom(Node::new(Atom { relation, sites: sites.into() })))
}

fn constraint(op: ConstraintOp, first: LabelId, second: LabelId) -> Conjunct {
    Conjunct::Constraint(Constraint {
        op,
        first: ConstraintLabel { label: first, fresh: false },
        second: Operand::Label(ConstraintLabel { label: second, fresh: false }),
    })
}

fn body(conjuncts: Vec<Conjunct>) -> Node<Body> {
    Node::new(Body { conjuncts: conjuncts.into() })
}

fn or(branches: Vec<Vec<Conjunct>>) -> Conjunct {
    Conjunct::Or(branches.into_iter().map(body).collect())
}

fn relation_columns(columns: &[(&str, LabelId)]) -> Arc<[RelationColumn]> {
    columns
        .iter()
        .map(|(name, label)| RelationColumn { name: ColumnName::Written((*name).into()), label: *label })
        .collect()
}

fn key_body(columns: &[(&str, LabelId)], conjuncts: Vec<Conjunct>) -> KeyBody {
    KeyBody { body: body(conjuncts), columns: relation_columns(columns) }
}

fn clause(
    keyword: ClauseKeyword,
    name: &str,
    proposers: &[&str],
    columns: &[(&str, LabelId)],
    conjuncts: Vec<Conjunct>,
) -> Form {
    Form::Clause(Node::new(Clause {
        keyword,
        derives: ProgramRelation::Declared(relation_name(name)),
        gloss: None,
        proposers: proposers.iter().map(|p| LibName((*p).into())).collect(),
        body: body(conjuncts),
        ones: Arc::from([]),
        columns: relation_columns(columns),
    }))
}

fn rule(name: &str, columns: &[(&str, LabelId)], conjuncts: Vec<Conjunct>) -> Form {
    clause(ClauseKeyword::Rule, name, &[], columns, conjuncts)
}

fn det(name: &str, columns: &[(&str, LabelId)], conjuncts: Vec<Conjunct>) -> Form {
    clause(ClauseKeyword::Det, name, &[], columns, conjuncts)
}

fn input(name: &str, head: Vec<Site>, conjuncts: Vec<Conjunct>) -> Node<InstanceInput> {
    Node::new(InstanceInput { name: PortName(name.into()), head: head.into(), body: body(conjuncts) })
}

type Key<'a> = (&'a [(&'a str, LabelId)], Vec<Conjunct>, Vec<Node<InstanceInput>>);

fn init(name: &str, component: &str, key: Option<Key<'_>>, inputs: Vec<Node<InstanceInput>>) -> Form {
    Form::Instance(Node::new(Instance {
        name: InstanceName(written(name)),
        component: LibName(component.into()),
        key: key.map(|(columns, conjuncts, inputs)| Node::new(KeyClause { key: key_body(columns, conjuncts), inputs: inputs.into() })),
        inputs: inputs.into(),
    }))
}

fn program(forms: Vec<Form>) -> Node<Program> {
    Node::new(Program { forms: forms.into() })
}

fn color(digit: u8) -> DataValue {
    DataValue::Integer(i32::from(digit))
}

fn param(name: ProgramRelation, columns: Vec<TypeName>, value: ParamValue) -> Node<Param> {
    Node::new(Param { name, columns: columns.into(), value })
}

fn arcdata(representative: Option<Representative>, params: Vec<Node<Param>>) -> Node<Arcdata> {
    Node::new(Arcdata { representative, params: params.into(), excludes: Arc::from([]), witness_records: Arc::from([]) })
}

fn solver(task_id: &str, program: Node<Program>, arcdata: Node<Arcdata>, representative: Option<Arc<Solver>>) -> Solver {
    Solver { task_id: task_id.into(), program, arcdata, layout: Layout::default(), representative }
}

/// The grid that `text` draws, one row per line and cells separated by
/// spaces, as the arcdata file writes it: `_` gives no row, and `1` the
/// marker `1`.
fn marks(text: &str) -> Grid {
    Grid {
        rows: text
            .lines()
            .map(str::trim)
            .filter(|line| !line.is_empty())
            .map(|line| line.split(' ').map(|cell| (cell == "1").then_some(DataValue::Integer(1))).collect())
            .collect(),
        anchor: None,
    }
}

/// 25d8a9c8: `$Count` of `$detect` holds the nested `ALT $SliceMap`, the
/// combination of `$Count` and `$SliceMap`.
#[test]
fn nested_alt() {
    let (col, p_across, n, e, p, p_inner) = (LabelId(0), LabelId(1), LabelId(2), LabelId(3), LabelId(4), LabelId(5));
    // The key body's `Col` is local to it, and the input's is another variable.
    let member_col = LabelId(6);
    let slice_palette = init(
        "&slice_palette",
        "Cardinality",
        Some((&[("P_across", p_across)], 
            vec![atom(derived("&cell_split"), vec![fresh("Col", col), key("P_across", p_across)])],
            vec![input(
                "member",
                vec![join("m", member_col)],
                vec![atom(derived("&cell_split"), vec![fresh("Col", member_col), join("P_across", p_across)])],
            )],
        )),
        vec![],
    );
    let ncolors = rule("&ncolors", &[("P_across", p_across), ("N", n)], vec![atom(output("&slice_palette", "size"), vec![fields("key", vec![fresh("P_across", p_across)]), fresh("N", n)])]);
    let count_color = det(
        "&count_color", &[("E", e), ("P_across", p_across), ("N", n), ("Col", col)],
        vec![
            atom(derived("&ncolors"), vec![fresh("E", e), fresh("P_across", p_across), fresh("N", n)]),
            atom(derived("&slice_out"), vec![join("E", e), join("P_across", p_across), fresh("Col", col)]),
        ],
    );
    let count_output = rule(
        "&output", &[("P", p), ("P_across", p_across), ("N", n), ("Col", col)],
        vec![
            atom(derived("&cell_split"), vec![fresh("P", p), fresh("P_across", p_across)]),
            atom(derived("&ncolors"), vec![join("P_across", p_across), fresh("N", n)]),
            atom(derived("&count_color"), vec![join("N", n), fresh("Col", col)]),
        ],
    );
    let count_template = det(
        "&count_template", &[("E", e), ("P_across", p_across), ("N", n), ("P_inner", p_inner), ("Col", col)],
        vec![
            atom(derived("&ncolors"), vec![fresh("E", e), fresh("P_across", p_across), fresh("N", n)]),
            atom(
                derived("&slice_out"),
                vec![join("E", e), join("P_across", p_across), fresh("P_inner", p_inner), fresh("Col", col)],
            ),
        ],
    );
    let slice_map_output = rule(
        "&output", &[("P", p), ("P_inner", p_inner), ("P_across", p_across), ("N", n), ("Col", col)],
        vec![
            atom(derived("&cell_split"), vec![fresh("P", p), fresh("P_inner", p_inner), fresh("P_across", p_across)]),
            atom(derived("&ncolors"), vec![join("P_across", p_across), fresh("N", n)]),
            atom(derived("&count_template"), vec![join("N", n), join("P_inner", p_inner), fresh("Col", col)]),
        ],
    );
    let slice_map = Node::new(Alt {
        name: AltsName("$SliceMap".into()),
        items: vec![AltItem::Form(count_template), AltItem::Form(slice_map_output)].into(),
    });
    let count = Node::new(Alt {
        name: AltsName("$Count".into()),
        items: vec![
            AltItem::Form(slice_palette),
            AltItem::Form(ncolors),
            AltItem::Form(count_color),
            AltItem::Form(count_output),
            AltItem::Alt(slice_map),
        ]
        .into(),
    });
    let detect = Node::new(Alts {
        name: AltsName("$detect".into()),
        gloss: Text("detect".into()),
        concept: AltsName("$PairExist".into()),
        alts: vec![count].into(),
    });
    let tree = program(vec![Form::Alts(detect)]);

    let Form::Alts(alts) = &tree.value().forms[0] else { panic!("not an ALTS form") };
    let AltItem::Alt(nested) = &alts.value().alts[0].value().items[4] else { panic!("no nested ALT") };
    assert_eq!(nested.value().name, AltsName("$SliceMap".into()));
}

/// 009d5c81: `&key_member` gives a grid per Ident, each after its value.
#[test]
fn param_of_several_grids() {
    let key_member = param(
        ProgramRelation::Declared(relation_name("&key_member")),
        vec![TypeName::Ident, TypeName::Position],
        ParamValue::Grids(
            vec![
                GridRows {
                    before: vec![DataValue::Integer(0)].into(),
                    grid: marks(
                        "
                        _ 1 _
                        1 1 1
                        _ 1 _
                        ",
                    ),
                },
                GridRows {
                    before: vec![DataValue::Integer(1)].into(),
                    grid: marks(
                        "
                        1 _ 1
                        _ 1 _
                        1 1 1
                        ",
                    ),
                },
                GridRows {
                    before: vec![DataValue::Integer(2)].into(),
                    grid: marks(
                        "
                        1 1 1
                        1 _ 1
                        _ 1 _
                        ",
                    ),
                },
            ]
            .into(),
        ),
    );
    let key_out = param(
        ProgramRelation::Declared(relation_name("&key_out")),
        vec![TypeName::Ident, TypeName::Color],
        ParamValue::Rows(
            [(0, 2), (1, 3), (2, 7)]
                .iter()
                .map(|(ident, digit)| Arc::from([DataValue::Integer(*ident), color(*digit)]))
                .collect(),
        ),
    );
    let records = arcdata(None, vec![key_member, key_out]);

    let ParamValue::Grids(grids) = &records.value().params[0].value().value else { panic!("not grids") };
    assert_eq!(grids.len(), 3);
}

/// The `&output` clause that 0d3d703e and b1948b0a share.
fn swap_output() -> Form {
    let (p, col_in, col) = (LabelId(0), LabelId(1), LabelId(2));
    rule(
        "&output", &[("P", p), ("Col", col)],
        vec![or(vec![
            vec![
                atom(RelationRef::Fact(FactRelation::Input), vec![fresh("P", p), fresh("Col", col_in)]),
                atom(derived("&mapping"), vec![join("C_from", col_in), fresh("C_to", col)]),
            ],
            vec![
                atom(RelationRef::Fact(FactRelation::Input), vec![join("P", p), join("Col", col)]),
                not(derived("&mapping"), vec![join("C_from", col)]),
            ],
        ])],
    )
}

/// b1948b0a: `(representative 0d3d703e)`, read under 0d3d703e's solver.
#[test]
fn representative_solver() {
    let (e, p, col_in, col_out) = (LabelId(0), LabelId(1), LabelId(2), LabelId(3));
    let pair = init(
        "&pair",
        "Quotient",
        None,
        vec![input(
            "edge",
            vec![join("a", col_in), join("b", col_out)],
            vec![
                atom(RelationRef::Fact(FactRelation::ExInput), vec![fresh("E", e), fresh("P", p), fresh("Col", col_in)]),
                atom(RelationRef::Fact(FactRelation::ExOutput), vec![join("E", e), join("P", p), fresh("Col", col_out)]),
                constraint(ConstraintOp::Ne, col_in, col_out),
            ],
        )],
    );
    let (c1, c2) = (LabelId(0), LabelId(1));
    let swap = det(
        "&swap", &[("C2", c2), ("C1", c1)],
        vec![
            atom(output("&pair", "representative"), vec![fresh("a", c2), fresh("b", c1)]),
            constraint(ConstraintOp::Ne, c1, c2),
        ],
    );
    let (c_from, c_to) = (LabelId(0), LabelId(1));
    let mapping = rule(
        "&mapping", &[("C_from", c_from), ("C_to", c_to)],
        vec![or(vec![
            vec![atom(derived("&swap"), vec![fresh("C1", c_from), fresh("C2", c_to)])],
            vec![atom(derived("&swap"), vec![join("C1", c_to), join("C2", c_from)])],
        ])],
    );
    let swap_rows = param(
        ProgramRelation::Declared(relation_name("&swap")),
        vec![TypeName::Color, TypeName::Color],
        ParamValue::Rows(
            [(1, 5), (2, 6), (3, 4), (8, 9)].iter().map(|(a, b)| Arc::from([color(*a), color(*b)])).collect(),
        ),
    );
    let representative = Arc::new(solver(
        "0d3d703e",
        program(vec![pair, swap, mapping, swap_output()]),
        arcdata(None, vec![swap_rows]),
        None,
    ));

    let mapping_rows = param(
        ProgramRelation::Declared(relation_name("&mapping")),
        vec![TypeName::Color, TypeName::Color],
        ParamValue::Rows(vec![Arc::from([color(6), color(2)])].into()),
    );
    let tree = solver(
        "b1948b0a",
        program(vec![clause(ClauseKeyword::Det, "&mapping", &["ChangedPairs"], &[], vec![]), swap_output()]),
        arcdata(Some(Representative { task_id: "0d3d703e".into(), case: None }), vec![mapping_rows]),
        Some(representative),
    );

    assert_eq!(tree.representative.as_ref().map(|r| &*r.task_id), Some("0d3d703e"));
}

/// The `&prediction` clause that each demonstrated rule of 4c7dc4dd ends in.
/// Its labels take ids from `base` on, apart from those of the other forms of
/// its demonstrated rule.
fn prediction(base: u32) -> Form {
    let (pan, pan1, pan3, p_inner, col) =
        (LabelId(base), LabelId(base + 1), LabelId(base + 2), LabelId(base + 3), LabelId(base + 4));
    rule(
        "&prediction", &[("Pan", pan), ("Pan1", pan1), ("Pan3", pan3), ("P_inner", p_inner), ("Col", col)],
        vec![
            atom(derived("&slot"), vec![fresh("Answer", pan), fresh("Shown", pan1)]),
            atom(derived("&predict"), vec![fresh("Pan", pan3), fresh("P_inner", p_inner), fresh("Col", col)]),
        ],
    )
}

fn demo_rule(name: &str, forms: Vec<Form>) -> Node<DemoRule> {
    Node::new(DemoRule { name: DemoRuleName(name.into()), fields: Arc::from([]), text: None, forms: forms.into() })
}

/// 4c7dc4dd: `&catalog`, a keyed `DEMONSTRATED` form with three rules, and
/// the `&output` that reads it.
#[test]
fn demonstrated() {
    let (pan, pan1, pan3, p_inner, col, pan2) = (LabelId(0), LabelId(1), LabelId(2), LabelId(3), LabelId(4), LabelId(5));
    let slot_answer = |done: Option<LabelId>| {
        let mut sites = vec![join("Answer", pan), join("Shown", pan1)];
        sites.extend(done.map(|d| fresh("Done", d)));
        atom(derived("&slot"), sites)
    };
    let key_clause = Node::new(KeyClause {
        key: key_body(&[("Pan", pan), ("Pan1", pan1)], vec![or(vec![
            vec![
                atom(derived("&slot"), vec![key("Answer", pan), key("Shown", pan1)]),
                atom(derived("&content"), vec![fresh("Pan", pan3)]),
                atom(derived("&pval"), vec![join("Pan", pan3), fresh("P_inner", p_inner), fresh("Col", col)]),
            ],
            vec![slot_answer(Some(pan2))],
        ])]),
        // The key body's local labels and each input's are other variables.
        inputs: vec![
            input(
                "value",
                vec![join("o", LabelId(6)), join("i", LabelId(7)), join("v", LabelId(8))],
                vec![
                    slot_answer(None),
                    atom(derived("&content"), vec![fresh("Pan", LabelId(6))]),
                    atom(derived("&pval"), vec![join("Pan", LabelId(6)), fresh("P_inner", LabelId(7)), fresh("Col", LabelId(8))]),
                ],
            ),
            input("demonstration", vec![join("o", pan1), join("o2", LabelId(9))], vec![slot_answer(Some(LabelId(9)))]),
        ]
        .into(),
    });

    let extend = {
        let (pan, p, q, da) = (LabelId(0), LabelId(1), LabelId(2), LabelId(3));
        let spread = init(
            "&spread",
            "Quotient",
            None,
            vec![input(
                "edge",
                vec![fields("a", vec![join("Pan", pan), join("P", p)]), fields("b", vec![join("Pan", pan), join("P", q)])],
                vec![
                    atom(derived("&content"), vec![fresh("Pan", pan)]),
                    atom(derived("&pval"), vec![join("Pan", pan), fresh("P_inner", p)]),
                    atom(derived("&pval"), vec![join("Pan", pan), fresh("P_inner", q)]),
                    atom(lib("diag_axis_elem"), vec![fresh("Da", da)]),
                    atom(lib("same_line"), vec![join("A", da), join("P", p), join("Q", q)]),
                ],
            )],
        );
        let (pan, p_mark, col, r_pan, r_p, p_inner) = (LabelId(10), LabelId(11), LabelId(12), LabelId(13), LabelId(14), LabelId(15));
        // The key body's local labels and the input's are other variables.
        let (member_p_mark, member_col, member_r_pan, member_r_p) = (LabelId(16), LabelId(17), LabelId(18), LabelId(19));
        let representatives = |p_mark: LabelId, r_pan: LabelId, r_p: LabelId, inner: LabelUse| {
            vec![
                atom(
                    output("&spread", "representative"),
                    vec![
                        fields("a", vec![join("Pan", pan), join("P", p_mark)]),
                        fields("b", vec![fresh("Pan", r_pan), fresh("P", r_p)]),
                    ],
                ),
                atom(
                    output("&spread", "representative"),
                    vec![
                        fields("a", vec![join("Pan", pan), site("P", inner)]),
                        fields("b", vec![join("Pan", r_pan), join("P", r_p)]),
                    ],
                ),
            ]
        };
        let mut key_body = vec![atom(derived("&mark"), vec![key("Pan", pan), fresh("P_inner", p_mark), fresh("Col", col)])];
        key_body.extend(representatives(p_mark, r_pan, r_p, LabelUse::Key(p_inner)));
        let mut member_body =
            vec![atom(derived("&mark"), vec![join("Pan", pan), fresh("P_inner", member_p_mark), fresh("Col", member_col)])];
        member_body.extend(representatives(member_p_mark, member_r_pan, member_r_p, LabelUse::Join(p_inner)));
        let canvas = init(
            "&canvas",
            "Singleton",
            Some((&[("Pan", pan), ("P_inner", p_inner)], key_body, vec![input("member", vec![join("v", member_col)], member_body)])),
            vec![],
        );
        let (pan, p_inner, v, h, col) = (LabelId(20), LabelId(21), LabelId(22), LabelId(23), LabelId(24));
        let predict = rule(
            "&predict", &[("Pan", pan), ("P_inner", p_inner), ("V", v), ("H", h), ("Col", col)],
            vec![
                atom(derived("&pval"), vec![fresh("Pan", pan), fresh("P_inner", p_inner), fresh("Col", v)]),
                atom(derived("&hole"), vec![fresh("C", h)]),
                or(vec![
                    vec![
                        constraint(ConstraintOp::Eq, v, h),
                        atom(
                            output("&canvas", "value"),
                            vec![fields("key", vec![join("Pan", pan), join("P_inner", p_inner)]), fresh("v", col)],
                        ),
                    ],
                    vec![constraint(ConstraintOp::Ne, v, h), constraint(ConstraintOp::Eq, col, h)],
                ]),
            ],
        );
        demo_rule("$Extend", vec![spread, canvas, predict, prediction(30)])
    };

    let span = {
        let (key_label, a) = (LabelId(0), LabelId(1));
        let flank_axis = rule(
            "&flank_axis", &[("Key", key_label), ("A", a)],
            vec![atom(derived("&panel"), vec![fresh("Pan", key_label)]), atom(lib("axis_elem"), vec![fresh("A", a)])],
        );
        let (pan, p_inner, a, d, p) = (LabelId(10), LabelId(11), LabelId(12), LabelId(13), LabelId(14));
        let flank = init(
            "&flank",
            "Ray",
            Some((&[("Pan", pan)], 
                vec![or(vec![
                    vec![atom(derived("&mark"), vec![key("Pan", pan), fresh("P_inner", p_inner)])],
                    vec![
                        atom(derived("&flank_axis"), vec![join("Key", pan), fresh("A", a)]),
                        atom(lib("axis4_of"), vec![fresh("D", d), join("A", a)]),
                    ],
                    vec![
                        atom(derived("&flank_axis"), vec![join("Key", pan)]),
                        atom(RelationRef::Fact(FactRelation::Input), vec![fresh("P", p)]),
                    ],
                ])],
                vec![
                    // Each input's fresh labels are variables of their own.
                    input(
                        "source",
                        vec![join("P", LabelId(15))],
                        vec![atom(derived("&mark"), vec![join("Pan", pan), fresh("P_inner", LabelId(15))])],
                    ),
                    input(
                        "node",
                        vec![join("P", LabelId(16))],
                        vec![
                            atom(derived("&flank_axis"), vec![join("Key", pan)]),
                            atom(RelationRef::Fact(FactRelation::Input), vec![fresh("P", LabelId(16))]),
                        ],
                    ),
                    input(
                        "dir",
                        vec![join("D", LabelId(18))],
                        vec![
                            atom(derived("&flank_axis"), vec![join("Key", pan), fresh("A", LabelId(17))]),
                            atom(lib("axis4_of"), vec![fresh("D", LabelId(18)), join("A", LabelId(17))]),
                        ],
                    ),
                ],
            )),
            vec![],
        );
        let (key_label, p, a, d, o) = (LabelId(20), LabelId(21), LabelId(22), LabelId(23), LabelId(24));
        let flank_between = rule(
            "&flank_between", &[("Key", key_label), ("P", p), ("A", a), ("D", d), ("O", o)],
            vec![
                atom(derived("&pval"), vec![fresh("Pan", key_label), fresh("P_inner", p)]),
                atom(derived("&flank_axis"), vec![join("Key", key_label), fresh("A", a)]),
                atom(lib("axis4_of"), vec![fresh("D", d), join("A", a)]),
                atom(lib("dir8_opposite"), vec![join("D", d), fresh("D2", o)]),
                atom(output("&flank", "ray"), vec![fields("key", vec![join("Pan", key_label)]), join("P", p), join("D", d)]),
                atom(output("&flank", "ray"), vec![fields("key", vec![join("Pan", key_label)]), join("P", p), join("D", o)]),
            ],
        );
        let (pan, p_inner, col, h) = (LabelId(30), LabelId(31), LabelId(32), LabelId(33));
        let predict = rule(
            "&predict", &[("Pan", pan), ("P_inner", p_inner), ("Col", col)],
            vec![or(vec![
                vec![atom(derived("&mark"), vec![fresh("Pan", pan), fresh("P_inner", p_inner), fresh("Col", col)])],
                vec![
                    atom(derived("&pval"), vec![join("Pan", pan), join("P_inner", p_inner), fresh("Col", h)]),
                    atom(derived("&hole"), vec![join("C", h)]),
                    Conjunct::If {
                        test: body(vec![atom(derived("&flank_between"), vec![join("Key", pan), join("P", p_inner)])]),
                        then: body(vec![atom(derived("&own"), vec![join("Pan", pan), join("Col", col)])]),
                        otherwise: body(vec![constraint(ConstraintOp::Eq, col, h)]),
                    },
                ],
            ])],
        );
        demo_rule("$Span", vec![flank_axis, flank, flank_between, predict, prediction(40)])
    };

    let reflect = {
        let (pan, p_inner) = (LabelId(0), LabelId(1));
        let window = init(
            "&window",
            "BoundingBox",
            Some((&[("Pan", pan)], 
                vec![atom(derived("&mark"), vec![key("Pan", pan), fresh("P_inner", p_inner)])],
                vec![input("cell", vec![join("P", LabelId(2))], vec![atom(derived("&mark"), vec![join("Pan", pan), fresh("P_inner", LabelId(2))])])],
            )),
            vec![],
        );
        let (pan, p_inner2, col, b, d, p_inner) = (LabelId(10), LabelId(11), LabelId(12), LabelId(13), LabelId(14), LabelId(15));
        let repeat = rule(
            "&repeat", &[("Pan", pan), ("P_inner2", p_inner2), ("Col", col), ("B", b), ("D", d), ("P_inner", p_inner)],
            vec![
                atom(derived("&pval"), vec![fresh("Pan", pan), fresh("P_inner", p_inner2), fresh("Col", col)]),
                atom(output("&window", "box"), vec![fields("key", vec![join("Pan", pan)]), fresh("B", b)]),
                atom(lib("inside"), vec![join("A", p_inner2), join("B", b)]),
                atom(lib("d4_elem"), vec![fresh("D", d)]),
                atom(lib("apply"), vec![join("D", d), join("P", p_inner2), fresh("P_out", p_inner)]),
            ],
        );
        let (pan, p_inner, col) = (LabelId(20), LabelId(21), LabelId(22));
        let image = init(
            "&image",
            "Singleton",
            Some((&[("Pan", pan), ("P_inner", p_inner)], 
                vec![atom(derived("&repeat"), vec![key("Pan", pan), key("P_inner", p_inner), fresh("Col", col)])],
                vec![input(
                    "member",
                    vec![join("v", LabelId(23))],
                    vec![atom(derived("&repeat"), vec![join("Pan", pan), join("P_inner", p_inner), fresh("Col", LabelId(23))])],
                )],
            )),
            vec![],
        );
        let (pan, p_inner, col) = (LabelId(30), LabelId(31), LabelId(32));
        let predict = rule(
            "&predict", &[("Pan", pan), ("P_inner", p_inner), ("Col", col)],
            vec![
                atom(derived("&pval"), vec![fresh("Pan", pan), fresh("P_inner", p_inner)]),
                or(vec![
                    vec![atom(
                        output("&image", "value"),
                        vec![fields("key", vec![join("Pan", pan), join("P_inner", p_inner)]), fresh("v", col)],
                    )],
                    vec![
                        not(derived("&repeat"), vec![join("Pan", pan), join("P_inner", p_inner)]),
                        atom(derived("&own"), vec![join("Pan", pan), join("Col", col)]),
                    ],
                ]),
            ],
        );
        demo_rule("$Reflect", vec![window, repeat, image, predict, prediction(40)])
    };

    let catalog = Form::Demonstrated(Node::new(Demonstrated {
        name: relation_name("&catalog"),
        key: Some(key_clause),
        inputs: Arc::from([]),
        rules: vec![extend, span, reflect].into(),
    }));
    let (pan, pan1, p, col) = (LabelId(0), LabelId(1), LabelId(2), LabelId(3));
    let output_clause = rule(
        "&output", &[("Pan", pan), ("Pan1", pan1), ("P", p), ("Col", col)],
        vec![
            atom(derived("&slot"), vec![fresh("Answer", pan), fresh("Shown", pan1)]),
            atom(
                derived("&catalog"),
                vec![fields("key", vec![join("Pan", pan), join("Pan1", pan1)]), join("o", pan), fresh("i", p), fresh("v", col)],
            ),
        ],
    );
    let tree = program(vec![catalog, output_clause]);

    let Form::Demonstrated(form) = &tree.value().forms[0] else { panic!("not a DEMONSTRATED form") };
    assert_eq!(form.value().rules.len(), 3);
}

/// 409aa875: `&glyph`, a `RIGID_DET` form whose parts are keyed by an
/// Ident, the parts' stored rows, and the key clause of `&occ` that reads a
/// part at a pose.
#[test]
fn rigid_det_keyed_by_ident() {
    // Each part's labels are fresh in it, so each part has variables of its own.
    let part = |name: &str, id: LabelId, column: &str, label: LabelId| {
        Node::new(Atom { relation: derived(name), sites: vec![fresh("Id", id), fresh(column, label)].into() })
    };
    let glyph = Form::RigidDet(Node::new(RigidDet {
        name: RigidDetName(written("&glyph")),
        key: None,
        instance: None,
        parts: vec![
            part("&shape", LabelId(0), "P", LabelId(1)),
            part("&apex", LabelId(2), "P", LabelId(3)),
            part("&aim", LabelId(4), "D", LabelId(5)),
        ]
        .into(),
    }));
    let (pose, id, s, p) = (LabelId(0), LabelId(1), LabelId(2), LabelId(3));
    let shape = |sites: Vec<Site>| atom(RelationRef::Output(rigid_output("&glyph", "shape")), sites);
    let occ = init(
        "&occ",
        "Occurrences",
        Some((&[("D", pose), ("Id", id)], 
            vec![or(vec![
                vec![shape(vec![key("Pose", pose), key("Id", id), fresh("P", s)])],
                vec![shape(vec![join("Pose", pose), join("Id", id)]), atom(derived("&ink"), vec![fresh("P", p)])],
            ])],
            vec![
                // The key body's local `S` and `P` and each input's are other variables.
                input(
                    "cell",
                    vec![join("P", LabelId(4))],
                    vec![shape(vec![join("Pose", pose), join("Id", id)]), atom(derived("&ink"), vec![fresh("P", LabelId(4))])],
                ),
                input("shape", vec![join("P", LabelId(5))], vec![shape(vec![join("Pose", pose), join("Id", id), fresh("P", LabelId(5))])]),
            ],
        )),
        vec![],
    );
    let tree = program(vec![glyph, occ]);
    let stored = |part: &str, grids: Vec<Grid>| {
        param(
            ProgramRelation::Output(rigid_output("&glyph", part)),
            vec![TypeName::Ident, TypeName::Position],
            ParamValue::Grids(
                grids
                    .into_iter()
                    .enumerate()
                    .map(|(i, grid)| GridRows { before: vec![DataValue::Integer(i as i32)].into(), grid })
                    .collect(),
            ),
        )
    };
    let records = arcdata(
        None,
        vec![
            stored(
                "shape",
                vec![
                    marks(
                        "
                        1 1
                        1 _
                        ",
                    ),
                    marks(
                        "
                        _ 1 _
                        1 _ 1
                        ",
                    ),
                ],
            ),
            stored(
                "apex",
                vec![
                    marks(
                        "
                        1 _
                        _ _
                        ",
                    ),
                    marks(
                        "
                        _ 1 _
                        _ _ _
                        ",
                    ),
                ],
            ),
        ],
    );

    let Form::RigidDet(form) = &tree.value().forms[0] else { panic!("not a RIGID_DET form") };
    assert_eq!(form.value().parts.len(), 3);
    assert!(matches!(&records.value().params[0].value().name, ProgramRelation::Output(_)));
}
