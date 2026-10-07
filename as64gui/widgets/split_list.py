from PyQt6 import QtCore, QtGui, QtWidgets


# Rows alternate between these colors, starting with the first
ROW_COLORS = (QtGui.QColor(20, 22, 24), QtGui.QColor(15, 17, 19))
ROW_HEIGHT = 37


class SplitListWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self.splits = []
        self._display_count = 7  # Total number of items to display
        self._display_index = 0  # First item to be displayed
        self._selected_index = 0  # Currently selected item (highlighted)
        self._scroll_steps = 0  # keep track of scroll steps in case users mouse has smaller than usual increments

    def paintEvent(self, event):
        painter = QtGui.QPainter()

        split_height = int(event.rect().height() / self._display_count)
        split_width = event.rect().width()
        text_width = split_width - split_height
        x_pos = split_height
        pixmap_dimension = int(split_height * 0.8)
        pixmap_spacing = int((split_height - pixmap_dimension) / 2)

        painter.begin(self)

        for i in range(self._display_count):
            try:
                split_index = i + self._display_index
                y_pos = split_height * i

                painter.fillRect(0, int(y_pos), int(split_width), int(split_height), ROW_COLORS[i % 2])

                if split_index == self._selected_index:
                    painter.fillRect(0, int(y_pos), int(split_width), int(split_height), 
                                     QtWidgets.QApplication.palette().color(QtGui.QPalette.ColorRole.Highlight))

                if self.splits[split_index].pixmap:
                    painter.drawPixmap(int(pixmap_spacing), int(split_height * i + pixmap_spacing), int(pixmap_dimension), int(pixmap_dimension), self.splits[split_index].pixmap)

                painter.drawText(int(x_pos), int(y_pos), int(text_width), int(split_height), 
                                 QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, 
                                 self.splits[split_index].text)
            except IndexError:
                pass

        painter.end()

    def resizeEvent(self, event):
        # Show as many rows as fit, keeping the selected split visible
        self._display_count = max(1, self.height() // ROW_HEIGHT)
        self._display_index = max(0, min(self._display_index, len(self.splits) - self._display_count))
        self.set_selected_index(self._selected_index)
        super().resizeEvent(event)

    def wheelEvent(self, event):
        self.scroll_vertically(event.angleDelta())
        event.accept()

    def scroll_vertically(self, steps):
        self._scroll_steps += steps.y()

        if self._scroll_steps >= 120:
            if self._display_index > 0:
                self._display_index -= 1
            self._scroll_steps = 0
        elif self._scroll_steps <= -120:
            if self._display_index < (len(self.splits) - self._display_count):
                self._display_index += 1
            self._scroll_steps = 0

        self.repaint()

    def set_selected_index(self, index):
        max_displayed_index = self._display_index + self._display_count - 1
        if index > max_displayed_index:
            self._display_index += index - max_displayed_index

        if index < self._display_index:
            self._display_index -= self._display_index - index

        self._selected_index = index
        self.repaint()

    def add_split(self, title, icon=None):
        self.splits.append(SplitListItem(title, icon))

    def clear(self):
        self.splits = []
        self._display_index = 0
        self.set_selected_index(0)


class SplitListItem(object):
    def __init__(self, text, pixmap=None):
        self.text = text
        self.pixmap = pixmap
