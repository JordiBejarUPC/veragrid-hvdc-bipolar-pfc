from __future__ import annotations

from typing import Any


class LivePlotConfig:
    """
    Live plotting configuration bundle.

    :param enabled:
        Enable or disable live plotting.
    :param refresh_interval:
        Number of episodes between plot refreshes.
    :param window_title:
        Figure window title.
    """

    __slots__ = ("_enabled", "_refresh_interval", "_window_title")

    def __init__(
        self,
        enabled: bool = True,
        refresh_interval: int = 1,
        window_title: str = "AI Operator Training Monitor",
    ) -> None:
        self._enabled: bool = enabled
        self._refresh_interval: int = refresh_interval
        self._window_title: str = window_title

    def get_enabled(self) -> bool:
        """
        Get the plotting enabled flag.

        :return:
            ``True`` when plotting is enabled.
        """

        return self._enabled

    def get_refresh_interval(self) -> int:
        """
        Get the refresh interval in episodes.

        :return:
            Refresh interval.
        """

        return self._refresh_interval

    def get_window_title(self) -> str:
        """
        Get the figure window title.

        :return:
            Window title.
        """

        return self._window_title


class SingleAgentLivePlotter:
    """
    Live plotter for single-agent training summaries.

    :param plot_config:
        Live plotting configuration.
    """

    __slots__ = (
        "_plot_config",
        "_enabled",
        "_plt",
        "_figure",
        "_axes",
        "_episode_indices",
        "_reward_values",
        "_actor_loss_values",
        "_value_loss_values",
        "_entropy_values",
        "_secure_rate_values",
        "_pf_convergence_values",
        "_voltage_violation_values",
        "_overload_violation_values",
        "_maximum_loading_values",
    )

    def __init__(self, plot_config: LivePlotConfig | None = None) -> None:
        plot_config_obj: LivePlotConfig = LivePlotConfig() if plot_config is None else plot_config
        self._plot_config: LivePlotConfig = plot_config_obj
        self._enabled: bool = False
        self._plt: Any = None
        self._figure: Any = None
        self._axes: Any = None
        self._episode_indices: list[int] = list()
        self._reward_values: list[float] = list()
        self._actor_loss_values: list[float] = list()
        self._value_loss_values: list[float] = list()
        self._entropy_values: list[float] = list()
        self._secure_rate_values: list[float] = list()
        self._pf_convergence_values: list[float] = list()
        self._voltage_violation_values: list[float] = list()
        self._overload_violation_values: list[float] = list()
        self._maximum_loading_values: list[float] = list()
        self._initialize_backend()

    def is_enabled(self) -> bool:
        """
        Check whether the live plotter is active.

        :return:
            ``True`` when plotting is active.
        """

        return self._enabled

    def update(self, episode_summary: Any) -> None:
        """
        Update the live figure from one single-agent episode summary.

        :param episode_summary:
            Single-agent episode summary object.
        :return:
            ``None``.
        """

        self._episode_indices.append(episode_summary.get_episode_idx())
        self._reward_values.append(episode_summary.get_total_reward())
        self._actor_loss_values.append(episode_summary.get_actor_loss())
        self._value_loss_values.append(episode_summary.get_value_loss())
        self._entropy_values.append(episode_summary.get_entropy())
        grid_metrics = episode_summary.get_grid_metric_summary()
        self._secure_rate_values.append(grid_metrics.get_secure_rate())
        self._pf_convergence_values.append(grid_metrics.get_pf_convergence_rate())
        self._voltage_violation_values.append(grid_metrics.get_mean_voltage_violation())
        self._overload_violation_values.append(grid_metrics.get_mean_overload_violation())
        self._maximum_loading_values.append(grid_metrics.get_mean_maximum_branch_loading())

        if self._enabled and should_refresh_plot(
            episode_idx=episode_summary.get_episode_idx(),
            refresh_interval=self._plot_config.get_refresh_interval(),
        ):
            self._redraw_single_agent()
        else:
            episode_summary = episode_summary

    def close(self) -> None:
        """
        Close the live plotting window.

        :return:
            ``None``.
        """

        if self._enabled:
            self._plt.ioff()
            self._plt.show(block=False)
        else:
            self._enabled = self._enabled

    def _initialize_backend(self) -> None:
        """
        Initialize matplotlib in interactive mode when available.

        :return:
            ``None``.
        """

        if self._plot_config.get_enabled():
            try:
                import matplotlib.pyplot as plt
            except ImportError:
                self._enabled = False
                self._plt = None
                self._figure = None
                self._axes = None
            else:
                self._enabled = True
                self._plt = plt
                self._plt.ion()
                self._figure, self._axes = self._plt.subplots(3, 2, figsize=(14, 10))
                self._figure.canvas.manager.set_window_title(self._plot_config.get_window_title())
                self._figure.tight_layout()
        else:
            self._enabled = False
            self._plt = None
            self._figure = None
            self._axes = None

    def _redraw_single_agent(self) -> None:
        """
        Redraw the single-agent monitoring figure.

        :return:
            ``None``.
        """

        reward_axis = self._axes[0, 0]
        actor_axis = self._axes[0, 1]
        value_axis = self._axes[1, 0]
        entropy_axis = self._axes[1, 1]
        rate_axis = self._axes[2, 0]
        violation_axis = self._axes[2, 1]

        clear_and_plot_axis(
            axis=reward_axis,
            x_values=self._episode_indices,
            y_values=self._reward_values,
            title="Episode Reward",
            y_label="Reward",
        )
        clear_and_plot_axis(
            axis=actor_axis,
            x_values=self._episode_indices,
            y_values=self._actor_loss_values,
            title="Actor Loss",
            y_label="Loss",
        )
        clear_and_plot_axis(
            axis=value_axis,
            x_values=self._episode_indices,
            y_values=self._value_loss_values,
            title="Value Loss",
            y_label="Loss",
        )
        clear_and_plot_axis(
            axis=entropy_axis,
            x_values=self._episode_indices,
            y_values=self._entropy_values,
            title="Entropy",
            y_label="Entropy",
        )
        clear_axis(rate_axis, "Grid Rates", "Rate")
        plot_metric_series(
            axis=rate_axis,
            x_values=self._episode_indices,
            y_values=self._secure_rate_values,
            label="secure_rate",
        )
        plot_metric_series(
            axis=rate_axis,
            x_values=self._episode_indices,
            y_values=self._pf_convergence_values,
            label="pf_convergence_rate",
        )
        finalize_axis_legend(rate_axis)
        clear_axis(violation_axis, "Grid Violations", "Metric")
        plot_metric_series(
            axis=violation_axis,
            x_values=self._episode_indices,
            y_values=self._voltage_violation_values,
            label="voltage_violation",
        )
        plot_metric_series(
            axis=violation_axis,
            x_values=self._episode_indices,
            y_values=self._overload_violation_values,
            label="overload_violation",
        )
        plot_metric_series(
            axis=violation_axis,
            x_values=self._episode_indices,
            y_values=self._maximum_loading_values,
            label="max_loading",
        )
        finalize_axis_legend(violation_axis)

        self._figure.tight_layout()
        self._figure.canvas.draw_idle()
        self._plt.pause(0.001)


