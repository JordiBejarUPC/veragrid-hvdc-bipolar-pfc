import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_5ca30db4(states, params, history, d_history, h, indices, history2=None):
    # Vectorized O(1) Kernel
    residuals = ((2.0/h) * (states[indices['v_0']] - history[indices['v_0']]) - d_history[indices['v_0']]) - 5000.0 * (0.0 - states[indices['x_0']]) + 5000.0 * (states[indices['x_1']] - states[indices['x_0']]) - 0.5 * states[indices['v_0']]
    return residuals