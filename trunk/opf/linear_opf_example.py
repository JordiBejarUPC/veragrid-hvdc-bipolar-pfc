from __future__ import annotations

import sys
from time import perf_counter

from PySide6 import QtWidgets

import VeraGridEngine as vg
from VeraGrid.Gui.Main.VeraGridMain import VeraGridMainGUI
from VeraGrid.Session.session import GcThread
from VeraGridEngine.basic_structures import IntVec
from VeraGridEngine.enumerations import (
    EngineType,
    MIPFramework,
    MIPSolvers,
    OpfDispatchMode,
    SimulationTypes,
    SolverType,
    TimeGrouping,
    ZonalGrouping,
)


# This is the same plain driver run that was here originally.
# Keep it first so it remains the reference benchmark for the numerical path.
fname: str = "/home/santi/Escritorio/Demo NY grid/NY_activs.gridcal"
exit_code: int = 1

print("Loading...")
grid: vg.MultiCircuit = vg.open_file(fname)

print("Running optimization...")
driver2: vg.OptimalPowerFlowTimeSeriesDriver = vg.OptimalPowerFlowTimeSeriesDriver(
    grid=grid,
    options=vg.OptimalPowerFlowOptions(
        zonal_grouping=ZonalGrouping.NoGrouping,
        time_grouping=TimeGrouping.Daily,
    ),
    engine=EngineType.GSLV
)

# Wall timing includes everything around driver.run().
# driver2.elapsed is the driver's own internal timing.
plain_wall_start: float = perf_counter()
driver2.run()
plain_wall_seconds: float = perf_counter() - plain_wall_start

print("Plain done")
print("Plain driver elapsed:", driver2.elapsed, "s")
print("Plain wall elapsed:", plain_wall_seconds, "s")
# ----------------------------------------------------------------------------------------------------------------------

# The next block runs the same operation through the GUI machinery.
# The important part is that the GUI combo boxes are set, not just the driver.
# That catches the exact class of bug where the GUI silently keeps VeraGrid,
# changes a grouping option, enables reports, or uses another solver setting.
print("Loading GUI...")
application: QtWidgets.QApplication | None = QtWidgets.QApplication.instance()

if application is None:
    application = QtWidgets.QApplication(list())
else:
    pass

main_window: VeraGridMainGUI = VeraGridMainGUI()

# Use a fresh grid for the GUI path so the direct benchmark cannot mutate state
# that the GUI then reuses.
main_window.circuit = vg.open_file(fname)
main_window.file_name = fname

# The GUI uses these indices when OPF time series is active.
# update_date_dependent_combos() also initializes the default start/end range.
main_window.update_date_dependent_combos()

# Force the GUI dispatcher down the time-series OPF path.
# Without this, optimal_power_flow_dispatcher() may run the snapshot path.
main_window.ui.actionactivate_time_series.setChecked(True)

# Select GSLV in the actual GUI engine combo box.
# The combo model stores EngineType instances in UserRole, so findData() is the
# same lookup the visible GUI selection would use.
engine_index: int = main_window.ui.engineComboBox.findData(EngineType.GSLV)
if engine_index >= 0:
    main_window.ui.engineComboBox.setCurrentIndex(engine_index)
    engine_ok: bool = True
else:
    engine_ok = False