class MultiAgentLivePlotter:
    """
    Live plotter for multi-agent training summaries.

    :param plot_config:
        Live plotting configuration.
    """

    __slots__ = (
        "_plot_config",
        "_enabled",
        "_plt",
        "_figure",
        "_reward_axis",
        "_loss_axis",
        "_control_axis",
        "_grid_axis",
        "_episode_indices",
        "_group_reward_series",
        "_group_actor_loss_series",
        "_group_aggression_series",
        "_group_random_action_probability_series",
        "_secure_rate_values",
        "_pf_convergence_values",
        "_voltage_violation_values",
        "_overload_violation_values",
        "_maximum_loading_values",
    )

    def __init__(self, plot_config: LivePlotConfig | None = None) -> None:
        plot_config_obj: LivePlotConfig = LivePlotConfig(
            window_title="AI Operator Multi-Agent Monitor"
        ) if plot_config is None else plot_config
        self._plot_config: LivePlotConfig = plot_config_obj
        self._enabled: bool = False
        self._plt: Any = None
        self._figure: Any = None
        self._reward_axis: Any = None
        self._loss_axis: Any = None
        self._control_axis: Any = None
        self._grid_axis: Any = None
        self._episode_indices: list[int] = list()
        self._group_reward_series: dict[str, list[float]] = dict()
        self._group_actor_loss_series: dict[str, list[float]] = dict()
        self._group_aggression_series: dict[str, list[float]] = dict()
        self._group_random_action_probability_series: dict[str, list[float]] = dict()
        self._secure_rate_values: list[float] = list()
        self._pf_convergence_values: list[float] = list()
        self._voltage_violation_values: list[float] = list()
        self._overload_violation_values: list[float] = list()
        self._maximum_loading_values: list[float] = list()
        self._initialize_backend()

    def is_enabled(self) -> bool:
        """
        Check whether the live plotter is active.

        :return:
            ``True`` when plotting is active.
        """

        return self._enabled

    def update(self, episode_summary: Any) -> None:
        """
        Update the live figure from one multi-agent episode summary.

        :param episode_summary:
            Multi-agent episode summary object.
        :return:
            ``None``.
        """

        self._episode_indices.append(episode_summary.get_episode_idx())
        group_summaries: list[Any] = episode_summary.get_group_summaries()
        group_idx: int

        for group_idx in range(len(group_summaries)):
            group_summary: Any = group_summaries[group_idx]
            group_name: str = group_summary.get_policy_group()
            append_group_metric(
                metric_series=self._group_reward_series,
                group_name=group_name,
                value=group_summary.get_total_reward(),
                expected_size=len(self._episode_indices),
            )
            append_group_metric(
                metric_series=self._group_actor_loss_series,
                group_name=group_name,
                value=group_summary.get_actor_loss(),
                expected_size=len(self._episode_indices),
            )
            append_group_metric(
                metric_series=self._group_aggression_series,
                group_name=group_name,
                value=group_summary.get_aggression_scale(),
                expected_size=len(self._episode_indices),
            )
            append_group_metric(
                metric_series=self._group_random_action_probability_series,
                group_name=group_name,
                value=group_summary.get_random_action_probability(),
                expected_size=len(self._episode_indices),
            )

        grid_metrics = episode_summary.get_grid_metric_summary()
        self._secure_rate_values.append(grid_metrics.get_secure_rate())
        self._pf_convergence_values.append(grid_metrics.get_pf_convergence_rate())
        self._voltage_violation_values.append(grid_metrics.get_mean_voltage_violation())
        self._overload_violation_values.append(grid_metrics.get_mean_overload_violation())
        self._maximum_loading_values.append(grid_metrics.get_mean_maximum_branch_loading())

        if self._enabled and should_refresh_plot(
            episode_idx=episode_summary.get_episode_idx(),
            refresh_interval=self._plot_config.get_refresh_interval(),
        ):
            self._redraw_multi_agent()
        else:
            episode_summary = episode_summary

    def close(self) -> None:
        """
        Close the live plotting window.

        :return:
            ``None``.
        """

        if self._enabled:
            self._plt.ioff()
            self._plt.show(block=False)
        else:
            self._enabled = self._enabled

    def _initialize_backend(self) -> None:
        """
        Initialize matplotlib in interactive mode when available.

        :return:
            ``None``.
        """

        if self._plot_config.get_enabled():
            try:
                import matplotlib.pyplot as plt
            except ImportError:
                self._enabled = False
                self._plt = None
                self._figure = None
                self._reward_axis = None
                self._loss_axis = None
                self._control_axis = None
                self._grid_axis = None
            else:
                self._enabled = True
                self._plt = plt
                self._plt.ion()
                self._figure, axes = self._plt.subplots(2, 2, figsize=(14, 10))
                flat_axes = axes.ravel()
                self._reward_axis = flat_axes[0]
                self._loss_axis = flat_axes[1]
                self._control_axis = flat_axes[2]
                self._grid_axis = flat_axes[3]
                self._figure.canvas.manager.set_window_title(self._plot_config.get_window_title())
                self._figure.tight_layout()
        else:
            self._enabled = False
            self._plt = None
            self._figure = None
            self._reward_axis = None
            self._loss_axis = None
            self._control_axis = None
            self._grid_axis = None

    def _redraw_multi_agent(self) -> None:
        """
        Redraw the multi-agent monitoring figure.

        :return:
            ``None``.
        """

        clear_axis(self._reward_axis, "Policy Group Reward", "Reward")
        clear_axis(self._loss_axis, "Policy Group Actor Loss", "Loss")
        clear_axis(self._control_axis, "Attacker Dynamics", "Value")
        clear_axis(self._grid_axis, "Grid Metrics", "Metric")
        plot_group_series(
            axis=self._reward_axis,
            episode_indices=self._episode_indices,
            metric_series=self._group_reward_series,
        )
        plot_group_series(
            axis=self._loss_axis,
            episode_indices=self._episode_indices,
            metric_series=self._group_actor_loss_series,
        )
        plot_group_series(
            axis=self._control_axis,
            episode_indices=self._episode_indices,
            metric_series=self._group_aggression_series,
        )
        plot_group_series(
            axis=self._control_axis,
            episode_indices=self._episode_indices,
            metric_series=rename_group_series(self._group_random_action_probability_series, "rand_prob"),
        )
        plot_metric_series(
            axis=self._grid_axis,
            x_values=self._episode_indices,
            y_values=self._secure_rate_values,
            label="secure_rate",
        )
        plot_metric_series(
            axis=self._grid_axis,
            x_values=self._episode_indices,
            y_values=self._pf_convergence_values,
            label="pf_convergence_rate",
        )
        plot_metric_series(
            axis=self._grid_axis,
            x_values=self._episode_indices,
            y_values=self._voltage_violation_values,
            label="voltage_violation",
        )
        plot_metric_series(
            axis=self._grid_axis,
            x_values=self._episode_indices,
            y_values=self._overload_violation_values,
            label="overload_violation",
        )
        plot_metric_series(
            axis=self._grid_axis,
            x_values=self._episode_indices,
            y_values=self._maximum_loading_values,
            label="max_loading",
        )
        finalize_axis_legend(self._control_axis)
        finalize_axis_legend(self._grid_axis)
        self._figure.tight_layout()
        self._figure.canvas.draw_idle()
        self._plt.pause(0.001)


