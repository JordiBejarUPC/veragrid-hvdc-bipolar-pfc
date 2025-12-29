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
from VeraGridEngine.enumerations import WindingType
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


def _ref_id(x):
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
    :param cubics_by_objid:
    :param bus_by_term_id:
    :return:
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 2:
        return bus_by_term_id[term_ids[0]], bus_by_term_id[term_ids[1]]

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
    :param cubics_by_objid:
    :param bus_by_term_id:
    :return:
    """
    # Prefer robust mapping using StaCubic.fold_id -> ElmTerm.ID -> Bus
    term_ids = get_terminal_ids(element_id=elm_id, cubics_by_objid=cubics_by_objid)
    if len(term_ids) == 1:
        return bus_by_term_id[term_ids[0]]

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
        Vnom=float(elmterm.uknom),
        vmin=0.9,
        vmax=1.1,
        xpos=float(x),
        ypos=float(-y),
        active=(int(elmterm.outserv or 0) == 0),
    )

    return bus


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
        CnF=typlne.cline * 1000,
        R0=typlne.rline0,
        X0=typlne.xline0,
        B0=typlne.bline0,
        CnF0=typlne.cline0 * 1000,
        Vnom=typlne.uline,
        Imax=typlne.sline,
        use_conductance=typlne.cline != 0.0
    )

    return elm


def _convert_pf_tr2_connection(code: str) -> WindingType | None:
    """
    Convert a PowerFactory 2-character transformer connection code to VeraGrid WindingType.
    If the code is unknown, return None and let defaults apply.
    """
    if code is None:
        return None

    c = str(code).strip().upper()
    if c == "":
        return None

    # Common PowerFactory 2-char winding codes in DGS: Y, YN, D, Z, ZN
    conversion_dict: Dict[str, WindingType] = {
        "D": WindingType.Delta,
        "Y": WindingType.NeutralStar,
        "YN": WindingType.GroundedStar,
        "Z": WindingType.ZigZag,
        "ZN": WindingType.ZigZag,
    }

    if c in conversion_dict:
        return conversion_dict[c]
    elif c.startswith("Y"):
        # Defensive fallback: any "Y*" treated as star (prefer grounded if it contains N)
        if "N" in c:
            return WindingType.GroundedStar
        return WindingType.NeutralStar
    else:
        return None


def convert_dgs_to_transformer_type(typtr2: TypTr2) -> dev.TransformerType:
    """
    Convert a TypTr2 to TransformerType
    :param typtr2: TypTr2
    :return: TransformerType
    """
    tpe = dev.TransformerType(hv_nominal_voltage=float(typtr2.utrn_h),
                              lv_nominal_voltage=float(typtr2.utrn_l),
                              nominal_power=float(typtr2.strn),
                              copper_losses=float(typtr2.pcutr),
                              iron_losses=float(typtr2.pfe),
                              no_load_current=float(typtr2.curmg),
                              short_circuit_voltage=float(typtr2.uktr),
                              gr_hv1=0.5,
                              gx_hv1=0.5,
                              name=typtr2.loc_name)

    conn_hv = _convert_pf_tr2_connection(typtr2.tr2cn_h)
    conn_lv = _convert_pf_tr2_connection(typtr2.tr2cn_l)

    if conn_hv is not None:
        tpe.conn_hv = conn_hv

    if conn_lv is not None:
        tpe.conn_lv = conn_lv

    return tpe


def _order_hv_lv(bus_a: dev.Bus, bus_b: dev.Bus, logger: Logger, tr_name: str) -> Tuple[dev.Bus, dev.Bus]:
    """
    Order two buses as (HV, LV) based on nominal voltage.
    If voltages are equal or undefined, keep the original order and warn.
    """
    va = float(bus_a.Vnom)
    vb = float(bus_b.Vnom)

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
                              # nominal_power=float(template.nominal_power or 0.001),
                              # copper_losses=float(template.copper_losses or 0.0),
                              # iron_losses=float(template.iron_losses or 0.0),
                              # no_load_current=float(template.no_load_current or 0.0),
                              # short_circuit_voltage=float(template.short_circuit_voltage or 0.0),
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
    if x is None:
        return default
    return float(x)


def _safe_int(x, default: int = 0) -> int:
    """
    Convert a value to int safely.
    """
    if x is None:
        return default
    return int(x)


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
    p = _safe_float(elmlod.plini, 0.0)
    q = _safe_float(elmlod.qlini, 0.0)

    # Fallback: S + cos(phi)
    if p == 0.0 and q == 0.0:
        s = _safe_float(elmlod.slini, 0.0)
        cosphi = _safe_float(elmlod.coslini, 0.0)

        if s != 0.0 and cosphi != 0.0:
            cosphi = max(min(cosphi, 1.0), -1.0)
            p = s * cosphi
            sinphi = math.sqrt(max(0.0, 1.0 - cosphi * cosphi))
            q = s * sinphi
            logger.add_warning(f"Load '{name}': P/Q not provided, derived from slini/coslini.")

    # Apply scaling
    scale = _get_scale_factor(scale0=elmlod.scale0, logger=logger, name=name)
    p *= scale
    q *= scale

    return p, q


def _add_load_to_grid(grid: dev.MultiCircuit, bus: dev.Bus, load: dev.Load, logger: Logger) -> None:
    """
    Add a load to the grid with compatibility across MultiCircuit API variants.
    """
    load.bus = bus
    grid.add_load(bus=bus, api_obj=load)
    return


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
                    active=(int(elmlod.outserv or 0) == 0))

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
    q_step: float = _safe_float(elmshnt.qcapn, 0.0)
    n_on: int = _safe_int(elmshnt.ncapa, 1)

    if n_on <= 0:
        n_on = 1

    b_mvar: float = q_step * float(n_on)

    # If total rated MVAr is present in schema, prefer it when non-zero
    qtotn: float = _safe_float(elmshnt.qtotn, 0.0)
    if qtotn != 0.0:
        b_mvar = qtotn

    if b_mvar == 0.0:
        logger.add_warning(f"Shunt '{name}': computed B=0.0 MVAr (qcapn={q_step}, ncapa={n_on}).")

    return g_mw, b_mvar


def _add_shunt_to_grid(grid: dev.MultiCircuit, bus: dev.Bus, shunt: dev.Shunt, logger: Logger) -> None:
    """
    Add a fixed shunt to the grid with compatibility across MultiCircuit API variants.
    """
    shunt.bus = bus
    grid.add_shunt(bus=bus, api_obj=shunt)
    return


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
    ncapx: int = _safe_int(elmshnt.ncapx, 1)
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
                      active=(_safe_int(elmshnt.outserv, 0) == 0))

    return bus, shunt


def _pf_from_pq(p_mw: float, q_mvar: float, default: float = 0.8) -> float:
    """
    Compute power factor from (P, Q).
    """
    s = math.sqrt(p_mw * p_mw + q_mvar * q_mvar)
    if s <= 0.0:
        return default
    pf = abs(p_mw) / s
    return max(0.0, min(1.0, pf))


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
    gen.bus = bus
    grid.add_generator(bus=bus, api_obj=gen)
    return


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
    if _safe_int(elmsym.i_mot, 0) != 0:
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

    p_mw = _safe_float(elmsym.pgini, 0.0)
    q_mvar = _safe_float(elmsym.qgini, 0.0)

    # Voltage control
    vset = _safe_float(elmsym.usetp, 1.0)
    is_controlled = (_safe_int(elmsym.iv_mode, 0) != 0)

    # Power factor (used mainly when not controlled)
    pf = _safe_float(elmsym.cosgini, 0.0)
    if pf == 0.0 and typsym is not None:
        pf = _safe_float(typsym.cosn, 0.0)
    if pf == 0.0:
        pf = _pf_from_pq(p_mw=p_mw, q_mvar=q_mvar, default=0.8)

    # Nominal power
    snom = 9999.0
    if typsym is not None:
        snom = _safe_float(typsym.sgn, 9999.0)

    # Limits (q_min/q_max are often in p.u. on Sbase in DGS exports)
    qmin_raw = _safe_float(elmsym.q_min, -9999.0)
    qmax_raw = _safe_float(elmsym.q_max, 9999.0)

    qmin = _interpret_pu_limit(value=qmin_raw, baseMVA=baseMVA, reference_abs=abs(q_mvar),
                               logger=logger, name=name, field="q_min")
    qmax = _interpret_pu_limit(value=qmax_raw, baseMVA=baseMVA, reference_abs=abs(q_mvar),
                               logger=logger, name=name, field="q_max")

    # Optional P limits if present in schema
    pmin = _safe_float(elmsym.Pmin_uc, 0.0)
    pmax = _safe_float(elmsym.Pmax_uc, 9999.0)

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
                        active=(_safe_int(elmsym.outserv, 0) == 0),
                        Pmin=pmin,
                        Pmax=pmax,
                        Sbase=baseMVA)

    # Optional sequence data from type (best-effort, may not exist in all exports)
    if typsym is not None:
        r1 = _safe_float(typsym.rstr, 0.0)
        x1 = _safe_float(typsym.xd, 0.0)

        if r1 != 0.0 or x1 != 0.0:
            gen.R1 = float(r1)
            gen.X1 = float(x1)

    return bus, gen


def to_veragrid(self, logger: Logger | None = None) -> dev.MultiCircuit:
    """

    :param self:
    :param logger:
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
        pos_by_objid[g.pDataObj] = (float(g.rCenterX), float(g.rCenterY))

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
        bus, gen = convert_dgs_to_generator(elmsym=elmsym,
                                            stacubic_dict=stacubic_dict,
                                            buses=grid.buses,
                                            typsym_dict=typsym_dict,
                                            baseMVA=baseMVA,
                                            logger=logger,
                                            cubics_by_objid=cubics_by_objid,
                                            bus_by_term_id=bus_by_term_id)

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
        bus, shunt = convert_dgs_to_shunt(elmshnt=elmshnt,
                                          stacubic_dict=stacubic_dict,
                                          buses=grid.buses,
                                          logger=logger,
                                          cubics_by_objid=cubics_by_objid,
                                          bus_by_term_id=bus_by_term_id)

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
        grid.add_transformer_type(obj=tpe)
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

