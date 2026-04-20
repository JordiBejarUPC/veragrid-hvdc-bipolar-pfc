from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType
from typing import Sequence

from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate
from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog.catalog import get_powerfactory_basic_catalog_descriptor_by_key
from VeraGridEngine.Templates.catalog.powerfactory_basic_catalog.catalog import get_powerfactory_basic_catalog_templates_dir
from VeraGridEngine.Utils.Symbolic.block import Block
from VeraGridEngine.Utils.Symbolic.symbolic import CmpOp
from VeraGridEngine.Utils.Symbolic.symbolic import Comparison
from VeraGridEngine.Utils.Symbolic.symbolic import Const
from VeraGridEngine.Utils.Symbolic.symbolic import Expr
from VeraGridEngine.Utils.Symbolic.symbolic import Func2
from VeraGridEngine.Utils.Symbolic.symbolic import Var
from VeraGridEngine.Utils.procedural_logic import AnalogFlipFlopLogic
from VeraGridEngine.Utils.procedural_logic import FixedSampleLogic
from VeraGridEngine.Utils.procedural_logic import FlipFlopLogic
from VeraGridEngine.Utils.procedural_logic import GradientLimiterLogic
from VeraGridEngine.Utils.procedural_logic import MovingAverageLogic
from VeraGridEngine.Utils.procedural_logic import PickupDropoffLogic
from VeraGridEngine.Utils.procedural_logic import ResetOnRisingEdgeLogic
from VeraGridEngine.Utils.procedural_logic import SampledValueLogic
from VeraGridEngine.Utils.procedural_logic import TimeDelayLogic


class _TemplateVariableGroups:
    """
    Explicit variable groups used by the standalone module emitter.
    """

    __slots__ = ("param_vars", "state_vars", "algebraic_vars", "diff_vars")

    def __init__(self,
                 param_vars: Sequence[Var],
                 state_vars: Sequence[Var],
                 algebraic_vars: Sequence[Var],
                 diff_vars: Sequence[Var]) -> None:
        """
        Store the variable groups used by one emitted template module.

        :param param_vars: Runtime parameter variables.
        :param state_vars: State variables.
        :param algebraic_vars: Algebraic and shared variables.
        :param diff_vars: Differential variables.
        :returns: None.
        """
        self.param_vars = tuple(param_vars)
        self.state_vars = tuple(state_vars)
        self.algebraic_vars = tuple(algebraic_vars)
        self.diff_vars = tuple(diff_vars)


