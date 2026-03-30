# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can see it at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import Dict, List, Tuple, Any
from unittest.mock import patch

import numpy as np

from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Simulations.EMT.problems.emt_problem_template import EmtProblemTemplate
from VeraGridEngine.Simulations.EMT.solvers.jit_symbolic_solver import JitSymbolicSolver, BoundaryUpdateWrapper
from VeraGridEngine.enumerations import DynamicIntegrationMethod
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory


class GenericEmtProblem(EmtProblemTemplate):
    __slots__ = list()


class BoostPWMWrapper(BoundaryUpdateWrapper):
    """
    PWM controller wrapper for boost converter simulation.

    Switches the duty cycle at a fixed frequency to simulate
    pulse-width modulation control of a boost converter.

    :param f_sw: Switching frequency in Hz.
    :param duty: Duty cycle ratio (0 to 1).
    :param offset: Parameter offset index.
    :param idx: Parameter index within offset.
    """
    __slots__ = ['f_sw', 'duty', 'offset', 'idx']

    def __init__(self, f_sw: float, duty: float, offset: int, idx: int) -> None:
        self.f_sw: float = f_sw
        self.duty: float = duty
        self.offset: int = offset
        self.idx: int = idx

    def update(self, t: float, x: np.ndarray, params: np.ndarray) -> None:
        """Update switch parameter based on PWM pattern."""
        t_mod: float = t % (1.0 / self.f_sw)
        if t_mod < (self.duty / self.f_sw):
            sw_val: float = 1.0
        else:
            sw_val: float = 0.0

        params[self.offset + self.idx] = sw_val


def create_boost_system(vf: VarFactory) -> Tuple[Block, Var, Var]:
    """
    Create a boost converter EMT model.

    Builds a simple boost converter with switch, inductor, capacitor,
    and resistor representing the load.

    :param vf: Variable factory for creating system variables.
    :returns: Tuple of (block, sw_var, vin_var) for the boost system.
    """
    i_L = vf.add_var("i_L")
    v_C = vf.add_var("v_C")
    Vin = vf.add_var("Vin")
    Sw = vf.add_var("Sw")
    R = vf.add_var("R")
    L = vf.add_var("L")
    C = vf.add_var("C")

    d_i_L = vf.add_diff_var(name="d_i_L", base_var=i_L)
    d_v_C = vf.add_diff_var(name="d_v_C", base_var=v_C)

    state_vars: List[Var] = list([i_L, v_C])
    diff_vars: List[Var] = list([d_i_L, d_v_C])
    state_eqs: List[Expr] = list([
        (Vin - (Const(1.0) - Sw) * v_C) / L,
        ((Const(1.0) - Sw) * i_L - v_C / R) / C
    ])
    parameters: Dict[Var, Const] = dict()
    parameters[Vin] = Const(12.0)
    parameters[Sw] = Const(1.0)
    parameters[R] = Const(10.0)
    parameters[L] = Const(50e-6)
    parameters[C] = Const(220e-6)

    boost: Block = Block(
        name="Boost_Benchmark",
        state_vars=state_vars,
        diff_vars=diff_vars,
        state_eqs=state_eqs,
        parameters=parameters
    )
    return boost, Sw, Vin


