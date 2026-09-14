"""Small reusable pieces the screens are assembled from."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ..core.i18n import tr
from . import icons, theme


def separator(vertical: bool = True, length: int = 20) -> QFrame:
    line = QFrame()
    line.setObjectName("separator")
    if vertical:
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFixedWidth(1)
        line.setFixedHeight(length)
    else:
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
    return line


def stretch(layout) -> None:
    layout.addStretch(1)


def icon_button(name: str, tooltip: str = "", size: int = 18, object_name: str = "iconButton",
                color: str = theme.TEXT_BUTTON) -> QToolButton:
    button = QToolButton()
    button.setObjectName(object_name)
    button.setIcon(icons.icon(name, size, color))
    button.setIconSize(QSize(size, size))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def text_button(text: str, object_name: str = "compactButton", icon_name: str = "",
                color: str = theme.TEXT_BUTTON) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName(object_name)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon_name:
        button.setIcon(icons.icon(icon_name, 15, color))
        button.setIconSize(QSize(15, 15))
    return button


def caption(text: str = "", object_name: str = "caption") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setWordWrap(True)
    return label


def elide(label: QLabel, text: str, width: int | None = None) -> None:
    """Set *text* on *label*, shortened in the middle to fit."""
    metrics = label.fontMetrics()
    available = width if width is not None else max(40, label.width())
    label.setText(metrics.elidedText(str(text), Qt.TextElideMode.ElideMiddle, available))
    label.setToolTip(str(text))


class Segmented(QFrame):
    """A row of mutually exclusive buttons carrying a value each."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]] | None = None, primary: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmentBar")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        self._primary = primary
        self._quiet = False
        self._group.buttonClicked.connect(self._emit)
        if options:
            self.set_options(options)

    def set_options(self, options: list[tuple[str, str]], icons_for: dict | None = None) -> None:
        current = self.value()
        for button in list(self._buttons.values()):
            self._group.removeButton(button)
            self._layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()
        for value, label in options:
            button = QPushButton(label)
            button.setObjectName("segmentPrimary" if self._primary else "segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("value", value)
            name = (icons_for or {}).get(value)
            if name:
                button.setIcon(icons.icon(name, 14, theme.TEXT_BUTTON))
                button.setIconSize(QSize(14, 14))
            self._group.addButton(button)
            self._layout.addWidget(button)
            self._buttons[value] = button
        if current in self._buttons:
            self.set_value(current, quiet=True)
        elif options:
            self.set_value(options[0][0], quiet=True)

    def _emit(self, button: QPushButton) -> None:
        if not self._quiet:
            self.changed.emit(str(button.property("value")))

    def value(self) -> str:
        for value, button in self._buttons.items():
            if button.isChecked():
                return value
        return ""

    def set_value(self, value: str, quiet: bool = False) -> None:
        button = self._buttons.get(value)
        if button is None:
            return
        self._quiet = quiet
        button.setChecked(True)
        self._quiet = False


class Switch(QAbstractButton):
    """A pill toggle. Drawn rather than styled so it looks the same everywhere."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(38, 22)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        return QSize(38, 22)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        on = self.isChecked()
        enabled = self.isEnabled()
        track = QColor(theme.ACCENT if on else "#1C2230")
        border = QColor("#8C76F7" if on else "#333D50")
        if not enabled:
            track.setAlpha(110)
            border.setAlpha(110)
        painter.setBrush(track)
        painter.setPen(border)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        knob = self.height() - 8
        x = self.width() - knob - 4 if on else 4
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#FFFFFF" if on else "#5A6478"))
        painter.drawEllipse(QRectF(x, 4, knob, knob))
        painter.end()


class KeyCap(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("keyCap")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(32, 32)


class Pill(QLabel):
    def __init__(self, text: str = "", accent: bool = False,
                 parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("badgeAccent" if accent else "badge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)


class StarRating(QWidget):
    """Five stars; clicking the lit one again clears the rating."""

    rated = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self._buttons: list[QToolButton] = []
        self._value = 0
        for index in range(1, 6):
            button = QToolButton()
            button.setObjectName("iconButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIconSize(QSize(16, 16))
            button.setFixedSize(22, 22)
            button.setToolTip(f"{index}")
            button.clicked.connect(lambda _=False, value=index: self._clicked(value))
            layout.addWidget(button)
            self._buttons.append(button)
        self.set_value(0)

    def _clicked(self, value: int) -> None:
        new = 0 if value == self._value else value
        self.set_value(new)
        self.rated.emit(new)

    def value(self) -> int:
        return self._value

    def set_value(self, value: int) -> None:
        self._value = max(0, min(5, int(value or 0)))
        for index, button in enumerate(self._buttons, start=1):
            lit = index <= self._value
            button.setIcon(icons.icon("star", 16, theme.WARN if lit else "#3E4759",
                                      1.6))


class LabelSwatches(QWidget):
    """The five colour labels plus a clear button."""

    labelled = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._buttons: dict[str, QToolButton] = {}
        self._value = ""
        for name, colour in theme.LABEL_COLOURS.items():
            button = QToolButton()
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(18, 18)
            button.setToolTip(name)
            button.setStyleSheet(
                f"QToolButton {{ background: {colour}; border: 1px solid {colour};"
                f" border-radius: 5px; }}")
            button.clicked.connect(lambda _=False, value=name: self._clicked(value))
            layout.addWidget(button)
            self._buttons[name] = button
        clear = QToolButton()
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.setFixedSize(18, 18)
        clear.setToolTip(tr("none"))
        clear.setStyleSheet(
            "QToolButton { background: transparent; border: 1px dashed #3E4759;"
            " border-radius: 5px; }")
        clear.clicked.connect(lambda: self._clicked(""))
        layout.addWidget(clear)
        layout.addStretch(1)

    def _clicked(self, value: str) -> None:
        new = "" if value == self._value else value
        self.set_value(new)
        self.labelled.emit(new)

    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value if value in theme.LABEL_COLOURS else ""
        for name, button in self._buttons.items():
            colour = theme.LABEL_COLOURS[name]
            ring = "; outline: none; border: 2px solid #FFFFFF" if name == self._value else ""
            button.setStyleSheet(
                f"QToolButton {{ background: {colour}; border: 1px solid {colour};"
                f" border-radius: 5px{ring}; }}")


class BindingCard(QFrame):
    """One row of the quick-sort sidebar."""

    activated = Signal(int)
    folder_requested = Signal(int)

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("bindingCard")
        self.index = index
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)
        self.cap = KeyCap()
        row.addWidget(self.cap)

        texts = QVBoxLayout()
        texts.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.name_label = QLabel()
        self.name_label.setObjectName("bindingName")
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.badge = Pill()
        top.addWidget(self.name_label, 1)
        top.addWidget(self.badge, 0)
        self.path_label = QLabel()
        self.path_label.setObjectName("bindingPath")
        self.path_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        texts.addLayout(top)
        texts.addWidget(self.path_label)
        row.addLayout(texts, 1)

        self.count = Pill("", accent=True)
        self.count.setVisible(False)
        row.addWidget(self.count, 0)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.folder_requested.emit(self.index)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit(self.index)

    def update_binding(self, binding, count: int = 0, action_label: str = "",
                       badge_text: str = "") -> None:
        self.cap.setText(binding.key or "?")
        name = (Path(binding.folder).name or binding.folder) if binding.folder else action_label
        elide(self.name_label, name or action_label, max(60, self.name_label.width() or 140))
        detail = binding.folder or ""
        if binding.path_template:
            detail = f"{detail}\\{binding.path_template}" if detail else binding.path_template
        elide(self.path_label, detail or action_label,
              max(60, self.path_label.width() or 160))
        self.badge.setText(badge_text)
        self.badge.setVisible(bool(badge_text))
        self.count.setText(str(count))
        self.count.setVisible(bool(count))
        self.setProperty("configured", "true" if binding.is_configured() else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class SectionCard(QFrame):
    """A titled block used throughout the settings screens."""

    def __init__(self, title: str, icon_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsCard")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(10)
        header = QHBoxLayout()
        header.setSpacing(9)
        if icon_name:
            badge = QLabel()
            badge.setPixmap(icons.pixmap(icon_name, 16, "#A594FF"))
            badge.setFixedSize(26, 26)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "QLabel { background: #1A1730; border: 1px solid #3A2F63; border-radius: 8px; }")
            header.addWidget(badge)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        header.addWidget(label, 1)
        outer.addLayout(header)
        self.body = QVBoxLayout()
        self.body.setSpacing(2)
        outer.addLayout(self.body)

    def add_row(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget


class SettingRow(QWidget):
    """Label, optional explanation, and one control on the right."""

    def __init__(self, title: str, description: str = "", control: QWidget | None = None,
                 first: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        if not first:
            outer.addWidget(separator(vertical=False))
        row = QHBoxLayout()
        row.setContentsMargins(0, 11, 0, 11)
        row.setSpacing(16)
        texts = QVBoxLayout()
        texts.setSpacing(3)
        label = QLabel(title)
        label.setWordWrap(True)
        label.setStyleSheet("font-weight: 600; color: #DCE1EC;")
        texts.addWidget(label)
        if description:
            texts.addWidget(caption(description))
        row.addLayout(texts, 1)
        if control is not None:
            control.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
            row.addWidget(control, 0, Qt.AlignmentFlag.AlignTop)
        outer.addLayout(row)
        self.control = control
