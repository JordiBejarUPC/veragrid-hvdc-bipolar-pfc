import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_8f9c8c0a(states, params, history, d_history, h, indices, history2=None):
    # Vectorized O(1) Kernel
    residuals = ((2.0/h) * (states[indices['v_199']] - history[indices['v_199']]) - d_history[indices['v_199']]) - 5000.0 * (states[indices['x_198']] - states[indices['x_199']]) + 5000.0 * (0.0 - states[indices['x_199']]) - 0.5 * states[indices['v_199']]
    return residuals