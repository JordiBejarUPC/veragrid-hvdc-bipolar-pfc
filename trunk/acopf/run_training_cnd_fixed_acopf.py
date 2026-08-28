import VeraGridEngine as vg

from VeraGridEngine.Devices.Branches.transformer import Transformer2W
from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.types import BRANCH_TYPES
from VeraGridEngine.Simulations.OPF.Formulations.ac_opf_problem import NonlinearOPFResults


file_name: str = "/home/santi/Git/eRoots/VeraGridDemos/Trainings/CND/Training_CND_19AUG2026_real.veragrid"
grid: MultiCircuit = vg.open_file(file_name)

if grid is not None:
    phase_shift_count: int = 0
    zero_rate_monitor_count: int = 0
    branches: list[BRANCH_TYPES] = grid.get_branches(add_hvdc=False, add_vsc=False, add_switch=True)

    for branch in branches:
        if isinstance(branch, Transformer2W):
            if abs(branch.tap_phase) > 0.0:
                branch.tap_phase = 0.0
                phase_shift_count += 1
            else:
                pass
        else:
            pass

        if branch.active and branch.monitor_loading and branch.rate <= 0.0:
            branch.monitor_loading = False
            zero_rate_monitor_count += 1
        else:
            pass

    options: vg.OptimalPowerFlowOptions = vg.OptimalPowerFlowOptions(
        solver=vg.SolverType.NONLINEAR_OPF,
        ips_method=vg.SolverType.NR_PC,
        ips_iterations=200,
        verbose=0
    )
    results: NonlinearOPFResults = vg.nonlinear_opf(grid, options)

    print("phase shifts cleared:", phase_shift_count)
    print("zero-rate monitors disabled:", zero_rate_monitor_count)
    print("converged:", results.converged)
    print("iterations:", results.iterations)
    print("error:", results.error)
else:
    print("Could not open:", file_name)
