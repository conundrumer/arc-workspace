"""The `@derive` and `@store` branches: the checks on them and on the
determination, and what the `derive` and `store` surveys share.

`checker.branches.cases` holds the runs of cases on the pairs and the
cases that take a branch; `checker.branches.witnesses` the witnesses a
survey builds and the entries it builds from them;
`checker.branches.ignores` the named `@ignore` lines; and
`checker.branches.checks` the checks. `cases` imports none of the others,
`witnesses` and `ignores` import `cases`, and `checks` imports none of
them."""
