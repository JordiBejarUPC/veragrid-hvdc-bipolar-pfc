from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from VeraGridEngine.Devices.Profiles.profile_bool import ProfileBool


class TrackProfile:
    """
    Light wrapper binding a track name to a boolean profile.
    """

    __slots__ = ("_name", "_profile")

    def __init__(self, name: str, profile: ProfileBool) -> None:
        """
        Build a track wrapper.

        :param name: User-facing track name.
        :param profile: Boolean profile edited by the track.
        """
        self._name: str = name
        self._profile: ProfileBool = profile

    @property
    def name(self) -> str:
        """
        Get the track name.

        :return: Track name.
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """
        Set the track name.

        :param value: New track name.
        :return: ``None``.
        """
        self._name = value

    @property
    def profile(self) -> ProfileBool:
        """
        Get the bound profile.

        :return: Bound profile.
        """
        return self._profile


class TrackCollection:
    """
    Shared track state for the DAW-style editor.
    """

    __slots__ = ("_tracks", "_time_values")

    def __init__(self, tracks: list[TrackProfile], time_values: list[datetime]) -> None:
        """
        Build the collection.

        :param tracks: Track list.
        :param time_values: Timeline values.
        """
        self._tracks: list[TrackProfile] = tracks
        self._time_values: list[datetime] = time_values
        self._normalize_all_profiles()

    @property
    def step_count(self) -> int:
        """
        Get the timeline length.

        :return: Number of steps.
        """
        return len(self._time_values)

    @property
    def time_values(self) -> list[datetime]:
        """
        Get the timeline values.

        :return: Timeline values.
        """
        return self._time_values

    def get_track_count(self) -> int:
        """
        Get the number of tracks.

        :return: Track count.
        """
        return len(self._tracks)

    def get_track(self, row: int) -> TrackProfile:
        """
        Get one track.

        :param row: Track row.
        :return: Track wrapper.
        """
        return self._tracks[row]

    def get_tracks(self) -> list[TrackProfile]:
        """
        Get all tracks.

        :return: Track list.
        """
        return self._tracks

    def _normalize_profile(self, profile: ProfileBool) -> np.ndarray:
        """
        Force one profile to match the current timeline length.

        :param profile: Profile to normalize.
        :return: Dense boolean array.
        """
        dense_array: np.ndarray = np.full(self.step_count, profile.default_value, dtype=bool)
        current_size: int = profile.size()

        if current_size > 0:
            source_array: np.ndarray = profile.toarray().astype(bool, copy=False)
            copy_size: int = min(current_size, self.step_count)
            dense_array[:copy_size] = source_array[:copy_size]
        else:
            dense_array = dense_array

        profile.set(dense_array)
        return dense_array

    def _normalize_all_profiles(self) -> None:
        """
        Normalize all profiles to the timeline length.

        :return: ``None``.
        """
        track: TrackProfile
        for track in self._tracks:
            self._normalize_profile(track.profile)

    def get_dense_array(self, row: int) -> np.ndarray:
        """
        Get one profile as a dense boolean array.

        :param row: Track row.
        :return: Dense boolean array.
        """
        return self._normalize_profile(self._tracks[row].profile)

    def set_step(self, row: int, column: int, value: bool) -> None:
        """
        Set one timeline step.

        :param row: Track row.
        :param column: Time step.
        :param value: Boolean state to store.
        :return: ``None``.
        """
        dense_array: np.ndarray = self.get_dense_array(row)
        dense_array[column] = value
        self._tracks[row].profile.set(dense_array)

    def fill_track(self, row: int, value: bool) -> None:
        """
        Fill a whole track with one value.

        :param row: Track row.
        :param value: Boolean state to store.
        :return: ``None``.
        """
        dense_array: np.ndarray = np.full(self.step_count, value, dtype=bool)
        self._tracks[row].profile.set(dense_array)

    def get_row_intervals(self, row: int) -> list[tuple[int, int]]:
        """
        Get contiguous active intervals for one track.

        :param row: Track row.
        :return: Inclusive intervals.
        """
        dense_array: np.ndarray = self.get_dense_array(row)
        intervals: list[tuple[int, int]] = list()
        start_column: int = -1
        column: int
        for column in range(self.step_count):
            cell_active: bool = bool(dense_array[column])
            if cell_active and start_column < 0:
                start_column = column
            else:
                if (not cell_active) and start_column >= 0:
                    intervals.append((start_column, column - 1))
                    start_column = -1
                else:
                    pass

        if start_column >= 0:
            intervals.append((start_column, self.step_count - 1))
        else:
            pass

        return intervals

    def set_row_intervals(self, row: int, intervals: list[tuple[int, int]]) -> None:
        """
        Rewrite one profile from inclusive intervals.

        :param row: Track row.
        :param intervals: Inclusive active intervals.
        :return: ``None``.
        """
        dense_array: np.ndarray = np.zeros(self.step_count, dtype=bool)
        start_column: int
        end_column: int
        for start_column, end_column in intervals:
            dense_array[start_column:end_column + 1] = True
        self._tracks[row].profile.set(dense_array)

    def add_interval(self, row: int, start_column: int, end_column: int) -> None:
        """
        Add one active interval to a track.

        :param row: Track row.
        :param start_column: First active column.
        :param end_column: Last active column.
        :return: ``None``.
        """
        intervals: list[tuple[int, int]] = self.get_row_intervals(row)
        intervals.append((start_column, end_column))
        normalized_intervals: list[tuple[int, int]] = merge_intervals(intervals)
        self.set_row_intervals(row, normalized_intervals)

    def delete_interval(self, row: int, start_column: int, end_column: int) -> None:
        """
        Delete one active interval from a track.

        :param row: Track row.
        :param start_column: First active column.
        :param end_column: Last active column.
        :return: ``None``.
        """
        intervals: list[tuple[int, int]] = self.get_row_intervals(row)
        new_intervals: list[tuple[int, int]] = list()

        interval_start: int
        interval_end: int
        for interval_start, interval_end in intervals:
            if interval_start == start_column and interval_end == end_column:
                pass
            else:
                new_intervals.append((interval_start, interval_end))

        self.set_row_intervals(row, new_intervals)

    def add_track(self, name: str) -> None:
        """
        Add a new empty track.

        :param name: Track name.
        :return: ``None``.
        """
        profile: ProfileBool = ProfileBool(default_value=False)
        profile.set(np.zeros(self.step_count, dtype=bool))
        self._tracks.append(TrackProfile(name=name, profile=profile))

    def remove_track(self, row: int) -> None:
        """
        Remove one track.

        :param row: Track row.
        :return: ``None``.
        """
        if 0 <= row < len(self._tracks):
            self._tracks.pop(row)
        else:
            pass


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Merge overlapping or touching inclusive intervals.

    :param intervals: Inclusive intervals.
    :return: Normalized intervals.
    """
    if len(intervals) == 0:
        return list()
    else:
        sorted_intervals: list[tuple[int, int]] = sorted(intervals)
        merged_intervals: list[tuple[int, int]] = list()
        current_start: int = sorted_intervals[0][0]
        current_end: int = sorted_intervals[0][1]

        start_column: int
        end_column: int
        for start_column, end_column in sorted_intervals[1:]:
            if start_column <= current_end + 1:
                current_end = max(current_end, end_column)
            else:
                merged_intervals.append((current_start, current_end))
                current_start = start_column
                current_end = end_column

        merged_intervals.append((current_start, current_end))
        return merged_intervals