def should_refresh_plot(episode_idx: int, refresh_interval: int) -> bool:
    """
    Decide whether the plot should refresh at the current episode.

    :param episode_idx:
        One-based episode index.
    :param refresh_interval:
        Number of episodes between redraws.
    :return:
        ``True`` when a redraw should happen.
    """

    if refresh_interval > 0:
        return episode_idx % refresh_interval == 0
    else:
        return False


def clear_and_plot_axis(
    axis: Any,
    x_values: list[int],
    y_values: list[float],
    title: str,
    y_label: str,
) -> None:
    """
    Clear one axis and draw a single metric line.

    :param axis:
        Matplotlib axis.
    :param x_values:
        Episode indices.
    :param y_values:
        Metric values.
    :param title:
        Axis title.
    :param y_label:
        Axis y label.
    :return:
        ``None``.
    """

    axis.clear()
    axis.plot(x_values, y_values)
    axis.set_title(title)
    axis.set_xlabel("Episode")
    axis.set_ylabel(y_label)
    axis.grid(True)


def clear_axis(axis: Any, title: str, y_label: str) -> None:
    """
    Clear one axis and apply common formatting.

    :param axis:
        Matplotlib axis.
    :param title:
        Axis title.
    :param y_label:
        Axis y label.
    :return:
        ``None``.
    """

    axis.clear()
    axis.set_title(title)
    axis.set_xlabel("Episode")
    axis.set_ylabel(y_label)
    axis.grid(True)


