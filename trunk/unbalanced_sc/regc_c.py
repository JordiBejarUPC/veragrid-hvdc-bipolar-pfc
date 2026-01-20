import numpy as np

def transformation_alpha_beta(ur, ui, fref, Fnom):

    dphi_ref = (fref - 1.0) * 2.0 * np.pi * Fnom

    mag = np.sqrt(ur * ur + ui * ui)
    phi = np.arctan2(ui, ur)

    ur1 = mag * np.cos(phi + dphi_ref)
    ui1 = mag * np.sin(phi + dphi_ref)

    return ur1, ui1, dphi_ref

def pll(ir, ii, ur1, ui1, dphi, Vt):

    uq = 0
    phi = 2 * np.atan((-ur1 + np.sqrt(ui1**2 - uq**2 + ur1**2)) / (ui1 + uq))

    phi1 = phi - dphi

    id_pll = np.cos(phi1) * ir + np.sin(phi1) * ii
    iq_pll = -np.sin(phi1) * ir + np.cos(phi1) * ii

    return iq_pll, id_pll

def regc_c(Qgen0, Iqcmd, ir, ii, ur, ui, fref, Fnom, Vt, Ipcmd, is_blocked):

    iq_ref = - Iqcmd

    ur1, ui1, dphi_ref = transformation_alpha_beta(ur, ui, fref, Fnom)

    iq_pll, id_pll = pll(ir, ii, ur1, ui1, dphi_ref, Vt)

    Vt_fltr = max(Vt, 0.01)

    RateFlag = 0 # Rate limit in: 0 = active current, 1 = active power
    if RateFlag > 0.5:
        V_or_one = Vt_fltr
    else:
        V_or_one = 1

    ip_or_pp = Ipcmd * V_or_one

    id_ref = ip_or_pp / V_or_one

    iq_err = iq_ref - iq_pll
    id_err = id_ref - id_pll

    # The PI should be added

    iqref = iq_ref
    idref = id_ref

    return iqref, idref


iq_ref, id_ref = regc_c(Qgen0=0.0,
                        Iqcmd=0.8257392,
                        ir=-0.8601111,
                        ii=-0.9747866,
                        ur=-0.01885961,
                        ui=-0.5427275,
                        fref=1.0,
                        Fnom=50.0,
                        Vt=0.5430551,
                        Ipcmd=1.004069,
                        is_blocked=0.0)

print('\nid_ref =', id_ref)
print('\niq_ref =', iq_ref)

# Rf = 25
# iq_ref, id_ref = regc_c(Qgen0=0.0,
#                         Iqcmd=0.8257392,
#                         ir=-0.8601111,
#                         ii=-0.9747866,
#                         ur=-0.01885961,
#                         ui=-0.5427275,
#                         fref=1.0,
#                         Fnom=50.0,
#                         Vt=0.5430551,
#                         Ipcmd=1.004069,
#                         is_blocked=0.0)

# Rf = 50
# iq_ref, id_ref = regc_c(Qgen0=0.0,
#                         Iqcmd=0.2469015,
#                         ir=0.3062647,
#                         ii=-1.084971,
#                         ur=0.3961233,
#                         ui=-0.7321879,
#                         fref=1.0,
#                         Fnom=50.0,
#                         Vt=0.8324739,
#                         Ipcmd=1.1,
#                         is_blocked=0.0)
