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

# Slack de 1∠0, -120, 120 grados
Vsl = np.array([
    0.0 * np.exp(1j * 0.0),
    1.0 * np.exp(1j * 0.0),
    1.0 * np.exp(1j * -120 * np.pi / 180),
    1.0 * np.exp(1j * 120 * np.pi / 180)
])

# Inicialización con formulación directa de corriente
# Vload0 = np.linalg.solve(D, -C @ Vsl)

# Inicialización original
Vload0 = np.copy(Vsl)

# Vector de variables reales: [Re(Vn), Im(Vn), Re(Va), Im(Va), Re(Vb), Im(Vb), Re(Vc), Im(Vc)]
x = np.zeros(8, dtype=float)
x[0], x[1] = np.real(Vload0[0]), np.imag(Vload0[0])
x[2], x[3] = np.real(Vload0[1]), np.imag(Vload0[1])
x[4], x[5] = np.real(Vload0[2]), np.imag(Vload0[2])
x[6], x[7] = np.real(Vload0[3]), np.imag(Vload0[3])

# Iteraciones Newton–Raphson
for it in range(50):
    # Calcula residuo actual
    xcomplex = np.array([x[0] + 1j * x[1], x[2] + 1j * x[3], x[4] + 1j * x[5], x[6] + 1j * x[7]])
    res_pq = xcomplex * np.conj(D @ xcomplex + C @ Vsl)
    res_tot = np.array([np.real(res_pq), np.imag(res_pq)]).flatten()

    norm_res = np.linalg.norm(res_tot, np.inf)
    print(f"Iter {it}: Residuo = {norm_res:.3e}")
    if norm_res < 1e-8:
        break

    # Jacobiano numérico
    J = np.zeros((len(x), len(x)))
    for j in range(len(x)):
        xc = np.copy(x)
        xc[j] += 1e-12
        xcomplex = np.array([xc[0] + 1j * xc[1], xc[2] + 1j * xc[3], xc[4] + 1j * xc[5], xc[6] + 1j * xc[7]])
        res_pq = xcomplex * np.conj(D @ xcomplex + C @ Vsl)
        res_new = np.array([np.real(res_pq), np.imag(res_pq)]).flatten()
        J[:, j] = (res_new - res_tot) / 1e-12

    dx = np.linalg.solve(J, -res_tot)

    # Damping adaptativo
    alpha = 1.0
    while alpha > 1e-4:
        xtest = x + alpha * dx
        xcomplex = np.array([xtest[0] + 1j * xtest[1], xtest[2] + 1j * xtest[3], xtest[4] + 1j * xtest[5], xtest[6] + 1j * xtest[7]])
        res_pq = xcomplex * np.conj(D @ xcomplex + C @ Vsl)
        res_test = np.array([np.real(res_pq), np.imag(res_pq)]).flatten()
        if np.linalg.norm(res_test) < norm_res:
            x = xtest
            break
        alpha *= 0.5

# Resultado final
vn = x[0] + 1j * x[1]
va = x[2] + 1j * x[3]
vb = x[4] + 1j * x[5]
vc = x[6] + 1j * x[7]

print("Tensiones finales en bus 2:")
print(f"Vn = {abs(vn):.5f} ∠ {np.angle(vn, deg=True):.1f}°")
print(f"Va = {abs(va):.5f} ∠ {np.angle(va, deg=True):.1f}°")
print(f"Vb = {abs(vb):.5f} ∠ {np.angle(vb, deg=True):.1f}°")
print(f"Vc = {abs(vc):.5f} ∠ {np.angle(vc, deg=True):.1f}°")