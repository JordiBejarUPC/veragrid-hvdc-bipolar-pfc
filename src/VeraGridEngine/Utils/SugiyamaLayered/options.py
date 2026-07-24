"""Option handling for the Sugiyama layered pipeline.

The layout package keeps one explicit registry of supported options so the
phases can resolve graph and element configuration deterministically.
"""

from __future__ import annotations

from typing import Any


class OptionDefinition:
    """One supported layout option definition.

    :param identifier: Unique option identifier.
    :type identifier: str
    :param default: Default option value.
    :type default: Any
    :param value_type: Accepted Python type or tuple of types.
    :type value_type: type | tuple[type, ...]
    :param applies_to: Primitive kinds where the option is meaningful.
    :type applies_to: tuple[str, ...]
    """

    __slots__ = ("_identifier", "_default", "_value_type", "_applies_to")

    def __init__(
            self,
            identifier: str,
            default: Any,
            value_type: type | tuple[type, ...],
            applies_to: tuple[str, ...],
    ) -> None:
        self._identifier: str = identifier
        self._default: Any = default
        self._value_type: type | tuple[type, ...] = value_type
        self._applies_to: tuple[str, ...] = applies_to

    @property
    def identifier(self) -> str:
        """Return the option identifier.

        :return: Option identifier.
        :rtype: str
        """
        return self._identifier

    @property
    def default(self) -> Any:
        """Return the default option value.

        :return: Default option value.
        :rtype: Any
        """
        return self._default

    @property
    def value_type(self) -> type | tuple[type, ...]:
        """Return the accepted Python type.

        :return: Accepted type or tuple of types.
        :rtype: type | tuple[type, ...]
        """
        return self._value_type

    @property
    def applies_to(self) -> tuple[str, ...]:
        """Return the supported primitive kinds.

        :return: Supported primitive kinds.
        :rtype: tuple[str, ...]
        """
        return self._applies_to


def _build_default_registry() -> dict[str, OptionDefinition]:
    """Build the default option registry.

    :return: Default option definitions indexed by identifier.
    :rtype: dict[str, OptionDefinition]
    """
    registry: dict[str, OptionDefinition] = dict()

    registry["org.vera.sugiyama.algorithm"] = OptionDefinition(
        identifier="org.vera.sugiyama.algorithm",
        default="layered",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.direction"] = OptionDefinition(
        identifier="org.vera.sugiyama.direction",
        default="UNDEFINED",
        value_type=str,
        applies_to=("graph", "node"),
    )
    registry["org.vera.sugiyama.edgeRouting"] = OptionDefinition(
        identifier="org.vera.sugiyama.edgeRouting",
        default="ORTHOGONAL",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.spacing.nodeNode"] = OptionDefinition(
        identifier="org.vera.sugiyama.spacing.nodeNode",
        default=20.0,
        value_type=(int, float),
        applies_to=("graph", "node"),
    )
    registry["org.vera.sugiyama.spacing.componentComponent"] = OptionDefinition(
        identifier="org.vera.sugiyama.spacing.componentComponent",
        default=40.0,
        value_type=(int, float),
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.layered.spacing.nodeNodeBetweenLayers"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.spacing.nodeNodeBetweenLayers",
        default=20.0,
        value_type=(int, float),
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.layered.layering.strategy"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.layering.strategy",
        default="NETWORK_SIMPLEX",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.layered.cycleBreaking.strategy"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.cycleBreaking.strategy",
        default="GREEDY",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.layered.nodePlacement.strategy"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.nodePlacement.strategy",
        default="BRANDES_KOEPF",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.layered.nodePlacement.bk.fixedAlignment"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.nodePlacement.bk.fixedAlignment",
        default="NONE",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.layered.crossingMinimization.strategy"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.crossingMinimization.strategy",
        default="LAYER_SWEEP",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.portConstraints"] = OptionDefinition(
        identifier="org.vera.sugiyama.portConstraints",
        default="UNDEFINED",
        value_type=str,
        applies_to=("node",),
    )
    registry["org.vera.sugiyama.port.side"] = OptionDefinition(
        identifier="org.vera.sugiyama.port.side",
        default="UNDEFINED",
        value_type=str,
        applies_to=("port",),
    )
    registry["org.vera.sugiyama.portAlignment.default"] = OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.default",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    )
    registry["org.vera.sugiyama.portAlignment.west"] = OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.west",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    )
    registry["org.vera.sugiyama.portAlignment.east"] = OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.east",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    )
    registry["org.vera.sugiyama.portAlignment.north"] = OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.north",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    )
    registry["org.vera.sugiyama.portAlignment.south"] = OptionDefinition(
        identifier="org.vera.sugiyama.portAlignment.south",
        default="CENTER",
        value_type=str,
        applies_to=("graph", "node"),
    )
    registry["org.vera.sugiyama.layered.considerModelOrder.strategy"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.considerModelOrder.strategy",
        default="NONE",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.layered.edgeRouting.selfLoopDistribution"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.edgeRouting.selfLoopDistribution",
        default="NORTH",
        value_type=str,
        applies_to=("graph",),
    )
    registry["org.vera.sugiyama.layered.feedbackEdges"] = OptionDefinition(
        identifier="org.vera.sugiyama.layered.feedbackEdges",
        default=False,
        value_type=(bool, str),
        applies_to=("graph",),
    )

    return registry


SUGIYAMA_LAYERED_DEFAULTS: dict[str, OptionDefinition] = _build_default_registry()


class SugiyamaOptionResolver:
    """Resolve and validate layered layout options.

    :param registry: Optional custom option registry.
    :type registry: dict[str, OptionDefinition] | None
    """

    __slots__ = ("_registry",)

    def __init__(self, registry: dict[str, OptionDefinition] | None = None) -> None:
        if registry is None:
            self._registry: dict[str, OptionDefinition] = dict(SUGIYAMA_LAYERED_DEFAULTS)
        else:
            self._registry = dict(registry)

    def validate(self, option_id: str, value: Any) -> bool:
        """Validate one option value against the registry.

        :param option_id: Option identifier to validate.
        :type option_id: str
        :param value: Candidate value.
        :type value: Any
        :return: ``True`` when the value is acceptable.
        :rtype: bool
        """
        definition: OptionDefinition | None = self._registry.get(option_id, None)

        if definition is None:
            return True
        else:
            if isinstance(value, definition.value_type):
                return True
            else:
                if isinstance(value, str) and definition.value_type == (int, float):
                    try:
                        float(value)
                    except ValueError:
                        return False
                    else:
                        return True
                else:
                    return False

    def resolve_for_element(
            self,
            graph_options: dict[str, Any],
            element_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve options for one graph element.

        The algorithm starts from registry defaults, then applies graph-level
        overrides, and finally element-specific overrides. The precedence must
        be explicit because all phases inspect the resolved values repeatedly.

        :param graph_options: Graph-level option overrides.
        :type graph_options: dict[str, Any]
        :param element_options: Element-specific option overrides.
        :type element_options: dict[str, Any] | None
        :return: Resolved option dictionary.
        :rtype: dict[str, Any]
        """
        resolved: dict[str, Any] = dict()
        option_id: str
        definition: OptionDefinition

        for option_id, definition in self._registry.items():
            resolved[option_id] = definition.default

        resolved.update(graph_options)
        if element_options is None:
            pass
        else:
            resolved.update(element_options)

        return resolved
