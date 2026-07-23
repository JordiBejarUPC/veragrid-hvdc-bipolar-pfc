import os
import numpy as np
import numba as nb
import VeraGridEngine as vg

"""
This test tries the following:
The bus computed power is Sbus = V · conj(Ybus x V)
But what if we could compute that power without computing Ybus?

If we simply consider S as the summation of powers that enter and exit the bus we can do it,
and since the branches power computation only depend on the branch primitive vectors we can avoid using Ybus, Yf and Yt
Hence, we can compute the branch powers and compose Sbus by summation
The apparent advantage of this is that we can use vectorization and avoid the sparse matrices altogether
"""




@nb.njit(cache=True)
def alternative_S_Sf_St(V, yff, yft, ytf, ytt, F, T, Sbase, shunt_bus_idx, Y_shunt):
    """
    Alternative manner of computing Sbus, Sf, St without any sparse matrix
    :param V:
    :param yff:
    :param yft:
    :param ytf:
    :param ytt:
    :param F:
    :param T:
    :param Sbase:
    :param shunt_bus_idx:
    :param Y_shunt:
    :return:
    """

    nbus = len(V)
    nbr = len(F)
    S = np.zeros(nbus, dtype=nb.complex128)
    Sf = np.zeros(nbr, dtype=nb.complex128)
    St = np.zeros(nbr, dtype=nb.complex128)

    for k in range(nbr):
        # element-wise computation
        f = F[k]
        t = T[k]
        Vf_k = V[f]
        Vt_k = V[t]
        Sf_k = (Vf_k * np.conj(Vf_k * yff[k]) + Vf_k * np.conj(Vt_k * yft[k])) * Sbase
        St_k = (Vt_k * np.conj(Vt_k * ytt[k]) + Vt_k * np.conj(Vf_k * ytf[k])) * Sbase

        # both are + because Sf and St already have the correct sign
        S[f] += Sf_k
        S[t] += St_k
        Sf[k] = Sf_k
        St[k] = St_k

    # add the shunts
    nshunt = len(shunt_bus_idx)
    for k in range(nshunt):
        i = shunt_bus_idx[k]
        S[i] += 2 * V[i] * np.conj(Y_shunt[k] * V[i])  # Y is already in MW+jMVAr

    return Sf, St, S


@nb.njit(cache=True)
def alternative_S_Sf_St_vectorized(V, yff, yft, ytf, ytt, F, T, Sbase, shunt_bus_idx, Y_shunt):
    """
    Alternative manner of computing Sbus, Sf, St without any sparse matrix using vectorization
    :param V:
    :param yff:
    :param yft:
    :param ytf:
    :param ytt:
    :param F:
    :param T:
    :param Sbase:
    :param shunt_bus_idx:
    :param Y_shunt:
    :return:
    """
    Vf = V[F]
    Vt = V[T]
    Sf = (Vf * np.conj(Vf * yff) + Vf * np.conj(Vt * yft)) * Sbase
    St = (Vt * np.conj(Vt * ytt) + Vt * np.conj(Vf * ytf)) * Sbase

    nbus = len(V)
    S = np.zeros(nbus, dtype=nb.complex128)

    # We cannot avoid this loop, otherwise we would have to say
    # S += Cf x Sf + Ct x St which is exactly the same but wit sparse matrices, which is what we try to avoid
    nbr = len(F)
    for k in range(nbr):
        # both are + because Sf and St already have the correct sign
        S[F[k]] += Sf[k]
        S[T[k]] += St[k]

    # add the shunts
    Vsh = V[shunt_bus_idx]
    S[shunt_bus_idx] += 2 * Vsh * np.conj(Y_shunt * Vsh)  # Y is already in MW+jMVAr

    return Sf, St, S


def base(grid: vg.MultiCircuit):
    """
    We simply run a power flow to verify later that with non-trivial values the results are the same
    :param grid:
    :return:
    """
    pf_res = vg.power_flow(grid)

    nc = vg.compile_numerical_circuit_at(grid)
    adm = nc.get_admittance_matrices()

    return pf_res, nc, adm


def main(fname):
    """

    :return:
    """
    grid = vg.open_file(fname)

    pf_res, nc, adm = base(grid)

    # Alternative
    Sf_alt, St_alt, S_alt = alternative_S_Sf_St(
        V=pf_res.voltage,
        yff=adm.yff,
        yft=adm.yft,
        ytf=adm.ytf,
        ytt=adm.ytt,
        F=nc.passive_branch_data.F,
        T=nc.passive_branch_data.T,
        Sbase=nc.Sbase,
        shunt_bus_idx=nc.shunt_data.bus_idx,
        Y_shunt=nc.shunt_data.Y
    )

    # Comparison
    print("Sf diff: ", pf_res.Sf - Sf_alt)
    print("St diff: ", pf_res.St - St_alt)
    print("Sbus diff: ", pf_res.Sbus - S_alt)
    print()


if __name__ == "__main__":
    # fname = os.path.join("..", "..", "..", "Grids_and_profiles", "grids", "Lynn 5 Bus (pq).gridcal")
    fname = os.path.join("case14.matpower")
    main(fname)
