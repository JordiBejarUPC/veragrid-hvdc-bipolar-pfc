import VeraGridEngine.api as gce  # For interfacing with the GridCal API
import VeraGridEngine.Devices as dev
import VeraGridEngine.Simulations as sim
from VeraGridEngine.Compilers.circuit_to_newton_pa import translate_newton_pa_pf_results, newton_pa_pf
from VeraGridEngine.IO.file_handler import FileOpen
import VeraGridEngine.enumerations as en


#Loading the 5 buses cases from matpower
main_circuit = gce.open_file(r'C:\eRoots\VeraGrid\Grids_and_profiles\grids\case14.m')
#create lists of branches and generators, which are the elements which can fail, and which will be considered in the Contingency Analysis
branches = main_circuit.get_branches()
gens = main_circuit.get_generators()

# manually generate the contingencies, by adding each branch (branch=line or transformer) and generator to a contingency group
for i, br in enumerate(branches):
    # add a contingency group
    group = gce.ContingencyGroup(name="contingency branch {}".format(i+1))
    main_circuit.add_contingency_group(group)

    # add the branch contingency to the groups, only groups are failed at once
    con = gce.Contingency(device=br, name=br.name, group=group)
    main_circuit.add_contingency(con)

for i, gen in enumerate(gens):
    # add a contingency group
    group = gce.ContingencyGroup(name="contingency gen {}".format(i+1))
    main_circuit.add_contingency_group(group)

    # add the gen contingency to the groups, only groups are failed at once
    # con = gce.Contingency(device=gen, name=gen.name, group=group,
    #                       value=100.0,
    #                       prop=gce.ContingencyOperationTypes.PowerPercentage)

    con = gce.Contingency(device=gen, name=gen.name, group=group)

    main_circuit.add_contingency(con)

## add some other contingencies, which are considered as specials, i.e. that two lines are off simultaneously, in this lines 3 and 5
# group = gce.ContingencyGroup(name="Special contingency two lines off")
# main_circuit.add_contingency_group(group)
# main_circuit.add_contingency(gce.Contingency(idtag=branches[3].idtag, name=branches[3].name, group=group))
# main_circuit.add_contingency(gce.Contingency(idtag=branches[5].idtag, name=branches[5].name, group=group))

#setup and execute the contingency analysis
pf_options = gce.PowerFlowOptions(solver_type=gce.SolverType.NR)
# declare the contingency options
options_ = gce.ContingencyAnalysisOptions(use_provided_flows=False,
                                      Pf=None,
                                      contingency_method=en.ContingencyMethod.PowerFlow,
                                      pf_options=pf_options)

simulation = gce.ContingencyAnalysisDriver(grid=main_circuit,
                                       options=options_,
                                       linear_multiple_contingencies=None  # it is computed inside
                                       )

simulation.run()
