import numpy as np

C = np.array([
    [-0.17019146340963007+0.5067190568153365j,  0.004243243788576534-0.01273006380043095j,  0.0042036502938664864-0.013193234895327458j,  0.005328437560417841-0.014623485391019575j],
    [ 0.0042432437885765339-0.01273006380043095j, -0.1982750850072135+0.571507148724193j,  0.08397582053482056-0.2108467103296928j,  0.045910317545693774-0.15749679748266085j],
    [ 0.004203650293866486-0.013193234895327458j,  0.08397582053482056-0.2108467103296925j, -0.17362830964928058+0.5415998331424745j,  0.021725643737973713-0.12018695001472296j],
    [ 0.005328437560417841-0.014623485391019575j,  0.045910317545693774-0.15749679748266085j,  0.021725643737973727-0.12018695001472296j, -0.1536174720472099+0.5110383976048933j]
])

D = np.array([
    [ 0.22419446340963006-0.5472188551095454j, -0.025234237885765336+0.027730001795098654j, -0.022203650293866485+0.026693169271542534j, -0.02032843756041784+0.026623411131106817j],
    [-0.025234237885765336+0.027730001795098654j,  0.2192750850072135-0.5865069422429622j, -0.08397582053482056+0.2108467056189497j, -0.045910317545693774+0.1574967562014916j],
    [-0.022203650293866485+0.02669316927154253j,  -0.08397582053482056+0.2108467056189497j,  0.19162830964928057-0.5550996378083065j, -0.021725643737973727+0.12018692570488314j],
    [-0.02032843756041784+0.026623411131106817j,  -0.045910317545693774+0.1574967562014916j, -0.021725643737973727+0.12018692570488314j,  0.1686174720472099-0.5230382127950474j]
])

Uslack = np.array([
    0.0 * np.exp(1j * 0.0),
    1.0 * np.exp(1j * 0.0),
    1.0 * np.exp(1j * -120 * np.pi / 180),
    1.0 * np.exp(1j * 120 * np.pi / 180)
])

# Inicialización con formulación directa de corriente
# Vload0 = np.linalg.solve(D, -C @ Vsl)

# Inicialización original
Uload = np.copy(Uslack)

x = np.zeros(8, dtype=float)
x[0], x[1] = np.real(Uload[0]), np.imag(Uload[0])
x[2], x[3] = np.real(Uload[1]), np.imag(Uload[1])
x[4], x[5] = np.real(Uload[2]), np.imag(Uload[2])
x[6], x[7] = np.real(Uload[3]), np.imag(Uload[3])

iter = 0
for i in range(1000):
    xcomplex = np.array([x[0] + 1j * x[1], x[2] + 1j * x[3], x[4] + 1j * x[5], x[6] + 1j * x[7]])
    res_s = xcomplex * np.conj(D @ xcomplex + C @ Uslack) # S = U (Y U)* = 0
    res_p = np.real(res_s)
    res_q = np.imag(res_s)
    res_tot_old = np.array([res_p, res_q]).flatten()

    xc = np.copy(x)

    J = np.zeros((len(x), len(x)))

    for j in range(len(x)):
        xc += 1e-6
        xcomplex = np.array([xc[0] + 1j * xc[1], xc[2] + 1j * xc[3], xc[4] + 1j * xc[5], xc[6] + 1j * xc[7]])
        res_s = xcomplex * np.conj(D @ xcomplex + C @ Uslack)  # S = U (Y U)* = 0
        res_p = np.real(res_s)
        res_q = np.imag(res_s)
        res_tot_new = np.array([res_p, res_q]).flatten()
        J[:, j] = (res_tot_new - res_tot_old) / 1e-6
        xc[j] -= 1e-6

    print(J)

    dx = np.linalg.solve(J, -res_tot_old)
    x += 0.01 * dx

    print(abs(res_tot_old))
    print(abs(res_tot_new))
    print(x)
    print('--------')

    if np.max(abs(dx)) < 1e-6:
        break

    iter += 1

Un = x[0] + 1j * x[1]
Ua = x[2] + 1j * x[3]
Ub = x[4] + 1j * x[5]
Uc = x[6] + 1j * x[7]

print(f"Un = {abs(Un):.5f} ∠ {np.angle(Un, deg=True):.1f}°")
print(f"Ua = {abs(Ua):.5f} ∠ {np.angle(Ua, deg=True):.1f}°")
print(f"Ub = {abs(Ub):.5f} ∠ {np.angle(Ub, deg=True):.1f}°")
print(f"Uc = {abs(Uc):.5f} ∠ {np.angle(Uc, deg=True):.1f}°")

print("\n Iterations = ", iter)