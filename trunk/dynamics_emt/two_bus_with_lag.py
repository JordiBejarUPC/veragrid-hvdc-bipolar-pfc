# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import sys, os, inspect
# file_directory = os.path.dirname(os.path.abspath(__file__))
# up_two_directories = os.path.join(file_directory, '..', '..')
# up_two_directories = os.path.abspath(up_two_directories)
# sys.path.insert(0,up_two_directories)
# print(up_two_directories)
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
import math
import numpy as np
from matplotlib import pyplot as plt

# from VeraGridEngine.Utils.Symbolic.events import Events, Event
from VeraGridEngine.Devices.Dynamic.events import RmsEvents, RmsEvent
from VeraGridEngine.Utils.Symbolic.symbolic import Const, Var, cos, sin
from VeraGridEngine.Utils.Symbolic.block import Block
# from VeraGridEngine.Utils.MultiLinear.multilinearize import *
from VeraGridEngine.Utils.MultiLinear.differential_var  import DiffVar, LagVar
from VeraGridEngine.Utils.MultiLinear.diff_blocksolver  import DiffBlock, DiffBlockSolver
from VeraGridEngine.Utils.Symbolic.block_solver_no_diff import BlockSolver
import VeraGridEngine.api as gce
#parameter
Zc = Const(0.1)
L_ = 1e-6      # H/m
C_ = 1e-11     # F/m
length = 100e3 #m
Rsource = 3  # source impedance (ohm)
Vpeak = 230e3 * np.sqrt(2)
f = 50
omega = 2 * np.pi * f
nbus = 2

# ---- Derived line quantities ----
Zc = np.sqrt(L_ / C_)
v_wave = 1 / np.sqrt(L_ * C_)
tau = length / v_wave

#Sim setup
dt = tau / 50   # 50 points per delay
n_steps = int(10 / f / dt)  # ~10 cycles
t = np.arange(n_steps) * dt

# ---- Source voltage ----
vs = np.where(t >= 0, Vpeak * np.sin(omega * t), 0.0)  # switch closes at t=0

# ---- initialize MNA ----
# these change for each time step
G = np.zeros((nbus, nbus))

# add Bergeron's line params: initialize with open circuit
G[0,0] += 1 / Zc
G[1,1] += 1 / Zc

Rload = 1e-20 # short-circuit

# add voltage source to ground
G[0,0] += 1 / Rsource
#add load to ground
G[1,1] +=  1 / Rload

#variables
v1 = Var('v1')
v2 = Var('v2')
i1 = Var('i1')
i2 = Var('i2')
i_hist_1 = Var('i_hist_1')
i_hist_2 = Var('i_hist_2')

#lags
lag = int(round(tau / dt))
v1_delay = LagVar(name='v1_delay', base_var=v1, lag=lag)
v2_delay = LagVar(name='v2_delay', base_var=v2, lag=lag)
i1_delay = LagVar(name='i1_delay', base_var=i1, lag=lag)
i2_delay = LagVar(name='i2_delay', base_var=i2, lag=lag)

block = DiffBlock(
    algebraic_eqs=[
        v1/Zc - (Vpeak*cos(omega * t) / Rsource - i_hist_1),
        v2/Zc - (-i_hist_2),
    ],
    algebraic_vars=[v1, v2],
    history_eqs = [
        i_hist_1 - (-v2_delay/Zc -i2_delay),
        i_hist_2 - (-v1_delay/Zc -i1_delay),
    ],
    history_vars = [i_hist_1, i_hist_2]
)