class PowerFactoryBasicStandaloneModuleEmitter:
    """
    Emit one clean standalone catalog module from one materialized template block.
    """

    __slots__ = (
        "_block",
        "_display_name",
        "_default_template_name",
        "_referenced_vars_by_uid",
        "_identifier_map",
        "_variable_groups",
    )

    def __init__(self,
                 block: Block,
                 display_name: str,
                 default_template_name: str) -> None:
        """
        Build the standalone module emitter for one materialized template.

        :param block: Materialized template block.
        :param display_name: Human-facing template name.
        :param default_template_name: Default runtime template name.
        :returns: None.
        :raises ValueError: Raised when the block contains child blocks.
        """
        if len(block.children) > 0:
            raise ValueError("The standalone catalog emitter only supports leaf blocks")
        else:
            pass

        self._block = block
        self._display_name = display_name
        self._default_template_name = default_template_name
        self._referenced_vars_by_uid: dict[int, Var] = dict()
        self._collect_referenced_variables(self._referenced_vars_by_uid)
        self._identifier_map = self._build_identifier_map()
        self._variable_groups = self._build_variable_groups()

    def render(self) -> str:
        """
        Render the full standalone Python module.

        :returns: Python module text.
        """
        lines: list[str] = list()

        self._append_module_docstring(lines)
        self._append_imports(lines)
        self._append_default_name_function(lines)
        self._append_get_template_function(lines)

        return "\n".join(lines) + "\n"

    def _append_module_docstring(self, lines: list[str]) -> None:
        """
        Append the module docstring.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append('"""')
        lines.append(f"Standalone EMT template for the PowerFactory basic block '{self._display_name}'.")
        lines.append("")
        lines.append("This module is generated from the shipped VeraGrid catalog artifacts and keeps the")
        lines.append("symbolic surface explicit so both humans and tools can inspect it directly.")
        lines.append('"""')
        lines.append("")

    def _append_imports(self, lines: list[str]) -> None:
        """
        Append the import block.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append("from VeraGridEngine.Devices.Dynamic.emt_template import EmtModelTemplate")
        lines.append("from VeraGridEngine.Devices.Dynamic.var_factory import VarFactory")
        lines.append("from VeraGridEngine.Utils.Symbolic.block import Block")
        lines.append("from VeraGridEngine.Utils.Symbolic import symbolic as sym")
        lines.append("from VeraGridEngine.Utils.Symbolic.symbolic import Const")
        lines.append("from VeraGridEngine.Utils.Symbolic.symbolic import Expr")
        lines.append("from VeraGridEngine.Utils.Symbolic.symbolic import Var")
        logic_import_names: Sequence[str] = self._build_procedural_logic_import_names()

        if len(logic_import_names) > 0:
            lines.append("from VeraGridEngine.Utils.procedural_logic import " + ", ".join(logic_import_names))
        else:
            pass

        lines.append("from VeraGridEngine.enumerations import DeviceType")
        lines.append("")

    def _append_default_name_function(self, lines: list[str]) -> None:
        """
        Append the default-name helper.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("def build_default_template_name() -> str:")
        lines.append("    \"\"\"")
        lines.append("    Return the canonical runtime name for this standalone template.")
        lines.append("")
        lines.append("    :returns: Default template name.")
        lines.append("    \"\"\"")
        lines.append(f"    return {repr(self._default_template_name)}")
        lines.append("")

    def _append_get_template_function(self, lines: list[str]) -> None:
        """
        Append the template builder function.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("def get_template(vf: VarFactory, name: str | None = None) -> EmtModelTemplate:")
        lines.append("    \"\"\"")
        lines.append("    Materialize the standalone EMT template.")
        lines.append("")
        lines.append("    :param vf: Variable factory used to allocate the symbolic surface.")
        lines.append("    :param name: Optional explicit runtime template name.")
        lines.append("    :returns: Materialized EMT template.")
        lines.append("    \"\"\"")
        lines.append("    template_name: str")
        lines.append("    if name is None:")
        lines.append("        template_name = build_default_template_name()")
        lines.append("    else:")
        lines.append("        template_name = name")
        lines.append("")
        lines.append("    # Allocate the template container before building the symbolic surface.")
        lines.append("    template: EmtModelTemplate = EmtModelTemplate()")
        lines.append("    template.tpe = DeviceType.NoDevice")
        lines.append("    template.name = template_name")
        lines.append("")
        self._append_variable_declarations(lines)
        self._append_block_collection_builders(lines)
        self._append_block_constructor(lines)
        lines.append("")
        lines.append("    return template")
        lines.append("")

    def _append_variable_declarations(self, lines: list[str]) -> None:
        """
        Append the variable declarations grouped by their runtime role.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("    # Declare every variable explicitly before the equations reference it.")
        self._append_group_variable_declarations(lines, "runtime parameter", self._variable_groups.param_vars, False)
        self._append_group_variable_declarations(lines, "state", self._variable_groups.state_vars, False)
        self._append_group_variable_declarations(lines, "algebraic/shared", self._variable_groups.algebraic_vars, False)
        self._append_group_variable_declarations(lines, "differential", self._variable_groups.diff_vars, True)
        lines.append("")

    def _append_group_variable_declarations(self,
                                            lines: list[str],
                                            group_label: str,
                                            group_vars: Sequence[Var],
                                            differential_group: bool) -> None:
        """
        Append the declarations for one variable group.

        :param lines: Output line buffer.
        :param group_label: Human-facing group label.
        :param group_vars: Variables in the group.
        :param differential_group: ``True`` when the variables are differential variables.
        :returns: None.
        """
        lines.append(f"    # Declare the {group_label} variables used by the template.")
        sorted_vars: list[Var] = list(group_vars)
        sorted_vars.sort(key=self._var_sort_key)
        var_obj: Var

        for var_obj in sorted_vars:
            identifier: str = self._identifier_map[var_obj.uid]
            raw_var_name: str = self._build_runtime_free_var_name(var_obj.name)
            if differential_group:
                base_identifier: str = self._identifier_map[var_obj.base_var.uid]
                lines.append(
                    f"    {identifier}: Var = vf.add_diff_var({repr(raw_var_name + '_')} + template_name, base_var={base_identifier})"
                )
            else:
                lines.append(f"    {identifier}: Var = vf.add_var({repr(raw_var_name + '_')} + template_name)")

    def _append_block_collection_builders(self, lines: list[str]) -> None:
        """
        Append the typed collection builders used by the block constructor.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("    # Build explicit typed collections so the symbolic surface is easy to inspect.")
        self._append_expression_list(lines, "state_equations", list(self._block.state_eqs))
        self._append_var_list(lines, "state_variables", list(self._block.state_vars))
        self._append_expression_list(lines, "algebraic_equations", list(self._block.algebraic_eqs))
        self._append_var_list(lines, "algebraic_variables", list(self._block.algebraic_vars))
        self._append_var_list(lines, "differential_variables", list(self._block.diff_vars))
        self._append_var_list(lines, "input_variables", list(self._block.in_vars))
        self._append_var_list(lines, "output_variables", list(self._block.out_vars))
        self._append_expression_mapping(lines, "event_parameters", self._block.event_dict)
        self._append_expression_mapping(lines, "mode_parameters", self._block.mode_dict)
        self._append_expression_mapping(lines, "initial_equations", self._block.init_eqs)
        self._append_expression_mapping(lines, "differential_initial_equations", self._block.diff_init_eqs)
        self._append_procedural_logic_list(lines)

    def _append_expression_list(self,
                                lines: list[str],
                                list_name: str,
                                expressions: Sequence[Expr]) -> None:
        """
        Append one typed expression list.

        :param lines: Output line buffer.
        :param list_name: Target variable name.
        :param expressions: Expressions to append.
        :returns: None.
        """
        lines.append(f"    {list_name}: list[Expr] = list()")
        expr_obj: Expr
        for expr_obj in expressions:
            lines.append(f"    {list_name}.append({self._expr_to_python(expr_obj)})")

    def _append_var_list(self,
                         lines: list[str],
                         list_name: str,
                         vars_list: Sequence[Var]) -> None:
        """
        Append one typed variable list.

        :param lines: Output line buffer.
        :param list_name: Target variable name.
        :param vars_list: Variables to append.
        :returns: None.
        """
        lines.append(f"    {list_name}: list[Var] = list()")
        var_obj: Var
        for var_obj in vars_list:
            lines.append(f"    {list_name}.append({self._identifier_map[var_obj.uid]})")

    def _append_expression_mapping(self,
                                   lines: list[str],
                                   mapping_name: str,
                                   mapping: dict[Var, Expr | Const]) -> None:
        """
        Append one typed expression mapping.

        :param lines: Output line buffer.
        :param mapping_name: Target variable name.
        :param mapping: Mapping to append.
        :returns: None.
        """
        lines.append(f"    {mapping_name}: dict[Var, Expr | Const] = dict()")
        key_obj: Var
        value_obj: Expr | Const
        for key_obj, value_obj in mapping.items():
            lines.append(
                f"    {mapping_name}[{self._identifier_map[key_obj.uid]}] = {self._expr_or_const_to_python(value_obj)}"
            )

    def _append_procedural_logic_list(self, lines: list[str]) -> None:
        """
        Append the typed procedural-logic list.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("    procedural_logic_entries: list[object] = list()")
        logic_obj: object
        for logic_obj in self._block.procedural_logic:
            lines.append(f"    procedural_logic_entries.append({self._procedural_logic_entry_to_python(logic_obj)})")

    def _append_block_constructor(self, lines: list[str]) -> None:
        """
        Append the final block constructor.

        :param lines: Output line buffer.
        :returns: None.
        """
        lines.append("")
        lines.append("    # Assemble the final block from the explicit typed collections above.")
        lines.append("    template.block = Block(")
        lines.append("        state_vars=state_variables,")
        lines.append("        state_eqs=state_equations,")
        lines.append("        algebraic_vars=algebraic_variables,")
        lines.append("        algebraic_eqs=algebraic_equations,")
        lines.append("        diff_vars=differential_variables,")
        lines.append("        init_eqs=initial_equations,")
        lines.append("        diff_init_eqs=differential_initial_equations,")
        lines.append("        in_vars=input_variables,")
        lines.append("        out_vars=output_variables,")
        lines.append("        event_dict=event_parameters,")
        lines.append("        mode_dict=mode_parameters,")
        lines.append("        procedural_logic=procedural_logic_entries,")
        lines.append("        name=template_name,")
        lines.append("    )")

    def _build_identifier_map(self) -> dict[int, str]:
        """
        Build the deterministic Python identifier map for the block surface.

        :returns: Identifier by variable uid.
        """
        used_identifiers: dict[str, int] = dict()
        identifier_map: dict[int, str] = dict()
        ordered_vars: list[Var] = list(self._referenced_vars_by_uid.values())
        ordered_vars.sort(key=self._var_sort_key)
        var_obj: Var

        for var_obj in ordered_vars:
            base_identifier: str = self._safe_name(self._build_runtime_free_var_name(var_obj.name))
            current_count: int = used_identifiers.get(base_identifier, 0)
            used_identifiers[base_identifier] = current_count + 1
            if current_count == 0:
                identifier_map[var_obj.uid] = base_identifier
            else:
                identifier_map[var_obj.uid] = f"{base_identifier}_{current_count}"

        return identifier_map

    def _build_variable_groups(self) -> _TemplateVariableGroups:
        """
        Build the declaration groups used by the emitted module.

        :returns: Variable groups.
        """
        all_vars: list[Var] = list(self._referenced_vars_by_uid.values())
        state_uids: set[int] = {var_obj.uid for var_obj in self._block.state_vars}
        diff_uids: set[int] = {var_obj.uid for var_obj in self._block.diff_vars}
        param_uids: set[int] = {var_obj.uid for var_obj in self._block.event_dict.keys()}
        param_uids |= {var_obj.uid for var_obj in self._block.parameters.keys()}

        param_vars: list[Var] = list()
        state_vars: list[Var] = list()
        algebraic_vars: list[Var] = list()
        diff_vars: list[Var] = list()
        var_obj: Var

        for var_obj in all_vars:
            if var_obj.uid in diff_uids:
                diff_vars.append(var_obj)
            elif var_obj.uid in state_uids:
                state_vars.append(var_obj)
            elif var_obj.uid in param_uids:
                param_vars.append(var_obj)
            else:
                algebraic_vars.append(var_obj)

        return _TemplateVariableGroups(
            param_vars=param_vars,
            state_vars=state_vars,
            algebraic_vars=algebraic_vars,
            diff_vars=diff_vars,
        )

    def _collect_referenced_variables(self, vars_found: dict[int, Var]) -> None:
        """
        Collect every variable referenced by the emitted leaf block.

        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        self._collect_var_sequence(self._block.state_vars, vars_found)
        self._collect_var_sequence(self._block.algebraic_vars, vars_found)
        self._collect_var_sequence(self._block.diff_vars, vars_found)
        self._collect_var_sequence(self._block.in_vars, vars_found)
        self._collect_var_sequence(self._block.out_vars, vars_found)
        self._collect_mapping_variables(self._block.event_dict, vars_found)
        self._collect_mapping_variables(self._block.mode_dict, vars_found)
        self._collect_mapping_variables(self._block.init_eqs, vars_found)
        self._collect_mapping_variables(self._block.diff_init_eqs, vars_found)
        self._collect_expr_sequence(self._block.state_eqs, vars_found)
        self._collect_expr_sequence(self._block.algebraic_eqs, vars_found)
        self._collect_procedural_logic_variables(vars_found)

    def _collect_var_sequence(self,
                              vars_list: Sequence[Var],
                              vars_found: dict[int, Var]) -> None:
        """
        Collect one variable sequence into the uid map.

        :param vars_list: Variable sequence.
        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        var_obj: Var
        for var_obj in vars_list:
            vars_found[var_obj.uid] = var_obj

    def _collect_mapping_variables(self,
                                   mapping: dict[Var, Expr | Const],
                                   vars_found: dict[int, Var]) -> None:
        """
        Collect the variables referenced by one mapping.

        :param mapping: Mapping to inspect.
        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        key_obj: Var
        value_obj: Expr | Const
        for key_obj, value_obj in mapping.items():
            vars_found[key_obj.uid] = key_obj
            self._collect_expr_variables(value_obj, vars_found)

    def _collect_expr_sequence(self,
                               expressions: Sequence[Expr],
                               vars_found: dict[int, Var]) -> None:
        """
        Collect the variables referenced by one expression sequence.

        :param expressions: Expression sequence.
        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        expr_obj: Expr
        for expr_obj in expressions:
            self._collect_expr_variables(expr_obj, vars_found)

    def _collect_expr_variables(self,
                                expr_obj: Expr | Const | Comparison,
                                vars_found: dict[int, Var]) -> None:
        """
        Collect the variables referenced by one expression-like object.

        :param expr_obj: Expression-like object.
        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        expression: Expr
        if isinstance(expr_obj, Comparison):
            expression = expr_obj.to_expression()
        elif isinstance(expr_obj, Expr):
            expression = expr_obj
        else:
            expression = expr_obj

        if isinstance(expression, Var):
            vars_found[expression.uid] = expression
        elif isinstance(expression, Expr):
            var_obj: Var
            for var_obj in expression.get_vars():
                vars_found[var_obj.uid] = var_obj
        else:
            pass

    def _collect_procedural_logic_variables(self, vars_found: dict[int, Var]) -> None:
        """
        Collect variables referenced by the procedural logic entries.

        :param vars_found: Output mapping by variable uid.
        :returns: None.
        """
        logic_obj: object
        for logic_obj in self._block.procedural_logic:
            if isinstance(logic_obj, FixedSampleLogic):
                self._collect_expr_variables(logic_obj.condition_expr, vars_found)
                output_var: Var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, SampledValueLogic):
                self._collect_expr_variables(logic_obj.source_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, FlipFlopLogic):
                self._collect_expr_variables(logic_obj.set_expr, vars_found)
                self._collect_expr_variables(logic_obj.reset_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, AnalogFlipFlopLogic):
                self._collect_expr_variables(logic_obj.input_expr, vars_found)
                self._collect_expr_variables(logic_obj.set_expr, vars_found)
                self._collect_expr_variables(logic_obj.reset_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, PickupDropoffLogic):
                self._collect_expr_variables(logic_obj.bool_expr, vars_found)
                self._collect_expr_variables(logic_obj.pickup_delay_expr, vars_found)
                self._collect_expr_variables(logic_obj.drop_delay_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, TimeDelayLogic):
                self._collect_expr_variables(logic_obj.source_expr, vars_found)
                self._collect_expr_variables(logic_obj.delay_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, MovingAverageLogic):
                self._collect_expr_variables(logic_obj.source_expr, vars_found)
                self._collect_expr_variables(logic_obj.delay_expr, vars_found)
                self._collect_expr_variables(logic_obj.window_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, GradientLimiterLogic):
                self._collect_expr_variables(logic_obj.source_expr, vars_found)
                self._collect_expr_variables(logic_obj.lower_rate_expr, vars_found)
                self._collect_expr_variables(logic_obj.upper_rate_expr, vars_found)
                output_var = self._find_var_by_name_from_candidates(logic_obj.output_var_name, vars_found)
                vars_found[output_var.uid] = output_var
            elif isinstance(logic_obj, ResetOnRisingEdgeLogic):
                self._collect_expr_variables(logic_obj.reset_expr, vars_found)
                self._collect_expr_variables(logic_obj.value_expr, vars_found)
                target_var: Var = self._find_var_by_name_from_candidates(logic_obj.target_var_name, vars_found)
                vars_found[target_var.uid] = target_var
            else:
                raise TypeError(f"Unsupported procedural logic export type: {type(logic_obj).__name__}")

    def _build_procedural_logic_import_names(self) -> Sequence[str]:
        """
        Build the deterministic procedural-logic import list.

        :returns: Sorted import-name tuple.
        """
        names: set[str] = set()
        logic_obj: object
        for logic_obj in self._block.procedural_logic:
            if isinstance(logic_obj, FixedSampleLogic):
                names.add("selfix")
            elif isinstance(logic_obj, SampledValueLogic):
                if logic_obj.output_var_name.startswith("proc_select_") or "__proc_select_" in logic_obj.output_var_name:
                    names.add("sampled_value")
                else:
                    names.add("lastvalue")
            elif isinstance(logic_obj, FlipFlopLogic):
                names.add("flipflop")
            elif isinstance(logic_obj, AnalogFlipFlopLogic):
                names.add("aflipflop")
            elif isinstance(logic_obj, PickupDropoffLogic):
                names.add("picdro")
            elif isinstance(logic_obj, TimeDelayLogic):
                names.add("delay")
            elif isinstance(logic_obj, MovingAverageLogic):
                names.add("movingavg")
            elif isinstance(logic_obj, GradientLimiterLogic):
                names.add("gradlim_const")
            elif isinstance(logic_obj, ResetOnRisingEdgeLogic):
                names.add("reset")
            else:
                raise TypeError(f"Unsupported procedural logic export type: {type(logic_obj).__name__}")

        return tuple(sorted(names))

    def _procedural_logic_entry_to_python(self, logic_obj: object) -> str:
        """
        Convert one procedural-logic entry to Python code.

        :param logic_obj: Procedural-logic entry.
        :returns: Python expression text.
        """
        if isinstance(logic_obj, FixedSampleLogic):
            output_var: Var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return f"selfix({self._expr_like_to_python(logic_obj.condition_expr)}, output={self._identifier_map[output_var.uid]})"
        elif isinstance(logic_obj, SampledValueLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            if logic_obj.output_var_name.startswith("proc_select_") or "__proc_select_" in logic_obj.output_var_name:
                return f"sampled_value(output={self._identifier_map[output_var.uid]}, source={self._expr_like_to_python(logic_obj.source_expr)})"
            else:
                return f"lastvalue({self._expr_like_to_python(logic_obj.source_expr)}, output={self._identifier_map[output_var.uid]})"
        elif isinstance(logic_obj, FlipFlopLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"flipflop({self._expr_like_to_python(logic_obj.set_expr)}, "
                f"{self._expr_like_to_python(logic_obj.reset_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, AnalogFlipFlopLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"aflipflop({self._expr_like_to_python(logic_obj.input_expr)}, "
                f"{self._expr_like_to_python(logic_obj.set_expr)}, "
                f"{self._expr_like_to_python(logic_obj.reset_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, PickupDropoffLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"picdro({self._expr_like_to_python(logic_obj.bool_expr)}, "
                f"{self._expr_like_to_python(logic_obj.pickup_delay_expr)}, "
                f"{self._expr_like_to_python(logic_obj.drop_delay_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, TimeDelayLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"delay({self._expr_like_to_python(logic_obj.source_expr)}, "
                f"{self._expr_like_to_python(logic_obj.delay_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, MovingAverageLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"movingavg({self._expr_like_to_python(logic_obj.source_expr)}, "
                f"{self._expr_like_to_python(logic_obj.delay_expr)}, "
                f"{self._expr_like_to_python(logic_obj.window_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, GradientLimiterLogic):
            output_var = self._find_referenced_var_by_name(logic_obj.output_var_name)
            return (
                f"gradlim_const({self._expr_like_to_python(logic_obj.source_expr)}, "
                f"{self._expr_like_to_python(logic_obj.lower_rate_expr)}, "
                f"{self._expr_like_to_python(logic_obj.upper_rate_expr)}, output={self._identifier_map[output_var.uid]})"
            )
        elif isinstance(logic_obj, ResetOnRisingEdgeLogic):
            target_var: Var = self._find_referenced_var_by_name(logic_obj.target_var_name)
            return (
                f"reset({self._identifier_map[target_var.uid]}, "
                f"{self._expr_like_to_python(logic_obj.reset_expr)}, "
                f"{self._expr_like_to_python(logic_obj.value_expr)})"
            )
        else:
            raise TypeError(f"Unsupported procedural logic export type: {type(logic_obj).__name__}")

    def _expr_like_to_python(self, expr_obj: Expr | Comparison) -> str:
        """
        Convert one expression-like object to Python code.

        :param expr_obj: Expression-like object.
        :returns: Python expression text.
        """
        if isinstance(expr_obj, Comparison):
            rhs_text: str
            if isinstance(expr_obj.rhs, Expr):
                rhs_text = self._expr_to_python_natural(expr_obj.rhs)
            else:
                rhs_text = repr(expr_obj.rhs)

            cmp_name_by_op: dict[CmpOp, str] = dict()
            cmp_name_by_op[CmpOp.EQ] = "EQ"
            cmp_name_by_op[CmpOp.LE] = "LE"
            cmp_name_by_op[CmpOp.GE] = "GE"
            cmp_name_by_op[CmpOp.LT] = "LT"
            cmp_name_by_op[CmpOp.GT] = "GT"

            return (
                f"sym.Comparison(lhs={self._expr_to_python_natural(expr_obj.lhs)}, "
                f"op=sym.CmpOp.{cmp_name_by_op[expr_obj.op]}, rhs={rhs_text})"
            )
        else:
            return self._expr_to_python_natural(expr_obj)

    def _expr_or_const_to_python(self, expr_obj: Expr | Const) -> str:
        """
        Convert one expression-or-constant object to Python code.

        :param expr_obj: Expression-or-constant object.
        :returns: Python expression text.
        """
        if isinstance(expr_obj, Const):
            return f"vf.add_const({repr(expr_obj.value)}, name={repr(expr_obj.name)})"
        else:
            return self._expr_to_python(expr_obj)

    def _expr_to_python(self, expr_obj: Expr) -> str:
        """
        Convert one symbolic expression to Python code.

        :param expr_obj: Symbolic expression.
        :returns: Python expression text.
        """
        if isinstance(expr_obj, Var):
            return self._identifier_map[expr_obj.uid]
        elif isinstance(expr_obj, Const):
            return f"sym.Const({repr(expr_obj.value)})"
        elif isinstance(expr_obj, Func2):
            return f"sym.{expr_obj.name}({self._expr_to_python(expr_obj.arg1)}, {self._expr_to_python(expr_obj.arg2)})"
        else:
            pass

        from VeraGridEngine.Utils.Symbolic.symbolic import BinOp
        from VeraGridEngine.Utils.Symbolic.symbolic import Func
        from VeraGridEngine.Utils.Symbolic.symbolic import UnOp

        if isinstance(expr_obj, BinOp):
            return f"({self._expr_to_python(expr_obj.left)} {expr_obj.op} {self._expr_to_python(expr_obj.right)})"
        elif isinstance(expr_obj, UnOp):
            return f"({expr_obj.op}{self._expr_to_python(expr_obj.operand)})"
        elif isinstance(expr_obj, Func):
            return f"sym.{expr_obj.op}({self._expr_to_python(expr_obj.arg)})"
        else:
            raise TypeError(f"Unsupported expression type for catalog export: {type(expr_obj).__name__}")

    def _expr_to_python_natural(self, expr_obj: Expr) -> str:
        """
        Convert one symbolic expression to more compact Python code.

        :param expr_obj: Symbolic expression.
        :returns: Python expression text.
        """
        if isinstance(expr_obj, Var):
            return self._identifier_map[expr_obj.uid]
        elif isinstance(expr_obj, Const):
            return repr(expr_obj.value)
        elif isinstance(expr_obj, (bool, float, int)):
            return repr(expr_obj)
        elif isinstance(expr_obj, Func2):
            return f"sym.{expr_obj.name}({self._expr_to_python_natural(expr_obj.arg1)}, {self._expr_to_python_natural(expr_obj.arg2)})"
        else:
            pass

        from VeraGridEngine.Utils.Symbolic.symbolic import BinOp
        from VeraGridEngine.Utils.Symbolic.symbolic import Func
        from VeraGridEngine.Utils.Symbolic.symbolic import UnOp

        if isinstance(expr_obj, BinOp):
            return f"({self._expr_to_python_natural(expr_obj.left)} {expr_obj.op} {self._expr_to_python_natural(expr_obj.right)})"
        elif isinstance(expr_obj, UnOp):
            return f"({expr_obj.op}{self._expr_to_python_natural(expr_obj.operand)})"
        elif isinstance(expr_obj, Func):
            return f"sym.{expr_obj.op}({self._expr_to_python_natural(expr_obj.arg)})"
        else:
            raise TypeError(f"Unsupported expression type for natural catalog export: {type(expr_obj).__name__}")

    def _find_local_var_by_name(self, var_name: str) -> Var:
        """
        Return the local variable that matches one emitted variable name.

        :param var_name: Expected variable name.
        :returns: Matching variable.
        :raises KeyError: Raised when the variable is not found.
        """
        vars_list: list[Var] = list()
        vars_list.extend(list(self._block.state_vars))
        vars_list.extend(list(self._block.algebraic_vars))
        vars_list.extend(list(self._block.diff_vars))
        vars_list.extend(list(self._block.in_vars))
        vars_list.extend(list(self._block.out_vars))
        vars_list.extend(list(self._block.event_dict.keys()))
        vars_list.extend(list(self._block.mode_dict.keys()))
        var_obj: Var

        for var_obj in vars_list:
            if var_obj.name == var_name:
                return var_obj
            else:
                pass

        raise KeyError(f"Variable '{var_name}' not found in emitted block '{self._block.name}'")

    def _find_var_by_name_from_candidates(self,
                                          var_name: str,
                                          vars_found: dict[int, Var]) -> Var:
        """
        Return one referenced variable from the partially collected uid map or local surface.

        :param var_name: Expected variable name.
        :param vars_found: Partially collected referenced variables.
        :returns: Matching variable.
        :raises KeyError: Raised when the variable cannot be resolved.
        """
        candidate_var: Var
        for candidate_var in vars_found.values():
            if candidate_var.name == var_name:
                return candidate_var
            else:
                pass

        return self._find_local_var_by_name(var_name)

    def _find_referenced_var_by_name(self, var_name: str) -> Var:
        """
        Return one referenced variable from the final referenced-variable map.

        :param var_name: Expected variable name.
        :returns: Matching variable.
        :raises KeyError: Raised when the variable cannot be resolved.
        """
        return self._find_var_by_name_from_candidates(var_name, self._referenced_vars_by_uid)

    def _safe_name(self, name: str) -> str:
        """
        Convert one symbolic variable name into a safe Python identifier.

        :param name: Raw symbolic name.
        :returns: Safe Python identifier.
        """
        cleaned_name: str = re.sub(r"[^0-9a-zA-Z_]", "_", name)
        cleaned_name = re.sub(r"_+", "_", cleaned_name).strip("_")

        if cleaned_name == "":
            cleaned_name = "unnamed"
        else:
            pass

        if cleaned_name[0].isdigit():
            cleaned_name = f"v_{cleaned_name}"
        else:
            pass

        return cleaned_name

    def _build_runtime_free_var_name(self, var_name: str) -> str:
        """
        Remove the current runtime suffix from one materialized variable name.

        :param var_name: Materialized variable name.
        :returns: Runtime-free variable name.
        """
        suffix: str = f"_{self._default_template_name}"

        if var_name.endswith(suffix):
            return var_name[: -len(suffix)]
        else:
            return var_name

    def _var_sort_key(self, var_obj: Var) -> str:
        """
        Build the deterministic sort key for one symbolic variable.

        :param var_obj: Symbolic variable.
        :returns: Sort key.
        """
        return self._build_runtime_free_var_name(var_obj.name)


def _build_template_from_imported_module(imported_module: ModuleType) -> EmtModelTemplate:
    """
    Materialize one EMT template from one imported standalone module.

    :param imported_module: Imported standalone module.
    :returns: Materialized EMT template.
    :raises TypeError: Raised when the module does not expose a valid ``get_template`` function.
    """
    template_builder_obj: object | None = imported_module.__dict__.get("get_template", None)

    if callable(template_builder_obj):
        template_obj: object = template_builder_obj(VarFactory())
        if isinstance(template_obj, EmtModelTemplate):
            return template_obj
        else:
            raise TypeError("The imported standalone catalog module returned an invalid template object")
    else:
        raise TypeError("The imported standalone catalog module does not expose get_template()")


def _sanitize_display_name(default_template_name: str) -> str:
    """
    Remove the imported type suffix from one default template name.

    :param default_template_name: Default runtime template name.
    :returns: Clean display name.
    """
    return re.sub(r"__\d+$", "", default_template_name).strip()


def _build_module_sort_key(module_path: Path) -> tuple[int, str]:
    """
    Build the deterministic sort key for one standalone module path.

    :param module_path: Standalone module path.
    :returns: Sort key ordered by numeric typ_id and filename.
    """
    match_obj = re.fullmatch(r"typ_(\d+)__.+", module_path.stem)
    if match_obj is None:
        raise ValueError(f"Unexpected standalone module filename '{module_path.name}'")
    else:
        return int(match_obj.group(1)), module_path.name


def _import_template_module_from_path(module_path: Path) -> ModuleType:
    """
    Import one standalone module directly from one source path.

    :param module_path: Standalone module path.
    :returns: Imported standalone module.
    :raises ImportError: Raised when the module cannot be imported.
    """
    module_name: str = f"veragrid_catalog_rewrite_{module_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import standalone module from '{module_path}'")
    else:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def rewrite_powerfactory_basic_catalog_template_module_from_path(source_path: Path,
                                                                 output_directory: Path) -> Path:
    """
    Rewrite one standalone catalog module from one explicit source path.

    :param source_path: Source standalone module path.
    :param output_directory: Destination directory.
    :returns: Path to the rewritten module.
    """
    imported_module: ModuleType = _import_template_module_from_path(source_path)
    template: EmtModelTemplate = _build_template_from_imported_module(imported_module)
    emitter: PowerFactoryBasicStandaloneModuleEmitter = PowerFactoryBasicStandaloneModuleEmitter(
        block=template.block,
        display_name=_sanitize_display_name(template.name),
        default_template_name=template.name,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    target_path: Path = output_directory / source_path.name
    target_path.write_text(emitter.render(), encoding="utf-8")
    return target_path


def rewrite_powerfactory_basic_catalog_standalone_modules_from_directory(source_directory: Path,
                                                                         output_directory: Path) -> Sequence[Path]:
    """
    Rewrite every standalone catalog module from one explicit source directory.

    :param source_directory: Source directory containing ``typ_*.py`` modules.
    :param output_directory: Destination directory.
    :returns: Written module paths.
    """
    source_paths: list[Path] = list(source_directory.glob("typ_*.py"))
    source_paths.sort(key=_build_module_sort_key)
    written_paths: list[Path] = list()
    source_path: Path

    for source_path in source_paths:
        written_paths.append(rewrite_powerfactory_basic_catalog_template_module_from_path(source_path, output_directory))

    return tuple(written_paths)


def rewrite_powerfactory_basic_catalog_template_module(template_key: str,
                                                      output_directory: Path | None = None) -> Path:
    """
    Rewrite one standalone catalog module using the clean emitter.

    :param template_key: Stable catalog template key.
    :param output_directory: Optional destination directory.
    :returns: Path to the rewritten module.
    """
    source_directory: Path = get_powerfactory_basic_catalog_templates_dir()
    target_directory: Path = get_powerfactory_basic_catalog_templates_dir() if output_directory is None else output_directory
    descriptor = get_powerfactory_basic_catalog_descriptor_by_key()[template_key]
    source_path: Path = source_directory / descriptor.module_filename
    return rewrite_powerfactory_basic_catalog_template_module_from_path(source_path, target_directory)


def rewrite_powerfactory_basic_catalog_standalone_modules(output_directory: Path | None = None) -> Sequence[Path]:
    """
    Rewrite every standalone catalog module using the clean emitter.

    :param output_directory: Optional destination directory.
    :returns: Written module paths.
    """
    source_directory: Path = get_powerfactory_basic_catalog_templates_dir()
    target_directory: Path = get_powerfactory_basic_catalog_templates_dir() if output_directory is None else output_directory
    return rewrite_powerfactory_basic_catalog_standalone_modules_from_directory(source_directory, target_directory)
