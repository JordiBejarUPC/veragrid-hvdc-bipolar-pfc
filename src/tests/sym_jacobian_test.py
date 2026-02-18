# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

import numpy as np
import pytest
import random

from VeraGridEngine.Utils.Symbolic.symbolic import Var, sin
from VeraGridEngine.Utils.Symbolic.compiled_functions import SymbolicJacobian


def finite_difference_jacobian(func, x, eps=1e-8):
    n = len(x)
    f0 = func(x)
    m = len(f0)
    J = np.zeros((m, n))

    for i in range(n):
        x_eps = x.copy()
        x_eps[i] += eps
        f1 = func(x_eps)
        J[:, i] = (f1 - f0) / eps

    return J


def build_random_system(n_vars, n_eqs):
    vars_ = [Var(f"x{i}") for i in range(n_vars)]

    eqs = []
    for _ in range(n_eqs):
        expr = 0
        for v in vars_:
            coef = random.uniform(-2, 2)
            expr += coef * v**2

        # añadir algo no lineal
        v_rand = random.choice(vars_)
        expr += sin(v_rand)

        eqs.append(expr)

    return vars_, eqs


@pytest.mark.parametrize("use_jit", [False, True])
def test_symbolic_jacobian_stress(use_jit):

    random.seed(0)
    np.random.seed(0)

    for _ in range(5):  # repetir varios sistemas

        n_vars = random.randint(2, 5)
        n_eqs = random.randint(2, 5)

        variables, eqs = build_random_system(n_vars, n_eqs)

        compiler_names_dict = {
            v.uid: f"x[{i}]"
            for i, v in enumerate(variables)
        }

        alias_names_dict = {}

        jac = SymbolicJacobian(
            eqs=eqs,
            variables=variables,
            compiler_names_dict=compiler_names_dict,
            alias_names_dict=alias_names_dict,
            VARS_NAME="x",
            DIFF_NAME="dx",
            EVENT_PARAMS_NAME="vp",
            PARAMS_NAME="cp",
            use_jit=use_jit,
            batch_size=3,
            n_jobs=2
        )

        def f_numeric(vals):
            # evaluar usando numpy manualmente
            result = []
            for eq in eqs:
                # asumir que tienes método eval
                result.append(eq.eval(vals))
            return np.array(result)

        xval = np.random.randn(n_vars)
        dx = np.zeros_like(xval)
        vp = np.zeros(0)
        cp = np.zeros(0)

        J_compiled = jac(xval, dx, vp, cp, h=1e-8).toarray()
        J_fd = finite_difference_jacobian(f_numeric, xval)

        assert np.allclose(J_compiled, J_fd, atol=1e-6)