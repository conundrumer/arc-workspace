# Partial: grid facts and INIT components

Rows 1044 of 1044. Rate 150.9 tasks/s. ETA 0 s.

<!-- read -->

Read on 1044 rows: pick half 542, read half 502. 2644 read-half component picks.

| component | positives (read) | base rate | observable | pick AUC | read AUC [95%] | control mean [range] | ms median/largest | bits all picks | bits vs prior |
|---|---|---|---|---|---|---|---|---|---|
| Agreement | 39 (18) | 0.036 | in_shape_varies (low) | 0.677 | 0.513 [0.398, 0.634] | 0.502 [0.381, 0.640] | 0.02/0.21 | -0.0031 | -0.0031 |
| Boundary | 59 (35) | 0.070 | object_size (high) | 0.724 | 0.691 [0.581, 0.789] | 0.503 [0.403, 0.590] | 0.21/2.98 | 0.0006 | 0.0005 |
| BoundingBox | 487 (246) | 0.490 | in_cells (high) | 0.735 | 0.685 [0.638, 0.730] | 0.498 [0.446, 0.549] | 0.03/0.17 | -0.0046 | -0.0053 |
| Cardinality | 410 (196) | 0.390 | distinct_shapes (high) | 0.601 | 0.637 [0.587, 0.684] | 0.500 [0.450, 0.552] | 0.21/3.05 | 0.0015 | 0.0014 |
| Connectivity | 386 (188) | 0.375 | object_size (high) | 0.668 | 0.665 [0.618, 0.711] | 0.497 [0.452, 0.547] | 0.21/2.98 | 0.0011 | 0.0008 |
| Distance | 59 (24) | 0.048 | changed_colors (high) | 0.744 | 0.683 [0.576, 0.779] | 0.498 [0.370, 0.606] | 0.03/0.15 | 0.0025 | 0.0025 |
| Division | 133 (63) | 0.125 | add_only (low) | 0.768 | 0.651 [0.577, 0.722] | 0.499 [0.425, 0.569] | 0.03/0.17 | -0.0014 | -0.0014 |
| Enclosure | 45 (22) | 0.044 | object_size (high) | 0.841 | 0.719 [0.624, 0.810] | 0.502 [0.393, 0.613] | 0.21/2.98 | -0.0072 | -0.0072 |
| Flood | 46 (22) | 0.044 | object_size (high) | 0.682 | 0.690 [0.577, 0.798] | 0.499 [0.384, 0.615] | 0.21/2.98 | 0.0026 | 0.0026 |
| Frame | 273 (126) | 0.251 | recolor_only (low) | 0.709 | 0.754 [0.708, 0.798] | 0.500 [0.445, 0.551] | 0.03/0.18 | 0.0212 | 0.0212 |
| Inclusion | 90 (43) | 0.086 | lost_colors (high) | 0.720 | 0.691 [0.605, 0.772] | 0.498 [0.416, 0.579] | 0.03/0.35 | 0.0066 | 0.0066 |
| Occurrences | 69 (37) | 0.074 | in_cells (high) | 0.622 | 0.570 [0.482, 0.658] | 0.496 [0.408, 0.581] | 0.03/0.17 | -0.0006 | -0.0006 |
| Order | 474 (238) | 0.474 | in_cells (high) | 0.655 | 0.643 [0.591, 0.688] | 0.500 [0.452, 0.546] | 0.03/0.17 | 0.0025 | 0.0023 |
| Outlines | 27 (15) | 0.030 | has_enclosure (high) | 0.857 | 0.887 [0.848, 0.919] | 0.502 [0.373, 0.652] | 0.16/1.23 | 0.0065 | 0.0065 |
| Periods | 22 (14) | 0.028 | periodic_out (high) | 0.852 | 0.936 [0.847, 0.980] | 0.502 [0.359, 0.639] | 0.06/0.38 | 0.0163 | 0.0155 |
| Propagation | 58 (29) | 0.058 | singleton_share (high) | 0.644 | 0.415 [0.298, 0.526] | 0.500 [0.404, 0.603] | 0.21/3.05 | -0.0111 | -0.0113 |
| Quotient | 85 (34) | 0.068 | area_log_ratio (low) | 0.609 | 0.614 [0.533, 0.697] | 0.499 [0.404, 0.591] | 0.02/0.13 | 0.0005 | 0.0005 |
| Ray | 228 (110) | 0.219 | bg_share (high) | 0.714 | 0.654 [0.595, 0.711] | 0.498 [0.437, 0.554] | 0.05/0.23 | 0.0142 | 0.0142 |
| Singleton | 223 (110) | 0.219 | in_cells (high) | 0.631 | 0.619 [0.560, 0.679] | 0.500 [0.445, 0.556] | 0.03/0.17 | 0.0021 | 0.0020 |
| Tiling | 118 (50) | 0.100 | changed_colors (low) | 0.871 | 0.826 [0.766, 0.871] | 0.501 [0.421, 0.578] | 0.03/0.15 | 0.0177 | 0.0177 |
| Walk | 51 (21) | 0.042 | in_cells (low) | 0.697 | 0.782 [0.663, 0.885] | 0.502 [0.390, 0.630] | 0.03/0.17 | 0.0057 | 0.0052 |

```
{
 "tasks": 1044,
 "pick_half": 542,
 "read_half": 502,
 "components_seen": 26,
 "components_kept": 21,
 "observables": 39,
 "read_picks": 2644,
 "pick_picks": 2742,
 "n_boot": 2000,
 "n_shuffles": 500,
 "k_smooth": 10.0,
 "seed": 20261101,
 "bits_all_tables_vs_marginal": 0.09002272505885572,
 "bits_all_tables_vs_marginal_ci": [
  0.04589432925833787,
  0.1358680921011154
 ],
 "bits_all_tables_control_mean": -0.046646544936090356,
 "bits_all_tables_control_range": [
  -0.07393873043205111,
  -0.026064922817470654
 ],
 "bits_tilted_prior_vs_prior": 0.08701569930691613,
 "bits_tilted_prior_vs_prior_ci": [
  0.04171616206887461,
  0.13271699065153406
 ],
 "bits_all_tables_vs_prior": 0.08259391678642186,
 "bits_all_tables_vs_prior_ci": [
  0.035830202989412106,
  0.13169326573928028
 ],
 "bits_marginal_vs_prior": -0.007428808272433875,
 "components_with_interval_over_half": 18,
 "spearman_in_cells_vs_picks_read": 0.20980968728336083,
 "spearman_object_size_vs_picks_read": 0.2535960938930983,
 "prior_tasks": 1009,
 "prior_leave_out_equals_the_99": true,
 "json_ms_median": 0.24359999999999998,
 "json_ms_largest": 3.2674,
 "left_out_components": {
  "CellDistance": 17,
  "Excess": 14,
  "ExtentDivisions": 3,
  "Unfold": 5,
  "Wallpaper": 7
 },
 "read_seconds": 2.74408221244812
}
```
