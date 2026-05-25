# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import sys, os
import numpy as np


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'src')))
from matplotlib import pyplot as plt

from VeraGridEngine.Utils.Symbolic.block import compare_blocks_structurally

from VeraGridEngine.Templates.Rms.genrow_rms_template import get_genrow_rms_template
from VeraGridEngine.Templates.Rms.pvd1_rms_template import get_pvd1_complete_rms_template, get_pvd1_dc_mppt_rms_template
from VeraGridEngine.Templates.Rms.line_rms_template import get_line_rms_template
from VeraGridEngine.Templates.Rms.load_rms_template import get_load_rms_template
from VeraGridEngine.Templates.Rms.genqec_exc_gov_sat_template import get_complete_generator_template_rms
from VeraGridEngine.Utils.Symbolic.block import compare_n_blocks_structurally

import VeraGridEngine.api as gce

###########################################################################################################################
# Build VeraGrid object
###########################################################################################################################




grid = gce.MultiCircuit(Sbase=100, fbase=50.0)

# generator

gen1_rms_model = get_pvd1_dc_mppt_rms_template(grid.var_factory).block
gen1_rms_model.unify_blocks()

gen2_rms_model = get_pvd1_dc_mppt_rms_template(grid.var_factory).block
gen2_rms_model.unify_blocks()

equivalence_classes = compare_n_blocks_structurally([gen1_rms_model, gen2_rms_model])
print(equivalence_classes)




