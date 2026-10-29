import VeraGridEngine.api as gce  # For interfacing with the GridCal API
import VeraGridEngine.Devices as dev
import VeraGridEngine.Simulations as sim
from VeraGridEngine.Compilers.circuit_to_newton_pa import translate_newton_pa_pf_results, newton_pa_pf
from VeraGridEngine.IO.file_open import FileOpen
import VeraGridEngine.enumerations as en
from sklearn.metrics import mean_squared_error


# Example based on the network proposed by "Power System State Estimation" by Ali Abur and Antonio Gómez Expósito
# it is also the same that is being used on the examples in PandaPower
# setup, execute and return the results of a power flow
def ExecutePF(grid, show=False):
    options = gce.PowerFlowOptions(gce.SolverType.NR, verbose=False)
    power_flow = gce.PowerFlowDriver(grid, options)
    power_flow.run()

    losses = power_flow.results.losses.sum()
    bus_df = power_flow.results.get_bus_df()
    branch_df = power_flow.results.get_branch_df()
    if show:
        print('Converged:', power_flow.results.converged, 'error:', power_flow.results.error)
        print(bus_df)
        print(branch_df)

    return losses, bus_df, branch_df


# creates the network defined in the network proposed by "Power System State Estimation" by Ali Abur and Antonio Gómez Expósito
# in order to study the state estimation problem
# parameter load when True, adds the loads, aimed to calculate the powerflow
# when False, it creates the network without loads, aimed to calculate the optimal power flow, as the loads will be "substitute" by the measurements

def CreateGrid(load=True):
    Vbase = 10  # kV
    Sbase = 100

    m_circuit = gce.MultiCircuit(Sbase=Sbase)
    m_circuit.Sbase = Sbase
    b1 = gce.Bus('b1', Vnom=Vbase, is_slack=True)
    b2 = gce.Bus('b2', Vnom=Vbase)
    b3 = gce.Bus('b3', Vnom=Vbase)
    m_circuit.add_bus(b1)
    m_circuit.add_bus(b2)
    m_circuit.add_bus(b3)

    br0 = gce.Line(b1, b2, name='l1')
    br0.fill_design_properties(r_ohm=0.01, x_ohm=0.03, c_nf=0.0,
                               length=1.0, Imax=1.0, freq=m_circuit.fBase, Sbase=m_circuit.Sbase)
    br1 = gce.Line(b1, b3, name='l2')
    br1.fill_design_properties(r_ohm=0.02, x_ohm=0.05, c_nf=0.0,
                               length=1.0, Imax=1.0, freq=m_circuit.fBase, Sbase=m_circuit.Sbase)
    br2 = gce.Line(b2, b3, name='l3')
    br2.fill_design_properties(r_ohm=0.03, x_ohm=0.08, c_nf=0.0,
                               length=1.0, Imax=1.0, freq=m_circuit.fBase, Sbase=m_circuit.Sbase)

    m_circuit.add_line(br0)
    m_circuit.add_line(br1)
    m_circuit.add_line(br2)

    if load:
        load1 = gce.Load('load 1', P=50, Q=30)
        load2 = gce.Load('load 2', P=150, Q=80)
        m_circuit.add_load(b2, load1)
        m_circuit.add_load(b3, load2)

    return m_circuit


# Create an execute the powerflow of the network with loads
m_circuit = CreateGrid(load=True)
losses, bus_df, branch_df = ExecutePF(m_circuit, show=False)
# Create the network without loads, instead the exampled adds measurements to the network, based on the book "Power System State Estimation" by Ali Abur and Antonio Gómez Expósito
# it executes the State Estimation algorithm implemented in GridCal, and shows the results of the state estimation
m_circuit2 = CreateGrid(load=False)
m_circuit2.add_vm_measurement(gce.VmMeasurement(1.006, 0.004, m_circuit2.buses[0]))
m_circuit2.add_vm_measurement(gce.VmMeasurement(0.968, 0.004, m_circuit2.buses[1]))
m_circuit2.add_pi_measurement(gce.PiMeasurement(-0.501, 0.010, m_circuit2.buses[1]))
m_circuit2.add_qi_measurement(gce.QiMeasurement(-0.286, 0.010, m_circuit2.buses[1]))
m_circuit2.add_pf_measurement(gce.PfMeasurement(0.888, 0.008, m_circuit2.lines[0]))
m_circuit2.add_pf_measurement(gce.PfMeasurement(1.173, 0.008, m_circuit2.lines[1]))
m_circuit2.add_qf_measurement(gce.QfMeasurement(0.568, 0.008, m_circuit2.lines[0]))
m_circuit2.add_qf_measurement(gce.QfMeasurement(0.663, 0.008, m_circuit2.lines[1]))

# Declare the simulation driver and run
se = gce.StateEstimationDriver(circuit=m_circuit2)
se.run()

print('Converged:', se.results.converged, 'error:', se.results.error)

print("compare the results")
print("---- True Power Flow results ----")
print(bus_df)
print(branch_df)
print("---- State Estimation results ----")
print(se.results.get_bus_df())
print(se.results.get_branch_df() * 100)

# Calculate the MSE between both measures Powerflow or State Estimation WLS (gridcal), by using the Mean Squared Error (MSE) function
sepf = se.results.get_branch_df().Pf.values
pfpf = branch_df.Pf.values
error = mean_squared_error(sepf * 100, pfpf)
print(f"Mean Squared Error for Pf: {error}")

seqf = se.results.get_branch_df().Qf.values
pfqf = branch_df.Qf.values
error = mean_squared_error(seqf * 100, pfqf)
print(f"Mean Squared Error for Pf: {error}")
