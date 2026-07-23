# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
To run this script andes must be installed (pip install andes)
"""
import andes
import time
import pandas as pd
import numpy as np
import scipy.sparse as sp


def main():

   start = time.time()
   np.set_printoptions(precision=15, suppress=False)

   ss = andes.load('Gen_Load/kundur_ieee_no_shunt.json', default_config=True)
   # ss = andes.load('Gen_Load/simple_system3.json', default_config=True)
   n_xy = len(ss.dae.xy_name)
   print(f"Andes variables = {n_xy}")
   ss.files.no_output = True

   # fix P & Q load Andes
   ss.PQ.config.p2p = 1.0
   ss.PQ.config.p2i = 0
   ss.PQ.config.p2z = 0

   ss.PQ.config.q2q = 1.0
   ss.PQ.config.q2i = 0
   ss.PQ.config.q2z = 0

   dae = ss.dae

   # Run PF
   ss.PFlow.config.tol = 1e-13
   ss.PFlow.run()

   # print(f"Bus voltages = {ss.Bus.v.v}")
   # print(f"Bus angles = {ss.Bus.a.v}")

   end_pf = time.time()

   print(f"ANDES - PF time = {end_pf - start:.6f} [s]")

   start_eig = time.time()

   eig = ss.EIG
   eig.run()

   end_eig = time.time()

   print(f"ANDES - stability - Run time: {end_eig - start_eig:.6f} [s]")

   # fx = dae.fx
   # fy = dae.fy
   # gx = dae.gx
   # gy = dae.gy
   # A = eig.As
   # gyx = eig.gyx

   # gy_str = [str(e) for e in dae.y_name]
   # df_gy_str = pd.DataFrame(gy_str)
   # df_gy_str.to_csv("gy_str_results_Andes.csv", index=False, header=False)
   #
   # gy_vars = [str(e) for e in dae.y_name_output]
   # df_gy_vars = pd.DataFrame(gy_vars)
   # df_gy_vars.to_csv("gy_vars_results_Andes.csv", index=False, header=False)


   df_Eig = pd.DataFrame(eig.mu)
   df_Eig.to_csv("Eigenvalues_results_Andes.csv", index=False, header=False)

   # dense_pfactors = np.array(eig.pfactors).T
   df_pfactors = pd.DataFrame(eig.pfactors.T)
   df_pfactors.to_csv("pfactors_results_Andes.csv", index=False, header=False, float_format="%.10f")

   # case_path = get_case('kundur/kundur_full.xlsx')
   # ss = andes.run(case_path, routine='eig')
   # with open('kundur_full_eig.txt', 'r') as f:
   #    print(f.read())

   print("Eigenvalues:", eig.mu)
   print("Participation factors:", eig.pfactors)

   return eig.As, eig.mu, eig.N, eig.W, eig.pfactors

if __name__ == '__main__':
    As, mu, N, W, pfactors =  main()




