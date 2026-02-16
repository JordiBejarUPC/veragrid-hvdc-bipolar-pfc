import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_8f9c8c0a(states, params, history, d_history, h, indices, history2=None):
    # Vectorized Matrix Kernel (No Dicts)
    residuals = ((2.0/h) * (states[indices[:, 3]] - history[indices[:, 3]]) - d_history[indices[:, 3]]) - 5000.0 * (states[indices[:, 1]] - states[indices[:, 2]]) + 5000.0 * (0.0 - states[indices[:, 2]]) - 0.5 * states[indices[:, 3]]
    return residuals