# EMT Lookup Tables Roadmap

## Scope

This roadmap covers only native `lookup tables` functionality inside VeraGrid.

Out of scope for this phase:
- DGS / PF parser integration
- Automatic extraction of lookup data from external formats
- Coupling lookup tables with unknown DGS devices
- EMT compensator deep work
- Nonlinear resistor ATP integration

Additional active decisions:
- `Transformer` and `XFMR Transformer` remain separate for now.
- `mode_dict` must appear in the GUI inside `Parameters` as `Mode Parameter`.
- Lookup-table creation must use modal dialogs.
- The first lookup-table modal must support manual table editing plus paste from clipboard.
- New or touched code must follow the project coding rules and avoid dynamic imports.

## Goal

Unlock executable lookup tables in VeraGrid with:
- Working native catalog entries.
- Modal-based table loading on block creation.
- Automated tests.
- GUI support.
- No DGS / PF coupling yet.

## Phase 0 - Dynamic Editor Performance

### Objective

Make the Dynamic Editor fluid enough to support large EMT blocks and future lookup-table workflows.

### Deliverables

- Lazy-load side panels in the Dynamic Editor.
- Cache string rendering for symbolic expressions.
- Remove expensive `ResizeToContents` behavior from large tables.
- Avoid full scene rebuilds for non-structural parameter edits.
- Make `Add default catalogue` lazy and near-instant.
- Cache static CSV catalogue parsing.
- Avoid eager materialization of heavy EMT templates during default catalogue loading.

### Validation

- Selecting large blocks such as bridge templates remains fluid.
- Editing parameters does not rebuild the whole scene unless structurally required.
- `Add default catalogue` feels immediate.

### Exit Criterion

The Dynamic Editor remains responsive when loading or selecting large blocks.

## Phase 1 - Mode Parameter GUI Base

### Objective

Expose `mode_dict` in the GUI using the same `Parameters` area.

### Deliverables

- New parameter type: `Mode Parameter`.
- The `Parameters` table shows:
  `Parameter`, `Event Parameter`, and `Mode Parameter`.
- Add, edit, and remove support for `mode_dict`.
- The EMT event dialog can target both `event_dict` and `mode_dict`.
- EMT mode events expose `force_step_alignment`.

### Validation

- GUI tests for parameter rendering and editing.
- Backend tests for event delivery to `mode_dict`.

### Exit Criterion

A user can inspect and edit `mode_dict` from the standard parameter area.

## Phase 2 - Lookup Table Modal Infrastructure

### Objective

Introduce a modal workflow before materializing lookup-table blocks from the native catalog.

### Deliverables

- Detect lookup-table descriptors at creation time.
- Open a modal dialog before block instantiation.
- Support manual table editing.
- Support paste from clipboard.
- Validate table shape and numeric consistency.
- Materialize the block with the captured table data.

### Validation

- Cancel does not create a block.
- Accept creates a configured block.
- Pasted data is correctly parsed into the modal grid.

### Exit Criterion

Lookup tables can be inserted only after table data is provided through a modal dialog.

## Phase 3 - Unlock Linear Lookup Tables

### Objective

Unlock the lowest-risk lookup-table family first.

### In Scope

- `lookup_array_linear`
- `lookup_array_linear_noclipping`
- `lookup_array_object_linear`
- `lookup_array_object_linear_noclipping`
- `lookup_matrix_linear`
- `lookup_matrix_object_linear`

### Deliverables

- Executable symbolic or procedural implementations.
- Descriptor promotion from pending to ready.
- Functional contracts and tests.
- GUI visibility in the native catalog.
- Modal loading support.

### Validation

- 1D linear interpolation works inside the domain.
- Clipping and no-clipping variants behave explicitly.
- Matrix interpolation works for interior and edge cases.
- Blocks appear in the editor once unlocked.

### Exit Criterion

Linear lookup tables are usable end to end in VeraGrid.

## Phase 4 - Unlock Inverse Lookup Tables

### Objective

Enable inverse lookup behavior with an explicit numerical contract.

### In Scope

- `inverse_lookup_array_linear`
- `inverse_lookup_array_object_linear`

### Deliverables

- Explicit monotonicity contract.
- Well-defined resolution policy.
- Functional tests.
- Modal validation rules.

### Validation

- Monotonic tables solve correctly.
- Invalid or ambiguous tables are rejected explicitly.

### Exit Criterion

Inverse lookup blocks are usable with predictable behavior.

## Phase 5 - Unlock Spline Lookup Tables

### Objective

Enable spline-based lookup tables after the linear family is stable.

### In Scope

- `lookup_array_spline`
- `lookup_array_object_spline`
- `lookup_matrix_spline`
- `lookup_matrix_object_spline`

### Deliverables

- Executable spline implementations.
- Validation rules for minimum points and extrapolation behavior.
- Functional tests.
- Modal support.

### Validation

- Spline outputs remain stable for representative test cases.
- Invalid spline inputs are rejected clearly.

### Exit Criterion

Spline lookup tables are editor-ready and tested.

## Deferred Work

After lookup tables are stable:
- DGS / PF coupling.
- Ramp event.
- EMT switch work.
- Pulse demo.
- Combined RLC wizard.
- Ground, neutral, and transformer EMT semantics.
- Nonlinear resistor integration.

## Current Priority Order

1. Phase 0 - Dynamic Editor Performance.
2. Phase 1 - Mode Parameter GUI Base.
3. Phase 2 - Lookup Table Modal Infrastructure.
4. Phase 3 - Unlock Linear Lookup Tables.
5. Phase 4 - Unlock Inverse Lookup Tables.
6. Phase 5 - Unlock Spline Lookup Tables.
