import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_kernel_6b9f4599(states, params, history, d_history, h, indices, history2=None):
    # Vectorized O(1) Kernel
    residuals = ((2.0/h) * (states[indices['i_L']] - history[indices['i_L']]) - d_history[indices['i_L']]) - (params[0] - states[indices['v_C']]) / params[2]
    return residuals