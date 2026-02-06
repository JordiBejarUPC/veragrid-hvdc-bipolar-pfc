import time
import numpy as np
import scipy.linalg
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def compute_participation_factors(An, Am, v, w, n_eigenvalues, num_states):
    """
    :param An: number of rows(states) in the state matrix
    :param Am: number of columns(modes) in the state matrix
    :param v: right eigenvectors
    :param w: left eigenvectors
    :param n_eigenvalues: number of eigenvalues
    :param num_states: number of states
    :return: participation factors
    """
    participation_factors = np.zeros((An, Am))
    for row in range(w.shape[0]):
        for column in range(w.shape[0]):
            participation_factors[row, column] = abs(w[row, column]) * abs(v[row, column])

    # normalize participation factors
    pfact_abs = np.ones(num_states) @ participation_factors
    for i in range(n_eigenvalues):
        participation_factors[:, i] /= pfact_abs[i]

    return participation_factors


def calculate_dense_eigs_PF(A_dense):
    # -----------------------------
    # Eigenvalues + eigenvectors
    # -----------------------------
    t0 = time.perf_counter()

    print("Calculating dense eigenvalues...")
    eigenvalues_dense, w_dense, v_dense = scipy.linalg.eig(
        A_dense,
        left=True,
        right=True
    )

    t_eig_dense = time.perf_counter() - t0

    # -----------------------------
    # Participation factors
    # -----------------------------
    t1 = time.perf_counter()

    print("Calculating dense participation factors...")
    PF_dense = compute_participation_factors(
        An=A_dense.shape[0],
        Am=A_dense.shape[1],
        v=v_dense,
        w=w_dense,
        n_eigenvalues=len(eigenvalues_dense),
        num_states=A_dense.shape[0]
    )

    t_pf_dense = time.perf_counter() - t1

    # -----------------------------
    # Total
    # -----------------------------
    t_dense = t_eig_dense + t_pf_dense

    return eigenvalues_dense, t_dense, t_eig_dense, t_pf_dense


def calculate_sparse_eigs_PF(A_sparse, k):
    """
    Reduced small-signal stability analysis using projection.
    """

    # -----------------------------
    # STEP 1: Sparse dominant eigs
    # -----------------------------
    t0 = time.perf_counter()

    print("Calculating sparse dominant right eigenpairs (Arnoldi)...")
    eigvals_r, V = spla.eigs(
        A_sparse,
        k=k,
        sigma=0.0,     # shift-invert → critical modes
        which="LM"
    )

    t_eig_sparse = time.perf_counter() - t0

    # -----------------------------
    # STEP 2–6: Reduced PF
    # -----------------------------
    t1 = time.perf_counter()

    print("Building reduced projected matrix...")
    A_r = V.conj().T @ (A_sparse @ V)

    print("Computing reduced dense eigen-decomposition...")
    eigvals_red, W_r, V_r = scipy.linalg.eig(
        A_r,
        left=True,
        right=True
    )

    print("Lifting left eigenvectors...")
    W = V @ W_r

    print("Bi-orthonormalising...")
    for i in range(k):
        norm_factor = W[:, i].conj().T @ V[:, i]
        if np.abs(norm_factor) < 1e-12:
            raise RuntimeError("Bi-orthogonality lost in reduced projection")
        W[:, i] /= norm_factor

    print("Computing reduced participation factors...")
    PF = np.abs(V * W)
    PF_norm = PF / PF.sum(axis=0, keepdims=True)
    # PF_sparse = compute_participation_factors(An=A_r.shape[0],
    #                                           Am=A_r.shape[1],
    #                                           v=V,
    #                                           w=W,
    #                                           n_eigenvalues=len(eigvals_red),
    #                                           num_states=num_states)

    t_pf_sparse = time.perf_counter() - t1

    # -----------------------------
    # Total
    # -----------------------------
    t_sparse = t_eig_sparse + t_pf_sparse

    print(f"Reduced sparse PF calculation time: {t_sparse:.3f} s")

    return eigvals_r, t_sparse, t_eig_sparse, t_pf_sparse


