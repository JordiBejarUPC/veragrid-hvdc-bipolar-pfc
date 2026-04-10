
from pathlib import Path

import numpy as np
import VeraGridEngine.api as gc


PRIVATE_TESTS_ROOT = Path(__file__).resolve().parent
DATA_ROOT = PRIVATE_TESTS_ROOT / "data"


def normalize_empty_profiles(grid):
    for elm in grid.get_all_elements_iter():
        for prop in elm.registered_properties.values():
            if prop.has_profile():
                profile = elm.get_profile_by_prop(prop)
                if profile.size() == 0:
                    profile.clear()


def load_roundtrip_grids(tmp_path):
    raw_path = DATA_ROOT / "01_A-HP_0-ST_2027_INV_MAX-D_v33.raw"
    veragrid_path = tmp_path / "01_A-HP_0-ST_2027_INV_MAX-D_v33.veragrid"

    imported_grid = gc.open_file(str(raw_path))
    gc.save_file(grid=imported_grid, filename=str(veragrid_path))
    reloaded_grid = gc.open_file(str(veragrid_path))

    return imported_grid, reloaded_grid


def test_raw_to_veragrid_roundtrip_preserves_multicircuit(tmp_path):
    imported_grid, reloaded_grid = load_roundtrip_grids(tmp_path)

    normalize_empty_profiles(imported_grid)
    normalize_empty_profiles(reloaded_grid)

    circuits_match, circuit_logger = imported_grid.compare_circuits(reloaded_grid)
    if not circuits_match:
        circuit_logger.print()
    assert circuits_match

    imported_nc = gc.compile_numerical_circuit_at(imported_grid)
    reloaded_nc = gc.compile_numerical_circuit_at(reloaded_grid)

    numerical_match, numerical_logger = imported_nc.compare(nc_2=reloaded_nc, tol=1e-6)
    if not numerical_match:
        numerical_logger.print()
    assert numerical_match


def test_raw_to_veragrid_roundtrip_preserves_power_flow_voltages(tmp_path):
    imported_grid, reloaded_grid = load_roundtrip_grids(tmp_path)

    imported_pf = gc.power_flow(imported_grid)
    reloaded_pf = gc.power_flow(reloaded_grid)

    assert np.allclose(imported_pf.voltage, reloaded_pf.voltage, atol=1e-9)
