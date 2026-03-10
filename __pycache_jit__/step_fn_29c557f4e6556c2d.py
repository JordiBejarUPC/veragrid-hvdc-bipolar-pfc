import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def step_fn(states, params, history, d_history, h, history2=None):
    residuals = np.zeros(1, dtype=np.float64)
    residuals[0] = ((states[0] - history[0]) / h) + states[0]
    return residuals