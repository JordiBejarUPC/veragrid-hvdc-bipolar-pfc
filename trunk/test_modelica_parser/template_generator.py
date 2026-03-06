# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

"""
VeraGrid Automatic Template Generator.
Converts a VeraGrid Symbolic Block (parsed from Modelica) into a high-performance
Python source file. It separates continuous DAE math from discrete procedural logic.
"""

from typing import List, Set, Union
from pathlib import Path

# VeraGrid Engine Imports
from VeraGridEngine.Utils.Symbolic.symbolic import Var, Const, BinOp, UnOp, Func, Expr
from VeraGridEngine.Utils.Symbolic.block import Block
from trunk.test_modelica_parser.modelica_parser import ModelicaXMLParser, LogicExpr, ExternalFunc


def _clean_name(name: str) -> str:
    """
    Converts Modelica variable names into valid Python identifiers.
    Replaces illegal characters, handles derivatives, and prevents warnings.

    :param name: The original Modelica variable name.
    :type name: str
    :return: A cleaned, Python-compliant identifier.
    :rtype: str
    """
    # 1. Convert OMC derivative naming "der(x)" to VeraGrid standard "d_x"
    temp_name: str = name
    if temp_name.startswith("der(") and temp_name.endswith(")"):
        temp_name = "d_" + temp_name[4:-1]
    else:
        pass

    # 2. Handle the special '$' character by converting it to 'v_'
    temp_name: str = temp_name.replace("$", "v_")

    # 3. Replace dots with underscores for valid attribute access
    temp_name = temp_name.replace(".", "_")

    # 4. Handle array subscripts (e.g., idq_sr[1] -> idq_sr_1)
    temp_name = temp_name.replace("[", "_").replace("]", "")

    # 5. Strip any remaining parentheses to guarantee valid Python syntax
    temp_name = temp_name.replace("(", "_").replace(")", "")

    return temp_name

def _get_var_name(v: Var) -> str:
    """
    Helper function to extract variable names for sorting.
    Replaces forbidden lambda functions.

    :param v: The symbolic variable.
    :type v: Var
    :return: The name of the variable.
    :rtype: str
    """
    return str(v.name)

