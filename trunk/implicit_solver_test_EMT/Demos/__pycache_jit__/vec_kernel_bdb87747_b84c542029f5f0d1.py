import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_bdb87747(states, params, history, d_history, h, indices, history2=None):
    # Vectorized O(1) Kernel
    residuals = ((2.0/h) * (states[indices['v_1']] - history[indices['v_1']]) - d_history[indices['v_1']]) - 5000.0 * (states[indices['x_0']] - states[indices['x_1']]) + 5000.0 * (states[indices['x_2']] - states[indices['x_1']]) - 0.5 * states[indices['v_1']]
    return residuals