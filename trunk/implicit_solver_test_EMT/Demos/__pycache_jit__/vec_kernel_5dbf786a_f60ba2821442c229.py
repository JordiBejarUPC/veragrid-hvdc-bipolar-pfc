import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_5dbf786a(states, params, history, d_history, h, indices, history2=None):
    # Vectorized O(1) Kernel
    residuals = ((2.0/h) * (states[indices['x_0']] - history[indices['x_0']]) - d_history[indices['x_0']]) - states[indices['v_0']]
    return residuals