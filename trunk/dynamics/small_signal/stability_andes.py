# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
To run this script andes must be installed (pip install andes)
"""
import andes
import pandas as pd
import numpy as np

CASES = {
    "KUNDUR_no_shunt": 'kundur_ieee_no_shunt.json',
    "SMIB": andes.get_case("smib/SMIB.json"),
    "IEEE14": andes.get_case("ieee14/ieee14_full.xlsx"),
    "IEEE39": andes.get_case("ieee39/ieee39_full.xlsx"),
}

# CASE = CASES["KUNDUR_no_shunt"]
CASE = CASES["SMIB"]
# CASE = CASES["IEEE14"]
# CASE = CASES["IEEE39"]

def main():

    np.set_printoptions(precision=15, suppress=False)


    print(f"Loading case: {CASE}")


    ss = andes.load(CASE, default_config=True)

    ss.files.no_output = True

    # Constant-power loads, matching your Kundur setup
    ss.PQ.config.p2p = 1.0
    ss.PQ.config.p2i = 0
    ss.PQ.config.p2z = 0

    ss.PQ.config.q2q = 1.0
    ss.PQ.config.q2i = 0
    ss.PQ.config.q2z = 0

    ss.PFlow.config.tol = 1e-13
    ss.PFlow.run()

    print(f"\nDifferential states: {len(ss.dae.x)}")
    print(f"Algebraic variables: {len(ss.dae.y)}")

    print("\nState names:")
    for i, name in enumerate(ss.dae.x_name):
        print(f"{i:4d}: {name}")

    eig = ss.EIG
    eig.run()

    print("\nEigenvalues:")
    print(eig.mu)

    key = next(k for k, v in CASES.items() if v == CASE)

    pd.DataFrame(eig.mu).to_csv(
        f"Eigenvalues_results_Andes_{key}.csv",
        index=False,
        header=False,
    )

    pd.DataFrame(eig.pfactors.T).to_csv(
        f"pfactors_results_Andes_{key}.csv",
        index=False,
        header=False,
        float_format="%.10f",
    )

    return eig.As, eig.mu, eig.N, eig.W, eig.pfactors


if __name__ == '__main__':
    As, mu, N, W, pfactors = main()