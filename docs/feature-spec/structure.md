# Structure of the search

The objects of the search over programs and the maps between them. The [Type contract](../sample-build/contract.md) gives their types, and the [Feature specification](feature-spec.md) gives the feature language.

## Objects

- **Evidence** E: a task's train pairs and test inputs, its ARC examples.
- **Query**: a clause of arclog. It reads parameterized tables and derives parameterized tables.
- **State** S: a finite set of queries closed under reads, so a DAG. S ≤ S′ means S ⊆ S′, so states form a partial order with the base tables at the bottom.
- **Goal set** G: the states that hold an `OUT` form whose output equals each train output, at some assignment.

## Maps

- **Evaluation**: E and S give a database D(S), with one parameterized table per relation, whose tables are indexed by assignment, ARC example and constraint model. Where S ≤ S′, D(S′) extends D(S), and the tables of S do not change. A new `DET` refines the assignment index.
- **Feature**: f(D, t) is a number or a boolean, for a table t. A feature is a query with an aggregate at its root, so a feature is a query reduced to a value.
- **Levels**: [Levels](../sample-build/contract.md#levels) gives the levels from a feature's value on one table to the features of a state, each with its index.
* comment: The user's words, session 12a37de8, 2026-11-06: "Always qualify or conventional terms . No more single loose words. Row is confusing".
- **Feature vector**: r(q, S, E, e, a) is what a learned model reads of a candidate query q at a state S, an ARC example e of E and an assignment a of q's parameterized table. Offline ranking keeps one feature vector for each candidate query and ARC example. It holds q's features at e and a, the numbers across ARC examples (`stable`, `least`, `mean` and `most`) of q's features, and the features of S and E, each in a column that means one thing on every feature vector of every task. So a feature vector keeps which feature's value goes with which at an ARC example. At a test input, a feature that reads the output has no value. A learned model reads the numbers across ARC examples as columns of its feature vector, and finds out for itself whether the least value matters. [Feature export](export-design.md#what-a-learned-model-reads) gives the columns.
    - How a query with several assignments gives feature vectors is not defined.
- **Policy**: π(q | S, E) is a distribution over the queries that can be added at S. The writer realises it by writing one query, token by token.
    - Each table token names one parameterized table of S, and every parameterized table of S is a choice. The writer's learned model scores that choice from the features of that parameterized table. Which tables a query reads is what the learned model learns, so no step before the writer narrows the choice. No column combines the features of the tables of S into one value for the state. A table token's column may compare its table with the other tables that the writing point admits.
    - While a query is being written, the writer's learned model sees what the query so far computes.

## The two searches

- **Program search** grows one DAG of queries, S, as a theorem prover grows its set of derived clauses. Most queries in S are never part of a program. A program is a set of queries of S closed under inputs, with one `OUT`.
- **Query search** is the writer: it writes one query at S, and that query's atoms are its result.
- A query is an experiment, and its parameterized tables are the experiment's result. A feature is a hypothesis about that result. The features of the tables of S, such as [the judgments](#the-judgments) and progress toward the train output, guide the next query.
- The learned model learns from negatives: tables that the search's own runs on train tasks computed and that no case of the task's solver holds, beside the tables of the solver's cases.

## Conditions

- Each operator has a **precondition** on what it reads and a **postcondition** on what it gives. The postcondition is what follows from the precondition, whatever the table rows are.
- **Derived postcondition** of a parameterized table: what must hold of its table rows, from how its query builds it.
- **Measured postcondition** of a parameterized table: what holds of its table rows on this task.
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
