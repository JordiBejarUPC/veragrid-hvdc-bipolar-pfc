# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
"""Static IEEE39 network normalization for the dynamic reference case."""

from __future__ import annotations

from VeraGridEngine.Devices.Injections.generator import Generator
from VeraGridEngine.Devices.Injections.load import Load
from VeraGridEngine.Devices.Injections.shunt import Shunt
from VeraGridEngine.Devices.Substation.bus import Bus
import VeraGridEngine.api as gce


class Ieee39GeneratorOperatingPoint:
    """Static operating point and limits for one IEEE39 generator."""

    __slots__ = ("bus_number", "p", "vset", "snom", "qmax", "qmin")

    def __init__(
        self: "Ieee39GeneratorOperatingPoint",
        bus_number: int,
        p: float,
        vset: float,
        snom: float,
        qmax: float,
        qmin: float,
    ) -> None:
        """Store one generator operating point.

        :param bus_number: One-based IEEE bus number.
        :param p: Scheduled active power in MW.
        :param vset: Regulated voltage magnitude in per unit.
        :param snom: Machine rating in MVA.
        :param qmax: Maximum reactive power in MVAr.
        :param qmin: Minimum reactive power in MVAr.
        :return: None.
        """
        self.bus_number: int = bus_number
        self.p: float = p
        self.vset: float = vset
        self.snom: float = snom
        self.qmax: float = qmax
        self.qmin: float = qmin


class Ieee39LoadOperatingPoint:
    """Static operating point for one IEEE39 constant-power load."""

    __slots__ = ("bus_number", "p", "q")

    def __init__(
        self: "Ieee39LoadOperatingPoint",
        bus_number: int,
        p: float,
        q: float,
    ) -> None:
        """Store one load operating point.

        :param bus_number: One-based IEEE bus number.
        :param p: Active demand in MW.
        :param q: Reactive demand in MVAr.
        :return: None.
        """
        self.bus_number: int = bus_number
        self.p: float = p
        self.q: float = q


def _bus_number(bus: Bus) -> int:
    """Return the integer RAW bus code.

    :param bus: VeraGrid bus loaded from the IEEE39 RAW file.
    :return: One-based IEEE bus number.
    """
    return int(bus.code)


def _find_bus(grid: gce.MultiCircuit, bus_number: int) -> Bus | None:
    """Find one IEEE39 bus by its stable RAW bus code.

    :param grid: RAW-loaded VeraGrid network.
    :param bus_number: One-based IEEE bus number.
    :return: Matching bus or ``None``.
    """
    matching_bus: Bus | None = None
    bus: Bus
    for bus in grid.buses:
        if _bus_number(bus) == bus_number:
            matching_bus = bus
        else:
            pass
    return matching_bus


def _get_generator_operating_points() -> tuple[Ieee39GeneratorOperatingPoint, ...]:
    """Return dynamic-case generator operating points in bus order.

    :return: Ten generator records for buses 30 through 39.
    """
    return (
        Ieee39GeneratorOperatingPoint(30, 436.086385, 1.035534, 1040.0, 153.18, -58.084),
        Ieee39GeneratorOperatingPoint(31, 645.999998, 1.013246, 836.0, 429.804, -122.665),
        Ieee39GeneratorOperatingPoint(32, 724.999998, 1.020528, 843.7, 446.722, -180.218),
        Ieee39GeneratorOperatingPoint(33, 651.999998, 1.01343, 1174.8, 548.208, -213.78),
        Ieee39GeneratorOperatingPoint(34, 507.999998, 1.019109, 1080.2, 611.495, -188.028),
        Ieee39GeneratorOperatingPoint(35, 686.999998, 1.06, 1085.7, 593.788, -234.972),
        Ieee39GeneratorOperatingPoint(36, 579.999998, 1.06, 1025.2, 568.372, -249.132),
        Ieee39GeneratorOperatingPoint(37, 321.521338, 1.013996, 970.2, 443.468, -216.122),
        Ieee39GeneratorOperatingPoint(38, 764.783381, 1.052803, 1684.1, 834.775, -356.889),
        Ieee39GeneratorOperatingPoint(39, 574.17, 1.03, 1199.0, 574.85, -173.261),
    )


def _get_load_operating_points() -> tuple[Ieee39LoadOperatingPoint, ...]:
    """Return dynamic-case constant-power loads in bus order.

    :return: Nineteen load records.
    """
    return (
        Ieee39LoadOperatingPoint(3, 600.0, 250.0),
        Ieee39LoadOperatingPoint(4, 450.0, 184.0),
        Ieee39LoadOperatingPoint(7, 233.8, 84.0),
        Ieee39LoadOperatingPoint(8, 522.0, 176.6),
        Ieee39LoadOperatingPoint(12, 120.0, 30.0),
        Ieee39LoadOperatingPoint(15, 320.0, 153.0),
        Ieee39LoadOperatingPoint(16, 329.0, 32.3),
        Ieee39LoadOperatingPoint(18, 158.0, 30.0),
        Ieee39LoadOperatingPoint(20, 680.0, 103.0),
        Ieee39LoadOperatingPoint(21, 274.0, 115.0),
        Ieee39LoadOperatingPoint(23, 247.5, 84.6),
        Ieee39LoadOperatingPoint(24, 308.6, -92.2),
        Ieee39LoadOperatingPoint(25, 224.0, 47.2),
        Ieee39LoadOperatingPoint(26, 139.0, 17.0),
        Ieee39LoadOperatingPoint(27, 281.0, 75.5),
        Ieee39LoadOperatingPoint(28, 206.0, 27.6),
        Ieee39LoadOperatingPoint(29, 283.5, 126.9),
        Ieee39LoadOperatingPoint(31, 80.0, 40.0),
        Ieee39LoadOperatingPoint(39, 400.0, 250.0),
    )


