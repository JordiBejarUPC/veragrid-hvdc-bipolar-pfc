import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_40fcf13e(states, params, history, d_history, h, indices, history2=None):
    # Vectorized O(1) Kernel
    residuals = ((2.0/h) * (states[indices['v_C']] - history[indices['v_C']]) - d_history[indices['v_C']]) - (states[indices['i_L']] - states[indices['v_C']] / params[3]) / params[5]
    return residuals