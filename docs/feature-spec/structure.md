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
- **Row**: r(q, S, E, e) is what a model reads of a candidate query q at a state S and an example e of E, a train pair or a test input. It holds q's features at e, q's features over all examples, and the features of S and E, each in a column that means one thing on every row of every task. So a row keeps which feature's value goes with which at an example. At a test input, a feature that reads the output has no value.
- **Policy**: π(q | S, E) is a distribution over the queries that can be added at S.

## Conditions

- Each operator has a **precondition** on what it reads and a **postcondition** on what it gives. The postcondition is what follows from the precondition, whatever the rows are.
- **Derived postcondition** of a table: what must hold of its rows, from how its query builds it.
- **Measured postcondition** of a table: what holds of its rows on this task.
- A claim is **entailed** where the derived postcondition gives it, and **contingent** where it does not, so that it could have failed.
- A term whose value the conditions already give has no derivation, so it is never constructed. The [Feature specification](feature-spec.md) gives the rules.

## The judgments

A query's result is judged in this order, as a search meets each one.

- **Contingency**, at generation time, before the query runs: the query's claim is not entailed by its derived postcondition.
- **Confirmation**, at execution time, once the query has run: the measured postcondition holds the claim on the evidence. A result with no confirmation is degenerate, such as an empty table or a copy of a table that exists.
- **Novelty:** the result says something that the tables before it do not say.
- **Relevance:** the result's claims about the train output single out that output among the outputs of plausible wrong readings of the rule.
- **Value:** a path from the result can still reach a state in the goal set. Only a search shows it.

## The loop

S gives D(S), the features of D(S) give π, π gives a query q, and q gives S ∪ {q}. The loop ends at a state in G.

## The hypothesis

The features are a sufficient statistic: π depends on E only through the features of D(S) and the syntax of S.