class TrackHeadersWidget(QtWidgets.QWidget):
    """
    Left-side header panel showing track names and selection.
    """

    selectedRowChanged = QtCore.Signal(int)

    __slots__ = ("_collection", "_selected_row", "_row_height", "_header_width")

    def __init__(self, collection: TrackCollection, row_height: int = 56, header_width: int = 220) -> None:
        """
        Build the header widget.

        :param collection: Shared track data.
        :param row_height: Height of each track lane.
        :param header_width: Width of the header panel.
        """
        QtWidgets.QWidget.__init__(self)
        self._collection: TrackCollection = collection
        self._selected_row: int = 0
        self._row_height: int = row_height
        self._header_width: int = header_width
        self.setMinimumWidth(self._header_width)

    def get_row_height(self) -> int:
        """
        Get the track lane height.

        :return: Row height.
        """
        return self._row_height

    def set_selected_row(self, row: int) -> None:
        """
        Set the selected track row.

        :param row: Track row.
        :return: ``None``.
        """
        self._selected_row = row
        self.update()

    def refresh_size(self) -> None:
        """
        Refresh the widget height after track changes.

        :return: ``None``.
        """
        total_height: int = max(1, self._collection.get_track_count() * self._row_height)
        self.setMinimumHeight(total_height)
        self.resize(self._header_width, total_height)
        self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Select a track by clicking its header.

        :param event: Mouse event.
        :return: ``None``.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            row: int = int(event.position().y()) // self._row_height
            if 0 <= row < self._collection.get_track_count():
                self.set_selected_row(row)
                self.selectedRowChanged.emit(row)
                event.accept()
            else:
                QtWidgets.QWidget.mousePressEvent(self, event)
        else:
            QtWidgets.QWidget.mousePressEvent(self, event)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """
        Paint the track headers.

        :param event: Qt paint event.
        :return: ``None``.
        """
        del event
        painter: QtGui.QPainter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("#11151b"))

        row: int
        for row in range(self._collection.get_track_count()):
            top: int = row * self._row_height
            row_rect: QtCore.QRect = QtCore.QRect(0, top, self.width(), self._row_height)

            if row == self._selected_row:
                row_color: QtGui.QColor = QtGui.QColor("#1d2a3a")
            else:
                row_color = QtGui.QColor("#161c24")
            painter.fillRect(row_rect.adjusted(0, 0, 0, -1), row_color)

            painter.setPen(QtGui.QPen(QtGui.QColor("#2d3642")))
            painter.drawLine(0, top + self._row_height - 1, self.width(), top + self._row_height - 1)

            track: TrackProfile = self._collection.get_track(row)
            track_array: np.ndarray = self._collection.get_dense_array(row)
            active_count: int = int(np.count_nonzero(track_array))

            painter.setPen(QtGui.QPen(QtGui.QColor("#f3f5f7")))
            name_rect: QtCore.QRect = row_rect.adjusted(14, 10, -14, -24)
            painter.drawText(name_rect, int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter), track.name)

            painter.setPen(QtGui.QPen(QtGui.QColor("#8c9bad")))
            info_rect: QtCore.QRect = row_rect.adjusted(14, 28, -14, -8)
            painter.drawText(
                info_rect,
                int(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter),
                f"{active_count} active steps",
            )

        painter.end()