class ModelicaToPythonTranspiler:
    """
    Translates Modelica AST structures into VeraGrid-compliant Python code.
    Specifically designed for EMT simulations where logic must be procedural.
    """
    __slots__ = ['block', 'parser', 'model_name', 'external_funcs']

    def __init__(self, block: Block, parser: ModelicaXMLParser, model_name: str):
        self.block = block
        self.parser = parser
        self.model_name = model_name
        self.external_funcs: Set[str] = set()

    def expr_to_string(self, expr: Union[Expr, LogicExpr, ExternalFunc], prefix: str = "",
                       symbolic_mode: bool = True) -> str:
        """Recursively converts expressions into their string representation."""
        match expr:
            case Var():
                return f"{prefix}{_clean_name(expr.name)}"
            case Const():
                return str(expr.value)
            case UnOp():
                child_unop: Expr = expr.operand
                child_str: str = self.expr_to_string(child_unop, prefix, symbolic_mode)
                return f"({expr.op}{child_str})"
            case BinOp():
                left_str: str = self.expr_to_string(expr.left, prefix, symbolic_mode)
                right_str: str = self.expr_to_string(expr.right, prefix, symbolic_mode)
                return f"({left_str} {expr.op} {right_str})"
            case LogicExpr():
                if expr.op == "if_else":
                    cond_str: str = self.expr_to_string(expr.args[0], prefix, symbolic_mode)
                    then_str: str = self.expr_to_string(expr.args[1], prefix, symbolic_mode)
                    else_str: str = self.expr_to_string(expr.args[2], prefix, symbolic_mode)
                    return f"({then_str} if {cond_str} else {else_str})"
                else:
                    if len(expr.args) == 1:
                        arg_str: str = self.expr_to_string(expr.args[0], prefix, symbolic_mode)
                        return f"(not {arg_str})"
                    else:
                        if expr.op in ("max", "min", "atan2"):
                            arg1: str = self.expr_to_string(expr.args[0], prefix, symbolic_mode)
                            arg2: str = self.expr_to_string(expr.args[1], prefix, symbolic_mode)
                            return f"sym.{expr.op}({arg1}, {arg2})"

                        op_str_bin: str = expr.op
                        if expr.op == "greater":
                            op_str_bin = ">"
                        elif expr.op == "less":
                            op_str_bin = "<"
                        elif expr.op == "greaterOrEqual":
                            op_str_bin = ">="
                        elif expr.op == "lessOrEqual":
                            op_str_bin = "<="
                        elif expr.op == "and":
                            op_str_bin = "and"
                        elif expr.op == "or":
                            op_str_bin = "or"
                        elif expr.op == "equal":
                            op_str_bin = "=="
                        elif expr.op == "notEqual":
                            op_str_bin = "!="

                        left_log: str = self.expr_to_string(expr.args[0], prefix, symbolic_mode)
                        right_log: str = self.expr_to_string(expr.args[1], prefix, symbolic_mode)
                        return f"({left_log} {op_str_bin} {right_log})"
            case Func():
                if isinstance(expr.arg, tuple):
                    args_str: str = ", ".join([self.expr_to_string(a, prefix, symbolic_mode) for a in expr.arg])
                    return f"sym.{expr.op}({args_str})"
                else:
                    single_arg_str: str = self.expr_to_string(expr.arg, prefix, symbolic_mode)
                    return f"sym.{expr.op}({single_arg_str})"
            case ExternalFunc():
                args_str: str = ", ".join([self.expr_to_string(a, prefix, symbolic_mode) for a in expr.args])
                if symbolic_mode:
                    return f"sym.{expr.name}({args_str})"
                else:
                    return f"ext_funcs.{expr.name}({args_str})"
            case _:
                return str(expr)

    def _contains_logic(self, expr: Union[Expr, LogicExpr, ExternalFunc]) -> bool:
        """
        Recursive check to see if an equation contains discrete logic or conditionals.
        """
        if isinstance(expr, LogicExpr):
            return True
        else:
            if isinstance(expr, BinOp):
                if self._contains_logic(expr.left):
                    return True
                else:
                    if self._contains_logic(expr.right):
                        return True
                    else:
                        return False
            else:
                if isinstance(expr, UnOp):
                    child_unop_logic: Expr = expr.operand
                    if isinstance(child_unop_logic, tuple):
                        has_logic: bool = False
                        for arg in child_unop_logic:
                            if self._contains_logic(arg):
                                has_logic = True
                            else:
                                pass
                        return has_logic
                    else:
                        if child_unop_logic is not None:
                            return self._contains_logic(child_unop_logic)
                        else:
                            return False
                else:
                    if isinstance(expr, Func):
                        if expr.arg is not None:
                            if isinstance(expr.arg, tuple):
                                has_logic_func: bool = False
                                for a in expr.arg:
                                    if self._contains_logic(a):
                                        has_logic_func = True
                                    else:
                                        pass
                                return has_logic_func
                            else:
                                return self._contains_logic(expr.arg)
                        else:
                            return False
                    else:
                        if isinstance(expr, ExternalFunc):
                            has_logic_ext: bool = False
                            for a in expr.args:
                                if self._contains_logic(a):
                                    has_logic_ext = True
                                else:
                                    pass
                            return has_logic_ext
                        else:
                            return False

    def _extract_all_vars(self, expr: Union[Expr, LogicExpr], var_set: Set[Var]) -> None:
        """
        Extracts all unique Variable objects from an expression tree.

        :param expr: The expression tree to scan.
        :type expr: Union[Expr, LogicExpr]
        :param var_set: The set being populated with found variables.
        :type var_set: Set[Var]
        :return: None
        :rtype: None
        """
        match expr:
            case Var():
                var_set.add(expr)
            case BinOp():
                self._extract_all_vars(expr.left, var_set)
                self._extract_all_vars(expr.right, var_set)
            case UnOp():
                child_unop_ext: Expr = expr.operand
                if isinstance(child_unop_ext, tuple):
                    for a in child_unop_ext:
                        self._extract_all_vars(a, var_set)
                else:
                    if child_unop_ext is not None:
                        self._extract_all_vars(child_unop_ext, var_set)
                    else:
                        pass
            case Func():
                if expr.arg is not None:
                    if isinstance(expr.arg, tuple):
                        for a in expr.arg:
                            self._extract_all_vars(a, var_set)
                    else:
                        self._extract_all_vars(expr.arg, var_set)
                else:
                    pass
            case LogicExpr():
                for a in expr.args:
                    self._extract_all_vars(a, var_set)
            case ExternalFunc():
                self.external_funcs.add(expr.name)
                for a in expr.args:
                    self._extract_all_vars(a, var_set)
            case _:
                pass

    def _generate_procedural_logic_block(self) -> List[str]:
        """
        Generates the procedural Python code for the apply_boundary_logic function.
        This handles both continuous logical conditions (If-Then-Else) and discrete
        event handlers (When blocks and Reinit assignments).

        :return: A list of strings representing the indented Python code block.
        :rtype: List[str]
        """
        logic_lines: List[str] = list()
        logic_found: bool = False

        # 1. Continuous Logical Equations (If-Then-Else and state transitions)
        for eq in self.parser.equations:
            if self._contains_logic(eq):
                if isinstance(eq, BinOp) and eq.op == "-" and isinstance(eq.left, Var):
                    target_var: str = _clean_name(eq.left.name)
                    logic_expression: str = self.expr_to_string(eq.right, prefix="state.", symbolic_mode=False)

                    logic_lines.append(f"    state.{target_var} = {logic_expression}")
                    logic_found = True
                else:
                    logic_lines.append(f"    # TODO: Unhandled logic structure -> {self.expr_to_string(eq)}")
                    logic_found = True
            else:
                pass

        # 2. Discrete Event Handlers (When Blocks and Reinit)
        if self.parser.when_equations:
            logic_lines.append("\n    # --- Discrete Event Handlers (When Blocks) ---")

            # Ensure the external functions interface includes the event trigger evaluator
            self.external_funcs.add("event_triggered")

            for cond_expr, statements in self.parser.when_equations.items():
                cond_str: str = self.expr_to_string(cond_expr, prefix="state.", symbolic_mode=False)

                # Modelica 'when' blocks trigger only on the rising edge (False -> True)
                logic_lines.append(f"    if ext_funcs.event_triggered({cond_str}):")

                for stmt in statements:
                    # A Reinit was extracted as a subtraction: Target - NewValue
                    if isinstance(stmt, BinOp) and stmt.op == "-":
                        if isinstance(stmt.left, Var) or (isinstance(stmt.left, Func) and stmt.left.op == "der"):

                            # Extract the target variable name cleanly
                            if isinstance(stmt.left, Func) and stmt.left.op == "der" and isinstance(stmt.left.arg, Var):
                                target: str = "d_" + _clean_name(stmt.left.arg.name)
                            elif isinstance(stmt.left, Var):
                                target: str = _clean_name(stmt.left.name)
                            else:
                                target: str = "unknown_target"

                            new_val_str: str = self.expr_to_string(stmt.right, prefix="state.", symbolic_mode=False)
                            logic_lines.append(f"        state.{target} = {new_val_str}")
                        else:
                            logic_lines.append(f"        # Unhandled Reinit target: {stmt.left}")
                    else:
                        logic_lines.append(f"        # Unhandled When statement: {stmt}")

                logic_found = True
        else:
            pass

        # 3. Logical Initialization Equations (Procedural Pre-Solver Eval)
        init_logic_lines: List[str] = list()
        for eq in self.parser.initial_equations:
            if self._contains_logic(eq):
                if isinstance(eq, BinOp) and eq.op == "-":
                    if isinstance(eq.left, Var):
                        target_var: str = _clean_name(eq.left.name)
                        logic_expression: str = self.expr_to_string(eq.right, prefix="state.", symbolic_mode=False)
                        init_logic_lines.append(f"        state.{target_var} = {logic_expression}")
                    elif isinstance(eq.left, Func) and eq.left.op == "der" and isinstance(eq.left.arg, Var):
                        target_var: str = "d_" + _clean_name(eq.left.arg.name)
                        logic_expression: str = self.expr_to_string(eq.right, prefix="state.", symbolic_mode=False)
                        init_logic_lines.append(f"        state.{target_var} = {logic_expression}")

        if init_logic_lines:
            logic_lines.append("\n    # --- Procedural Initialization Logic ---")
            logic_lines.append("    # Evaluates logic blocks during the first step (t=0) to feed the symbolic solver")
            logic_lines.append("    if state.time == 0.0:")
            logic_lines.extend(init_logic_lines)
            logic_found = True

        if not logic_found:
            logic_lines.append("    pass")
        else:
            pass

        return logic_lines

    def generate_python_file(self, output_dir: str = ".") -> Path:
        """
        Generates the final .py file.
        Separates equations into continuous DAE residuals and procedural logic.
        """
        # 1. Equation Segregation
        state_eqs: List[Expr] = list()
        algebraic_eqs: List[Expr] = list()
        boundary_logic: List[Union[Expr, LogicExpr]] = list()
        all_vars: Set[Var] = set()

        eq_collections = (self.block.state_eqs, self.block.algebraic_eqs)
        for eq_list in eq_collections:
            for eq in eq_list:
                self._extract_all_vars(eq, all_vars)

                if self._contains_logic(eq):
                    boundary_logic.append(eq)
                else:
                    # DAE classification: equations with derivatives vs purely algebraic
                    eq_vars: Set[Var] = set()
                    self._extract_all_vars(eq, eq_vars)

                    has_derivative: bool = False
                    for v in eq_vars:
                        if v.name.startswith("d_"):
                            has_derivative = True
                            break
                        else:
                            pass

                    if has_derivative:
                        state_eqs.append(eq)
                    else:
                        algebraic_eqs.append(eq)

        # Variable Classification
        param_vars = set(self.block.parameters.keys())
        diff_vars = {v for v in all_vars if v.name.startswith("d_") and v.base_var is not None}
        state_vars = {v.base_var for v in diff_vars if v.base_var is not None}
        algebraic_vars = {v for v in all_vars if v not in diff_vars and v not in state_vars and v not in param_vars}

        # 2. Start Writing Content
        clean_model_name_logic: str = _clean_name(self.model_name.lower())

        lines: List[str] = [
            "# --- AUTO-GENERATED EMT TEMPLATE ---",
            "# Source: Modelica Flat XML Transpilation",
            "\nimport numpy as np",
            "from abc import ABC, abstractmethod",
            "from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory",
            "from VeraGridEngine.Utils.Symbolic import symbolic as sym",
            "from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate",
            "from VeraGridEngine.Utils.Symbolic.block import Block",
            "from VeraGridEngine.enumerations import DeviceType\n"
        ]

        if self.external_funcs:
            interface_name = f"I{_clean_name(self.model_name.split('.')[-1])}ExternalFunctions"
            lines.append(f"class {interface_name}(ABC):")
            lines.append('    """')
            lines.append('    Abstract interface for external functions detected in the Modelica XML.')
            lines.append('    The user MUST implement these methods or register them in the symbolic engine.')
            lines.append('    """')
            for f_name in sorted(self.external_funcs):
                lines.append("    @abstractmethod")
                lines.append(f"    def {f_name}(self, *args):")
                lines.append("        pass")
            lines.append("\n")
        else:
            pass

        lines.append(f"def apply_boundary_logic_{clean_model_name_logic}(state):")
        lines.append('    """Procedural logic for switching and discrete events."""')

        # 3. Procedural Boundary Updater (EMT Logic)
        lines.extend(self._generate_procedural_logic_block())
        lines.append("\n")

        # 4. Continuous Template Function
        clean_model_name: str = _clean_name(self.model_name.lower())
        func_name: str = f"get_{clean_model_name}_emt_template"

        lines.append(f"def {func_name}(vf: VarFactory, name: str='{self.model_name}') -> EmtModelTemplate:")
        lines.append('    """Initializes the continuous DAE block and factory variables."""')
        lines.append("    templ = EmtModelTemplate()")
        lines.append("    templ.tpe = DeviceType.GeneratorDevice  # TODO: Verify correct DeviceType")
        lines.append("    templ.name = name\n")

        # Variable Registration
        lines.append("    # --- Parameters ---")
        for p in sorted(param_vars, key=_get_var_name):
            clean_p = _clean_name(p.name)
            lines.append(f"    {clean_p} = vf.add_var('{p.name}')")

        lines.append("\n    # --- State Variables ---")
        for v in sorted(state_vars, key=_get_var_name):
            clean_v = _clean_name(v.name)
            lines.append(f"    {clean_v} = vf.add_var('{v.name}_' + name)")

        lines.append("\n    # --- Algebraic Variables ---")
        for v in sorted(algebraic_vars, key=_get_var_name):
            clean_v = _clean_name(v.name)
            lines.append(f"    {clean_v} = vf.add_var('{v.name}_' + name)")

        lines.append("\n    # --- Derivative Variables ---")
        for v in sorted(diff_vars, key=_get_var_name):
            clean_v = _clean_name(v.name)
            base_name = _clean_name(v.base_var.name) if v.base_var else "UNKNOWN"
            lines.append(f"    {clean_v} = vf.add_diff_var('{v.name}', base_var={base_name})")

        # Block Assembly
        lines.append("\n    # --- Continuous Block Assembly ---")
        lines.append("    templ.block = Block(")
        lines.append("        state_eqs=[")
        for eq in state_eqs:
            lines.append(f"            {self.expr_to_string(eq)},")
        lines.append("        ],")
        state_vars_str = ", ".join(_clean_name(v.name) for v in sorted(state_vars, key=_get_var_name))
        lines.append(f"        state_vars=[{state_vars_str}],")
        lines.append("\n        algebraic_eqs=[")
        for eq in algebraic_eqs:
            lines.append(f"            {self.expr_to_string(eq)},")
        lines.append("        ],")
        alg_vars_str = ", ".join(_clean_name(v.name) for v in sorted(algebraic_vars, key=_get_var_name))
        lines.append(f"        algebraic_vars=[{alg_vars_str}],")
        lines.append("    )")

        # Parameters and Initial Guesses
        lines.append("\n    # --- Parameter Values ---")
        lines.append("    templ.block.event_dict = {")
        for p, const_val in self.block.parameters.items():
            clean_p = _clean_name(p.name)
            lines.append(f"        {clean_p}: vf.add_const({const_val.value}),")
        lines.append("    }")

        lines.append("\n    # --- Initial Equations and Guesses ---")
        lines.append("    templ.block.init_eqs = {")

        # Dictionary to act as a funnel. Duplicate assignments will overwrite previous ones,
        # keeping the dictionary clean for VeraGrid.
        init_dict: Dict[str, str] = dict()

        # 1. Algebraic Initialization Relationships (from Modelica initial equations)
        for eq in self.parser.initial_equations:
            if isinstance(eq, BinOp) and eq.op == "-":
                lhs: Expr = eq.left
                rhs: Expr = eq.right

                # Modelica sometimes exports ‘x - $START.x = 0’. We ignore those pseudo-variables.
                rhs_str_check: str = self.expr_to_string(rhs, prefix="", symbolic_mode=True)

                if "START" not in rhs_str_check:
                    # SHIELD: VeraGrid's continuous DAE solver (init_eqs) cannot handle discrete logic.
                    # We evaluate if the initialization equation contains If-Then-Else or logic statements.
                    contains_logic: bool = self._contains_logic(rhs)

                    # If logic is NOT found, it is a continuous algebraic relationship valid for the symbolic solver.
                    if not contains_logic:
                        if isinstance(lhs, Var):
                            clean_lhs_var: str = _clean_name(lhs.name)
                            rhs_str_var: str = ""

                            if isinstance(rhs, Const):
                                rhs_str_var = f"vf.add_const({rhs.value})"
                            else:
                                rhs_str_var = rhs_str_check

                            # Save or overwrite in the local dictionary
                            init_dict[clean_lhs_var] = rhs_str_var

                        elif isinstance(lhs, Func) and lhs.op == "der" and isinstance(lhs.arg, Var):
                            clean_lhs_der: str = "d_" + _clean_name(lhs.arg.name)
                            rhs_str_der: str = ""

                            if isinstance(rhs, Const):
                                rhs_str_der = f"vf.add_const({rhs.value})"
                            else:
                                rhs_str_der = rhs_str_check

                            # Save or overwrite derivative in the local dictionary
                            init_dict[clean_lhs_der] = rhs_str_der
                        else:
                            pass
                    else:
                        # Logic IS found. We skip adding it to the symbolic init_eqs dict.
                        # It has already been processed by the procedural boundary logic block.
                        pass
                else:
                    pass
            else:
                pass

        # --- Pre-sort variables safely without list addition ---
        var_collections = (state_vars, algebraic_vars)
        all_sorted_vars: List[Var] = list()
        for v_set in var_collections:
            for v_item in v_set:
                all_sorted_vars.append(v_item)
        all_sorted_vars.sort(key=_get_var_name)

        # 2. Fixed Initial Conditions (fixed="true" override loose equations)
        for v in all_sorted_vars:
            is_fixed: bool | None = self.parser.fixed_initial_values.get(v.uid, None)
            if is_fixed:
                fixed_val: float | None = self.parser.initial_guesses.get(v.uid, None)
                if fixed_val is not None:
                    clean_v: str = _clean_name(v.name)
                    # Fixed true is unmovable, it crushes any previous equation
                    init_dict[clean_v] = f"vf.add_const({fixed_val})"
                else:
                    pass
            else:
                pass

        # 3. Fallback Guesses (start="X" but fixed="false")
        for v in all_sorted_vars:
            clean_v: str = _clean_name(v.name)
            # Only add a default guess if it hasn't been initialized by equations or fixed constraints
            existing_guess: str | None = init_dict.get(clean_v, None)
            if existing_guess is None:
                guess: float | None = self.parser.initial_guesses.get(v.uid, None)
                if guess is not None:
                    init_dict[clean_v] = f"vf.add_const({guess})"
                else:
                    init_dict[clean_v] = "vf.add_const(0.0)"
            else:
                pass

        # 4. Write the consolidated, duplicate-free dictionary to the file
        for var_name, var_expr in init_dict.items():
            lines.append(f"        {var_name}: {var_expr},")

        lines.append("    }")

        lines.append("\n    return templ\n")

        # 5. Disk Write
        safe_filename: str = _clean_name(self.model_name.lower())
        output_path: Path = Path(output_dir) / f"auto_generated_{safe_filename}.py"
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path