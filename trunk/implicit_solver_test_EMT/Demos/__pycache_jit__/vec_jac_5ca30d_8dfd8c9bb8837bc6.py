import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_jac_5ca30d(states, params, history, d_history, h, indices, history2=None):
    n_items = len(indices['__TARGET__'])
    n_derivs = 4
    results = np.empty((n_items, n_derivs), dtype=np.float64)
    results[:, 0] = 0.5 + params[2]
    results[:, 1] = 10000.0
    results[:, 2] = -5000.0
    results[:, 3] = 0.5 + params[2]
    return results