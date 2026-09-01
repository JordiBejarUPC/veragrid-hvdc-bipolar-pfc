# VeraGrid FMU Import

This package owns FMU archive validation, declarative device persistence, typed
worker communication, and solver-agnostic FMI lifecycle coordination. Imported
models remain data: no import or persistence path generates, evaluates, or
dynamically imports source code.

## Ownership

- `device_config.py` owns the versioned Co-Simulation and Model Exchange device
  records. Version 4 persists `maximum_event_iterations` explicitly; only
  versions 1 through 3 synthesize the compatibility default of 32.
- `runtime_protocol.py`, `runtime_worker.py`, `runtime_worker_host.py`, and
  `runtime_session.py` own typed, bounded FMI 3 process communication.
- `runtime_coordinator.py` is the sole owner of the FMI 3 Model Exchange
  accepted/candidate transaction, native checkpoint, Event Mode fixpoint, and
  time-event request.
- `experimental_me.py` owns the device adapters, endpoint-domain detection,
  state-event localization, and cross-participant RMS orchestration.
- `emt_boundary.py` connects the same adapter transaction to the
  solver-independent EMT boundary protocol.
- RMS and EMT solvers own step-size selection and retry. The FMI importer does
  not choose a numerical solver or advance Co-Simulation past an earlier
  Model Exchange event.

GUI or Qt code must not enter this layer. A second coordinator, callback table,
generated-source model, or visible-state rollback would duplicate an existing
owner.

## FMI 3 Model Exchange transaction

1. Preparation requires `canGetAndSetFMUState`. A model without native FMU
   state checkpoints is rejected before solver-coupled evaluation.
2. Initialization settles Event Mode and saves the complete native accepted
   point.
3. The solver prepares one candidate. Endpoint event-indicator domains use
   `z > 0` versus `z <= 0`, so exact zero is non-positive.
4. When an endpoint domain changes, the importer localizes the global earliest
   supported event, restores every participant, and asks the solver to retry.
5. Acceptance optionally enters Event Mode, settles its bounded fixpoint, and
   replaces the native checkpoint. Rejection restores the prior checkpoint.

`maximum_event_iterations` accepts exact non-Boolean integers in `[1, 1024]`
and defaults to 32. It is independent of the RMS/EMT localization iteration
bound and event-time tolerance.

A defined FMI `nextEventTime` must be finite and strictly greater than the
exact Event Mode entry time. That reference is the simulation start during
initialization and the candidate time during accepted-step settlement.

## State-event envelope and numerical bounds

The earliest-event guarantee applies only when both endpoint times are finite,
their subtraction is finite and strictly positive, every indicator has at most
one transition inside the interval, and the configured bisection bound can
meet the effective tolerance. A model capable of repeated interior transitions
requires a smaller solver step; adaptive subdivision and dense output are out
of scope.

Localization uses an effective tolerance equal to the configured positive
finite tolerance or a 16-ULP time-scale floor, whichever is larger. Exact
`frexp` preflight proves the required iteration count before the first probe.
Every midpoint is computed as the lower endpoint plus half the finite width,
which remains safe for supported same-sign extreme times. Opposite-sign finite
endpoints whose subtraction overflows are rejected before probing.

One fixed-size mutable state list is allocated per localization and reused.
For a participant with positive state cardinality, each worker probe receives a
new immutable state tuple. A valid event-only FMU with zero continuous states
passes the canonical empty tuple and remains supported.

For `P` prepared participants, `C` crossing participants, and `n_i`
bisections per crossing participant, the bounded worker traffic is:

- no crossing: `2 * P`;
- crossing: `3 * P + 4 * sum(n_i)`;
- common bound `N`: at most `3 * P + 4 * C * N`.

Indicator cardinality does not multiply the localization loop.

## Exclusions

FMI Scheduled Execution, FMU re-instantiation or replay rollback, adaptive
subdivision, dense solver output, GUI ownership, new third-party dependencies,
global process state, and generated source representations are outside this
package contract.
