# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from enum import Enum

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory

from VeraGridEngine.Templates.international_standards.templates.ac1a import get_template as build_ac1a_template
from VeraGridEngine.Templates.international_standards.templates.ac1c import get_template as build_ac1c_template
from VeraGridEngine.Templates.international_standards.templates.ac6a import get_template as build_ac6a_template
from VeraGridEngine.Templates.international_standards.templates.ac6c import get_template as build_ac6c_template
from VeraGridEngine.Templates.international_standards.templates.ac7b import get_template as build_ac7b_template
from VeraGridEngine.Templates.international_standards.templates.ac7c import get_template as build_ac7c_template
from VeraGridEngine.Templates.international_standards.templates.ac8b import get_template as build_ac8b_template
from VeraGridEngine.Templates.international_standards.templates.ac8c import get_template as build_ac8c_template
from VeraGridEngine.Templates.international_standards.templates.bbsex1 import get_template as build_bbsex1_template
from VeraGridEngine.Templates.international_standards.templates.besscbcurrentsourcenoplantcontrol import get_template as build_besscbcurrentsourcenoplantcontrol_template
from VeraGridEngine.Templates.international_standards.templates.dc1a import get_template as build_dc1a_template
from VeraGridEngine.Templates.international_standards.templates.dc1c import get_template as build_dc1c_template
from VeraGridEngine.Templates.international_standards.templates.exac1 import get_template as build_exac1_template
from VeraGridEngine.Templates.international_standards.templates.govhydro4 import get_template as build_govhydro4_template
from VeraGridEngine.Templates.international_standards.templates.govsteam1 import get_template as build_govsteam1_template
from VeraGridEngine.Templates.international_standards.templates.govsteameu import get_template as build_govsteameu_template
from VeraGridEngine.Templates.international_standards.templates.ieeeg1 import get_template as build_ieeeg1_template
from VeraGridEngine.Templates.international_standards.templates.ieeeg2 import get_template as build_ieeeg2_template
from VeraGridEngine.Templates.international_standards.templates.ieeet1 import get_template as build_ieeet1_template
from VeraGridEngine.Templates.international_standards.templates.ieeex2 import get_template as build_ieeex2_template
from VeraGridEngine.Templates.international_standards.templates.ieex2a import get_template as build_ieex2a_template
from VeraGridEngine.Templates.international_standards.templates.maxex2 import get_template as build_maxex2_template
from VeraGridEngine.Templates.international_standards.templates.oel2c import get_template as build_oel2c_template
from VeraGridEngine.Templates.international_standards.templates.oel3c import get_template as build_oel3c_template
from VeraGridEngine.Templates.international_standards.templates.oel4c import get_template as build_oel4c_template
from VeraGridEngine.Templates.international_standards.templates.oel5c import get_template as build_oel5c_template
from VeraGridEngine.Templates.international_standards.templates.pss1aomega import get_template as build_pss1aomega_template
from VeraGridEngine.Templates.international_standards.templates.pss1apgen import get_template as build_pss1apgen_template
from VeraGridEngine.Templates.international_standards.templates.pss2a import get_template as build_pss2a_template
from VeraGridEngine.Templates.international_standards.templates.pss2b import get_template as build_pss2b_template
from VeraGridEngine.Templates.international_standards.templates.pss2c import get_template as build_pss2c_template
from VeraGridEngine.Templates.international_standards.templates.pss3b import get_template as build_pss3b_template
from VeraGridEngine.Templates.international_standards.templates.pss3c import get_template as build_pss3c_template
from VeraGridEngine.Templates.international_standards.templates.pss6c import get_template as build_pss6c_template
from VeraGridEngine.Templates.international_standards.templates.psskundur import get_template as build_psskundur_template
from VeraGridEngine.Templates.international_standards.templates.pvcurrentsourcebnoplantcontrol import get_template as build_pvcurrentsourcebnoplantcontrol_template
from VeraGridEngine.Templates.international_standards.templates.pvvoltagesourceanoplantcontrol import get_template as build_pvvoltagesourceanoplantcontrol_template
from VeraGridEngine.Templates.international_standards.templates.pvvoltagesourcebnoplantcontrol import get_template as build_pvvoltagesourcebnoplantcontrol_template
from VeraGridEngine.Templates.international_standards.templates.reecb import get_template as build_reecb_template
from VeraGridEngine.Templates.international_standards.templates.reecc import get_template as build_reecc_template
from VeraGridEngine.Templates.international_standards.templates.regcbcs import get_template as build_regcbcs_template
from VeraGridEngine.Templates.international_standards.templates.repca import get_template as build_repca_template
from VeraGridEngine.Templates.international_standards.templates.scl1c import get_template as build_scl1c_template
from VeraGridEngine.Templates.international_standards.templates.scl2c import get_template as build_scl2c_template
from VeraGridEngine.Templates.international_standards.templates.scrx import get_template as build_scrx_template
from VeraGridEngine.Templates.international_standards.templates.sexs import get_template as build_sexs_template
from VeraGridEngine.Templates.international_standards.templates.st1a import get_template as build_st1a_template
from VeraGridEngine.Templates.international_standards.templates.st1c import get_template as build_st1c_template
from VeraGridEngine.Templates.international_standards.templates.st4b import get_template as build_st4b_template
from VeraGridEngine.Templates.international_standards.templates.st4c import get_template as build_st4c_template
from VeraGridEngine.Templates.international_standards.templates.st5b import get_template as build_st5b_template
from VeraGridEngine.Templates.international_standards.templates.st5c import get_template as build_st5c_template
from VeraGridEngine.Templates.international_standards.templates.st6b import get_template as build_st6b_template
from VeraGridEngine.Templates.international_standards.templates.st6c import get_template as build_st6c_template
from VeraGridEngine.Templates.international_standards.templates.st7b import get_template as build_st7b_template
from VeraGridEngine.Templates.international_standards.templates.st7c import get_template as build_st7c_template
from VeraGridEngine.Templates.international_standards.templates.st9c import get_template as build_st9c_template
from VeraGridEngine.Templates.international_standards.templates.tgov3 import get_template as build_tgov3_template
from VeraGridEngine.Templates.international_standards.templates.uel1 import get_template as build_uel1_template
from VeraGridEngine.Templates.international_standards.templates.uel2c import get_template as build_uel2c_template
from VeraGridEngine.Templates.international_standards.templates.vrkundur import get_template as build_vrkundur_template
from VeraGridEngine.Templates.international_standards.templates.wpp4bcurrentsource2020 import get_template as build_wpp4bcurrentsource2020_template
from VeraGridEngine.Templates.international_standards.templates.wt4acurrentsource import get_template as build_wt4acurrentsource_template
from VeraGridEngine.Templates.international_standards.templates.wt4acurrentsource2020 import get_template as build_wt4acurrentsource2020_template
from VeraGridEngine.Templates.international_standards.templates.wt4bcurrentsource2020 import get_template as build_wt4bcurrentsource2020_template
from VeraGridEngine.Templates.international_standards.templates.wt4bcurrentsource import get_template as build_wt4bcurrentsource_template
from VeraGridEngine.Templates.international_standards.templates.wt4injector import get_template as build_wt4injector_template
from VeraGridEngine.Templates.international_standards.templates.wtg4acurrentsource import get_template as build_wtg4acurrentsource_template
from VeraGridEngine.Templates.international_standards.templates.wtg4bcurrentsource import get_template as build_wtg4bcurrentsource_template
from VeraGridEngine.Templates.international_standards.templates.ieeevc_1981 import get_template as build_ieeevc_1981_template
from VeraGridEngine.Templates.international_standards.templates.esdc2a import get_template as build_esdc2a_template
from VeraGridEngine.Templates.international_standards.templates.frqtpa import get_template as build_frqtpa_template
from VeraGridEngine.Templates.international_standards.templates.vtgtpa import get_template as build_vtgtpa_template
from VeraGridEngine.Templates.international_standards.templates.cimtr1 import get_template as build_cimtr1_template
from VeraGridEngine.Templates.international_standards.templates.cimw import get_template as build_cimw_template
from VeraGridEngine.Templates.international_standards.templates.gensal import get_template as build_gensal_template
from VeraGridEngine.Templates.international_standards.templates.genrou import get_template as build_genrou_template
from VeraGridEngine.Templates.international_standards.templates.ggov1 import get_template as build_ggov1_template
from VeraGridEngine.Templates.international_standards.templates.hygov import get_template as build_hygov_template
from VeraGridEngine.Templates.international_standards.templates.ieel import get_template as build_ieel_template
from VeraGridEngine.Templates.international_standards.templates.tgov1 import get_template as build_tgov1_template


