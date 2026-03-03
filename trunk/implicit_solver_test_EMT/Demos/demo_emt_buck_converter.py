# ==============================================================================
# EMT simulation of a DC-DC Buck Converter using the NEW ARCHITECTURE.
# ==============================================================================

import time
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, List, Dict

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate

from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver, BoundaryUpdateWrapper
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = []

class PWMControllerWrapper(BoundaryUpdateWrapper):
    __slots__ = ['t_sw', 'duty', 'v_in', 'offset', 'idx']

    def __init__(self, t_sw: float, duty: float, v_in: float, offset: int, idx: int):
        self.t_sw: float = t_sw
        self.duty: float = duty
        self.v_in: float = v_in
        self.offset: int = offset
        self.idx: int = idx

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        t_mod: float = t % self.t_sw
        if t_mod < (self.duty * self.t_sw):
            val: float = self.v_in
        else:
            val: float = 0.0
        params[self.offset + self.idx] = val


# -----------------------------------------------------------------------------
# Model definition
# -----------------------------------------------------------------------------

def create_buck_converter_system() -> Tuple[Block, Var]:
    i_L = Var("i_L")
    v_C = Var("v_C")

    Vin_sw = Var("Vin_sw")
    R = Var("R")
    L = Var("L")
    C = Var("C")

    state_vars: List[Var] = list([i_L, v_C])
    state_eqs: List[Expr] = list([
        (Vin_sw - v_C) / L,
        (i_L - v_C / R) / C,
    ])

    parameters: Dict[Var, Const] = dict({
        Vin_sw: Const(0.0),
        R: Const(5.0),
        L: Const(100e-6),
        C: Const(470e-6),
    })

    block = Block(
        name="BuckConverter",
        state_vars=state_vars,
        state_eqs=state_eqs,
        parameters=parameters,
    )

    return block, Vin_sw


# -----------------------------------------------------------------------------
# Simulation runner
# -----------------------------------------------------------------------------

def run_case(backend_str: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    print("\n" + "=" * 70)
    print(f"Running Buck Converter | Backend: {backend_str}")
    print("=" * 70)

    # --- Electrical / control parameters ---
    V_IN: float = 48.0
    V_OUT_REF: float = 12.0
    F_SW: float = 20e3
    T_SW: float = 1.0 / F_SW
    DUTY: float = V_OUT_REF / V_IN

    DT: float = 1e-6
    T_TOTAL: float = 0.020

    block, vin_var = create_buck_converter_system()
    block.unify_blocks()
    glob_time = Var("t_glob")

    problem = GenericEmtProblem(sys_block=block, glob_time=glob_time)
    problem.set_newton_trace_collector(NewtonTraceCollector())

    integration_method = DynamicIntegrationMethod.DaeTrapezoidal

    if backend_str == "SD":
        solver = JitSymbolicSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    elif backend_str == "AD":
        solver = JitAdSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    elif backend_str == "StructuralVectorizedSolver":
        solver = StructuralVectorizedSolver(
            problem, t0=0.0, t_end=T_TOTAL, h=DT,
            method=integration_method, verbose=False
        )
    else:
        raise ValueError(f"Unknown backend : {backend_str}")

    offset: int = problem.get_variable_parameter_number()
    idx: int = problem.uid2idx_params[vin_var.uid]
    pwm_updater = PWMControllerWrapper(T_SW, DUTY, V_IN, offset, idx)

    t_start: float = time.time()

    if backend_str == "SD":
        t_arr, y_arr = solver.simulate(boundary_updater=pwm_updater)
    else:
        x0: np.ndarray = problem.get_x0()
        dx0: np.ndarray = np.zeros(problem.get_all_vars_number(), dtype=np.float64)
        params0: np.ndarray = np.zeros(problem.get_variable_parameter_number(), dtype=np.float64)
        t_arr, y_arr = solver.simulate(x0=x0, dx0=dx0, params0=params0, boundary_updater=pwm_updater)

    elapsed: float = time.time() - t_start

    idx_iL: int = problem.get_var_idx(block.state_vars[0])
    idx_vC: int = problem.get_var_idx(block.state_vars[1])

    sol_i: np.ndarray = y_arr[:, idx_iL]
    sol_v: np.ndarray = y_arr[:, idx_vC]

    print(f"Elapsed time : {elapsed:.4f} s")
    print(f"Final V_out  : {sol_v[-1]:.6f} V")
    print(f"Final I_L    : {sol_i[-1]:.6f} A")

    collector = problem.get_newton_trace_collector()
    if collector:
        print(f"Newton iters : {len(collector.records)}")
    else:
        pass

    return t_arr, sol_v, sol_i, elapsed


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> None:
    t_sym, v_sym, i_sym, time_sym = run_case("SD")
    t_ad, v_ad, i_ad, time_ad = run_case("AD")
    t_vec, v_vec, i_vec, time_vec = run_case("StructuralVectorizedSolver")

    print("\n" + "-" * 70)
    print("COMPARISON SUMMARY (NEW SOLVERS)")
    print("-" * 70)
    print(f"SD (Symbolic) time : {time_sym:.4f} s")
    print(f"AD time            : {time_ad:.4f} s")
    print(f"StructuralVectorizedSolver time        : {time_vec:.4f} s")

    err_ad_v = np.max(np.abs(v_sym - v_ad))
    err_vec_v = np.max(np.abs(v_sym - v_vec))

    print("-" * 30)
    print(f"Max Error AD vs SD      : {err_ad_v:.3e}")
    print(f"Max Error StructuralVectorizedSolver vs SD  : {err_vec_v:.3e}")

    assert np.allclose(v_sym, v_ad, atol=1e-5), "AD Solver Failed Accuracy Check!"
    assert np.allclose(v_sym, v_vec, atol=1e-5), "StructuralVectorizedSolver Solver Failed Accuracy Check!"

    print("\n>>> SUCCESS: All new engines produced identical physical results.")

    plt.figure(figsize=(10, 8))

    plt.subplot(2, 1, 1)
    plt.plot(t_sym * 1000, v_sym, 'k-', linewidth=4, alpha=0.3, label='SD (Reference)')
    plt.plot(t_ad * 1000, v_ad, 'b--', label='AD')
    plt.plot(t_vec * 1000, v_vec, 'r:', linewidth=2, label='StructuralVectorizedSolver')
    plt.ylabel('Voltage [V]')
    plt.title('Buck Converter: New Architecture Consistency Check')
    plt.legend()
    plt.grid(True)

    plt.subplot(2, 1, 2)
    plt.plot(t_sym * 1000, i_sym, 'k-', linewidth=4, alpha=0.3, label='SD')
    plt.plot(t_ad * 1000, i_ad, 'b--', label='AD')
    plt.plot(t_vec * 1000, i_vec, 'r:', linewidth=2, label='StructuralVectorizedSolver')
    plt.ylabel('Current [A]')
    plt.xlabel('Time [ms]')
    plt.legend()
    plt.grid(True)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()