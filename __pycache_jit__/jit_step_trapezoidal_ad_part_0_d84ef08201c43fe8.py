import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def jit_step_trapezoidal_ad_part_0(states, params, history, d_history, h, residuals, history2=None):
    residuals[0] = ((2.0/h) * (states[0] - history[0]) - d_history[0]) - states[0] * states[0]