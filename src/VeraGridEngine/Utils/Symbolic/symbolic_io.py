# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations
from typing import Dict, Any, List
from VeraGridEngine.Utils.Symbolic.symbolic import Var, DiffVar, Expr, Const, BinOp, UnOp, Func
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.enumerations import VarPowerFlowRefferenceType, ParamPowerFlowRefferenceType


def symbolic_objects_to_dict(obj_dict: Dict[int, Var | Const | DiffVar]) -> List[Dict[str, Any]]:
    """
    Save the list of all unique vars, diffvars and const
    :param obj_dict: Dictionary storing the unique objects
    :return: List of dictionaries representing each object
    """
    lst: List[Dict[str, Any]] = list()

    for uuid, expr in obj_dict.items():

        if isinstance(expr, Const):

            # add it to the references dict
            obj_dict[expr.uid] = expr

            # The const didn't exist, we create it here
            if isinstance(expr.value, complex):
                lst.append({"type": "Const",
                            "value": [expr.value.real, expr.value.imag],
                            "kind": "complex",
                            "uid": expr.uid})
            else:
                lst.append({"type": "Const",
                            "value": expr.value,
                            "uid": expr.uid})

        elif isinstance(expr, Var):

            if isinstance(expr, DiffVar):
                lst.append({
                    "type": "DiffVar",
                    "name": expr.name,
                    "uid": expr.uid,
                    "base_var": expr.base_var.uid,
                })

            else:
                # it is a normal var
                lst.append({"type": "Var",
                            "name": expr.name,
                            "uid": expr.uid})

    return lst


def parse_const_dict(data_list: List[Dict[str, Any]]) -> Dict[int, Const]:
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

    return obj_dict


def parse_vars_dict(data_list: List[Dict[str, Any]]) -> Dict[int, Var]:
    """

    :param data_list: 
    :return: 
    """
    obj_dict: Dict[int, Var] = dict()
    for data in data_list:
        assert data["type"] == "Var"

        obj = Var(name=data["name"], uid=data["uid"])

        # at this point we can store the object
        obj_dict[obj.uid] = obj

    return obj_dict


def parse_diff_var_dict(data_list: List[Dict[str, Any]],
                        var_dict: Dict[int, Var], diff_var_dict: Dict[int, DiffVar]) -> Dict[int, Var | Const | DiffVar]:
    """

    :param data_list: 
    :param var_dict: dictionary of vars
    :param diff_var_dict: dictionary of diffVars
    :return: 
    """
    obj_dict: Dict[int, Var | Const | DiffVar] = dict()
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
        if data["base_var"] in var_dict.keys():
            base_var = var_dict[data["base_var"]]
        elif data["base_var"] in diff_var_dict.keys():
            base_var = diff_var_dict[data["base_var"]]
        else:
            base_var = obj_dict[data["base_var"]]


        obj = DiffVar(name=data["name"],
                      uid=data["uid"],
                      base_var=base_var)

        # at this point we can store the object
        obj_dict[obj.uid] = obj

    return obj_dict


