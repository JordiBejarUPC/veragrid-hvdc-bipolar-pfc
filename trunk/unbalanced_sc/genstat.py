import numpy as np

u1 = - 0.1520085 - 0.3936368j
iq_ref = -1.067915
id_ref = 0.00294366

cos_u1 = np.real(u1) / abs(u1)
sin_u1 = np.imag(u1) / abs(u1)

i1 = (id_ref * cos_u1 - iq_ref * sin_u1) + 1j * (id_ref * sin_u1 + iq_ref * cos_u1)

s1 = u1 * np.conj(i1)

Pref = np.real(s1) * 2 # MW
Qref = np.imag(s1) * 2 # MVAr

print('\nP_ref =', Pref, 'MW')
print('Q_ref =', Qref, 'MVAr')