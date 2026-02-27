# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math

import numpy as np
from matplotlib import pyplot as plt

import sys
import os

from VeraGridEngine.Devices.multi_circuit import MultiCircuit
from VeraGridEngine.Devices.Substation.bus import Bus
from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Branches.line import Line
from VeraGridEngine.Simulations.PowerFlow.power_flow_driver import PowerFlowResults, PowerFlowOptions

from VeraGridEngine import VarPowerFlowRefferenceType, power_flow
from VeraGridEngine.Utils.Symbolic.block_solver import BlockSolver

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin, piecewise
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.block_solver_no_diff import BlockSolverNoDiff
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_genqec, get_governor, get_exciter, get_stabilizer
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
import VeraGridEngine.api as gce
from VeraGridEngine.enumerations import DynamicIntegrationMethod

def test_diff_block_in_harmonic_oscillator():
    x = Var('x')
    y_var = Var('y')
    dt = Const(0.001)

    dx = Var('dx', base_var=x)
    dy = Var('dy', base_var=y_var)
    d2x = Var('d2x', base_var=dx)
    d3x = Var('d3x', base_var=d2x)

    # build system: dx + y = 0, dy - x = 0
    diff_block = Block(
        algebraic_eqs=[
            dx + y_var,
            dy - x,
        ],
        algebraic_vars=[x, y_var],
        diff_vars=[dx, dy, d2x],
    )

    t = Var('t')
    slv = BlockSolver(diff_block, t)

    vars_mapping = {x: 1.0, y_var: 0.0}   # initial condition x(0)=1, y(0)=0
    div_vars_mapping = {dx: 0.0, dy: 1.0}
    params_mapping = {slv.dt: 0.001}

    x0 = np.array([1.0, 0.0])
    dx0 = slv.build_init_diffvars_vector(div_vars_mapping)
    params0 = np.array([0.001, 0.0])

    t, y,_ = slv.simulate(
        t0=0,
        t_end=2*np.pi,
        h=0.001,
        x0=x0,
        dx0=dx0,
        params0=params0,
        method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=False
    )

    x_sim = y[:, slv.get_var_idx(x)]
    y_sim = y[:, slv.get_var_idx(y_var)]

    # compare against analytical solution
    x_ref = np.cos(t)
    y_ref = np.sin(t)
    
    plt.figure()
    plt.plot(t, x_sim, label="x")
    plt.plot(t, x_ref, label="x")
    plt.plot(t, y_sim, label="y")
    plt.plot(t, y_ref, label="y")
    plt.xlabel("t")
    plt.legend()
    plt.grid(True)
    plt.show()

    assert np.allclose(x_sim, x_ref, atol=1e-2)
    assert np.allclose(y_sim, y_ref, atol=1e-2)

def test_diff_block_second_order_oscillator():
    x = Var('x')
    dt = Const(0.001)

    dx = Var('dx', base_var=x)
    d2x = Var('d2x', base_var=dx)

    # build system: d2x + dx + x = 0
    diff_block = Block(
        algebraic_eqs=[
            d2x + dx + x,
        ],
        algebraic_vars=[x],
        diff_vars=[dx, d2x],
    )

    t = Var('t')
    slv = BlockSolver(diff_block, t)

    # initial conditions:
    # x(0) = 1
    # dx(0) = 0
    vars_mapping = {x: 1.0}
    diff_vars_mapping = {dx: 0.0, d2x: -1.0}  # from d2x = -dx - x

    x0 = np.array([1.0])
    dx0 = slv.build_init_diffvars_vector(diff_vars_mapping)
    params0 = np.array([0.001])

    t, y, _ = slv.simulate(
        t0=0.0,
        t_end=10.0,
        h=0.001,
        x0=x0,
        dx0=dx0,
        params0=params0,
        method=DynamicIntegrationMethod.DaeBackEuler,
        verbose=False
    )

    x_sim = y[:, slv.get_var_idx(x)]

    # analytical solution of x'' + x' + x = 0
    # overdamped/underdamped depending on coefficients;
    # here: lambda = (-1 ± sqrt(1 - 4)) / 2 = complex
    omega = np.sqrt(3) / 2
    x_ref = np.exp(-0.5 * t) * np.cos(omega * t)

    plt.figure()
    plt.plot(t, x_sim, label="x (sim)")
    plt.plot(t, x_ref, "--", label="x (ref)")
    plt.xlabel("t")
    plt.legend()
    plt.grid(True)
    plt.show()

    assert np.allclose(x_sim, x_ref, atol=1e-2)


if __name__ == "__main__":
    #test_diff_block_in_harmonic_oscillator()
    test_diff_block_second_order_oscillator()
    print("All tests passed.")