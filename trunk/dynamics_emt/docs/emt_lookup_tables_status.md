# EMT Lookup Tables Status

## Branch State

- Local branch: `devel_dynamics`
- Sync state at session start: local and remote diverged
- Local head at plan handoff: `c07b67606 improve dynamic EMT handover support`
- Remote head at plan handoff: `30473e957 Merge remote-tracking branch 'eRoots/devel_dynamics' into devel_dynamics`
- Current blocker: decide whether to continue with `merge`, `rebase`, or skip sync temporarily

## Progress Board

- [x] Phase 0 - Dynamic Editor Performance
- [x] Phase 1 - Mode Parameter GUI Base
- [x] Phase 2 - Lookup Table Modal Infrastructure
- [x] Phase 3 - Unlock Linear Lookup Tables
- [x] Phase 4 - Unlock Inverse Lookup Tables
- [x] Phase 5 - Unlock Spline Lookup Tables

## Active Tasks

- [ ] Review whether EMT event rows should visually label `mode_dict` vs `event_dict` parameter type inside the dialog.

## Session Log

### Session 0 - Planning completed

- Defined the EMT roadmap with backend and frontend scope.
- Decided that `Transformer` and `XFMR Transformer` stay separate for now.
- Kept DGS / PF integration out of the lookup-table scope for this phase.
- Confirmed that lookup-table creation must use modal dialogs.
- Confirmed the first modal input method as manual table editing plus paste from clipboard.
- Identified Dynamic Editor performance hotspots before scaling up native catalog work.
- Identified which lookup-table templates are already functional and which remain pending.

### Session 1 - Build mode start

- Tried `git pull --ff-only` before editing.
- Pull failed because local and remote history diverged.
- Persisted the roadmap and this status tracker in `trunk/dynamics_emt/docs`.
- Merged `origin/devel_dynamics` into the local branch.
- Resolved merge conflicts in:
  - `src/VeraGridEngine/Devices/Dynamic/var_factory.py`
  - `src/VeraGridEngine/Simulations/EMT/problems/emt_problem_dae.py`
- Validated the merge with focused EMT and RMS regression tests.
- Improved Dynamic Editor responsiveness by:
  - caching rendered expression text in side-panel tables,
  - refreshing only the visible `QToolBox` page,
  - avoiding full canvas rebuilds for parameter-only edits,
  - reducing expensive table resize behavior,
  - cleaning editor signal teardown on close.
- Made default catalogue loading more idempotent and cheaper by:
  - caching CSV-backed catalogue reads,
  - avoiding repeated repopulation when the default catalogue is already present,
  - enabling lazy loading for default RMS and EMT dynamic model catalogues so `Add default catalogue` does not instantiate heavy templates immediately,
  - preventing generic GUI dependency lookups from materializing the lazy dynamic catalogue right after the menu action,
  - replacing eager default EMT template instances with lazy placeholders that preserve the same visible catalogue entries while deferring block materialization until use.
- Added `Mode Parameter` support in the `Parameters` panel.
- Allowed EMT event selection to include both `event_dict` and `mode_dict` variables.
- Added a modal lookup-table dialog for one-dimensional linear tables with:
  - manual row editing,
  - add/remove row actions,
  - sort by x,
  - paste from clipboard,
  - keyboard shortcuts for copy, paste, and row deletion.
- Added a dedicated modal lookup-matrix dialog with:
  - editable x axis,
  - editable y axis,
  - editable z matrix,
  - add/remove x and y actions,
  - axis sorting,
  - paste from clipboard using a spreadsheet-style 2D surface,
  - keyboard shortcuts for copy, paste, and selection-aware deletion.
- Unlocked and tested the first 1D linear lookup-table family in the native catalog:
  - `lookup_array_linear`
  - `lookup_array_linear_noclipping`
  - `lookup_array_object_linear`
  - `lookup_array_object_linear_noclipping`
- Unlocked and tested the first 2D matrix linear lookup-table family in the native catalog:
  - `lookup_matrix_linear`
  - `lookup_matrix_object_linear`
- Added a runtime 1D lookup-template builder so modal-provided tables can create blocks with arbitrary point counts.
- Added a runtime 2D bilinear lookup-template builder so modal-provided matrix surfaces can create blocks with arbitrary axis sizes.
- Added GUI tests for:
  - clipboard parsing in the lookup modal,
  - modal-driven lookup block creation,
  - updated native-catalog counts after unlocking the new lookup descriptors.
- Added GUI tests for:
  - clipboard parsing in the lookup-matrix modal,
  - modal-driven lookup-matrix block creation.
- Added functional contracts for the newly unlocked 1D lookup descriptors.
- Added functional contracts for the newly unlocked 2D lookup-matrix descriptors.
- Added GUI and catalogue regression tests covering:
  - side-panel lazy refresh,
  - no scene rebuild on non-structural parameter edits,
  - `Mode Parameter` visibility,
  - default catalogue idempotence,
  - workspace editor teardown.
- Exposed `force_step_alignment` for EMT `mode_dict` events in the event dialog.
- Added dedicated EMT event-dialog tests covering:
  - enabled `force_step_alignment` for mode parameters,
  - disabled `force_step_alignment` for continuous event parameters.
- Unlocked and tested the inverse linear lookup-table family in the native catalog:
  - `inverse_lookup_array_linear`
  - `inverse_lookup_array_object_linear`
- Unlocked and tested the spline lookup-table family in the native catalog:
  - `lookup_array_spline`
  - `lookup_array_object_spline`
  - `lookup_matrix_spline`
  - `lookup_matrix_object_spline`
- Added runtime builders for:
  - inverse 1D linear lookup,
  - 1D natural cubic spline lookup,
  - 2D tensor-product spline lookup.
- Added modal-driven editor coverage for:
  - inverse lookup array creation,
  - spline lookup array creation,
  - spline lookup matrix creation.
- Relevant validations passed:
  - `src/tests/EMT/test_emt_system_validation.py`
  - `src/tests/EMT/test_emt_initialization_workflow.py`
  - `src/tests/EMT/test_simulation_with_event_emt.py`
  - `src/tests/EMT/test_alignment_step_three_solvers.py`
  - `src/tests/EMT/test_dynamic_events_editor_dialog.py`
  - `src/tests/RMS/test_simulation_with_event.py`
  - `src/tests/SmallSignal/test_small_signal_rms.py`
  - `src/tests/DynamicCatalog/test_dynamic_block_editor_catalog_gui.py`
  - `src/tests/DynamicCatalog/test_catalog_readiness.py`
  - `src/tests/DynamicCatalog/test_catalog_functional.py` (1D/2D linear, inverse, and spline lookup contracts)
  - `src/tests/Base/test_default_catalogue_idempotent.py`
  - `src/tests/DynamicEditor/test_dynamic_editor_workspace.py`
  - `src/tests/Base/test_tower_saving_issue.py`

## Notes For Next Session

- If the branch strategy is not resolved first, keep changes isolated and avoid broad refactors touching many existing files.
- The current lookup-table roadmap is functionally delivered for the planned native VeraGrid scope.
- The next large deferred target remains DGS / PF coupling only after a separate device-mapping decision.
