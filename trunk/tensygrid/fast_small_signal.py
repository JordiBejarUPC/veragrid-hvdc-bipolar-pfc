import numpy as np
import scipy.sparse as sparse
from scipy import linalg
from scipy.sparse.linalg import eigs

# 1. Instantly load the compiled sparse matrices
A_csr = sparse.load_npz("ieee118_grid_A.npz")
E_csr = sparse.load_npz("ieee118_grid_E.npz")

print(f"Loaded Grid State-Space with {A_csr.shape[0]} dimensions.")

# 2. Singular Pencil Patching (The exact same logic as before)
A_patched = A_csr.tolil()
n_dims = A_csr.shape[0]

for i in range(n_dims):
    a_data = A_csr.data[A_csr.indptr[i]:A_csr.indptr[i + 1]]
    e_data = E_csr.data[E_csr.indptr[i]:E_csr.indptr[i + 1]]
    a_max = np.max(np.abs(a_data)) if len(a_data) > 0 else 0.0
    e_max = np.max(np.abs(e_data)) if len(e_data) > 0 else 0.0
    if a_max < 1e-10 and e_max < 1e-10:
        A_patched[i, i] = -1.0

# 3. Solve (e.g., trying to find the 200 most unstable poles with ARPACK)
k_modes = 1000
shift_val = 1e-4
ncv_val = min(n_dims, max(2 * k_modes + 1, 500))

print(f"Solving for {k_modes} eigenvalues...")
evals, evecs = eigs(A_patched, k=k_modes, M=E_csr, sigma=shift_val, which='LR', ncv=ncv_val)

print("Finished! Top 10 Eigenvalues:")
for ev in np.sort(evals)[-10:]:
    print(f"  {ev.real:.4f} + {ev.imag:.4f}j")