# Structure of the search

The objects of the search over programs and the maps between them. The [Type contract](../sample-build/contract.md) gives their types, and the [Feature specification](feature-spec.md) gives the feature language.

## Objects

- **Evidence** E: a task's train pairs and test inputs.
- **Query**: a clause of arclog. It reads relations and derives relations.
- **State** S: a finite set of queries closed under reads, so a DAG. S ≤ S′ means S ⊆ S′, so states form a partial order with the base tables at the bottom.
- **Goal set** G: the states that hold an `OUT` form whose output equals each train output, at some assignment.

## Maps

- **Evaluation**: E and S give a database D(S), with one table per relation, indexed by assignment, example and model. Where S ≤ S′, D(S′) extends D(S), and the tables of S do not change. A new `DET` refines the assignment index.
- **Feature**: f(D, t, e) is a number or a boolean, for a table t at an example e. A feature is a query with an aggregate at its root, so a feature is a query reduced to a value.
- **Levels**: a feature's value stands at one level of the contract, and a level above it takes a symmetric function over an index.
    - `TableVector`: one table at one assignment, and the base tables.
    - `AssignmentVector`: one table over its assignments.
    - `QueryVector`: one query, the tables it uses and the tables it computes.
    - State features: any tables of a state.
- **Policy**: π(q | S, E) is a distribution over the queries that can be added at S.

## Conditions

- Each operator has a **precondition** on what it reads and a **postcondition** on what it gives. The postcondition is what follows from the precondition, whatever the rows are.
- **Derived postcondition** of a table: what must hold of its rows, from how its query builds it.
- **Measured postcondition** of a table: what holds of its rows on this task.
- A fact is **entailed** where the derived postcondition gives it, and **contingent** where it holds of the rows and the derived postcondition does not give it. A table is a hypothesis about the task through its contingent facts. A contingent fact need not be relevant.
- A term whose value the conditions already give has no derivation, so it is never constructed. The [Feature specification](feature-spec.md) gives the rules.

## The loop

S gives D(S), the features of D(S) give π, π gives a query q, and q gives S ∪ {q}. The loop ends at a state in G.

## The hypothesis

The features are a sufficient statistic: π depends on E only through the features of D(S) and the syntax of S.
