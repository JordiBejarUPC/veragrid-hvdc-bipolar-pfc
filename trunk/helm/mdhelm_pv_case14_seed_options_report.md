# MDHEM IEEE14 Seed-Mode Report

Generated: `2026-07-09T23:08:18`
Case file: `/home/santi/Git/eRoots/VeraGrid/trunk/helm/case14.matpower`
Report file: `/home/santi/Git/eRoots/VeraGrid/trunk/helm/mdhelm_pv_case14_seed_options_report.md`

## Scope

This report compares three artifact training modes on the same IEEE 14 scenarios.
Newton-Raphson is never used to answer artifact queries.
Newton-Raphson appears only in two places:

1. as an optional explicit germ seed when that mode is selected,
2. as the external reference used to score the artifact outputs.

## Settings

- `max_order = 4`
- `scenario_count = 10`
- `random_seed = 14`
- `artifact_tolerance = 1.0000e-05`
- `voltage_threshold = 2.0000e-02`
- `branch_flow_threshold_mva = 10.0000`
- `loading_threshold = 1.0000e-01`
- `injection_write_threshold = 2.0000e-06`

## Summary

| mode | explicit seed | external NR seed | seed converged | seed error | germ error | passed | worst dV | worst dSf | worst dloading | worst write err | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| internal HELM germ | no | no | True | n/a | 3.0413e-11 | 10/10 | 6.2847e-06 | 2.0537e-03 | 2.0537e-07 | 5.5511e-17 | ok |
| explicit HELM seed | yes | no | True | 3.0413e-11 | 3.0413e-11 | 10/10 | 6.2847e-06 | 2.0537e-03 | 2.0537e-07 | 5.5511e-17 | ok |
| explicit NR seed | yes | yes | True | 4.8295e-15 | 4.8295e-15 | 10/10 | 4.2123e-11 | 1.7443e-08 | 1.7443e-12 | 5.5511e-17 | ok |

## internal HELM germ

- artifact: `/home/santi/Git/eRoots/VeraGrid/trunk/helm/mdhelm_pv_case14_internal_helm_artifact.npz`
- external NR seed used during training: `no`
- explicit seed converged: `True`
- explicit seed error: `n/a`
- artifact germ error: `3.0413e-11`
- passed scenarios: `10/10`

| scenario | dP sum | dQ sum | nr conv | art conv | write err | nr err | art err | max dV | max dSf | max dloading | passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | +0.000e+00 | +0.000e+00 | True | True | 0.000e+00 | 4.829e-15 | 6.849e-15 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_01 | +0.000e+00 | -1.084e-18 | True | True | 2.776e-17 | 1.044e-14 | 3.289e-10 | 6.284e-06 | 2.051e-03 | 2.051e-07 | True |
| random_02 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 5.641e-15 | 4.737e-12 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_03 | +0.000e+00 | +1.735e-18 | True | True | 2.776e-17 | 8.799e-15 | 7.818e-11 | 6.285e-06 | 2.054e-03 | 2.054e-07 | True |
| random_04 | -3.469e-18 | +0.000e+00 | True | True | 5.551e-17 | 6.200e-15 | 3.045e-11 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_05 | +8.674e-19 | -1.735e-18 | True | True | 2.776e-17 | 9.999e-15 | 9.564e-11 | 6.284e-06 | 2.051e-03 | 2.051e-07 | True |
| random_06 | +0.000e+00 | -8.674e-19 | True | True | 2.776e-17 | 1.034e-14 | 2.333e-11 | 6.285e-06 | 2.053e-03 | 2.053e-07 | True |
| random_07 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 4.163e-15 | 6.868e-13 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_08 | +0.000e+00 | -4.337e-19 | True | True | 5.551e-17 | 7.161e-15 | 4.324e-11 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_09 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 8.174e-15 | 7.602e-11 | 6.284e-06 | 2.051e-03 | 2.051e-07 | True |

## explicit HELM seed

- artifact: `/home/santi/Git/eRoots/VeraGrid/trunk/helm/mdhelm_pv_case14_explicit_helm_artifact.npz`
- external NR seed used during training: `no`
- explicit seed converged: `True`
- explicit seed error: `3.0413e-11`
- artifact germ error: `3.0413e-11`
- passed scenarios: `10/10`

