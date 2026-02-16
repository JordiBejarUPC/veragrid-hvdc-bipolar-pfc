import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def jac_eval_trapezoidal_dense(states, params, history, d_history, h, history2=None):
    residuals = np.zeros(4, dtype=np.float64)
    residuals[0] = params[6]
    residuals[1] = -(-1 / params[4])
    residuals[2] = -(1 / params[5])
    residuals[3] = -(-(1 / params[3]) / params[5]) + params[6]
    return residuals