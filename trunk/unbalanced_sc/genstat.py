import numpy as np

def genstat(ur, ui, iq_ref, id_ref):

    u1 = ur + 1j * ui

    cos_u1 = np.real(u1) / abs(u1)
    sin_u1 = np.imag(u1) / abs(u1)

    i1 = (id_ref * cos_u1 - iq_ref * sin_u1) + 1j * (id_ref * sin_u1 + iq_ref * cos_u1)

    s1 = u1 * np.conj(i1)

    Pref = np.real(s1) * 2  # MW
    Qref = np.imag(s1) * 2  # MVAr

    return Pref, Qref

Pref, Qref = genstat(ur = -0.1520085,
                     ui = -0.3936368,
                     iq_ref = -1.067915,
                     id_ref = 0.00294366)

print('\nP_ref =', Pref, 'MW')
print('Q_ref =', Qref, 'MVAr')