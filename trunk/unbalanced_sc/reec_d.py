import numpy as np
import bisect

def current_blocking(Vt):

    vblkl = 0.1 # Voltage below which the converter is blocked in [pu]
    vblkh = 1.2 # Voltage above which the converter is blocked in [pu]

    is_blocked = float((Vt >= vblkh) or (Vt <= vblkl))

    return is_blocked

def reactive_current_injection(Vt):

    Vref0 = 0.0 # Reference voltage, enter 0 for terminal voltage in [pu]
    Vref = 1.005925
    dbd1 = -0.05
    dbd2 = 0.05
    Kqv = 2.0
    Iqh1 = 1.1 # Maximum limit of reactive current injection in [pu]
    Iql1 = -1.1 # Minimum limit of reactive current injection in [pu]

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

    return Iqinj


def fault_detection(Vt):

    Vdip = 0.9 # Undervoltage condition trigger voltage in [pu]
    Vup = 1.1 # Overvoltage condition trigger voltage in [pu]

    Voltage_Dip = float((Vt < Vdip) or (Vt > Vup))

    return Voltage_Dip, Voltage_Dip

def qv_limitation(PFAref, Pe, Qext):

    o1 = np.tan(PFAref)
    o2 = Pe
    Qcalc = o1 * o2

    PfFlag = 0.0 # Power factor flag: 1 = pf control, 0 = Q control

    if PfFlag > 0.0:
        yi = Qcalc
    else:
        yi = Qext

    qvmin = -1.0 # Minimum reactive power limit in [pu]
    qvmax = 1.0 # Maximum reactive power limit in [pu]

    o3 = min(max(yi, qvmin), qvmax)

    return o3


def voltage_limitation(yi1):

    Vmin = 0.9 # Minimum voltage control in [pu]
    Vmax = 1.1 # Maximum voltage control in [pu]

    yi2 = min(max(yi1, Vmin), Vmax)

    return yi2

def voltage_current_compensation(Vt, Vt_r, Vt_i, It_r, It_i):

    Rc = 0.0 # Current compensation resistance in [pu]
    Xc = 0.1 # Current compensation reactance in [pu]

    vcr = Vt_r - Rc * It_r + Xc * It_i
    vci = Vt_i - Rc * It_i - Xc * It_r

    argVc = max(abs(vcr * vcr + vci * vci), 0)

    if Rc > 0.0 or Xc > 0.0:
        Vcomp = np.sqrt(argVc)
    else:
        Vcomp = Vt

    return Vcomp


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


def freeze_iq_after_dip(Voltage_Dip, Iq_frz, y_in):

    if Voltage_Dip == 0.0:
        Iq_unlim = y_in
    else:
        Iq_unlim = Iq_frz

    return Iq_unlim


def reec_d(ur,
           ui,
           u,
           q,
           p,
           Paux,
           PFAref,
           Qext,
           Vref1,
           Pref,
           Pref_out):

    Vt = u              # Input 0
    Vt_r = ur           # Input 1
    Vt_i = ui           # Input 2
    It_r = 0.0          # Input 3
    It_i = 0.0          # Input 4
    Iq_frz = 0.0        # Input 5
    PFAref = PFAref     # Input 6
    Pe = p              # Input 7
    Qext = Qext         # Input 8
    Qgen = q            # Input 9
    p_flag = 1.0        # Input 10
    Paux = Paux         # Input 11
    Speed = 1.0         # Input 12
    Pref = Pref         # Input 13
    Pref_WGO = Pref_out # Input 14

    is_blocked = current_blocking(Vt)

    Iqinj = reactive_current_injection(Vt)

    Voltage_Dip, freeze_Voltage_Dip = fault_detection(Vt)

    Vcomp = voltage_current_compensation(Vt, Vt_r, Vt_i, It_r, It_i)

    Kc = 0.02 # Reactive-current compensation gain
    yi12 = Vt + Kc * Qgen

    VcmpFlag = 0.0 # 0 = reactive droop, 1 = current compensation
    if VcmpFlag > 0.0:
        Vcmp = Vcomp
    else:
        Vcmp = yi12

    o3 = qv_limitation(PFAref, Pe, Qext)

    yi9 = o3 / max(0.01, Vt)

    yi8 = yi9

    yi1 = o3 - Qgen

    yi2 = voltage_limitation(yi1)

    yi7 = Vref1 + o3

    VFlag = 1.0 # Voltage control flag: 1 = Q ctrl, 0 = voltage control
    if VFlag > 0.0:
        yi3 = yi2
    else:
        yi3 = yi7

    o4 = voltage_limitation(yi3)

    yi4 = o4 - Vcmp

    oarray_vdlq = [(1.10, 1.10), (1.15, 1.00), (1.30, 0.00)]
    vdlq = vdl(Vt, oarray_vdlq)

    oarray_vdlp = [(1.10, 1.10), (1.15, 1.00), (1.30, 0.00)]
    vdlp = vdl(Vt, oarray_vdlp)

    Iq_unlim, Ip_unlim = 0.05269481, 1.075758 # TO CALCULATE FIRST

    iqmin, iqmax, i_in1, i_in = current_limit_logic(Iq_unlim, vdlq, vdlp, Ip_unlim, is_blocked)

    yi5, freeze_up_sig, freeze_low_sig = pi_freeze_signals_steady(freeze_Voltage_Dip, yi4, iqmin, iqmax)

    QFlag = 0.0 # Q control flag: 1 = voltage/Q, 0 = constant PF or Q control
    if QFlag > 0.0:
        o5 = yi5
    else:
        o5 = yi8

    y_in = Iqinj + o5

    Iq_unlim = freeze_iq_after_dip(Voltage_Dip, Iq_frz, y_in)

    Iqcmd = max(min(Iq_unlim, iqmax), iqmin)

    WGO_active = 0.0 # Weak Grid Option
    if WGO_active > 0.0:
        yi13 = Pref_WGO
    else:
        yi13 = Pref

    dPmin = -2.0 # Ramp rate on power reference in [pu/s]
    dPmax = 2.0  # Ramp rate on power reference in [pu/s]
    Iqcmd = max(min(yi13, dPmax), dPmin)

    return Iqcmd, Ipcmd, is_blocked


Iqcmd, Ipcmd, is_blocked = reec_d(ur=0.9097126,
                                  ui=-0.1911462,
                                  u=0.9295773,
                                  q=0.1699287,
                                  p=3.264566,
                                  Paux=0.0,
                                  PFAref=0.0,
                                  Qext=0.0,
                                  Vref1=0.0,
                                  Pref=1.0,
                                  Pref_out=1.0)