class TimelineRulerWidget(QtWidgets.QWidget):
    """
    Top ruler showing the timeline steps.
    """

    zoomRequested = QtCore.Signal(int, float)

    __slots__ = ("_collection", "_step_width", "_ruler_height")

    def __init__(self, collection: TrackCollection, step_width: int = 28, ruler_height: int = 30) -> None:
        """
        Build the ruler widget.

        :param collection: Shared track data.
        :param step_width: Width of each timeline step.
        :param ruler_height: Height of the ruler.
        """
        QtWidgets.QWidget.__init__(self)
        self._collection: TrackCollection = collection
        self._step_width: int = step_width
        self._ruler_height: int = ruler_height
        self.refresh_size()

    def refresh_size(self) -> None:
        """
        Refresh the ruler width.

        :return: ``None``.
        """
        total_width: int = self._collection.step_count * self._step_width
        self.setMinimumSize(total_width, self._ruler_height)
        self.resize(total_width, self._ruler_height)
        self.update()

    def set_step_width(self, value: int) -> None:
        """
        Set the current time-axis step width.

        :param value: New step width in pixels.
        :return: ``None``.
        """
        self._step_width = value
        self.refresh_size()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """
        Paint the ruler.

        :param event: Qt paint event.
        :return: ``None``.
        """
        del event
        painter: QtGui.QPainter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("#0f1318"))

        step: int
        for step in range(self._collection.step_count):
            left: int = step * self._step_width
            cell_rect: QtCore.QRect = QtCore.QRect(left, 0, self._step_width, self.height())

            if step % 4 == 0:
                background_color: QtGui.QColor = QtGui.QColor("#151b23")
            else:
                background_color = QtGui.QColor("#11161d")
            painter.fillRect(cell_rect.adjusted(0, 0, -1, 0), background_color)

            painter.setPen(QtGui.QPen(QtGui.QColor("#2d3642")))
            painter.drawLine(left, 0, left, self.height())

            painter.setPen(QtGui.QPen(QtGui.QColor("#90a0b3")))
            painter.drawText(
                cell_rect.adjusted(0, 0, 0, -2),
                int(QtCore.Qt.AlignmentFlag.AlignCenter | QtCore.Qt.AlignmentFlag.AlignBottom),
                self._format_time_label(step),
            )

        painter.setPen(QtGui.QPen(QtGui.QColor("#2d3642")))
        painter.drawLine(self.rect().bottomLeft(), self.rect().bottomRight())
        painter.end()

    def _format_time_label(self, step: int) -> str:
        """
        Format one ruler label from the time profile.

        :param step: Time index.
        :return: Compact time label.
        """
        time_value: datetime = self._collection.time_values[step]
        if self._collection.step_count > 24:
            return time_value.strftime("%H:%M")
        else:
            return time_value.strftime("%H:%M\n%d")

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """
        Request horizontal zoom from the mouse wheel.

        :param event: Mouse wheel event.
        :return: ``None``.
        """
        delta_y: int = event.angleDelta().y()
        if delta_y != 0:
            self.zoomRequested.emit(delta_y, float(event.position().x()))
            event.accept()
        else:
            QtWidgets.QWidget.wheelEvent(self, event)


