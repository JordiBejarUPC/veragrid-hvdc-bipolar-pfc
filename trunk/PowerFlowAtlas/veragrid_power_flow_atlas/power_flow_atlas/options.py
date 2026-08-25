from power_flow_atlas.enumerations import AtlasFallbackMode, SeriesEvaluationMethod


class PowerFlowAtlasOptions:
    """Configuration for atlas construction and online evaluation.

    The object is deliberately mutable only through explicit setters. This keeps
    changes observable while avoiding implicit dictionary-based configuration.
    """

    __slots__ = (
        "_series_order",
        "_series_method",
        "_series_tolerance",
        "_newton_tolerance",
        "_maximum_newton_iterations",
        "_validity_radius",
        "_minimum_pade_denominator",
        "_reactive_limit_tolerance",
        "_fallback_mode",
    )

    def __init__(
        self,
        series_order: int = 8,
        series_method: SeriesEvaluationMethod = SeriesEvaluationMethod.Pade,
        series_tolerance: float = 1.0e-8,
        newton_tolerance: float = 1.0e-10,
        maximum_newton_iterations: int = 3,
        validity_radius: float = 0.15,
        minimum_pade_denominator: float = 1.0e-10,
        reactive_limit_tolerance: float = 1.0e-7,
        fallback_mode: AtlasFallbackMode = AtlasFallbackMode.FullPowerFlow,
    ) -> None:
        """Create atlas options.

        :param series_order: Maximum directional voltage-series order.
        :param series_method: Method used to evaluate the directional series.
        :param series_tolerance: Maximum accepted fixed-regime residual in p.u.
        :param newton_tolerance: Tolerance used by the VeraGrid correction step.
        :param maximum_newton_iterations: Maximum correction iterations.
        :param validity_radius: Maximum normalized first-order state displacement.
        :param minimum_pade_denominator: Minimum safe Padé denominator magnitude.
        :param reactive_limit_tolerance: Reactive-limit verification tolerance.
        :param fallback_mode: Policy used when the series is not certified.
        """
        # Establish a complete valid state before applying caller-provided
        # values. Every setter handles invalid inputs without leaving the
        # options object partially initialized.
        self._series_order: int = 8
        self._series_method: SeriesEvaluationMethod = SeriesEvaluationMethod.Pade
        self._series_tolerance: float = 1.0e-8
        self._newton_tolerance: float = 1.0e-10
        self._maximum_newton_iterations: int = 3
        self._validity_radius: float = 0.15
        self._minimum_pade_denominator: float = 1.0e-10
        self._reactive_limit_tolerance: float = 1.0e-7
        self._fallback_mode: AtlasFallbackMode = AtlasFallbackMode.FullPowerFlow

        self.set_series_order(series_order)
        self.set_series_method(series_method)
        self.set_series_tolerance(series_tolerance)
        self.set_newton_tolerance(newton_tolerance)
        self.set_maximum_newton_iterations(maximum_newton_iterations)
        self.set_validity_radius(validity_radius)
        self.set_minimum_pade_denominator(minimum_pade_denominator)
        self.set_reactive_limit_tolerance(reactive_limit_tolerance)
        self.set_fallback_mode(fallback_mode)

    def get_series_order(self) -> int:
        """Return the maximum directional voltage-series order."""
        return self._series_order

    def set_series_order(self, series_order: int) -> None:
        """Set the maximum directional voltage-series order.

        :param series_order: New order, which must be at least one.
        """
        if series_order >= 1:
            self._series_order = series_order
        else:
            self._series_order = 1

    def get_series_method(self) -> SeriesEvaluationMethod:
        """Return the configured series-evaluation method."""
        return self._series_method

    def set_series_method(self, series_method: SeriesEvaluationMethod) -> None:
        """Set the series-evaluation method.

        :param series_method: New evaluation method.
        """
        if isinstance(series_method, SeriesEvaluationMethod):
            self._series_method = series_method
        else:
            self._series_method = SeriesEvaluationMethod.Pade

    def get_series_tolerance(self) -> float:
        """Return the maximum accepted fixed-regime residual."""
        return self._series_tolerance

    def set_series_tolerance(self, series_tolerance: float) -> None:
        """Set the maximum accepted fixed-regime residual.

        :param series_tolerance: Positive mismatch tolerance in p.u.
        """
        if series_tolerance > 0.0:
            self._series_tolerance = series_tolerance
        else:
            self._series_tolerance = 1.0e-8

    def get_newton_tolerance(self) -> float:
        """Return the VeraGrid Newton-correction tolerance."""
        return self._newton_tolerance

    def set_newton_tolerance(self, newton_tolerance: float) -> None:
        """Set the VeraGrid Newton-correction tolerance.

        :param newton_tolerance: Positive Newton tolerance in p.u.
        """
        if newton_tolerance > 0.0:
            self._newton_tolerance = newton_tolerance
        else:
            self._newton_tolerance = 1.0e-10

    def get_maximum_newton_iterations(self) -> int:
        """Return the maximum number of VeraGrid correction iterations."""
        return self._maximum_newton_iterations

    def set_maximum_newton_iterations(self, maximum_newton_iterations: int) -> None:
        """Set the maximum number of VeraGrid correction iterations.

        :param maximum_newton_iterations: Non-negative correction limit.
        """
        if maximum_newton_iterations >= 0:
            self._maximum_newton_iterations = maximum_newton_iterations
        else:
            self._maximum_newton_iterations = 0

    def get_validity_radius(self) -> float:
        """Return the normalized first-order patch radius."""
        return self._validity_radius

    def set_validity_radius(self, validity_radius: float) -> None:
        """Set the normalized first-order patch radius.

        :param validity_radius: Positive dimensionless radius.
        """
        if validity_radius > 0.0:
            self._validity_radius = validity_radius
        else:
            self._validity_radius = 0.15

    def get_minimum_pade_denominator(self) -> float:
        """Return the minimum safe Padé denominator magnitude."""
        return self._minimum_pade_denominator

    def set_minimum_pade_denominator(self, minimum_pade_denominator: float) -> None:
        """Set the minimum safe Padé denominator magnitude.

        :param minimum_pade_denominator: Positive denominator threshold.
        """
        if minimum_pade_denominator > 0.0:
            self._minimum_pade_denominator = minimum_pade_denominator
        else:
            self._minimum_pade_denominator = 1.0e-10

    def get_reactive_limit_tolerance(self) -> float:
        """Return the reactive-limit verification tolerance."""
        return self._reactive_limit_tolerance

    def set_reactive_limit_tolerance(self, reactive_limit_tolerance: float) -> None:
        """Set the reactive-limit verification tolerance.

        :param reactive_limit_tolerance: Non-negative tolerance in p.u.
        """
        if reactive_limit_tolerance >= 0.0:
            self._reactive_limit_tolerance = reactive_limit_tolerance
        else:
            self._reactive_limit_tolerance = 0.0

    def get_fallback_mode(self) -> AtlasFallbackMode:
        """Return the configured fallback policy."""
        return self._fallback_mode

    def set_fallback_mode(self, fallback_mode: AtlasFallbackMode) -> None:
        """Set the fallback policy.

        :param fallback_mode: New fallback policy.
        """
        if isinstance(fallback_mode, AtlasFallbackMode):
            self._fallback_mode = fallback_mode
        else:
            self._fallback_mode = AtlasFallbackMode.FullPowerFlow
