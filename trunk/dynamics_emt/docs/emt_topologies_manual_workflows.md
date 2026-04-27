# EMT Topologies Manual Workflows

## Goal

This note documents practical editor workflows for the delivered EMT topology support.

## Workflow 1: Mixed Star Topologies On One Bus

1. Open the EMT Dynamic Editor for a load-capable device.
2. Insert one `R load` configured as `Y`.
3. Insert one `RLC Combo` configured as `Yn`.
4. Insert one `ZIP load` configured as `Yg`.
5. Open `Edit Hierarchy` on the `Yg` block and inspect the auto-created `Grounding Link EMT`.

Expected result:

- The floating `Y` block has no external neutral port.
- The `Yn` block exposes `N` without grounding.
- The `Yg` block exposes `N` and contains an internal `Grounding Link EMT`.

## Workflow 2: Manual Neutral Grounding

1. Create one load block in `Yn`.
2. Open `Edit Hierarchy`.
3. Add one `Grounding Link EMT` block from the library.
4. Connect the `N` port into the grounding link.
5. Modify the grounding link to choose:
   - solid bond,
   - direct `R/L/C`, or
   - `R + Reactances`.

Expected result:

- The user controls grounding explicitly instead of relying on hidden internal grounding.

## Workflow 3: Delta Loads

1. Create one `R load`, `Exponential load`, or `ZIP load`.
2. Select `Delta` in the creation modal.
3. Choose active phases.

Interpretation:

- `A` maps to branch `AB`.
- `B` maps to branch `BC`.
- `C` maps to branch `CA`.

Notes:

- Single-phase delta is rejected.
- Two-phase delta is accepted when it maps to at least one physical delta branch.

## Workflow 4: Compare Grounding Cases With Scripts

Use the scripts when you want a reproducible non-GUI comparison.

- Neutral and grounding comparison:
  - `trunk/dynamics_emt/scripting_neutral_ground_shunt_emt.py`
- Delta `Exponential` and `ZIP` cases:
  - `trunk/dynamics_emt/scripting_delta_loads_emt.py`

Both scripts export PNGs under `trunk/dynamics_emt/plot_results/`.

## Workflow 5: Reconfigure Existing Blocks

1. Right-click the EMT block.
2. Use `Modify Template`.
3. Change topology or electrical values.
4. Reopen `Edit Hierarchy` if needed.

Expected result:

- The rebuilt block preserves identity in the parent editor.
- The internal diagram is refreshed when topology actually changes.

## Recommended Manual Demo Matrix

Use this small matrix when manually smoke-testing topologies in the editor.

| Block | Cases to try |
| --- | --- |
| `R load` | `Y`, `Yn`, `Yg`, `Delta` |
| `RLC Combo` | `Yg` solid, `Yn + Grounding Link EMT`, `Delta` |
| `Exponential load` | `Yn`, `Yg`, `Delta` |
| `ZIP load` | `Yn`, `Yg`, `Delta` |

## Debug Tips

- If `Edit Hierarchy` looks empty, the block likely predates the persisted topology-diagram work and should be rebuilt through `Modify Template`.
- If a neutral case is rejected as floating at runtime, make sure the bus-side network actually provides a neutral path or a grounding path that the EMT validator can see.
