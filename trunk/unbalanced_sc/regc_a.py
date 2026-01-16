def iq_limiter(Qgen0, Iqcmd):

    Iqrmin = -999.0 # Minimum reactive current rate limit in [pu/s]
    Iqrmax = 999.0 # Maximum reactive current rate limit in [pu/s]

    if Qgen0 > 0.0:
        sign_Qgen0 = 1.0
    else:
        sign_Qgen0 = 0.0

    if sign_Qgen0 > 0.5:
        # absortion
        iq = min(max(Iqcmd, -999.0), Iqrmax)
    else:
        # injection
        iq = min(max(Iqcmd, -abs(Iqrmin)), 999)

    return iq

def ip_limiter(Lvpl_lim, Ipcmd):

    ip = min(Lvpl_lim, Ipcmd)

    return ip

def high_voltage_reactive_current(iq, Vt):

    Volim = 1.2 # Voltage limit for high voltage clamp logic in [pu]
    Iolim = -1.1 # Current limit  for high voltage clamp logic in [pu]
    Khv = 0.7 # High voltage clamp logic accelerator factor

    if Vt > Volim:
        iqhv = Khv * (Vt - Volim)
    else:
        iqhv = 0.0

    iq_ref = -max(iq - iqhv, Iolim)

    return iq_ref

def low_voltage_active_current(ip, Vt):

    lvpnt0 = 0.4 # Minimum low voltage active current breakpoint in [pu]
    lvpnt1 = 0.8 # Maximum low voltage active current breakpoint in [pu]

    if Vt < lvpnt0:
        idlv = 0.0
    elif Vt > lvpnt1:
        idlv = 1.0
    else:
        idlv = 1 / (lvpnt1 - lvpnt0) * (Vt - lvpnt0)

    id_ref = ip * idlv

    return id_ref

def low_voltage_power_logic(Vt):

    zerox = 0.4 # LVPL zero crossing in [pu]
    brkpt = 0.9 # LVPL breakpoint in [pu]
    lvpl1 = 1.22 # LVPL gain breakpoint in [pu current / pu voltage]

    mlvpl = lvpl1 / (brkpt - zerox)

    if Vt < zerox:
        Lvplsw1 = 0.0
    elif Vt > brkpt:
        Lvplsw1 = 9999.0
    else:
        Lvplsw1 = mlvpl * (Vt - zerox)

    return Lvplsw1

def input_selector(Lvplsw0, Lvplsw1):

    Lvplsw = 1.0 # Low voltage power logic switch [1-Curve/0-Zero]

    if Lvplsw > 0.5:
        Lvpl_lim = Lvplsw1
    else:
        Lvpl_lim = Lvplsw0

    return Lvpl_lim

def regc_a(Qgen0,
           Iqcmd,
           Vt,
           Lvplsw0,
           Ipcmd):

    iq = iq_limiter(Qgen0, Iqcmd)

    iq_ref = high_voltage_reactive_current(iq, Vt)

    Lvplsw1 = low_voltage_power_logic(Vt)

    Lvpl_lim = input_selector(Lvplsw0, Lvplsw1)

    ip = ip_limiter(Lvpl_lim, Ipcmd)

    id_ref = low_voltage_active_current(ip, Vt)

    return id_ref, iq_ref


id_ref, iq_ref = regc_a(Qgen0=0.0,
                        Iqcmd=0.05,
                        Vt=0.93,
                        Lvplsw0=9999.0,
                        Ipcmd=1.08)

print('\nid_ref =', id_ref)
print('\niq_ref =', iq_ref)