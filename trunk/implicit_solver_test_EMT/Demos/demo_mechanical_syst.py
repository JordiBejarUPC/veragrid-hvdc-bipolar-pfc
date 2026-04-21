# ==============================================================================
# EMT simulation of a mechanical system.
# ==============================================================================

import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Tuple, List, Dict

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.diagnostic import NewtonTraceCollector

from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate

from VeraGridEngine.Simulations.EMT.solvers.solver_AD import JitAdSolver
from VeraGridEngine.Simulations.EMT.solvers.StructuralVectorizedSolver import StructuralVectorizedSolver
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver
from VeraGridEngine.Simulations.EMT.solvers.structural_compiled_solver import StructuralCompiledSolver
from VeraGridEngine.enumerations import DynamicIntegrationMethod, EmtSolverTypes
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Simulations.EMT.initialization_emt import init_explicit_emt


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = []

    def __init__(self,
                 sys_block: Block,
                 glob_time: Var):

        super().__init__(sys_block=sys_block, glob_time=glob_time)

        self._run_explicit_initialization()

    def _run_explicit_initialization(self):
        """
        Runs init_explicit for every block that defines init_eqs.

        - init_explicit expects sys_vars: Dict[int, Var] (it only uses len(sys_vars) but we comply)
        - init_explicit may MODIFY self._event_parameters_eqs (fill Const(None) -> Const(val)).
          BaseProblem builds event fn from a COPY; therefore we MUST rebuild runtime vectors after.
        """

        # sys_vars dict (uid -> Var), size = n_vars
        sys_vars: Dict[int, Var] = {v.uid: v for v in (self._state_vars + self._algebraic_vars)}
        sys_diff_vars: Dict[int, Var] = {dv.uid: dv for dv in self._diff_vars}

        try:
            init_explicit_emt(
                mdl=self.sys_block,
                sys_vars=sys_vars,
                sys_diff_vars=sys_diff_vars,
                variable_parameters=self._variable_parameters,
                event_parameters_eqs=self._event_parameters_eqs,
                constant_parameters=self._constant_parameters,
                init_guess=self.init_guess,
                diff_init_guess=self.diff_init_guess,
                uid2idx_vars=self.uid2idx_vars,
                uid2idx_diff=self.uid2idx_diff,
                uid2idx_params=self.uid2idx_params,
                uid2idx_event_params=self.uid2idx_event_params,
                compiler_names_dict=self._compiler_names_dict,
                alias_names_dict=self._alias_names_dict,
                VARIABLE_PARAMS_NAME=self.VARIABLE_PARAMS_NAME,
                VARS_NAME=self.VARS_NAME,
                DIFF_NAME=self.DIFF_NAME,
                CONSTANT_PARAMS_NAME=self.CONSTANT_PARAMS_NAME
            )
        except Exception as e:
            print(f"[EMT][init_explicit] failed for block '{getattr(self.sys_block, 'name', 'unknown')}'. Error: {e}")

        self._build_runtime_param_vectors()

    def get_init_guess_table(self,
                             include_all_vars: bool = True,
                             only_in_init_guess: bool = False,
                             tol_zero: float = 1e-12) -> pd.DataFrame:
        """
        Return a table with uid, alias/name and initial value for each variable.

        include_all_vars:
            - True: include all state+algebraic vars, even if not in init_guess (value=0).
            - False: include only uids present in init_guess (or only_in_init_guess=True).

        only_in_init_guess:
            - True: filter to only those explicitly initialized (uid in init_guess).
            - False: keep everything (depending on include_all_vars).

        tol_zero:
            threshold to flag values close to zero.
        """
        # Build x0 and dx0 from current guesses
        x0 = self.get_x0()
        dx0 = self.get_dx0()

        uid2idx_vars = self.uid2idx_vars
        uid2idx_diff = self.uid2idx_diff

        # Define the sets we want to process: (Variables, Guess_Source, Index_Map, Vector, Label)
        data_sets = [
            (list(self.get_state_vars()) + list(self.get_algebraic_vars()), self.init_guess, uid2idx_vars, x0, "Var"),
            (list(self.get_diff_vars()), self.diff_init_guess, uid2idx_diff, dx0, "DiffVar")
        ]

        rows = []
        for vars_list, guess_dict, idx_map, vector, var_type in data_sets:
            for v in vars_list:
                uid = v.uid
                idx = idx_map.get(uid, None)
                val = float(vector[idx]) if idx is not None else 0.0

                in_guess = uid in guess_dict

                keep_row = True
                if only_in_init_guess and (not in_guess):
                    keep_row = False
                if (not include_all_vars) and (not in_guess):
                    keep_row = False

                if keep_row:
                    alias = self._alias_names_dict.get(uid, None) if hasattr(self, "_alias_names_dict") else None

                    rows.append({
                        "uid": uid,
                        "type": var_type,
                        "idx": idx,  # add this
                        "alias": alias,
                        "name": v.name,
                        "value": val,
                        "in_init_guess": in_guess,
                        "is_zero": abs(val) <= tol_zero,
                    })
                else:
                    pass

        df = pd.DataFrame(rows)

        # Nice ordering: Group by type, then initialization status
        if not df.empty:
            df = df.sort_values(["type", "idx"], ascending=[False, True])

        return df


