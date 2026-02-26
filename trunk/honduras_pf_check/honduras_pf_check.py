import numpy as np
import VeraGridEngine as vg


#
m_file = "/home/santi/Escritorio/01_A_HP_0_ST_2027_INV_MAX_D_v33.m"
raw_file = "/home/santi/Escritorio/01_A-HP_0-ST_2027_INV_MAX-D_v33.raw"

m_grid = vg.open_file(m_file)
m_grid.convert_line_to_transformer(m_grid.lines[156])
m_nc = vg.compile_numerical_circuit_at(m_grid)
m_adm = m_nc.get_admittance_matrices()

raw_grid = vg.open_file(raw_file,
                        options=vg.FileOpenOptions(
                            psse_use_short_names=True,
                            psse_flatten_virtual_taps=False
                        ))
raw_nc = vg.compile_numerical_circuit_at(raw_grid)
raw_adm = raw_nc.get_admittance_matrices()

# ok, logger = m_nc.compare(raw_nc, tol=1e-6)
#
# logger.print()
#
# Y_m = m_adm.Ybus.toarray()
# Y_raw = raw_adm.Ybus.toarray()
#
# B_m = Y_m.imag
# B_raw = Y_raw.imag
#
# B_diff = B_m - B_raw
# idx = np.where(abs(B_diff) > 1e-6)
#
# for i, j in zip(idx[0], idx[1]):
#     print(i, j, B_diff[i, j])

raw_branches_dict = {br.code: br for br in raw_grid.get_branches_iter()}

for br_m, br_raw in zip(m_grid.get_branches_iter(), raw_grid.get_branches_iter()):

    for prp in ["R", "X", "G", "B", "tap_module", "tap_angle"]:

        if hasattr(br_m, prp):
            a = getattr(br_m, prp)
            b = getattr(br_raw, prp)
            if not np.isclose(a, b):
                print(br_m.code, br_raw.code, " ", prp, a, b)
print()