def expr_to_dict(expr: Expr,
                 const_dict: Dict[int, Const],
                 var_dict: Dict[int, Var],
                 diff_var_dict: Dict[int, DiffVar]) -> Dict[str, Any]:
    """
    Serialise any `Expr` tree into a plain Python dictionary that’s
    JSON-friendly.  Each node type becomes a small dict that records:

        • its own type      (\"Const\", \"Var\", \"BinOp\", …)
        • the data it carries (value, name, operator…)
        • its unique uid     (string, so it survives round-trip)
        • nested children    (recursively serialised)
    :param expr: Expression child
    :param const_dict: Dictionary that keeps a reference of the Const objects already saved
    :param var_dict: Dictionary that keeps a reference of the VAr objects already saved
    :param diff_var_dict: Dictionary that keeps a reference of the DiffVar objects already saved
    :return: Dict to save in jason
    """

    if isinstance(expr, Const):

        c = const_dict.get(expr.uid, None)

        if c is None:
            # add it to the references dict
            const_dict[expr.uid] = expr

        # the const already exists
        return {
            "type": "Const",
            "uid": expr.uid
        }

    elif isinstance(expr, Var):

        if isinstance(expr, DiffVar):

            c = diff_var_dict.get(expr.uid, None)

            if c is None:
                # add it to the references dict
                diff_var_dict[expr.uid] = expr

            # the diffvar already exists
            return {
                "type": "DiffVar",
                "uid": expr.uid
            }

        else:
            c = var_dict.get(expr.uid, None)

            if c is None:
                # add it to the references dict
                var_dict[expr.uid] = expr

            # the var already exists
            return {
                "type": "Var",
                "uid": expr.uid
            }

    elif isinstance(expr, BinOp):
        return {
            "type": "BinOp",
            "op": expr.op,
            "left": expr_to_dict(expr=expr.left,
                                 const_dict=const_dict, var_dict=var_dict, diff_var_dict=diff_var_dict),
            "right": expr_to_dict(expr=expr.right,
                                  const_dict=const_dict, var_dict=var_dict, diff_var_dict=diff_var_dict),
            "uid": expr.uid,
        }

    elif isinstance(expr, UnOp):
        return {
            "type": "UnOp",
            "op": expr.op,  # only \"-\" for now
            "operand": expr_to_dict(expr=expr.operand,
                                    const_dict=const_dict, var_dict=var_dict, diff_var_dict=diff_var_dict),
            "uid": expr.uid,
        }

    elif isinstance(expr, Func):
        return {
            "type": "Func",
            "op": expr.op,  # sin, cos, log, …
            "arg": expr_to_dict(expr=expr.arg,
                                const_dict=const_dict, var_dict=var_dict, diff_var_dict=diff_var_dict),
            "uid": expr.uid,
        }

    else:
        raise TypeError(f"Unsupported Expr subclass: {type(expr).__name__}")


def expr_list_to_list(lst: List[Expr],
                      const_dict: Dict[int, Const],
                      var_dict: Dict[int, Var],
                      diff_var_dict: Dict[int, DiffVar]) -> List[Dict[str, Any]]:
    """

    :param lst:
    :param const_dict:
    :param var_dict:
    :param diff_var_dict:
    :return:
    """
    lst2: List[Dict[str, Any]] = list()

    for expr in lst:
        lst2.append(
            expr_to_dict(expr=expr,
                         const_dict=const_dict,
                         var_dict=var_dict,
                         diff_var_dict=diff_var_dict)
        )
    return lst2


def parse_expr(data: Dict[str, Any],
               const_dict: Dict[int, Const],
               var_dict: Dict[int, Var],
               diff_var_dict: Dict[int, DiffVar]) -> Const | Var | DiffVar | UnOp | BinOp | Func:
    """
    De-Serialize expression from dictionary
    :param data: Some dictionary containing the expression
    :param const_dict: Dictionary that keeps a reference of the Const objects already saved
    :param var_dict: Dictionary that keeps a reference of the VAr objects already saved
    :param diff_var_dict: Dictionary that keeps a reference of the DiffVar objects already saved
    :return: Expression chil
    """
    t = data["type"]

    if t == "Const":
        return const_dict[data["uid"]]

    elif t == "Var":
        return var_dict[data["uid"]]

    elif t == "DiffVar":

        return diff_var_dict[data["uid"]]

    elif t == "BinOp":
        left = parse_expr(data=data["left"],
                          const_dict=const_dict,
                          var_dict=var_dict,
                          diff_var_dict=diff_var_dict)

        right = parse_expr(data=data["right"],
                           const_dict=const_dict,
                           var_dict=var_dict,
                           diff_var_dict=diff_var_dict)

        obj = BinOp(left=left, op=data["op"], right=right, uid=data["uid"])

    elif t == "UnOp":
        operand = parse_expr(data=data["operand"],
                             const_dict=const_dict,
                             var_dict=var_dict,
                             diff_var_dict=diff_var_dict)
        obj = UnOp(op=data["op"], operand=operand, uid=data["uid"])

    elif t == "Func":
        arg = parse_expr(data=data["arg"],
                         const_dict=const_dict,
                         var_dict=var_dict,
                         diff_var_dict=diff_var_dict)

        obj = Func(arg=arg, op=data["op"], uid=data["uid"])

    else:
        raise ValueError(f"Unknown type '{t}' in symbolic deserialization")

    return obj