def compare_sparse_vs_dense_time(
    n_states_min,
    n_states_max,
    n_points,
    density,
    k_per,
    seed=1
):
    n_states_arr = np.linspace(
        n_states_min,
        n_states_max,
        n_points,
        dtype=int
    )

    t_dense_arr = []
    t_sparse_arr = []

    t_eig_dense_arr = []
    t_pf_dense_arr = []

    t_eig_sparse_arr = []
    t_pf_sparse_arr = []

    for n_states in n_states_arr:
        print("\n" + "=" * 60)
        print(f"Running benchmark for n_states = {n_states}")
        print("=" * 60)

        np.random.seed(seed)

        # Same matrix for dense & sparse
        A_sparse = sp.random(
            n_states,
            n_states,
            density=density,
            format="csr",
            data_rvs=np.random.randn
        )

        A_dense = A_sparse.toarray()

        # Reduced order: almost full, as you were doing
        k = int(k_per*n_states)

        try:
            _, t_dense, t_eig_dense, t_pf_dense = calculate_dense_eigs_PF(A_dense)

        except Exception as e:
            print(f"FAILED dense calculation for n_states={n_states}: {e}")
            t_dense =  np.nan
            t_eig_dense = np.nan
            t_pf_dense = np.nan

        try:
            _, t_sparse, t_eig_sparse, t_pf_sparse = calculate_sparse_eigs_PF(A_sparse, k)

        except Exception as e:
            print(f"FAILED sparse calculation for n_states={n_states}: {e}")
            t_sparse = np.nan
            t_eig_sparse = np.nan
            t_pf_sparse = np.nan

        t_dense_arr.append(t_dense)
        t_sparse_arr.append(t_sparse)

        t_eig_dense_arr.append(t_eig_dense)
        t_pf_dense_arr.append(t_pf_dense)

        t_eig_sparse_arr.append(t_eig_sparse)
        t_pf_sparse_arr.append(t_pf_sparse)

    return (
        n_states_arr,
        np.array(t_dense_arr),
        np.array(t_sparse_arr),
        np.array(t_eig_dense_arr),
        np.array(t_pf_dense_arr),
        np.array(t_eig_sparse_arr),
        np.array(t_pf_sparse_arr),
    )

def print_comparison_report(
    n_states_arr,
    t_dense_arr,
    t_sparse_arr,
    t_eig_dense_arr,
    t_pf_dense_arr,
    t_eig_sparse_arr,
    t_pf_sparse_arr,
    density,
    k_per
):
    print("\n" + "=" * 130)
    print("DENSE vs SPARSE SMALL-SIGNAL STABILITY — PERFORMANCE COMPARISON")
    print(f"Matrix density          : {density:.3f}")
    print(f"Reduced eig percentage  : k_per = {k_per:.2f}  (k = ⌊k_per · n_states⌋)")
    print("=" * 130)

    header = (
        f"{'States':>7} | "
        f"{'Dense eig [s]':>12} {'Dense PF [s]':>12} {'Dense tot [s]':>12} | "
        f"{'Sparse eig [s]':>13} {'Sparse PF [s]':>13} {'Sparse tot [s]':>13} | "
        f"{'Speed-up':>9}"
    )
    print(header)
    print("-" * 130)

    for i in range(len(n_states_arr)):
        n = n_states_arr[i]

        td = t_dense_arr[i]
        ts = t_sparse_arr[i]

        td_eig = t_eig_dense_arr[i]
        td_pf  = t_pf_dense_arr[i]

        ts_eig = t_eig_sparse_arr[i]
        ts_pf  = t_pf_sparse_arr[i]

        if any(np.isnan(v) for v in [td, ts, td_eig, td_pf, ts_eig, ts_pf]):
            print(
                f"{n:7d} | "
                f"{'FAILED':>12} {'FAILED':>12} {'FAILED':>12} | "
                f"{'FAILED':>13} {'FAILED':>13} {'FAILED':>13} | "
                f"{'-':>9}"
            )
        else:
            speedup = td / ts if ts > 0 else np.inf

            print(
                f"{n:7d} | "
                f"{td_eig:12.4e} {td_pf:12.4e} {td:12.4e} | "
                f"{ts_eig:13.4e} {ts_pf:13.4e} {ts:13.4e} | "
                f"{speedup:9.2f}"
            )

    print("-" * 130)

    valid = (~np.isnan(t_dense_arr)) & (~np.isnan(t_sparse_arr))
    if np.any(valid):
        avg_speedup = np.mean(t_dense_arr[valid] / t_sparse_arr[valid])
        max_speedup = np.max(t_dense_arr[valid] / t_sparse_arr[valid])

        print(f"Average speed-up : {avg_speedup:.2f} x")
        print(f"Maximum speed-up : {max_speedup:.2f} x")

    print("=" * 130 + "\n")



    # PARAMETERS
n_states_min = 10
n_states_max = 200
n_points = 19
density = 0.4
k_per = 0.01

(
    n_states_arr,
    t_dense_arr,
    t_sparse_arr,
    t_eig_dense_arr,
    t_pf_dense_arr,
    t_eig_sparse_arr,
    t_pf_sparse_arr
) = compare_sparse_vs_dense_time(
    n_states_min=n_states_min,
    n_states_max=n_states_max,
    n_points=n_points,
    density=density,
    k_per = k_per
)

print_comparison_report(
    n_states_arr,
    t_dense_arr,
    t_sparse_arr,
    t_eig_dense_arr,
    t_pf_dense_arr,
    t_eig_sparse_arr,
    t_pf_sparse_arr,
    density=density,
    k_per = k_per
)