class InternationalStandardModel(Enum):
    """Identify every supported international-standard dynamic model."""

    AC1A = 'ac1a'
    AC1C = 'ac1c'
    AC6A = 'ac6a'
    AC6C = 'ac6c'
    AC7B = 'ac7b'
    AC7C = 'ac7c'
    AC8B = 'ac8b'
    AC8C = 'ac8c'
    BBSEX1 = 'bbsex1'
    BESSCBCURRENTSOURCENOPLANTCONTROL = 'besscbcurrentsourcenoplantcontrol'
    DC1A = 'dc1a'
    DC1C = 'dc1c'
    EXAC1 = 'exac1'
    GOVHYDRO4 = 'govhydro4'
    GOVSTEAM1 = 'govsteam1'
    GOVSTEAMEU = 'govsteameu'
    IEEEG1 = 'ieeeg1'
    IEEEG2 = 'ieeeg2'
    IEEET1 = 'ieeet1'
    IEEEX2 = 'ieeex2'
    IEEX2A = 'ieex2a'
    MAXEX2 = 'maxex2'
    OEL2C = 'oel2c'
    OEL3C = 'oel3c'
    OEL4C = 'oel4c'
    OEL5C = 'oel5c'
    PSS1AOMEGA = 'pss1aomega'
    PSS1APGEN = 'pss1apgen'
    PSS2A = 'pss2a'
    PSS2B = 'pss2b'
    PSS2C = 'pss2c'
    PSS3B = 'pss3b'
    PSS3C = 'pss3c'
    PSS6C = 'pss6c'
    PSSKUNDUR = 'psskundur'
    PVCURRENTSOURCEBNOPLANTCONTROL = 'pvcurrentsourcebnoplantcontrol'
    PVVOLTAGESOURCEANOPLANTCONTROL = 'pvvoltagesourceanoplantcontrol'
    PVVOLTAGESOURCEBNOPLANTCONTROL = 'pvvoltagesourcebnoplantcontrol'
    REECB = 'reecb'
    REECC = 'reecc'
    REGCBCS = 'regcbcs'
    REPCA = 'repca'
    SCL1C = 'scl1c'
    SCL2C = 'scl2c'
    SCRX = 'scrx'
    SEXS = 'sexs'
    ST1A = 'st1a'
    ST1C = 'st1c'
    ST4B = 'st4b'
    ST4C = 'st4c'
    ST5B = 'st5b'
    ST5C = 'st5c'
    ST6B = 'st6b'
    ST6C = 'st6c'
    ST7B = 'st7b'
    ST7C = 'st7c'
    ST9C = 'st9c'
    TGOV3 = 'tgov3'
    UEL1 = 'uel1'
    UEL2C = 'uel2c'
    VRKUNDUR = 'vrkundur'
    WPP4BCURRENTSOURCE2020 = 'wpp4bcurrentsource2020'
    WT4ACURRENTSOURCE = 'wt4acurrentsource'
    WT4ACURRENTSOURCE2020 = 'wt4acurrentsource2020'
    WT4BCURRENTSOURCE2020 = 'wt4bcurrentsource2020'
    WT4BCURRENTSOURCE = 'wt4bcurrentsource'
    WT4INJECTOR = 'wt4injector'
    WTG4ACURRENTSOURCE = 'wtg4acurrentsource'
    WTG4BCURRENTSOURCE = 'wtg4bcurrentsource'
    IEEEVC_1981 = 'ieeevc_1981'
    ESDC2A = 'esdc2a'
    FRQTPA = 'frqtpa'
    VTGTPA = 'vtgtpa'
    CIMTR1 = 'cimtr1'
    CIMW = 'cimw'
    GENSAL = 'gensal'
    GENROU = 'genrou'
    GGOV1 = 'ggov1'
    HYGOV = 'hygov'
    IEEL = 'ieel'
    TGOV1 = 'tgov1'


