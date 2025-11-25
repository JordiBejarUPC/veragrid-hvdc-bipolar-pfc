import numpy as np
import VeraGridEngine.api as vg

fname = '/home/santi/Documentos/Git/eRoots/VeraGrid/Grids_and_profiles/grids/ACTIVS500.veragrid'

grid = vg.open_file(fname)

# 1. Copperplate dispatch (suppose it is done)

# 2. power flow + Contingencies

pf_drv = vg.PowerFlowDriver(grid=grid)
pf_drv.run()

con_opf = vg.ContingencyAnalysisOptions(

    # use the provided flows?
    use_provided_flows=True,

    # Pass here more exact base flows, otherwise linear ones will be computed
    Pf=pf_drv.results.Sf,

    # Contingency method to use
    contingency_method=vg.ContingencyMethod.PowerFlow,

    # optional, you can send here any contingency groups
    contingency_groups=grid.get_contingency_groups(),

    # if no power flow options are provided
    # a linear power flow is used
    pf_options=vg.PowerFlowOptions()
)
con = vg.ContingencyAnalysisDriver(grid=grid, options=con_opf)

# COmpute linear sensitivites
nc = vg.compile_numerical_circuit_at(grid)

lin = vg.LinearAnalysis(nc)

Sbus = nc.get_power_injections()  # MW + jMVAr

con.run()
nbr = grid.get_branch_number()
ncon = grid.get_contingency_groups_number()
threshold = 0.05
for k in range(nbr):

    base_loading = abs(pf_drv.results.loading[k])
    if base_loading < 1.0:

        # No base overload

        for con_idx in range(ncon):
            con_loading = abs(con.results.loading[con_idx, k])

            if con_loading > 1.0:

                # And, contingency overload

                print(f"Contingency: base {base_loading * 100} %, "
                      f"con: {con_loading * 100}%")

                Overload_MW = abs(con.results.Sf[con_idx, k]) - nc.passive_branch_data.rates[k]

                ptdf_line = np.sort(lin.PTDF[k, :])[::-1]

                for i, val in enumerate(ptdf_line):
                    if val > threshold:
                        P = nc.bus_data.srap_availbale_power[i]
                        if P > 0:
                            print(f"\tbus {i} can help: {val}")

                            dFlow = val * P

                            if dFlow >= Overload_MW:
                                print("\t\tCan solve!")

    else:
        # base overload!
        Overload_MW = abs(pf_drv.results.Sf[k]) - nc.passive_branch_data.rates[k]

        print(f"Base overload: {base_loading * 100} %")

        ptdf_line = np.sort(lin.PTDF[k, :])[::-1]

        for i, val in enumerate(ptdf_line):
            if val > threshold:

                P = nc.bus_data.srap_availbale_power[i]
                if P > 0:
                    print(f"\tbus {i} can help: {val}")

                    dFlow = val * P

                    if dFlow >= Overload_MW:
                        print("\t\tCan solve!")

# print(con.results.loading)
