# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys, os
import numpy as np
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
from matplotlib import pyplot as plt

from VeraGridEngine.Utils.Symbolic.symbolic_compare_expressions import equivalent, equivalent_systems
from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Simulations.Rms.problems.rms_problem_dae import RmsProblemDae
from VeraGridEngine.Simulations.Rms.rms_options import RmsOptions
from VeraGridEngine.Simulations.Rms.numerical.back_euler_fx import BackEulerImplicitIntegration
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Utils.Symbolic.bus_rms_template import initialize_bus_rms
from VeraGridEngine.Utils.Symbolic.templates_common_functions import set_rms_model
from VeraGridEngine.Devices.Events.rms_events_group import RmsEventsGroup

from VeraGridEngine.enumerations import DynamicIntegrationMethod, RmsInitializationMethod
from VeraGridEngine.Devices.Events.rms_event import RmsEvent
import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################




grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# generator

gen1_rms_model = get_complete_generator_template_rms(grid.var_factory).block
gen1_rms_model.unify_blocks()

gen2_rms_model = get_complete_generator_template_rms(grid.var_factory).block
gen2_rms_model.unify_blocks()

# eq_added = grid.var_factory.add_var("V1") + grid.var_factory.add_var("V2")

# gen2_rms_model.algebraic_eqs.append(eq_added)

equal = equivalent_systems(gen1_rms_model.algebraic_eqs, gen2_rms_model.algebraic_eqs)

print(equal)