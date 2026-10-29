from PySide6.QtWidgets import QApplication, QTreeView, QStyledItemDelegate, QStyleOptionViewItem
from PySide6.QtGui import QStandardItemModel, QStandardItem
from PySide6.QtCore import Qt, QRect

SPAN_ROLE = Qt.UserRole + 1


class SpanDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Only span for rows marked with SPAN_ROLE and only for column 0
        if index.data(SPAN_ROLE) is True:
            if index.column() == 0:
                view = option.widget
                full = QStyleOptionViewItem(option)

                # Compute full width of the row inside the viewport
                full.rect = QRect(0, option.rect.y(),
                                  view.viewport().width(),
                                  option.rect.height())

                super().paint(painter, full, index)
                return
            else:
                # Do NOT paint other columns for spanned rows
                return

        # Normal row/column
        super().paint(painter, option, index)


def build_model():
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Column 1", "Column 2", "Column 3"])

    # ---------- NORMAL ROW ----------
    normal_row = [
        QStandardItem("Normal row"),
        QStandardItem("A"),
        QStandardItem("B"),
    ]
    model.appendRow(normal_row)

    # ---------- SPANNED ROW ----------
    spanned_item = QStandardItem("This row spans all columns")
    spanned_item.setData(True, SPAN_ROLE)

    # Dummy columns are required, but they won’t display
    dummy2 = QStandardItem("")
    dummy3 = QStandardItem("")

    model.appendRow([spanned_item, dummy2, dummy3])

    # ---------- ANOTHER NORMAL ROW ----------
    another = [
        QStandardItem("Another row"),
        QStandardItem("X"),
        QStandardItem("Y"),
    ]
    model.appendRow(another)

    return model


if __name__ == "__main__":
    app = QApplication([])

    view = QTreeView()
    view.setUniformRowHeights(True)  # important for nicer rendering
    view.setItemDelegate(SpanDelegate(view))

    model = build_model()
    view.setModel(model)

    view.expandAll()
    view.setMinimumWidth(500)
    view.show()

    app.exec()