def parse_expr_list(lst: List[Dict[str, Any]],
                    const_dict: Dict[int, Const],
                    var_dict: Dict[int, Var],
                    diff_var_dict: Dict[int, DiffVar]) -> List[Const | Var | DiffVar | UnOp | BinOp | Func]:
    """

    :param lst:
    :param const_dict:
    :param var_dict:
    :param diff_var_dict:
    :return:
    """
    lst2 = list()
    for data in lst:
        lst2.append(
            parse_expr(
                data=data,
                const_dict=const_dict,
                var_dict=var_dict,
                diff_var_dict=diff_var_dict
            )
        )
    return lst2


class BlockSaver:

    def __init__(self):
        self.var_dict: Dict[int, Var] = dict()
        self.const_dict: Dict[int, Const] = dict()
        self.diff_var_dict: Dict[int, DiffVar] = dict()
        self.blocks: Dict[int, Dict[str, Any]] = dict()

    def get_const_to_save(self) -> List[Dict[str, Any]]:
        """

        :return:
        """
        return symbolic_objects_to_dict(self.const_dict)

    def get_vars_to_save(self) -> List[Dict[str, Any]]:
        """

        :return:
        """
        return symbolic_objects_to_dict(self.var_dict)

    def get_diff_vars_to_save(self) -> List[Dict[str, Any]]:
        """

        :return:
        """
        return symbolic_objects_to_dict(self.diff_var_dict)

    def get_blocks(self) -> Dict[int, Dict[str, Any]]:
        return self.blocks

    def save_block(self, blk: Block, store: bool = False) -> Dict[str, Any]:
        """
        Get a dictionary representing the block
        All "global references" such a as Conts, Var and DiffVar are stored in the class for later
        :param blk: Block
        :param store: Store the block data?
        :return: Dictionary representing the block
        """
        state_expressions = expr_list_to_list(
            lst=blk.state_eqs,
            const_dict=self.const_dict,
            var_dict=self.var_dict,
            diff_var_dict=self.diff_var_dict
        )

        algebraic_expressions = expr_list_to_list(
            lst=blk.algebraic_eqs,
            const_dict=self.const_dict,
            var_dict=self.var_dict,
            diff_var_dict=self.diff_var_dict
        )

        differential_eqs_expressions = expr_list_to_list(
            lst=blk.differential_eqs,
            const_dict=self.const_dict,
            var_dict=self.var_dict,
            diff_var_dict=self.diff_var_dict
        )

        init_eq_list = list()
        for var, expr in blk.init_eqs.items():

            # TODO: this signals a code small somewhere else
            found_var = self.var_dict.get(var.uid, None)

            if found_var is None :
                self.var_dict[var.uid] = var


            init_eq_list.append(
                {
                    "var": var.uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.const_dict,
                        var_dict=self.var_dict,
                        diff_var_dict=self.diff_var_dict
                    )
                }
            )

        events_list = list()
        for var, expr in blk.event_dict.items():

            # TODO: this signals a code small somewhere else
            found_var = self.var_dict.get(var.uid, None)
            if found_var is None:
                self.var_dict[var.uid] = var

            events_list.append(
                {
                    "var": var.uid,
                    "expr": expr_to_dict(
                        expr=expr,
                        const_dict=self.const_dict,
                        var_dict=self.var_dict,
                        diff_var_dict=self.diff_var_dict
                    )
                }
            )

        in_vars: List[int] = list()
        for var in blk.in_vars:

            # TODO: this signals a code small somewhere else
            found_var = self.var_dict.get(var.uid, None)
            if found_var is None:
                self.var_dict[var.uid] = var

            in_vars.append(var.uid)

        out_vars: List[int] = list()
        for var in blk.out_vars:

            # TODO: this signals a code small somewhere else
            found_var = self.var_dict.get(var.uid, None)
            if found_var is None:
                self.var_dict[var.uid] = var

            out_vars.append(var.uid)

        init_values: List[Dict[str, float | int]] = list()
        for var, value in blk.init_values.items():

            found_var = self.var_dict.get(var.uid, None)
            if found_var is None:
                raise ValueError(f"Initial value not previously defined {var.name}")

            init_values.append({"var": var.uid, "value": value.value})

        parameters: List[Dict[str, float | int]] = list()
        for var, value in blk.parameters.items():

            found_var = self.var_dict.get(var.uid, None)
            if found_var is None:
                raise ValueError(f"Parameter not previously defined {var.name}")

            parameters.append({"var": var.uid, "value": value.value})

        # diff_vars: List[DiffVar] = list()
        for diff_var in blk.diff_vars:
            if diff_var.uid not in self.diff_var_dict:
                self.diff_var_dict[diff_var.uid] = diff_var

        d = {
            "uid": blk.uid,

            "vars2device": {var_uid: dev.idtag for var_uid, dev in blk.vars2device.items()},

            "vars_glob_name2uid": blk.vars_glob_name2uid,

            "state_vars": [v.uid for v in blk.state_vars],

            "state_eqs": state_expressions,

            "algebraic_vars": [v.uid for v in blk.algebraic_vars],

            "algebraic_eqs": algebraic_expressions,

            "diff_vars": [v.uid for v in blk.diff_vars],

            "differential_eqs": differential_eqs_expressions,

            "reformulated_vars": [v.uid for v in blk.reformulated_vars],

            "init_eqs": init_eq_list,

            "init_values": init_values,

            "parameters": parameters,

            "external_mapping": {dyn_var_type.value: var.uid
                                 for dyn_var_type, var in blk.external_mapping.items()},

            "api_obj_mapping": {dyn_param_type.value: param.uid
                                for dyn_param_type, param in blk.api_obj_mapping.items()},

            "event_dict": events_list,
            "name": blk.name,
            "children": [self.save_block(child) for child in blk.children],
            "in_vars": in_vars,
            "out_vars": out_vars
        }

        if store:
            self.blocks[blk.uid] = d


        return d


