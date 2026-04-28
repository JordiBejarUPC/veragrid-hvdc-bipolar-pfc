# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0
from __future__ import annotations

from typing import Union, List, Dict, Any
from VeraGridEngine.Devices.Parents.editable_device import EditableDevice
from VeraGridEngine.enumerations import DeviceType, VarPowerFlowRefferenceType
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const


class VarFactory(EditableDevice):
    """
    VarFactory
    """

    __slots__ = (
        '_var_dict',
        '_const_dict',
        '_diff_var_dict',
        '_vars_info'

    )

    def __init__(self,
                 idtag: Union[str, None] = "",
                 name: str = "Var Factory",
                 code: str = "",
                 comment: str = "") -> None:
        """
        VarFactory
        :param idtag: String. Element unique identifier
        :param name: String. Contingency name
        :param code: String. Contingency code name
        :param comment: Comment
        """

        EditableDevice.__init__(self,
                                idtag=idtag,
                                code=code,
                                name=name,
                                device_type=DeviceType.VarFactory,
                                comment=comment)

        self._var_dict: Dict[int, Var] = dict()
        self._const_dict: Dict[int, Const] = dict()
        self._diff_var_dict: Dict[int, Var] = dict()
        self._vars_info: Dict[Any, List[Var]] = dict()

    @property
    def vars_info(self) -> Dict[Any, List[Var]]:
        return self._vars_info

    def get_vars_to_save(self,
                         dev:Any,
                         names: List[str]) -> List[Var]:
        """
        this function returns a list of variables which names are in names
        :param dev:
        :type dev:
        :param names:
        :type names:
        :return:
        :rtype:
        """
        return [v for v in self._vars_info[dev] if v.name in names]

    def add_var(self,
                name: str,
                reference: VarPowerFlowRefferenceType | None = None,
                network_conn: bool = False,
                uid: int | None = None,
                diff_var: Var | None = None,
                base_var: Var | None = None) -> Var:
        """
        Adds a ver to the class
        :param name:
        :param reference:
        :param network_conn:
        :param uid:
        :param diff_var:
        :param base_var:
        :return:
        """
        v = Var(name=name, reference=reference, network_conn=network_conn, uid=uid, diff_var=None, base_var=None)
        self._var_dict[v.uid] = v
        return v

    def get_var(self, uid: int) -> Var | None:
        """
        Gets a Var from the class
        :param uid:
        :return:
        """
        if uid is not None:
            return self._var_dict[uid]
        else:
            return None

    def add_diff_var(self,
                     name: str,
                     reference: VarPowerFlowRefferenceType | None = None,
                     network_conn: bool = False,
                     uid: int | None = None,
                     diff_var: Var | None = None,
                     base_var: Var | None = None) -> Var:
        """
        Adds a Diff ver to the class
        :param name:
        :param reference:
        :param network_conn:
        :param uid:
        :param diff_var:
        :param base_var:
        :return:
        """
        v = Var(name=name, reference=reference, network_conn=network_conn, uid=uid, diff_var=diff_var, base_var=base_var)
        self._diff_var_dict[v.uid] = v
        return v

    def get_diff_var(self, uid: int) -> Var:
        """
        Gets a Diff Var from the class
        :param uid:
        :return:
        """
        return self._diff_var_dict[uid]

    def add_const(self,
                  value: float | None = None,
                  uid: int | None = None,
                  name: str = "")-> Const:
        """
        Adds a Cont to the class
        :param value:
        :param uid:
        :param name:
        :return:
        """
        v = Const(value=value, uid=uid, name=name)
        self._const_dict[v.uid] = v
        return v

    def get_const(self, uid: int) -> Const:
        """
        Gets a Cont from the class
        :param uid:
        :return:
        """
        return self._const_dict[uid]

    def get_const_dict(self) -> Dict[int, Const]:
        """

        :return:
        """
        return self._const_dict

    def get_vars_dict(self) -> Dict[int, Var]:
        """

        :return:
        """
        return self._var_dict

    def get_diff_var_dict(self) -> Dict[int, Var]:
        """

        :return:
        """
        return self._diff_var_dict

    def parse_const_dict(self, data_list: List[Dict[str, Any]]):
        """

        :param data_list:
        :return:
        """
        obj_dict: Dict[int, Const] = dict()
        for data in data_list:

            t = data["type"]
            if t == "Const":
                if data.get("kind") == "complex":
                    arr = data["value"]
                    obj = Const(value=complex(arr[0], arr[1]),
                                uid=data["uid"])
                else:
                    obj = Const(value=data["value"],
                                uid=data["uid"])

            else:
                raise ValueError(f"Unhandled symbolic primitive {t}")

            # at this point we can store the object
            obj_dict[obj.uid] = obj

        self._const_dict = obj_dict

    def parse_var_dict(self, data_list: List[Dict[str, Any]]):
        """

        :param data_list:
        :return:
        """
        obj_dict: Dict[int, Var] = dict()
        for data in data_list:
            assert data["type"] == "Var"

            # Older persisted symbolic models may not store the power-flow
            # reference field, so keep loading those files by defaulting to None.
            ref_data: Any = data.get("ref", None)
            key_ref: VarPowerFlowRefferenceType | None

            if ref_data is not None:
                key_ref = VarPowerFlowRefferenceType(ref_data)
            else:
                key_ref = None

            obj = Var(name=data["name"], uid=data["uid"], reference=key_ref)

            # at this point we can store the object
            obj_dict[obj.uid] = obj

        self._var_dict = obj_dict

    def parse_diff_var_dict(self,
            data_list: List[Dict[str, Any]]):
        """

        :param data_list:
        :param var_dict: dictionary of vars
        :param diff_var_dict: dictionary of diffVars
        :return:
        """
        obj_dict: Dict[int, Var | Const | Var] = dict()
        for data in data_list:
            assert data["type"] == "DiffVar"

            """
            lst.append({
                    "type": "DiffVar",
                    "name": expr.name,
                    "uid": expr.uid,
                    "base_var": _expr_to_dict(expr=expr.base_var, obj_dict=obj_dict),
                })
            """
            if data["base_var"] in self._var_dict.keys():
                base_var = self._var_dict[data["base_var"]]
            elif data["base_var"] in self._diff_var_dict.keys():
                base_var = self._diff_var_dict[data["base_var"]]
            else:
                base_var = obj_dict[data["base_var"]]

            # Older persisted symbolic models may not store the power-flow
            # reference field on differential variables either.
            reference: VarPowerFlowRefferenceType | None = data.get("ref", None)
            obj = Var(name=data["name"],
                      uid=data["uid"],
                      base_var=base_var,
                      reference=reference)

            # at this point we can store the object
            obj_dict[obj.uid] = obj

        self._diff_var_dict = obj_dict

    def register_var(self, dev:Any, var:Var):

        """
        Associate a variable with a device
        :param dev: Device
        :param var: Variable
        """

        var_list = self._vars_info.get(dev, None)

        if var_list is None:
            self._vars_info[dev] = [var]
        else:
            var_list.append(var)

    def find_var_or_diff_var(self, var_uid: int | None):
        if var_uid in self.get_vars_dict():
            return self.get_var(var_uid)
        elif var_uid in self.get_diff_var_dict():
            return self.get_diff_var(var_uid)
        elif var_uid is None:
            return None
        else:
            raise ValueError(f"Var with uid:{var_uid} not added in VarFactory as var or diff_var.")





    def get_existing_symbol_names(self) -> set[str]:
        """Return all symbolic names already stored in the factory.

        The returned set contains the names of regular variables,
        differential variables, and named constants already registered in this
        factory.

        :return: Set with every registered symbolic name.
        """
        names: set[str] = set()

        names.update(v.name for v in self._var_dict.values())
        names.update(v.name for v in self._diff_var_dict.values())
        names.update(c.name for c in self._const_dict.values() if c.name)

        return names

    @staticmethod
    def symbol_uses_template_name(symbol_name: str, template_name: str) -> bool:
        """Check whether one symbol name uses one template instance name.

        The helper supports both suffix-based and middle-segment naming
        patterns used by the EMT templates, such as ``Raa_Pi`` and
        ``i_ser_Pi_A``.

        :param symbol_name: Full symbolic variable or constant name.
        :param template_name: Candidate template instance name.
        :return: True when the symbol appears to use the template name.
        """
        if not template_name:
            return False

        return (
            symbol_name == template_name
            or symbol_name.startswith(f"{template_name}_")
            or symbol_name.endswith(f"_{template_name}")
            or f"_{template_name}_" in symbol_name
        )

    def is_template_name_used(self, name: str) -> bool:
        """Check whether one template instance name is already in use.

        :param name: Candidate template instance name.
        :return: True when any registered symbol appears to use ``name``.
        """
        return any(
            self.symbol_uses_template_name(symbol_name=symbol_name,
                                           template_name=name)
            for symbol_name in self.get_existing_symbol_names()
        )

    def get_unique_template_name(self, name: str) -> str:
        """Return one template name that is not already used.

        The first instance keeps the requested name. Collisions, including
        user-provided explicit names, are resolved deterministically by
        appending an increasing integer suffix.

        :param name: Requested template instance name.
        :return: Unique template instance name.
        """
        if not self.is_template_name_used(name):
            return name

        i = 1
        while self.is_template_name_used(f"{name}{i}"):
            i += 1

        return f"{name}{i}"
