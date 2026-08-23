# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# SPDX-License-Identifier: MPL-2.0

from typing import List, Tuple
from PySide6 import QtCore, QtWidgets
import numpy as np
from VeraGridEngine.Devices.types import ALL_DEV_TYPES
from VeraGridEngine.Utils.Filtering.objects_filtering import FilterObjects
from VeraGrid.Gui.object_model import ObjectsModel


class ObjectModelFilterProxy(QtCore.QSortFilterProxyModel):
    """
    Proxy that delegates the parsing/evaluation of the search expression into an ObjectsModel
    to a `FilterObjects` instance.
    """

    def __init__(self,
                 mdl: ObjectsModel,
                 parent: QtCore.QObject | None = None):
        """
        Constructor
        :param mdl: ObjectsModel
        :param parent: some parent
        """
        super().__init__(parent)

        self._mdl: ObjectsModel = mdl

        # filtering engine already initialized
        self._filter_engine = FilterObjects(self._mdl.objects)

        # indexes allowed after the last call to setExpression()
        self._allowed_rows: set[int] = set(range(len(self._mdl.objects)))

        # set the source model
        super().setSourceModel(mdl)

    @property
    def all_objects(self) -> List[ALL_DEV_TYPES]:
        """
        Return all objects in the underlying source model order.

        :return: Objects in DB/source order.
        """
        return self.get_objects_in_db_order()

    @property
    def objects(self) -> List[ALL_DEV_TYPES]:
        """
        Return objects in the visible proxy order.

        :return: Objects in filtered/sorted display order.
        """
        return self.get_objects_in_display_order()

    def get_objects_in_db_order(self) -> List[ALL_DEV_TYPES]:
        """
        Return all objects in the underlying source model order.

        :return: Objects in DB/source order.
        """
        return self._mdl.objects

    def get_objects_in_display_order(self) -> List[ALL_DEV_TYPES]:
        """
        Return the visible objects in the same order shown by the view.

        :return: Objects in filtered/sorted display order.
        """
        objects: List[ALL_DEV_TYPES] = list()
        row: int
        for row in range(self.rowCount()):
            obj: ALL_DEV_TYPES | None = self.get_object_at_proxy_row(proxy_row=row)
            if obj is not None:
                objects.append(obj)
            else:
                pass
        return objects

    @property
    def attributes(self):
        return self._mdl.attributes

    @QtCore.Slot(str)
    def setExpression(self, expr: str) -> Tuple[bool, str]:
        """
        Call this whenever the user changes the search text.
        """
        has_error = False
        error_txt = ""
        if not expr.strip():
            # empty => show everything
            self._allowed_rows = set(range(len(self.get_objects_in_db_order())))
        else:
            try:
                self._filter_engine.filter(expr)  # updates .filtered_indices
                self._allowed_rows = set(self._filter_engine.filtered_indices)
            except Exception as e:
                # invalid expression: fall back to show none
                error_txt = f"Filter expression error: {e}"
                self._allowed_rows = set()
                has_error = True

        self.invalidateFilter()  # <- triggers filterAcceptsRow()

        return has_error, error_txt

    def source_row(self, proxy_row: int) -> int:
        """
        Convert a visible proxy row into the underlying source row.

        :param proxy_row: Row index in the filtered/sorted proxy.
        :return: Source row index or -1.
        """
        return self.get_source_row_from_proxy_row(proxy_row=proxy_row)

    def get_source_row_from_proxy_row(self, proxy_row: int) -> int:
        """
        Convert a visible proxy row into the underlying source row.

        :param proxy_row: Row index in the filtered/sorted proxy.
        :return: Source row index or -1.
        """
        if proxy_row > -1:
            proxy_index: QtCore.QModelIndex = self.index(proxy_row, 0)
            if proxy_index.isValid():
                return self.mapToSource(proxy_index).row()
            else:
                return -1
        else:
            return -1

    def object_at(self, proxy_row: int) -> ALL_DEV_TYPES | None:
        """
        Return the object shown at one visible proxy row.

        :param proxy_row: Row index in the filtered/sorted proxy.
        :return: Object or None.
        """
        return self.get_object_at_proxy_row(proxy_row=proxy_row)

    def get_object_at_proxy_row(self, proxy_row: int) -> ALL_DEV_TYPES | None:
        """
        Return the object shown at one visible proxy row.

        :param proxy_row: Row index in the filtered/sorted proxy.
        :return: Object or None.
        """
        source_row: int = self.get_source_row_from_proxy_row(proxy_row=proxy_row)
        if 0 <= source_row < len(self._mdl.objects):
            return self._mdl.objects[source_row]
        else:
            return None

    def objects_at_proxy_rows(self, proxy_rows: List[int]) -> List[ALL_DEV_TYPES]:
        """
        Return objects shown at the requested visible proxy rows.

        :param proxy_rows: Row indexes in the filtered/sorted proxy.
        :return: Objects in the requested row order.
        """
        return self.get_objects_at_proxy_rows(proxy_rows=proxy_rows)

    def get_objects_at_proxy_rows(self, proxy_rows: List[int]) -> List[ALL_DEV_TYPES]:
        """
        Return objects shown at the requested visible proxy rows.

        :param proxy_rows: Row indexes in the filtered/sorted proxy.
        :return: Objects in the requested row order.
        """
        objects: List[ALL_DEV_TYPES] = list()
        proxy_row: int
        for proxy_row in proxy_rows:
            obj: ALL_DEV_TYPES | None = self.get_object_at_proxy_row(proxy_row=proxy_row)
            if obj is not None:
                objects.append(obj)
            else:
                pass
        return objects

    # ------------------------------------------------------------------  QSortFilterProxyModel
    def filterAcceptsRow(self, source_row: int,
                         source_parent: QtCore.QModelIndex) -> bool:
        """
        Called by Qt for every row that might be shown.
        """
        return source_row in self._allowed_rows

    def get_data(self):
        """

        :return:
        """

        n_rows = self.rowCount()
        n_cols = self.columnCount()
        data = np.empty((n_rows, n_cols), dtype=object)

        proxy_row: int
        source_row: int
        for proxy_row in range(n_rows):
            source_row = self.get_source_row_from_proxy_row(proxy_row=proxy_row)
            if source_row > -1:
                for j in range(n_cols):
                    data[proxy_row, j] = self._mdl.data_raw(r=source_row, c=j)
            else:
                pass

        columns = [self._mdl.headerData(section=i, orientation=QtCore.Qt.Orientation.Horizontal,
                                        role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(n_cols)]

        index = [self._mdl.headerData(section=self.get_source_row_from_proxy_row(proxy_row=i),
                                      orientation=QtCore.Qt.Orientation.Vertical,
                                      role=QtCore.Qt.ItemDataRole.DisplayRole) for i in range(n_rows)]

        return index, columns, data

    def copy_to_column(self, index: QtCore.QModelIndex):
        """
        Copy the value pointed by the index to all the other cells in the column
        :param index: QModelIndex instance
        """
        col = index.column()
        row = index.row()
        if row > -1 and col > -1:
            if self._mdl.transposed:
                attr_name = self._mdl.attributes[row]
                sel = self.get_object_at_proxy_row(proxy_row=col)
            else:
                attr_name = self._mdl.attributes[col]
                sel = self.get_object_at_proxy_row(proxy_row=row)

            if sel is not None:
                value = getattr(sel, attr_name)
                for elm in self.objects:
                    if elm != sel:
                        if attr_name not in self._mdl.non_editable_attributes:
                            setattr(elm, attr_name, value)
                        else:
                            pass  # the column cannot be edited
            else:
                pass

    def copy_to_clipboard(self):
        """
        Copy proxy view to clipboard
        :return:
        """
        if self.columnCount() > 0:

            index, columns, data = self.get_data()

            data = data.astype(str)

            # header first
            txt = '\t' + '\t'.join(columns) + '\n'

            # data
            for t, index_value in enumerate(index):
                txt += str(index_value) + '\t' + '\t'.join(data[t, :]) + '\n'

            # copy to clipboard
            cb = QtWidgets.QApplication.clipboard()
            cb.clear()
            cb.setText(txt)

    def set_time_index(self, time_index: int | None):
        """
        Set the time index of the table
        :param time_index: None or integer value
        """
        self._mdl.time_index_ = time_index
        row_count: int = self.rowCount()
        col_count: int = self.columnCount()

        if row_count > 0 and col_count > 0:
            top_left: QtCore.QModelIndex = self.index(0, 0)
            bottom_right: QtCore.QModelIndex = self.index(row_count - 1, col_count - 1)
            self.dataChanged.emit(
                top_left,
                bottom_right,
                [QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole],
            )
        else:
            pass
