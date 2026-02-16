import numpy as np
import math
from VeraGridEngine.Utils.Symbolic.symbolic import _heaviside

def vec_jac_6b9f45(states, params, history, d_history, h, indices, history2=None):
    n_items = len(indices['__TARGET__'])
    n_derivs = 2
    results = np.empty((n_items, n_derivs), dtype=np.float64)
    results[:, 0] = params[6]
    results[:, 1] = -(-1 / params[4])
    return results