# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations
import math
import numpy as np
import sys
import os
from pathlib import Path
from typing import Dict, List, Type, Optional, Tuple
import VeraGridEngine.Devices as dev
from VeraGridEngine.basic_structures import Logger
from VeraGridEngine.IO.dgs.dgs_objects import (DGSElement,
                                               ChaRef,
                                               ChaVec,
                                               ElmAsm,
                                               ElmCoup,
                                               ElmFeeder,
                                               ElmGenstat,
                                               ElmLne,
                                               ElmLnesec,
                                               ElmLod,
                                               ElmLodlv,
                                               ElmLodlvp,
                                               ElmNet,
                                               ElmShnt,
                                               ElmSite,
                                               ElmSubstat,
                                               ElmSym,
                                               ElmTerm,
                                               ElmTr2,
                                               ElmTr3,
                                               ElmXnet,
                                               ElmZone,
                                               General,
                                               IntFolder,
                                               IntGrf,
                                               IntGrfcon,
                                               IntGrfnet,
                                               RelFuse,
                                               StaCubic,
                                               StaSwitch,
                                               TypAsmo,
                                               TypFuse,
                                               TypLne,
                                               TypLod,
                                               TypSym,
                                               TypTr2,
                                               TypTr3)


def _populate_from_pf_object(pf_obj: DGSElement, dgs_cls: Type[DGSElement]):
    """
    Populate a DGSElement subclass from a PowerFactory API object,
    using the class schema (properties_list).
    Assumes the DGSElement has an explicit __init__.
    """
    elem = dgs_cls()

    for prop in dgs_cls.properties_list:
        name = prop.name

        if hasattr(pf_obj, name):
            try:
                value = getattr(pf_obj, name)
            except Exception:
                value = None
        else:
            value = None

        setattr(elem, name, value)

    return elem


def _ref_id(x):
    """

    :param x:
    :return:
    """
    if x is None:
        return None
    s = str(x)
    return s.split("\\")[-1] if "\\" in s else s


def get_terminal_ids(element_id: str, cubics_by_objid: Dict[str, List[StaCubic]]) -> List[str]:
    """

    :param element_id:
    :param cubics_by_objid:
    :return:
    """
    cbs = cubics_by_objid.get(_ref_id(element_id), [])
    # fold_id suele ser el ID del ElmTerm “padre”
    return [_ref_id(cb.fold_id) for cb in cbs if _ref_id(cb.fold_id) is not None]


def parse_header(line: str) -> Tuple[str, Dict[str, int]]:
    """
    Parse $$ header line and return property -> index map.
    """
    element_type = line[2:].split(";", 1)[0]
    parts = line.strip().split(';')[1:]  # skip $$ElementType
    header_map: Dict[str, int] = {}

    for i, name_stub in enumerate(parts):
        name_stub = parts[i]
        stubs = name_stub.split("(")
        prop_name = stubs[0] if len(stubs) > 0 else name_stub
        header_map[prop_name] = i

    return element_type, header_map


def get_branch_buses(elm_id: str,
                     stacubic_dict: Dict[str, List[int]],
                     buses: List[dev.Bus],
                     cubics_by_objid: Dict[str, List[StaCubic]],
                     bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.Bus]:
    """
    Function to get the buses from a branch element
    :param elm_id:
    :param stacubic_dict:
    :param buses:
    :return:
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 2:
        try:
            return bus_by_term_id[term_ids[0]], bus_by_term_id[term_ids[1]]
        except KeyError:
            # Fall back to legacy obj_bus indexing if terminal mapping is incomplete
            pass

    # Legacy fallback (index-based), kept for backward compatibility
    bus_ids = stacubic_dict.get(elm_id, None)
    if bus_ids is None:
        raise ValueError(f"No buses for the line {elm_id}")

    if len(bus_ids) != 2:
        raise ValueError(f"Not exactly 2 buses for the line {elm_id}")

    bus_from = buses[bus_ids[0]]
    bus_to = buses[bus_ids[1]]

    return bus_from, bus_to


def get_injection_bus(elm_id: str,
                      stacubic_dict: Dict[str, List[int]],
                      buses: List[dev.Bus],
                      cubics_by_objid: Dict[str, List[StaCubic]],
                      bus_by_term_id: Dict[str, dev.Bus]) -> dev.Bus:
    """
    Function to get the bus from a injection element
    :param elm_id:
    :param stacubic_dict:
    :param buses:
    :return:
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 1:
        try:
            return bus_by_term_id[term_ids[0]]
        except KeyError:
            # Fall back to legacy obj_bus indexing if terminal mapping is incomplete
            pass

    # Legacy fallback (index-based), kept for backward compatibility
    bus_ids = stacubic_dict.get(elm_id, None)
    if bus_ids is None:
        raise ValueError(f"No buses for the element {elm_id}")

    if len(bus_ids) != 1:
        raise ValueError(f"Not exactly 1 bus for the element {elm_id}")

    return buses[bus_ids[0]]


def convert_dgs_to_bus(elmterm: ElmTerm,
                       pos_by_objid: Dict[str, Tuple[float, float]]) -> dev.Bus:
    """
    Convert ElmTerm to Bus
    :param elmterm: ElmTerm
    :param pos_by_objid: dictionary of graphical positions
    :return: Bus
    """
    tid = _ref_id(elmterm.ID)
    x, y = pos_by_objid.get(tid, (0.0, 0.0))
    bus = dev.Bus(
        name=elmterm.loc_name or f"Bus_{tid}",
        Vnom=float(elmterm.uknom or 0.0),
        vmin=0.9,
        vmax=1.1,
        xpos=float(x),
        ypos=float(-y),
        active=(int(elmterm.outserv or 0) == 0),
    )

    return bus


def convert_dgs_from_bus(bus: dev.Bus) -> ElmTerm:
    elm = ElmTerm()

    # TODO: implement conversion

    return elm


def convert_dgs_to_sequence_line(typlne: TypLne) -> dev.SequenceLineType:
    """
    Convert a TypLne to SequenceLineType
    :param typlne: TypLne
    :return: SequenceLineType
    """
    elm = dev.SequenceLineType(
        name=typlne.loc_name,
        R=typlne.rline,
        X=typlne.xline,
        B=typlne.bline,
        CnF=typlne.cline,
        R0=typlne.rline0,
        X0=typlne.xline0,
        B0=typlne.bline0,
        CnF0=typlne.cline0,
        Vnom=typlne.uline,
        Imax=typlne.sline,
        use_conductance=typlne.cline != 0.0
    )

    return elm


