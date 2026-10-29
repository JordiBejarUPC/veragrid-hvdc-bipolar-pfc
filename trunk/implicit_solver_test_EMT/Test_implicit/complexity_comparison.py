# ==============================================================================
# Complexity Benchmark (Big-O Empirical Analysis) for EMT Solvers
# ==============================================================================

import time
import numpy as np
from typing import List, Dict, Any

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.enumerations import DynamicIntegrationMethod

# Unified Solver Suite
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver


# --- CONCRETE CLASS FOR BENCHMARK ---
class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


def estimate_big_o(ns: np.ndarray, times: np.ndarray) -> str:
    """Calculates empirical complexity using Log-Log regression slope (m)."""
    if len(ns) < 2:
        return "N/A"
    else:
        pass

    valid: List[int] = list([i for i, t in enumerate(times) if t > 0.000001])

    if len(valid) < 2:
        return "O(1) Constant"
    else:
        pass

    log_n: np.ndarray = np.log([ns[i] for i in valid])
    log_t: np.ndarray = np.log([times[i] for i in valid])
    slope, _ = np.polyfit(log_n, log_t, 1)

    if slope < 0.3: return f"O(1) (m={slope:.2f})"
    if 0.8 <= slope <= 1.3: return f"O(N) Linear (m={slope:.2f})"
    if 1.8 <= slope <= 2.5: return f"O(N^2) Quadratic (m={slope:.2f})"
    return f"O(N^{slope:.2f})"

def benchmark_new_architecture(n_oscillators: int, n_steps: int, backend: str = "SD") -> Dict[str, float]:
    """Isolates Setup (Assembly) and Run (Physics) phases for complexity analysis."""

    k_sym: Var = Var("k")

    vars_pos: List[Var] = list([Var(f"x_{i}") for i in range(n_oscillators)])
    vars_vel: List[Var] = list([Var(f"v_{i}") for i in range(n_oscillators)])

    dvars_pos: List[Var] = list([Var(f"dx_{i}", base_var=v) for i, v in enumerate(vars_pos)])
    dvars_vel: List[Var] = list([Var(f"dv_{i}", base_var=v) for i, v in enumerate(vars_vel)])

    state_vars: List[Var] = list()
    state_eqs: List[Expr] = list()
    diff_vars: List[Var] = list()

    for i in range(n_oscillators):
        x_i: Var = vars_pos[i]
        v_i: Var = vars_vel[i]
        dx_i: Var = dvars_pos[i]
        dv_i: Var = dvars_vel[i]

        if i > 0:
            x_L: Expr = vars_pos[i - 1]
        else:
            x_L = Const(0.0)

        if i < n_oscillators - 1:
            x_R: Expr = vars_pos[i + 1]
        else:
            x_R = Const(0.0)

        force: Expr = k_sym * (x_L - x_i) + k_sym * (x_R - x_i) - 0.5 * v_i

        state_vars.extend(list([x_i, v_i]))
        state_eqs.extend(list([v_i, force]))
        diff_vars.extend(list([dx_i, dv_i]))

    block: Block = Block(
        name="Chain",
        state_vars=state_vars,
        state_eqs=state_eqs,
        parameters=dict({k_sym: Const(10.0)})
    )
    block.diff_vars = diff_vars
    block.unify_blocks()

    problem: GenericEmtProblem = GenericEmtProblem(block, Var("t_glob"))
    h: float = 0.01
    target_method: DynamicIntegrationMethod = DynamicIntegrationMethod.DaeTrapezoidal

    # --- PHASE 1: ASSEMBLY/SETUP ---
    t_setup_start: float = time.perf_counter()

    solver: Any
    if backend == "SD":
        solver = JitSymbolicSolver(problem, t0=0.0, t_end=h, h=h, method=target_method)
    elif backend == "AD":
        solver = JitAdSolver(problem, t0=0.0, t_end=h, h=h, method=target_method)
    elif backend == "StructuralVectorizedSolver":
        solver = StructuralVectorizedSolver(problem, t0=0.0, t_end=h, h=h, method=target_method)
    else:
        raise ValueError(f"Unknown backend: {backend}")

    x0: np.ndarray = problem.get_x0()
    dx0: np.ndarray = np.zeros(len(state_vars), dtype=np.float64)
    p0: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)

    # Warmup
    if backend == "SD":
        solver.simulate()
    else:
        solver.simulate()

    t_setup: float = time.perf_counter() - t_setup_start

    # --- PHASE 2: INTEGRATION/SIMULATION ---
    t_run_start: float = time.perf_counter()

    if backend == "SD":
        solver_run = JitSymbolicSolver(problem, t0=0.0, t_end=h * n_steps, h=h, method=target_method)
        solver_run.simulate()
        t_run: float = time.perf_counter() - t_run_start
    elif backend == "AD":
        solver.t_end = h * n_steps
        solver.simulate()
        t_run: float = getattr(solver, 'last_sim_loop_time', time.perf_counter() - t_run_start)
    elif backend == "StructuralVectorizedSolver":
        solver.t_end = h * n_steps
        solver.simulate()
        t_run: float = getattr(solver, '_last_sim_loop_time', time.perf_counter() - t_run_start)
    else:
        t_run = 0.0

    return dict({'run': t_run, 'setup': t_setup})


def run_full_analysis() -> None:
    print("=" * 100)
    print(f"{'ARCHITECTURAL DUAL-COMPLEXITY ANALYSIS (BIG-O)':^100}")
    print("=" * 100)

    sizes: List[int] = list([10, 50, 100, 200, 400])
    backends: List[str] = list(["SD", "AD", "StructuralVectorizedSolver"])

    results: Dict[str, Dict[str, List[float]]] = dict()
    for b in backends:
        results[b] = dict({'run': list(), 'setup': list()})

    for b in backends:
        print(f"\n>>> Profiling Backend: {b}")
        print(f"{'States (2N)':<14} | {'Run Time (s)':<16} | {'Setup Time (s)':<12}")
        print("-" * 50)
        for N in sizes:
            res: Dict[str, float] = benchmark_new_architecture(N, 100, backend=b)
            results[b]['run'].append(res['run'])
            results[b]['setup'].append(res['setup'])
            print(f"{N * 2:<14} | {res['run']:.6f}         | {res['setup']:.4f}")

    # Results Summary
    print("\n" + "=" * 100)
    print(f"{'COMPLEXITY CLASS SUMMARY':^100}")
    print("=" * 100)
    print(f"{'Backend':<30} | {'Setup Complexity':<30} | {'Sim Complexity':<30}")
    print("-" * 100)
    for b in backends:
        ns_arr: np.ndarray = np.array(sizes) * 2
        setup_arr: np.ndarray = np.array(results[b]['setup'])
        sim_arr: np.ndarray = np.array(results[b]['run'])

        setup_comp: str = estimate_big_o(ns_arr, setup_arr)
        sim_comp: str = estimate_big_o(ns_arr, sim_arr)

        print(f"{b:<30} | {setup_comp:<30} | {sim_comp:<30}")
    print("=" * 100)


if __name__ == "__main__":
    run_full_analysis()