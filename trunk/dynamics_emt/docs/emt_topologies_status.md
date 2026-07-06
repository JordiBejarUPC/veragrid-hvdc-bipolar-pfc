# EMT Topologies Status

## Scope

This status note tracks the explicit EMT load-topology work delivered in the Dynamic Editor and EMT templates.

## Topology Semantics

- `Y`: floating star without external neutral terminal.
- `Yn`: star with explicit neutral terminal `N`.
- `Yg`: star with explicit neutral terminal plus automatic `Grounding Link EMT` in solid-bond mode.
- `Delta`: branch-oriented delta topology using the branch convention `A -> AB`, `B -> BC`, `C -> CA`.

## Reusable EMT Blocks

- `Ground EMT`: ideal one-terminal ground reference block.
- `Grounding Link EMT`: one-terminal configurable neutral-to-ground branch.
  - Supports `solid connection`.
  - Supports direct `R/L/C` values.
  - Supports `R + Reactances` modal conversion in the editor.

## Editor Support

### Modal-backed blocks

- `RLC Combo`
- `R load`
- `L load`
- `C load`
- `Exponential load`
- `ZIP load`
- `Grounding Link EMT`

### Supported topologies by block

| Block | Y | Yn | Yg | Delta |
| --- | --- | --- | --- | --- |
| `RLC Combo` | yes | yes | yes | yes |
| `R load` | yes | yes | yes | yes |
| `L load` | yes | yes | yes | yes |
| `C load` | yes | yes | yes | yes |
| `Exponential load` | yes | yes | yes | yes |
| `ZIP load` | yes | yes | yes | yes |

## Hierarchy Behavior

- `Edit Hierarchy` now persists and reopens the internal topology of wrapped EMT load blocks.
- `Yg` is no longer a hidden condition; it materializes an internal `Grounding Link EMT` child.
- `Modify Template` updates the preserved diagram when the rebuilt block carries a new internal topology.

## Runtime Validation Note

- EMT topology validation now recognizes internal grounding stored in the block `diagram`, not only live `children`.
- This is required because `set_emt_model()` flattens symbolic children with `unify_blocks()` before runtime.

## Demo Scripts

- `trunk/dynamics_emt/scripting_neutral_ground_shunt_emt.py`
  - Compares `y_floating`, `yg_solid`, and `yn_grounding_link`.
- `trunk/dynamics_emt/scripting_delta_loads_emt.py`
  - Runs delta EMT demos for `Exponential` and `ZIP` loads.

Wrapper demos:

- `trunk/implicit_solver_test_EMT/Demos/demo_neutral_ground_shunt_emt.py`
- `trunk/implicit_solver_test_EMT/Demos/demo_delta_loads_emt.py`

## Automated Coverage

- `src/tests/DynamicCatalog/test_dynamic_block_editor_catalog_gui.py`
- `src/tests/EMT/test_rlc_combo_emt_template.py`
- `src/tests/EMT/test_neutral_ground_shunt_emt_script.py`
- `src/tests/EMT/test_delta_loads_emt_script.py`
- `src/tests/EMT/test_emt_system_validation.py`

## Current Limits

- The `Grounding Link EMT` block is still modeled as a one-terminal branch to ground, not a generic two-terminal `N <-> G` branch.
- The delivered delta support is aimed at the load-style EMT workflows already exposed in the editor.
- No broader rewrite has been done for unrelated EMT devices such as generators, switches, or transformers beyond the validation compatibility needed for the grounding-link topology.

## Practical Outcome

At this point the Dynamic Editor can build, reopen, and simulate mixed EMT load topologies with explicit neutral and grounding semantics across the available load families.