def _convert_pf_tr2_connection(code: str):
    """
    Convert a PowerFactory 2-character transformer connection code to VeraGrid enum when available.
    If the enum is not available or the code is unknown, return None and let defaults apply.
    """
    try:
        from VeraGridEngine.enumerations import WindingsConnection
    except Exception:
        return None

    if code is None:
        return None

    c = str(code).strip().upper()
    if c == "":
        return None

    # Common PowerFactory 2-char winding codes in DGS: Y, YN, D, Z, ZN
    try:
        return getattr(WindingsConnection, c)
    except AttributeError:
        return None


def convert_dgs_to_transformer_type(typtr2: TypTr2) -> dev.TransformerType:
    """
    Convert a TypTr2 to TransformerType
    :param typtr2: TypTr2
    :return: TransformerType
    """
    tpe = dev.TransformerType(hv_nominal_voltage=float(typtr2.utrn_h or 0.0),
                              lv_nominal_voltage=float(typtr2.utrn_l or 0.0),
                              nominal_power=float(typtr2.strn or 0.0),
                              copper_losses=float(typtr2.pcutr or 0.0),
                              iron_losses=float(typtr2.pfe or 0.0),
                              no_load_current=float(typtr2.curmg or 0.0),
                              short_circuit_voltage=float(typtr2.uktr or 0.0),
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name=typtr2.loc_name)

    conn_hv = _convert_pf_tr2_connection(getattr(typtr2, "tr2cn_h", None))
    conn_lv = _convert_pf_tr2_connection(getattr(typtr2, "tr2cn_l", None))

    if conn_hv is not None and hasattr(tpe, "conn_hv"):
        tpe.conn_hv = conn_hv

    if conn_lv is not None and hasattr(tpe, "conn_lv"):
        tpe.conn_lv = conn_lv

    return tpe


def _order_hv_lv(bus_a: dev.Bus, bus_b: dev.Bus, logger: Logger, tr_name: str) -> Tuple[dev.Bus, dev.Bus]:
    """
    Order two buses as (HV, LV) based on nominal voltage.
    If voltages are equal or undefined, keep the original order and warn.
    """
    va = float(getattr(bus_a, "Vnom", 0.0) or 0.0)
    vb = float(getattr(bus_b, "Vnom", 0.0) or 0.0)

    if va == 0.0 or vb == 0.0:
        logger.add_warning(f"Transformer '{tr_name}': one or both buses have Vnom=0.0 (va={va}, vb={vb}).")
        return bus_a, bus_b

    if va > vb:
        return bus_a, bus_b
    if vb > va:
        return bus_b, bus_a

    logger.add_warning(f"Transformer '{tr_name}': HV/LV ambiguous (equal Vnom={va}). Keeping original order.")
    return bus_a, bus_b


def convert_dgs_to_transformer(tr2: ElmTr2,
                               buses: List[dev.Bus],
                               stacubic_dict: Dict[str, List[int]],
                               templates_dict: Dict[str, dev.TransformerType],
                               freq: float,
                               baseMVA: float,
                               logger: Logger,
                               cubics_by_objid: Dict[str, List[StaCubic]],
                               bus_by_term_id: Dict[str, dev.Bus]) -> dev.Transformer2W:
    """
    Convert ElmTr2 to Transformer2W
    :param tr2: ElmTr2
    :param buses:
    :param stacubic_dict:
    :param templates_dict:
    :param freq:
    :param baseMVA:
    :param logger:
    :param cubics_by_objid:
    :param bus_by_term_id:
    :return: Transformer2W
    """
    template = templates_dict.get(tr2.typ_id, None)
    if template is None:
        template = templates_dict.get(_ref_id(tr2.typ_id), None)

    if template is None:
        raise ValueError(f"No template for the transformer {tr2.ID}")

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=tr2.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        # Fall back to legacy check only if terminal mapping is not available
        bus_ids = stacubic_dict.get(tr2.ID, None)
        if bus_ids is None:
            raise ValueError(f"No buses for the transformer {tr2.ID}")

        if len(bus_ids) != 2:
            raise ValueError(f"Not exactly 2 buses for the transformer {tr2.ID}")

    bus_from, bus_to = get_branch_buses(elm_id=tr2.ID,
                                        stacubic_dict=stacubic_dict,
                                        buses=buses,
                                        cubics_by_objid=cubics_by_objid,
                                        bus_by_term_id=bus_by_term_id)

    bus_hv, bus_lv = _order_hv_lv(bus_a=bus_from,
                                  bus_b=bus_to,
                                  logger=logger,
                                  tr_name=tr2.loc_name)

    trafo = dev.Transformer2W(bus_from=bus_hv,
                              bus_to=bus_lv,
                              name=tr2.loc_name,
                              active=not tr2.outserv,
                              HV=max(bus_hv.Vnom, bus_lv.Vnom),
                              LV=min(bus_hv.Vnom, bus_lv.Vnom),
                              nominal_power=float(
                                  getattr(template, "Sn", getattr(template, "nominal_power", 0.001)) or 0.001),
                              copper_losses=float(
                                  getattr(template, "Pcu", getattr(template, "copper_losses", 0.0)) or 0.0),
                              iron_losses=float(getattr(template, "Pfe", getattr(template, "iron_losses", 0.0)) or 0.0),
                              no_load_current=float(
                                  getattr(template, "I0", getattr(template, "no_load_current", 0.0)) or 0.0),
                              short_circuit_voltage=float(
                                  getattr(template, "Vsc", getattr(template, "short_circuit_voltage", 0.0)) or 0.0),
                              template=template)

    trafo.apply_template(obj=template, Sbase=baseMVA, logger=logger)

    return trafo


def convert_dgs_to_line(lne: ElmLne,
                        buses: List[dev.Bus],
                        stacubic_dict: Dict[str, List[int]],
                        templates_dict: Dict[str, dev.SequenceLineType],
                        freq: float,
                        baseMVA: float,
                        logger: Logger,
                        cubics_by_objid: Dict[str, List[StaCubic]],
                        bus_by_term_id: Dict[str, dev.Bus]) -> dev.Line:
    """

    :param lne:
    :param buses:
    :param stacubic_dict:
    :param templates_dict:
    :param freq:
    :param baseMVA:
    :param logger:
    :return:
    """

    template = templates_dict.get(lne.typ_id, None)
    if template is None:
        raise ValueError(f"No template for the line {lne.ID}")

    # Check connectivity through robust StaCubic.fold_id mapping first (preferred)
    term_ids = get_terminal_ids(element_id=lne.ID, cubics_by_objid=cubics_by_objid)
    if len(term_ids) != 2:
        # Fall back to legacy check only if terminal mapping is not available
        bus_ids = stacubic_dict.get(lne.ID, None)
        if bus_ids is None:
            raise ValueError(f"No buses for the line {lne.ID}")

        if len(bus_ids) != 2:
            raise ValueError(f"Not exactly 2 buses for the line {lne.ID}")

    bus_from, bus_to = get_branch_buses(elm_id=lne.ID,
                                        stacubic_dict=stacubic_dict,
                                        buses=buses,
                                        cubics_by_objid=cubics_by_objid,
                                        bus_by_term_id=bus_by_term_id)

    line = dev.Line(bus_from=bus_from,
                    bus_to=bus_to,
                    name=lne.loc_name,
                    active=not lne.outserv,
                    length=lne.dline)

    line.apply_template(obj=template, Sbase=baseMVA, freq=freq, logger=logger)

    return line


