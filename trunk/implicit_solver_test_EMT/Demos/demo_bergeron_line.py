# ==============================================================================
# GENERALIZED EMT BERGERON LINE MODEL & STANDALONE DEMO
# ==============================================================================

import numpy as np
import matplotlib.pyplot as plt
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple

# VeraGridEngine Imports
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = []


class BoundaryUpdateWrapper(ABC):
    __slots__ = []

    @abstractmethod
    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        pass


class BergeronBoundaryUpdater(BoundaryUpdateWrapper):
    __slots__ = ['line', 'step_counter']

    def __init__(self, line: 'BergeronLineModel'):
        self.line = line
        self.step_counter: int = 0

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        self.line.update_history(self.step_counter, x, params)
        self.step_counter += 1


# ==============================================================================
# 1. GENERALIZED BERGERON MODEL (For emt_line.py)
# ==============================================================================
class BergeronLineModel:
    """
    Generalized N-phase implicit Bergeron Line Model.
    Designed to be instantiated in EmtProblemDae and solved via JitAdSolver.
    """
    __slots__ = [
        'name', 'Gc', 'H', 'num_phases', 'n_delay', 'buf_vf', 'buf_vt',
        'buf_if', 'buf_it', 'Ih_f', 'Ih_t', 'block', 'v_f_vars', 'v_t_vars',
        'idx_vf', 'idx_vt', 'idx_hf', 'idx_ht'
    ]

    def __init__(self, name: str, Gc: np.ndarray, H: np.ndarray, tau: float, h: float):
        self.idx_ht = None
        self.idx_vf = None
        self.idx_hf = None
        self.idx_vt = None
        self.v_t_vars = None
        self.v_f_vars = None
        self.name: str = name
        self.Gc: np.ndarray = np.asarray(Gc, dtype=np.float64)
        self.H: np.ndarray = np.asarray(H, dtype=np.float64)
        self.num_phases: int = self.Gc.shape[0]
        self.n_delay: int = max(1, int(round(tau / h)))

        # Circular buffers for history tracking
        self.buf_vf: np.ndarray = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_vt: np.ndarray = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_if: np.ndarray = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)
        self.buf_it: np.ndarray = np.zeros((self.n_delay + 1, self.num_phases), dtype=np.float64)

        self.Ih_f: List[Var] = list()
        self.Ih_t: List[Var] = list()
        for i in range(self.num_phases):
            self.Ih_f.append(Var(f"Ih_f_{name}_ph{i}"))
            self.Ih_t.append(Var(f"Ih_t_{name}_ph{i}"))

        # DAE Block: Map event parameters to initial Const(0.0)
        event_dict: Dict[Var, Expr] = dict()
        for var in self.Ih_f + self.Ih_t:
            event_dict[var] = Const(0.0)

        self.block: Block = Block(
            name=f"Bergeron_{name}",
            event_dict=event_dict
        )

    def get_nodal_injections(self, v_f_vars: List[Var], v_t_vars: List[Var]) -> Tuple[List[Expr], List[Expr]]:
        """
        Returns symbolic KCL current injections for the From and To buses.
        """
        self.v_f_vars = v_f_vars
        self.v_t_vars = v_t_vars

        i_f_exprs: List[Expr] = list()
        i_t_exprs: List[Expr] = list()

        for i in range(self.num_phases):
            i_f = sum(self.Gc[i, j] * self.v_f_vars[j] for j in range(self.num_phases)) + self.Ih_f[i]
            i_t = sum(self.Gc[i, j] * self.v_t_vars[j] for j in range(self.num_phases)) + self.Ih_t[i]

            i_f_exprs.append(i_f)
            i_t_exprs.append(i_t)

        return i_f_exprs, i_t_exprs

    def setup_indices(self, problem: GenericEmtProblem, vprms_offset: int = 0) -> None:
        """Maps symbolic UIDs to numerical array indices for the solver."""

        self.idx_vf = np.array([problem.uid2idx_vars[v.uid] for v in self.v_f_vars], dtype=np.int32)
        self.idx_vt = np.array([problem.uid2idx_vars[v.uid] for v in self.v_t_vars], dtype=np.int32)
        self.idx_hf = np.array([problem.uid2idx_event_params[p.uid] + vprms_offset for p in self.Ih_f], dtype=np.int32)
        self.idx_ht = np.array([problem.uid2idx_event_params[p.uid] + vprms_offset for p in self.Ih_t], dtype=np.int32)

    def update_history(self, step_counter: int, x_prev: np.ndarray, full_params: np.ndarray) -> None:
        """Evaluates history equations right before the Newton iteration."""
        k_curr: int = step_counter % (self.n_delay + 1)
        k_delay: int = (step_counter - self.n_delay) % (self.n_delay + 1)

        # 1. Read converged voltages from t_{n-1} using advanced indexing
        v_f_now = x_prev[self.idx_vf]
        v_t_now = x_prev[self.idx_vt]

        self.buf_vf[k_curr, :] = v_f_now
        self.buf_vt[k_curr, :] = v_t_now

        hf_vals = full_params[self.idx_hf]
        ht_vals = full_params[self.idx_ht]

        i_f_now = self.Gc @ v_f_now + hf_vals
        i_t_now = self.Gc @ v_t_now + ht_vals

        self.buf_if[k_curr, :] = i_f_now
        self.buf_it[k_curr, :] = i_t_now

        # 3. Retrieve delayed state (t_{n-1} - tau)
        v_f_tau = self.buf_vf[k_delay, :]
        v_t_tau = self.buf_vt[k_delay, :]
        i_f_tau = self.buf_if[k_delay, :]
        i_t_tau = self.buf_it[k_delay, :]

        # 4. Bergeron matrix math (Incident and reflected waves)
        X_f = -self.Gc @ v_t_tau - i_t_tau
        Y_f = -self.Gc @ v_f_tau - i_f_tau
        X_t = -self.Gc @ v_f_tau - i_f_tau
        Y_t = -self.Gc @ v_t_tau - i_t_tau

        I_mat = np.eye(self.num_phases)
        I_hist_f = 0.5 * ((I_mat + self.H) @ X_f + (I_mat - self.H) @ Y_f)
        I_hist_t = 0.5 * ((I_mat + self.H) @ X_t + (I_mat - self.H) @ Y_t)

        full_params[self.idx_hf] = I_hist_f
        full_params[self.idx_ht] = I_hist_t


