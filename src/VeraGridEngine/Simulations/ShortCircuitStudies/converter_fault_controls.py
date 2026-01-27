import numpy as np
import bisect

def vdl(x, points):
    """
    Linear approximation with clamping.
    points: list of (x_i, y_i), sorted by x_i
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    # Clamp
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]

    # Find segment
    i = bisect.bisect_right(xs, x) - 1
    x0, y0 = xs[i], ys[i]
    x1, y1 = xs[i + 1], ys[i + 1]

    # Linear interpolation
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

def current_limit_logic(Iqcmd, vdlq, vdlp, Ipcmd, is_blocked):

    PqFlag = 0.0 # Priority flag on current limit
    Imax = 1.3 # Maximum converter current limit in [pu]
    Ke = 0.0 # Ipmin scaling factor

    if is_blocked > 0.0:
        blocking_factor = 0.0
    else:
        blocking_factor = 1.0

    # Reactive limits
    if PqFlag > 0.0:
        ip_used = min(vdlp, Imax, Ipcmd)
        iqmax = min(vdlq, np.sqrt(max(Imax ** 2 - ip_used ** 2, 0.0))) * blocking_factor
    else:
        iqmax = min(vdlq, Imax) * blocking_factor

    if iqmax < 0.0:
        iqmin = iqmax * blocking_factor
    else:
        iqmin = -iqmax * blocking_factor

    # Reactive limits
    if PqFlag > 0.0:
        ipmax = min(vdlp, Imax) * blocking_factor
    else:
        iq_used = min(vdlq, Imax, Iqcmd)
        ipmax = min(vdlp, np.sqrt(max(Imax ** 2 - iq_used ** 2, 0.0)))

    ipmin = -Ke * ipmax * blocking_factor

    return iqmin, iqmax, ipmin, ipmax

def pi_freeze_signals_steady(freeze, yi4, iqmin, iqmax):

    Kvp = 1.0
    VFlag = 1.0

    # Pre-saturation signal (no integral in steady-state model)
    u = Kvp * yi4

    # Output saturation
    yo = min(max(u, iqmin), iqmax)

    # Replicate the logic of freeze_up / freeze_low (as floats)
    freeze_up  = float((u >= (iqmax - 0.01)) and (freeze == 0.0) and (VFlag == 1.0))
    freeze_low = float((u <= (iqmin - 0.01)) and (freeze == 0.0) and (VFlag == 1.0))

    return yo, freeze_up, freeze_low

def reec_d(ur,
           ui,
           u,
           Vpf,
           q,
           p,
           Paux,
           PFAref,
           Qext,
           Vref1,
           Pref,
           Pref_out,
           Iq_unlim_0,
           Ip_unlim_0,
           ):

    Vt = u              # Input 0
    Vt_r = ur           # Input 1
    Vt_i = ui           # Input 2
    It_r = 0.0          # Input 3
    It_i = 0.0          # Input 4
    PFAref = PFAref     # Input 6
    Pe = p              # Input 7
    Qext = Qext         # Input 8
    Qgen = q            # Input 9
    Paux = Paux         # Input 11
    Speed = 1.0         # Input 12
    Pref = Pref         # Input 13
    Pref_WGO = Pref_out # Input 14

    # Current Blocking
    vblkl = 0.1 # Voltage below which the converter is blocked in [pu]
    vblkh = 1.2 # Voltage above which the converter is blocked in [pu]
    is_blocked = float((Vt >= vblkh) or (Vt <= vblkl))

    # Reactive Current Injection
    Vref0 = 0.0  # Reference voltage, enter 0 for terminal voltage in [pu]
    Vref = Vpf
    dbd1 = -0.05
    dbd2 = 0.05
    Kqv = 2.0
    Iqh1 = 1.1  # Maximum limit of reactive current injection in [pu]
    Iql1 = -1.1  # Minimum limit of reactive current injection in [pu]
    if Vref0 < 0.5:
        Vref0_sig = Vref
    else:
        Vref0_sig = Vref0
    Vdif = Vref0_sig - Vt
    if dbd1 == 0.0 and dbd2 == 0.0:
        Verr = Vdif
    elif Vdif > abs(dbd2):
        Verr = Vdif - abs(dbd2)
    elif Vdif < -abs(dbd1):
        Verr = Vdif + abs(dbd1)
    else:
        Verr = 0.0
    Iqv = Verr * Kqv
    Iqinj = min(max(Iqv, Iql1), Iqh1)

    # Fault Detection
    Vdip = 0.9 # Undervoltage condition trigger voltage in [pu]
    Vup = 1.1 # Overvoltage condition trigger voltage in [pu]
    Voltage_Dip = float((Vt < Vdip) or (Vt > Vup))
    freeze_Voltage_Dip = Voltage_Dip

    # Voltage Current Compensation
    Rc = 0.0  # Current compensation resistance in [pu]
    Xc = 0.1  # Current compensation reactance in [pu]
    vcr = Vt_r - Rc * It_r + Xc * It_i
    vci = Vt_i - Rc * It_i - Xc * It_r
    argVc = max(abs(vcr * vcr + vci * vci), 0)
    if Rc > 0.0 or Xc > 0.0:
        Vcomp = np.sqrt(argVc)
    else:
        Vcomp = Vt

    Kc = 0.02 # Reactive-current compensation gain
    yi12 = Vt + Kc * Qgen

    VcmpFlag = 0.0 # 0 = reactive droop, 1 = current compensation
    if VcmpFlag > 0.0:
        Vcmp = Vcomp
    else:
        Vcmp = yi12

    # Q-V Limitation
    o1 = np.tan(PFAref)
    o2 = Pe
    Qcalc = o1 * o2
    PfFlag = 0.0  # Power factor flag: 1 = pf control, 0 = Q control
    if PfFlag > 0.0:
        yi = Qcalc
    else:
        yi = Qext
    qvmin = -1.0  # Minimum reactive power limit in [pu]
    qvmax = 1.0  # Maximum reactive power limit in [pu]
    o3 = min(max(yi, qvmin), qvmax)

    yi9 = o3 / max(0.01, Vt)

    yi8 = yi9

    yi1 = o3 - Qgen

    # Voltage Limitation
    Vmin = 0.9  # Minimum voltage control in [pu]
    Vmax = 1.1  # Maximum voltage control in [pu]
    yi2 = min(max(yi1, Vmin), Vmax)

    yi7 = Vref1 + o3

    VFlag = 1.0 # Voltage control flag: 1 = Q ctrl, 0 = voltage control
    if VFlag > 0.0:
        yi3 = yi2
    else:
        yi3 = yi7

    o4 = min(max(yi3, Vmin), Vmax)

    yi4 = o4 - Vcmp

    oarray_vdlq = [(1.10, 1.10), (1.15, 1.00), (1.30, 0.00)]
    vdlq = vdl(Vt, oarray_vdlq)

    oarray_vdlp = [(1.10, 1.10), (1.15, 1.00), (1.30, 0.00)]
    vdlp = vdl(Vt, oarray_vdlp)

    iqmin, iqmax, i_in1, i_in = current_limit_logic(Iq_unlim_0, vdlq, vdlp, Ip_unlim_0, is_blocked)

    yi5, freeze_up_sig, freeze_low_sig = pi_freeze_signals_steady(freeze_Voltage_Dip, yi4, iqmin, iqmax)

    QFlag = 0.0 # Q control flag: 1 = voltage/Q, 0 = constant PF or Q control
    if QFlag > 0.0:
        o5 = yi5
    else:
        o5 = yi8

    Iq_unlim = Iqinj + o5

    Iqcmd = max(min(Iq_unlim, iqmax), iqmin)

    WGO_active = 0.0 # Weak Grid Option
    if WGO_active > 0.0:
        yi13 = Pref_WGO
    else:
        yi13 = Pref

    dPmin = -2.0 # Ramp rate on power reference in [pu/s]
    dPmax = 2.0  # Ramp rate on power reference in [pu/s]
    o6 = max(min(yi13, dPmax), dPmin)

    yi11 = Speed * o6

    PFlag = 1.0
    if PFlag > 0.0:
        yi10 = yi11
    else:
        yi10 = o6

    Pmin, Pmax = 0, 1 # Minimum and Maximum power reference in [pu]
    Pord = max(min(yi10, Pmax), Pmin)

    o12 = Paux + Pord

    o7 = max(Vt, 0.01)

    Ip_unlim = o12 / o7

    Ipcmd = max(min(Ip_unlim, i_in), i_in1)

    return Iqcmd, Ipcmd, is_blocked, Iq_unlim, Ip_unlim


def regc_c(Iqcmd, ir, ii, ur, ui, fref, Fnom, Vt, Ipcmd, is_blocked):

    iq_ref = - Iqcmd

    dphi_ref = (fref - 1.0) * 2.0 * np.pi * Fnom

    mag = np.sqrt(ur * ur + ui * ui)
    phi = np.arctan2(ui, ur)

    ur1 = mag * np.cos(phi + dphi_ref)
    ui1 = mag * np.sin(phi + dphi_ref)

    uq = 0
    phi = 2 * np.atan((-ur1 + np.sqrt(ui1 ** 2 - uq ** 2 + ur1 ** 2)) / (ui1 + uq))

    phi1 = phi - dphi_ref

    id_pll = np.cos(phi1) * ir + np.sin(phi1) * ii
    iq_pll = -np.sin(phi1) * ir + np.cos(phi1) * ii

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

def genstat(ur, ui, iq_ref, id_ref, Sn):

    u1 = ur + 1j * ui

    cos_u1 = np.real(u1) / abs(u1)
    sin_u1 = np.imag(u1) / abs(u1)

    i1 = (id_ref * cos_u1 - iq_ref * sin_u1) + 1j * (id_ref * sin_u1 + iq_ref * cos_u1)

    s1 = u1 * np.conj(i1)

    Pref = np.real(s1) * Sn  # MW
    Qref = np.imag(s1) * Sn  # MVAr

    return Pref, Qref

def wecc_wt_type_4b(V_measured, P_measured, Q_measured, S_base_vg, S_rated_vsc, Vpf):

    Vt = abs(V_measured) # Absolute value of the converter's voltage [pu]
    Vt_r = np.real(V_measured) # Real component of the converter's voltage [pu]
    Vt_i = np.imag(V_measured) # Imaginary component of the converter's voltage [pu]

    S_measured = (-P_measured - 1j * Q_measured) * S_base_vg / S_rated_vsc # Converter's power [pu]
    P = np.real(S_measured) # Converter's active power [pu]
    Q = np.imag(S_measured) # Converter's reactive power [pu]

    I_measured = S_measured / V_measured # Converter's current [pu]
    Ir = np.real(I_measured) # Real component of the converter's current [pu]
    Ii = np.imag(I_measured) # Imaginary component of the converter's current [pu]

    Iq_unlim_0, Iqcmd = 0.0, 0.0
    Ip_unlim_0, Ipcmd = 1.3, 1.3
    Iq_error = 1
    Ip_error = 1

    print('Vt =', round(Vt,6))
    print('Vt_i =', round(Vt_i,7))
    print('Vt_r =', round(Vt_r,7))
    print('Q =', round(Q,8))
    print('P =', round(P,7))
    print('Vpf =', round(Vpf,7))

    # Vt = 0.858757
    # Vt_i = -0.1253401
    # Vt_r = 0.8495608
    # Q = 0.06907914
    # P = 0.9446327
    # Vpf = 0.9489775

    while Iq_error > 1e-6 or Ip_error > 1e-6:
        Iqcmd, Ipcmd, is_blocked, Iq_unlim, Ip_unlim = reec_d(ur=Vt_r,
                                                              ui=Vt_i,
                                                              u=Vt,
                                                              q=Q,
                                                              p=P,
                                                              Vpf=Vpf,
                                                              Paux=0.0,
                                                              PFAref=0.0,
                                                              Qext=0.0,
                                                              Vref1=0.0,
                                                              Pref=1.0,
                                                              Pref_out=1.0,
                                                              Iq_unlim_0=Iq_unlim_0,
                                                              Ip_unlim_0=Ip_unlim_0)

        Iq_error = abs(Iq_unlim - Iq_unlim_0)
        Ip_error = abs(Ip_unlim - Ip_unlim_0)

        print('\n', Iq_error, ' ', Ip_error)

        Iq_unlim_0 = Iq_unlim
        Ip_unlim_0 = Ip_unlim

    print()

    iq_ref, id_ref = regc_c(Iqcmd=Iqcmd, # Current reference from REEC_D [pu]
                            ir=Ir, # Real component of the converter's current [pu]
                            ii=Ii, # Imaginary component of the converter's current [pu]
                            ur=Vt_r, # Real component of the converter's voltage [pu]
                            ui=Vt_i, # Imaginary component of the converter's voltage [pu]
                            fref=1.0, # Reference frequency [pu]
                            Fnom=50.0, # Nominal frequency [Hz]
                            Vt=Vt, # Absolute value of the converter's voltage [pu]
                            Ipcmd=Ipcmd, # Current reference from REEC_D [pu]
                            is_blocked=0.0 # Converter's disconnection = 1
                            )

    print()

    Pref, Qref = genstat(ur=Vt_r, # Real component of the converter's voltage [pu]
                         ui=Vt_i, # Imaginary component of the converter's voltage [pu]
                         iq_ref=iq_ref, # Current reference from REGC_C [pu]
                         id_ref=id_ref, # Current reference from REGC_C [pu]
                         Sn=S_rated_vsc # Converter's nominal power [MVA]
                         )

    print("\nPref =", Pref, 'MW')
    print("\nQref =", Qref, 'MVAr\n')

    return -Pref/S_base_vg, -Qref/S_base_vg