def _safe_float(x, default: float = 0.0) -> float:
    """
    Convert a value to float safely.
    """
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _safe_int(x, default: int = 0) -> int:
    """
    Convert a value to int safely.
    """
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _get_scale_factor(scale0: float, logger: Logger, name: str) -> float:
    """
    Interpret PowerFactory/DGS load scaling factor.
    """
    s = _safe_float(scale0, default=1.0)
    if s == 0.0:
        return 1.0

    # Heuristic: values > 10 are very likely percentages (e.g., 100 = 100%)
    if s > 10.0:
        logger.add_warning(f"Load '{name}': scale0={s} looks like percent. Interpreting as {s / 100.0}.")
        return s / 100.0

    return s


def _extract_load_pq(elmlod: ElmLod, logger: Logger) -> Tuple[float, float]:
    """
    Extract (P, Q) in MW/MVAr from an ElmLod.
    """
    name = elmlod.loc_name or _ref_id(elmlod.ID) or "Load"

    # Primary: direct P/Q
    p = _safe_float(getattr(elmlod, "plini", 0.0), 0.0)
    q = _safe_float(getattr(elmlod, "qlini", 0.0), 0.0)

    # Fallback: S + cos(phi)
    if p == 0.0 and q == 0.0:
        s = _safe_float(getattr(elmlod, "slini", 0.0), 0.0)
        cosphi = _safe_float(getattr(elmlod, "coslini", 0.0), 0.0)

        if s != 0.0 and cosphi != 0.0:
            cosphi = max(min(cosphi, 1.0), -1.0)
            p = s * cosphi
            sinphi = math.sqrt(max(0.0, 1.0 - cosphi * cosphi))
            q = s * sinphi
            logger.add_warning(f"Load '{name}': P/Q not provided, derived from slini/coslini.")

    # Apply scaling
    scale = _get_scale_factor(scale0=getattr(elmlod, "scale0", 1.0), logger=logger, name=name)
    p *= scale
    q *= scale

    return p, q


def _add_load_to_grid(grid: dev.MultiCircuit, bus: dev.Bus, load: dev.Load, logger: Logger) -> None:
    """
    Add a load to the grid with compatibility across MultiCircuit API variants.
    """
    try:
        load.bus = bus
    except Exception:
        pass

    try:
        grid.add_load(bus=bus, api_obj=load)
        return
    except TypeError:
        pass

    try:
        grid.add_load(obj=load, bus=bus)
        return
    except TypeError:
        pass

    try:
        grid.add_load(bus, load)
        return
    except TypeError:
        pass

    try:
        grid.add_load(obj=load)
        return
    except TypeError as e:
        logger.add_warning(f"Failed to add load '{load.name}' to grid: {e}")
        raise


