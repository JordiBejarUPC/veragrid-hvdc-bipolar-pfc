# EMT Solver Optimization Roadmap

## Purpose

This roadmap defines the next optimization stages for the four EMT solver backends:

- `SYMBOLIC`
- `AD`
- `VECTORIZED`
- `COMPILED`

The goal is not to collapse them into a single solver, but to preserve them as research families while driving each one toward its own performance ceiling with reproducible evidence.

The roadmap is organized in phases so every optimization step has:

- a technical objective,
- concrete deliverables,
- validation artifacts,
- and an explicit exit criterion.

---

## Phase 1 - Cross-Process Cache For COMPILED

### Objective

Reduce the true process-cold build cost of `StructuralCompiledSolver` by persisting structural compilation artifacts across Python processes.

### Scope

- Persist generated structural residual kernels.
- Persist generated structural AD Jacobian kernels.
- Persist structural matrix-vectorized kernels when needed.
- Version the cache by Python version, platform, backend ABI, discretization method, and structural signature.

### Deliverables

- Persistent cache directory for compiled EMT artifacts.
- Deterministic cache keys based on structural signatures.
- Cache hit and miss counters in backend build statistics.
- A/B benchmark tables comparing cache disabled vs cache enabled.

### Validation

- Existing EMT regression suite must still pass.
- Process-cold benchmark must show a measurable build reduction for `COMPILED`.
- Numerical trajectories must remain unchanged with and without cache.

### Risks

- Cache invalidation bugs can silently reuse stale artifacts.
- Platform-specific bytecode or Numba cache behavior can break portability.
- Excessive cache granularity can erase expected gains.

### Exit Criterion

`COMPILED` process-cold build decreases materially on `ZIPload`, `Rload`, and `Event`, with no regression in waveform similarity or solver robustness.

---

## Phase 2 - Extend Persistent Cache To AD And SYMBOLIC

### Objective

Apply the same persistent compilation strategy to `JitAdSolver` and `JitSymbolicSolver` so their first-process build costs also collapse.

### Scope

- Residual kernels.
- Jacobian kernels.
- Shared structural key generation where possible.
- Backend-specific cache metadata where needed.

### Deliverables

- Persistent cache integration for `AD`.
- Persistent cache integration for `SYMBOLIC`.
- Updated benchmark exports exposing cache usage statistics for all backends.

### Validation

- Existing EMT regression suite must still pass.
- Temporal trace similarity tests must still pass.
- Standard process-cold and cold/warm process tables must show reduced first-build cost.

### Risks

- Symbolic and AD kernels may need different invalidation boundaries.
- Synthetic differential-variable handling may destabilize key generation if not canonicalized correctly.

### Exit Criterion

`AD` and `SYMBOLIC` show stable reductions in process-cold build while preserving current numerical behavior.

---

## Phase 3 - Common Cache Layer And Metrics

### Objective

Turn the cache mechanism into a shared EMT compilation service with unified observability.

### Scope

- Common cache layout.
- Common cache metadata schema.
- Common counters for hits, misses, stores, invalidations, and load times.
- Benchmark exports that separate source-generation time, machine-compilation time, and cache reuse time.

### Deliverables

- Shared cache utility used by `SYMBOLIC`, `AD`, `VECTORIZED`, and `COMPILED` where meaningful.
- Unified benchmark fields for cache lifecycle.
- Compiler microbenchmark with repeated statistics.

### Validation

- New cache statistics must appear in exported benchmark artifacts.
- Repeated subprocess benchmarks must remain deterministic enough for median-based reporting.

### Risks

- Overgeneralizing the cache API can make backend-specific optimizations harder.
- Statistics can become inconsistent if different backends report different cache semantics.

### Exit Criterion

All solver backends expose a coherent cache story in the benchmark tables and internal build statistics.

---

## Phase 4 - Second Optimization Pass Per Solver

### Objective

Once process-cold build is under control, revisit each solver with cleaner measurements and push hot-loop performance again.

### Scope

#### COMPILED

- Revisit Jacobian build path.
- Revisit factorization refresh and invalidation policy.
- Revisit residual vs direct residual path selection.

#### AD

- Revisit Jacobian specialization strategy.
- Revisit batch size and kernel partitioning.

#### SYMBOLIC

- Revisit residual batching strategy.
- Revisit Jacobian reuse policy.

#### VECTORIZED

- Revisit group partitioning thresholds.
- Revisit direct residual mode selection.

### Deliverables

- Per-backend tuning notes.
- Updated benchmark deltas against the frozen baseline.

### Validation

- Full EMT benchmark corpus.
- Temporal waveform similarity tests.
- Standard process-cold and paper-grade repeated reports.

### Risks

- Gains in one backend can reduce fairness if semantic behavior drifts.
- Aggressive reuse may alter Newton behavior and must stay visible in diagnostics.

### Exit Criterion

Every backend gets at least one additional performance pass using the now-stable cache-aware measurement stack.

---

## Phase 5 - Thesis-Grade Reporting Layer

### Objective

Freeze the benchmark and reporting stack into a doctoral-grade evidence package.

### Scope

- Standard process-cold tables.
- Cold/warm process tables.
- Repeated median and standard deviation tables.
- Visual waveform export for sanity checking.
- Cache lifecycle discussion.

### Deliverables

- Final benchmark tables for thesis/paper.
- Short explanatory text for each backend family.
- Explicit narrative on when each solver is relevant.

### Validation

- All report generators run from the repository.
- All tables are backed by artifacts under `trunk/dynamics_emt/benchmark_results`.

### Risks

- Mixing regression-short and paper-long tables can create interpretability problems.
- Over-reporting noisy subprocess data can obscure the main conclusions.

### Exit Criterion

The EMT solver study is reproducible, benchmarked, visually inspected, and ready to be cited in research writing.

---

## Recommended Execution Order

1. Phase 1 - `COMPILED` persistent cross-process cache.
2. Phase 2 - extend the cache to `AD` and `SYMBOLIC`.
3. Phase 3 - unify cache metrics and reporting.
4. Phase 4 - second per-solver optimization pass with cleaner measurements.
5. Phase 5 - thesis-grade packaging.

---

## Immediate Next Task

The next technical step is:

> implement a persistent cross-process cache for `StructuralCompiledSolver` artifacts and quantify its effect on standard process-cold benchmarks.
