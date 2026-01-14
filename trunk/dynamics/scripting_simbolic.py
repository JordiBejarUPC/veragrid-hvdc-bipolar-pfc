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
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import GenqecBuild, GovernorBuild, ExciterBuild, StabilizerBuild
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Simulations.Rms.initialization import initialize_rms
import VeraGridEngine.api as gce

a = Var('a')
b = Var('b')
mult = a*b
mult = mult.subs({a:b*2})
print(type(mult))