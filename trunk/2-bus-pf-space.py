import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


def generate_2bus_fractal_labeled(resolution=400, max_iter=30):
    """
    Simulates a 2-Bus network to map Newton-Raphson convergence basins
    with explicit plot color labels and no root marker dots.
    """
    # System Grid Parameters (Per Unit)
    V1 = 1.0  # Slack Bus Voltage
    theta1 = 0.0  # Slack Bus Angle

    # Line Admittance (Y-bus components)
    Y12 = 1.961
    alpha12 = -1.373  # Transmission angle in radians
    Y22 = 1.961
    alpha22 = 1.768  # Self-admittance angle

    # Bus 2 Scheduled Loading (P2, Q2)
    P_sched = -0.4
    Q_sched = -0.2

    # System Roots for Classification
    root0 = np.array([0.95, 0.08])  # Stable solution
    root1 = np.array([0.09, 1.02])  # Unstable solution

    # Build the mesh grid of initial guesses (State Space)
    v_space = np.linspace(0.01, 1.5, resolution)
    t_space = np.linspace(-np.pi, np.pi, resolution)
    T, V = np.meshgrid(t_space, v_space)

    theta = T.flatten()
    volt = V.flatten()
    N = len(theta)

    # 0 = Diverged (Black), 1 = High-V (Blue), 2 = Low-V (Red)
    color_map = np.zeros(N, dtype=int)

    # Vectorized Newton-Raphson Engine
    for i in range(N):
        x = np.array([volt[i], theta[i]])
        converged = False

        for k in range(max_iter):
            v_k = x[0]
            t_k = x[1]

            # Evaluate mismatches
            P_calc = V1 * v_k * Y12 * np.cos(t_k - theta1 - alpha12) + (v_k ** 2) * Y22 * np.cos(-alpha22)
            Q_calc = V1 * v_k * Y12 * np.sin(t_k - theta1 - alpha12) + (v_k ** 2) * Y22 * np.sin(-alpha22)
            f_mismatch = np.array([P_calc - P_sched, Q_calc - Q_sched])

            if np.linalg.norm(f_mismatch) < 1e-4:
                converged = True
                break

            # Compute Jacobian elements
            dP_dV = V1 * Y12 * np.cos(t_k - theta1 - alpha12) + 2 * v_k * Y22 * np.cos(-alpha22)
            dP_dtheta = -V1 * v_k * Y12 * np.sin(t_k - theta1 - alpha12)

            dQ_dV = V1 * Y12 * np.sin(t_k - theta1 - alpha12) + 2 * v_k * Y22 * np.sin(-alpha22)
            dQ_dtheta = V1 * v_k * Y12 * np.cos(t_k - theta1 - alpha12)

            J = np.array([[dP_dV, dP_dtheta],
                          [dQ_dV, dQ_dtheta]])

            try:
                dx = np.linalg.solve(J, -f_mismatch)
                x += dx
            except np.linalg.LinAlgError:
                break

        if converged:
            dist_to_high = np.linalg.norm(x - root0)
            dist_to_low = np.linalg.norm(x - root1)

            if dist_to_high < dist_to_low:
                color_map[i] = 1  # Map to Blue Basin
            else:
                color_map[i] = 2  # Map to Red Basin

    Z = color_map.reshape(resolution, resolution)

    # Plotting setup
    plt.figure(figsize=(10, 7))
    cmap_custom = plt.cm.colors.ListedColormap(['#111111', '#1f77b4', '#d62728'])
    plt.pcolormesh(T, V, Z, cmap=cmap_custom, shading='auto')

    # Graph labels
    plt.title("2-Bus Power Flow Newton-Raphson Convergence Fractal Map", fontsize=12, fontweight='bold')
    plt.xlabel("Initial Guess: Phase Angle $\\theta_2$ (radians)", fontsize=10)
    plt.ylabel("Initial Guess: Voltage Magnitude $V_2$ (p.u.)", fontsize=10)

    # Create explicit color legend patches matching your output
    blue_patch = mpatches.Patch(color='#1f77b4', label='Blue: Operable (High-Voltage) Basin')
    red_patch = mpatches.Patch(color='#d62728', label='Red: Voltage Collapse (Low-Voltage) Basin')
    black_patch = mpatches.Patch(color='#111111', label='Black: Numerical Divergence / Failure')

    # Add legend to the plot layout
    plt.legend(handles=[blue_patch, red_patch, black_patch], loc='upper right', facecolor='white', framealpha=0.95)
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    generate_2bus_fractal_labeled(resolution=400, max_iter=30)
