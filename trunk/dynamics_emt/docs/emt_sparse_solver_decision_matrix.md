# EMT Sparse Solver Decision Matrix

## Purpose

This matrix defines the recommended mononuclear roadmap for VeraGrid EMT sparse linear algebra and related numerical backends before moving into parallel and HPC phases.

The immediate goal is:

> maximize single-node CPU EMT performance first, then parallelize on top of a proven sparse-core architecture.

This document explicitly separates:

- sparse direct linear solvers, which are an immediate priority,
- broader nonlinear/DAE suites, which are strategically useful but not the first bottleneck,
- and HPC/distributed technologies, which are intentionally deferred.

---

## Decision Principle

For fixed-step implicit EMT, the strongest short-term leverage usually comes from:

1. sparse direct factorization quality,
2. symbolic and numeric reuse,
3. Jacobian build cost,
4. event-local invalidation policy,
5. and benchmark discipline.

Because of that, the mononuclear roadmap must prioritize sparse direct backends before broader solver suites.

---

## Decision Matrix

| Technology | Layer | Main Strength | Main Weakness | Best Use Case | Single-Core EMT Value | Integration Cost | License Risk | Decision | Priority |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `SuperLU` | Sparse direct | Robust baseline, portable, already integrated | Not always the fastest for circuit-type matrices | Stable default backend and fallback | High | Low | Low | Keep as default baseline | Immediate |
| `Pardiso` | Sparse direct | Very strong CPU performance, industrial-grade factorization | External dependency and licensing/runtime separation required | Large stiff EMT cases, high reuse scenarios | Very High | Medium | Medium | Keep and benchmark aggressively | Immediate |
| `KLU` | Sparse direct | Excellent fit for circuit sparsity, low fill-in on network-like systems | Ecosystem friction on Windows, wrapper quality varies | Circuit-structured EMT matrices with strong symbolic reuse | Very High | High | Medium | Keep and mature the native plugin | Immediate |
| `UMFPACK` | Sparse direct | Mature and respected sparse direct solver | Usually less compelling than Pardiso/KLU in this roadmap | Reference comparisons and portability studies | Medium | Medium | Low | Consider later if needed | Later |
| `MUMPS` | Sparse direct | Strong large sparse direct solver, scales well beyond one core later | Heavier integration and deployment burden | Bridge from single-node to shared/distributed workflows | Medium now / High later | High | Medium | Defer until post-mononuclear phase | Later |
| `WSMP` | Sparse direct | Potentially very strong on some industrial matrices | Access and packaging complexity | Enterprise-only experiments | Medium | High | High | Not a current priority | Deferred |
| `SUNDIALS IDA` | DAE/nonlinear suite | Powerful general DAE integration and nonlinear infrastructure | Different problem layer; not a drop-in sparse backend replacement | Research line for adaptive/general DAE EMT variants | Medium | High | Low | Strategic research branch, not first speed path | Later |
| `SUNDIALS KINSOL` | Nonlinear solve suite | Mature nonlinear solve machinery | Does not remove sparse backend bottleneck | Alternative Newton layer experiments | Medium | High | Low | Interesting but secondary | Later |
| `SuperLU_DIST` | Sparse direct distributed | Natural path toward distributed sparse factorization | Overkill before HPC phase | Future distributed EMT | Low now / High later | High | Low | HPC-phase candidate | Deferred |
| `cuDSS` / `cuSOLVER` | GPU sparse direct | Possible major acceleration for some sparse solves | Data movement and workflow complexity can erase gains | Future GPU EMT, batched scenarios | Low now / Potentially High later | High | Medium | Not before CPU sparse path is mature | Deferred |

---

## Immediate Mononuclear Roadmap

### Tier A - Must Have Now

#### 1. `SuperLU`

- Keep it as the default internal backend.
- Keep it as the fallback path for all external plugin failures.
- Use it as the reference sparse backend in all EMT validation and benchmark tests.

#### 2. `Pardiso`

- Keep it as the main external high-performance backend candidate.
- Benchmark it first on `StructuralCompiledSolver`.
- Benchmark it second on `StructuralVectorizedSolver`.
- Use it to identify whether VeraGrid is limited by sparse factorization or by model/Jacobian generation.

#### 3. `KLU`

- Keep it as a first-class target because it is highly relevant for circuit-structured sparse matrices.
- Mature the native plugin path rather than relying on fragile Python wrappers.
- Compare it directly to `SuperLU` and `Pardiso` on the EMT corpus.

---

## Recommended Execution Order

### Phase M1 - Stable Single-Core Sparse Stack

1. `SuperLU` internal baseline.
2. `Pardiso` external plugin, benchmarked and validated.
3. `KLU` native external plugin, benchmarked and validated.

Exit criterion:

- all three backends run through the EMT sparse interface,
- `StructuralCompiledSolver` supports them cleanly,
- `StructuralVectorizedSolver` supports them cleanly,
- numerical trajectories remain within tolerance,
- and process-cold plus warm runtime differences are measured.

### Phase M2 - Best-Backend Selection Per Solver Family

After the three sparse backends are working, determine the default recommended backend per EMT solver family:

- `COMPILED`:
  - likely `Pardiso` or `KLU`, depending on case family.
- `VECTORIZED`:
  - likely `SuperLU`, `Pardiso`, or `KLU` depending on matrix structure and build/runtime balance.
- `SYMBOLIC` / `AD`:
  - likely benefit later from the same sparse abstraction, but after compiled/vectorized are fully benchmarked.

Exit criterion:

- each solver family has a defensible sparse backend recommendation for mononuclear CPU execution.

### Phase M3 - Only Then Revisit Broader Solver Suites

Only after sparse-direct competition is settled should VeraGrid explore:

- `SUNDIALS IDA`
- `SUNDIALS KINSOL`
- additional factorization engines like `UMFPACK` or `MUMPS`

Reason:

- these are important for generality and future research,
- but they are not the shortest path to beating commercial EMT tools on fixed-step implicit EMT runtime.

---

## Recommendation Summary

### What VeraGrid should push now

1. `SuperLU` as default internal baseline.
2. `Pardiso` as primary external performance backend.
3. `KLU` as primary circuit-specialized external backend.

### What VeraGrid should postpone

1. `SUNDIALS` integration as a speed-first initiative.
2. distributed sparse stacks.
3. GPU sparse stacks.

### Why

Because the current mononuclear opportunity is still dominated by:

- sparse direct factorization choice,
- symbolic/numeric reuse,
- build cost,
- and event-aware invalidation policy.

That is exactly the terrain where `SuperLU`, `Pardiso`, and `KLU` matter most.

---

## Current Strategic Position

If the objective is:

> "the fastest EMT simulator in the world on a single node before parallel and HPC work"

then the sparse roadmap should be:

1. finish `SuperLU` / `Pardiso` / `KLU` cleanly,
2. benchmark them hard on the EMT corpus,
3. freeze the best mononuclear sparse strategy,
4. and only then move outward to broader nonlinear suites and HPC technologies.