class BlockParser:

    def __init__(self):
        self.var_dict: Dict[int, Var] = dict()
        self.const_dict: Dict[int, Const] = dict()
        self.diff_var_dict: Dict[int, DiffVar] = dict()
        self.block_dict: Dict[int, Block] = dict()

    def parse_consts(self, data: List[Dict[str, Any]]):
        """

        :param data:
        :return:
        """
        self.const_dict = parse_const_dict(data_list=data)

    def parse_vars(self, data: List[Dict[str, Any]]):
        """

        :param data:
        :return:
        """
        self.var_dict = parse_vars_dict(data_list=data)

    def parse_diff_vars(self, data: List[Dict[str, Any]]):
        """

        :param data:
        :return:
        """
        self.diff_var_dict = parse_diff_var_dict(data_list=data, var_dict=self.var_dict, diff_var_dict=self.diff_var_dict)

    def parse_block(self, data: Dict[Any, Any]) -> Block:
        """

        :param data:
        :return:
        """

        state_vars = [self.var_dict[v] for v in data["state_vars"]]

        state_eqs = parse_expr_list(lst=data["state_eqs"],
                                    const_dict=self.const_dict,
                                    var_dict=self.var_dict,
                                    diff_var_dict=self.diff_var_dict)

        algebraic_vars = [self.var_dict[v] for v in data["algebraic_vars"]]

        algebraic_eqs = parse_expr_list(lst=data["algebraic_eqs"],
                                        const_dict=self.const_dict,
                                        var_dict=self.var_dict,
                                        diff_var_dict=self.diff_var_dict)
        if data["diff_vars"]:
            diff_vars = [self.diff_var_dict[v] for v in data["diff_vars"]]
        else:
            diff_vars = []

        differential_eqs = parse_expr_list(lst=data["differential_eqs"],
                                           const_dict=self.const_dict,
                                           var_dict=self.var_dict,
                                           diff_var_dict=self.diff_var_dict)

        in_vars = [self.var_dict[v] for v in data["in_vars"]]

        out_vars = [self.var_dict[v] for v in data["out_vars"]]

        children = [self.parse_block(child) for child in data["children"]]

        init_eqs: Dict[Var, Expr] = dict()
        for entry in data["init_eqs"]:
            var = self.var_dict[entry["var"]]
            init_eqs[var] = parse_expr(data=entry["expr"],
                                       const_dict=self.const_dict,
                                       var_dict=self.var_dict,
                                       diff_var_dict=self.diff_var_dict)

        event_dict: Dict[Var, Expr] = dict()
        for entry in data["event_dict"]:
            var = self.var_dict[entry["var"]]
            event_dict[var] = parse_expr(data=entry["expr"],
                                         const_dict=self.const_dict,
                                         var_dict=self.var_dict,
                                         diff_var_dict=self.diff_var_dict)

        parameters: Dict[Var, Const] = dict()
        for entry in data["parameters"]:
            var = self.var_dict[entry["var"]]
            parameters[var] = Const(entry["value"])

        init_values: Dict[Var, Const] = dict()
        for entry in data["init_values"]:
            var = self.var_dict[entry["var"]]
            init_values[var] = Const(entry["value"])

        external_mapping: Dict[VarPowerFlowRefferenceType, Var] = dict()
        for key_str, var_uid in data["external_mapping"].items():
            key = VarPowerFlowRefferenceType(key_str)
            external_mapping[key] = self.var_dict[var_uid]

        api_obj_mapping: Dict[ParamPowerFlowRefferenceType, Var] = dict()
        for key_str, var_uid in data["api_obj_mapping"].items():
            key = ParamPowerFlowRefferenceType(key_str)
            api_obj_mapping[key] = self.var_dict[var_uid]

        # # parse children
        # for child_uid in data["children"]:
        #     child_data = self.block_dict[child_uid]
        #     child_block = self.parse_block(data=child_data)



        block = Block(
            state_vars=state_vars,
            state_eqs=state_eqs,
            algebraic_vars=algebraic_vars,
            algebraic_eqs=algebraic_eqs,
            diff_vars=diff_vars,
            differential_eqs=differential_eqs,
            in_vars=in_vars,
            out_vars=out_vars,
            init_eqs=init_eqs,
            event_dict=event_dict,
            children=children,  # TODO think about this
            parameters=parameters,
            init_values=init_values,
            external_mapping=external_mapping,
            api_obj_mapping=api_obj_mapping,
            name=data["name"],
            uid=data["uid"]
        )

        # TODO: Review if this is what is used
        # block.vars_glob_name2uid = data.get("vars_glob_name2uid", {})

        # TODO: This is a circuilar reference, and we can only fill it after all other processes
        # block.vars2device = {int(k): v for k, v in data.get("vars2device", {}).items()}

        self.block_dict[block.uid] = block

        return block


def block_deep_copy(block: Block):
    """
    Create depp copy of a block
    :param block:
    :return:
    """
    saver = BlockSaver()
    d = saver.save_block(block, store=False)
    const_save = saver.get_const_to_save()
    vars_save = saver.get_vars_to_save()
    diff_vars_save = saver.get_diff_vars_to_save()

    parser = BlockParser()
    parser.parse_consts(data=const_save)
    parser.parse_vars(data=vars_save)
    parser.parse_diff_vars(data=diff_vars_save)
    block2 = parser.parse_block(data=d)

    return block2