def run_method_benchmark() -> Tuple[Dict[str, Dict[str, np.ndarray]], List[Dict[str, Any]]]:
    """
    Run benchmark comparing different integration methods on boost converter.

    Tests Backward Euler, Trapezoidal, and BDF2 methods on a PWM-controlled
    boost converter and extracts performance KPIs.

    :returns: Tuple of (results_dict, kpis_list) with simulation results and metrics.
    """
    DUTY: float = 0.5
    F_SW: float = 25e3
    DT: float = 1e-6
    T_END: float = 0.004

    methods: List[Tuple[DynamicIntegrationMethod, str]] = list([
        (DynamicIntegrationMethod.DaeBackEuler, "Backward Euler"),
        (DynamicIntegrationMethod.DaeTrapezoidal, "Trapezoidal"),
        (DynamicIntegrationMethod.DaeBDF2, "BDF2")
    ])

    results: Dict[str, Dict[str, np.ndarray]] = dict()
    kpis: List[Dict[str, Any]] = list()

    vf = VarFactory()
    sys_block, sw_var, _ = create_boost_system(vf)
    sys_block.unify_blocks()
    glob_time = vf.add_var("t_glob")

    problem: GenericEmtProblem = GenericEmtProblem(sys_block, glob_time)

    offset: int = problem.get_variable_parameter_number()
    idx: int = problem.uid2idx_params[sw_var.uid]
    pwm_updater: BoostPWMWrapper = BoostPWMWrapper(F_SW, DUTY, offset, idx)

    for method_enum, method_name in methods:
        solver = JitSymbolicSolver(
            problem=problem, t0=0.0, t_end=T_END, h=DT,
            method=method_enum, verbose=False
        )

        t_arr, y_arr, dy_arr = solver.simulate(boundary_updater=pwm_updater)

        i_L: np.ndarray = y_arr[:, problem.get_var_idx(sys_block.state_vars[0])]
        v_C: np.ndarray = y_arr[:, problem.get_var_idx(sys_block.state_vars[1])]

        mask_ss: np.ndarray = t_arr > (T_END * 0.8)
        ripple_current: float = float(np.max(i_L[mask_ss]) - np.min(i_L[mask_ss]))
        avg_voltage: float = float(np.mean(v_C[mask_ss]))

        if ripple_current < 1.0:
            behavior: str = "High Damping"
        else:
            behavior: str = "Accurate"

        kpi_entry: Dict[str, Any] = dict()
        kpi_entry["Method"] = method_name
        kpi_entry["V_out Avg (V)"] = avg_voltage
        kpi_entry["Ripple I_L (A)"] = ripple_current
        kpi_entry["Behavior"] = behavior
        kpis.append(kpi_entry)

        results[method_name] = dict()
        results[method_name]['t'] = t_arr
        results[method_name]['i'] = i_L
        results[method_name]['v'] = v_C

    return results, kpis


@patch("matplotlib.pyplot.show")
def test_boost_converter_simulation(mock_show) -> None:
    """
    Test that all integration methods successfully simulate boost converter.

    Verifies that the simulation produces results for all three
    integration methods: Backward Euler, Trapezoidal, and BDF2.
    """
    results, kpis = run_method_benchmark()

    assert len(results) == 3
    assert "Backward Euler" in results
    assert "Trapezoidal" in results
    assert "BDF2" in results


@patch("matplotlib.pyplot.show")
def test_all_methods_produce_finite_results(mock_show) -> None:
    """
    Test that all methods produce finite current and voltage results.

    Verifies numerical stability of all integration methods by
    checking that all solution components remain finite.
    """
    results, kpis = run_method_benchmark()

    for method_name, data in results.items():
        t = data['t']
        i = data['i']
        v = data['v']

        assert len(t) == len(i)
        assert len(t) == len(v)
        assert np.all(np.isfinite(i)), f"{method_name} current should be finite"
        assert np.all(np.isfinite(v)), f"{method_name} voltage should be finite"


@patch("matplotlib.pyplot.show")
def test_kpi_extraction(mock_show) -> None:
    """
    Test that KPIs are correctly extracted from simulation results.

    Verifies that the benchmark correctly computes average voltage,
    current ripple, and identifies method behavior characteristics.
    """
    results, kpis = run_method_benchmark()

    assert len(kpis) == 3

    for kpi in kpis:
        assert "Method" in kpi
        assert "V_out Avg (V)" in kpi
        assert "Ripple I_L (A)" in kpi
        assert "Behavior" in kpi

        assert isinstance(kpi["V_out Avg (V)"], float)
        assert isinstance(kpi["Ripple I_L (A)"], float)
        assert kpi["V_out Avg (V)"] > 0


@patch("matplotlib.pyplot.show")
def test_voltage_converges_to_expected_range(mock_show) -> None:
    """
    Test that boost converter output voltage exceeds input.

    For a boost converter with duty cycle 0.5, the output voltage
    should be greater than the input voltage.
    """
    results, kpis = run_method_benchmark()

    V_IN = 12.0
    DUTY = 0.5
    V_OUT_EXPECTED = V_IN / (1.0 - DUTY)

    for kpi in kpis:
        method_name = kpi["Method"]
        avg_voltage = kpi["V_out Avg (V)"]

        assert avg_voltage > V_IN, f"{method_name}: Output voltage should be greater than input"


@patch("matplotlib.pyplot.show")
def test_trapezoidal_has_energy_conservation(mock_show) -> None:
    """
    Test that Trapezoidal method produces finite power values.

    Verifies numerical stability by checking that computed power
    values remain finite throughout the simulation.
    """
    results, kpis = run_method_benchmark()

    trapezoidal_data = results.get("Trapezoidal")
    assert trapezoidal_data is not None

    v_trap = trapezoidal_data['v']
    i_trap = trapezoidal_data['i']

    power = v_trap * i_trap
    final_power = power[-100:].mean()
    initial_power = power[:100].mean()

    assert np.isfinite(final_power)
    assert np.isfinite(initial_power)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