class TrackClipWidget(QtWidgets.QFrame):
    """
    Continuous clip widget with resize handles.
    """

    clipChanged = QtCore.Signal(int, int, int, int)
    clipEditFinished = QtCore.Signal(int)
    clipDeleteRequested = QtCore.Signal(int, int, int)
    clipSelected = QtCore.Signal(int)
    clipSplitRequested = QtCore.Signal(int, int, int, int)

    __slots__ = (
        "_row",
        "_start_column",
        "_end_column",
        "_step_width",
        "_row_height",
        "_selected",
        "_drag_mode",
        "_press_global_x",
        "_initial_start",
        "_initial_end",
    )

    def __init__(self, row: int, start_column: int, end_column: int, step_width: int, row_height: int, parent: QtWidgets.QWidget) -> None:
        """
        Build a clip widget.

        :param row: Track row.
        :param start_column: First active column.
        :param end_column: Last active column.
        :param step_width: Width of one time step.
        :param row_height: Height of one track lane.
        :param parent: Parent widget.
        """
        QtWidgets.QFrame.__init__(self, parent)
        self._row: int = row
        self._start_column: int = start_column
        self._end_column: int = end_column
        self._step_width: int = step_width
        self._row_height: int = row_height
        self._selected: bool = False
        self._drag_mode: str = ""
        self._press_global_x: int = 0
        self._initial_start: int = start_column
        self._initial_end: int = end_column
        self.setMouseTracking(True)
        self._update_geometry()

    def get_row(self) -> int:
        """
        Get the track row.

        :return: Track row.
        """
        return self._row

    def get_start_column(self) -> int:
        """
        Get the first active time index.

        :return: Start column.
        """
        return self._start_column

    def get_end_column(self) -> int:
        """
        Get the last active time index.

        :return: End column.
        """
        return self._end_column

    def set_selected(self, value: bool) -> None:
        """
        Set the selection state.

        :param value: Selection state.
        :return: ``None``.
        """
        self._selected = value
        self.update()

    def _update_geometry(self) -> None:
        """
        Place the widget in the timeline lane.

        :return: ``None``.
        """
        left: int = self._start_column * self._step_width + 2
        top: int = self._row * self._row_height + 8
        width: int = max(12, (self._end_column - self._start_column + 1) * self._step_width - 4)
        height: int = self._row_height - 16
        self.setGeometry(left, top, width, height)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """
        Paint the clip body and resize handles.

        :param event: Qt paint event.
        :return: ``None``.
        """
        del event
        painter: QtGui.QPainter = QtGui.QPainter(self)

        if self._selected:
            fill_color: QtGui.QColor = QtGui.QColor("#5fd980")
            border_color: QtGui.QColor = QtGui.QColor("#daf8df")
        else:
            fill_color = QtGui.QColor("#59c173")
            border_color = QtGui.QColor("#9be2ad")

        painter.fillRect(self.rect(), fill_color)
        painter.setPen(QtGui.QPen(border_color, 2))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        handle_color: QtGui.QColor = QtGui.QColor("#effff1")
        painter.fillRect(QtCore.QRect(0, 0, 6, self.height()), handle_color)
        painter.fillRect(QtCore.QRect(self.width() - 6, 0, 6, self.height()), handle_color)

        painter.setPen(QtGui.QPen(QtGui.QColor("#2e6c40")))
        tick_x: int = self._step_width
        while tick_x < self.width():
            painter.drawLine(tick_x, 2, tick_x, self.height() - 2)
            tick_x += self._step_width

        painter.end()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Start a move or resize gesture.

        :param event: Mouse event.
        :return: ``None``.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clipSelected.emit(self._row)
            self._selected = True
            self._press_global_x = int(event.globalPosition().x())
            self._initial_start = self._start_column
            self._initial_end = self._end_column
            local_x: int = int(event.position().x())

            if local_x <= 8:
                self._drag_mode = "left"
            else:
                if local_x >= self.width() - 8:
                    self._drag_mode = "right"
                else:
                    self._drag_mode = "move"
            event.accept()
        else:
            QtWidgets.QFrame.mousePressEvent(self, event)

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Continue a move or resize gesture.

        :param event: Mouse event.
        :return: ``None``.
        """
        if self._drag_mode == "":
            local_x: int = int(event.position().x())
            if local_x <= 8 or local_x >= self.width() - 8:
                self.setCursor(QtCore.Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor)
            QtWidgets.QFrame.mouseMoveEvent(self, event)
        else:
            delta_steps: int = int(round((int(event.globalPosition().x()) - self._press_global_x) / self._step_width))
            new_start: int = self._initial_start
            new_end: int = self._initial_end

            if self._drag_mode == "left":
                new_start = self._initial_start + delta_steps
                new_start = min(new_start, new_end)
            else:
                if self._drag_mode == "right":
                    new_end = self._initial_end + delta_steps
                    new_end = max(new_end, new_start)
                else:
                    span: int = self._initial_end - self._initial_start
                    new_start = self._initial_start + delta_steps
                    new_end = new_start + span

            self.clipChanged.emit(self._row, self._start_column, self._end_column, self._clamp_and_apply(new_start, new_end))
            event.accept()

    def _clamp_and_apply(self, new_start: int, new_end: int) -> int:
        """
        Apply clamped geometry and report the packed target span.

        :param new_start: Candidate start column.
        :param new_end: Candidate end column.
        :return: Packed integer ``new_start * 100000 + new_end``.
        """
        parent_widget: TrackTimelineWidget = self.parentWidget()  # type: ignore[assignment]
        max_column: int = parent_widget.get_step_count() - 1

        if new_start < 0:
            shift: int = -new_start
            new_start = 0
            if self._drag_mode == "move":
                new_end += shift
            else:
                new_end = new_end
        else:
            new_start = new_start

        if new_end > max_column:
            shift = new_end - max_column
            new_end = max_column
            if self._drag_mode == "move":
                new_start -= shift
            else:
                new_start = new_start
        else:
            new_end = new_end

        new_start = max(0, new_start)
        new_end = min(max_column, new_end)
        new_start = min(new_start, new_end)

        self._start_column = new_start
        self._end_column = new_end
        self._update_geometry()
        return new_start * 100000 + new_end

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        End a move or resize gesture.

        :param event: Mouse event.
        :return: ``None``.
        """
        edited_row: int = self._row
        self._drag_mode = ""
        self.unsetCursor()
        self.clipEditFinished.emit(edited_row)
        QtWidgets.QFrame.mouseReleaseEvent(self, event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Split the clip into two clips when possible.

        :param event: Mouse event.
        :return: ``None``.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            split_column: int = self._start_column + int(event.position().x()) // self._step_width
            if self._start_column < split_column <= self._end_column:
                self.clipSplitRequested.emit(self._row, self._start_column, self._end_column, split_column)
                event.accept()
            else:
                QtWidgets.QFrame.mouseDoubleClickEvent(self, event)
        else:
            QtWidgets.QFrame.mouseDoubleClickEvent(self, event)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        """
        Show the clip context menu.

        :param event: Qt context-menu event.
        :return: ``None``.
        """
        menu: QtWidgets.QMenu = QtWidgets.QMenu(self)
        delete_action: QtGui.QAction = menu.addAction("Delete Clip")
        chosen_action: QtGui.QAction | None = menu.exec(event.globalPos())

        if chosen_action == delete_action:
            self.clipDeleteRequested.emit(self._row, self._start_column, self._end_column)
            event.accept()
        else:
            QtWidgets.QFrame.contextMenuEvent(self, event)


class TrackTimelineWidget(QtWidgets.QWidget):
    """
    Right-side DAW-like timeline canvas.
    """

    selectedRowChanged = QtCore.Signal(int)
    trackDataChanged = QtCore.Signal()
    zoomRequested = QtCore.Signal(int, float)

    __slots__ = (
        "_collection",
        "_row_height",
        "_step_width",
        "_selected_row",
        "_clip_widgets",
        "_default_clip_length",
    )

    def __init__(self, collection: TrackCollection, row_height: int = 56, step_width: int = 28) -> None:
        """
        Build the timeline widget.

        :param collection: Shared track data.
        :param row_height: Height of each track lane.
        :param step_width: Width of each time step.
        """
        QtWidgets.QWidget.__init__(self)
        self._collection: TrackCollection = collection
        self._row_height: int = row_height
        self._step_width: int = step_width
        self._selected_row: int = 0
        self._clip_widgets: list[TrackClipWidget] = list()
        self._default_clip_length: int = 4
        self.refresh_size()
        self._rebuild_clips()

    def get_step_width(self) -> int:
        """
        Get the timeline step width.

        :return: Step width.
        """
        return self._step_width

    def set_step_width(self, value: int) -> None:
        """
        Set the current time-axis step width.

        :param value: New step width in pixels.
        :return: ``None``.
        """
        self._step_width = value
        self.refresh_size()

    def get_row_height(self) -> int:
        """
        Get the lane height.

        :return: Row height.
        """
        return self._row_height

    def get_step_count(self) -> int:
        """
        Get the number of timeline steps.

        :return: Step count.
        """
        return self._collection.step_count

    def set_selected_row(self, row: int) -> None:
        """
        Set the selected track row.

        :param row: Track row.
        :return: ``None``.
        """
        if 0 <= row < self._collection.get_track_count():
            self._selected_row = row
            self._apply_selection_to_clips()
            self.update()
        else:
            pass

    def get_selected_row(self) -> int:
        """
        Get the selected track row.

        :return: Selected row.
        """
        return self._selected_row

    def refresh_size(self) -> None:
        """
        Refresh canvas dimensions after track changes.

        :return: ``None``.
        """
        total_width: int = max(1, self._collection.step_count * self._step_width)
        total_height: int = max(1, self._collection.get_track_count() * self._row_height)
        self.setMinimumSize(total_width, total_height)
        self.resize(total_width, total_height)
        self._rebuild_clips()
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """
        Paint the timeline lanes and time grid.

        :param event: Qt paint event.
        :return: ``None``.
        """
        del event
        painter: QtGui.QPainter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtGui.QColor("#0d1116"))

        row: int
        for row in range(self._collection.get_track_count()):
            top: int = row * self._row_height
            lane_rect: QtCore.QRect = QtCore.QRect(0, top, self.width(), self._row_height)

            if row == self._selected_row:
                lane_color: QtGui.QColor = QtGui.QColor("#172231")
            else:
                lane_color = QtGui.QColor("#10161d")
            painter.fillRect(lane_rect.adjusted(0, 0, 0, -1), lane_color)

            painter.setPen(QtGui.QPen(QtGui.QColor("#27303b")))
            painter.drawLine(0, top + self._row_height - 1, self.width(), top + self._row_height - 1)

            column: int
            for column in range(self._collection.step_count):
                left: int = column * self._step_width

                if column % 4 == 0:
                    vertical_pen: QtGui.QPen = QtGui.QPen(QtGui.QColor("#2a3542"))
                else:
                    vertical_pen = QtGui.QPen(QtGui.QColor("#1d252f"))
                painter.setPen(vertical_pen)
                painter.drawLine(left, top, left, top + self._row_height)

        painter.end()

    def _rebuild_clips(self) -> None:
        """
        Recreate clip widgets from the profiles.

        :return: ``None``.
        """
        clip_widget: TrackClipWidget
        for clip_widget in self._clip_widgets:
            clip_widget.deleteLater()
        self._clip_widgets = list()

        row: int
        for row in range(self._collection.get_track_count()):
            track_array: np.ndarray = self._collection.get_dense_array(row)
            start_column: int = -1
            column: int
            for column in range(self._collection.step_count):
                cell_active: bool = bool(track_array[column])
                if cell_active and start_column < 0:
                    start_column = column
                else:
                    if (not cell_active) and start_column >= 0:
                        self._create_clip_widget(row, start_column, column - 1)
                        start_column = -1
                    else:
                        pass

            if start_column >= 0:
                self._create_clip_widget(row, start_column, self._collection.step_count - 1)
            else:
                pass

        self._apply_selection_to_clips()

    def _create_clip_widget(self, row: int, start_column: int, end_column: int) -> None:
        """
        Create one clip widget.

        :param row: Track row.
        :param start_column: First active column.
        :param end_column: Last active column.
        :return: ``None``.
        """
        clip_widget: TrackClipWidget = TrackClipWidget(
            row=row,
            start_column=start_column,
            end_column=end_column,
            step_width=self._step_width,
            row_height=self._row_height,
            parent=self,
        )
        clip_widget.clipSelected.connect(self._on_clip_selected)
        clip_widget.clipChanged.connect(self._on_clip_changed)
        clip_widget.clipEditFinished.connect(self._on_clip_edit_finished)
        clip_widget.clipDeleteRequested.connect(self._on_clip_delete_requested)
        clip_widget.clipSplitRequested.connect(self._on_clip_split_requested)
        clip_widget.show()
        self._clip_widgets.append(clip_widget)

    def _apply_selection_to_clips(self) -> None:
        """
        Propagate the selected track state to all clip widgets.

        :return: ``None``.
        """
        clip_widget: TrackClipWidget
        for clip_widget in self._clip_widgets:
            clip_widget.set_selected(clip_widget.get_row() == self._selected_row)

    def _on_clip_selected(self, row: int) -> None:
        """
        Handle clip selection.

        :param row: Selected track row.
        :return: ``None``.
        """
        self.set_selected_row(row)
        self.selectedRowChanged.emit(row)

    def _on_clip_changed(self, row: int, old_start: int, old_end: int, packed_span: int) -> None:
        """
        Rewrite one profile after moving or resizing a clip.

        :param row: Track row.
        :param old_start: Previous start column.
        :param old_end: Previous end column.
        :param packed_span: Packed new span.
        :return: ``None``.
        """
        del old_start
        del old_end
        new_start: int = packed_span // 100000
        new_end: int = packed_span % 100000
        del new_start
        del new_end
        self.trackDataChanged.emit()
        self.update()

    def _on_clip_edit_finished(self, row: int) -> None:
        """
        Resolve overlaps and merge touching clips after an edit.

        :param row: Edited track row.
        :return: ``None``.
        """
        intervals: list[tuple[int, int]] = list()
        clip_widget: TrackClipWidget
        for clip_widget in self._clip_widgets:
            if clip_widget.get_row() == row:
                intervals.append((clip_widget.get_start_column(), clip_widget.get_end_column()))
            else:
                pass

        normalized_intervals: list[tuple[int, int]] = merge_intervals(intervals)
        self._collection.set_row_intervals(row, normalized_intervals)
        self._rebuild_clips()
        self.trackDataChanged.emit()
        self.update()

    def _on_clip_split_requested(self, row: int, start_column: int, end_column: int, split_column: int) -> None:
        """
        Split one clip into two intervals.

        :param row: Track row.
        :param start_column: Original start column.
        :param end_column: Original end column.
        :param split_column: First column of the right-side clip.
        :return: ``None``.
        """
        intervals: list[tuple[int, int]] = self._collection.get_row_intervals(row)
        new_intervals: list[tuple[int, int]] = list()
        interval_start: int
        interval_end: int
        for interval_start, interval_end in intervals:
            if interval_start == start_column and interval_end == end_column:
                left_interval: tuple[int, int] = (interval_start, split_column - 1)
                right_interval: tuple[int, int] = (split_column, interval_end)
                if left_interval[0] <= left_interval[1]:
                    new_intervals.append(left_interval)
                else:
                    pass
                if right_interval[0] <= right_interval[1]:
                    new_intervals.append(right_interval)
                else:
                    pass
            else:
                new_intervals.append((interval_start, interval_end))

        self._collection.set_row_intervals(row, merge_intervals(new_intervals))
        self._rebuild_clips()
        self.trackDataChanged.emit()
        self.update()

    def _on_clip_delete_requested(self, row: int, start_column: int, end_column: int) -> None:
        """
        Delete one clip from the selected track.

        :param row: Track row.
        :param start_column: Clip start column.
        :param end_column: Clip end column.
        :return: ``None``.
        """
        self._collection.delete_interval(row, start_column, end_column)
        self._rebuild_clips()
        self.trackDataChanged.emit()
        self.update()

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Select a lane by clicking empty timeline space.

        :param event: Mouse event.
        :return: ``None``.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            row: int = int(event.position().y()) // self._row_height
            if 0 <= row < self._collection.get_track_count():
                self.set_selected_row(row)
                self.selectedRowChanged.emit(row)
                event.accept()
            else:
                QtWidgets.QWidget.mousePressEvent(self, event)
        else:
            QtWidgets.QWidget.mousePressEvent(self, event)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        """
        Add a new default-length clip by double-clicking empty lane space.

        :param event: Mouse event.
        :return: ``None``.
        """
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            row: int = int(event.position().y()) // self._row_height
            column: int = int(event.position().x()) // self._step_width

            row_ok: bool = 0 <= row < self._collection.get_track_count()
            column_ok: bool = 0 <= column < self._collection.step_count
            if row_ok and column_ok:
                self.set_selected_row(row)
                self.selectedRowChanged.emit(row)
                end_column: int = min(column + self._default_clip_length - 1, self._collection.step_count - 1)
                self._collection.add_interval(row, column, end_column)
                self._rebuild_clips()
                self.trackDataChanged.emit()
                self.update()
                event.accept()
            else:
                QtWidgets.QWidget.mouseDoubleClickEvent(self, event)
        else:
            QtWidgets.QWidget.mouseDoubleClickEvent(self, event)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """
        Request horizontal zoom from the mouse wheel.

        :param event: Mouse wheel event.
        :return: ``None``.
        """
        delta_y: int = event.angleDelta().y()
        if delta_y != 0:
            self.zoomRequested.emit(delta_y, float(event.position().x()))
            event.accept()
        else:
            QtWidgets.QWidget.wheelEvent(self, event)