def parse_international_standard_model(module_name: str) -> InternationalStandardModel | None:
    """
    Parse one serialized module name into the model enumeration.

    :param module_name: Module name stored in the standards manifest.
    :type module_name: str
    :return: Matching model enumeration, or ``None`` for an unknown name.
    :rtype: InternationalStandardModel | None
    """
    model: InternationalStandardModel | None

    # Convert the serialized manifest boundary once so runtime comparisons stay enum-safe.
    try:
        model = InternationalStandardModel(module_name)
    except ValueError:
        model = None

    return model


def build_international_standard_template(
        model: InternationalStandardModel,
        vf: VarFactory,
        name: str | None = None,
) -> EmtModelTemplate:
    """
    Materialize one international-standard dynamic model without function pointers.

    :param model: Enumerated dynamic model to materialize.
    :type model: InternationalStandardModel
    :param vf: Variable factory that owns the symbolic variables.
    :type vf: VarFactory
    :param name: Optional runtime instance name.
    :type name: str | None
    :return: Materialized EMT-compatible dynamic template.
    :rtype: EmtModelTemplate
    """
    template: EmtModelTemplate

    # Dispatch explicitly so every supported state is visible and statically imported.
    if model == InternationalStandardModel.AC1A:
        template = build_ac1a_template(vf=vf, name=name)
    elif model == InternationalStandardModel.AC1C:
        template = build_ac1c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.AC6A:
        template = build_ac6a_template(vf=vf, name=name)
    elif model == InternationalStandardModel.AC6C:
        template = build_ac6c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.AC7B:
        template = build_ac7b_template(vf=vf, name=name)
    elif model == InternationalStandardModel.AC7C:
        template = build_ac7c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.AC8B:
        template = build_ac8b_template(vf=vf, name=name)
    elif model == InternationalStandardModel.AC8C:
        template = build_ac8c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.BBSEX1:
        template = build_bbsex1_template(vf=vf, name=name)
    elif model == InternationalStandardModel.BESSCBCURRENTSOURCENOPLANTCONTROL:
        template = build_besscbcurrentsourcenoplantcontrol_template(vf=vf, name=name)
    elif model == InternationalStandardModel.DC1A:
        template = build_dc1a_template(vf=vf, name=name)
    elif model == InternationalStandardModel.DC1C:
        template = build_dc1c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.EXAC1:
        template = build_exac1_template(vf=vf, name=name)
    elif model == InternationalStandardModel.GOVHYDRO4:
        template = build_govhydro4_template(vf=vf, name=name)
    elif model == InternationalStandardModel.GOVSTEAM1:
        template = build_govsteam1_template(vf=vf, name=name)
    elif model == InternationalStandardModel.GOVSTEAMEU:
        template = build_govsteameu_template(vf=vf, name=name)
    elif model == InternationalStandardModel.IEEEG1:
        template = build_ieeeg1_template(vf=vf, name=name)
    elif model == InternationalStandardModel.IEEEG2:
        template = build_ieeeg2_template(vf=vf, name=name)
    elif model == InternationalStandardModel.IEEET1:
        template = build_ieeet1_template(vf=vf, name=name)
    elif model == InternationalStandardModel.IEEEX2:
        template = build_ieeex2_template(vf=vf, name=name)
    elif model == InternationalStandardModel.IEEX2A:
        template = build_ieex2a_template(vf=vf, name=name)
    elif model == InternationalStandardModel.MAXEX2:
        template = build_maxex2_template(vf=vf, name=name)
    elif model == InternationalStandardModel.OEL2C:
        template = build_oel2c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.OEL3C:
        template = build_oel3c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.OEL4C:
        template = build_oel4c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.OEL5C:
        template = build_oel5c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSS1AOMEGA:
        template = build_pss1aomega_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSS1APGEN:
        template = build_pss1apgen_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSS2A:
        template = build_pss2a_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSS2B:
        template = build_pss2b_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSS2C:
        template = build_pss2c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSS3B:
        template = build_pss3b_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSS3C:
        template = build_pss3c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSS6C:
        template = build_pss6c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PSSKUNDUR:
        template = build_psskundur_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PVCURRENTSOURCEBNOPLANTCONTROL:
        template = build_pvcurrentsourcebnoplantcontrol_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PVVOLTAGESOURCEANOPLANTCONTROL:
        template = build_pvvoltagesourceanoplantcontrol_template(vf=vf, name=name)
    elif model == InternationalStandardModel.PVVOLTAGESOURCEBNOPLANTCONTROL:
        template = build_pvvoltagesourcebnoplantcontrol_template(vf=vf, name=name)
    elif model == InternationalStandardModel.REECB:
        template = build_reecb_template(vf=vf, name=name)
    elif model == InternationalStandardModel.REECC:
        template = build_reecc_template(vf=vf, name=name)
    elif model == InternationalStandardModel.REGCBCS:
        template = build_regcbcs_template(vf=vf, name=name)
    elif model == InternationalStandardModel.REPCA:
        template = build_repca_template(vf=vf, name=name)
    elif model == InternationalStandardModel.SCL1C:
        template = build_scl1c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.SCL2C:
        template = build_scl2c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.SCRX:
        template = build_scrx_template(vf=vf, name=name)
    elif model == InternationalStandardModel.SEXS:
        template = build_sexs_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST1A:
        template = build_st1a_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST1C:
        template = build_st1c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST4B:
        template = build_st4b_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST4C:
        template = build_st4c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST5B:
        template = build_st5b_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST5C:
        template = build_st5c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST6B:
        template = build_st6b_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST6C:
        template = build_st6c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST7B:
        template = build_st7b_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST7C:
        template = build_st7c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ST9C:
        template = build_st9c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.TGOV3:
        template = build_tgov3_template(vf=vf, name=name)
    elif model == InternationalStandardModel.UEL1:
        template = build_uel1_template(vf=vf, name=name)
    elif model == InternationalStandardModel.UEL2C:
        template = build_uel2c_template(vf=vf, name=name)
    elif model == InternationalStandardModel.VRKUNDUR:
        template = build_vrkundur_template(vf=vf, name=name)
    elif model == InternationalStandardModel.WPP4BCURRENTSOURCE2020:
        template = build_wpp4bcurrentsource2020_template(vf=vf, name=name)
    elif model == InternationalStandardModel.WT4ACURRENTSOURCE:
        template = build_wt4acurrentsource_template(vf=vf, name=name)
    elif model == InternationalStandardModel.WT4ACURRENTSOURCE2020:
        template = build_wt4acurrentsource2020_template(vf=vf, name=name)
    elif model == InternationalStandardModel.WT4BCURRENTSOURCE2020:
        template = build_wt4bcurrentsource2020_template(vf=vf, name=name)
    elif model == InternationalStandardModel.WT4BCURRENTSOURCE:
        template = build_wt4bcurrentsource_template(vf=vf, name=name)
    elif model == InternationalStandardModel.WT4INJECTOR:
        template = build_wt4injector_template(vf=vf, name=name)
    elif model == InternationalStandardModel.WTG4ACURRENTSOURCE:
        template = build_wtg4acurrentsource_template(vf=vf, name=name)
    elif model == InternationalStandardModel.WTG4BCURRENTSOURCE:
        template = build_wtg4bcurrentsource_template(vf=vf, name=name)
    elif model == InternationalStandardModel.IEEEVC_1981:
        template = build_ieeevc_1981_template(vf=vf, name=name)
    elif model == InternationalStandardModel.ESDC2A:
        template = build_esdc2a_template(vf=vf, name=name)
    elif model == InternationalStandardModel.FRQTPA:
        template = build_frqtpa_template(vf=vf, name=name)
    elif model == InternationalStandardModel.VTGTPA:
        template = build_vtgtpa_template(vf=vf, name=name)
    elif model == InternationalStandardModel.CIMTR1:
        template = build_cimtr1_template(vf=vf, name=name)
    elif model == InternationalStandardModel.CIMW:
        template = build_cimw_template(vf=vf, name=name)
    elif model == InternationalStandardModel.GENSAL:
        template = build_gensal_template(vf=vf, name=name)
    elif model == InternationalStandardModel.GENROU:
        template = build_genrou_template(vf=vf, name=name)
    elif model == InternationalStandardModel.GGOV1:
        template = build_ggov1_template(vf=vf, name=name)
    elif model == InternationalStandardModel.HYGOV:
        template = build_hygov_template(vf=vf, name=name)
    elif model == InternationalStandardModel.IEEL:
        template = build_ieel_template(vf=vf, name=name)
    elif model == InternationalStandardModel.TGOV1:
        template = build_tgov1_template(vf=vf, name=name)
    else:
        # The Enum exhausts the supported domain; this branch protects future additions.
        raise ValueError(f"Unsupported international-standard model: {model!s}")

    return template