# ==============================================================================
# 2. STANDALONE DEMO (Validation test)
# ==============================================================================
def create_test_system(R_load: float) -> Tuple[Block, BergeronLineModel, float, float, Var, Var]:
    """
    Creates a test grid: Ideal Voltage Source (Step) -> Line -> Resistive Load
    """
    Zc: float = 350.0
    tau: float = 0.005
    h: float = 1e-4
    V_step: float = 100.0

    Gc_mat: np.ndarray = np.array([[1.0 / Zc]])
    H_mat: np.ndarray = np.array([[1.0]])

    line = BergeronLineModel("L1", Gc=Gc_mat, H=H_mat, tau=tau, h=h)

    v_f = Var("v_f")
    v_t = Var("v_t")

    i_f_exprs, i_t_exprs = line.get_nodal_injections([v_f], [v_t])
    i_t_line = i_t_exprs[0]

    kcl_f = v_f - V_step

    if R_load > 1e6:
        kcl_t = i_t_line
    else:
        kcl_t = i_t_line + (v_t / R_load)

    sys_block = Block(
        name="TestGrid",
        algebraic_vars=[v_f, v_t],
        algebraic_eqs=[kcl_f, kcl_t]
    )
    sys_block.add(line.block)

    return sys_block, line, h, tau, v_f, v_t


def run_test(case_name: str, R_load: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Executes a single test case using JitAdSolver."""
    print(f"\n--- Running Test: {case_name} (R_load = {R_load} ohm) ---")

    sys_block, line, h, tau, v_f_var, v_t_var = create_test_system(R_load)
    sys_block.unify_blocks()
    glob_time = Var("t_glob")

    problem = GenericEmtProblem(sys_block=sys_block, glob_time=glob_time)
    line.setup_indices(problem, vprms_offset=0)
    line_updater = BergeronBoundaryUpdater(line)

    solver = JitAdSolver(
        problem=problem,
        t0=0.0,
        t_end=0.03,
        h=h,
        method=DynamicIntegrationMethod.DaeTrapezoidal,
        verbose=False
    )

    x0 = problem.get_x0()
    dx0 = np.zeros(problem.get_all_vars_number(), dtype=np.float64)
    params0 = problem.event_params_values

    t_arr, y_arr = solver.simulate(
        x0=x0,
        dx0=dx0,
        params0=params0,
        boundary_updater=line_updater
    )

    idx_vf: int = problem.get_var_idx(v_f_var)
    idx_vt: int = problem.get_var_idx(v_t_var)

    v_f_sol = y_arr[:, idx_vf]
    v_t_sol = y_arr[:, idx_vt]

    return t_arr, v_f_sol, v_t_sol, tau


def main() -> None:
    t1, vf1, vt1, tau = run_test("Open Circuit", R_load=1e9)
    t2, vf2, vt2, _ = run_test("Matched Load", R_load=350.0)

    plt.figure(figsize=(11, 6))
    plt.plot(t1 * 1000, vf1, 'k--', alpha=0.7, label="V_From (Ideal Source: 100V)")
    plt.plot(t1 * 1000, vt1, 'r-', linewidth=2, label="V_To (Open -> Total Reflection 200V)")
    plt.plot(t2 * 1000, vt2, 'b-', linewidth=2, label=r"V_To (Matched $Z_L = Z_c$ -> Stable 100V)")

    plt.axvline(x=tau * 1000, color='gray', linestyle=':', label=r"Wave Arrival (Multiples of $\tau$)")
    plt.axvline(x=3 * tau * 1000, color='gray', linestyle=':')
    plt.axvline(x=5 * tau * 1000, color='gray', linestyle=':')

    plt.title("EMT Architecture Validation: Generalized Implicit Bergeron DAE", fontsize=14, fontweight='bold')
    plt.xlabel("Time [ms]", fontsize=12)
    plt.ylabel("Node Voltage [V]", fontsize=12)
    plt.legend(loc="lower right")
    plt.grid(True, which='both', linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()