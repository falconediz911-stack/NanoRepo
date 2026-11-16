#!/usr/bin/env python3
"""NanoOS OVERRIDE adaptive UI foundation (V2).

Responsive policy is testable without Qt. The Qt controller applies shared
spacing and widget density properties, then emits decisions for application-
specific layout reflow. Dimensions are Qt logical pixels, not framebuffer pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Final

VALID_PREFERENCES: Final[frozenset[str]] = frozenset({"auto", "compact", "comfortable"})
VALID_LAYOUT_MODES: Final[frozenset[str]] = frozenset({"compact", "standard", "expanded"})
ENGINE_VERSION = "NANOOS_OVERRIDE_ADAPTIVE_UI_V2"


@dataclass(frozen=True, slots=True)
class AdaptiveDecision:
    """A deterministic layout decision for a window's currently available area."""
    layout_mode: str
    density_mode: str
    width: int
    height: int
    recommended_columns: int
    compact_spacing: int


class AdaptiveLayoutPolicy:
    """Shared responsive rules based on actual available window dimensions."""
    COMPACT_MAX_WIDTH: Final[int] = 960
    COMPACT_MAX_HEIGHT: Final[int] = 520
    EXPANDED_MIN_WIDTH: Final[int] = 1440
    EXPANDED_MIN_HEIGHT: Final[int] = 760
    COMPACT_SPACING: Final[int] = 6

    @staticmethod
    def normalize_preference(value: object) -> str:
        if not isinstance(value, str):
            return "auto"
        value = value.strip().lower()
        return value if value in VALID_PREFERENCES else "auto"

    @classmethod
    def decide(
        cls,
        width: int,
        height: int,
        preference: object = "auto",
        *,
        min_card_width: int = 280,
        card_gap: int = 16,
    ) -> AdaptiveDecision:
        """Compute layout/density without requiring a running Qt application."""
        width = max(0, int(width))
        height = max(0, int(height))
        preference = cls.normalize_preference(preference)
        tight = width < cls.COMPACT_MAX_WIDTH or height < cls.COMPACT_MAX_HEIGHT

        if preference == "compact" or tight:
            layout_mode = "compact"
        elif width >= cls.EXPANDED_MIN_WIDTH and height >= cls.EXPANDED_MIN_HEIGHT:
            layout_mode = "expanded"
        else:
            layout_mode = "standard"

        if preference == "compact":
            density_mode = "compact"
        elif preference == "comfortable":
            density_mode = "comfortable"
        elif layout_mode == "compact":
            density_mode = "compact"
        elif layout_mode == "expanded":
            density_mode = "comfortable"
        else:
            density_mode = "standard"

        min_card_width = max(1, int(min_card_width))
        card_gap = max(0, int(card_gap))
        if layout_mode == "compact":
            columns = 1
        else:
            columns = max(1, (max(1, width) + card_gap) // (min_card_width + card_gap))
            columns = min(4, columns)
            if layout_mode == "standard":
                columns = min(2, columns)

        return AdaptiveDecision(
            layout_mode=layout_mode,
            density_mode=density_mode,
            width=width,
            height=height,
            recommended_columns=int(columns),
            compact_spacing=cls.COMPACT_SPACING,
        )


ADAPTIVE_QSS = r"""
/* NANOOS_OVERRIDE_ADAPTIVE_UI_V2: compact controls; preserve each app's base theme. */
QPushButton[nanoosDensityMode="compact"],
QToolButton[nanoosDensityMode="compact"] {
    min-height: 28px;
    padding: 4px 8px;
    font-size: 10pt;
}
QLineEdit[nanoosDensityMode="compact"],
QTextEdit[nanoosDensityMode="compact"],
QPlainTextEdit[nanoosDensityMode="compact"],
QComboBox[nanoosDensityMode="compact"],
QSpinBox[nanoosDensityMode="compact"],
QDoubleSpinBox[nanoosDensityMode="compact"] {
    min-height: 28px;
    padding: 3px 6px;
    font-size: 10pt;
}
QLabel[nanoosDensityMode="compact"] {
    font-size: 10pt;
}
QCheckBox[nanoosDensityMode="compact"],
QRadioButton[nanoosDensityMode="compact"] {
    spacing: 5px;
    font-size: 10pt;
}
QGroupBox[nanoosDensityMode="compact"] {
    margin-top: 8px;
    padding: 5px;
}
"""

try:  # Keep policy importable and testable without PySide6.
    from PySide6.QtCore import QEvent, QObject, QTimer, Signal
    from PySide6.QtWidgets import QLayout, QWidget
    _QT_IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover - depends on runtime environment
    QEvent = QObject = QTimer = Signal = QLayout = QWidget = None  # type: ignore[assignment]
    _QT_IMPORT_ERROR = exc


if QObject is not None:  # pragma: no branch
    class AdaptiveUiController(QObject):
        """Shared Qt adapter; apps subscribe to decisions for structural reflow."""
        layoutModeChanged = Signal(str)
        decisionChanged = Signal(object)

        def __init__(self, window: "QWidget", preference: str | None = None):
            super().__init__(window)
            self.window = window
            raw_preference = preference
            if raw_preference is None:
                raw_preference = window.property("nanoosDensityPreference")
            if raw_preference is None:
                raw_preference = os.environ.get("NANOOS_UI_DENSITY", "auto")
            self.preference = AdaptiveLayoutPolicy.normalize_preference(raw_preference)
            self.decision: AdaptiveDecision | None = None
            self._base_layouts: dict[object, tuple[tuple[int, int, int, int], int]] = {}
            self._pending = False

            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(35)
            self._timer.timeout.connect(self._recompute)

            existing_qss = window.styleSheet().rstrip()
            if "NANOOS_OVERRIDE_ADAPTIVE_UI_V2" not in existing_qss:
                window.setStyleSheet((existing_qss + "\n" + ADAPTIVE_QSS).strip())

            window.installEventFilter(self)
            self._watch_events = {QEvent.Type.Resize, QEvent.Type.Show}
            for event_name in ("ScreenChangeInternal", "DevicePixelRatioChange", "FontChange"):
                event_type = getattr(QEvent.Type, event_name, None)
                if event_type is not None:
                    self._watch_events.add(event_type)
            self._schedule_recompute()

        def eventFilter(self, watched, event):  # noqa: N802 - Qt API spelling
            if watched is self.window and event.type() in self._watch_events:
                self._schedule_recompute()
            return False

        def set_preference(self, preference: str) -> None:
            self.preference = AdaptiveLayoutPolicy.normalize_preference(preference)
            self.window.setProperty("nanoosDensityPreference", self.preference)
            self._schedule_recompute()

        def _schedule_recompute(self) -> None:
            if not self._pending:
                self._pending = True
                self._timer.start()

        def _remember_layouts(self) -> None:
            layouts = list(self.window.findChildren(QLayout))
            root_layout = self.window.layout()
            if root_layout is not None:
                layouts.append(root_layout)
            for layout in layouts:
                if layout in self._base_layouts:
                    continue
                margins = layout.contentsMargins()
                self._base_layouts[layout] = (
                    (margins.left(), margins.top(), margins.right(), margins.bottom()),
                    layout.spacing(),
                )

        def _apply_layout_spacing(self, compact: bool) -> None:
            self._remember_layouts()
            for layout, (margins, original_spacing) in list(self._base_layouts.items()):
                try:
                    if compact:
                        reduced = tuple(min(value, 8) for value in margins)
                        layout.setContentsMargins(*reduced)
                        layout.setSpacing(6 if original_spacing < 0 else min(original_spacing, 6))
                    else:
                        layout.setContentsMargins(*margins)
                        layout.setSpacing(original_spacing)
                except RuntimeError:
                    self._base_layouts.pop(layout, None)

        def _apply_widget_properties(self, decision: AdaptiveDecision) -> None:
            widgets = [self.window, *self.window.findChildren(QWidget)]
            for widget in widgets:
                changed = False
                for property_name, value in (
                    ("nanoosLayoutMode", decision.layout_mode),
                    ("nanoosDensityMode", decision.density_mode),
                ):
                    if widget.property(property_name) != value:
                        widget.setProperty(property_name, value)
                        changed = True
                if changed:
                    style = widget.style()
                    style.unpolish(widget)
                    style.polish(widget)
                    widget.updateGeometry()
                    widget.update()

        def _recompute(self) -> None:
            self._pending = False
            if self.window is None:
                return
            decision = AdaptiveLayoutPolicy.decide(
                self.window.width(), self.window.height(), self.preference
            )
            if decision == self.decision:
                return
            previous = self.decision
            self.decision = decision
            self._apply_layout_spacing(decision.density_mode == "compact")
            self._apply_widget_properties(decision)
            if previous is None or previous.layout_mode != decision.layout_mode:
                self.layoutModeChanged.emit(decision.layout_mode)
            self.decisionChanged.emit(decision)


def attach_adaptive_ui(window, preference: str | None = None):
    """Attach one controller to a window; repeated calls reuse the existing one."""
    if _QT_IMPORT_ERROR is not None:
        raise RuntimeError("NanoOS OVERRIDE adaptive UI requires PySide6 at runtime.") from _QT_IMPORT_ERROR
    existing = getattr(window, "_nanoos_override_adaptive_controller", None)
    if existing is not None:
        return existing
    controller = AdaptiveUiController(window, preference)
    setattr(window, "_nanoos_override_adaptive_controller", controller)
    return controller
