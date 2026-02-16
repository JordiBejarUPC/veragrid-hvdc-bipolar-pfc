import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_8f9c8c0a(states, params, history, d_history, h, indices, history2=None):
    # Vectorized O(1) Kernel
    residuals = ((2.0/h) * (states[indices['v_499']] - history[indices['v_499']]) - d_history[indices['v_499']]) - 5000.0 * (states[indices['x_498']] - states[indices['x_499']]) + 5000.0 * (0.0 - states[indices['x_499']]) - 0.5 * states[indices['v_499']]
    return residuals