class TrackEditorWidget(QtWidgets.QWidget):
    """
    Example DAW-style editor for several ``ProfileBool`` objects.
    """

    __slots__ = (
        "_collection",
        "_headers_widget",
        "_ruler_widget",
        "_timeline_widget",
        "_headers_scroll",
        "_timeline_scroll",
        "_next_track_number",
        "_min_step_width",
        "_max_step_width",
    )

    def __init__(
        self,
        tracks: Optional[list[TrackProfile]] = None,
        time_values: Optional[list[datetime]] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        """
        Build the editor widget.

        :param tracks: Optional starting tracks.
        :param time_values: Timeline values.
        :param parent: Optional Qt parent.
        """
        QtWidgets.QWidget.__init__(self, parent)

        if tracks is None:
            track_list: list[TrackProfile] = list()
        else:
            track_list = tracks

        if time_values is None:
            timeline_values: list[datetime] = build_demo_time_axis(32)
        else:
            timeline_values = time_values

        self._collection: TrackCollection = TrackCollection(track_list, timeline_values)
        self._headers_widget: TrackHeadersWidget = TrackHeadersWidget(self._collection)
        self._ruler_widget: TimelineRulerWidget = TimelineRulerWidget(self._collection)
        self._timeline_widget: TrackTimelineWidget = TrackTimelineWidget(self._collection)
        self._headers_scroll: QtWidgets.QScrollArea = QtWidgets.QScrollArea()
        self._timeline_scroll: QtWidgets.QScrollArea = QtWidgets.QScrollArea()
        self._next_track_number: int = self._collection.get_track_count() + 1
        self._min_step_width: int = 12
        self._max_step_width: int = 96

        self._build_layout()
        self._connect_widgets()
        self._refresh_editor_geometry()

    def _build_layout(self) -> None:
        """
        Assemble the DAW-like layout.

        :return: ``None``.
        """
        main_layout: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout(self)
        controls_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()

        add_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Add Track")
        remove_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Remove Track")
        fill_on_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Fill On")
        fill_off_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Fill Off")

        controls_layout.addWidget(add_button)
        controls_layout.addWidget(remove_button)
        controls_layout.addWidget(fill_on_button)
        controls_layout.addWidget(fill_off_button)
        controls_layout.addStretch(1)

        self._headers_scroll.setWidget(self._headers_widget)
        self._headers_scroll.setWidgetResizable(False)
        self._headers_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._headers_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._headers_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self._timeline_scroll.setWidget(self._timeline_widget)
        self._timeline_scroll.setWidgetResizable(False)
        self._timeline_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        ruler_container: QtWidgets.QWidget = QtWidgets.QWidget()
        ruler_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout(ruler_container)
        ruler_layout.setContentsMargins(0, 0, 0, 0)
        ruler_layout.setSpacing(0)

        header_corner: QtWidgets.QLabel = QtWidgets.QLabel("Tracks")
        header_corner.setFixedWidth(self._headers_widget.width())
        header_corner.setFixedHeight(self._ruler_widget.height())
        header_corner.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header_corner.setStyleSheet("background:#0f1318;color:#dfe5eb;border-bottom:1px solid #2d3642;")

        ruler_scroll: QtWidgets.QScrollArea = QtWidgets.QScrollArea()
        ruler_scroll.setWidget(self._ruler_widget)
        ruler_scroll.setWidgetResizable(False)
        ruler_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ruler_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ruler_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        ruler_layout.addWidget(header_corner)
        ruler_layout.addWidget(ruler_scroll, 1)

        tracks_container: QtWidgets.QWidget = QtWidgets.QWidget()
        tracks_layout: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout(tracks_container)
        tracks_layout.setContentsMargins(0, 0, 0, 0)
        tracks_layout.setSpacing(0)
        tracks_layout.addWidget(self._headers_scroll)
        tracks_layout.addWidget(self._timeline_scroll, 1)

        main_layout.addLayout(controls_layout)
        main_layout.addWidget(ruler_container)
        main_layout.addWidget(tracks_container, 1)

        add_button.clicked.connect(self.add_track)
        remove_button.clicked.connect(self.remove_selected_track)
        fill_on_button.clicked.connect(self.fill_selected_track_on)
        fill_off_button.clicked.connect(self.fill_selected_track_off)

        # Sync horizontal panning between the ruler and the timeline.
        timeline_horizontal_bar: QtWidgets.QScrollBar = self._timeline_scroll.horizontalScrollBar()
        ruler_horizontal_bar: QtWidgets.QScrollBar = ruler_scroll.horizontalScrollBar()
        timeline_horizontal_bar.valueChanged.connect(ruler_horizontal_bar.setValue)
        ruler_horizontal_bar.valueChanged.connect(timeline_horizontal_bar.setValue)

    def _connect_widgets(self) -> None:
        """
        Connect the shared interaction signals.

        :return: ``None``.
        """
        self._timeline_widget.selectedRowChanged.connect(self._headers_widget.set_selected_row)
        self._headers_widget.selectedRowChanged.connect(self._timeline_widget.set_selected_row)
        self._timeline_widget.trackDataChanged.connect(self._headers_widget.update)
        self._timeline_widget.trackDataChanged.connect(self._timeline_widget.update)
        self._timeline_widget.zoomRequested.connect(self._on_zoom_requested)
        self._ruler_widget.zoomRequested.connect(self._on_zoom_requested)

        # Sync vertical scrolling between headers and lanes.
        timeline_vertical_bar: QtWidgets.QScrollBar = self._timeline_scroll.verticalScrollBar()
        headers_vertical_bar: QtWidgets.QScrollBar = self._headers_scroll.verticalScrollBar()
        timeline_vertical_bar.valueChanged.connect(headers_vertical_bar.setValue)
        headers_vertical_bar.valueChanged.connect(timeline_vertical_bar.setValue)

    def _refresh_editor_geometry(self) -> None:
        """
        Refresh the widgets after structural changes.

        :return: ``None``.
        """
        self._headers_widget.refresh_size()
        self._timeline_widget.refresh_size()
        self._ruler_widget.refresh_size()
        self._headers_widget.update()
        self._timeline_widget.update()

    def _on_zoom_requested(self, delta_y: int, anchor_x: float) -> None:
        """
        Zoom the time axis around the mouse position.

        :param delta_y: Wheel delta.
        :param anchor_x: Mouse x-coordinate in the local zoom source.
        :return: ``None``.
        """
        old_step_width: int = self._timeline_widget.get_step_width()
        if delta_y > 0:
            requested_step_width: int = old_step_width + 4
        else:
            requested_step_width = old_step_width - 4

        new_step_width: int = max(self._min_step_width, min(self._max_step_width, requested_step_width))
        if new_step_width == old_step_width:
            return
        else:
            pass

        horizontal_bar: QtWidgets.QScrollBar = self._timeline_scroll.horizontalScrollBar()
        old_scroll: int = horizontal_bar.value()
        anchor_column: float = (old_scroll + anchor_x) / old_step_width

        self._timeline_widget.set_step_width(new_step_width)
        self._ruler_widget.set_step_width(new_step_width)

        new_scroll: int = int(round(anchor_column * new_step_width - anchor_x))
        horizontal_bar.setValue(max(0, new_scroll))

    def _get_selected_row(self) -> int:
        """
        Get the currently selected row.

        :return: Selected row.
        """
        return self._timeline_widget.get_selected_row()

    def add_track(self) -> None:
        """
        Add a new empty track.

        :return: ``None``.
        """
        name: str = f"Track {self._next_track_number}"
        self._collection.add_track(name)
        self._next_track_number += 1
        self._refresh_editor_geometry()

    def remove_selected_track(self) -> None:
        """
        Remove the selected track.

        :return: ``None``.
        """
        row: int = self._get_selected_row()
        if self._collection.get_track_count() > 0:
            self._collection.remove_track(row)
            if self._collection.get_track_count() > 0:
                new_row: int = min(row, self._collection.get_track_count() - 1)
                self._timeline_widget.set_selected_row(new_row)
                self._headers_widget.set_selected_row(new_row)
            else:
                self._timeline_widget.set_selected_row(0)
                self._headers_widget.set_selected_row(0)
            self._refresh_editor_geometry()
        else:
            pass

    def fill_selected_track_on(self) -> None:
        """
        Fill the selected track with ``True``.

        :return: ``None``.
        """
        if self._collection.get_track_count() > 0:
            row: int = self._get_selected_row()
            self._collection.fill_track(row, True)
            self._timeline_widget.refresh_size()
            self._headers_widget.update()
            self._timeline_widget.update()
        else:
            pass

    def fill_selected_track_off(self) -> None:
        """
        Fill the selected track with ``False``.

        :return: ``None``.
        """
        if self._collection.get_track_count() > 0:
            row: int = self._get_selected_row()
            self._collection.fill_track(row, False)
            self._timeline_widget.refresh_size()
            self._headers_widget.update()
            self._timeline_widget.update()
        else:
            pass

    def get_tracks(self) -> list[TrackProfile]:
        """
        Return the edited tracks.

        :return: Track list.
        """
        return self._collection.get_tracks()


class TrackEditorWindow(QtWidgets.QMainWindow):
    """
    Main window hosting the track editor example.
    """

    __slots__ = ()

    def __init__(self, editor: TrackEditorWidget, parent: Optional[QtWidgets.QWidget] = None) -> None:
        """
        Build the example window.

        :param editor: Central editor widget.
        :param parent: Optional Qt parent.
        """
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setWindowTitle("BoolProfile Track Editor")
        self.resize(1200, 420)
        self.setCentralWidget(editor)


def build_demo_tracks(step_count: int) -> list[TrackProfile]:
    """
    Build a few demo profiles.

    :param step_count: Number of timeline steps.
    :return: Demo track list.
    """
    names: list[str] = ["Generator Active", "Load Connected", "Line Enabled", "Bus Slack"]
    patterns: list[np.ndarray] = list()

    pattern_a: np.ndarray = np.zeros(step_count, dtype=bool)
    pattern_a[1:8] = True
    pattern_a[12:18] = True
    patterns.append(pattern_a)

    pattern_b: np.ndarray = np.zeros(step_count, dtype=bool)
    pattern_b[4:6] = True
    pattern_b[8:14] = True
    pattern_b[24:31] = True
    patterns.append(pattern_b)

    pattern_c: np.ndarray = np.zeros(step_count, dtype=bool)
    pattern_c[6:22] = True
    patterns.append(pattern_c)

    pattern_d: np.ndarray = np.zeros(step_count, dtype=bool)
    pattern_d[0:2] = True
    pattern_d[16:19] = True
    pattern_d[28:32] = True
    patterns.append(pattern_d)

    tracks: list[TrackProfile] = list()
    idx: int
    for idx, name in enumerate(names):
        profile: ProfileBool = ProfileBool(default_value=False)
        profile.set(patterns[idx])
        tracks.append(TrackProfile(name=name, profile=profile))

    return tracks


def build_demo_time_axis(step_count: int) -> list[datetime]:
    """
    Build a simple time profile for the demo.

    :param step_count: Number of time samples.
    :return: Timeline values.
    """
    start_time: datetime = datetime(2026, 7, 14, 0, 0, 0)
    time_values: list[datetime] = list()
    step: int
    for step in range(step_count):
        time_values.append(start_time + timedelta(hours=step))
    return time_values


def main() -> int:
    """
    Run the standalone example.

    :return: Qt exit code.
    """
    app: QtWidgets.QApplication = QtWidgets.QApplication(sys.argv)
    step_count: int = 32
    editor: TrackEditorWidget = TrackEditorWidget(
        tracks=build_demo_tracks(step_count),
        time_values=build_demo_time_axis(step_count),
    )
    window: TrackEditorWindow = TrackEditorWindow(editor=editor)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
