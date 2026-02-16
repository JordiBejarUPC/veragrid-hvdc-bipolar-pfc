import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def jit_step_trapezoidal_part_0(states, params, history, d_history, h, residuals, history2=None):
    residuals[0] = ((2.0/h) * (states[0] - history[0]) - d_history[0]) - (params[2] - (1.0 - params[3]) * states[1]) / params[5]
    residuals[1] = ((2.0/h) * (states[1] - history[1]) - d_history[1]) - ((1.0 - params[3]) * states[0] - states[1] / params[4]) / params[6]