# -----------------------------------------------------------------------------
# Model definition
# -----------------------------------------------------------------------------

def create_mechanical_system(vf: VarFactory) -> Tuple[Block, Var]:
    # state vars
    theta = vf.add_var("theta")
    omega = vf.add_var("omega")

    # algebraic vars
    Tm = vf.add_var("Tm")
    Te = vf.add_var("Te")

    # parameters
    D = vf.add_var("D")
    H = vf.add_var("H")
    omega_ref = vf.add_var("omega_ref")

    # derivatives
    d_theta = vf.add_diff_var(name="d_theta", base_var=theta)
    d_omega = vf.add_diff_var(name="d_omega", base_var=omega)

    state_vars: List[Var] = list([theta, omega])
    diff_vars: List[Var] = list([d_theta, d_omega])
    state_eqs: List[Expr] = list([
        omega,
        (Tm - Te - D * (omega - omega_ref)) / (2 * H)
    ])
    algebraic_vars: List[Var] = list([Tm, Te])
    algebraic_eqs: List[Expr] = list([
        Tm - Const(1),
        Te - Const(1)
    ])

    parameters: Dict[Var, Const] = dict({
        D: Const(2.0),
        H: Const(5.0),
        omega_ref: Const(1.0),
    })

    init_eqs: Dict[Var, Const] = dict({
        theta: Const(0.0),
        omega: Const(1.0),
        Tm: Const(1.0),
        Te: Const(1.0)
    })

    diff_init_eqs: Dict[Var, Const] = dict({
        d_theta: Const(1.0),
        d_omega: Const(0.0),
    })

    block = Block(
        name="MechanicalSystem",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        algebraic_vars=algebraic_vars,
        algebraic_eqs=algebraic_eqs,
        parameters=parameters,
        init_eqs=init_eqs,
        diff_init_eqs=diff_init_eqs
    )

    return block, theta


# -----------------------------------------------------------------------------
# Simulation runner
# -----------------------------------------------------------------------------

