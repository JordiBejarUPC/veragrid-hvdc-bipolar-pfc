import os

import numpy as np
import VeraGridEngine.api as vg

fname = os.path.join(os.getcwd(), '../../Grids_and_profiles/grids/ACTIVS500.veragrid')

grid = vg.open_file(fname)

# 1. Copperplate dispatch (suppose it is done)

# 2. power flow + Contingencies

pf_drv = vg.PowerFlowDriver(grid=grid)
pf_drv.run()

con_opf = vg.ContingencyAnalysisOptions(

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

available_margin = nc.generator_data.pmax - nc.generator_data.p
arbitrary_generators_providing_support = np.where(available_margin > 10)[0]  # These will be the ones with reserve capacity that will be offered in the tertiary market

# create technologies list
technologies = np.array(['Unknown'] * grid.get_generators_number(), dtype=str)
for k, elm in enumerate(grid.generators):
    if elm.tech_list:
        technologies[k] = elm.tech_list[0].name
    else:
        technologies[k] = 'Unknown'

# First, remedial actions are applied to the base overloaded branches.
for k in range(nbr):

    selected_generators = []
    generator_weights = []
    generator_technologies = []

    compensating_generators = []
    compensating_weights = []
    compensating_technologies = []

    total_marginP = 0
    correction_P = 0

    base_loading = abs(pf_drv.results.loading[k])
    if base_loading > 1.0:
        Overload_MW = abs(pf_drv.results.Sf[k]) - nc.passive_branch_data.rates[k]

        idx = np.argsort(lin.PTDF[k, :])[::-1]
        ptdf_line = np.sort(lin.PTDF[k, :])[::-1]

        for i, val in enumerate(ptdf_line):

            if val > threshold:

                P = nc.bus_data.srap_available_power[idx[i]]
                gens = np.where(nc.generator_data.get_bus_indices() == idx[i])[0]

                marginP = 0
                for gen in gens:
                    available_reduction = nc.generator_data.p[gen] - nc.generator_data.pmin[gen]
                    if available_reduction > 0:

                        selected_generators.append(gen)
                        generator_weights.append(val)
                        generator_technologies.append(technologies[gen])

                        marginP += available_reduction
                        total_marginP += available_reduction

                if marginP > 0:
                    print(f"\tbus {i} can help: {val}")

                    dFlow = val * marginP

                    if dFlow >= Overload_MW: # we could set a conditional so that when the marginP is enough, we consider the contingency solved and stop searching for generators.
                        print("\t\tCan solve!")

            # elif val < 0: # Technically, a lot of generators can enter here to substitute the lost generation. Probably should be a few big units with some room for compensation.
            #
            #     gens = np.where(nc.generator_data.get_bus_indices() == idx[i])[0]
            #
            #     for gen in gens:
            #         available_increment = nc.generator_data.pmax[gen] - nc.generator_data.p[gen]
            #         if available_increment > 0:
            #             compensating_generators.append(gen)
            #             compensating_weights.append(val)
            #             compensating_technologies.append(nc.generator_data.technologies[gen])
            #             correction_P += available_increment

        for gen in arbitrary_generators_providing_support:
            if gen in selected_generators:
                pass
            else:
                compensating_generators.append(gen)
                compensating_weights.append(lin.PTDF[k, :][nc.generator_data.bus_idx[gen]])
                compensating_technologies.append(technologies[gen])
                correction_P += available_margin[gen]
        print('')



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
                        P = nc.bus_data.srap_available_power[i]
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

                P = nc.bus_data.srap_available_power[i]
                if P > 0:
                    print(f"\tbus {i} can help: {val}")

                    dFlow = val * P

                    if dFlow >= Overload_MW:
                        print("\t\tCan solve!")

# print(con.results.loading)
