import numpy as np


def calc1(r, x, g, b, tau, m, mf, mt, Vf, Vt):
    """

    :param r:
    :param x:
    :param g:
    :param b:
    :param tau:
    :param m:
    :param mf:
    :param mt:
    :param Vf:
    :param Vt:
    :return:
    """
    ys = 1 / (r + 1j * x)
    bc2 = (g + 1j * b) / 2.0

    yff = (ys + bc2) / (m ** 2 * mf ** 2 * np.exp(2j * tau))
    yft = -ys / (m * mf * mt)
    ytf = -ys / (m * mf * mt * np.exp(2j * tau))
    ytt = (ys + bc2) / (mt * mt)

    If = Vf * yff + Vt * yft
    It = Vf * ytf + Vt * ytt

    Sf = Vf * np.conj(If)
    St = Vt * np.conj(It)

    return Sf, St


def calc_cost(r, x, g, b, tau_set, m_set, mf, mt, Vf, Vt):
    """

    :param r:
    :param x:
    :param g:
    :param b:
    :param tau_set:
    :param m_set:
    :param mf:
    :param mt:
    :param Vf:
    :param Vt:
    :return:
    """
    ys = 1 / (r + 1j * x)
    bc2 = (g + 1j * b) / 2.0
    # mp = m * np.exp(1j * tau)

    yff = (ys + bc2) / (m_set ** 2 * mf ** 2 * np.exp(2j * tau_set))
    yft = -ys / (m_set * mf * mt)
    ytf = -ys / (m_set * mf * mt * np.exp(2j * tau_set))
    ytt = (ys + bc2) / (mt * mt)

    If = Vf * yff + Vt * yft
    It = Vf * ytf + Vt * ytt

    Sf = Vf * np.conj(If)
    St = Vt * np.conj(It)

    return Sf, St, ys, bc2, yff, yft, ytf, ytt


def calc_var(tau, m, mf, mt, Vf, Vt, ys, bc2, yff_c, yft_c, ytf_c, ytt_c):
    """

    :param tau:
    :param m:
    :param mf:
    :param mt:
    :param Vf:
    :param Vt:
    :param ys:
    :param bc2:
    :param yff_c:
    :param yft_c:
    :param ytf_c:
    :param ytt_c:
    :return:
    """
    yff_v = (ys + bc2) / (m ** 2 * mf ** 2 * np.exp(2j * tau))
    yft_v = -ys / (m * mf * mt)
    ytf_v = -ys / (m * mf * mt * np.exp(2j * tau))
    ytt_v = (ys + bc2) / (mt * mt)

    dIf = Vf * (yff_v - yff_c) + Vt * (yft_v - yft_c)
    dIt = Vf * (ytf_v - ytf_c) + Vt * (ytt_v - ytt_c)

    dSf = Vf * np.conj(dIf)
    dSt = Vt * np.conj(dIt)

    return dSf, dSt


def main():
    """
    This test checks that we can indeed build the
    Sf and St vectors in 2 parts
    :return:
    """

    # Original
    Sf1, St1 = calc1(r=0.01, x=0.05, g=0.0, b=0.002,
                     tau=0.1, m=0.98, mf=0.998, mt=1.001,
                     Vf=complex(1, 0), Vt=complex(0.98, 0.1))

    print(f"Base Sf:{Sf1}, St:{St1}")

    # Constant part
    Sfc2, Stc2, ys, bc2, yff_c, yft_c, ytf_c, ytt_c = calc_cost(
        r=0.01, x=0.05, g=0.0, b=0.002,
        tau_set=0.1, m_set=1.0,
        mf=0.998, mt=1.001,
        Vf=complex(1, 0), Vt=complex(0.98, 0.1)
    )
    # variable part (dependent on the tap (m < tau)
    dSfv2, dStv2 = calc_var(tau=0.1, m=0.98, mf=0.998, mt=1.001,
                            Vf=complex(1, 0), Vt=complex(0.98, 0.1),
                            ys=ys, bc2=bc2, yff_c=yff_c, yft_c=yft_c,
                            ytf_c=ytf_c, ytt_c=ytt_c)

    # we compose the final power that should be equal to the original
    Sf2 = Sfc2 + dSfv2
    St2 = Stc2 + dStv2

    print(f"Split Sf:{Sf2}, St:{St2}")

    print(f"diff Sf:{Sf1 - Sf2}, St:{St1 - St2}")


if __name__ == "__main__":
    main()
