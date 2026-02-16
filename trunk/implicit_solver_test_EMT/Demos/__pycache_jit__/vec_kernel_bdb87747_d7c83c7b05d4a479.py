import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_bdb87747(states, params, history, d_history, h, indices, history2=None):
    # Vectorized Matrix Kernel (No Dicts)
    residuals = ((2.0/h) * (states[indices[:, 4]] - history[indices[:, 4]]) - d_history[indices[:, 4]]) - 5000.0 * (states[indices[:, 1]] - states[indices[:, 2]]) + 5000.0 * (states[indices[:, 3]] - states[indices[:, 2]]) - 0.5 * states[indices[:, 4]]
    return residuals