def run_case(backend_str: EmtSolverTypes,
             h: float,
             t_end: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    print("\n" + "=" * 70)
    print(f"Running Mechanical system | Backend: {backend_str}")
    print("=" * 70)

    vf = VarFactory()
    block, vin_var = create_mechanical_system(vf=vf)
    block.unify_blocks()
    glob_time = vf.add_var("t_glob")

    problem = GenericEmtProblem(sys_block=block, glob_time=glob_time)
    problem.set_newton_trace_collector(NewtonTraceCollector())

    df = problem.get_init_guess_table()
    print(f"{df}")

    integration_method = DynamicIntegrationMethod.DaeTrapezoidal
    predictor_method = DynamicIntegrationMethod.OdeEuler

    if backend_str == EmtSolverTypes.Symbolic:
        solver = JitSymbolicSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=integration_method, pred_method=predictor_method, verbose=True
        )
    elif backend_str == EmtSolverTypes.Automatic:
        solver = JitAdSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=integration_method, verbose=False
        )
    elif backend_str == EmtSolverTypes.StructuralAD:
        solver = StructuralVectorizedSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=integration_method, verbose=False
        )
    elif backend_str == EmtSolverTypes.StructuralCompiled:
        solver = StructuralCompiledSolver(
            problem, t0=0.0, t_end=t_end, h=h,
            method=integration_method, verbose=False
        )
    else:
        raise ValueError(f"Unknown backend : {backend_str}")

    t_start: float = time.time()

    t_arr, y_arr, dy_arr = solver.simulate()

    elapsed: float = time.time() - t_start

    idx_theta: int = problem.get_var_idx(block.state_vars[0])
    idx_omega: int = problem.get_var_idx(block.state_vars[1])

    idx_d_theta: int = problem.get_diff_var_idx(block.diff_vars[0])
    idx_d_omega: int = problem.get_diff_var_idx(block.diff_vars[1])

    sol_theta: np.ndarray = y_arr[:, idx_theta]
    sol_omega: np.ndarray = y_arr[:, idx_omega]

    sol_d_theta: np.ndarray = dy_arr[:, idx_d_theta]
    sol_d_omega: np.ndarray = dy_arr[:, idx_d_omega]

    print(f"Elapsed time : {elapsed:.4f} s")
    print(f"Final V_out  : {sol_theta[-1]:.6f} V")
    print(f"Final I_L    : {sol_omega[-1]:.6f} A")

    collector = problem.get_newton_trace_collector()
    if collector:
        print(f"Newton iters : {len(collector.records)}")
    else:
        pass

    return t_arr, y_arr, dy_arr, sol_theta, sol_omega, sol_d_theta, sol_d_omega, elapsed


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main() -> None:
    h = 1e-6
    t_end = 0.01

    (t_sym_sd, y_sd, dy_sd, sol_theta_sd, sol_omega_sd,
     sol_d_theta_sd, sol_d_omega_sd, time_sym_sd) = run_case(backend_str=EmtSolverTypes.Symbolic, h=h, t_end=t_end)
    (t_sym_ad, y_ad, dy_ad, sol_theta_ad, sol_omega_ad,
     sol_d_theta_ad, sol_d_omega_ad, time_sym_ad) = run_case(backend_str=EmtSolverTypes.Automatic, h=h, t_end=t_end)
    (t_sym_vec, y_vec, dy_vec, sol_theta_vec, sol_omega_vec,
     sol_d_theta_vec, sol_d_omega_vec, time_sym_vec) = run_case(backend_str=EmtSolverTypes.StructuralAD, h=h, t_end=t_end)
    (t_sym_comp, y_comp, dy_comp, sol_theta_comp, sol_omega_comp,
     sol_d_theta_comp, sol_d_omega_comp, time_sym_comp) = run_case(backend_str=EmtSolverTypes.StructuralCompiled,h=h,
                                                                      t_end=t_end)

    steps: int = int(t_end / h)
    tme: np.ndarray = np.linspace(0, t_end, steps)

    res = np.concatenate((y_sd, dy_sd, y_ad, dy_ad, y_vec, dy_vec, y_comp, dy_comp), axis=1)

    cols_y_sd = [f"y_sd{i}" for i in range(y_sd.shape[1])]
    cols_dy_sd = [f"dy_sd{i}" for i in range(dy_sd.shape[1])]
    cols_y_ad = [f"y_ad{i}" for i in range(y_ad.shape[1])]
    cols_dy_ad = [f"dy_ad{i}" for i in range(dy_ad.shape[1])]
    cols_y_vec = [f"y_vec{i}" for i in range(y_vec.shape[1])]
    cols_dy_vec = [f"dy_vec{i}" for i in range(dy_vec.shape[1])]
    cols_y_comp = [f"y_comp{i}" for i in range(y_comp.shape[1])]
    cols_dy_comp = [f"dy_comp{i}" for i in range(dy_comp.shape[1])]
    cols = cols_y_sd + cols_dy_sd + cols_y_ad + cols_dy_ad + cols_y_vec + cols_dy_vec + cols_y_comp + cols_dy_comp

    results_df = pd.DataFrame(res, index=t_sym_sd, columns=cols)
    results_df.index.name = "time_s"

    name = "demo_check_derivatives.csv"
    results_df.to_csv(name, index=False)

    plt.figure(figsize=(12, 8))

    plt.subplot(3, 4, 1)
    plt.plot(tme, sol_theta_sd[:len(tme)], label='Theta (rad)', color='blue')
    plt.title("Angle Symbolic solver")
    plt.xlabel("Time")
    plt.ylabel("Angle")
    plt.legend(loc='upper left')
    plt.grid(True)
    plt.legend()

    plt.subplot(3, 4, 5)
    plt.plot(tme, sol_omega_sd[:len(tme)], label='Omega (rad/s)', color='blue')
    plt.plot(tme, sol_d_theta_sd[:len(tme)], label='d_theta (rad/s)', color='red')
    plt.title("Speed Symbolic solver")
    plt.xlabel("Time")
    plt.ylabel("Speed")
    plt.legend(loc='upper left')
    plt.grid(True)

    plt.subplot(3, 4, 9)
    plt.plot(tme, sol_d_omega_sd[:len(tme)], label='d_omega (rad/s2)', color='red')
    plt.title("Acceleration Symbolic solver")
    plt.xlabel("Time")
    plt.ylabel("Acceleration")
    plt.legend(loc='upper left')
    plt.grid(True)

    plt.subplot(3, 4, 2)
    plt.plot(tme, sol_theta_ad[:len(tme)], label='Theta (rad)', color='blue')
    plt.title("Angle AD solver")
    plt.xlabel("Time")
    plt.ylabel("Angle")
    plt.legend(loc='upper left')
    plt.grid(True)
    plt.legend()

    plt.subplot(3, 4, 6)
    plt.plot(tme, sol_omega_ad[:len(tme)], label='Omega (rad/s)', color='blue')
    plt.plot(tme, sol_d_theta_ad[:len(tme)], label='d_theta (rad/s)', color='red')
    plt.title("Speed AD solver")
    plt.xlabel("Time")
    plt.ylabel("Speed")
    plt.legend(loc='upper left')
    plt.grid(True)

    plt.subplot(3, 4, 10)
    plt.plot(tme, sol_d_omega_ad[:len(tme)], label='d_omega (rad/s2)', color='red')
    plt.title("Acceleration AD solver")
    plt.xlabel("Time")
    plt.ylabel("Acceleration")
    plt.legend(loc='upper left')
    plt.grid(True)

    plt.subplot(3, 4, 3)
    plt.plot(tme, sol_theta_vec[:len(tme)], label='Theta (rad)', color='blue')
    plt.title("Angle Structural Vectorized solver")
    plt.xlabel("Time")
    plt.ylabel("Angle")
    plt.legend(loc='upper left')
    plt.grid(True)
    plt.legend()

    plt.subplot(3, 4, 7)
    plt.plot(tme, sol_omega_vec[:len(tme)], label='Omega (rad/s)', color='blue')
    plt.plot(tme, sol_d_theta_vec[:len(tme)], label='d_theta (rad/s)', color='red')
    plt.title("Speed Structural Vectorized solver")
    plt.xlabel("Time")
    plt.ylabel("Speed")
    plt.legend(loc='upper left')
    plt.grid(True)

    plt.subplot(3, 4, 11)
    plt.plot(tme, sol_d_omega_vec[:len(tme)], label='d_omega (rad/s2)', color='red')
    plt.title("Acceleration Structural Vectorized solver")
    plt.xlabel("Time")
    plt.ylabel("Acceleration")
    plt.legend(loc='upper left')
    plt.grid(True)

    plt.subplot(3, 4, 4)
    plt.plot(tme, sol_theta_comp[:len(tme)], label='Theta (rad)', color='blue')
    plt.title("Angle Structural Compiled solver")
    plt.xlabel("Time")
    plt.ylabel("Angle")
    plt.legend(loc='upper left')
    plt.grid(True)
    plt.legend()

    plt.subplot(3, 4, 8)
    plt.plot(tme, sol_omega_comp[:len(tme)], label='Omega (rad/s)', color='blue')
    plt.plot(tme, sol_d_theta_comp[:len(tme)], label='d_theta (rad/s)', color='red')
    plt.title("Speed Structural Compiled solver")
    plt.xlabel("Time")
    plt.ylabel("Speed")
    plt.legend(loc='upper left')
    plt.grid(True)

    plt.subplot(3, 4, 12)
    plt.plot(tme, sol_d_omega_comp[:len(tme)], label='d_omega (rad/s2)', color='red')
    plt.title("Acceleration Structural Compiled solver")
    plt.xlabel("Time")
    plt.ylabel("Acceleration")
    plt.legend(loc='upper left')
    plt.grid(True)

    plt.tight_layout()
    print("Generating plots...")
    plt.show()


if __name__ == "__main__":
    main()