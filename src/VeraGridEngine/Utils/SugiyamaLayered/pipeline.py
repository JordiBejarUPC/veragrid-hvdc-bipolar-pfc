"""Pipeline infrastructure for the Sugiyama layered engine."""

from __future__ import annotations

from time import perf_counter

from VeraGridEngine.Utils.SugiyamaLayered.model import SugiyamaGraph
from VeraGridEngine.Utils.SugiyamaLayered.options import SugiyamaOptionResolver


class PhaseTiming:
    """Execution timing for one pipeline phase.

    :param name: Phase name.
    :type name: str
    :param seconds: Execution time in seconds.
    :type seconds: float
    """

    __slots__ = ("_name", "_seconds")

    def __init__(self, name: str, seconds: float) -> None:
        self._name: str = name
        self._seconds: float = seconds

    @property
    def name(self) -> str:
        """Return the phase name.

        :return: Phase name.
        :rtype: str
        """
        return self._name

    @property
    def seconds(self) -> float:
        """Return the elapsed phase time.

        :return: Elapsed phase time.
        :rtype: float
        """
        return self._seconds


class PipelineReport:
    """Pipeline execution report.

    :param timings: Optional phase timings.
    :type timings: list[PhaseTiming] | None
    :param notes: Optional diagnostic notes.
    :type notes: list[str] | None
    """

    __slots__ = ("_timings", "_notes")

    def __init__(
            self,
            timings: list[PhaseTiming] | None = None,
            notes: list[str] | None = None,
    ) -> None:
        timings_data: list[PhaseTiming]
        notes_data: list[str]

        if timings is None:
            timings_data = list()
        else:
            timings_data = list(timings)

        if notes is None:
            notes_data = list()
        else:
            notes_data = list(notes)

        self._timings: list[PhaseTiming] = timings_data
        self._notes: list[str] = notes_data

    @property
    def timings(self) -> list[PhaseTiming]:
        """Return the timing records.

        :return: Phase timing records.
        :rtype: list[PhaseTiming]
        """
        return self._timings

    @property
    def notes(self) -> list[str]:
        """Return the diagnostic notes.

        :return: Diagnostic notes.
        :rtype: list[str]
        """
        return self._notes


class LayoutContext:
    """Shared mutable pipeline context.

    :param graph: Graph being laid out.
    :type graph: SugiyamaGraph
    :param option_resolver: Option resolver used by the phases.
    :type option_resolver: SugiyamaOptionResolver
    :param report: Optional pipeline report.
    :type report: PipelineReport | None
    :param phase_state: Optional shared phase state storage.
    :type phase_state: dict[str, object] | None
    """

    __slots__ = ("_graph", "_option_resolver", "_report", "_phase_state")

    def __init__(
            self,
            graph: SugiyamaGraph,
            option_resolver: SugiyamaOptionResolver,
            report: PipelineReport | None = None,
            phase_state: dict[str, object] | None = None,
    ) -> None:
        report_data: PipelineReport
        phase_state_data: dict[str, object]

        if report is None:
            report_data = PipelineReport()
        else:
            report_data = report

        if phase_state is None:
            phase_state_data = dict()
        else:
            phase_state_data = dict(phase_state)

        self._graph: SugiyamaGraph = graph
        self._option_resolver: SugiyamaOptionResolver = option_resolver
        self._report: PipelineReport = report_data
        self._phase_state: dict[str, object] = phase_state_data

    @property
    def graph(self) -> SugiyamaGraph:
        """Return the graph under layout.

        :return: Graph under layout.
        :rtype: SugiyamaGraph
        """
        return self._graph

    @property
    def option_resolver(self) -> SugiyamaOptionResolver:
        """Return the option resolver.

        :return: Option resolver.
        :rtype: SugiyamaOptionResolver
        """
        return self._option_resolver

    @property
    def report(self) -> PipelineReport:
        """Return the pipeline report.

        :return: Pipeline report.
        :rtype: PipelineReport
        """
        return self._report

    @property
    def phase_state(self) -> dict[str, object]:
        """Return the shared phase state storage.

        :return: Shared phase state storage.
        :rtype: dict[str, object]
        """
        return self._phase_state


class LayoutPhaseBase:
    """Base class for layered layout phases."""

    __slots__ = ()

    name: str = ""

    def run(self, context: LayoutContext) -> None:
        """Execute the phase.

        :param context: Shared pipeline context.
        :type context: LayoutContext
        :return: None.
        :rtype: None
        """
        raise NotImplementedError("Layout phases must implement run().")


class LayoutPipeline:
    """Ordered collection of layout phases.

    :param phases: Pipeline phase instances.
    :type phases: list[LayoutPhaseBase]
    """

    __slots__ = ("_phases",)

    def __init__(self, phases: list[LayoutPhaseBase]) -> None:
        self._phases: list[LayoutPhaseBase] = list(phases)

    @property
    def phases(self) -> list[LayoutPhaseBase]:
        """Return the pipeline phases.

        :return: Pipeline phases.
        :rtype: list[LayoutPhaseBase]
        """
        return self._phases

    def run(self, context: LayoutContext) -> PipelineReport:
        """Execute all phases in sequence.

        The pipeline records each phase timing immediately after the phase
        completes so failures can be correlated with the already executed
        portion of the algorithm.

        :param context: Shared pipeline context.
        :type context: LayoutContext
        :return: Pipeline report.
        :rtype: PipelineReport
        """
        phase: LayoutPhaseBase

        for phase in self._phases:
            start_seconds: float = perf_counter()
            phase.run(context)
            elapsed_seconds: float = perf_counter() - start_seconds
            context.report.timings.append(PhaseTiming(name=phase.name, seconds=elapsed_seconds))

        return context.report