def append_group_metric(
    metric_series: dict[str, list[float]],
    group_name: str,
    value: float,
    expected_size: int,
) -> None:
    """
    Append one group metric value while keeping aligned series lengths.

    :param metric_series:
        Metric dictionary keyed by policy group.
    :param group_name:
        Policy group name.
    :param value:
        Metric value to append.
    :param expected_size:
        Target series length after append.
    :return:
        ``None``.
    """

    if group_name in metric_series:
        series: list[float] = metric_series[group_name]
    else:
        series = list()
        metric_series[group_name] = series

    while len(series) < expected_size - 1:
        series.append(float("nan"))

    series.append(value)


def plot_group_series(
    axis: Any,
    episode_indices: list[int],
    metric_series: dict[str, list[float]],
) -> None:
    """
    Plot one metric for all policy groups.

    :param axis:
        Matplotlib axis.
    :param episode_indices:
        Episode indices.
    :param metric_series:
        Metric values keyed by policy group.
    :return:
        ``None``.
    """

    group_names: list[str] = list(metric_series.keys())
    group_idx: int

    for group_idx in range(len(group_names)):
        group_name: str = group_names[group_idx]
        axis.plot(episode_indices, metric_series[group_name], label=group_name)

    if len(group_names) > 0:
        axis.legend()
    else:
        group_idx = 0


def plot_metric_series(axis: Any, x_values: list[int], y_values: list[float], label: str) -> None:
    """
    Plot one named metric series on an existing axis.

    :param axis:
        Matplotlib axis.
    :param x_values:
        Episode indices.
    :param y_values:
        Metric values.
    :param label:
        Legend label.
    :return:
        ``None``.
    """

    axis.plot(x_values, y_values, label=label)


def finalize_axis_legend(axis: Any) -> None:
    """
    Attach a legend to one axis when it contains plotted series.

    :param axis:
        Matplotlib axis.
    :return:
        ``None``.
    """

    handles, labels = axis.get_legend_handles_labels()
    if len(labels) > 0:
        axis.legend()
    else:
        handles = handles


def rename_group_series(metric_series: dict[str, list[float]], suffix: str) -> dict[str, list[float]]:
    """
    Build a relabeled view of one group metric dictionary.

    :param metric_series:
        Original metric dictionary.
    :param suffix:
        Label suffix to append.
    :return:
        Relabeled metric dictionary.
    """

    renamed_series: dict[str, list[float]] = dict()
    group_names: list[str] = list(metric_series.keys())
    group_idx: int

    for group_idx in range(len(group_names)):
        group_name: str = group_names[group_idx]
        renamed_series[f"{group_name}_{suffix}"] = metric_series[group_name]

    return renamed_series
