import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def step_fn(states, params, history, d_history, h, history2=None):
    residuals = np.zeros(2, dtype=np.float64)
    residuals[0] = ((2.0/h) * (states[0] - history[0]) - d_history[0]) - states[1]
    residuals[1] = ((2.0/h) * (states[1] - history[1]) - d_history[1]) + states[0]
    return residuals