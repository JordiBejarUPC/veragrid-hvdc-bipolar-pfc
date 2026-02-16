import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_5dbf786a(states, params, history, d_history, h, indices, history2=None):
    # Vectorized Matrix Kernel (No Dicts)
    residuals = ((2.0/h) * (states[indices[:, 0]] - history[indices[:, 0]]) - d_history[indices[:, 0]]) - states[indices[:, 1]]
    return residuals