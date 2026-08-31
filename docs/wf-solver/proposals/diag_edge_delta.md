# `diag_edge_delta` — edge delta at a corner with two amounts

Two `edge_delta`s at the two edges of a corner. Not: `edge_delta` at a DiagDir (one amount at both edges); `jump` chains at a corner; `diag_dist`.

Match: `edge_delta`, `diag_dirs`, `jump_delta.*jump(`.

Callers: 8618d23e alone. 1e81d6f9 was `edge_delta` at a DiagDir (fixed). Near: 4522001f, 22208ba4 (diagonal shifts); the opposite-pair form at five sites, now `axis_delta`.

Verdict: close; 8618d23e keeps it as a plain relation. 2026-08-29.
