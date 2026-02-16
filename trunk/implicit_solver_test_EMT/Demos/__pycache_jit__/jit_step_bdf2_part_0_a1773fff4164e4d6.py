import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def jit_step_bdf2_part_0(states, params, history, d_history, h, residuals, history2=None):
    residuals[0] = ((1.5*states[0] - 2.0*history[0] + 0.5*history2[0]) / h) - (params[2] - (1.0 - params[3]) * states[1]) / params[5]
    residuals[1] = ((1.5*states[1] - 2.0*history[1] + 0.5*history2[1]) / h) - ((1.0 - params[3]) * states[0] - states[1] / params[4]) / params[6]