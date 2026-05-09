# Souffle: undocumented features

Two features have been merged into Souffle but are not on the official documentation site (`souffle-lang.github.io`): **user-defined aggregates** and **lattices**. Both were contributed by Julien Henry (MathWorks); both ship in the released compiler and are exercised by tests in `tests/interface/`. This doc describes how to use them.

The features are related. Lattices give you automatic lub/glb on relation attributes; user-defined aggregates give you manual fold-with-a-stateful-functor over an aggregate body. Both rely on a stateful functor folding over tuples.

## User-defined aggregates

Source: PR [#2282](https://github.com/souffle-lang/souffle/pull/2282) (merged 2022-10-17), follow-up fix [#2456](https://github.com/souffle-lang/souffle/pull/2456).

### Syntax

```
result = @@<functor> <expr> : <init>, { <body> }
```

The `@@` (double-at) prefix distinguishes a user-defined aggregate from a normal user-defined functor call (`@functor(...)`).

- `<functor>` is a previously declared `.functor`.
- `<expr>` is the per-tuple expression accumulated into the result.
- `<init>` is the initial value of the accumulator.
- `<body>` is a normal aggregate body — a conjunction of literals — that ranges over the tuples being folded.

Operationally:

```
acc = init
for each solution of body:
    acc = functor(acc, expr)
return acc
```

### Functor requirements

The functor must be declared `stateful` and take exactly two arguments. The first argument is the accumulator; the second is the per-tuple expression. The return type and second-argument type need not match the accumulator type — only the first argument and the return have to share a type.

```
.functor lub(acc:Interval, x:Interval):Interval stateful
.functor lub_number(acc:Interval, x:number):Interval stateful
```

`stateful` is required because the accumulator is typically a record (ADT or struct), and only stateful functors receive the `RecordTable*` needed to construct one.

### Worked example

From `tests/interface/aggregates/aggregates.dl`:

```souffle
.type AbstractValue = [lb:number, ub:number]

.decl A(i:AbstractValue)
A([x, x+1]) :- x = range(0, 1000).

.functor lub(i1:AbstractValue, i2:AbstractValue):AbstractValue stateful

.decl B(i:AbstractValue)
.output B
B(i) :- i = @@lub x : [0,0], {A(x)}.
```

`B` ends up holding a single fact: the interval `[0, 1000]`, computed by folding `lub` over all tuples in `A` starting from `[0,0]`.

The C++ side is a regular stateful functor:

```cpp
extern "C" souffle::RamDomain lub(
        souffle::SymbolTable*, souffle::RecordTable* rt,
        souffle::RamDomain a, souffle::RamDomain b) {
    const souffle::RamDomain* i1 = rt->unpack(a, 2);
    const souffle::RamDomain* i2 = rt->unpack(b, 2);
    souffle::RamDomain res[2] = {std::min(i1[0], i2[0]), std::max(i1[1], i2[1])};
    return rt->pack(res, 2);
}
```

### Determinism caveat

Souffle does not check that the functor is commutative or associative. If it isn't, the result depends on the order in which the body's solutions are visited, which is an implementation detail. Use only commutative and associative functors when you care about deterministic output.

## Lattices

Source: PR [#2438](https://github.com/souffle-lang/souffle/pull/2438) (merged 2023-11-15), fix [#2442](https://github.com/souffle-lang/souffle/pull/2442). The design follows Flix (Madsen et al., PLDI 2016).

### Declaration

A lattice is attached to an existing type with `.lattice`:

```souffle
.lattice MyType<> {
    Bottom -> $myBottom(),
    Top    -> $myTop(),
    Lub    -> @mylub(_, _),
    Glb    -> @myglb(_, _)
}
```

- The `<>` after the type name is required syntax.
- Each operator maps to either a constant expression (`Bottom`, `Top`) or a user-defined functor reference (`Lub`, `Glb`).
- `Lub` and `Glb` must be regular user-defined functors — `@name(_, _)` — taking two values of the lattice type and returning one. They are typically `stateful` if the lattice type is a record/ADT.
- `Bottom` and `Top` are optional; `Lub` and `Glb` drive the runtime semantics.

The grammar parses a fifth operator `Leq` (defined in `src/ast/Lattice.h`'s `LatticeOperator` enum), but no tests exercise it; behavior is unverified.

### Use in relations

A relation attribute opts into lattice semantics by writing the type with a `<>` suffix:

```souffle
.decl R(key:number, v:MyType<>)   // v is a lattice attribute
.decl S(key:number, v:MyType)     // v is a regular attribute
```

Both forms reference the same underlying type `MyType`. Only the `<>` form triggers automatic lub/glb behavior.

### Semantics

**In the head — automatic lub.** A relation with a lattice attribute holds at most one tuple per distinct assignment of its non-lattice attributes. Multiple derivations producing the same non-lattice key are merged via `Lub`. With `MyType` an ADT with constructors `$a()` and `$b()`:

```souffle
R(0, $a()).
R(0, $b()).
```

results in a single tuple `R(0, lub($a(), $b()))`.

A tuple `R(k, v)` semantically also implies `R(k, v')` for every `v' <= v` in the lattice — but only the maximal element is materialized.

**In the body — automatic glb.** When the same variable is bound to a lattice attribute in multiple body atoms, the binding is the `Glb` of the values:

```souffle
.decl P(v:MyType<>)
.decl Q(v:MyType<>)
.decl A(v:MyType<>)

A(x) :- P(x), Q(x).
```

If `P(a)` and `Q(b)` hold, `x` is bound to `glb(a, b)`, and `A(glb(a, b))` is derived.

### Worked example: Sign domain

From `tests/interface/lattice1/lattice1.dl`:

```souffle
.type Sign = Bottom{} | Negative{} | Positive{} | Top{} | Zero{}

.functor lub(a:Sign, b:Sign):Sign stateful
.functor glb(a:Sign, b:Sign):Sign stateful

.lattice Sign<> {
    Bottom -> $Bottom(),
    Top    -> $Top(),
    Lub    -> @lub(_, _),
    Glb    -> @glb(_, _)
}

.decl S(n:number, s:Sign<>)
S(n, $Zero())     :- N(n), n = 0.
S(n, $Positive()) :- N(n), n > 0.
S(n, $Negative()) :- N(n), n < 0.
```

`S` will contain at most one tuple per `n`, with the sign joined under `Lub` if multiple clauses fire.

### Worked example: Interval analysis

From `tests/interface/lattice2/lattice2.dl` — a small abstract interpreter for value-range analysis. Recursion through a lattice-typed relation converges via repeated lub:

```souffle
Values(n, v, $I($Cst(x), $Cst(x))) :- Set_Value(n, v, x).

Values(n, v, i) :-
    Values(pred, v, i),
    Edge(pred, n),
    !Set_Value(n, v, _),
    !Increment_Value(n, v, _),
    !Restrict_Value(n, v, _).

Values(n, v, @incr(i, x)) :-
    Values(pred, v, i),
    Edge(pred, n),
    Increment_Value(n, v, x).
```

Each iteration of the fixpoint produces new candidate intervals, and the lattice machinery keeps only the lub per `(n, v)` key. The fixpoint terminates as long as the lattice has finite ascending chains (or the abstract operators include widening).

## How they relate

| | User-defined aggregate | Lattice |
| --- | --- | --- |
| Triggered by | `@@functor x : init, {body}` in a clause | `.lattice T<>` block + `T<>` attribute |
| Where the fold runs | Inside one clause body | Across all derivations of a relation |
| Functor signature | `(acc, x) -> acc`, stateful | `(a, b) -> result` for both Lub and Glb |
| Initial value | Per call site, written inline | Optional `Bottom` in lattice block |

Use a user-defined aggregate when the fold is local to a single rule (e.g., "give me the join of all `x` such that `P(x)`"). Use a lattice when you want every clause that derives into the relation to participate in the same join automatically.

## Limits and gotchas

- Lub/Glb in a `.lattice` block must reference user-defined functors; intrinsic operators (`min`, `max`, `+`) cannot be used. Wrap them in a one-line functor if needed.
- The `Leq` lattice operator is parsed but lacks test coverage — don't depend on it.
- Stateful functors are linked from C++ (`SOUFFLE_USE_LIBFFI` controls dynamic loading). The interpreter and synthesizer paths both work, but the C++ side must be compiled and discoverable at run time.
- Souffle does not verify that your operators actually form a lattice. If `Lub` isn't commutative, associative, and idempotent — or if `Glb` doesn't satisfy the dual properties — output becomes order-dependent.

## References

- [PR #2282 — User defined aggregate](https://github.com/souffle-lang/souffle/pull/2282)
- [PR #2456 — fix `apply` on user-defined aggregate `init`](https://github.com/souffle-lang/souffle/pull/2456)
- [PR #2438 — Lattice support](https://github.com/souffle-lang/souffle/pull/2438)
- [PR #2442 — Lattice fix](https://github.com/souffle-lang/souffle/pull/2442)
- Tests: `tests/interface/aggregates/`, `tests/interface/lattice{1,2,3}/` in souffle-lang/souffle.
- Source: `src/ast/UserDefinedAggregator.{h,cpp}`, `src/ast/Lattice.{h,cpp}`, `src/parser/parser.yy` (rules `lattice_decl`, `lattice_operator`, and the `@@` aggregator branch).
- Flix paper: Madsen, Yee, Lhoták, *From Datalog to FLIX: A Declarative Language for Fixed Points on Lattices*, PLDI 2016.