def convert_dgs_to_load(elmlod: ElmLod,
                        stacubic_dict: Dict[str, List[int]],
                        buses: List[dev.Bus],
                        logger: Logger,
                        cubics_by_objid: Dict[str, List[StaCubic]],
                        bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.Load]:
    """
    Convert ElmLod to VeraGrid Load.
    """
    bus = get_injection_bus(elm_id=elmlod.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    p_mw, q_mvar = _extract_load_pq(elmlod=elmlod, logger=logger)

    load = dev.Load(name=elmlod.loc_name or f"Load_{_ref_id(elmlod.ID)}",
                    P=p_mw,
                    Q=q_mvar,
                    active=(int(getattr(elmlod, "outserv", 0) or 0) == 0))

    return bus, load


def _extract_shunt_gb(elmshnt: ElmShnt, logger: Logger) -> Tuple[float, float]:
    """
    Extract (G, B) from an ElmShnt.
    VeraGrid expects:
      - G in MW @ v=1 p.u.
      - B in MVAr @ v=1 p.u.
    PowerFactory DGS provides qcapn as MVAr per step and ncapa as connected steps.
    """
    name = elmshnt.loc_name or _ref_id(elmshnt.ID) or "Shunt"

    # Active losses are not provided in the common DGS export, assume 0.0 MW @ v=1 p.u.
    g_mw: float = 0.0

    # Reactive power per step (MVAr) and connected steps
    q_step: float = _safe_float(getattr(elmshnt, "qcapn", 0.0), 0.0)
    n_on: int = _safe_int(getattr(elmshnt, "ncapa", 1), 1)
    if n_on <= 0:
        n_on = 1

    b_mvar: float = q_step * float(n_on)

    # If total rated MVAr is present in schema, prefer it when non-zero
    qtotn: float = _safe_float(getattr(elmshnt, "qtotn", 0.0), 0.0)
    if qtotn != 0.0:
        b_mvar = qtotn

    if b_mvar == 0.0:
        logger.add_warning(f"Shunt '{name}': computed B=0.0 MVAr (qcapn={q_step}, ncapa={n_on}).")

    return g_mw, b_mvar


def _add_shunt_to_grid(grid: dev.MultiCircuit, bus: dev.Bus, shunt: dev.Shunt, logger: Logger) -> None:
    """
    Add a fixed shunt to the grid with compatibility across MultiCircuit API variants.
    """
    try:
        shunt.bus = bus
    except Exception:
        pass

    try:
        grid.add_shunt(bus=bus, api_obj=shunt)
        return
    except (TypeError, AttributeError):
        pass

    try:
        grid.add_shunt(obj=shunt, bus=bus)
        return
    except (TypeError, AttributeError):
        pass

    try:
        grid.add_shunt(bus, shunt)
        return
    except (TypeError, AttributeError):
        pass

    try:
        grid.add_shunt(obj=shunt)
        return
    except (TypeError, AttributeError):
        pass

    # Fallback: append to 'shunts' list if present
    if hasattr(grid, "shunts"):
        try:
            grid.shunts.append(shunt)
            return
        except Exception as e:
            logger.add_warning(f"Failed to append shunt '{shunt.name}' to grid.shunts: {e}")
            raise

    logger.add_warning(f"Failed to add shunt '{shunt.name}' to grid: no compatible API found.")
    raise AttributeError("No compatible method to add Shunt to MultiCircuit.")


def convert_dgs_to_shunt(elmshnt: ElmShnt,
                         stacubic_dict: Dict[str, List[int]],
                         buses: List[dev.Bus],
                         logger: Logger,
                         cubics_by_objid: Dict[str, List[StaCubic]],
                         bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.Shunt]:
    """
    Convert ElmShnt to VeraGrid fixed Shunt.
    """
    name = elmshnt.loc_name or f"Shunt_{_ref_id(elmshnt.ID)}"

    # Fixed shunts only: if max steps > 1, the device is stepped/controllable in PF
    ncapx: int = _safe_int(getattr(elmshnt, "ncapx", 1), 1)
    if ncapx > 1:
        logger.add_warning(f"ElmShnt '{name}': ncapx={ncapx} indicates stepped shunt. Skipping fixed conversion.")
        raise ValueError("ElmShnt is stepped/controllable (ncapx>1).")

    bus = get_injection_bus(elm_id=elmshnt.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    g_mw, b_mvar = _extract_shunt_gb(elmshnt=elmshnt, logger=logger)

    shunt = dev.Shunt(name=name,
                      G=g_mw,
                      B=b_mvar,
                      active=(_safe_int(getattr(elmshnt, "outserv", 0), 0) == 0))

    return bus, shunt


def _pf_from_pq(p_mw: float, q_mvar: float, default: float = 0.8) -> float:
    """
    Compute power factor from (P, Q).
    """
    try:
        s = math.sqrt(p_mw * p_mw + q_mvar * q_mvar)
        if s <= 0.0:
            return default
        pf = abs(p_mw) / s
        return max(0.0, min(1.0, pf))
    except Exception:
        return default


def _interpret_pu_limit(value: float,
                        baseMVA: float,
                        reference_abs: float,
                        logger: Logger,
                        name: str,
                        field: str) -> float:
    """
    Interpret a DGS limit that might be in p.u. (on Sbase) or in MW/MVAr.
    """
    v = _safe_float(value, default=0.0)

    # If reference is small too, do not guess
    if abs(reference_abs) <= 5.0:
        return v

    # Heuristic: if |value| is small while reference magnitude is clearly in MW/MVAr,
    # then it is very likely a p.u. value and we scale by baseMVA.
    if abs(v) <= 5.0 and baseMVA > 0.0:
        logger.add_warning(f"Generator '{name}': {field}={v} looks like p.u. on Sbase. Interpreting as {v * baseMVA}.")
        return v * baseMVA

    return v


def _add_generator_to_grid(grid: dev.MultiCircuit, bus: dev.Bus, gen: dev.Generator, logger: Logger) -> None:
    """
    Add a generator to the grid with compatibility across MultiCircuit API variants.
    """
    try:
        gen.bus = bus
    except Exception:
        pass

    try:
        grid.add_generator(bus=bus, api_obj=gen)
        return
    except (TypeError, AttributeError):
        pass

    try:
        grid.add_generator(obj=gen, bus=bus)
        return
    except (TypeError, AttributeError):
        pass

    try:
        grid.add_generator(bus, gen)
        return
    except (TypeError, AttributeError):
        pass

    try:
        grid.add_generator(obj=gen)
        return
    except (TypeError, AttributeError):
        pass

    # Fallback: append to 'generators' list if present
    if hasattr(grid, "generators"):
        try:
            grid.generators.append(gen)
            return
        except Exception as e:
            logger.add_warning(f"Failed to append generator '{gen.name}' to grid.generators: {e}")
            raise

    logger.add_warning(f"Failed to add generator '{gen.name}' to grid: no compatible API found.")
    raise AttributeError("No compatible method to add Generator to MultiCircuit.")


def convert_dgs_to_generator(elmsym: ElmSym,
                             stacubic_dict: Dict[str, List[int]],
                             buses: List[dev.Bus],
                             typsym_dict: Dict[str, TypSym],
                             baseMVA: float,
                             logger: Logger,
                             cubics_by_objid: Dict[str, List[StaCubic]],
                             bus_by_term_id: Dict[str, dev.Bus]) -> Tuple[dev.Bus, dev.Generator]:
    """
    Convert ElmSym to VeraGrid Generator.
    """
    name = elmsym.loc_name or f"Gen_{_ref_id(elmsym.ID)}"

    # Skip motors (ElmSym can represent synchronous motors too)
    if _safe_int(getattr(elmsym, "i_mot", 0), 0) != 0:
        logger.add_warning(f"ElmSym '{name}' is marked as motor (i_mot=1). Skipping Generator conversion.")
        raise ValueError("ElmSym is a motor, not a generator.")

    bus = get_injection_bus(elm_id=elmsym.ID,
                            stacubic_dict=stacubic_dict,
                            buses=buses,
                            cubics_by_objid=cubics_by_objid,
                            bus_by_term_id=bus_by_term_id)

    # Resolve type (optional but recommended)
    typsym = typsym_dict.get(elmsym.typ_id, None)
    if typsym is None:
        typsym = typsym_dict.get(_ref_id(elmsym.typ_id), None)

    p_mw = _safe_float(getattr(elmsym, "pgini", 0.0), 0.0)
    q_mvar = _safe_float(getattr(elmsym, "qgini", 0.0), 0.0)

    # Voltage control
    vset = _safe_float(getattr(elmsym, "usetp", 1.0), 1.0)
    is_controlled = (_safe_int(getattr(elmsym, "iv_mode", 0), 0) != 0)

    # Power factor (used mainly when not controlled)
    pf = _safe_float(getattr(elmsym, "cosgini", 0.0), 0.0)
    if pf == 0.0 and typsym is not None:
        pf = _safe_float(getattr(typsym, "cosn", 0.0), 0.0)
    if pf == 0.0:
        pf = _pf_from_pq(p_mw=p_mw, q_mvar=q_mvar, default=0.8)

    # Nominal power
    snom = 9999.0
    if typsym is not None:
        snom = _safe_float(getattr(typsym, "sgn", 9999.0), 9999.0)

    # Limits (q_min/q_max are often in p.u. on Sbase in DGS exports)
    qmin_raw = _safe_float(getattr(elmsym, "q_min", -9999.0), -9999.0)
    qmax_raw = _safe_float(getattr(elmsym, "q_max", 9999.0), 9999.0)

    qmin = _interpret_pu_limit(value=qmin_raw, baseMVA=baseMVA, reference_abs=abs(q_mvar),
                               logger=logger, name=name, field="q_min")
    qmax = _interpret_pu_limit(value=qmax_raw, baseMVA=baseMVA, reference_abs=abs(q_mvar),
                               logger=logger, name=name, field="q_max")

    # Optional P limits if present in schema
    pmin = _safe_float(getattr(elmsym, "Pmin_uc", 0.0), 0.0)
    pmax = _safe_float(getattr(elmsym, "Pmax_uc", 9999.0), 9999.0)

    # Interpret P limits if they look like p.u. too
    pmin = _interpret_pu_limit(value=pmin, baseMVA=baseMVA, reference_abs=abs(p_mw),
                               logger=logger, name=name, field="Pmin_uc")
    pmax = _interpret_pu_limit(value=pmax, baseMVA=baseMVA, reference_abs=abs(p_mw),
                               logger=logger, name=name, field="Pmax_uc")

    gen = dev.Generator(name=name,
                        P=p_mw,
                        power_factor=pf,
                        vset=vset,
                        is_controlled=is_controlled,
                        Qmin=qmin,
                        Qmax=qmax,
                        Snom=snom,
                        active=(_safe_int(getattr(elmsym, "outserv", 0), 0) == 0),
                        Pmin=pmin,
                        Pmax=pmax,
                        Sbase=baseMVA)

    # Optional sequence data from type (best-effort, may not exist in all exports)
    if typsym is not None:
        r1 = _safe_float(getattr(typsym, "rstr", 0.0), 0.0)
        x1 = _safe_float(getattr(typsym, "xd", 0.0), 0.0)

        if r1 != 0.0 or x1 != 0.0:
            gen.R1 = float(r1)
            gen.X1 = float(x1)

    return bus, gen


class DgsCircuit:
    """Strongly-typed container for a PowerFactory DGS file."""

    _ELEMENT_CLASSES: List[Type[DGSElement]] = [
        ChaRef,
        ChaVec,
        ElmAsm,
        ElmCoup,
        ElmFeeder,
        ElmGenstat,
        ElmLne,
        ElmLnesec,
        ElmLod,
        ElmLodlv,
        ElmLodlvp,
        ElmNet,
        ElmShnt,
        ElmSite,
        ElmSubstat,
        ElmSym,
        ElmTerm,
        ElmTr2,
        ElmTr3,
        ElmXnet,
        ElmZone,
        General,
        IntFolder,
        IntGrf,
        IntGrfcon,
        IntGrfnet,
        RelFuse,
        StaCubic,
        StaSwitch,
        TypAsmo,
        TypFuse,
        TypLne,
        TypLod,
        TypSym,
        TypTr2,
        TypTr3,
    ]

    _REGISTRY: Dict[str, Type[DGSElement]] = {cls.element_type: cls for cls in _ELEMENT_CLASSES}

    def __init__(self) -> None:
        """

        """

        self._id_counter = 0

        self.charefs: List[ChaRef] = list()
        self.chavecs: List[ChaVec] = list()
        self.elmasms: List[ElmAsm] = list()
        self.elmcoups: List[ElmCoup] = list()
        self.elmfeeders: List[ElmFeeder] = list()
        self.elmgenstats: List[ElmGenstat] = list()
        self.elmlnes: List[ElmLne] = list()
        self.elmlnesecs: List[ElmLnesec] = list()
        self.elmlods: List[ElmLod] = list()
        self.elmlodlvs: List[ElmLodlv] = list()
        self.elmlodlvps: List[ElmLodlvp] = list()
        self.elmnets: List[ElmNet] = list()
        self.elmshnts: List[ElmShnt] = list()
        self.elmsites: List[ElmSite] = list()
        self.elmsubstats: List[ElmSubstat] = list()
        self.elmsyms: List[ElmSym] = list()
        self.elmterms: List[ElmTerm] = list()
        self.elmtr2s: List[ElmTr2] = list()
        self.elmtr3s: List[ElmTr3] = list()
        self.elmxnets: List[ElmXnet] = list()
        self.elmzones: List[ElmZone] = list()
        self.generals: List[General] = list()
        self.intfolders: List[IntFolder] = list()
        self.intgrfs: List[IntGrf] = list()
        self.intgrfcons: List[IntGrfcon] = list()
        self.intgrfnets: List[IntGrfnet] = list()
        self.relfuses: List[RelFuse] = list()
        self.stacubics: List[StaCubic] = list()
        self.staswitchs: List[StaSwitch] = list()
        self.typasmos: List[TypAsmo] = list()
        self.typfuses: List[TypFuse] = list()
        self.typlnes: List[TypLne] = list()
        self.typlods: List[TypLod] = list()
        self.typsyms: List[TypSym] = list()
        self.typtr2s: List[TypTr2] = list()
        self.typtr3s: List[TypTr3] = list()

        self._CLASS_TO_LIST: Dict[Type[DGSElement], List[DGSElement]] = {
            ChaRef: self.charefs,
            ChaVec: self.chavecs,
            ElmAsm: self.elmasms,
            ElmCoup: self.elmcoups,
            ElmFeeder: self.elmfeeders,
            ElmGenstat: self.elmgenstats,
            ElmLne: self.elmlnes,
            ElmLnesec: self.elmlnesecs,
            ElmLod: self.elmlods,
            ElmLodlv: self.elmlodlvs,
            ElmLodlvp: self.elmlodlvps,
            ElmNet: self.elmnets,
            ElmShnt: self.elmshnts,
            ElmSite: self.elmsites,
            ElmSubstat: self.elmsubstats,
            ElmSym: self.elmsyms,
            ElmTerm: self.elmterms,
            ElmTr2: self.elmtr2s,
            ElmTr3: self.elmtr3s,
            ElmXnet: self.elmxnets,
            ElmZone: self.elmzones,
            General: self.generals,
            IntFolder: self.intfolders,
            IntGrf: self.intgrfs,
            IntGrfcon: self.intgrfcons,
            IntGrfnet: self.intgrfnets,
            RelFuse: self.relfuses,
            StaCubic: self.stacubics,
            StaSwitch: self.staswitchs,
            TypAsmo: self.typasmos,
            TypFuse: self.typfuses,
            TypLne: self.typlnes,
            TypLod: self.typlods,
            TypSym: self.typsyms,
            TypTr2: self.typtr2s,
            TypTr3: self.typtr3s,
        }

    def new_id(self) -> str:
        """

        :return:
        """
        self._id_counter += 1
        return str(self._id_counter)

    def add_element_cubicles(self, element_id: str, dgs_buses: List[ElmTerm]):
        """
        Add cubicles
        :param element_id: Element ID
        :param dgs_buses: list of ElmTerm
        """
        for b in dgs_buses:
            c = StaCubic()
            c.ID = self.new_id()
            c.obj_id = element_id
            c.obj_bus = b.ID
            self.stacubics.append(c)

    def parse_dgs(self, path: str):
        """
        Parse a DGS file and populate the typed lists.
        """
        path = Path(path)
        current_cls: Optional[Type[DGSElement]] = None
        header_map: Dict[str, int] | None = None

        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for raw_line in f:
                line = raw_line.strip()

                if line == "" or line.startswith("*"):
                    # Empty line or comment
                    pass

                elif line.startswith("$$"):
                    # Header line
                    element_type, header_map = parse_header(line)
                    current_cls = self._REGISTRY.get(element_type)

                else:
                    # Data line
                    if current_cls is not None:
                        try:
                            obj = current_cls.parse_line(line=line, header_map=header_map)
                        except (ValueError, IndexError):
                            # Legitimate parse failure (bad data line)
                            obj = None

                        if obj is not None:
                            try:
                                objects_lst = self._CLASS_TO_LIST[current_cls]
                                objects_lst.append(obj)
                            except KeyError:
                                # Programming/configuration error → re-raise
                                raise

    def write_dgs(self, path: str):
        """
        Write the circuit back to a DGS file.
        """
        path = Path(path)

        with path.open("w", encoding="utf-8") as f:
            for cls in self._ELEMENT_CLASSES:
                objects: List[DGSElement] = self._CLASS_TO_LIST[cls]

                if objects:
                    header = "$$" + cls.element_type + ";" + ";".join(
                        f"{p.name}({p.dgs_type})" for p in cls.properties_list
                    )
                    f.write(header + "\n")

                    for obj in objects:
                        f.write(obj.to_dgs_line() + "\n")

                    f.write("\n")

    def from_api(self, study_case_name: str | None = None, pf_path: str = "") -> None:
        """
        Populate this (empty) PfCircuit from an active PowerFactory application.
        Assumes:
        - self is empty (no existing elements)
        - schema registries (_ELEMENT_CLASSES, _CLASS_TO_LIST) are complete
        :param study_case_name: case name if any
        :param pf_path: PowerFactory path
        :return:
        """
        if pf_path == "":
            pf_path = r"C:\Program Files\DIgSILENT\PowerFactory 2025 SP1"
        os.environ["PATH"] = pf_path + ";" + os.environ["PATH"]
        python_folder = f"{sys.version_info.major}.{sys.version_info.minor}"
        module_folder = os.path.join(pf_path, "Python", python_folder)

        if not os.path.exists(module_folder):
            print(f"PowerFactory path for the compatible module not found: {module_folder}")

        # add the pf path to the system path
        sys.path.append(pf_path)
        sys.path.append(module_folder)

        # Obtain PowerFactory application ------------------------------------------------------------------------------
        try:
            import powerfactory as pf
            print(f"loaded PowerFactory version {pf.__version__}")
        except ImportError as e:
            print("PowerFactory Python module not available. "
                  "Ensure this is executed inside a PowerFactory Python environment.", str(e))
            return None

        try:
            app = pf.GetApplicationExt()
        except pf.ExitError as error:
            print(error)
            print('error.code = %d' % error.code)
            return None

        except RuntimeError as e:
            print("Failed to obtain PowerFactory application. "
                  "Ensure PowerFactory is running and a project is open.", str(e))
            return None

        # Activate study case  -----------------------------------------------------------------------------------------

        try:
            project = app.GetActiveProject()
        except RuntimeError as e:
            print("No active PowerFactory project.", str(e))
            return None

        if project is None:
            print("No active PowerFactory project.")
            return None

        # Fetch all study cases
        try:
            cases = project.GetContents("*.IntCase", recursive=True)
        except RuntimeError as e:
            print("Failed to retrieve study cases.", str(e))
            return None

        if not cases:
            print("No study cases found in the project.")
            return None

        active_case = None

        if study_case_name is not None:
            for case in cases:
                if case.loc_name == study_case_name:
                    active_case = case
                    break

            if active_case is None:
                print(f"Study case '{study_case_name}' not found in project.")
                return None

        else:
            # Use currently active case, if any
            try:
                active_case = app.GetActiveStudyCase()
            except RuntimeError:
                active_case = None

            if active_case is None:
                print("No study case is active. Please specify study_case_name explicitly.")
                return None

        # Activate selected case
        try:
            active_case.Activate()
        except RuntimeError as e:
            print(f"Failed to activate study case '{active_case.loc_name}'.", str(e))
            return None

        # Iterate over all known DGSElement subclasses
        for dgs_cls in self._ELEMENT_CLASSES:
            pf_class_name = dgs_cls.element_type

            try:
                pf_objects = app.GetCalcRelevantObjects(f"*.{pf_class_name}")
            except (RuntimeError, AttributeError):
                pf_objects = list()

            if pf_objects:
                target_list = self._CLASS_TO_LIST[dgs_cls]

                for pf_obj in pf_objects:
                    elem = _populate_from_pf_object(pf_obj, dgs_cls)
                    target_list.append(elem)

    def to_veragrid(self, logger: Logger | None = None) -> dev.MultiCircuit:
        """

        :return:
        """
        if logger is None:
            logger = Logger()

        grid = dev.MultiCircuit()

        baseMVA = 100.0

        # --- frequency ---
        if len(self.elmnets) > 0:
            frequency = float(self.elmnets[0].frnom or 50.0)
        else:
            frequency = 50.0

        # StaCubic dictionary
        stacubic_dict: Dict[str, List[int]] = dict()
        for elm in self.stacubics:
            lst = stacubic_dict.get(elm.obj_id, None)
            if lst is None:
                stacubic_dict[elm.obj_id] = [elm.obj_bus]
            else:
                lst.append(elm.obj_bus)

        # StaCubic dictionary (robust)
        cubics_by_objid: Dict[str, List[StaCubic]] = dict()
        for cb in self.stacubics:
            oid = _ref_id(cb.obj_id)
            if oid is None:
                continue
            lst = cubics_by_objid.get(oid, None)
            if lst is None:
                cubics_by_objid[oid] = [cb]
            else:
                lst.append(cb)

        # graphics dictioary
        pos_by_objid: Dict[str, Tuple[float, float]] = dict()
        for g in self.intgrfs:
            pos_by_objid[g.pDataObj] = (float(g.rCenterX or 0.0), float(g.rCenterY or 0.0))

        # Buses
        bus_by_term_id: Dict[str, dev.Bus] = dict()
        for elmterm in self.elmterms:
            bus = convert_dgs_to_bus(elmterm=elmterm, pos_by_objid=pos_by_objid)
            grid.add_bus(obj=bus)
            tid = _ref_id(elmterm.ID)
            if tid is not None:
                bus_by_term_id[tid] = bus

        # Generator types
        typsym_dict: Dict[str, TypSym] = dict()
        for typsym in self.typsyms:
            typsym_dict[typsym.ID] = typsym
            tid = _ref_id(typsym.ID)
            if tid is not None:
                typsym_dict[tid] = typsym

        # Generators
        for elmsym in self.elmsyms:
            try:
                bus, gen = convert_dgs_to_generator(elmsym=elmsym,
                                                    stacubic_dict=stacubic_dict,
                                                    buses=grid.buses,
                                                    typsym_dict=typsym_dict,
                                                    baseMVA=baseMVA,
                                                    logger=logger,
                                                    cubics_by_objid=cubics_by_objid,
                                                    bus_by_term_id=bus_by_term_id)
            except ValueError:
                continue

            _add_generator_to_grid(grid=grid, bus=bus, gen=gen, logger=logger)

        # Loads
        for elmlod in self.elmlods:
            bus, load = convert_dgs_to_load(elmlod=elmlod,
                                            stacubic_dict=stacubic_dict,
                                            buses=grid.buses,
                                            logger=logger,
                                            cubics_by_objid=cubics_by_objid,
                                            bus_by_term_id=bus_by_term_id)

            _add_load_to_grid(grid=grid, bus=bus, load=load, logger=logger)

        # Shunts (fixed)
        for elmshnt in self.elmshnts:
            try:
                bus, shunt = convert_dgs_to_shunt(elmshnt=elmshnt,
                                                  stacubic_dict=stacubic_dict,
                                                  buses=grid.buses,
                                                  logger=logger,
                                                  cubics_by_objid=cubics_by_objid,
                                                  bus_by_term_id=bus_by_term_id)
            except ValueError:
                continue

            _add_shunt_to_grid(grid=grid, bus=bus, shunt=shunt, logger=logger)

        # Loads (LV)
        if len(self.elmlodlvs) > 0 or len(self.elmlodlvps) > 0:
            logger.add_warning("ElmLodlv/ElmLodlvp found but not converted: no P/Q fields available in DGS schema.")

        # Line types
        typlne_dict: Dict[str, dev.SequenceLineType] = dict()
        for typlne in self.typlnes:
            seq_lne = convert_dgs_to_sequence_line(typlne=typlne)
            grid.add_sequence_line(obj=seq_lne)
            typlne_dict[typlne.ID] = seq_lne

        # Transformer types
        typtr2_dict: Dict[str, dev.TransformerType] = dict()
        for typtr2 in self.typtr2s:
            tpe = convert_dgs_to_transformer_type(typtr2=typtr2)
            if hasattr(grid, "add_transformer_type"):
                grid.add_transformer_type(obj=tpe)
            elif hasattr(grid, "add_transformer2w_type"):
                grid.add_transformer2w_type(obj=tpe)
            typtr2_dict[typtr2.ID] = tpe
            tid = _ref_id(typtr2.ID)
            if tid is not None:
                typtr2_dict[tid] = tpe

        # lines
        for elmlne in self.elmlnes:
            line = convert_dgs_to_line(lne=elmlne,
                                       buses=grid.buses,
                                       stacubic_dict=stacubic_dict,
                                       templates_dict=typlne_dict,
                                       freq=frequency,
                                       baseMVA=baseMVA,
                                       logger=logger,
                                       cubics_by_objid=cubics_by_objid,
                                       bus_by_term_id=bus_by_term_id)
            grid.add_line(obj=line, logger=logger)

        # Transformers 2W
        for elmtr2 in self.elmtr2s:
            trafo = convert_dgs_to_transformer(tr2=elmtr2,
                                               buses=grid.buses,
                                               stacubic_dict=stacubic_dict,
                                               templates_dict=typtr2_dict,
                                               freq=frequency,
                                               baseMVA=baseMVA,
                                               logger=logger,
                                               cubics_by_objid=cubics_by_objid,
                                               bus_by_term_id=bus_by_term_id)

            grid.add_transformer2w(obj=trafo)

        return grid


_ID_COUNTER: int = 1


def _new_id() -> str:
    global _ID_COUNTER
    v = _ID_COUNTER
    _ID_COUNTER += 1
    return str(v)


def dgs_to_circuit(path: str) -> dev.MultiCircuit:
    """
    Entry point: read a DGS and return a VeraGrid MultiCircuit.
    """
    dgs = DgsCircuit()
    dgs.parse_dgs(path)
    return dgs.to_veragrid()




# def to_veragrid_old(self) -> dev.MultiCircuit:
#     """
#
#     :return:
#     """
#     grid = dev.MultiCircuit()
#
#     baseMVA = 100.0
#
#     # --- frequency ---
#     if self.elmnets:
#         frequency = float(self.elmnets[0].frnom or 50.0)
#     else:
#         frequency = 50.0
#     w = 2.0 * math.pi * frequency
#
#     # StaCubic dictionary
#     stacubic_dict: Dict[str, List[int]] = dict()
#     for elm in self.stacubics:
#         lst = stacubic_dict.get(elm.obj_id, None)
#         if lst is None:
#             stacubic_dict[elm.obj_id] = [elm.obj_bus]
#         else:
#             lst.append(elm.obj_bus)
#
#     # --- positions from IntGrf (optional) ---
#     pos_by_objid: Dict[str, Tuple[float, float]] = dict()
#     for g in self.intgrfs:
#         obj = _ref_id(g.pDataObj)
#         if obj:
#             pos_by_objid[obj] = (float(g.rCenterX or 0.0), float(g.rCenterY or 0.0))
#
#     # --- dictionaries ---
#     term_by_id = {_ref_id(t.ID): t for t in self.elmterms if _ref_id(t.ID) is not None}
#     typlne_by_id = {_ref_id(t.ID): t for t in self.typlnes if _ref_id(t.ID) is not None}
#     typtr2_by_id = {_ref_id(t.ID): t for t in self.typtr2s if _ref_id(t.ID) is not None}
#     typsym_by_id = {_ref_id(t.ID): t for t in self.typsyms if _ref_id(t.ID) is not None}
#
#     cubics_by_objid = {}
#     for c in self.stacubics:
#         obj = _ref_id(c.obj_id)
#         if not obj:
#             continue
#         cubics_by_objid.setdefault(obj, []).append(c)
#
#     # --- add buses ---
#     busobj_by_termid = {}
#     for t in self.elmterms:
#         tid = _ref_id(t.ID)
#         if not tid:
#             continue
#
#         x, y = pos_by_objid.get(tid, (0.0, 0.0))
#         bus = dev.Bus(
#             name=t.loc_name or f"Bus_{tid}",
#             Vnom=float(t.uknom or 0.0),
#             vmin=0.9,
#             vmax=1.1,
#             xpos=float(x),
#             ypos=float(-y),
#             active=(int(t.outserv or 0) == 0),
#         )
#         grid.add_bus(bus)
#         busobj_by_termid[tid] = bus
#
#     # --- ElmXnet (external grid) ---
#     for xnet in self.elmxnets:
#         eid = _ref_id(xnet.ID)
#         terms = get_terminal_ids(eid)
#         if not terms:
#             warn(f"ElmXnet {eid} has no StaCubic -> cannot connect")
#             continue
#         bus = busobj_by_termid.get(terms[0])
#         if bus is None:
#             warn(f"ElmXnet {eid} terminal {terms[0]} not found in ElmTerm")
#             continue
#
#         bustp = (xnet.bustp or "").strip()
#         # a veces viene como bytes en otros loaders; aquí debería ser str
#         if bustp == "SL":
#             bus.is_slack = True
#         elif bustp == "PV":
#             gen = dev.ExternalGrid(
#                 name=xnet.loc_name or f"PV_{eid}",
#                 P=float(xnet.pgini or 0.0),
#                 vset=float(xnet.usetp or 1.0),
#                 Qmin=-9999, Qmax=9999,
#                 Snom=9999,
#             )
#             grid.add_generator(bus, gen)
#         elif bustp == "PQ":
#             load = dev.Load(
#                 name=xnet.loc_name or f"PQ_{eid}",
#                 P=float(xnet.pgini or 0.0),
#                 Q=float(xnet.qgini or 0.0),
#             )
#             grid.add_load(bus, load)
#
#     # --- lines ---
#     for l in self.elmlnes:
#         eid = _ref_id(l.ID)
#         type_id = _ref_id(l.typ_id)
#         tpe = typlne_by_id.get(type_id)
#         if tpe is None:
#             warn(f"Line {eid} type {type_id} not found")
#             continue
#
#         terms = get_terminal_ids(eid)
#         if len(terms) < 2:
#             warn(f"Line {eid} has <2 terminals via StaCubic")
#             continue
#
#         bus_from = busobj_by_termid.get(terms[0])
#         bus_to = busobj_by_termid.get(terms[1])
#         if bus_from is None or bus_to is None:
#             warn(f"Line {eid} terminals not found in buses: {terms}")
#             continue
#
#         length_km = float(l.dline or 0.0)
#
#         R = float(tpe.rline or 0.0) * length_km
#         X = float(tpe.xline or 0.0) * length_km
#
#         # susceptance in Siemens
#         B_S = 0.0
#         if getattr(tpe, "cline", None) is not None:
#             B_S = float(tpe.cline or 0.0) * length_km * w * 1e-6
#         elif getattr(tpe, "bline", None) is not None:
#             B_S = float(tpe.bline or 0.0) * length_km * 1e-6
#
#         Vbase = float(tpe.uline or bus_from.Vnom or 0.0)
#         if Vbase <= 0:
#             warn(f"Line {eid} has invalid Vbase")
#             continue
#
#         zbase = (Vbase ** 2) / baseMVA
#         ybase = 1.0 / zbase
#
#         r_pu = R / zbase
#         x_pu = X / zbase
#         b_pu = B_S / ybase
#
#         Irated = float(tpe.sline or 0.0)  # kA
#         Smax = Irated * Vbase  # MVA
#
#         line = dev.Line(
#             bus_from=bus_from,
#             bus_to=bus_to,
#             name=l.loc_name or f"Line_{eid}",
#             r=r_pu,
#             x=x_pu,
#             b=b_pu,
#             rate=Smax,
#             active=(int(l.outserv or 0) == 0),
#             mttf=0,
#             mttr=0,
#         )
#         grid.add_line(line)
#
#     # --- transformers 2W ---
#     for tr in self.elmtr2s:
#         eid = _ref_id(tr.ID)
#         type_id = _ref_id(tr.typ_id)
#         tpe = typtr2_by_id.get(type_id)
#         if tpe is None:
#             warn(f"Transformer {eid} type {type_id} not found")
#             continue
#
#         terms = get_terminal_ids(eid)
#         if len(terms) < 2:
#             warn(f"Transformer {eid} has <2 terminals via StaCubic")
#             continue
#
#         bus_from = busobj_by_termid.get(terms[0])
#         bus_to = busobj_by_termid.get(terms[1])
#         if bus_from is None or bus_to is None:
#             warn(f"Transformer {eid} terminals not found in buses: {terms}")
#             continue
#
#         Snom = float(tpe.strn or 0.0)
#         if Snom <= 0:
#             Snom = 9999.0
#
#         tr_type = dev.TransformerType(
#             hv_nominal_voltage=float(tpe.utrn_h or 0.0),
#             lv_nominal_voltage=float(tpe.utrn_l or 0.0),
#             nominal_power=Snom,
#             copper_losses=float(tpe.pcutr or 0.0),
#             iron_losses=float(tpe.pfe or 0.0),
#             no_load_current=float(tpe.curmg or 0.0),
#             short_circuit_voltage=float(tpe.uktr or 0.0),
#             gr_hv1=0.5,
#             gx_hv1=0.5,
#         )
#
#         Zs, Zsh = tr_type.get_impedances(
#             VH=float(tpe.utrn_h or 0.0),
#             VL=float(tpe.utrn_l or 0.0),
#             Sbase=baseMVA,
#         )
#
#         Ysh = (1.0 / Zsh) if Zsh not in (0, 0j) else 0j
#
#         trafo = dev.Transformer2W(
#             bus_from=bus_from,
#             bus_to=bus_to,
#             name=tr.loc_name or f"Tr2_{eid}",
#             r=Zs.real,
#             x=Zs.imag,
#             g=Ysh.real,
#             b=Ysh.imag,
#             rate=Snom,
#             tap_module=1.0,
#             tap_phase=0.0,
#             active=(int(tr.outserv or 0) == 0),
#             mttf=0,
#             mttr=0,
#         )
#         grid.add_transformer2w(trafo)
#
#     # --- loads ---
#     for ld in self.elmlods:
#         eid = _ref_id(ld.ID)
#         terms = get_terminal_ids(eid)
#         if not terms:
#             warn(f"Load {eid} has no terminal via StaCubic")
#             continue
#         bus = busobj_by_termid.get(terms[0])
#         if bus is None:
#             warn(f"Load {eid} terminal {terms[0]} not found in ElmTerm")
#             continue
#
#         scale = float(ld.scale0 or 1.0)
#         load = dev.Load(
#             name=ld.loc_name or f"Load_{eid}",
#             P=float(ld.plini or 0.0) * scale,
#             Q=float(ld.qlini or 0.0) * scale,
#         )
#         grid.add_load(bus, load)
#
#     # --- shunts ---
#     for sh in self.elmshnts:
#         eid = _ref_id(sh.ID)
#         terms = get_terminal_ids(eid)
#         if not terms:
#             warn(f"Shunt {eid} has no terminal via StaCubic")
#             continue
#         bus = busobj_by_termid.get(terms[0])
#         if bus is None:
#             warn(f"Shunt {eid} terminal {terms[0]} not found in ElmTerm")
#             continue
#
#         # replico tu dgs_parser: b = qcapn o qtotn "tal cual"
#         b_val = float(sh.qcapn or sh.qtotn or 0.0)
#         shunt = dev.Shunt(name=sh.loc_name or f"Shunt_{eid}", B=b_val)
#         grid.add_shunt(bus, shunt)
#
#
#     return grid