| scenario | dP sum | dQ sum | nr conv | art conv | write err | nr err | art err | max dV | max dSf | max dloading | passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | +0.000e+00 | +0.000e+00 | True | True | 0.000e+00 | 4.829e-15 | 6.849e-15 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_01 | +0.000e+00 | -1.084e-18 | True | True | 2.776e-17 | 1.044e-14 | 3.289e-10 | 6.284e-06 | 2.051e-03 | 2.051e-07 | True |
| random_02 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 5.641e-15 | 4.737e-12 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_03 | +0.000e+00 | +1.735e-18 | True | True | 2.776e-17 | 8.799e-15 | 7.818e-11 | 6.285e-06 | 2.054e-03 | 2.054e-07 | True |
| random_04 | -3.469e-18 | +0.000e+00 | True | True | 5.551e-17 | 6.200e-15 | 3.045e-11 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_05 | +8.674e-19 | -1.735e-18 | True | True | 2.776e-17 | 9.999e-15 | 9.564e-11 | 6.284e-06 | 2.051e-03 | 2.051e-07 | True |
| random_06 | +0.000e+00 | -8.674e-19 | True | True | 2.776e-17 | 1.034e-14 | 2.333e-11 | 6.285e-06 | 2.053e-03 | 2.053e-07 | True |
| random_07 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 4.163e-15 | 6.868e-13 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_08 | +0.000e+00 | -4.337e-19 | True | True | 5.551e-17 | 7.161e-15 | 4.324e-11 | 6.284e-06 | 2.052e-03 | 2.052e-07 | True |
| random_09 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 8.174e-15 | 7.602e-11 | 6.284e-06 | 2.051e-03 | 2.051e-07 | True |

## explicit NR seed

- artifact: `/home/santi/Git/eRoots/VeraGrid/trunk/helm/mdhelm_pv_case14_explicit_nr_artifact.npz`
- external NR seed used during training: `yes`
- explicit seed converged: `True`
- explicit seed error: `4.8295e-15`
- artifact germ error: `4.8295e-15`
- passed scenarios: `10/10`

| scenario | dP sum | dQ sum | nr conv | art conv | write err | nr err | art err | max dV | max dSf | max dloading | passed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| base | +0.000e+00 | +0.000e+00 | True | True | 0.000e+00 | 4.829e-15 | 1.199e-14 | 7.022e-16 | 5.644e-13 | 5.638e-17 | True |
| random_01 | +0.000e+00 | -1.084e-18 | True | True | 2.776e-17 | 1.044e-14 | 3.289e-10 | 4.212e-11 | 1.744e-08 | 1.744e-12 | True |
| random_02 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 5.641e-15 | 4.741e-12 | 1.083e-12 | 2.488e-10 | 2.488e-14 | True |
| random_03 | +0.000e+00 | +1.735e-18 | True | True | 2.776e-17 | 8.799e-15 | 7.821e-11 | 1.499e-11 | 5.862e-09 | 5.862e-13 | True |
| random_04 | -3.469e-18 | +0.000e+00 | True | True | 5.551e-17 | 6.200e-15 | 3.043e-11 | 6.952e-12 | 1.803e-09 | 1.803e-13 | True |
| random_05 | +8.674e-19 | -1.735e-18 | True | True | 2.776e-17 | 9.999e-15 | 9.562e-11 | 1.404e-11 | 5.850e-09 | 5.850e-13 | True |
| random_06 | +0.000e+00 | -8.674e-19 | True | True | 2.776e-17 | 1.034e-14 | 2.332e-11 | 5.697e-12 | 1.544e-09 | 1.544e-13 | True |
| random_07 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 4.163e-15 | 6.768e-13 | 1.086e-13 | 3.090e-11 | 3.090e-15 | True |
| random_08 | +0.000e+00 | -4.337e-19 | True | True | 5.551e-17 | 7.161e-15 | 4.325e-11 | 1.020e-11 | 3.334e-09 | 3.334e-13 | True |
| random_09 | +0.000e+00 | +0.000e+00 | True | True | 5.551e-17 | 8.174e-15 | 7.600e-11 | 1.289e-11 | 5.194e-09 | 5.194e-13 | True |