def _find_generator_point(
    bus_number: int,
    points: tuple[Ieee39GeneratorOperatingPoint, ...],
) -> Ieee39GeneratorOperatingPoint | None:
    """Find a generator operating point without an untyped dictionary.

    :param bus_number: One-based bus number.
    :param points: Generator operating-point records.
    :return: Matching point or ``None``.
    """
    matching_point: Ieee39GeneratorOperatingPoint | None = None
    point: Ieee39GeneratorOperatingPoint
    for point in points:
        if point.bus_number == bus_number:
            matching_point = point
        else:
            pass
    return matching_point


def _find_load_point(
    bus_number: int,
    points: tuple[Ieee39LoadOperatingPoint, ...],
) -> Ieee39LoadOperatingPoint | None:
    """Find a load operating point without an untyped dictionary.

    :param bus_number: One-based bus number.
    :param points: Load operating-point records.
    :return: Matching point or ``None``.
    """
    matching_point: Ieee39LoadOperatingPoint | None = None
    point: Ieee39LoadOperatingPoint
    for point in points:
        if point.bus_number == bus_number:
            matching_point = point
        else:
            pass
    return matching_point


def configure_ieee39_static_network(grid: gce.MultiCircuit) -> None:
    """Normalize a RAW-loaded network to the IEEE39 dynamic workbook.

    The RAW file contains four additional synchronous condensers and several
    stale load values.  The dynamic workbook retains only generators at buses
    30..39 and converts switched shunts at buses 4 and 5 to fixed shunts.

    :param grid: IEEE39 network loaded from the matching RAW case.
    :return: None.
    :raises ValueError: If a required generator or load is absent.
    """
    generator_points: tuple[Ieee39GeneratorOperatingPoint, ...] = _get_generator_operating_points()
    load_points: tuple[Ieee39LoadOperatingPoint, ...] = _get_load_operating_points()

    # Remove RAW-only condensers and configure the ten dynamic generators.
    generators: list[Generator] = list(grid.generators)
    generator: Generator
    configured_generator_count: int = 0
    for generator in generators:
        generator_bus_number: int = _bus_number(generator.bus)
        generator_point: Ieee39GeneratorOperatingPoint | None = _find_generator_point(
            generator_bus_number,
            generator_points,
        )
        if generator_point is None:
            grid.delete_injection_device(generator)
        else:
            generator.P = generator_point.p
            generator.Vset = generator_point.vset
            generator.Snom = generator_point.snom
            generator.Qmax = generator_point.qmax
            generator.Qmin = generator_point.qmin
            generator.Pmax = generator_point.snom
            generator.Pmin = 0.0
            configured_generator_count += 1
    if configured_generator_count != len(generator_points):
        raise ValueError(
            f"Configured {configured_generator_count} IEEE39 generators; "
            f"expected {len(generator_points)}."
        )
    else:
        pass

    # Parameter tables are indexed in bus order 30..39; reject a RAW importer
    # ordering change instead of silently applying a machine record to a
    # different generator.
    generator_index: int
    for generator_index in range(len(grid.generators)):
        ordered_bus_number: int = _bus_number(grid.generators[generator_index].bus)
        expected_bus_number: int = generator_index + 30
        if ordered_bus_number != expected_bus_number:
            raise ValueError(
                f"IEEE39 generator {generator_index + 1} is at bus "
                f"{ordered_bus_number}; expected bus {expected_bus_number}."
            )
        else:
            pass

    # Correct the load records to the values exported by the dynamic workbook.
    loads: list[Load] = list(grid.loads)
    load: Load
    configured_load_count: int = 0
    for load in loads:
        load_bus_number: int = _bus_number(load.bus)
        load_point: Ieee39LoadOperatingPoint | None = _find_load_point(
            load_bus_number,
            load_points,
        )
        if load_point is None:
            grid.delete_injection_device(load)
        else:
            load.P = load_point.p
            load.Q = load_point.q
            configured_load_count += 1
    if configured_load_count != len(load_points):
        raise ValueError(
            f"Configured {configured_load_count} IEEE39 loads; "
            f"expected {len(load_points)}."
        )
    else:
        pass

    # Replace switched RAW shunts with the two fixed workbook susceptances.
    shunt_devices: list[object] = list(grid.shunts)
    controllable_shunts: list[object] = list(grid.controllable_shunts)
    shunt_device: object
    for shunt_device in shunt_devices:
        grid.delete_injection_device(shunt_device)
    for shunt_device in controllable_shunts:
        grid.delete_injection_device(shunt_device)
    bus_four: Bus | None = _find_bus(grid=grid, bus_number=4)
    bus_five: Bus | None = _find_bus(grid=grid, bus_number=5)
    if bus_four is None or bus_five is None:
        raise ValueError("IEEE39 buses 4 and 5 are required for fixed shunts.")
    else:
        pass
    grid.add_shunt(bus=bus_four, api_obj=Shunt(name="IEEE39 fixed shunt 4", B=100.0))
    grid.add_shunt(bus=bus_five, api_obj=Shunt(name="IEEE39 fixed shunt 5", B=200.0))

    # The matching workbook contains 34 AC lines and 12 tap transformers.
    if len(grid.lines) != 34:
        raise ValueError(f"IEEE39 requires 34 lines; found {len(grid.lines)}.")
    else:
        pass
    if len(grid.transformers2w) != 12:
        raise ValueError(
            f"IEEE39 requires 12 two-winding transformers; "
            f"found {len(grid.transformers2w)}."
        )
    else:
        pass
    if len(grid.shunts) != 2:
        raise ValueError(f"IEEE39 requires 2 fixed shunts; found {len(grid.shunts)}.")
    else:
        pass