if engine_ok:
    # Changing the engine rebuilds solver-related combo models.
    # Run the same GUI callback explicitly so the benchmark sees the real GSLV UI state.
    main_window.modify_ui_options_according_to_the_engine()

    # Force the linear OPF solver, matching the plain benchmark.
    solver_index: int = main_window.ui.lpf_solver_comboBox.findData(SolverType.LINEAR_OPF)
    if solver_index >= 0:
        main_window.ui.lpf_solver_comboBox.setCurrentIndex(solver_index)
        solver_ok: bool = True
    else:
        solver_ok = False

    # Keep OPF dispatch normal, matching the default direct options.
    dispatch_index: int = main_window.ui.opfDispatchModeComboBox.findData(OpfDispatchMode.Normal)
    if dispatch_index >= 0:
        main_window.ui.opfDispatchModeComboBox.setCurrentIndex(dispatch_index)
        dispatch_ok: bool = True
    else:
        dispatch_ok = False

    # Force the same MIP framework used by default in OptimalPowerFlowOptions.
    mip_framework_index: int = main_window.ui.mip_framework_comboBox.findData(MIPFramework.PuLP)
    if mip_framework_index >= 0:
        main_window.ui.mip_framework_comboBox.setCurrentIndex(mip_framework_index)
        mip_framework_ok: bool = True
    else:
        mip_framework_ok = False

    # The solver list depends on the framework, so rebuild it after setting PuLP.
    main_window.update_available_mip_solvers()

    # Force HiGHS in the GUI selector.
    mip_solver_index: int = main_window.ui.mip_solver_comboBox.findData(MIPSolvers.HIGHS)
    if mip_solver_index >= 0:
        main_window.ui.mip_solver_comboBox.setCurrentIndex(mip_solver_index)
        mip_solver_ok: bool = True
    else:
        mip_solver_ok = False

    # Match the direct benchmark: daily grouping.
    time_grouping_index: int = main_window.ui.opf_time_grouping_comboBox.findData(TimeGrouping.Daily)
    if time_grouping_index >= 0:
        main_window.ui.opf_time_grouping_comboBox.setCurrentIndex(time_grouping_index)
        time_grouping_ok: bool = True
    else:
        time_grouping_ok = False

    # Match the direct benchmark: no zonal grouping.
    zonal_grouping_index: int = main_window.ui.opfZonalGroupByComboBox.findData(ZonalGrouping.NoGrouping)
    if zonal_grouping_index >= 0:
        main_window.ui.opfZonalGroupByComboBox.setCurrentIndex(zonal_grouping_index)
        zonal_grouping_ok: bool = True
    else:
        zonal_grouping_ok = False

    # Disable every GUI-only optional feature that would make the GUI path do
    # more work than the plain driver benchmark.
    main_window.ui.considerContingenciesOpfCheckBox.setChecked(False)
    main_window.ui.skipOpfGenerationLimitsCheckBox.setChecked(False)
    main_window.ui.opfConsiderRampsCheckBox.setChecked(False)
    main_window.ui.opfConsiderUpDownTimeCheckBox.setChecked(False)
    main_window.ui.opfSpinningReserveCheckBox.setChecked(False)
    main_window.ui.addOptimalPowerFlowReportCheckBox.setChecked(False)
    main_window.ui.fixOpfCheckBox.setChecked(False)
    main_window.ui.useGslkAsCostsOpfCheckBox.setChecked(False)
    main_window.ui.quadraticCostsOpfCheckBox.setChecked(False)
    main_window.ui.approximateLossesOpfCheckBox.setChecked(False)
    main_window.ui.save_mip_checkBox.setChecked(False)

    gui_config_ok: bool = (solver_ok and dispatch_ok and mip_framework_ok and mip_solver_ok and
                           time_grouping_ok and zonal_grouping_ok)
else:
    gui_config_ok = False

if main_window.circuit.time_profile is None:
    print("GUI run skipped: the grid has no time profile.")
else:
    if gui_config_ok:
        # Use the full time range selected by the GUI, then print the count at
        # the end so a time-index mismatch is obvious.
        main_window.setup_sim_indices(st=0, en=main_window.circuit.get_time_number() - 1)
        gui_options: vg.OptimalPowerFlowOptions | None = main_window.get_opf_options()

        print("Running GUI optimization...")
        print("GUI selected engine:", main_window.get_preferred_engine())
        if gui_options is not None:
            print("GUI solver:", gui_options.solver)
            print("GUI time grouping:", gui_options.time_grouping)
            print("GUI zonal grouping:", gui_options.zonal_grouping)
            print("GUI MIP framework:", gui_options.mip_framework)
            print("GUI MIP solver:", gui_options.mip_solver)
        else:
            pass

        # This is the actual GUI route: dispatcher -> run_opf_time_series() ->
        # SimulationSession.run() -> GcThread -> driver.run().
        gui_wall_start: float = perf_counter()
        main_window.optimal_power_flow_dispatcher()
        gui_thread: GcThread | None = main_window.session.threads.get(SimulationTypes.OPFTimeSeries_run, None)

        if gui_thread is None:
            print("GUI run failed to start.")
        else:
            # The worker completion and post-processing are signal driven.
            # Process Qt events while waiting so post_opf_time_series() runs.
            while gui_thread.isRunning():
                application.processEvents()
                gui_thread.wait(50)

            application.processEvents()
            gui_wall_seconds: float = perf_counter() - gui_wall_start

            gui_driver: vg.OptimalPowerFlowTimeSeriesDriver | None
            gui_results: object | None
            gui_driver, gui_results = main_window.session.optimal_power_flow_ts
            time_indices: IntVec | None = main_window.get_time_indices()

            print("GUI done")
            print("Plain driver engine:", driver2.engine)
            print("GUI driver engine:", gui_driver.engine if gui_driver is not None else None)
            print("GUI thread failed:", gui_thread.has_failed())
            print("GUI has results:", gui_results is not None)
            print("GUI time indices:", len(time_indices) if time_indices is not None else None)
            print("Plain driver elapsed:", driver2.elapsed, "s")
            print("Plain wall elapsed:", plain_wall_seconds, "s")
            print("GUI driver elapsed:", gui_driver.elapsed if gui_driver is not None else None, "s")
            print("GUI wall elapsed:", gui_wall_seconds, "s")
            exit_code = 1 if gui_thread.has_failed() else 0
    else:
        print("GUI run skipped: GSLV or a required OPF option is not available in the GUI.")

main_window.close()
application.processEvents()

sys.exit(exit_code)
