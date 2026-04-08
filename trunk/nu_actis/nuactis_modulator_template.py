# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Utils.Symbolic import symbolic as sym
from VeraGridEngine.Devices.Dynamic.rms_template import RmsModelTemplate
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import DeviceType


def get_nuactis_modulator_rms_template(vf: VarFactory, name: str = "NuActis_Modulator") -> RmsModelTemplate:
    templ = RmsModelTemplate()
    templ.tpe = DeviceType.NoDevice
    templ.name = name

    pmd = vf.add_var("Pmd_" + name)
    pmq = vf.add_var("Pmq_" + name)
    md = vf.add_var("md_" + name)
    mq = vf.add_var("mq_" + name)
    m_mag = vf.add_var("m_mag_" + name)
    k_lim = vf.add_var("k_lim_" + name)

    mod_m_max = vf.add_var("Modulator__m_max_" + name)
    mod_eps = vf.add_var("Modulator__eps_" + name)

    one = sym.Const(1.0)

    modulator = Block(
        algebraic_eqs=[
            m_mag - sym.sqrt((pmd * pmd) + (pmq * pmq) + mod_eps),
            k_lim - (one + (((mod_m_max / (m_mag + mod_eps)) - one) * sym.heaviside(one - (mod_m_max / (m_mag + mod_eps))))),
            md - (pmd * k_lim),
            mq - (pmq * k_lim),
        ],
        algebraic_vars=[m_mag, k_lim, md, mq],
        in_vars=[pmd, pmq],
        out_vars=[md, mq],
        name="NuActis_Modulator",
    )

    modulator.event_dict = {
        mod_m_max: vf.add_const(1.1, name="m_max"),
        mod_eps: vf.add_const(1e-6, name="eps"),
    }

    modulator.init_eqs = {
        m_mag: sym.sqrt((pmd * pmd) + (pmq * pmq) + mod_eps),
        k_lim: (one + (((mod_m_max / (m_mag + mod_eps)) - one) * sym.heaviside(one - (mod_m_max / (m_mag + mod_eps))))),
        md: pmd * k_lim,
        mq: pmq * k_lim,
    }

    templ.block = modulator
    templ.block.name = name

    return templ


def get_template(vf: VarFactory, name: str | None = None) -> RmsModelTemplate:
    return get_nuactis_modulator_rms_template(vf=vf, name="NuActis_Modulator" if name is None else name)
