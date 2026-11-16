#!/usr/bin/env python3

import json
import shutil
import sqlite3
import subprocess
import sys
import re
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QTimer, Signal, QPoint, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QFont, QPainter, QColor, QPalette, QPixmap
from PySide6.QtWidgets import (
    QMenu,
    QCheckBox,
    QComboBox,
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QProgressBar,
    QWidget,
)


from PySide6.QtGui import QTextLayout, QTextOption
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QLineEdit
from PySide6.QtWidgets import QAbstractItemView
from PySide6.QtCore import QSize

class NanoOSLatencyHistoryPlot(QWidget):
    """NANOOS_LATENCY_HISTORY_NANO_SMOOTHNESS_V1_1."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._samples = []
        self._display_samples = []
        self._target_samples = []
        self._animation_from_samples = []

        self._display_low = 0.0
        self._display_high = 100.0
        self._target_low = 0.0
        self._target_high = 100.0
        self._animation_from_low = 0.0
        self._animation_from_high = 100.0
        self._animation_started = None
        self._animation_duration = 0.420

        self.setObjectName("latencyLabHistoryPlot")
        self.setMinimumWidth(0)
        self.setMinimumHeight(224)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        # Approximately 60 FPS when the event loop has enough time.
        self._animation_timer = QTimer(self)
        self._animation_timer.setInterval(16)
        self._animation_timer.timeout.connect(self._animate_frame)

    @staticmethod
    def _resample(values, count):
        values = list(values)
        if count <= 0 or not values:
            return []
        if len(values) == count:
            return values
        if len(values) == 1:
            return [values[0]] * count
        if count == 1:
            return [values[-1]]

        scale = (len(values) - 1) / (count - 1)
        result = []
        for i in range(count):
            position = i * scale
            left = int(position)
            right = min(left + 1, len(values) - 1)
            fraction = position - left
            result.append(
                values[left] * (1.0 - fraction)
                + values[right] * fraction
            )
        return result

    @staticmethod
    def _range_for(values):
        if not values:
            return 0.0, 100.0
        minimum = min(values)
        maximum = max(values)
        span = maximum - minimum
        padding = max(span * 0.22, maximum * 0.035, 0.5)
        low = max(0.0, minimum - padding)
        high = maximum + padding
        if high <= low:
            high = low + 1.0
        return low, high

    def set_samples(self, samples):
        """Retarget the animation using actual RTT measurements."""
        import math
        import time

        cleaned = []
        for sample in list(samples)[-32:]:
            try:
                value = float(sample)
            except (TypeError, ValueError):
                continue
            if math.isfinite(value) and value >= 0:
                cleaned.append(value)

        if cleaned == self._target_samples:
            return

        self._samples = list(cleaned)

        if not cleaned:
            self._animation_timer.stop()
            self._display_samples = []
            self._target_samples = []
            self._animation_from_samples = []
            self._display_low, self._display_high = 0.0, 100.0
            self._target_low, self._target_high = 0.0, 100.0
            self._animation_started = None
            self.update()
            return

        target_low, target_high = self._range_for(cleaned)

        if not self._display_samples:
            midpoint = (min(cleaned) + max(cleaned)) / 2.0
            from_samples = [midpoint] * len(cleaned)
        else:
            # Retarget from the currently visible frame, not the old target.
            from_samples = self._resample(
                self._display_samples,
                len(cleaned),
            )

        self._animation_from_samples = from_samples
        self._target_samples = list(cleaned)
        self._animation_from_low = self._display_low
        self._animation_from_high = self._display_high
        self._target_low = target_low
        self._target_high = target_high
        self._animation_started = time.monotonic()

        if not self._animation_timer.isActive():
            self._animation_timer.start()
        self.update()

    def _animate_frame(self):
        """Interpolate chart values with smoothstep easing."""
        import time

        if not self._target_samples:
            self._animation_timer.stop()
            return

        if self._animation_started is None:
            progress = 1.0
        else:
            progress = (
                time.monotonic() - self._animation_started
            ) / self._animation_duration

        progress = max(0.0, min(1.0, progress))
        eased = progress * progress * (3.0 - 2.0 * progress)

        start_values = self._animation_from_samples
        target_values = self._target_samples

        if len(start_values) != len(target_values):
            start_values = self._resample(
                start_values, len(target_values)
            )

        self._display_samples = [
            old + (new - old) * eased
            for old, new in zip(start_values, target_values)
        ]

        self._display_low = (
            self._animation_from_low
            + (self._target_low - self._animation_from_low) * eased
        )
        self._display_high = (
            self._animation_from_high
            + (self._target_high - self._animation_from_high) * eased
        )

        if progress >= 1.0:
            self._display_samples = list(self._target_samples)
            self._display_low = self._target_low
            self._display_high = self._target_high
            self._animation_started = None
            self._animation_timer.stop()

        self.update()

    def paintEvent(self, event):
        from PySide6.QtGui import (
            QBrush,
            QFont,
            QLinearGradient,
            QPainterPath,
            QPen,
        )

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        canvas = self.rect().adjusted(0, 0, -1, -1)
        painter.setPen(QPen(QColor("#223543"), 1))
        painter.setBrush(QColor("#0b1118"))
        painter.drawRoundedRect(canvas, 12, 12)

        width = self.width()
        height = self.height()
        left, right = 60, width - 17
        top, bottom = 29, height - 31

        if right <= left + 20 or bottom <= top + 20:
            painter.end()
            return

        samples = self._display_samples
        low = self._display_low
        high = max(self._display_high, low + 0.001)

        painter.setFont(QFont("monospace", 8))
        painter.setPen(QColor("#7f93a7"))
        painter.drawText(12, 18, "RTT / MS")

        for i in range(5):
            ratio = i / 4.0
            y = top + ratio * (bottom - top)
            value = high - ratio * (high - low)

            painter.setPen(QPen(QColor("#223543"), 1))
            painter.drawLine(int(left), int(y), int(right), int(y))
            painter.setPen(QColor("#7f93a7"))
            painter.drawText(7, int(y) + 4, f"{value:.1f}")

        painter.setPen(QPen(QColor("#223543"), 1))
        painter.drawLine(int(left), int(top), int(left), int(bottom))
        painter.drawLine(int(left), int(bottom), int(right), int(bottom))
        painter.setPen(QColor("#7f93a7"))
        painter.drawText(int(left), height - 9, "OLDER")
        painter.drawText(int(right) - 43, height - 9, "LATEST")

        if not samples:
            painter.setFont(QFont("Inter", 10))
            painter.setPen(QColor("#7f93a7"))
            painter.drawText(
                int(left) + 12,
                int((top + bottom) / 2),
                "Run a ping test to plot real samples.",
            )
            painter.end()
            return

        span = high - low
        points = []
        for i, value in enumerate(samples):
            x_ratio = 0.5 if len(samples) == 1 else i / (len(samples) - 1)
            y_ratio = max(0.0, min(1.0, (high - value) / span))
            points.append(QPointF(
                left + x_ratio * (right - left),
                top + y_ratio * (bottom - top),
            ))

        # Average reference moves smoothly along with the data.
        average = sum(samples) / len(samples)
        average_y = top + ((high - average) / span) * (bottom - top)
        painter.setPen(
            QPen(QColor("#f2c879"), 1.2, Qt.PenStyle.DashLine)
        )
        painter.drawLine(
            int(left), int(average_y), int(right), int(average_y)
        )

        if len(points) >= 2:
            curve = QPainterPath()
            curve.moveTo(points[0])
            for point in points[1:]:
                curve.lineTo(point)

            area = QPainterPath(curve)
            area.lineTo(points[-1].x(), bottom)
            area.lineTo(points[0].x(), bottom)
            area.closeSubpath()

            gradient = QLinearGradient(0, top, 0, bottom)
            gradient.setColorAt(0.0, QColor(56, 200, 244, 75))
            gradient.setColorAt(1.0, QColor(56, 200, 244, 4))

            painter.setPen(QPen(QColor(0, 0, 0, 0), 0))
            painter.setBrush(QBrush(gradient))
            painter.drawPath(area)

            curve_pen = QPen(QColor("#66c7e8"), 2.4)
            curve_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            curve_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(curve_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(curve)

        painter.setPen(QPen(QColor("#9be3f7"), 1))
        for point in points[:-1]:
            painter.setBrush(QColor("#66c7e8"))
            painter.drawEllipse(point, 2.1, 2.1)

        latest = points[-1]
        painter.setPen(QPen(QColor("#e6eef6"), 1.5))
        painter.setBrush(QColor("#66c7e8"))
        painter.drawEllipse(latest, 4.2, 4.2)

        painter.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#9be3f7"))
        painter.drawText(
            max(int(left), int(right) - 110),
            18,
            f"NOW  {samples[-1]:.2f} ms",
        )
        painter.end()


class NanoOSCompactTabSelector(QComboBox):
    """Compact NanoOS navigation selector with a custom, non-scrolling menu."""

    def showPopup(self):
        menu = QMenu(self)
        menu.setObjectName("nanoosCompactTabMenu")
        menu.setMinimumWidth(max(220, self.width()))
        menu.setStyleSheet("""
            QMenu#nanoosCompactTabMenu {
                background-color: #101b26;
                color: #e6eef6;
                border: 1px solid #31566a;
                padding: 5px;
            }
            QMenu#nanoosCompactTabMenu::item {
                background-color: #101b26;
                color: #e6eef6;
                min-height: 28px;
                padding: 8px 14px;
                margin: 2px;
                border-radius: 7px;
            }
            QMenu#nanoosCompactTabMenu::item:hover {
                background-color: #10293a;
                color: #ffffff;
            }
            QMenu#nanoosCompactTabMenu::item:selected {
                background-color: #1f4a61;
                color: #ffffff;
            }
            QMenu#nanoosCompactTabMenu::item:checked {
                background-color: #1f4a61;
                color: #ffffff;
                font-weight: 600;
            }
            QMenu#nanoosCompactTabMenu::separator {
                height: 1px;
                background: #223543;
                margin: 4px 8px;
            }
        """)

        for index in range(self.count()):
            action = menu.addAction(self.itemText(index))
            action.setCheckable(True)
            action.setChecked(index == self.currentIndex())
            action.triggered.connect(
                lambda checked=False, selected=index:
                    self.setCurrentIndex(selected)
            )

        try:
            menu.exec(self.mapToGlobal(QPoint(0, self.height())))
        finally:
            menu.deleteLater()


APP_NAME = "NanoOS GameMode"
VERSION = "V2"

CONFIG_DIR = Path.home() / ".config" / "nanoos"
STATE_FILE = CONFIG_DIR / "gamemode.json"

GAMEMODE_CONFIG_DIR = Path.home() / ".config"
GAMEMODE_CONFIG = GAMEMODE_CONFIG_DIR / "gamemode.ini"
GAMEMODE_BACKUP = GAMEMODE_CONFIG_DIR / "gamemode.ini.nanoos-backup"

PROFILE_DATA = {
    "Balanced": {
        "desiredgov": "powersave",
        "desiredprof": "balanced",
        "desired_epp": "balance_performance",
        "desired_platform": "balanced",
        "renice": "0",
        "ioprio": "off",
        "softrealtime": "off",
    },
    "Performance": {
        "desiredgov": "performance",
        "desiredprof": "performance",
        "desired_epp": "performance",
        "desired_platform": "performance",
        "renice": "5",
        "ioprio": "0",
        "softrealtime": "off",
    },
    "Gaming": {
        "desiredgov": "performance",
        "desiredprof": "performance",
        "desired_epp": "performance",
        "desired_platform": "performance",
        "renice": "10",
        "ioprio": "0",
        "softrealtime": "off",
    },
}

DEFAULT_STATE = {
    "gamemode": False,
    "cpu_boost": True,
    "gpu_performance": True,
    "nanoos_performance_mode": "Balanced",
    "io_optimization": True,
    "scheduler_optimization": True,
    "screensaver_inhibit": True,
    "profile": "Gaming",
}


_NANOOS_UI_ICONS = {
    "chevron-down.svg": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
        '<path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="#9be3f7" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "chevron-down-disabled.svg": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
        '<path d="M2.5 4.5 6 8l3.5-3.5" fill="none" stroke="#4e6276" stroke-width="1.6" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "check.svg": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">'
        '<path d="M3 7.3 5.8 10 11 4" fill="none" stroke="#04121b" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
}


def nanoos_ui_icon(name):
    """Path to a small UI icon, for use in Qt stylesheets (url(...))."""
    shipped = Path("/usr/share/nanoos/ui") / name
    if shipped.is_file():
        return shipped.as_posix()
    cache = Path.home() / ".cache" / "nanoos" / "ui"
    target = cache / name
    try:
        if not target.is_file() or target.read_text() != _NANOOS_UI_ICONS[name]:
            cache.mkdir(parents=True, exist_ok=True)
            target.write_text(_NANOOS_UI_ICONS[name], encoding="utf-8")
    except OSError:
        return ""
    return target.as_posix()


def load_state():
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            state = DEFAULT_STATE.copy()
            state.update(data)
            return state
    except (OSError, json.JSONDecodeError):
        pass

    return DEFAULT_STATE.copy()


def save_state(state):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
    )


def find_cpu_boost_control():
    candidates = [
        Path("/sys/devices/system/cpu/cpufreq/boost"),
        Path("/sys/devices/system/cpu/boost"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def read_cpu_boost():
    control = find_cpu_boost_control()

    if control is None:
        return None

    try:
        value = control.read_text().strip()
        return value == "1"
    except OSError:
        return None


HELPER_PATH = "/usr/lib/nanoos-gamemode/nanoos-gamemode-helper"

# While a batch is open, helper operations are queued and sent to the
# root helper in ONE pkexec call (one authorization for a whole profile
# instead of one per setting).
_HELPER_BATCH = None


def _execute_helper(arguments):
    if shutil.which("pkexec") is None:
        return False, "pkexec is unavailable."
    if not Path(HELPER_PATH).is_file():
        return False, (
            "The NanoOS GameMode helper is not installed "
            f"({HELPER_PATH})."
        )

    try:
        result = subprocess.run(
            ["pkexec", HELPER_PATH, *[str(value) for value in arguments]],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return False, "Timed out waiting for administrator authorization."
    except OSError as exc:
        return False, str(exc)

    if result.returncode == 0:
        return True, ""
    if result.returncode in (126, 127):
        return False, "Administrator authorization was cancelled."
    return False, (
        result.stderr.strip()
        or result.stdout.strip()
        or "The NanoOS GameMode helper failed."
    )


def run_privileged_helper(operation, *arguments):
    if _HELPER_BATCH is not None:
        _HELPER_BATCH.append(
            (str(operation), [str(value) for value in arguments])
        )
        return True, ""
    return _execute_helper([operation, *arguments])


class PrivilegedBatch:
    """Queue helper operations and apply them with one authorization."""

    def __init__(self):
        self.ok = True
        self.error = ""

    def __enter__(self):
        global _HELPER_BATCH
        self._previous = _HELPER_BATCH
        _HELPER_BATCH = []
        return self

    def __exit__(self, exc_type, exc, traceback):
        global _HELPER_BATCH
        queued, _HELPER_BATCH = _HELPER_BATCH, self._previous
        if exc_type is None and queued:
            self.ok, self.error = _execute_helper(
                ["batch", *[f"{op}={args[0]}" for op, args in queued if args]]
            )
        return False


def gpu_performance_control():
    """Which GPU performance control exists: 'nvidia', 'amdgpu' or None."""
    if shutil.which("nvidia-smi") is not None:
        return "nvidia"
    try:
        if any(Path("/sys/class/drm").glob(
            "card[0-9]*/device/power_dpm_force_performance_level"
        )):
            return "amdgpu"
    except OSError:
        pass
    return None


def set_cpu_boost(enabled):
    control = find_cpu_boost_control()

    if control is None:
        return False, "CPU boost control is not exposed by the kernel."

    value = "1" if enabled else "0"

    try:
        control.write_text(value)
        return True, ""

    except PermissionError:
        return run_privileged_helper("boost", value)

    except OSError as exc:
        return False, str(exc)


def set_gpu_performance(enabled):
    # Intel and other GPUs have no runtime control: keep the preference
    # (it still feeds gamemode.ini) instead of raising an error dialog.
    if gpu_performance_control() is None:
        return True, ""

    mode = "on" if enabled else "off"
    return run_privileged_helper("gpu", mode)


def gamemode_status():
    try:
        result = subprocess.run(
            ["gamemoded", "-s"],
            capture_output=True,
            text=True,
            timeout=4,
        )

        text = (result.stdout + "\n" + result.stderr).lower()

        if "active" in text and "inactive" not in text:
            return True, text.strip()

        return False, text.strip()

    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)


class NanoOSButton(QPushButton):
    """Fully custom rounded NanoOS button.

    Qt's native button renderer is intentionally bypassed so it cannot
    draw square focus/highlight frames over the NanoOS UI.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)

        # Keep Qt's stylesheet from painting another rectangle behind us.
        self.setStyleSheet(
            "background: transparent;"
            "border: none;"
            "outline: none;"
            "padding: 0;"
        )

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        # NANOOS_OVERRIDE_GAMEMODE_TEXT_LAYOUT_V1
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        enabled = self.isEnabled()
        checked = self.isCheckable() and self.isChecked()
        hovered = self.underMouse()
        name = self.objectName()

        if not enabled:
            background, border, foreground = QColor("#0b1118"), QColor("#132230"), QColor("#4e6276")
        elif name == "navButton":
            if checked:
                background, border, foreground = QColor("#1a2936"), QColor("#223543"), QColor("#ffffff")
            elif hovered:
                background, border, foreground = QColor("#101b26"), QColor("#1a2936"), QColor("#e6eef6")
            else:
                background, border, foreground = QColor("#070b11"), QColor("#070b11"), QColor("#7f93a7")
        elif name == "masterToggle":
            if checked:
                background, border, foreground = QColor("#173524"), QColor("#2d8050"), QColor("#77e5a1")
            elif hovered:
                background, border, foreground = QColor("#1a2936"), QColor("#31566a"), QColor("#e6eef6")
            else:
                background, border, foreground = QColor("#132230"), QColor("#223543"), QColor("#e6eef6")
        elif checked:
            background, border, foreground = QColor("#10293a"), QColor("#2f8fb5"), QColor("#e6eef6")
        elif hovered:
            background, border, foreground = QColor("#132230"), QColor("#223543"), QColor("#ffffff")
        else:
            background, border, foreground = QColor("#101b26"), QColor("#223543"), QColor("#e6eef6")

        painter.setPen(border)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 16, 16)

        content = rect.adjusted(14, 8, -14, -8)
        font = QFont(self.font())
        font.setWeight(QFont.Weight.DemiBold if checked else QFont.Weight.Normal)
        if name == "navButton":
            font.setPixelSize(13)
        painter.setFont(font)
        painter.setPen(foreground)

        # NANOOS_OVERRIDE_MULTILINE_BUTTON_TEXT_V12
        alignment = (
            Qt.AlignmentFlag.AlignLeft
            if name == "navButton"
            else Qt.AlignmentFlag.AlignHCenter
        )

        paragraphs = self.text().splitlines() or [""]
        layouts = []
        total_height = 0.0
        paragraph_gap = 2.0

        for paragraph in paragraphs:
            option = QTextOption()
            option.setWrapMode(QTextOption.WrapMode.WordWrap)
            option.setAlignment(alignment)

            text_layout = QTextLayout(paragraph, font)
            text_layout.setTextOption(option)
            text_layout.beginLayout()

            paragraph_height = 0.0
            while True:
                line = text_layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(max(1, content.width()))
                line.setPosition(QPointF(0, paragraph_height))
                paragraph_height += line.height()

            text_layout.endLayout()
            layouts.append((text_layout, total_height))
            total_height += paragraph_height + paragraph_gap

        if layouts:
            total_height = max(0.0, total_height - paragraph_gap)

        offset_y = max(0.0, (content.height() - total_height) / 2)
        painter.save()
        painter.setClipRect(content)
        painter.translate(content.left(), content.top() + offset_y)

        for text_layout, paragraph_y in layouts:
            text_layout.draw(painter, QPointF(0, paragraph_y))

        painter.restore()
        painter.end()


class NanoOSGameRow(QFrame):
    """Non-native game row; no selection or focus rectangle."""

    def __init__(self, game, profile, parent=None):
        super().__init__(parent)

        self.game = game
        self.profile = profile
        self.hovered = False

        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        rect = self.rect().adjusted(1, 1, -1, -1)

        background = (
            QColor("#132230")
            if self.hovered
            else QColor("#101b26")
        )

        border = (
            QColor("#223543")
            if self.hovered
            else QColor("#1a2936")
        )

        painter.setPen(border)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 14, 14)

        title_font = QFont(self.font())
        title_font.setPixelSize(14)
        title_font.setWeight(QFont.Weight.DemiBold)

        painter.setFont(title_font)
        painter.setPen(QColor("#e6eef6"))

        painter.drawText(
            rect.adjusted(18, 6, -180, -6),
            Qt.AlignmentFlag.AlignLeft |
            Qt.AlignmentFlag.AlignVCenter,
            self.game,
        )

        profile_font = QFont(self.font())
        profile_font.setPixelSize(12)

        painter.setFont(profile_font)
        painter.setPen(QColor("#7f93a7"))

        painter.drawText(
            rect.adjusted(rect.width() - 170, 6, -18, -6),
            Qt.AlignmentFlag.AlignRight |
            Qt.AlignmentFlag.AlignVCenter,
            self.profile,
        )

        painter.end()


class NanoOSNavItem(QFrame):
    """Custom NanoOS sidebar item with zero native button chrome."""

    clicked = Signal()

    def __init__(self, symbol, label, parent=None):
        super().__init__(parent)

        self.symbol = symbol
        self.label = label
        self._checked = False
        self._hovered = False

        self.setFixedHeight(46)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def setChecked(self, checked):
        self._checked = bool(checked)
        self.update()

    def isChecked(self):
        return self._checked

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        rect = self.rect().adjusted(1, 1, -1, -1)

        if self._checked:
            background = QColor("#1a2936")
            foreground = QColor("#ffffff")
        elif self._hovered:
            background = QColor("#101b26")
            foreground = QColor("#e6eef6")
        else:
            background = QColor("#070b11")
            foreground = QColor("#7f93a7")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 12, 12)

        painter.setPen(foreground)

        font = self.font()
        font.setPixelSize(14)
        font.setWeight(QFont.Weight.DemiBold)

        painter.setFont(font)

        symbol_rect = rect.adjusted(15, 0, -rect.width() + 48, 0)

        painter.drawText(
            symbol_rect,
            Qt.AlignmentFlag.AlignLeft |
            Qt.AlignmentFlag.AlignVCenter,
            self.symbol,
        )

        label_rect = rect.adjusted(48, 0, -14, 0)

        painter.drawText(
            label_rect,
            Qt.AlignmentFlag.AlignLeft |
            Qt.AlignmentFlag.AlignVCenter,
            self.label,
        )

        painter.end()


class ToggleButton(NanoOSButton):
    changed = Signal(bool)

    def __init__(self, title, subtitle="", parent=None):
        super().__init__(parent)

        self.title = title
        self.subtitle = subtitle

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(104)
        # The global "QPushButton { min-height: 22px }" rule overrides
        # setMinimumHeight(), which clipped the third (ON/OFF) line. A
        # widget-level stylesheet wins over the application one.
        self.setStyleSheet(self.styleSheet() + "min-height: 104px;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.clicked.connect(self._changed)

        self.update_text()

    def _changed(self, checked):
        self.update_text()
        self.changed.emit(checked)

    def setChecked(self, checked):
        super().setChecked(checked)
        self.update_text()

    def update_text(self):
        state = "ON" if self.isChecked() else "OFF"
        dot = "●" if self.isChecked() else "○"

        self.setText(
            f"{self.title}\n"
            f"{self.subtitle}\n"
            f"{dot}  {state}"
        )


class ProfileCard(NanoOSButton):
    selected = Signal(str)

    def __init__(self, name, description, parent=None):
        super().__init__(parent)

        self.name = name
        self.description = description

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        # NANOOS_OVERRIDE_PROFILE_CARD_GEOMETRY_V15
        self.setFixedHeight(250)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.clicked.connect(lambda: self.selected.emit(self.name))

        self.update_text()

    def sizeHint(self):
        base = super().sizeHint()
        return QSize(max(220, base.width()), 250)

    def minimumSizeHint(self):
        return QSize(180, 250)

    def paintEvent(self, event):
        # NANOOS_OVERRIDE_PROFILE_CARD_CENTERED_V7
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        area = rect.adjusted(16, 12, -16, -12)
        selected = self.isChecked()

        if not self.isEnabled():
            bg, border = QColor("#0b1118"), QColor("#223543")
            title_color, detail_color = QColor("#7f93a7"), QColor("#7f93a7")
        elif selected:
            bg, border = QColor("#10293a"), QColor("#66c7e8")
            title_color, detail_color = QColor("#e6eef6"), QColor("#9be3f7")
        elif self.underMouse():
            bg, border = QColor("#132230"), QColor("#4e6276")
            title_color, detail_color = QColor("#e6eef6"), QColor("#b4c3d2")
        else:
            bg, border = QColor("#101b26"), QColor("#223543")
            title_color, detail_color = QColor("#e6eef6"), QColor("#b4c3d2")

        painter.setPen(border)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 17, 17)

        display_name = "Ultra" if self.name == "Gaming" else self.name
        title = ("●  " if selected else "○  ") + display_name

        title_font = QFont(self.font())
        title_font.setBold(True)
        title_font.setPointSize(max(12, title_font.pointSize() + 1))

        detail_font = QFont(self.font())
        detail_font.setPointSize(max(9, detail_font.pointSize() - 1))

        def make_layout(text, font):
            option = QTextOption()
            option.setWrapMode(QTextOption.WrapMode.WordWrap)
            option.setAlignment(Qt.AlignmentFlag.AlignHCenter)

            text_layout = QTextLayout(text, font)
            text_layout.setTextOption(option)
            text_layout.beginLayout()
            height = 0.0

            while True:
                line = text_layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(max(1, area.width()))
                line.setPosition(QPointF(0.0, height))
                height += line.height()

            text_layout.endLayout()
            return text_layout, height

        title_layout, title_height = make_layout(title, title_font)
        detail_layout, detail_height = make_layout(
            self.description, detail_font
        )

        gap = 8.0
        y = max(
            0.0,
            (area.height() - title_height - gap - detail_height) / 2.0
        )

        painter.save()
        painter.setClipRect(area)
        painter.translate(area.left(), area.top() + y)
        painter.setPen(title_color)
        title_layout.draw(painter, QPointF(0.0, 0.0))
        painter.translate(0.0, title_height + gap)
        painter.setPen(detail_color)
        detail_layout.draw(painter, QPointF(0.0, 0.0))
        painter.restore()
        painter.end()

    def update_text(self):
        marker = "●" if self.isChecked() else "○"

        display_name = "Ultra" if self.name == "Gaming" else self.name
        self.setText(
            f"{marker}  {display_name}\n"
            f"{self.description}"
        )



class NanoOSSmoothProgressBar(QProgressBar):
    """Custom-painted progress bar with a floating-point fill position."""

    def __init__(self, *args, **kwargs):
        self._smooth_value = 0.0
        self._nanoos_value_animation = None
        super().__init__(*args, **kwargs)
        self._smooth_value = float(QProgressBar.value(self))
        self.setTextVisible(False)

    def get_smooth_value(self):
        return float(self._smooth_value)

    def set_smooth_value(self, value):
        try:
            value = max(0.0, min(100.0, float(value)))
        except (TypeError, ValueError):
            return

        self._smooth_value = value
        # Keep the underlying integer value useful for accessibility and
        # existing code while drawing the actual fill fractionally.
        QProgressBar.setValue(self, int(round(value)))
        self.update()

    smoothValue = Property(
        float, get_smooth_value, set_smooth_value
    )

    def setValue(self, value):
        # Cancel either a legacy QPropertyAnimation or V27 timer state.
        animation = getattr(self, "_nanoos_value_animation", None)

        if isinstance(animation, dict):
            timer = animation.get("timer")
            if timer is not None:
                timer.stop()
                timer.deleteLater()
        elif animation is not None:
            animation.stop()
            animation.deleteLater()

        self._nanoos_value_animation = None
        QProgressBar.setValue(self, int(value))

        if hasattr(self, "_smooth_value"):
            self._smooth_value = float(QProgressBar.value(self))

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        outer = self.rect().adjusted(1, 1, -1, -1)
        painter.setPen(QColor("#223543"))
        painter.setBrush(QColor("#0b1118"))
        painter.drawRoundedRect(outer, 7, 7)

        inner = outer.adjusted(2, 2, -2, -2)
        fraction = max(0.0, min(1.0, self._smooth_value / 100.0))
        fill_width = int(round(inner.width() * fraction))

        if fill_width > 0 and inner.height() > 0:
            painter.save()
            painter.setClipRect(inner)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#2f8fb5"))
            painter.drawRoundedRect(
                inner.left(),
                inner.top(),
                fill_width,
                inner.height(),
                6,
                6,
            )
            painter.restore()

        fmt = self.format()
        displayed = fmt

        if re.fullmatch(r"\d+%", fmt.strip()):
            displayed = f"{int(round(self._smooth_value))}%"
        elif "%p" in fmt:
            displayed = fmt.replace(
                "%p", str(int(round(self._smooth_value)))
            )
            displayed = displayed.replace(
                "%v", str(int(round(self._smooth_value)))
            )

        painter.setFont(self.font())
        painter.setPen(QColor("#e6eef6"))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            displayed,
        )
        painter.end()


class NanoOSGameMode(QMainWindow):
    def __init__(self):
        super().__init__()
        QApplication.setStyle("Fusion")

        # ----------------------------------------------------
        # NANOOS PALETTE LOCK
        #
        # Prevent Qt/platform fallback colors from producing
        # random white Windows-95-looking controls.
        # ----------------------------------------------------
        palette = QPalette()

        palette.setColor(
            QPalette.ColorRole.Window,
            QColor("#0b1118"),
        )
        palette.setColor(
            QPalette.ColorRole.WindowText,
            QColor("#e6eef6"),
        )
        palette.setColor(
            QPalette.ColorRole.Base,
            QColor("#0b1118"),
        )
        palette.setColor(
            QPalette.ColorRole.AlternateBase,
            QColor("#101b26"),
        )
        palette.setColor(
            QPalette.ColorRole.ToolTipBase,
            QColor("#0b1118"),
        )
        palette.setColor(
            QPalette.ColorRole.ToolTipText,
            QColor("#e6eef6"),
        )
        palette.setColor(
            QPalette.ColorRole.Text,
            QColor("#e6eef6"),
        )
        palette.setColor(
            QPalette.ColorRole.Button,
            QColor("#101b26"),
        )
        palette.setColor(
            QPalette.ColorRole.ButtonText,
            QColor("#e6eef6"),
        )
        palette.setColor(
            QPalette.ColorRole.BrightText,
            QColor("#ffffff"),
        )
        palette.setColor(
            QPalette.ColorRole.Highlight,
            QColor("#223543"),
        )
        palette.setColor(
            QPalette.ColorRole.HighlightedText,
            QColor("#ffffff"),
        )
        palette.setColor(
            QPalette.ColorRole.Link,
            QColor("#b4c3d2"),
        )
        palette.setColor(
            QPalette.ColorRole.LinkVisited,
            QColor("#7f93a7"),
        )

        # Disabled controls.
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.WindowText,
            QColor("#4e6276"),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.Text,
            QColor("#4e6276"),
        )
        palette.setColor(
            QPalette.ColorGroup.Disabled,
            QPalette.ColorRole.ButtonText,
            QColor("#4e6276"),
        )

        QApplication.instance().setPalette(palette)

        self.state = load_state()
        self.request_process = None
        self.profile_cards = []

        self.setWindowTitle(APP_NAME)
        self.resize(1180, 760)
        self.setMinimumSize(680, 520)

        self.build_ui()
        self.apply_theme()
        self._nanoos_apply_shared_shell_style()
        self._nanoos_polish_controls()
        self.sync_controls()
        self._nanoos_override_attach_dynamic_engine()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(
            lambda: self.isVisible()
            and not self.isMinimized()
            and self.refresh_status()
        )
        self.refresh_timer.start(2000)

        self.refresh_status()

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def build_ui(self):
        # Same frame as NanoOS Welcome / Control Center: a rounded shell
        # holding a sidebar card and the content area.
        root = QWidget()
        root.setObjectName("nanoosWindow")
        outer_layout = QVBoxLayout(root)
        outer_layout.setContentsMargins(18, 18, 18, 18)
        outer_layout.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("shell")
        outer_layout.addWidget(shell, 1)
        root_layout = QHBoxLayout(shell)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        sidebar = self.build_sidebar()
        self._nanoos_override_sidebar = sidebar
        root_layout.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        self._nanoos_override_content_layout = content_layout
        content_layout.setContentsMargins(34, 30, 34, 28)
        content_layout.setSpacing(18)

        header = QHBoxLayout()

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        # Breadcrumb line, as on every NanoOS app page.
        title = QLabel("NANOOS  /  GAMEMODE")
        title.setObjectName("sectionEyebrow")
        title_box.addWidget(title)
        self._nanoos_override_title_label = title

        # Kept (zero height) because the adaptive layout toggles it.
        subtitle = QLabel("")
        subtitle.setObjectName("muted")
        subtitle.setFixedHeight(0)
        title_box.addWidget(subtitle)
        self._nanoos_override_subtitle_label = subtitle

        header.addLayout(title_box)
        self._nanoos_override_header_layout = header

        self._nanoos_override_compact_nav = NanoOSCompactTabSelector()
        self._nanoos_override_compact_nav.setObjectName("NanoOSOverrideCompactNavigation")
        self._nanoos_override_compact_nav.addItems([
            "Overview", "Profiles", "Per-Game", "Hardware", "Settings",
            "Game Library",
            "Performance Lab",
            "Network Lab",
            "Audio Lab",
            "Latency Lab",
        ])
        # NANOOS_OVERRIDE_COMPACT_NAV_V14
        self._nanoos_override_compact_nav.setMinimumWidth(210)
        self._nanoos_override_compact_nav.setMinimumHeight(40)
        self._nanoos_override_compact_nav.setMinimumContentsLength(12)
        self._nanoos_override_compact_nav.setMaxVisibleItems(5)
        self._nanoos_override_compact_nav.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )

        compact_nav_view = self._nanoos_override_compact_nav.view()
        compact_nav_view.setAutoFillBackground(True)
        compact_nav_view.setMinimumWidth(220)
        compact_nav_view.setFixedHeight(210)
        compact_nav_view.setUniformItemSizes(True)
        compact_nav_popup = compact_nav_view.parentWidget()
        if compact_nav_popup is not None:
            compact_nav_popup.setMinimumHeight(214)
            compact_nav_popup.setAutoFillBackground(True)
            compact_nav_popup.setStyleSheet("""
                QFrame {
                    background-color: #101b26;
                    color: #e6eef6;
                    border: 1px solid #31566a;
                }
                QScrollBar:vertical,
                QScrollBar:horizontal {
                    width: 0px;
                    height: 0px;
                    border: none;
                    background: transparent;
                }
                QScrollBar::add-line,
                QScrollBar::sub-line {
                    width: 0px;
                    height: 0px;
                    border: none;
                }
            """)
        compact_nav_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        compact_nav_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        compact_nav_view.setStyleSheet("""
            QListView, QAbstractItemView {
                background-color: #101b26;
                color: #e6eef6;
                border: 1px solid #31566a;
                outline: none;
                padding: 2px;
                selection-background-color: #1f4a61;
                selection-color: #ffffff;
            }
            QListView::item, QAbstractItemView::item {
                background-color: #101b26;
                color: #e6eef6;
                border: none;
                min-height: 24px;
                padding: 3px 12px;
            }
            QListView::item:hover, QAbstractItemView::item:hover {
                background-color: #10293a;
                color: #ffffff;
            }
            QListView::item:selected,
            QAbstractItemView::item:selected {
                background-color: #1f4a61;
                color: #ffffff;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }
            QScrollBar::handle:vertical,
            QScrollBar::handle:horizontal,
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
                border: none;
            }
        """)
        self._nanoos_override_compact_nav.setVisible(False)
        header.addWidget(self._nanoos_override_compact_nav)
        header.addStretch()

        self.header_status = QLabel("● READY")
        self.header_status.setObjectName("statusPill")
        header.addWidget(self.header_status)

        content_layout.addLayout(header)

        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages, 1)

        for builder in (
            self.build_dashboard,
            self.build_profiles_page,
            self.build_games_page,
            self.build_hardware_page,
            self.build_settings_page,
            self.build_game_library_page,
            self.build_performance_lab_page,
            self.build_network_lab_page,
            self.build_audio_lab_page,
            self.build_latency_lab_page,
        ):
            self.pages.addWidget(self._nanoos_scrollable(builder()))
        self.pages.currentChanged.connect(
            self._nanoos_override_sync_navigation
        )

        root_layout.addWidget(content, 1)

        # Prevent Qt's native focus rectangles from appearing as
        # broken square highlights around rounded controls.
        for button in root.findChildren(QPushButton):
            button.setFocusPolicy(Qt.NoFocus)

        for widget in root.findChildren(QListWidget):
            widget.setFocusPolicy(Qt.NoFocus)

        self.setCentralWidget(root)
        self._nanoos_override_compact_nav.currentIndexChanged.connect(
            self._nanoos_override_compact_navigation_changed
        )
        self._nanoos_override_apply_adaptive_decision()

    # Page indexes of the live-telemetry pages (see build_ui order).
    NANOOS_PAGE_PERFORMANCE = 6
    NANOOS_PAGE_NETWORK = 7
    NANOOS_PAGE_AUDIO = 8

    @staticmethod
    def _nanoos_scrollable(page):
        """Wrap a page so it scrolls when the window is shorter than its
        content. Without this Qt squeezes widgets below their minimum
        height (overlapping titles, checkboxes with no labels)."""
        if isinstance(page, QScrollArea):
            return page
        area = QScrollArea()
        area.setObjectName("nanoosPageScroll")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        area.setWidget(page)
        area.viewport().setAutoFillBackground(False)
        page.setAutoFillBackground(False)
        return area

    def _nanoos_page_visible(self, index):
        """True when page `index` is on screen. Telemetry timers use this so
        the app does not poll nvidia-smi/pactl/sysfs while you are gaming
        with the window minimized or on another page."""
        pages = getattr(self, "pages", None)
        if pages is None:
            return True  # still building the UI: allow the first fill
        return (
            self.isVisible()
            and not self.isMinimized()
            and pages.currentIndex() == index
        )

    def _nanoos_refresh_current_page(self, index):
        refreshers = {
            self.NANOOS_PAGE_PERFORMANCE: "refresh_performance_lab",
            self.NANOOS_PAGE_NETWORK: "refresh_network_lab",
            self.NANOOS_PAGE_AUDIO: "refresh_audio_lab",
        }
        name = refreshers.get(index)
        if name and hasattr(self, name):
            QTimer.singleShot(0, getattr(self, name))

    def navigate(self, index, clicked_button=None):
        if index < 0 or index >= self.pages.count():
            return
        self.pages.setCurrentIndex(index)
        self._nanoos_override_sync_navigation(index)
        # Timers skip hidden pages, so bring this one up to date now.
        self._nanoos_refresh_current_page(index)

    def _nanoos_override_compact_navigation_changed(self, index):
        if index >= 0 and index != self.pages.currentIndex():
            self.navigate(index)

    def _nanoos_override_sync_navigation(self, index=None):
        if not hasattr(self, "pages"):
            return

        current = self.pages.currentIndex() if index is None else int(index)
        nav = getattr(self, "_nanoos_override_compact_nav", None)
        if nav is not None and nav.currentIndex() != current:
            previous = nav.blockSignals(True)
            try:
                nav.setCurrentIndex(current)
            finally:
                nav.blockSignals(previous)

        for nav_index, button in enumerate(
            getattr(self, "_nanoos_override_nav_buttons", [])
        ):
            button.setChecked(nav_index == current)

    def _nanoos_override_attach_dynamic_engine(self):
        import logging as _nanoos_override_logging
        import sys as _nanoos_override_sys

        self._nanoos_override_controller = None
        if "/usr/local/lib" not in _nanoos_override_sys.path:
            _nanoos_override_sys.path.insert(0, "/usr/local/lib")

        try:
            # NANOOS_OVERRIDE_DYNAMIC_IMPORT_PATH_V1
            import sys as _nanoos_import_sys
            from pathlib import Path as _NanoOSImportPath
            _nanoos_script_path = _NanoOSImportPath(__file__).resolve()
            _nanoos_library_candidates = (
                _NanoOSImportPath('/usr/lib/nanoos-gamemode'),
                _nanoos_script_path.parents[2] / 'local' / 'lib',
                _NanoOSImportPath('/usr/local/lib'),
            )
            for _nanoos_library in _nanoos_library_candidates:
                if (_nanoos_library / 'nanoos_override' / 'adaptive_ui.py').is_file():
                    if str(_nanoos_library) not in _nanoos_import_sys.path:
                        _nanoos_import_sys.path.insert(0, str(_nanoos_library))
                    break
            else:
                raise ModuleNotFoundError(
                    'NanoOS adaptive UI module not found in expected library paths'
                )
            from nanoos_override.adaptive_ui import attach_adaptive_ui
            controller = attach_adaptive_ui(self)
            controller.decisionChanged.connect(
                self._nanoos_override_apply_adaptive_decision
            )
            self._nanoos_override_controller = controller
            self._nanoos_override_apply_adaptive_decision()
        except Exception:
            _nanoos_override_logging.getLogger(
                "nanoos.override.gamemode"
            ).exception(
                "Nano Dynamic controller unavailable; using local responsive fallback."
            )
            self._nanoos_override_controller = None
            self._nanoos_override_apply_adaptive_decision()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "_nanoos_override_controller", None) is None:
            self._nanoos_override_apply_adaptive_decision()

    def _nanoos_override_apply_adaptive_decision(self, decision=None):
        """NANOOS_OVERRIDE_GAMEMODE_ADAPTIVE_V1: adapt the active GameMode UI."""
        content_layout = getattr(
            self, "_nanoos_override_content_layout", None
        )
        if content_layout is None:
            return

        width = max(1, int(getattr(decision, "width", self.width())))
        mode = getattr(decision, "layout_mode", None)
        if mode not in {"compact", "standard", "expanded"}:
            mode = (
                "compact" if width < 900
                else "standard" if width < 1200
                else "expanded"
            )
        compact = mode == "compact"

        sidebar = getattr(self, "_nanoos_override_sidebar", None)
        if sidebar is not None:
            sidebar.setVisible(not compact)

        nav = getattr(self, "_nanoos_override_compact_nav", None)
        if nav is not None:
            nav.setVisible(compact)
            nav.setMaximumWidth(max(150, min(220, width // 3)))

        if mode == "compact":
            margins = (12, 12, 12, 12)
            spacing = 10
            header_margins = (8, 8, 8, 8)
            header_spacing = 8
        elif mode == "standard":
            margins = (20, 20, 20, 18)
            spacing = 14
            header_margins = (14, 10, 14, 10)
            header_spacing = 12
        else:
            margins = (34, 30, 34, 28)
            spacing = 18
            header_margins = (20, 14, 20, 14)
            header_spacing = 16

        content_layout.setContentsMargins(*margins)
        content_layout.setSpacing(spacing)

        header_layout = getattr(
            self, "_nanoos_override_header_layout", None
        )
        if header_layout is not None:
            header_layout.setContentsMargins(*header_margins)
            header_layout.setSpacing(header_spacing)

        subtitle = getattr(self, "_nanoos_override_subtitle_label", None)
        if subtitle is not None:
            subtitle.setVisible(not compact)

        title = getattr(self, "_nanoos_override_title_label", None)
        if title is not None:
            title.setVisible(width >= 620)

        status = getattr(self, "header_status", None)
        if status is not None:
            status.setVisible(width >= 820)

        self._nanoos_override_sync_navigation()

    def page_header(self, title, subtitle):
        layout = QVBoxLayout()
        layout.setSpacing(4)

        label = QLabel(title)
        label.setObjectName("pageTitle")
        layout.addWidget(label)

        sub = QLabel(subtitle)
        sub.setObjectName("muted")
        layout.addWidget(sub)

        return layout

    def card(self):
        frame = QFrame()
        frame.setObjectName("card")
        return frame

    def build_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)

        layout.addLayout(
            self.page_header(
                "Overview",
                "Control every gaming optimization independently."
            )
        )

        hero = self.card()
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(26, 24, 26, 24)
        hero_layout.setSpacing(10)

        hero_top = QHBoxLayout()

        game_label = QVBoxLayout()

        active_label = QLabel("GAME MODE")
        active_label.setObjectName("eyebrow")
        game_label.addWidget(active_label)

        self.game_mode_big = QLabel("Ready")
        self.game_mode_big.setObjectName("heroTitle")
        game_label.addWidget(self.game_mode_big)

        self.game_mode_detail = QLabel("Waiting for a game request.")
        self.game_mode_detail.setObjectName("muted")
        game_label.addWidget(self.game_mode_detail)

        hero_top.addLayout(game_label)
        hero_top.addStretch()

        self.master_toggle = QPushButton("ENABLE")
        self.master_toggle.setObjectName("masterToggle")
        self.master_toggle.setCheckable(True)
        self.master_toggle.clicked.connect(self.toggle_gamemode)
        self.master_toggle.setMinimumSize(170, 70)

        hero_top.addWidget(self.master_toggle)

        hero_layout.addLayout(hero_top)

        layout.addWidget(hero)

        section = QLabel("OPTIMIZATIONS")
        section.setObjectName("sectionTitle")
        layout.addWidget(section)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        self.cpu_toggle = ToggleButton(
            "CPU Boost",
            "AMD CPU boost control"
        )

        self.gpu_toggle = ToggleButton(
            "Platform Performance",
            "GameMode performance profile"
        )

        self.io_toggle = ToggleButton(
            "I/O Optimization",
            "Highest GameMode I/O priority"
        )

        self.scheduler_toggle = ToggleButton(
            "Scheduler / Priority",
            "Process priority optimization"
        )

        self.screen_toggle = ToggleButton(
            "Display Inhibit",
            "Prevent screensaver while active"
        )

        switches = [
            self.cpu_toggle,
            self.gpu_toggle,
            self.io_toggle,
            self.scheduler_toggle,
            self.screen_toggle,
        ]

        for index, widget in enumerate(switches):
            row = index // 2
            col = index % 2
            grid.addWidget(widget, row, col)

        info = self.card()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(22, 20, 22, 20)

        self.profile_summary = QLabel()
        self.profile_summary.setObjectName("muted")
        info_layout.addWidget(self.profile_summary)

        # Below the toggles: row 2 holds the fifth toggle (Display Inhibit),
        # which this card used to cover.
        grid.addWidget(info, (len(switches) + 1) // 2, 0, 1, 2)

        layout.addLayout(grid)
        layout.addStretch()

        self.cpu_toggle.changed.connect(
            lambda checked: self.optimization_changed("cpu_boost", checked)
        )

        self.gpu_toggle.changed.connect(
            lambda checked: self.optimization_changed("gpu_performance", checked)
        )

        self.io_toggle.changed.connect(
            lambda checked: self.optimization_changed("io_optimization", checked)
        )

        self.scheduler_toggle.changed.connect(
            lambda checked: self.optimization_changed(
                "scheduler_optimization", checked
            )
        )

        self.screen_toggle.changed.connect(
            lambda checked: self.optimization_changed(
                "screensaver_inhibit", checked
            )
        )

        return page

    def build_profiles_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)

        layout.addLayout(
            self.page_header(
                "Profiles",
                "Choose a preset, then fine-tune the individual switches."
            )
        )

        profiles = QHBoxLayout()
        profiles.setSpacing(14)

        descriptions = {
            "Balanced":
                "Quiet desktop behavior with lighter optimization.",
            "Performance":
                "Higher CPU and process priority for demanding workloads.",
            "Gaming":
                "Maximum GameMode optimization preset.",
        }

        for name in ("Balanced", "Performance", "Gaming"):
            card = ProfileCard(name, descriptions[name])
            card.setFixedHeight(250)
            card.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            card.selected.connect(self.select_profile)
            profiles.addWidget(card)
            self.profile_cards.append(card)

        layout.addLayout(profiles)

        details = self.card()
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(24, 22, 24, 22)

        label = QLabel("CURRENT PROFILE")
        label.setObjectName("eyebrow")
        details_layout.addWidget(label)

        self.profile_name = QLabel(self.state["profile"])
        self.profile_name.setObjectName("heroTitle")
        details_layout.addWidget(self.profile_name)

        self.profile_details = QLabel()
        self.profile_details.setObjectName("muted")
        self.profile_details.setWordWrap(True)
        details_layout.addWidget(self.profile_details)

        layout.addWidget(details)
        layout.addStretch()

        return page

    # Display names for the internal profile keys ("Gaming" is shown as
    # "Ultra" everywhere in the UI).
    NANOOS_PROFILE_LABELS = {
        "": "Default",
        "Balanced": "Balanced",
        "Performance": "Performance",
        "Gaming": "Ultra",
    }

    @staticmethod
    def _nanoos_game_key(game):
        """Stable identifier for a detected game across rescans."""
        return f'{game.get("source", "")}|{game.get("launch_target", "")}'

    def _nanoos_game_profile(self, game):
        """The profile assigned to `game`, or "" for the default."""
        assignments = self.state.get("game_profiles")
        if not isinstance(assignments, dict):
            return ""
        profile = assignments.get(self._nanoos_game_key(game), "")
        return profile if profile in PROFILE_DATA else ""

    def build_games_page(self):
        # NANOOS_PER_GAME_PROFILES_V2: real per-game profiles, driven by the
        # games the Game Library detects.
        page = QWidget()
        page.setObjectName("perGamePage")
        page.setStyleSheet("""
            QWidget#perGamePage QFrame#perGameSummary,
            QWidget#perGamePage QFrame#perGameLibrary,
            QWidget#perGamePage QFrame#perGameDetail {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 16px;
            }
            QWidget#perGamePage QLineEdit#gamesSearch {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 10px 12px;
                min-height: 22px;
            }
            QWidget#perGamePage QPushButton#secondaryAction,
            QWidget#perGamePage QPushButton#profileChoice {
                background: #132230;
                color: #e6eef6;
                border: 1px solid #31566a;
                border-radius: 10px;
                padding: 9px 14px;
                min-height: 22px;
            }
            QWidget#perGamePage QPushButton#profileChoice:hover {
                border-color: #2f8fb5;
            }
            QWidget#perGamePage QPushButton#profileChoice:checked {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #66c7e8;
                font-weight: 700;
            }
            QWidget#perGamePage QPushButton#profileChoice:disabled,
            QWidget#perGamePage QPushButton#primaryAction:disabled {
                color: #4e6276;
                border-color: #223543;
                background: #101b26;
            }
            QWidget#perGamePage QPushButton#primaryAction {
                background: #66c7e8;
                color: #0b1118;
                border: 1px solid #9be3f7;
                border-radius: 10px;
                padding: 10px 18px;
                min-height: 22px;
                font-weight: 800;
            }
            QWidget#perGamePage QPushButton#primaryAction:hover {
                background: #e6eef6;
            }
            QWidget#perGamePage QListWidget#gameList {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 12px;
                padding: 6px;
                outline: none;
            }
            QWidget#perGamePage QListWidget#gameList::item {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 9px;
                padding: 10px 12px;
                margin: 3px 0;
            }
            QWidget#perGamePage QListWidget#gameList::item:selected {
                background: #10293a;
                border-color: #2f8fb5;
                color: #ffffff;
            }
            QWidget#perGamePage QLabel#gameDetailTitle {
                color: #e6eef6;
                font-size: 15px;
                font-weight: 700;
            }
        """)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(self.page_header(
            "Per-Game",
            "Give each game its own performance profile."
        ))

        summary = QFrame()
        summary.setObjectName("perGameSummary")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(18, 14, 18, 14)
        summary_text = QVBoxLayout()
        eyebrow = QLabel("PER-GAME PROFILES")
        eyebrow.setObjectName("eyebrow")
        summary_text.addWidget(eyebrow)

        summary_subtitle = QLabel(
            "Pick a profile for a game. When you launch it from NanoOS "
            "GameMode, that profile is applied and GameMode is switched "
            "on first. Games set to Default use your current profile."
        )
        summary_subtitle.setObjectName("muted")
        summary_subtitle.setWordWrap(True)
        summary_text.addWidget(summary_subtitle)
        summary_layout.addLayout(summary_text, 1)

        self.games_count_label = QLabel("0 GAMES")
        self.games_count_label.setObjectName("statusPill")
        summary_layout.addWidget(
            self.games_count_label, 0, Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(summary)

        library = self.card()
        library.setObjectName("perGameLibrary")
        library_layout = QVBoxLayout(library)
        library_layout.setContentsMargins(16, 16, 16, 16)
        library_layout.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self.games_search = QLineEdit()
        self.games_search.setObjectName("gamesSearch")
        self.games_search.setPlaceholderText("Search games, launchers and profiles")
        self.games_search.setAccessibleName("Search games and profiles")
        self.games_search.setClearButtonEnabled(True)
        toolbar.addWidget(self.games_search, 1)

        self.games_reset_button = QPushButton("Rescan")
        self.games_reset_button.setObjectName("secondaryAction")
        self.games_reset_button.setToolTip(
            "Look for installed games again."
        )
        toolbar.addWidget(self.games_reset_button)
        library_layout.addLayout(toolbar)

        self.games_list = QListWidget()
        self.games_list.setObjectName("gameList")
        self.games_list.setWordWrap(True)
        self.games_list.setMinimumHeight(190)
        self.games_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.games_list.setAccessibleName("Game profile list")
        library_layout.addWidget(self.games_list, 1)

        self.games_empty_label = QLabel("")
        self.games_empty_label.setObjectName("muted")
        self.games_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.games_empty_label.setWordWrap(True)
        self.games_empty_label.hide()
        library_layout.addWidget(self.games_empty_label)

        detail = QFrame()
        detail.setObjectName("perGameDetail")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(15, 13, 15, 13)
        detail_layout.setSpacing(8)
        self.games_detail_title = QLabel("Select a game")
        self.games_detail_title.setObjectName("gameDetailTitle")
        detail_layout.addWidget(self.games_detail_title)
        self.games_detail_description = QLabel(
            "Select a game to choose its profile."
        )
        self.games_detail_description.setObjectName("muted")
        self.games_detail_description.setWordWrap(True)
        detail_layout.addWidget(self.games_detail_description)

        choices = QHBoxLayout()
        choices.setSpacing(8)
        self.games_profile_buttons = {}
        for key in ("", "Balanced", "Performance", "Gaming"):
            button = QPushButton(self.NANOOS_PROFILE_LABELS[key])
            button.setObjectName("profileChoice")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(
                lambda _checked=False, key=key:
                    self._nanoos_assign_game_profile(key)
            )
            self.games_profile_buttons[key] = button
            choices.addWidget(button, 1)
        detail_layout.addLayout(choices)

        self.games_launch_button = QPushButton("LAUNCH WITH PROFILE")
        self.games_launch_button.setObjectName("primaryAction")
        self.games_launch_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.games_launch_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.games_launch_button.clicked.connect(
            self._nanoos_launch_per_game_selection
        )
        detail_layout.addWidget(self.games_launch_button)
        library_layout.addWidget(detail)
        layout.addWidget(library, 1)

        self.games_search.textChanged.connect(self.refresh_per_game_page)
        self.games_reset_button.clicked.connect(self.refresh_game_library)
        self.games_list.currentItemChanged.connect(
            self._nanoos_per_game_selection_changed
        )
        self._nanoos_per_game_selection_changed(None)
        return page

    def refresh_per_game_page(self, *_args):
        """Rebuild the Per-Game list from the detected game library."""
        if not hasattr(self, "games_list"):
            return

        games = getattr(self, "_game_library_entries", [])
        query = self.games_search.text().strip().casefold()
        current = self.games_list.currentItem()
        selected_key = (
            self._nanoos_game_key(current.data(Qt.ItemDataRole.UserRole))
            if current is not None else ""
        )

        blocked = self.games_list.blockSignals(True)
        self.games_list.clear()
        custom = 0
        restore_row = -1
        for game in games:
            profile = self._nanoos_game_profile(game)
            if profile:
                custom += 1
            label = self.NANOOS_PROFILE_LABELS[profile]
            searchable = (
                f'{game["name"]} {game["source"]} {label}'
            ).casefold()
            if query and query not in searchable:
                continue
            item = QListWidgetItem(
                f'{game["name"]}\n{game["source"]}  ·  Profile: {label}'
            )
            item.setData(Qt.ItemDataRole.UserRole, game)
            item.setSizeHint(QSize(0, 62))
            self.games_list.addItem(item)
            if self._nanoos_game_key(game) == selected_key:
                restore_row = self.games_list.count() - 1
        self.games_list.blockSignals(blocked)

        total = len(games)
        self.games_count_label.setText(
            f"{total} GAME{'' if total == 1 else 'S'}"
            + (f"  ·  {custom} CUSTOM" if custom else "")
        )

        if self.games_list.count() == 0:
            self.games_empty_label.setText(
                "No games match this search." if query else
                "No installed games detected yet. Install a game with "
                "Steam, Heroic, Lutris or a Minecraft launcher, then "
                "press Rescan."
            )
            self.games_empty_label.show()
            self._nanoos_per_game_selection_changed(None)
        else:
            self.games_empty_label.hide()
            self.games_list.setCurrentRow(max(0, restore_row))
            self._nanoos_per_game_selection_changed(
                self.games_list.currentItem()
            )

    def _nanoos_per_game_selection_changed(self, current, _previous=None):
        game = (
            current.data(Qt.ItemDataRole.UserRole)
            if current is not None else None
        )
        has_game = bool(game)
        for button in self.games_profile_buttons.values():
            button.setEnabled(has_game)
        self.games_launch_button.setEnabled(
            has_game and bool(game.get("can_launch", False))
        )

        if not has_game:
            self.games_detail_title.setText("Select a game")
            self.games_detail_description.setText(
                "Select a game to choose its profile."
            )
            return

        profile = self._nanoos_game_profile(game)
        self.games_profile_buttons[profile].setChecked(True)
        self.games_detail_title.setText(game["name"])
        if profile:
            behavior = (
                f"Launching applies the "
                f"{self.NANOOS_PROFILE_LABELS[profile]} profile and "
                f"switches GameMode on."
            )
        else:
            behavior = "Launching uses your current profile unchanged."
        if not game.get("can_launch", False):
            behavior += " No launch command is available for this entry."
        self.games_detail_description.setText(
            f'{game["source"]}  ·  {behavior}'
        )

    def _nanoos_assign_game_profile(self, profile):
        current = self.games_list.currentItem()
        if current is None:
            return
        game = current.data(Qt.ItemDataRole.UserRole)
        if not game:
            return

        assignments = self.state.get("game_profiles")
        if not isinstance(assignments, dict):
            assignments = {}
        key = self._nanoos_game_key(game)
        if profile:
            assignments[key] = profile
        else:
            assignments.pop(key, None)
        self.state["game_profiles"] = assignments

        try:
            save_state(self.state)
        except OSError as exc:
            self.show_error("Per-Game profile", str(exc))
            return
        self.refresh_per_game_page()

    def _nanoos_launch_per_game_selection(self):
        current = self.games_list.currentItem()
        if current is None:
            return
        game = current.data(Qt.ItemDataRole.UserRole)
        if not game:
            return
        _started, message = self._nanoos_launch_game(game)
        self.games_detail_description.setText(message)

    def _nanoos_prepare_game_profile(self, game):
        """Apply the game's assigned profile and switch GameMode on.

        Returns a short note for the status text ("" when the game uses
        the default profile and nothing was changed).
        """
        profile = self._nanoos_game_profile(game)
        if not profile:
            return ""

        if self.state.get("profile") != profile:
            self.select_profile(profile)
        if not self.master_toggle.isChecked():
            self.master_toggle.setChecked(True)
            self.master_toggle.setText("DISABLE")
            self._nanoos_shutdown_pending = False
            self.enable_gamemode()
        return (
            f" · {self.NANOOS_PROFILE_LABELS[profile]} profile applied, "
            f"GameMode on"
        )

    def build_game_library_page(self):
        # NANOOS_OVERRIDE_GAME_LIBRARY_V17
        page = QWidget()
        page.setObjectName("gameLibraryPage")
        page.setStyleSheet("""
            QWidget#gameLibraryPage QFrame {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 14px;
            }
            QWidget#gameLibraryPage QLineEdit {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #31566a;
                border-radius: 10px;
                padding: 10px;
            }
            QWidget#gameLibraryPage QListWidget {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 5px;
                outline: none;
                selection-background-color: #1f4a61;
                selection-color: #ffffff;
            }
            QWidget#gameLibraryPage QListWidget::item {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 8px;
                padding: 10px;
                margin: 3px;
            }
            QWidget#gameLibraryPage QListWidget::item:selected {
                background: #1f4a61;
                border-color: #66c7e8;
            }
            QWidget#gameLibraryPage QPushButton {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #2f8fb5;
                border-radius: 10px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QWidget#gameLibraryPage QPushButton:hover {
                background: #1f4a61;
                border-color: #66c7e8;
            }
        """)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addLayout(self.page_header(
            "Game Library",
            "Search installed Steam games and launch a selected game."
        ))

        summary = QFrame()
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(18, 14, 18, 14)

        heading = QLabel("GAME LIBRARY")
        heading.setObjectName("eyebrow")
        summary_layout.addWidget(heading)

        self.game_library_status = QLabel("Scanning Steam libraries…")
        self.game_library_status.setObjectName("muted")
        self.game_library_status.setWordWrap(True)
        summary_layout.addWidget(self.game_library_status)
        layout.addWidget(summary)

        browser = QFrame()
        browser_layout = QVBoxLayout(browser)
        browser_layout.setContentsMargins(16, 16, 16, 16)
        browser_layout.setSpacing(12)

        toolbar = QHBoxLayout()
        self.game_library_search = QLineEdit()
        self.game_library_search.setPlaceholderText(
            "Search installed games…"
        )
        self.game_library_search.setClearButtonEnabled(True)
        toolbar.addWidget(self.game_library_search, 1)

        self.game_library_refresh_button = QPushButton("REFRESH")
        toolbar.addWidget(self.game_library_refresh_button)
        browser_layout.addLayout(toolbar)

        self.game_library_list = QListWidget()
        self.game_library_list.setAccessibleName("Installed Steam games")
        self.game_library_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        browser_layout.addWidget(self.game_library_list, 1)

        self.game_library_detail = QLabel(
            "Select a game to inspect its installation."
        )
        self.game_library_detail.setObjectName("muted")
        self.game_library_detail.setWordWrap(True)
        browser_layout.addWidget(self.game_library_detail)

        actions = QHBoxLayout()
        actions.addStretch()
        self.game_library_launch_button = QPushButton(
            "LAUNCH SELECTED GAME"
        )
        self.game_library_launch_button.setEnabled(False)
        actions.addWidget(self.game_library_launch_button)
        browser_layout.addLayout(actions)

        layout.addWidget(browser, 1)

        self._game_library_entries = []
        self.game_library_search.textChanged.connect(
            self.filter_game_library
        )
        self.game_library_refresh_button.clicked.connect(
            self.refresh_game_library
        )
        self.game_library_list.currentItemChanged.connect(
            self.update_game_library_selection
        )
        self.game_library_list.itemDoubleClicked.connect(
            lambda _item: self.launch_selected_game()
        )
        self.game_library_launch_button.clicked.connect(
            self.launch_selected_game
        )

        self.refresh_game_library()
        return page

    def _is_steam_runtime_entry(self, appid, name):
        """Return True for common Steam runtime and compatibility tools."""
        runtime_appids = {
            "228980",   # Steamworks Common Redistributables
            "1070560",  # Steam Linux Runtime (Scout)
            "1391110",  # Steam Linux Runtime (Soldier)
            "1628350",  # Steam Linux Runtime (Sniper)
            "1826330",  # Proton EasyAntiCheat Runtime
            "1161040",  # Proton BattlEye Runtime
        }

        normalized = " ".join(
            name.casefold()
            .replace("_", " ")
            .replace("-", " ")
            .split()
        )

        runtime_markers = (
            "steam linux runtime",
            "steamworks common redistributables",
            "proton easyanticheat runtime",
            "proton easy anti cheat runtime",
            "proton battleye runtime",
            "proton battl eye runtime",
            "proton hotfix",
            "proton experimental",
        )

        return (
            str(appid) in runtime_appids
            or any(marker in normalized for marker in runtime_markers)
        )

    def refresh_game_library(self):
        # NANOOS_OVERRIDE_MULTI_LAUNCHER_LIBRARY_V20
        from pathlib import Path
        import json
        import re

        entries = {}
        runtime_skipped = 0

        def add_entry(
            name, source_name, launch_kind, launch_target,
            install_dir="", details="", runner="", can_launch=True
        ):
            name = str(name or "").strip()
            target = str(launch_target or "").strip()
            if not name or not target:
                return

            key = (source_name.casefold(), target.casefold())
            entries[key] = {
                "name": name,
                "source": source_name,
                "launch_kind": launch_kind,
                "launch_target": target,
                "install_dir": str(install_dir or ""),
                "details": str(details or ""),
                "runner": str(runner or ""),
                "can_launch": bool(can_launch),
            }

        # --------------------------------------------------------
        # Steam: scan native and Flatpak libraries.
        # --------------------------------------------------------
        steam_roots = [
            Path.home() / ".local/share/Steam",
            Path.home() / ".steam/steam",
            Path.home() / ".steam/root",
            Path.home() /
                ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        ]
        steamapps_dirs = set()

        for root in steam_roots:
            steamapps = root / "steamapps"
            if steamapps.is_dir():
                steamapps_dirs.add(steamapps)

                vdf = steamapps / "libraryfolders.vdf"
                try:
                    content = vdf.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError:
                    content = ""

                for raw_path in re.findall(
                    r'"path"\s*"([^"]+)"', content
                ):
                    library_root = Path(raw_path.replace("\\\\", "\\"))
                    library_steamapps = library_root / "steamapps"
                    if library_steamapps.is_dir():
                        steamapps_dirs.add(library_steamapps)

        steam_cmd = shutil.which("steam")
        xdg_open = shutil.which("xdg-open")

        for steamapps in sorted(steamapps_dirs, key=str):
            for manifest in steamapps.glob("appmanifest_*.acf"):
                try:
                    content = manifest.read_text(
                        encoding="utf-8", errors="replace"
                    )
                except OSError:
                    continue

                appid = re.search(r'"appid"\s*"(\d+)"', content)
                name = re.search(r'"name"\s*"([^"]+)"', content)
                install = re.search(r'"installdir"\s*"([^"]+)"', content)

                if not appid or not name:
                    continue

                game_id = appid.group(1)
                title = name.group(1)

                if self._is_steam_runtime_entry(game_id, title):
                    runtime_skipped += 1
                    continue

                install_dir = (
                    steamapps / "common" / install.group(1)
                    if install else steamapps / "common"
                )

                add_entry(
                    title, "Steam", "steam", game_id,
                    install_dir, f"Steam App ID: {game_id}",
                    can_launch=bool(steam_cmd or xdg_open),
                )

        # --------------------------------------------------------
        # Heroic: installed Epic/Legendary and GOG metadata.
        # --------------------------------------------------------
        heroic_installed_files = [
            (
                Path.home() / ".config/legendary/installed.json",
                "legendary", "Heroic · Epic",
            ),
            (
                Path.home() /
                ".var/app/com.heroicgameslauncher.hgl/config/"
                "legendary/installed.json",
                "legendary", "Heroic · Epic",
            ),
            (
                Path.home() / ".config/heroic/gog_store/installed.json",
                "gog", "Heroic · GOG",
            ),
            (
                Path.home() /
                ".var/app/com.heroicgameslauncher.hgl/config/"
                "heroic/gog_store/installed.json",
                "gog", "Heroic · GOG",
            ),
        ]

        heroic_cmd = shutil.which("heroic")
        heroic_can_launch = bool(heroic_cmd or xdg_open)

        for metadata_file, runner, source_name in heroic_installed_files:
            if not metadata_file.is_file():
                continue

            try:
                data = json.loads(
                    metadata_file.read_text(
                        encoding="utf-8", errors="replace"
                    )
                )
            except (OSError, json.JSONDecodeError):
                continue

            if isinstance(data, dict):
                records = data.items()
            elif isinstance(data, list):
                records = [
                    (
                        str(item.get("app_name") or item.get("id") or ""),
                        item,
                    )
                    for item in data if isinstance(item, dict)
                ]
            else:
                continue

            for key, item in records:
                if not isinstance(item, dict):
                    continue

                game_id = (
                    item.get("app_name")
                    or item.get("appName")
                    or item.get("app_id")
                    or item.get("id")
                    or key
                )
                title = (
                    item.get("title")
                    or item.get("name")
                    or item.get("app_title")
                    or item.get("app_name")
                    or str(key)
                )
                install_dir = (
                    item.get("install_path")
                    or item.get("installPath")
                    or item.get("install_dir")
                    or item.get("path")
                    or ""
                )

                if not game_id or not title:
                    continue

                add_entry(
                    title, source_name, "heroic", game_id,
                    install_dir,
                    f"{source_name} · ID: {game_id}",
                    runner=runner,
                    can_launch=heroic_can_launch,
                )

        # --------------------------------------------------------
        # Lutris: query its local SQLite database read-only.
        # --------------------------------------------------------
        lutris_databases = [
            Path.home() / ".local/share/lutris/pga.db",
            Path.home() /
                ".var/app/net.lutris.Lutris/data/lutris/pga.db",
        ]
        lutris_cmd = shutil.which("lutris")
        lutris_can_launch = bool(lutris_cmd or xdg_open)

        for database in lutris_databases:
            if not database.is_file():
                continue

            try:
                connection = sqlite3.connect(
                    database.as_uri() + "?mode=ro", uri=True,
                    timeout=2,
                )
                connection.row_factory = sqlite3.Row
            except sqlite3.Error:
                continue

            try:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table'"
                    )
                }
                if "games" not in tables:
                    continue

                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(games)"
                    )
                }
                if not columns:
                    continue

                rows = connection.execute("SELECT * FROM games").fetchall()

                for row in rows:
                    game = dict(row)

                    title = game.get("name")
                    game_id = game.get("id")
                    slug = game.get("slug") or ""
                    installed_value = game.get("installed")
                    install_dir = (
                        game.get("directory")
                        or game.get("install_path")
                        or ""
                    )
                    config_path = game.get("configpath") or ""

                    if not title:
                        continue

                    if installed_value is not None:
                        if str(installed_value).strip().casefold() not in (
                            "1", "true", "yes", "installed"
                        ):
                            continue
                    elif not install_dir or not Path(install_dir).exists():
                        continue

                    target = game_id or slug
                    if not target:
                        continue

                    add_entry(
                        title, "Lutris", "lutris", target,
                        install_dir,
                        f"Lutris ID: {target}"
                        + (f" · Runner: {game.get('runner')}" if game.get("runner") else "")
                        + (f" · Config: {config_path}" if config_path else ""),
                        can_launch=lutris_can_launch,
                    )

            except (sqlite3.Error, OSError, ValueError):
                pass
            finally:
                connection.close()

        # --------------------------------------------------------
        # Minecraft instances: Prism Launcher and MultiMC.
        # Each instance is listed separately, not as a game runtime.
        # --------------------------------------------------------
        prism_native = (
            shutil.which("prismlauncher")
            or shutil.which("PrismLauncher")
        )
        flatpak_cmd = shutil.which("flatpak")
        multimc_native = (
            shutil.which("multimc")
            or shutil.which("MultiMC")
        )
        modrinth_native = (
            shutil.which("modrinth-app")
            or shutil.which("ModrinthApp")
            or shutil.which("modrinth")
        )
        modrinth_flatpak_available = False
        if flatpak_cmd:
            try:
                modrinth_check = subprocess.run(
                    [
                        flatpak_cmd, "info",
                        "com.modrinth.ModrinthApp",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=3,
                )
                modrinth_flatpak_available = (
                    modrinth_check.returncode == 0
                )
            except (OSError, subprocess.SubprocessError):
                pass

        minecraft_roots = [
            (
                Path.home() / ".local/share/PrismLauncher/instances",
                "Prism Launcher", "prism",
            ),
            (
                Path.home() /
                ".var/app/org.prismlauncher.PrismLauncher/data/"
                "PrismLauncher/instances",
                "Prism Launcher", "prism-flatpak",
            ),
            (
                Path.home() / ".local/share/MultiMC/instances",
                "MultiMC", "multimc",
            ),
            (
                Path.home() / ".local/share/multimc/instances",
                "MultiMC", "multimc",
            ),
            (
                Path.home() / ".local/share/ModrinthApp/profiles",
                "Modrinth App", "modrinth",
            ),
            (
                Path.home() / ".local/share/com.modrinth.theseus/profiles",
                "Modrinth App", "modrinth",
            ),
            (
                Path.home() / ".config/com.modrinth.theseus/profiles",
                "Modrinth App", "modrinth",
            ),
        ]

        for instances_root, launcher_name, launch_kind in minecraft_roots:
            if not instances_root.is_dir():
                continue

            if launch_kind == "prism":
                can_launch = bool(prism_native)
            elif launch_kind == "prism-flatpak":
                can_launch = bool(flatpak_cmd)
            elif launch_kind == "multimc":
                can_launch = bool(multimc_native)
            elif launch_kind == "modrinth":
                can_launch = bool(
                    modrinth_native or modrinth_flatpak_available
                )
            else:
                can_launch = False

            for instance in sorted(instances_root.iterdir(), key=str.casefold):
                if not instance.is_dir():
                    continue

                config = instance / "instance.cfg"
                pack_manifest = instance / "mmc-pack.json"
                profile_json = instance / "profile.json"

                if not (
                    config.is_file()
                    or pack_manifest.is_file()
                    or (
                        launch_kind == "modrinth"
                        and profile_json.is_file()
                    )
                ):
                    continue

                title = instance.name
                if config.is_file():
                    try:
                        cfg_text = config.read_text(
                            encoding="utf-8", errors="replace"
                        )
                        match = re.search(
                            r"(?m)^name=(.*)$", cfg_text
                        )
                        if match and match.group(1).strip():
                            title = match.group(1).strip()
                    except OSError:
                        pass

                if launch_kind == "modrinth" and profile_json.is_file():
                    try:
                        profile_data = json.loads(
                            profile_json.read_text(
                                encoding="utf-8", errors="replace"
                            )
                        )
                        if isinstance(profile_data, dict):
                            metadata = profile_data.get("metadata", {})
                            if not isinstance(metadata, dict):
                                metadata = {}
                            title = (
                                profile_data.get("name")
                                or profile_data.get("title")
                                or profile_data.get("profile_name")
                                or metadata.get("name")
                                or title
                            )
                    except (OSError, json.JSONDecodeError):
                        pass

                add_entry(
                    f"Minecraft · {title}",
                    f"Minecraft · {launcher_name}",
                    launch_kind,
                    title if launch_kind == "modrinth" else instance.name,
                    instance,
                    f"{launcher_name} instance · {instance}",
                    can_launch=can_launch,
                )

        # Save as a list for source-aware UI and search.
        self._game_library_entries = sorted(
            entries.values(),
            key=lambda entry: (
                entry["name"].casefold(),
                entry["source"].casefold(),
            ),
        )

        counts = {}
        for entry in self._game_library_entries:
            counts[entry["source"]] = counts.get(entry["source"], 0) + 1

        if counts:
            source_summary = " · ".join(
                f"{name}: {count}"
                for name, count in sorted(counts.items())
            )
            self.game_library_status.setText(
                f"Found {len(self._game_library_entries)} "
                f"{'entry' if len(self._game_library_entries) == 1 else 'entries'}. "
                f"{source_summary}. "
                f"Ignored {runtime_skipped} Steam runtime/tool entries."
            )
        else:
            self.game_library_status.setText(
                "No installed games detected from Steam, Heroic, Lutris, "
                "Prism Launcher or MultiMC. Refresh after installing a "
                "game or opening the launcher once."
            )

        self.filter_game_library()
        self.refresh_per_game_page()

    def filter_game_library(self, *_args):
        query = self.game_library_search.text().strip().casefold()
        self.game_library_list.clear()

        for game in self._game_library_entries:
            searchable = (
                f'{game["name"]} {game["source"]} '
                f'{game["details"]} {game["install_dir"]}'
            ).casefold()
            if query and query not in searchable:
                continue

            item = QListWidgetItem(
                f'{game["name"]}\n{game["source"]}'
            )
            item.setData(Qt.ItemDataRole.UserRole, game)
            item.setToolTip(
                f'{game["name"]}\n'
                f'Source: {game["source"]}\n'
                f'{game["details"]}\n'
                f'{game["install_dir"]}'
            )
            self.game_library_list.addItem(item)

        if self.game_library_list.count():
            self.game_library_list.setCurrentRow(0)
        else:
            self.game_library_launch_button.setEnabled(False)
            self.game_library_detail.setText(
                "No entries match this search."
                if query else "No installed games found."
            )

    def update_game_library_selection(self, current, _previous=None):
        if current is None:
            self.game_library_launch_button.setEnabled(False)
            return

        game = current.data(Qt.ItemDataRole.UserRole)
        if not game:
            self.game_library_launch_button.setEnabled(False)
            return

        self.game_library_launch_button.setEnabled(
            bool(game.get("can_launch", False))
        )

        detail_lines = [
            game["name"],
            f'Source: {game["source"]}',
            game.get("details", ""),
        ]
        if game.get("install_dir"):
            detail_lines.append(f'Location: {game["install_dir"]}')

        if not game.get("can_launch", False):
            detail_lines.append(
                "Detected, but no supported launch command is available."
            )

        self.game_library_detail.setText(
            "\n".join(line for line in detail_lines if line)
        )

    def launch_selected_game(self):
        item = self.game_library_list.currentItem()
        if item is None:
            self.game_library_detail.setText("Select a game first.")
            return

        game = item.data(Qt.ItemDataRole.UserRole)
        if not game:
            self.game_library_detail.setText("Game information unavailable.")
            return

        _started, message = self._nanoos_launch_game(game)
        self.game_library_detail.setText(message)

    def _nanoos_launch_game(self, game):
        """Launch a detected game. Returns (started, status message).

        A game with a per-game profile gets that profile applied and
        GameMode switched on before its launcher is started.
        """
        from urllib.parse import quote

        kind = game.get("launch_kind")
        target = game.get("launch_target", "")
        uri = ""
        program = ""
        arguments = []

        if kind == "steam":
            uri = f"steam://rungameid/{quote(target, safe='')}"
            program = shutil.which("steam") or shutil.which("xdg-open")
            arguments = [uri]

        elif kind == "heroic":
            runner = game.get("runner") or "legendary"
            uri = (
                "heroic://launch?appName="
                + quote(target, safe="")
                + "&runner="
                + quote(runner, safe="")
            )
            program = shutil.which("heroic") or shutil.which("xdg-open")
            arguments = [uri]

        elif kind == "lutris":
            uri = f"lutris:rungameid/{quote(target, safe='')}"
            program = shutil.which("lutris") or shutil.which("xdg-open")
            arguments = [uri]

        elif kind == "prism":
            program = (
                shutil.which("prismlauncher")
                or shutil.which("PrismLauncher")
            )
            arguments = ["--launch", target]

        elif kind == "prism-flatpak":
            program = shutil.which("flatpak")
            arguments = [
                "run", "org.prismlauncher.PrismLauncher",
                "--launch", target,
            ]

        elif kind == "multimc":
            program = (
                shutil.which("multimc")
                or shutil.which("MultiMC")
            )
            arguments = ["--launch", target]

        elif kind == "modrinth":
            program = (
                shutil.which("modrinth-app")
                or shutil.which("ModrinthApp")
                or shutil.which("modrinth")
            )
            if program:
                arguments = ["--launch", target]
            else:
                program = shutil.which("flatpak")
                arguments = [
                    "run", "com.modrinth.ModrinthApp",
                    "--launch", target,
                ]

        if not program:
            return False, (
                f'No launcher executable found for {game["name"]}.'
            )

        try:
            profile_note = self._nanoos_prepare_game_profile(game)
        except Exception as exc:
            # Never let a profile problem stop the game from starting.
            profile_note = f" · profile not applied ({exc})"

        try:
            result = QProcess.startDetached(program, arguments)
            started = (
                bool(result[0]) if isinstance(result, tuple)
                else bool(result)
            )
        except Exception as exc:
            return False, f'Could not launch {game["name"]}: {exc}'

        if started:
            return True, (
                f'Launch request sent: {game["name"]} · {game["source"]}'
                f'{profile_note}'
            )
        return False, (
            f'Launcher did not start for {game["name"]}. '
            f'Check that {game["source"]} is installed and configured.'
        )

    def _nanoos_smooth_status_text(self, label, new_text):
        """Crossfade status text without restarting the same pending state."""
        from PySide6.QtCore import QPropertyAnimation, QEasingCurve
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        previous = getattr(label, "_nanoos_status_animation", None)
        pending_target = getattr(label, "_nanoos_status_target", None)

        effect = getattr(label, "_nanoos_status_opacity_effect", None)
        if effect is None:
            effect = QGraphicsOpacityEffect(label)
            effect.setOpacity(1.0)
            label.setGraphicsEffect(effect)
            label._nanoos_status_opacity_effect = effect

        # Repeated refreshes for the same pending target must not restart it.
        if previous is not None and pending_target == new_text:
            return

        # If the state has returned to its displayed text, cancel the
        # obsolete transition and restore full opacity.
        if label.text() == new_text:
            if previous is not None:
                try:
                    previous.stop()
                    previous.deleteLater()
                except RuntimeError:
                    pass

            label._nanoos_status_animation = None
            label._nanoos_status_target = None
            effect.setOpacity(1.0)
            return

        if previous is not None:
            try:
                previous.stop()
                previous.deleteLater()
            except RuntimeError:
                pass

        label._nanoos_status_target = new_text

        fade_out = QPropertyAnimation(effect, b"opacity", self)
        fade_out.setDuration(130)
        fade_out.setStartValue(float(effect.opacity()))
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutCubic)
        label._nanoos_status_animation = fade_out

        def swap_text_and_fade_in():
            if getattr(label, "_nanoos_status_animation", None) is not fade_out:
                return
            if getattr(label, "_nanoos_status_target", None) != new_text:
                return

            label.setText(new_text)

            fade_in = QPropertyAnimation(effect, b"opacity", self)
            fade_in.setDuration(210)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
            label._nanoos_status_animation = fade_in

            def finish_fade_in():
                if getattr(
                    label, "_nanoos_status_animation", None
                ) is fade_in:
                    effect.setOpacity(1.0)
                    label._nanoos_status_animation = None
                    label._nanoos_status_target = None
                fade_in.deleteLater()

            fade_in.finished.connect(finish_fade_in)
            fade_out.deleteLater()
            fade_in.start()

        fade_out.finished.connect(swap_text_and_fade_in)
        fade_out.start()

    def build_performance_lab_page(self):
        # NANOOS_OVERRIDE_PERFORMANCE_LAB_V21
        page = QWidget()
        page.setObjectName("performanceLabPage")
        page.setStyleSheet("""
            QWidget#performanceLabPage QFrame {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 14px;
            }
            QWidget#performanceLabPage QLabel {
                background: transparent;
                border: none;
                color: #e6eef6;
            }
            QWidget#performanceLabPage QProgressBar {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 7px;
                min-height: 20px;
                text-align: center;
                font-weight: 600;
            }
            QWidget#performanceLabPage QProgressBar::chunk {
                background: #2f8fb5;
                border-radius: 6px;
            }
            QWidget#performanceLabPage QPushButton {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #2f8fb5;
                border-radius: 10px;
                padding: 9px 14px;
                font-weight: 600;
            }
            QWidget#performanceLabPage QPushButton:hover {
                background: #1f4a61;
                border-color: #66c7e8;
            }
        """)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        layout.addLayout(self.page_header(
            "Performance Lab",
            "Live system telemetry from kernel and hardware interfaces."
        ))

        def metric_card(title_text, bar_name, detail_name):
            card = self.card()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 16, 18, 16)
            card_layout.setSpacing(9)

            title = QLabel(title_text)
            title.setObjectName("sectionTitle")
            card_layout.addWidget(title)

            bar = NanoOSSmoothProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            bar.setFormat("Sampling…")
            bar.setMinimumHeight(24)
            card_layout.addWidget(bar)

            detail = QLabel("Waiting for telemetry…")
            detail.setObjectName("muted")
            detail.setWordWrap(True)
            card_layout.addWidget(detail)

            setattr(self, bar_name, bar)
            setattr(self, detail_name, detail)
            return card

        metrics = QGridLayout()
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)

        metrics.addWidget(metric_card(
            "CPU UTILIZATION",
            "performance_cpu_bar",
            "performance_cpu_detail",
        ), 0, 0)

        metrics.addWidget(metric_card(
            "MEMORY UTILIZATION",
            "performance_memory_bar",
            "performance_memory_detail",
        ), 0, 1)

        metrics.addWidget(metric_card(
            "GPU UTILIZATION",
            "performance_gpu_bar",
            "performance_gpu_detail",
        ), 1, 0)

        metrics.addWidget(metric_card(
            "GPU MEMORY / VRAM",
            "performance_vram_bar",
            "performance_vram_detail",
        ), 1, 1)

        layout.addLayout(metrics)

        system_card = self.card()
        system_layout = QVBoxLayout(system_card)
        system_layout.setContentsMargins(18, 16, 18, 16)
        system_layout.setSpacing(8)

        system_title = QLabel("CPU & SYSTEM DETAILS")
        system_title.setObjectName("sectionTitle")
        system_layout.addWidget(system_title)

        self.performance_system_info = QLabel(
            "Reading CPU policy, frequency, load average and active profile…"
        )
        self.performance_system_info.setObjectName("muted")
        self.performance_system_info.setWordWrap(True)
        system_layout.addWidget(self.performance_system_info)

        layout.addWidget(system_card)

        # NANOOS_OVERRIDE_STORAGE_NETWORK_USB_V28
        device_card = self.card()
        device_layout = QVBoxLayout(device_card)
        device_layout.setContentsMargins(18, 14, 18, 14)
        device_layout.setSpacing(7)

        device_title = QLabel("STORAGE · USB")
        device_title.setObjectName("sectionTitle")
        device_layout.addWidget(device_title)

        self.performance_disk_io_detail = QLabel(
            "Disk I/O: collecting the first sample…"
        )
        self.performance_disk_io_detail.setObjectName("muted")
        self.performance_disk_io_detail.setWordWrap(True)
        device_layout.addWidget(self.performance_disk_io_detail)

        self.performance_storage_detail = QLabel(
            "Mounted volumes: scanning…"
        )
        self.performance_storage_detail.setObjectName("muted")
        self.performance_storage_detail.setWordWrap(True)
        device_layout.addWidget(self.performance_storage_detail)

        self.performance_usb_detail = QLabel(
            "USB storage: scanning…"
        )
        self.performance_usb_detail.setObjectName("muted")
        self.performance_usb_detail.setWordWrap(True)
        device_layout.addWidget(self.performance_usb_detail)

        layout.addWidget(device_card)

        footer = QHBoxLayout()
        self.performance_lab_status = QLabel(
            "Metrics refresh automatically."
        )
        self.performance_lab_status.setObjectName("muted")
        self.performance_lab_status.setWordWrap(True)
        footer.addWidget(self.performance_lab_status, 1)

        self.performance_refresh_button = QPushButton("REFRESH NOW")
        self.performance_refresh_button.clicked.connect(
            self.refresh_performance_lab
        )
        footer.addWidget(self.performance_refresh_button)
        layout.addLayout(footer)
        layout.addStretch()

        self._nanoos_perf_cpu_sample = None

        self._nanoos_perf_timer = QTimer(self)
        self._nanoos_perf_timer.setInterval(1000)
        self._nanoos_perf_timer.timeout.connect(
            lambda: self._nanoos_page_visible(self.NANOOS_PAGE_PERFORMANCE)
            and self.refresh_performance_lab()
        )

        self.refresh_performance_lab()
        self._nanoos_perf_timer.start()
        return page

    def _nanoos_animate_progress(
        self, bar, target_value, duration=1200
    ):
        """Animate fractional bar fill with precise timer-driven easing."""
        import math
        import time

        try:
            target_value = max(0.0, min(100.0, float(target_value)))
        except (TypeError, ValueError):
            return

        previous = getattr(bar, "_nanoos_value_animation", None)

        if isinstance(previous, dict):
            old_timer = previous.get("timer")
            if old_timer is not None:
                old_timer.stop()
                old_timer.deleteLater()
        elif previous is not None:
            previous.stop()
            previous.deleteLater()

        bar._nanoos_value_animation = None
        start_value = float(bar.smoothValue)

        if abs(start_value - target_value) < 0.01:
            bar.set_smooth_value(target_value)
            return

        duration_seconds = max(1, int(duration)) / 1000.0
        start_time = time.monotonic()

        timer = QTimer(bar)
        timer.setTimerType(Qt.TimerType.PreciseTimer)
        timer.setInterval(4)

        state = {
            "timer": timer,
            "start": start_value,
            "target": target_value,
            "start_time": start_time,
        }
        bar._nanoos_value_animation = state

        def animate_frame():
            if getattr(bar, "_nanoos_value_animation", None) is not state:
                timer.stop()
                timer.deleteLater()
                return

            elapsed = time.monotonic() - start_time
            progress = min(1.0, max(0.0, elapsed / duration_seconds))

            # InOutSine easing, evaluated using real elapsed time rather
            # than assuming every timer tick arrives exactly on schedule.
            eased = (1.0 - math.cos(math.pi * progress)) / 2.0
            value = start_value + (target_value - start_value) * eased

            bar.set_smooth_value(value)

            if progress >= 1.0:
                bar.set_smooth_value(target_value)
                timer.stop()

                if getattr(bar, "_nanoos_value_animation", None) is state:
                    bar._nanoos_value_animation = None

                timer.deleteLater()

        timer.timeout.connect(animate_frame)
        timer.start()

    def build_audio_lab_page(self):
        """NANOOS_AUDIO_LAB_OVERDRIVE_V2: premium audio control center."""
        page = QWidget()
        page.setObjectName("audioLabPage")
        page.setStyleSheet("""
            QWidget#audioLabPage QFrame {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 15px;
            }
            QWidget#audioLabPage QLabel {
                background: transparent;
                border: none;
                color: #e6eef6;
            }
            QLabel#audioLabTitle {
                font-size: 26px;
                font-weight: 900;
                color: #e6eef6;
            }
            QLabel#audioLabSubtitle, QLabel#audioLabHint {
                color: #7f93a7;
                font-size: 12px;
            }
            QLabel#audioLabSectionTitle {
                color: #e6eef6;
                font-size: 12px;
                font-weight: 900;
            }
            QLabel#audioLabStatusPill {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #2f8fb5;
                border-radius: 12px;
                padding: 7px 11px;
                font-size: 11px;
                font-weight: 900;
            }
            QLabel#audioMetricCaption {
                color: #b4c3d2;
                font-size: 11px;
                font-weight: 900;
            }
            QLabel#audioMetricValue {
                color: #e6eef6;
                font-size: 18px;
                font-weight: 900;
            }
            QLabel#audioDeviceDetail {
                font-size: 12px;
                padding-top: 2px;
                padding-bottom: 2px;
            }
            QWidget#audioLabPage QFrame {
                min-width: 0;
            }
            QLabel#audioDeviceDetail, QLabel#audioSystemDetail {
                color: #b4c3d2;
                font-size: 12px;
            }
            QLabel#audioVolumeValue {
                color: #e6eef6;
                font-size: 18px;
                font-weight: 900;
            }
            QWidget#audioLabPage QComboBox {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #31566a;
                border-radius: 9px;
                padding: 8px 10px;
                min-height: 25px;
            }
            QWidget#audioLabPage QComboBox QAbstractItemView {
                background: #101b26;
                color: #e6eef6;
                selection-background-color: #1f4a61;
                selection-color: white;
            }
            QWidget#audioLabPage QSlider::groove:horizontal {
                background: #223543;
                height: 6px;
                border-radius: 3px;
            }
            QWidget#audioLabPage QSlider::sub-page:horizontal {
                background: #66c7e8;
                border-radius: 3px;
            }
            QWidget#audioLabPage QSlider::handle:horizontal {
                background: #e6eef6;
                border: 2px solid #66c7e8;
                width: 16px;
                margin: -6px 0;
                border-radius: 9px;
            }
            QWidget#audioLabPage QPushButton {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #2f8fb5;
                border-radius: 10px;
                padding: 9px 13px;
                font-weight: 800;
            }
            QWidget#audioLabPage QPushButton:hover {
                background: #1f4a61;
                border-color: #66c7e8;
            }
            QWidget#audioLabPage QPushButton:disabled {
                background: #101b26;
                color: #7f93a7;
                border-color: #223543;
            }
            QListWidget#audioLabStreamList {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 9px;
                padding: 5px;
            }
            QListWidget#audioLabStreamList::item {
                padding: 7px;
                border-radius: 6px;
            }
            QListWidget#audioLabStreamList::item:selected {
                background: #1f4a61;
                color: white;
            }
            QProgressBar#audioActivityBar {
                background: #0b1118;
                border: none;
                border-radius: 2px;
                max-height: 4px;
                min-height: 4px;
            }
            QProgressBar#audioActivityBar::chunk {
                background: #66c7e8;
                border-radius: 2px;
            }
        """)

        self._nanoos_audio_lab_syncing_controls = False
        self._nanoos_audio_lab_backend_mode = "none"
        self._nanoos_audio_lab_sinks = []
        self._nanoos_audio_lab_sources = []
        self._nanoos_audio_lab_playback_streams = []
        self._nanoos_audio_lab_muted = {
            "sink": False,
            "source": False,
        }

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Premium header.
        hero = self.card()
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 17, 20, 17)
        hero_layout.setSpacing(14)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(5)

        title = QLabel("AUDIO LAB")
        title.setObjectName("audioLabTitle")

        subtitle = QLabel(
            "OVERDRIVE  ·  Live audio control, routing and diagnostics"
        )
        subtitle.setObjectName("audioLabSubtitle")
        subtitle.setWordWrap(True)

        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)

        self.audio_lab_status_pill = QLabel("INITIALIZING")
        self.audio_lab_status_pill.setObjectName("audioLabStatusPill")
        self.audio_lab_status_pill.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        hero_layout.addWidget(self.audio_lab_status_pill)
        layout.addWidget(hero)

        # Animated scan accent; this is decorative, not an audio-level meter.
        self.audio_lab_activity = QProgressBar()
        self.audio_lab_activity.setObjectName("audioActivityBar")
        self.audio_lab_activity.setRange(0, 0)
        self.audio_lab_activity.setTextVisible(False)
        self.audio_lab_activity.setFixedHeight(4)
        layout.addWidget(self.audio_lab_activity)

        # System overview.
        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)

        specs = (
            ("OUTPUT ROUTES", "—", "Playback endpoints", "outputs"),
            ("INPUT ROUTES", "—", "Recording endpoints", "inputs"),
            ("AUDIO ENGINE", "Checking…", "Detected control backend", "engine"),
        )

        for column, (caption_text, initial, hint_text, key) in enumerate(specs):
            card = self.card()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 14, 16, 14)
            card_layout.setSpacing(7)

            caption = QLabel(caption_text)
            caption.setObjectName("audioMetricCaption")

            value = QLabel(initial)
            value.setObjectName("audioMetricValue")
            value.setWordWrap(True)

            hint = QLabel(hint_text)
            hint.setObjectName("audioLabHint")
            hint.setWordWrap(True)

            card_layout.addWidget(caption)
            card_layout.addWidget(value)
            card_layout.addWidget(hint)

            if key == "outputs":
                self.audio_lab_output_count_value = value
            elif key == "inputs":
                self.audio_lab_input_count_value = value
            else:
                self.audio_lab_engine_value = value

            metrics.addWidget(card, 0, column)

        layout.addLayout(metrics)

        # Real output and input controls.
        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(12)
        controls.setVerticalSpacing(12)

        output_card = self.card()
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(18, 16, 18, 16)
        output_layout.setSpacing(10)

        output_title = QLabel("01  ·  PLAYBACK CONTROL")
        output_title.setObjectName("audioLabSectionTitle")
        output_layout.addWidget(output_title)

        self.audio_lab_output_detail = QLabel(
            "Discovering playback devices…"
        )
        self.audio_lab_output_detail.setObjectName("audioDeviceDetail")
        self.audio_lab_output_detail.setWordWrap(True)
        output_layout.addWidget(self.audio_lab_output_detail)

        output_caption = QLabel("OUTPUT DEVICE / DEFAULT ROUTE")
        output_caption.setObjectName("audioMetricCaption")
        output_layout.addWidget(output_caption)

        self.audio_lab_output_combo = QComboBox()
        self.audio_lab_output_combo.setMinimumWidth(0)
        self.audio_lab_output_combo.setMinimumContentsLength(10)
        self.audio_lab_output_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.audio_lab_output_combo.currentIndexChanged.connect(
            lambda _index: self._nanoos_audio_lab_set_default_device("sink")
        )
        output_layout.addWidget(self.audio_lab_output_combo)

        output_volume_row = QHBoxLayout()
        output_volume_row.addWidget(QLabel("MASTER OUTPUT"))
        self.audio_lab_output_volume_value = QLabel("—%")
        self.audio_lab_output_volume_value.setObjectName("audioVolumeValue")
        output_volume_row.addStretch(1)
        output_volume_row.addWidget(self.audio_lab_output_volume_value)
        output_layout.addLayout(output_volume_row)

        self.audio_lab_output_slider = QSlider(Qt.Orientation.Horizontal)
        self.audio_lab_output_slider.setRange(0, 100)
        self.audio_lab_output_slider.setValue(50)
        self.audio_lab_output_slider.setSingleStep(1)
        self.audio_lab_output_slider.valueChanged.connect(
            lambda value: self.audio_lab_output_volume_value.setText(
                f"{value}%"
            )
        )
        self.audio_lab_output_slider.sliderReleased.connect(
            lambda: self._nanoos_audio_lab_apply_volume("sink")
        )
        output_layout.addWidget(self.audio_lab_output_slider)

        self.audio_lab_output_mute_button = QPushButton("MUTE OUTPUT")
        self.audio_lab_output_mute_button.clicked.connect(
            lambda: self._nanoos_audio_lab_toggle_mute("sink")
        )
        output_layout.addWidget(self.audio_lab_output_mute_button)
        controls.addWidget(output_card, 0, 0)

        input_card = self.card()
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(18, 16, 18, 16)
        input_layout.setSpacing(10)

        input_title = QLabel("02  ·  RECORDING CONTROL")
        input_title.setObjectName("audioLabSectionTitle")
        input_layout.addWidget(input_title)

        self.audio_lab_input_detail = QLabel(
            "Discovering recording devices…"
        )
        self.audio_lab_input_detail.setObjectName("audioDeviceDetail")
        self.audio_lab_input_detail.setWordWrap(True)
        input_layout.addWidget(self.audio_lab_input_detail)

        input_caption = QLabel("INPUT DEVICE / DEFAULT ROUTE")
        input_caption.setObjectName("audioMetricCaption")
        input_layout.addWidget(input_caption)

        self.audio_lab_input_combo = QComboBox()
        self.audio_lab_input_combo.setMinimumWidth(0)
        self.audio_lab_input_combo.setMinimumContentsLength(10)
        self.audio_lab_input_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.audio_lab_input_combo.currentIndexChanged.connect(
            lambda _index: self._nanoos_audio_lab_set_default_device("source")
        )
        input_layout.addWidget(self.audio_lab_input_combo)

        input_volume_row = QHBoxLayout()
        input_volume_row.addWidget(QLabel("MICROPHONE GAIN"))
        self.audio_lab_input_volume_value = QLabel("—%")
        self.audio_lab_input_volume_value.setObjectName("audioVolumeValue")
        input_volume_row.addStretch(1)
        input_volume_row.addWidget(self.audio_lab_input_volume_value)
        input_layout.addLayout(input_volume_row)

        self.audio_lab_input_slider = QSlider(Qt.Orientation.Horizontal)
        self.audio_lab_input_slider.setRange(0, 100)
        self.audio_lab_input_slider.setValue(50)
        self.audio_lab_input_slider.setSingleStep(1)
        self.audio_lab_input_slider.valueChanged.connect(
            lambda value: self.audio_lab_input_volume_value.setText(
                f"{value}%"
            )
        )
        self.audio_lab_input_slider.sliderReleased.connect(
            lambda: self._nanoos_audio_lab_apply_volume("source")
        )
        input_layout.addWidget(self.audio_lab_input_slider)

        self.audio_lab_input_mute_button = QPushButton("MUTE INPUT")
        self.audio_lab_input_mute_button.clicked.connect(
            lambda: self._nanoos_audio_lab_toggle_mute("source")
        )
        input_layout.addWidget(self.audio_lab_input_mute_button)
        controls.addWidget(input_card, 1, 0)

        layout.addLayout(controls)

        # Active application streams and actual per-application routing.
        streams_card = self.card()
        streams_layout = QVBoxLayout(streams_card)
        streams_layout.setContentsMargins(18, 16, 18, 16)
        streams_layout.setSpacing(9)

        streams_title = QLabel("03  ·  APPLICATION AUDIO ROUTING")
        streams_title.setObjectName("audioLabSectionTitle")
        streams_layout.addWidget(streams_title)

        self.audio_lab_stream_hint = QLabel(
            "Inspect active playback streams and move a selected app "
            "to a different output device."
        )
        self.audio_lab_stream_hint.setObjectName("audioLabHint")
        self.audio_lab_stream_hint.setWordWrap(True)
        streams_layout.addWidget(self.audio_lab_stream_hint)

        self.audio_lab_stream_list = QListWidget()
        self.audio_lab_stream_list.setObjectName("audioLabStreamList")
        self.audio_lab_stream_list.setMinimumHeight(100)
        self.audio_lab_stream_list.setMaximumHeight(220)
        self.audio_lab_stream_list.setWordWrap(True)
        self.audio_lab_stream_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        streams_layout.addWidget(self.audio_lab_stream_list)

        stream_buttons = QHBoxLayout()
        self.audio_lab_move_stream_button = QPushButton(
            "MOVE SELECTED STREAM TO OUTPUT"
        )
        self.audio_lab_move_stream_button.clicked.connect(
            self._nanoos_audio_lab_move_stream
        )
        stream_buttons.addWidget(self.audio_lab_move_stream_button)

        self.audio_lab_refresh_streams_button = QPushButton(
            "REFRESH STREAMS"
        )
        self.audio_lab_refresh_streams_button.clicked.connect(
            self.refresh_audio_lab
        )
        stream_buttons.addWidget(self.audio_lab_refresh_streams_button)
        streams_layout.addLayout(stream_buttons)
        layout.addWidget(streams_card)

        # Detailed diagnostics.
        diagnostics_card = self.card()
        diagnostics_layout = QVBoxLayout(diagnostics_card)
        diagnostics_layout.setContentsMargins(18, 16, 18, 16)
        diagnostics_layout.setSpacing(9)

        diagnostics_title = QLabel("04  ·  ENGINE & HARDWARE DIAGNOSTICS")
        diagnostics_title.setObjectName("audioLabSectionTitle")
        diagnostics_layout.addWidget(diagnostics_title)

        self.audio_lab_system_detail = QLabel(
            "Checking audio services, sample rate and ALSA hardware…"
        )
        self.audio_lab_system_detail.setObjectName("audioSystemDetail")
        self.audio_lab_system_detail.setWordWrap(True)
        self.audio_lab_system_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        diagnostics_layout.addWidget(self.audio_lab_system_detail)
        layout.addWidget(diagnostics_card)

        footer = QHBoxLayout()
        self.audio_lab_last_update = QLabel("Waiting for first scan…")
        self.audio_lab_last_update.setObjectName("audioLabSubtitle")
        self.audio_lab_last_update.setWordWrap(True)
        footer.addWidget(self.audio_lab_last_update, 1)

        self.audio_lab_refresh_button = QPushButton("SCAN AUDIO SYSTEM")
        self.audio_lab_refresh_button.clicked.connect(
            self.refresh_audio_lab
        )
        footer.addWidget(self.audio_lab_refresh_button)
        layout.addLayout(footer)
        layout.addStretch(1)

        self._nanoos_audio_lab_timer = QTimer(self)
        self._nanoos_audio_lab_timer.setInterval(6000)
        self._nanoos_audio_lab_timer.timeout.connect(
            lambda: self._nanoos_page_visible(self.NANOOS_PAGE_AUDIO)
            and self.refresh_audio_lab()
        )

        self.refresh_audio_lab()
        self._nanoos_audio_lab_timer.start()

        # V2.1: scroll the complete dashboard instead of squeezing its cards.
        scroll = QScrollArea()
        scroll.setObjectName("audioLabScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setWidget(page)
        scroll.setStyleSheet('''
            QScrollArea#audioLabScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea#audioLabScrollArea QScrollBar:vertical {
                background: #0b1118;
                width: 10px;
                margin: 4px 2px;
                border-radius: 5px;
            }
            QScrollArea#audioLabScrollArea QScrollBar::handle:vertical {
                background: #31566a;
                min-height: 32px;
                border-radius: 5px;
            }
            QScrollArea#audioLabScrollArea QScrollBar::handle:vertical:hover {
                background: #66c7e8;
            }
            QScrollArea#audioLabScrollArea QScrollBar::add-line:vertical,
            QScrollArea#audioLabScrollArea QScrollBar::sub-line:vertical {
                height: 0px;
            }
        ''')
        return scroll

    @staticmethod
    def _nanoos_audio_lab_run(command, timeout=0.6):
        """Execute one bounded, shell-free diagnostic command."""
        import subprocess

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                timeout=timeout,
                check=False,
            )
            return result.returncode, result.stdout or ""
        except subprocess.TimeoutExpired:
            return 124, "Command timed out."
        except OSError as exc:
            return 127, str(exc)

    def _nanoos_audio_lab_parse_pactl_devices(
        self, output, kind, default_name=""
    ):
        import re

        singular = "Sink" if kind == "sink" else "Source"
        pattern = rf"(?m)^\s*{singular} #(\d+)\s*$"
        matches = list(re.finditer(pattern, output))
        records = []

        for index, match in enumerate(matches):
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(output)
            )
            block = output[match.end():end]

            def field_value(field):
                found = re.search(
                    rf"(?m)^\s*{re.escape(field)}:\s*(.+?)\s*$",
                    block,
                )
                return found.group(1).strip() if found else ""

            name = field_value("Name") or match.group(1)
            description = field_value("Description") or name
            volume_line = field_value("Volume")
            volume_match = re.search(r"(\d+(?:\.\d+)?)%", volume_line)
            volume = (
                max(0, min(100, round(float(volume_match.group(1)))))
                if volume_match else None
            )
            mute_value = field_value("Mute").lower()
            muted = mute_value == "yes"

            records.append({
                "id": match.group(1),
                "control_id": name,
                "name": name,
                "description": description,
                "default": name == default_name,
                "volume": volume,
                "muted": muted,
            })

        return records

    def _nanoos_audio_lab_parse_wpctl(self, output):
        import re

        devices = {"sinks": [], "sources": []}
        section = None

        for raw_line in output.splitlines():
            line = raw_line.lstrip(" │├└─\t")

            if line.startswith("Sinks:"):
                section = "sinks"
                continue
            if line.startswith("Sources:"):
                section = "sources"
                continue
            if line.startswith((
                "Devices:", "Filters:", "Streams:", "Clients:"
            )):
                section = None
                continue
            if section is None:
                continue

            match = re.match(r"(\*)?\s*(\d+)\.\s+(.+)", line)
            if not match:
                continue

            raw_name = match.group(3).strip()
            volume_match = re.search(r"\[vol:\s*([^\]]+)\]", raw_name)
            raw_volume = volume_match.group(1) if volume_match else ""
            if volume_match:
                raw_name = raw_name[:volume_match.start()].strip()

            try:
                volume = max(0, min(100, round(float(raw_volume) * 100)))
            except ValueError:
                volume = None

            devices[section].append({
                "id": match.group(2),
                "control_id": match.group(2),
                "name": raw_name,
                "description": raw_name,
                "default": bool(match.group(1)),
                "volume": volume,
                "muted": False,
            })

        return devices

    def _nanoos_audio_lab_parse_streams(self, output, kind):
        import re

        header = "Sink Input" if kind == "playback" else "Source Output"
        matches = list(re.finditer(
            rf"(?m)^\s*{re.escape(header)} #(\d+)\s*$",
            output,
        ))
        records = []

        for index, match in enumerate(matches):
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(output)
            )
            block = output[match.end():end]

            def value(pattern):
                found = re.search(pattern, block)
                return found.group(1).strip() if found else ""

            app = value(r'application\.name\s*=\s*"([^"]+)"')
            media = value(r'media\.name\s*=\s*"([^"]+)"')
            binary = value(r'application\.process\.binary\s*=\s*"([^"]+)"')
            route = value(r"(?m)^\s*(?:Sink|Source):\s*(\d+)\s*$")

            records.append({
                "id": match.group(1),
                "name": app or media or binary or f"{header} #{match.group(1)}",
                "media": media,
                "route": route,
                "kind": kind,
            })

        return records

    def _nanoos_audio_lab_selected_record(self, kind):
        combo = (
            self.audio_lab_output_combo
            if kind == "sink"
            else self.audio_lab_input_combo
        )
        records = (
            self._nanoos_audio_lab_sinks
            if kind == "sink"
            else self._nanoos_audio_lab_sources
        )
        selected = combo.currentData()

        for record in records:
            if str(record.get("control_id", "")) == str(selected):
                return record
        return None

    def _nanoos_audio_lab_fill_combo(self, combo, records, default_name):
        old_signals = combo.blockSignals(True)
        try:
            combo.clear()

            for record in records:
                label = record.get("description") or record.get("name", "Unknown")
                if record.get("default"):
                    label = "★  " + label
                combo.addItem(label, record.get("control_id"))

            target_index = -1
            for index, record in enumerate(records):
                if (
                    record.get("name") == default_name
                    or record.get("control_id") == default_name
                    or record.get("default")
                ):
                    target_index = index
                    break

            if target_index < 0 and records:
                target_index = 0

            combo.setCurrentIndex(target_index)
        finally:
            combo.blockSignals(old_signals)

        combo.setEnabled(bool(records))

    def _nanoos_audio_lab_update_selected_controls(self, kind):
        record = self._nanoos_audio_lab_selected_record(kind)

        slider = (
            self.audio_lab_output_slider
            if kind == "sink"
            else self.audio_lab_input_slider
        )
        value_label = (
            self.audio_lab_output_volume_value
            if kind == "sink"
            else self.audio_lab_input_volume_value
        )
        mute_button = (
            self.audio_lab_output_mute_button
            if kind == "sink"
            else self.audio_lab_input_mute_button
        )

        if record is None:
            slider.setEnabled(False)
            mute_button.setEnabled(False)
            value_label.setText("—%")
            return

        volume = record.get("volume")
        muted = bool(record.get("muted", False))

        if self._nanoos_audio_lab_backend_mode == "wpctl":
            code, text = self._nanoos_audio_lab_run(
                ["wpctl", "get-volume", str(record["control_id"])]
            )
            if code == 0:
                import re
                match = re.search(r"Volume:\s*([0-9.]+)", text)
                if match:
                    try:
                        volume = max(
                            0, min(100, round(float(match.group(1)) * 100))
                        )
                    except ValueError:
                        pass
                muted = "MUTED" in text.upper()

        can_control = self._nanoos_audio_lab_backend_mode in ("pactl", "wpctl")
        slider.setEnabled(can_control)
        mute_button.setEnabled(can_control)
        self._nanoos_audio_lab_muted[kind] = muted
        mute_button.setText(
            ("UNMUTE OUTPUT" if muted else "MUTE OUTPUT")
            if kind == "sink"
            else ("UNMUTE INPUT" if muted else "MUTE INPUT")
        )

        if volume is not None and not slider.isSliderDown():
            volume = max(0, min(100, int(volume)))
            old_signals = slider.blockSignals(True)
            slider.setValue(volume)
            slider.blockSignals(old_signals)
            value_label.setText(f"{volume}%")

    def _nanoos_audio_lab_set_default_device(self, kind):
        if getattr(self, "_nanoos_audio_lab_syncing_controls", False):
            return

        combo = (
            self.audio_lab_output_combo
            if kind == "sink"
            else self.audio_lab_input_combo
        )
        selected = combo.currentData()
        if selected is None:
            return

        if self._nanoos_audio_lab_backend_mode == "pactl":
            target = "sink" if kind == "sink" else "source"
            command = ["pactl", f"set-default-{target}", str(selected)]
        elif self._nanoos_audio_lab_backend_mode == "wpctl":
            command = ["wpctl", "set-default", str(selected)]
        else:
            return

        code, output = self._nanoos_audio_lab_run(command)
        if code != 0:
            self.audio_lab_system_detail.setText(
                f"Could not set default {kind} device:\n{output}"
            )
        self.refresh_audio_lab()

    def _nanoos_audio_lab_apply_volume(self, kind):
        if getattr(self, "_nanoos_audio_lab_syncing_controls", False):
            return

        record = self._nanoos_audio_lab_selected_record(kind)
        if record is None:
            return

        slider = (
            self.audio_lab_output_slider
            if kind == "sink"
            else self.audio_lab_input_slider
        )
        value = slider.value()
        identifier = str(record["control_id"])

        if self._nanoos_audio_lab_backend_mode == "pactl":
            command = [
                "pactl",
                "set-sink-volume" if kind == "sink" else "set-source-volume",
                identifier,
                f"{value}%",
            ]
        elif self._nanoos_audio_lab_backend_mode == "wpctl":
            command = ["wpctl", "set-volume", identifier, f"{value}%"]
        else:
            return

        code, output = self._nanoos_audio_lab_run(command)
        if code != 0:
            self.audio_lab_system_detail.setText(
                f"Volume control failed:\n{output}"
            )
        self.refresh_audio_lab()

    def _nanoos_audio_lab_toggle_mute(self, kind):
        if getattr(self, "_nanoos_audio_lab_syncing_controls", False):
            return

        record = self._nanoos_audio_lab_selected_record(kind)
        if record is None:
            return

        muted = not self._nanoos_audio_lab_muted.get(kind, False)
        identifier = str(record["control_id"])

        if self._nanoos_audio_lab_backend_mode == "pactl":
            command = [
                "pactl",
                "set-sink-mute" if kind == "sink" else "set-source-mute",
                identifier,
                "1" if muted else "0",
            ]
        elif self._nanoos_audio_lab_backend_mode == "wpctl":
            command = [
                "wpctl", "set-mute", identifier,
                "1" if muted else "0",
            ]
        else:
            return

        code, output = self._nanoos_audio_lab_run(command)
        if code != 0:
            self.audio_lab_system_detail.setText(
                f"Mute control failed:\n{output}"
            )
        self.refresh_audio_lab()

    def _nanoos_audio_lab_move_stream(self):
        item = self.audio_lab_stream_list.currentItem()
        if item is None:
            self.audio_lab_stream_hint.setText(
                "Select a playback stream first."
            )
            return

        if self._nanoos_audio_lab_backend_mode != "pactl":
            self.audio_lab_stream_hint.setText(
                "Per-app routing requires a working pactl-compatible server."
            )
            return

        stream_id = item.data(Qt.ItemDataRole.UserRole)
        target = self.audio_lab_output_combo.currentData()
        if stream_id is None or target is None:
            self.audio_lab_stream_hint.setText(
                "Select a playback stream and an output device."
            )
            return

        code, output = self._nanoos_audio_lab_run([
            "pactl", "move-sink-input", str(stream_id), str(target)
        ])

        if code == 0:
            self.audio_lab_stream_hint.setText(
                "Playback stream moved. Refreshing audio routes…"
            )
        else:
            self.audio_lab_stream_hint.setText(
                f"Could not move stream:\n{output}"
            )

        self.refresh_audio_lab()

    def refresh_audio_lab(self):
        """Inspect audio endpoints and refresh control state."""
        import re
        import time

        diagnostics = []
        sinks = []
        sources = []
        playback_streams = []
        recording_streams = []
        default_sink = ""
        default_source = ""
        server_name = "No responsive audio-control backend found"
        backend = "UNAVAILABLE"
        mode = "none"
        info_output = ""

        # Prefer the PulseAudio protocol. It also works with pipewire-pulse.
        info_code, info_output = self._nanoos_audio_lab_run(["pactl", "info"])

        if info_code == 0:
            mode = "pactl"
            server_name = "Audio server responded"
            for line in info_output.splitlines():
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key, value = key.strip().lower(), value.strip()
                if key == "server name":
                    server_name = value or server_name
                elif key == "default sink":
                    default_sink = value
                elif key == "default source":
                    default_source = value

            backend = (
                "PIPEWIRE-PULSE"
                if "pipewire" in server_name.lower()
                else "PULSE AUDIO"
            )
            diagnostics.append("Control API: pactl")
            diagnostics.append("Server query: successful")

            sink_code, sink_output = self._nanoos_audio_lab_run(
                ["pactl", "list", "sinks"]
            )
            source_code, source_output = self._nanoos_audio_lab_run(
                ["pactl", "list", "sources"]
            )
            playback_code, playback_output = self._nanoos_audio_lab_run(
                ["pactl", "list", "sink-inputs"]
            )
            recording_code, recording_output = self._nanoos_audio_lab_run(
                ["pactl", "list", "source-outputs"]
            )

            if sink_code == 0:
                sinks = self._nanoos_audio_lab_parse_pactl_devices(
                    sink_output, "sink", default_sink
                )
            else:
                diagnostics.append("Could not list playback endpoints.")

            if source_code == 0:
                sources = self._nanoos_audio_lab_parse_pactl_devices(
                    source_output, "source", default_source
                )
            else:
                diagnostics.append("Could not list recording endpoints.")

            if playback_code == 0:
                playback_streams = self._nanoos_audio_lab_parse_streams(
                    playback_output, "playback"
                )
            if recording_code == 0:
                recording_streams = self._nanoos_audio_lab_parse_streams(
                    recording_output, "recording"
                )

        else:
            # PipeWire-native fallback: enumeration and volume/mute control.
            wp_code, wp_output = self._nanoos_audio_lab_run(
                ["wpctl", "status"]
            )

            if wp_code == 0:
                mode = "wpctl"
                backend = "PIPEWIRE / WPCTL"
                server_name = "PipeWire control interface responded"
                parsed = self._nanoos_audio_lab_parse_wpctl(wp_output)
                sinks = parsed["sinks"]
                sources = parsed["sources"]
                for record in sinks:
                    if record.get("default"):
                        default_sink = record["control_id"]
                        break
                for record in sources:
                    if record.get("default"):
                        default_source = record["control_id"]
                        break
                diagnostics.append("Control API: wpctl")
                diagnostics.append("PipeWire query: successful")
                diagnostics.append(
                    "Per-app routing needs a pactl-compatible server."
                )
            else:
                diagnostics.append("pactl: unavailable or not responding")
                diagnostics.append("wpctl: unavailable or not responding")

        self._nanoos_audio_lab_backend_mode = mode
        self._nanoos_audio_lab_sinks = sinks
        self._nanoos_audio_lab_sources = sources
        self._nanoos_audio_lab_playback_streams = playback_streams

        self._nanoos_audio_lab_syncing_controls = True
        try:
            self._nanoos_audio_lab_fill_combo(
                self.audio_lab_output_combo, sinks, default_sink
            )
            self._nanoos_audio_lab_fill_combo(
                self.audio_lab_input_combo, sources, default_source
            )
        finally:
            self._nanoos_audio_lab_syncing_controls = False

        self.audio_lab_output_count_value.setText(str(len(sinks)))
        self.audio_lab_input_count_value.setText(str(len(sources)))
        self.audio_lab_engine_value.setText(backend)

        default_output_label = next(
            (item.get("description") or item.get("name")
             for item in sinks if item.get("default")),
            default_sink or "Not reported",
        )
        self.audio_lab_output_detail.setText(
            f"{len(sinks)} playback endpoint(s) detected.\n"
            f"Default output: {default_output_label}"
            if sinks else "No playback endpoints reported."
        )
        default_input_label = next(
            (item.get("description") or item.get("name")
             for item in sources if item.get("default")),
            default_source or "Not reported",
        )
        self.audio_lab_input_detail.setText(
            f"{len(sources)} recording endpoint(s) detected.\n"
            f"Default input: {default_input_label}"
            if sources else "No recording endpoints reported."
        )

        self._nanoos_audio_lab_update_selected_controls("sink")
        self._nanoos_audio_lab_update_selected_controls("source")

        self.audio_lab_stream_list.clear()
        for stream in playback_streams:
            route = stream.get("route", "")
            target_name = next(
                (
                    item.get("description") or item.get("name")
                    for item in sinks if str(item.get("id")) == str(route)
                ),
                f"Output ID {route}" if route else "Output not reported",
            )
            label = f"{stream['name']}   ·   {target_name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, stream["id"])
            self.audio_lab_stream_list.addItem(item)

        if not playback_streams:
            item = QListWidgetItem(
                "No active playback streams detected."
            )
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.audio_lab_stream_list.addItem(item)

        can_move_streams = mode == "pactl" and bool(playback_streams) and bool(sinks)
        self.audio_lab_move_stream_button.setEnabled(can_move_streams)
        self.audio_lab_stream_hint.setText(
            f"Playback streams: {len(playback_streams)}  ·  "
            f"Recording streams: {len(recording_streams)}  ·  "
            + (
                "Select an app above to move it to the chosen output."
                if mode == "pactl"
                else "Stream routing controls require pactl compatibility."
            )
        )

        # Sample rate and PipeWire clock information when the server reports it.
        sample_rate = "Not reported"
        rate_match = re.search(
            r"(?i)(?:default sample specification|sample specification)"
            r".*?(\d{4,6})\s*Hz",
            info_output,
        )
        if rate_match:
            sample_rate = f"{rate_match.group(1)} Hz"

        quantum_text = "Not reported"
        if "pipewire" in server_name.lower() or mode == "wpctl":
            meta_code, meta_output = self._nanoos_audio_lab_run(
                ["pw-metadata", "-n", "settings"]
            )
            if meta_code == 0:
                rate_match = re.search(
                    r"default\.clock\.rate[^0-9]*(\d{4,6})",
                    meta_output,
                    re.IGNORECASE,
                )
                quantum_match = re.search(
                    r"default\.clock\.quantum[^0-9]*(\d+)",
                    meta_output,
                    re.IGNORECASE,
                )
                if rate_match:
                    sample_rate = f"{rate_match.group(1)} Hz"
                if quantum_match:
                    quantum_text = quantum_match.group(1)
                if not rate_match and not quantum_match:
                    diagnostics.append(
                        "PipeWire metadata did not expose clock settings."
                    )
            else:
                diagnostics.append(
                    "pw-metadata unavailable; clock settings not reported."
                )

        try:
            alsa_cards = Path("/proc/asound/cards").read_text(
                encoding="utf-8", errors="replace"
            ).strip()
        except OSError:
            alsa_cards = ""

        try:
            alsa_pcm = Path("/proc/asound/pcm").read_text(
                encoding="utf-8", errors="replace"
            ).strip()
        except OSError:
            alsa_pcm = ""

        if not alsa_cards:
            alsa_cards = "No ALSA card inventory found."
        if not alsa_pcm:
            alsa_pcm = "No ALSA PCM inventory found."

        details = [
            f"Backend: {backend}",
            f"Server: {server_name}",
            f"Default playback: {default_sink or 'Not reported'}",
            f"Default recording: {default_source or 'Not reported'}",
            f"Reported sample rate: {sample_rate}",
            f"PipeWire quantum: {quantum_text}",
            f"Active playback streams: {len(playback_streams)}",
            f"Active recording streams: {len(recording_streams)}",
            "",
            "ALSA CARDS",
            "\n".join(alsa_cards.splitlines()[:10]),
            "",
            "ALSA PCM ENDPOINTS",
            "\n".join(alsa_pcm.splitlines()[:12]),
        ]

        if diagnostics:
            details.extend(["", "DIAGNOSTIC NOTES"])
            details.extend(diagnostics)

        details.extend([
            "",
            "Controls use the detected audio backend. Input volume changes "
            "are system microphone-gain adjustments, not audio recording.",
            "The page does not automatically restart services or capture "
            "microphone audio.",
        ])

        self.audio_lab_system_detail.setText("\n".join(details))

        if mode == "none":
            self.audio_lab_status_pill.setText("ENGINE UNAVAILABLE")
        elif not sinks and not sources:
            self.audio_lab_status_pill.setText("NO ROUTES FOUND")
        else:
            self.audio_lab_status_pill.setText("AUDIO ONLINE")

        self.audio_lab_last_update.setText(
            f"Last scan · {time.strftime('%H:%M:%S')} · "
            "automatic refresh every 6 seconds"
        )










    def build_latency_lab_page(self):
        """NANOOS_LATENCY_LAB_DESIGN_V2: premium responsive diagnostics UI."""
        content = QWidget()
        content.setObjectName("latencyLabPage")
        content.setMinimumWidth(0)
        content.setStyleSheet("""
            QWidget#latencyLabPage {
                background: transparent;
            }
            QWidget#latencyLabPage QFrame {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 17px;
            }
            QWidget#latencyLabPage QLabel {
                background: transparent;
                border: none;
                color: #e6eef6;
            }
            QLabel#latencyHeroEyebrow {
                color: #66c7e8;
                font-size: 10px;
                font-weight: 900;
            }
            QLabel#latencyLabTitle {
                color: #e6eef6;
                font-size: 27px;
                font-weight: 900;
            }
            QLabel#latencyLabSubtitle {
                color: #7f93a7;
                font-size: 12px;
            }
            QLabel#latencyLabStatus {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #2f8fb5;
                border-radius: 11px;
                padding: 8px 12px;
                font-size: 10px;
                font-weight: 900;
            }
            QLabel#latencyLabSection {
                color: #e6eef6;
                font-size: 11px;
                font-weight: 900;
            }
            QLabel#latencyLabHint {
                color: #7f93a7;
                font-size: 11px;
            }
            QLabel#latencyMetricCaption {
                color: #b4c3d2;
                font-size: 10px;
                font-weight: 900;
            }
            QLabel#latencyMetricValue {
                color: #e6eef6;
                font-size: 23px;
                font-weight: 900;
            }
            QLabel#latencyMetricPrimary {
                color: #66c7e8;
                font-size: 30px;
                font-weight: 900;
            }
            QLabel#latencyMetricUnit {
                color: #7f93a7;
                font-size: 10px;
            }
            QLabel#latencyLabChart {
                background: #0b1118;
                color: #66c7e8;
                border: 1px solid #223543;
                border-radius: 12px;
                padding: 15px 12px;
                font-family: monospace;
                font-size: 23px;
                font-weight: 800;
            }
            QLabel#latencyLabDetails {
                color: #b4c3d2;
                font-size: 12px;
            }
            QWidget#audioLabPage QLineEdit,
            QWidget#latencyLabPage QLineEdit {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #31566a;
                border-radius: 10px;
                padding: 11px 13px;
                min-height: 23px;
                selection-background-color: #1f4a61;
            }
            QWidget#latencyLabPage QPushButton {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #2f8fb5;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 800;
            }
            QWidget#latencyLabPage QPushButton:hover {
                background: #1f4a61;
                border-color: #66c7e8;
            }
            QWidget#latencyLabPage QPushButton:disabled {
                background: #101b26;
                color: #7f93a7;
                border-color: #223543;
            }
            QPushButton#latencyStartButton {
                background: #1f4a61;
                border: 1px solid #66c7e8;
                color: #e6eef6;
            }
            QPushButton#latencyStartButton:hover {
                background: #1f4a61;
                border-color: #9be3f7;
            }
            QProgressBar#latencyLabProgress {
                background: #0b1118;
                border: 1px solid #223543;
                border-radius: 3px;
                min-height: 7px;
                max-height: 7px;
            }
            QProgressBar#latencyLabProgress::chunk {
                background: #66c7e8;
                border-radius: 3px;
            }
            QScrollArea#latencyLabScroll {
                background: transparent;
                border: none;
            }
            QScrollArea#latencyLabScroll QScrollBar:vertical {
                background: #0b1118;
                width: 10px;
                margin: 4px 2px;
                border-radius: 5px;
            }
            QScrollArea#latencyLabScroll QScrollBar::handle:vertical {
                background: #31566a;
                min-height: 32px;
                border-radius: 5px;
            }
            QScrollArea#latencyLabScroll QScrollBar::handle:vertical:hover {
                background: #66c7e8;
            }
            QScrollArea#latencyLabScroll QScrollBar::add-line:vertical,
            QScrollArea#latencyLabScroll QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # A real scroll container keeps the page usable in compact layouts.
        scroll = QScrollArea()
        scroll.setObjectName("latencyLabScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 8, 12)
        layout.setSpacing(14)

        # HERO · spacious headline with clear status hierarchy.
        hero = self.card()
        hero.setObjectName("latencyHero")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 19, 20, 19)
        hero_layout.setSpacing(14)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(6)

        eyebrow = QLabel("NANOOS  /  NETWORK INTELLIGENCE")
        eyebrow.setObjectName("latencyHeroEyebrow")

        title = QLabel("Latency Lab")
        title.setObjectName("latencyLabTitle")

        subtitle = QLabel(
            "Measure response time, stability and packet delivery."
        )
        subtitle.setObjectName("latencyLabSubtitle")
        subtitle.setWordWrap(True)

        hero_copy.addWidget(eyebrow)
        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)

        self.latency_lab_status = QLabel("READY")
        self.latency_lab_status.setObjectName("latencyLabStatus")
        self.latency_lab_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.latency_lab_status.setMinimumWidth(88)
        hero_layout.addWidget(self.latency_lab_status, 0)

        layout.addWidget(hero)

        # TEST CONSOLE · target and explicit start/stop controls.
        target_card = self.card()
        target_card.setObjectName("latencyTargetCard")
        target_layout = QVBoxLayout(target_card)
        target_layout.setContentsMargins(18, 17, 18, 17)
        target_layout.setSpacing(11)

        target_title = QLabel("01   TEST CONSOLE")
        target_title.setObjectName("latencyLabSection")
        target_layout.addWidget(target_title)

        target_hint = QLabel(
            "Choose an address or hostname. Ten ICMP probes are sent "
            "when the test starts."
        )
        target_hint.setObjectName("latencyLabHint")
        target_hint.setWordWrap(True)
        target_layout.addWidget(target_hint)

        self.latency_lab_target = QLineEdit("1.1.1.1")
        self.latency_lab_target.setMinimumWidth(0)
        self.latency_lab_target.setMaxLength(253)
        self.latency_lab_target.setPlaceholderText(
            "IP address or hostname"
        )
        target_layout.addWidget(self.latency_lab_target)

        buttons = QHBoxLayout()
        buttons.setSpacing(9)

        self.latency_lab_start_button = QPushButton("▶   START TEST")
        self.latency_lab_start_button.setObjectName("latencyStartButton")
        self.latency_lab_start_button.clicked.connect(
            self._nanoos_latency_lab_start_test
        )
        buttons.addWidget(self.latency_lab_start_button, 1)

        self.latency_lab_stop_button = QPushButton("STOP")
        self.latency_lab_stop_button.setEnabled(False)
        self.latency_lab_stop_button.clicked.connect(
            self._nanoos_latency_lab_stop_test
        )
        buttons.addWidget(self.latency_lab_stop_button)

        target_layout.addLayout(buttons)

        self.latency_lab_progress = QProgressBar()
        self.latency_lab_progress.setObjectName("latencyLabProgress")
        self.latency_lab_progress.setRange(0, 10)
        self.latency_lab_progress.setValue(0)
        self.latency_lab_progress.setTextVisible(False)
        target_layout.addWidget(self.latency_lab_progress)

        self.latency_lab_sample_count = QLabel(
            "READY  ·  No samples collected"
        )
        self.latency_lab_sample_count.setObjectName("latencyLabHint")
        self.latency_lab_sample_count.setWordWrap(True)
        target_layout.addWidget(self.latency_lab_sample_count)

        layout.addWidget(target_card)

        # METRICS · four equal cards in a compact two-by-two grid.
        metric_section = QVBoxLayout()
        metric_section.setSpacing(9)

        metric_header = QLabel("02   LIVE TELEMETRY")
        metric_header.setObjectName("latencyLabSection")
        metric_section.addWidget(metric_header)

        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)

        specs = (
            ("CURRENT RTT", "—", "Latest successful reply", "current"),
            ("AVERAGE RTT", "—", "Mean response time", "average"),
            ("JITTER", "—", "Mean change between replies", "jitter"),
            ("PACKET LOSS", "—", "Reported by the ping test", "loss"),
        )

        for i, (caption_text, initial, hint_text, key) in enumerate(specs):
            card = self.card()
            card.setObjectName(
                "latencyPrimaryMetric" if key == "current"
                else "latencyMetricCard"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            card_layout.setSpacing(8)

            caption = QLabel(caption_text)
            caption.setObjectName("latencyMetricCaption")

            value = QLabel(initial)
            value.setObjectName(
                "latencyMetricPrimary"
                if key == "current" else "latencyMetricValue"
            )
            value.setWordWrap(True)

            hint = QLabel(hint_text)
            hint.setObjectName("latencyLabHint")
            hint.setWordWrap(True)

            card_layout.addWidget(caption)
            card_layout.addWidget(value)
            card_layout.addWidget(hint)
            card_layout.addStretch(1)

            if key == "current":
                self.latency_lab_current_value = value
            elif key == "average":
                self.latency_lab_average_value = value
            elif key == "jitter":
                self.latency_lab_jitter_value = value
            else:
                self.latency_lab_loss_value = value

            metrics.addWidget(card, i // 2, i % 2)

        metric_section.addLayout(metrics)
        layout.addLayout(metric_section)

        # HISTORY · actual ping measurements only.
        # HISTORY · plotted samples and compact summary statistics.
        history_card = self.card()
        history_card.setObjectName("latencyHistoryCard")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(18, 17, 18, 17)
        history_layout.setSpacing(12)

        history_header = QHBoxLayout()
        history_title = QLabel("03   LATENCY HISTORY")
        history_title.setObjectName("latencyLabSection")
        history_header.addWidget(history_title)
        history_header.addStretch(1)

        history_badge = QLabel("REAL RTT SAMPLES")
        history_badge.setObjectName("latencyLabHint")
        history_header.addWidget(history_badge)
        history_layout.addLayout(history_header)

        history_hint = QLabel(
            "A live response-time curve across the last 32 successful "
            "replies. The dashed line marks the current test average."
        )
        history_hint.setObjectName("latencyLabHint")
        history_hint.setWordWrap(True)
        history_layout.addWidget(history_hint)

        self.latency_lab_chart = NanoOSLatencyHistoryPlot()
        self.latency_lab_chart.setMinimumHeight(224)
        history_layout.addWidget(self.latency_lab_chart)

        history_stats = QGridLayout()
        history_stats.setContentsMargins(0, 0, 0, 0)
        history_stats.setHorizontalSpacing(10)
        history_stats.setVerticalSpacing(8)

        history_specs = (
            ("MINIMUM", "—", "minimum"),
            ("MAXIMUM", "—", "maximum"),
            ("LATEST", "—", "latest"),
        )

        for column, (caption_text, initial, key) in enumerate(history_specs):
            stat_card = self.card()
            stat_layout = QVBoxLayout(stat_card)
            stat_layout.setContentsMargins(12, 11, 12, 11)
            stat_layout.setSpacing(5)

            caption = QLabel(caption_text)
            caption.setObjectName("latencyMetricCaption")

            value = QLabel(initial)
            value.setObjectName("latencyMetricValue")
            value.setWordWrap(True)

            stat_layout.addWidget(caption)
            stat_layout.addWidget(value)

            if key == "minimum":
                self.latency_lab_history_min_value = value
            elif key == "maximum":
                self.latency_lab_history_max_value = value
            else:
                self.latency_lab_history_latest_value = value

            history_stats.addWidget(stat_card, 0, column)

        history_layout.addLayout(history_stats)

        self.latency_lab_history_meta = QLabel(
            "No successful samples yet. Start a test to populate history."
        )
        self.latency_lab_history_meta.setObjectName("latencyLabHint")
        self.latency_lab_history_meta.setWordWrap(True)
        history_layout.addWidget(self.latency_lab_history_meta)

        layout.addWidget(history_card)

        result_card = self.card()
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(18, 17, 18, 17)
        result_layout.setSpacing(10)

        result_title = QLabel("04   TEST REPORT")
        result_title.setObjectName("latencyLabSection")
        result_layout.addWidget(result_title)

        self.latency_lab_result_detail = QLabel(
            "Your test report will appear here after the first sample."
        )
        self.latency_lab_result_detail.setObjectName("latencyLabDetails")
        self.latency_lab_result_detail.setWordWrap(True)
        self.latency_lab_result_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        result_layout.addWidget(self.latency_lab_result_detail)

        layout.addWidget(result_card)

        footnote = QLabel(
            "Network measurements depend on the selected target, route "
            "and ICMP response behavior. They are not a direct measurement "
            "of latency inside an individual game server."
        )
        footnote.setObjectName("latencyLabHint")
        footnote.setWordWrap(True)
        layout.addWidget(footnote)
        layout.addStretch(1)

        # The existing QProcess-based test engine and handlers remain intact.
        self._nanoos_latency_lab_process = None
        self._nanoos_latency_lab_samples = []
        self._nanoos_latency_lab_history = []
        self._nanoos_latency_lab_output = ""
        self._nanoos_latency_lab_pending = ""
        self._nanoos_latency_lab_active_target = ""
        self._nanoos_latency_lab_stopped_by_user = False

        return scroll

    @staticmethod
    def _nanoos_latency_lab_valid_target(target):
        import ipaddress
        import re

        target = target.strip().rstrip(".")
        if not target or len(target) > 253:
            return False

        try:
            ipaddress.ip_address(target)
            return True
        except ValueError:
            pass

        labels = target.split(".")
        return all(
            len(label) <= 63
            and re.fullmatch(
                r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?",
                label,
            )
            for label in labels
        )

    def _nanoos_latency_lab_start_test(self):
        target = self.latency_lab_target.text().strip().rstrip(".")

        if not self._nanoos_latency_lab_valid_target(target):
            self.latency_lab_status.setText("INVALID TARGET")
            self.latency_lab_result_detail.setText(
                "Enter a valid IP address or hostname and try again."
            )
            return

        active = getattr(self, "_nanoos_latency_lab_process", None)
        if active is not None and (
            active.state() != QProcess.ProcessState.NotRunning
        ):
            return

        self._nanoos_latency_lab_samples = []
        self._nanoos_latency_lab_output = ""
        self._nanoos_latency_lab_pending = ""
        self._nanoos_latency_lab_active_target = target
        self._nanoos_latency_lab_stopped_by_user = False

        self.latency_lab_current_value.setText("—")
        self.latency_lab_average_value.setText("—")
        self.latency_lab_jitter_value.setText("—")
        self.latency_lab_loss_value.setText("Measuring…")
        self.latency_lab_progress.setValue(0)
        self.latency_lab_status.setText("RUNNING")
        self.latency_lab_result_detail.setText(
            f"Running 10 ping samples against {target}…"
        )
        self.latency_lab_sample_count.setText(
            "Waiting for the first reply…"
        )

        self.latency_lab_start_button.setEnabled(False)
        self.latency_lab_stop_button.setEnabled(True)
        self.latency_lab_target.setEnabled(False)

        process = QProcess(self)
        process.setProgram("ping")
        process.setArguments([
            "-n", "-i", "1", "-W", "2", "-c", "10", target
        ])
        process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        process.readyReadStandardOutput.connect(
            self._nanoos_latency_lab_read_output
        )
        process.finished.connect(
            self._nanoos_latency_lab_finished
        )
        process.errorOccurred.connect(
            self._nanoos_latency_lab_process_error
        )

        self._nanoos_latency_lab_process = process
        process.start()

    def _nanoos_latency_lab_read_output(self):
        import re

        process = getattr(self, "_nanoos_latency_lab_process", None)
        if process is None:
            return

        raw = bytes(process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        if not raw:
            return

        self._nanoos_latency_lab_output += raw
        combined = self._nanoos_latency_lab_pending + raw
        lines = combined.split("\n")
        self._nanoos_latency_lab_pending = lines.pop()

        for line in lines:
            match = re.search(
                r"time[=<]\s*([\d.]+)\s*ms", line, re.IGNORECASE
            )
            if not match:
                continue

            try:
                sample = float(match.group(1))
            except ValueError:
                continue

            self._nanoos_latency_lab_samples.append(sample)
            self._nanoos_latency_lab_history.append(sample)
            self._nanoos_latency_lab_history = (
                self._nanoos_latency_lab_history[-32:]
            )
            self._nanoos_latency_lab_update_metrics()

            samples = self._nanoos_latency_lab_samples
            self.latency_lab_progress.setValue(min(10, len(samples)))
            self.latency_lab_sample_count.setText(
                f"{len(samples)} successful replies in this test · "
                f"{len(self._nanoos_latency_lab_history)} recent samples "
                "in history"
            )

    def _nanoos_latency_lab_update_metrics(self):
        samples = self._nanoos_latency_lab_samples
        if not samples:
            return

        current = samples[-1]
        average = sum(samples) / len(samples)
        jitter = (
            sum(
                abs(samples[i] - samples[i - 1])
                for i in range(1, len(samples))
            ) / (len(samples) - 1)
            if len(samples) > 1 else None
        )

        self.latency_lab_current_value.setText(f"{current:.2f} ms")
        self.latency_lab_average_value.setText(f"{average:.2f} ms")
        self.latency_lab_jitter_value.setText(
            f"{jitter:.2f} ms" if jitter is not None else "—"
        )

        history = self._nanoos_latency_lab_history[-32:]
        self.latency_lab_chart.set_samples(history)

        if history:
            history_min = min(history)
            history_max = max(history)
            history_latest = history[-1]

            self.latency_lab_history_min_value.setText(
                f"{history_min:.2f} ms"
            )
            self.latency_lab_history_max_value.setText(
                f"{history_max:.2f} ms"
            )
            self.latency_lab_history_latest_value.setText(
                f"{history_latest:.2f} ms"
            )
            self.latency_lab_history_meta.setText(
                f"{len(history)} real sample(s) in view  ·  "
                f"range {history_min:.2f}–{history_max:.2f} ms  ·  "
                "newest sample at right"
            )
        else:
            self.latency_lab_history_min_value.setText("—")
            self.latency_lab_history_max_value.setText("—")
            self.latency_lab_history_latest_value.setText("—")
            self.latency_lab_history_meta.setText(
                "No successful samples yet. Start a test to populate history."
            )

        self.latency_lab_result_detail.setText(
            f"Target: {self._nanoos_latency_lab_active_target}\n"
            f"Replies received: {len(samples)}\n"
            f"Current RTT: {current:.2f} ms\n"
            f"Average RTT: {average:.2f} ms\n"
            f"Minimum RTT: {min(samples):.2f} ms\n"
            f"Maximum RTT: {max(samples):.2f} ms\n"
            + (
                f"Jitter estimate: {jitter:.2f} ms"
                if jitter is not None
                else "Jitter estimate: waiting for a second reply"
            )
        )

    def _nanoos_latency_lab_stop_test(self):
        process = getattr(self, "_nanoos_latency_lab_process", None)
        if process is None:
            return

        if process.state() == QProcess.ProcessState.NotRunning:
            return

        self._nanoos_latency_lab_stopped_by_user = True
        self.latency_lab_status.setText("STOPPING")
        self.latency_lab_result_detail.setText(
            "Stopping the test. Available samples will be retained."
        )
        process.terminate()

        QTimer.singleShot(
            1200,
            lambda proc=process:
                proc.kill()
                if proc.state() != QProcess.ProcessState.NotRunning
                else None,
        )

    def _nanoos_latency_lab_process_error(self, error):
        if error != QProcess.ProcessError.FailedToStart:
            return

        process = getattr(self, "_nanoos_latency_lab_process", None)
        if process is None:
            return

        self.latency_lab_status.setText("PING UNAVAILABLE")
        self.latency_lab_loss_value.setText("—")
        self.latency_lab_result_detail.setText(
            "Could not start the ping utility. Check that the ping "
            "command is installed and available in PATH."
        )

        self._nanoos_latency_lab_process = None
        process.deleteLater()

        self.latency_lab_start_button.setEnabled(True)
        self.latency_lab_stop_button.setEnabled(False)
        self.latency_lab_target.setEnabled(True)

    def _nanoos_latency_lab_finished(self, exit_code, exit_status):
        import re

        process = getattr(self, "_nanoos_latency_lab_process", None)
        if process is None:
            return

        self._nanoos_latency_lab_read_output()

        pending = self._nanoos_latency_lab_pending.strip()
        self._nanoos_latency_lab_pending = ""
        if pending:
            saved_output = self._nanoos_latency_lab_output
            self._nanoos_latency_lab_output += "\n" + pending
            # Parse a final reply line without reading the process again.
            match = re.search(
                r"time[=<]\s*([\d.]+)\s*ms", pending, re.IGNORECASE
            )
            if match:
                try:
                    sample = float(match.group(1))
                    self._nanoos_latency_lab_samples.append(sample)
                    self._nanoos_latency_lab_history.append(sample)
                    self._nanoos_latency_lab_history = (
                        self._nanoos_latency_lab_history[-32:]
                    )
                    self._nanoos_latency_lab_update_metrics()
                except ValueError:
                    pass

        output = self._nanoos_latency_lab_output
        loss_match = re.search(
            r"(\d+(?:\.\d+)?)%\s*packet loss", output, re.IGNORECASE
        )
        loss_text = "Not reported"

        if loss_match:
            loss_value = float(loss_match.group(1))
            loss_text = f"{loss_value:.1f}%"
        else:
            counts = re.search(
                r"(\d+)\s+packets transmitted,\s*"
                r"(\d+)\s+(?:packets\s+)?received",
                output,
                re.IGNORECASE,
            )
            if counts:
                sent = int(counts.group(1))
                received = int(counts.group(2))
                if sent:
                    loss_text = f"{100.0 * (sent - received) / sent:.1f}%"

        self.latency_lab_loss_value.setText(loss_text)

        samples = self._nanoos_latency_lab_samples
        stopped = self._nanoos_latency_lab_stopped_by_user

        if stopped:
            self.latency_lab_status.setText("STOPPED")
        elif samples:
            self.latency_lab_status.setText("TEST COMPLETE")
            self.latency_lab_progress.setValue(10)
        else:
            self.latency_lab_status.setText("NO REPLIES")

        if samples:
            summary = (
                f"Target: {self._nanoos_latency_lab_active_target}\n"
                f"Successful replies: {len(samples)}\n"
                f"Average RTT: {sum(samples) / len(samples):.2f} ms\n"
                f"Minimum RTT: {min(samples):.2f} ms\n"
                f"Maximum RTT: {max(samples):.2f} ms\n"
                f"Packet loss: {loss_text}\n"
            )
            if stopped:
                summary += "Test stopped early; results are partial."
            else:
                summary += f"Ping process exit code: {exit_code}"
        else:
            summary = (
                f"Target: {self._nanoos_latency_lab_active_target}\n"
                "No successful ping replies were measured.\n"
                f"Packet loss: {loss_text}\n"
                "Check connectivity, DNS/route configuration, firewall "
                "rules, and whether the target responds to ICMP."
            )

        self.latency_lab_result_detail.setText(summary)

        self._nanoos_latency_lab_process = None
        process.deleteLater()

        self.latency_lab_start_button.setEnabled(True)
        self.latency_lab_stop_button.setEnabled(False)
        self.latency_lab_target.setEnabled(True)

    def build_network_lab_page(self):
        """NANOOS_NETWORK_LAB_V1: dedicated live network dashboard."""
        page = QWidget()
        page.setObjectName("networkLabPage")
        page.setStyleSheet("""
            QWidget#networkLabPage QFrame {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 15px;
            }
            QWidget#networkLabPage QLabel {
                background: transparent;
                border: none;
                color: #e6eef6;
            }
            QLabel#networkLabTitle {
                font-size: 25px;
                font-weight: 800;
                color: #e6eef6;
            }
            QLabel#networkLabSubtitle,
            QLabel#networkMetricHint {
                color: #7f93a7;
                font-size: 12px;
            }
            QLabel#networkLabSectionTitle {
                font-size: 12px;
                font-weight: 800;
                color: #e6eef6;
            }
            QLabel#networkStatusPill {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #2f8fb5;
                border-radius: 12px;
                padding: 7px 11px;
                font-size: 11px;
                font-weight: 800;
            }
            QLabel#networkMetricCaption {
                color: #b4c3d2;
                font-size: 11px;
                font-weight: 800;
            }
            QLabel#networkMetricValue {
                color: #e6eef6;
                font-size: 25px;
                font-weight: 800;
            }
            QLabel#networkInterfaceDetail,
            QLabel#networkConnectionDetail,
            QLabel#networkLatencyDetail {
                color: #b4c3d2;
                font-size: 12px;
            }
            QWidget#networkLabPage QPushButton {
                background: #10293a;
                color: #e6eef6;
                border: 1px solid #2f8fb5;
                border-radius: 10px;
                padding: 9px 14px;
                font-weight: 700;
            }
            QWidget#networkLabPage QPushButton:hover {
                background: #1f4a61;
                border-color: #66c7e8;
            }
            QWidget#networkLabPage QPushButton:disabled {
                color: #7f93a7;
                background: #101b26;
                border-color: #223543;
            }
            QProgressBar#networkActivityBar {
                background: #0b1118;
                border: none;
                border-radius: 2px;
                max-height: 4px;
                min-height: 4px;
            }
            QProgressBar#networkActivityBar::chunk {
                background: #66c7e8;
                border-radius: 2px;
            }
        """)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Header card.
        hero = self.card()
        hero.setObjectName("networkHeroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(20, 17, 20, 17)
        hero_layout.setSpacing(14)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(5)

        title = QLabel("NETWORK LAB")
        title.setObjectName("networkLabTitle")
        subtitle = QLabel(
            "Live interface telemetry, connection details and latency."
        )
        subtitle.setObjectName("networkLabSubtitle")
        subtitle.setWordWrap(True)

        hero_copy.addWidget(title)
        hero_copy.addWidget(subtitle)
        hero_layout.addLayout(hero_copy, 1)

        self.network_lab_status_pill = QLabel("SCANNING")
        self.network_lab_status_pill.setObjectName("networkStatusPill")
        self.network_lab_status_pill.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        hero_layout.addWidget(self.network_lab_status_pill, 0)

        layout.addWidget(hero)

        # Continuously animated activity strip.
        self.network_lab_activity = QProgressBar()
        self.network_lab_activity.setObjectName("networkActivityBar")
        self.network_lab_activity.setRange(0, 0)
        self.network_lab_activity.setTextVisible(False)
        self.network_lab_activity.setFixedHeight(4)
        layout.addWidget(self.network_lab_activity)

        # Live throughput metric cards.
        metrics = QGridLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setHorizontalSpacing(12)
        metrics.setVerticalSpacing(12)

        metric_specs = (
            ("DOWNLOAD", "Sampling…", "Received by this system", "download"),
            ("UPLOAD", "Sampling…", "Sent by this system", "upload"),
            ("ACTIVE LINKS", "—", "Detected usable interfaces", "links"),
        )

        for column, (caption_text, initial, hint_text, key) in enumerate(
            metric_specs
        ):
            metric_card = self.card()
            metric_card.setObjectName("networkMetricCard")
            metric_layout = QVBoxLayout(metric_card)
            metric_layout.setContentsMargins(16, 15, 16, 15)
            metric_layout.setSpacing(7)

            caption = QLabel(caption_text)
            caption.setObjectName("networkMetricCaption")

            value = QLabel(initial)
            value.setObjectName("networkMetricValue")
            value.setWordWrap(True)

            hint = QLabel(hint_text)
            hint.setObjectName("networkMetricHint")
            hint.setWordWrap(True)

            metric_layout.addWidget(caption)
            metric_layout.addWidget(value)
            metric_layout.addWidget(hint)

            if key == "download":
                self.network_lab_download_value = value
            elif key == "upload":
                self.network_lab_upload_value = value
            else:
                self.network_lab_active_value = value

            metrics.addWidget(metric_card, 0, column)

        layout.addLayout(metrics)

        # Interface inventory and individual rates.
        interface_card = self.card()
        interface_layout = QVBoxLayout(interface_card)
        interface_layout.setContentsMargins(18, 15, 18, 15)
        interface_layout.setSpacing(9)

        interface_title = QLabel("INTERFACES · LIVE THROUGHPUT")
        interface_title.setObjectName("networkLabSectionTitle")
        interface_layout.addWidget(interface_title)

        self.network_lab_interface_detail = QLabel(
            "Discovering non-loopback interfaces…"
        )
        self.network_lab_interface_detail.setObjectName(
            "networkInterfaceDetail"
        )
        self.network_lab_interface_detail.setWordWrap(True)
        self.network_lab_interface_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        interface_layout.addWidget(self.network_lab_interface_detail)
        layout.addWidget(interface_card)

        # Connection information and latency diagnostics.
        lower = QGridLayout()
        lower.setContentsMargins(0, 0, 0, 0)
        lower.setHorizontalSpacing(12)
        lower.setVerticalSpacing(12)

        connection_card = self.card()
        connection_layout = QVBoxLayout(connection_card)
        connection_layout.setContentsMargins(18, 15, 18, 15)
        connection_layout.setSpacing(9)

        connection_title = QLabel("CONNECTION DETAILS")
        connection_title.setObjectName("networkLabSectionTitle")
        connection_layout.addWidget(connection_title)

        self.network_lab_connection_detail = QLabel(
            "Reading interface addresses, route and DNS information…"
        )
        self.network_lab_connection_detail.setObjectName(
            "networkConnectionDetail"
        )
        self.network_lab_connection_detail.setWordWrap(True)
        self.network_lab_connection_detail.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        connection_layout.addWidget(self.network_lab_connection_detail)
        lower.addWidget(connection_card, 0, 0)

        latency_card = self.card()
        latency_layout = QVBoxLayout(latency_card)
        latency_layout.setContentsMargins(18, 15, 18, 15)
        latency_layout.setSpacing(9)

        latency_title = QLabel("LATENCY DIAGNOSTICS")
        latency_title.setObjectName("networkLabSectionTitle")
        latency_layout.addWidget(latency_title)

        self.network_lab_latency_detail = QLabel(
            "Ready to test reachability to 1.1.1.1."
        )
        self.network_lab_latency_detail.setObjectName(
            "networkLatencyDetail"
        )
        self.network_lab_latency_detail.setWordWrap(True)
        latency_layout.addWidget(self.network_lab_latency_detail)

        self.network_lab_ping_button = QPushButton("RUN PING TEST")
        self.network_lab_ping_button.clicked.connect(
            self._nanoos_network_lab_start_ping
        )
        latency_layout.addWidget(self.network_lab_ping_button)
        lower.addWidget(latency_card, 0, 1)

        layout.addLayout(lower)

        # Footer controls and last update.
        footer = QHBoxLayout()
        self.network_lab_last_update = QLabel(
            "Waiting for the first interface sample…"
        )
        self.network_lab_last_update.setObjectName("networkLabSubtitle")
        self.network_lab_last_update.setWordWrap(True)
        footer.addWidget(self.network_lab_last_update, 1)

        self.network_lab_refresh_button = QPushButton("REFRESH NOW")
        self.network_lab_refresh_button.clicked.connect(
            self.refresh_network_lab
        )
        footer.addWidget(self.network_lab_refresh_button)
        layout.addLayout(footer)
        layout.addStretch(1)

        self._nanoos_network_io_sample = None
        self._network_lab_ping_process = None
        self._network_lab_ping_started = None

        self._nanoos_network_lab_timer = QTimer(self)
        self._nanoos_network_lab_timer.setInterval(1200)
        self._nanoos_network_lab_timer.timeout.connect(
            lambda: self._nanoos_page_visible(self.NANOOS_PAGE_NETWORK)
            and self.refresh_network_lab()
        )

        self._nanoos_network_lab_ping_timer = QTimer(self)
        self._nanoos_network_lab_ping_timer.setInterval(100)
        self._nanoos_network_lab_ping_timer.timeout.connect(
            self._nanoos_network_lab_poll_ping
        )

        self.refresh_network_lab()
        self._nanoos_network_lab_timer.start()
        return page

    @staticmethod
    def _nanoos_network_lab_format_rate(value):
        value = max(0.0, float(value))
        units = ("B/s", "KiB/s", "MiB/s", "GiB/s")
        unit = units[0]
        for unit in units:
            if value < 1024.0 or unit == units[-1]:
                break
            value /= 1024.0
        if unit == "B/s":
            return f"{value:.0f} {unit}"
        return f"{value:.1f} {unit}"

    def _nanoos_network_lab_ipv4(self, interface):
        try:
            import fcntl
            import socket
            import struct

            with socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM
            ) as sock:
                request = struct.pack(
                    "256s", interface[:15].encode("utf-8")
                )
                result = fcntl.ioctl(sock.fileno(), 0x8915, request)
                return socket.inet_ntoa(result[20:24])
        except (OSError, ImportError, ValueError, struct.error if False else OSError):
            return "—"

    def _nanoos_network_lab_default_gateway(self):
        try:
            import socket
            import struct

            lines = Path("/proc/net/route").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()[1:]

            for line in lines:
                fields = line.split()
                if len(fields) < 4 or fields[1] != "00000000":
                    continue
                try:
                    flags = int(fields[3], 16)
                    gateway_value = int(fields[2], 16)
                except ValueError:
                    continue
                if flags & 1:
                    return socket.inet_ntoa(
                        struct.pack("<L", gateway_value)
                    )
        except (OSError, ImportError):
            pass
        return "Not detected"

    def _nanoos_network_lab_dns_servers(self):
        servers = []
        try:
            for line in Path("/etc/resolv.conf").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                fields = line.split()
                if len(fields) >= 2 and fields[0] == "nameserver":
                    if fields[1] not in servers:
                        servers.append(fields[1])
        except OSError:
            pass
        return servers[:4]

    def refresh_network_lab(self):
        """Refresh Linux interface counters and connection diagnostics."""
        import time

        now = time.monotonic()
        network_counters = {}
        ignored_interfaces = (
            "lo", "docker", "veth", "virbr", "br-",
            "tun", "tap", "wg", "tailscale", "zt",
        )
        net_root = Path("/sys/class/net")

        try:
            lines = Path("/proc/net/dev").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()[2:]

            for line in lines:
                if ":" not in line:
                    continue

                interface, counters_text = line.split(":", 1)
                interface = interface.strip()
                if (
                    not interface
                    or interface.startswith(ignored_interfaces)
                ):
                    continue

                fields = counters_text.split()
                if len(fields) < 9:
                    continue

                try:
                    rx_bytes = int(fields[0])
                    tx_bytes = int(fields[8])
                except ValueError:
                    continue

                try:
                    state = (
                        net_root / interface / "operstate"
                    ).read_text(encoding="utf-8").strip()
                except OSError:
                    state = "unknown"

                if state not in ("up", "unknown") and not (
                    rx_bytes or tx_bytes
                ):
                    continue

                is_wifi = (net_root / interface / "wireless").exists()
                try:
                    mac = (
                        net_root / interface / "address"
                    ).read_text(encoding="utf-8").strip()
                except OSError:
                    mac = "—"

                network_counters[interface] = {
                    "rx": rx_bytes,
                    "tx": tx_bytes,
                    "kind": "Wi-Fi" if is_wifi else "Ethernet",
                    "state": state,
                    "mac": mac or "—",
                    "ipv4": self._nanoos_network_lab_ipv4(interface),
                }
        except OSError:
            network_counters = {}

        previous = getattr(self, "_nanoos_network_io_sample", None)
        self._nanoos_network_io_sample = (now, network_counters)

        per_interface_rates = {}
        total_rx_rate = 0.0
        total_tx_rate = 0.0
        has_rate_sample = False

        if previous is not None:
            previous_time, old_counters = previous
            elapsed = now - previous_time
            if elapsed > 0:
                for interface, current in network_counters.items():
                    old = old_counters.get(interface)
                    if old is None:
                        continue

                    rx_rate = max(
                        0, current["rx"] - old["rx"]
                    ) / elapsed
                    tx_rate = max(
                        0, current["tx"] - old["tx"]
                    ) / elapsed

                    per_interface_rates[interface] = (
                        rx_rate, tx_rate
                    )
                    total_rx_rate += rx_rate
                    total_tx_rate += tx_rate
                    has_rate_sample = True

        if has_rate_sample:
            self.network_lab_download_value.setText(
                self._nanoos_network_lab_format_rate(total_rx_rate)
            )
            self.network_lab_upload_value.setText(
                self._nanoos_network_lab_format_rate(total_tx_rate)
            )
        else:
            self.network_lab_download_value.setText("Sampling…")
            self.network_lab_upload_value.setText("Sampling…")

        online = [
            (name, info)
            for name, info in network_counters.items()
            if info["state"] in ("up", "unknown")
        ]
        self.network_lab_active_value.setText(str(len(online)))
        self.network_lab_status_pill.setText(
            "ONLINE" if online else "NO ACTIVE LINK"
        )

        interface_lines = []
        for interface, info in sorted(network_counters.items()):
            rates = per_interface_rates.get(interface)
            if rates is None:
                rx_text = tx_text = "Sampling…"
            else:
                rx_text = self._nanoos_network_lab_format_rate(rates[0])
                tx_text = self._nanoos_network_lab_format_rate(rates[1])

            interface_lines.append(
                f"{interface} · {info['kind']} · "
                f"{info['state'].upper()}\n"
                f"  IPv4 {info['ipv4']}  ·  MAC {info['mac']}\n"
                f"  ↓ {rx_text}    ↑ {tx_text}"
            )

        if interface_lines:
            self.network_lab_interface_detail.setText(
                "\n\n".join(interface_lines[:8])
            )
        else:
            self.network_lab_interface_detail.setText(
                "No readable non-loopback interfaces were detected."
            )

        gateway = self._nanoos_network_lab_default_gateway()
        dns_servers = self._nanoos_network_lab_dns_servers()
        dns_text = ", ".join(dns_servers) if dns_servers else "Not listed"
        primary = online[0] if online else None

        if primary:
            primary_text = (
                f"{primary[0]} ({primary[1]['kind']}, "
                f"{primary[1]['state']})"
            )
        else:
            primary_text = "No active interface detected"

        self.network_lab_connection_detail.setText(
            f"Primary interface: {primary_text}\n"
            f"Default gateway: {gateway}\n"
            f"DNS servers: {dns_text}\n"
            "Rates are measured from Linux interface byte counters."
        )
        self.network_lab_last_update.setText(
            f"Live · refreshed {time.strftime('%H:%M:%S')}"
        )

    def _nanoos_network_lab_start_ping(self):
        import subprocess
        import time

        process = getattr(self, "_network_lab_ping_process", None)
        if process is not None and process.poll() is None:
            return

        self.network_lab_ping_button.setEnabled(False)
        self.network_lab_ping_button.setText("TEST RUNNING…")
        self.network_lab_latency_detail.setText(
            "Sending one ICMP probe to 1.1.1.1…"
        )

        try:
            process = subprocess.Popen(
                ["ping", "-n", "-c", "1", "-W", "2", "1.1.1.1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as exc:
            self.network_lab_latency_detail.setText(
                f"Could not start ping: {exc}"
            )
            self.network_lab_ping_button.setEnabled(True)
            self.network_lab_ping_button.setText("RUN PING TEST")
            return

        self._network_lab_ping_process = process
        self._network_lab_ping_started = time.monotonic()
        self._nanoos_network_lab_ping_timer.start()

    def _nanoos_network_lab_poll_ping(self):
        import re
        import time

        process = getattr(self, "_network_lab_ping_process", None)
        if process is None:
            self._nanoos_network_lab_ping_timer.stop()
            return

        if process.poll() is None:
            started = getattr(self, "_network_lab_ping_started", time.monotonic())
            if time.monotonic() - started > 4.0:
                process.kill()
            return

        try:
            output, _ = process.communicate()
        except OSError as exc:
            output = str(exc)

        match = re.search(r"time[=<]\s*([\d.]+)\s*ms", output or "")
        if process.returncode == 0 and match:
            self.network_lab_latency_detail.setText(
                f"Reply received · {match.group(1)} ms to 1.1.1.1"
            )
        elif process.returncode == 0:
            self.network_lab_latency_detail.setText(
                "Reply received, but ping did not report an RTT value."
            )
        else:
            self.network_lab_latency_detail.setText(
                "No ping reply. Internet access may be unavailable, "
                "or ICMP traffic may be blocked."
            )

        self._network_lab_ping_process = None
        self._network_lab_ping_started = None
        self._nanoos_network_lab_ping_timer.stop()
        self.network_lab_ping_button.setEnabled(True)
        self.network_lab_ping_button.setText("RUN PING TEST")

    def refresh_performance_lab(self):
        # CPU usage from deltas in /proc/stat.
        cpu_percent = None
        try:
            first_line = Path("/proc/stat").read_text(
                encoding="utf-8"
            ).splitlines()[0].split()

            if first_line and first_line[0] == "cpu":
                values = [int(value) for value in first_line[1:]]
                if len(values) >= 4:
                    total = sum(values)
                    idle = values[3] + (
                        values[4] if len(values) > 4 else 0
                    )
                    previous = getattr(
                        self, "_nanoos_perf_cpu_sample", None
                    )
                    self._nanoos_perf_cpu_sample = (total, idle)

                    if previous is not None:
                        delta_total = total - previous[0]
                        delta_idle = idle - previous[1]
                        if delta_total > 0:
                            cpu_percent = round(
                                100 * (delta_total - delta_idle)
                                / delta_total
                            )
        except (OSError, ValueError, IndexError):
            pass

        if cpu_percent is None:
            self._nanoos_animate_progress(self.performance_cpu_bar, 0)
            self.performance_cpu_bar.setFormat("Sampling…")
            self.performance_cpu_detail.setText(
                "Waiting for two CPU samples from /proc/stat."
            )
        else:
            cpu_percent = max(0, min(100, cpu_percent))
            self._nanoos_animate_progress(self.performance_cpu_bar, cpu_percent)
            self.performance_cpu_bar.setFormat(f"{cpu_percent}%")
            self.performance_cpu_detail.setText(
                "System-wide CPU utilization from /proc/stat."
            )

        # RAM usage using MemAvailable, not just MemFree.
        try:
            mem = {}
            for line in Path("/proc/meminfo").read_text(
                encoding="utf-8"
            ).splitlines():
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts:
                    mem[key] = int(parts[0])

            total_kib = mem.get("MemTotal", 0)
            available_kib = mem.get(
                "MemAvailable", mem.get("MemFree", 0)
            )

            if total_kib > 0:
                used_kib = max(0, total_kib - available_kib)
                memory_percent = round(
                    used_kib * 100 / total_kib
                )
                self._nanoos_animate_progress(self.performance_memory_bar, memory_percent)
                self.performance_memory_bar.setFormat(
                    f"{memory_percent}%"
                )
                self.performance_memory_detail.setText(
                    f"{used_kib / 1024:.0f} MiB used / "
                    f"{total_kib / 1024:.0f} MiB total"
                )
            else:
                raise ValueError("MemTotal unavailable")
        except (OSError, ValueError):
            self._nanoos_animate_progress(self.performance_memory_bar, 0)
            self.performance_memory_bar.setFormat("Unavailable")
            self.performance_memory_detail.setText(
                "/proc/meminfo could not be read."
            )

        # Prefer nvidia-smi when available; otherwise try DRM sysfs.
        gpu_found = False
        try:
            if shutil.which("nvidia-smi"):
                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=1.5,
                    check=False,
                )

                if result.returncode == 0 and result.stdout.strip():
                    parts = [
                        value.strip()
                        for value in result.stdout.splitlines()[0].split(",")
                    ]
                    if len(parts) >= 4:
                        gpu_name = parts[0]
                        gpu_usage = int(parts[1])
                        vram_used = int(parts[2])
                        vram_total = int(parts[3])

                        if vram_total > 0:
                            vram_percent = round(
                                vram_used * 100 / vram_total
                            )
                            self._nanoos_animate_progress(self.performance_vram_bar, max(0, min(100, vram_percent)))
                            self.performance_vram_bar.setFormat(
                                f"{vram_percent}%"
                            )
                            self.performance_vram_detail.setText(
                                f"{vram_used} MiB used / "
                                f"{vram_total} MiB total"
                            )
                        else:
                            self._nanoos_animate_progress(self.performance_vram_bar, 0)
                            self.performance_vram_bar.setFormat(
                                "Unavailable"
                            )
                            self.performance_vram_detail.setText(
                                "GPU memory total unavailable."
                            )

                        gpu_usage = max(0, min(100, gpu_usage))
                        self._nanoos_animate_progress(self.performance_gpu_bar, gpu_usage)
                        self.performance_gpu_bar.setFormat(
                            f"{gpu_usage}%"
                        )
                        self.performance_gpu_detail.setText(gpu_name)
                        gpu_found = True
        except (
            OSError, ValueError, IndexError,
            subprocess.SubprocessError,
        ):
            pass

        if not gpu_found:
            drm_busy = None
            drm_vram_used = None
            drm_vram_total = None

            try:
                for busy_path in Path("/sys/class/drm").glob(
                    "card*/device/gpu_busy_percent"
                ):
                    if busy_path.is_file():
                        drm_busy = int(busy_path.read_text().strip())
                        device = busy_path.parent
                        used_path = device / "mem_info_vram_used"
                        total_path = device / "mem_info_vram_total"

                        if used_path.is_file() and total_path.is_file():
                            drm_vram_used = int(
                                used_path.read_text().strip()
                            )
                            drm_vram_total = int(
                                total_path.read_text().strip()
                            )
                        break
            except (OSError, ValueError):
                pass

            if drm_busy is not None:
                drm_busy = max(0, min(100, drm_busy))
                self._nanoos_animate_progress(self.performance_gpu_bar, drm_busy)
                self.performance_gpu_bar.setFormat(f"{drm_busy}%")
                self.performance_gpu_detail.setText(
                    "GPU busy percentage from DRM sysfs."
                )
                gpu_found = True
            else:
                self._nanoos_animate_progress(self.performance_gpu_bar, 0)
                self.performance_gpu_bar.setFormat("Unavailable")
                self.performance_gpu_detail.setText(
                    "No readable NVIDIA or DRM GPU utilization source."
                )

            if (
                drm_vram_used is not None
                and drm_vram_total is not None
                and drm_vram_total > 0
            ):
                vram_percent = round(
                    drm_vram_used * 100 / drm_vram_total
                )
                self._nanoos_animate_progress(self.performance_vram_bar, max(0, min(100, vram_percent)))
                self.performance_vram_bar.setFormat(
                    f"{vram_percent}%"
                )
                self.performance_vram_detail.setText(
                    f"{drm_vram_used / (1024 ** 2):.0f} MiB used / "
                    f"{drm_vram_total / (1024 ** 2):.0f} MiB total"
                )
            elif not shutil.which("nvidia-smi"):
                self._nanoos_animate_progress(self.performance_vram_bar, 0)
                self.performance_vram_bar.setFormat("Unavailable")
                self.performance_vram_detail.setText(
                    "VRAM telemetry is not exposed by this driver."
                )

        # CPU policy and load average are read-only sysfs/proc values.
        policy = Path("/sys/devices/system/cpu/cpufreq/policy0")

        def read_policy(name, fallback="Unavailable"):
            try:
                return (policy / name).read_text(
                    encoding="utf-8"
                ).strip()
            except OSError:
                return fallback

        governor = read_policy("scaling_governor")
        epp = read_policy("energy_performance_preference")
        frequency = read_policy("scaling_cur_freq")

        if frequency.isdigit():
            frequency_text = f"{int(frequency) / 1000:.0f} MHz"
        else:
            frequency_text = "Unavailable"

        try:
            load = " ".join(
                Path("/proc/loadavg").read_text(
                    encoding="utf-8"
                ).split()[:3]
            )
        except OSError:
            load = "Unavailable"

        active_profile = self.state.get("profile", "Unknown")

        self.performance_system_info.setText(
            f"CPU governor: {governor}\n"
            f"Energy performance preference: {epp}\n"
            f"Policy 0 current frequency: {frequency_text}\n"
            f"System load average (1/5/15 min): {load}\n"
            f"Active NanoOS profile: {active_profile}"
        )

        self.performance_lab_status.setText(
            "Live telemetry refreshed. Unsupported sensors are marked unavailable."
        )

        self.refresh_storage_network_metrics()

    def refresh_storage_network_metrics(self):
        # NANOOS_OVERRIDE_STORAGE_NETWORK_USB_V28
        import re
        import time

        now = time.monotonic()

        def human_rate(value):
            value = max(0.0, float(value))
            if value >= 1024 ** 2:
                return f"{value / (1024 ** 2):.1f} MiB/s"
            if value >= 1024:
                return f"{value / 1024:.1f} KiB/s"
            return f"{value:.0f} B/s"

        # --------------------------------------------------------
        # Disk throughput: /proc/diskstats sectors read/written.
        # Only top-level block devices are counted to avoid double
        # counting a whole disk and its partitions.
        # --------------------------------------------------------
        sys_block = Path("/sys/block")
        excluded_prefixes = (
            "loop", "ram", "zram", "dm-", "md", "sr", "fd"
        )
        disk_counters = {}

        try:
            for line in Path("/proc/diskstats").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines():
                parts = line.split()
                if len(parts) < 10:
                    continue

                device = parts[2]
                if device.startswith(excluded_prefixes):
                    continue
                if not (sys_block / device).exists():
                    continue

                try:
                    sectors_read = int(parts[5])
                    sectors_written = int(parts[9])
                except ValueError:
                    continue

                disk_counters[device] = (
                    sectors_read, sectors_written
                )
        except OSError:
            disk_counters = {}

        previous_disk = getattr(
            self, "_nanoos_disk_io_sample", None
        )
        self._nanoos_disk_io_sample = (now, disk_counters)

        if previous_disk is None:
            self.performance_disk_io_detail.setText(
                "Disk I/O: sampling; rates appear after the next refresh."
            )
        else:
            previous_time, old_counters = previous_disk
            elapsed = now - previous_time

            if elapsed <= 0:
                self.performance_disk_io_detail.setText(
                    "Disk I/O: waiting for a valid sample interval."
                )
            else:
                read_bytes_per_sec = 0
                write_bytes_per_sec = 0

                for device, current in disk_counters.items():
                    previous = old_counters.get(device)
                    if previous is None:
                        continue

                    read_delta = max(0, current[0] - previous[0])
                    write_delta = max(0, current[1] - previous[1])

                    # Linux diskstats reports sectors in 512-byte units.
                    read_bytes_per_sec += read_delta * 512 / elapsed
                    write_bytes_per_sec += write_delta * 512 / elapsed

                if disk_counters:
                    self.performance_disk_io_detail.setText(
                        "Disk I/O · "
                        f"Read ↓ {human_rate(read_bytes_per_sec)}"
                        "  ·  "
                        f"Write ↑ {human_rate(write_bytes_per_sec)}"
                    )
                else:
                    self.performance_disk_io_detail.setText(
                        "Disk I/O: /proc/diskstats unavailable."
                    )

        # --------------------------------------------------------
        # Network telemetry now lives in the dedicated Network Lab.

        # Mounted filesystems and available/free capacity.
        # /proc/mounts escapes spaces as \\040 and backslashes as \\134.
        # --------------------------------------------------------
        mounts = []
        try:
            mount_lines = Path("/proc/mounts").read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()

            seen_mounts = set()
            for line in mount_lines:
                fields = line.split()
                if len(fields) < 3:
                    continue

                device, mountpoint, filesystem = fields[:3]
                if not device.startswith("/dev/"):
                    continue

                mountpoint = (
                    mountpoint.replace(r"\040", " ")
                    .replace(r"\011", "\t")
                    .replace(r"\134", "\\")
                )
                if mountpoint in seen_mounts:
                    continue
                seen_mounts.add(mountpoint)

                try:
                    usage = shutil.disk_usage(mountpoint)
                except OSError:
                    continue

                mounts.append({
                    "device": Path(device).name,
                    "source": device,
                    "mountpoint": mountpoint,
                    "filesystem": filesystem,
                    "total": usage.total,
                    "free": usage.free,
                })
        except OSError:
            mounts = []

        if mounts:
            volume_lines = []
            for mount in mounts[:4]:
                total_gib = mount["total"] / (1024 ** 3)
                free_gib = mount["free"] / (1024 ** 3)
                volume_lines.append(
                    f'{mount["device"]} → {mount["mountpoint"]}: '
                    f'{free_gib:.1f} GiB free / {total_gib:.1f} GiB'
                )

            extra = len(mounts) - len(volume_lines)
            suffix = f" · +{extra} more" if extra > 0 else ""
            self.performance_storage_detail.setText(
                "Mounted volumes · " + "  |  ".join(volume_lines) + suffix
            )
        else:
            self.performance_storage_detail.setText(
                "Mounted volumes: no mounted /dev filesystems detected."
            )

        # --------------------------------------------------------
        # USB/removable block storage devices and mount points.
        # No mount/unmount/write operations are performed.
        # --------------------------------------------------------
        def physical_base(device_name):
            class_path = Path("/sys/class/block") / device_name
            try:
                resolved = class_path.resolve()
            except OSError:
                return device_name

            try:
                for candidate in sys_block.iterdir():
                    root = candidate.resolve()
                    if resolved == root or root in resolved.parents:
                        return candidate.name
            except OSError:
                pass

            return device_name

        mountpoints_by_device = {}
        for mount in mounts:
            device_name = Path(mount["source"]).name
            base = physical_base(device_name)
            mountpoints_by_device.setdefault(base, []).append(
                mount["mountpoint"]
            )

        usb_devices = []
        try:
            block_nodes = list(sys_block.iterdir())
        except OSError:
            block_nodes = []

        for device in block_nodes:
            if device.name.startswith(excluded_prefixes):
                continue

            try:
                resolved_parts = device.resolve().parts
            except OSError:
                resolved_parts = ()

            usb_path = any(
                re.fullmatch(r"usb\d+", part) is not None
                for part in resolved_parts
            )

            try:
                removable = (
                    (device / "removable").read_text(
                        encoding="utf-8"
                    ).strip() == "1"
                )
            except OSError:
                removable = False

            if not (usb_path or removable):
                continue

            mountpoints = mountpoints_by_device.get(device.name, [])
            if mountpoints:
                mount_text = ", ".join(mountpoints[:2])
            else:
                mount_text = "not mounted"

            label = "USB" if usb_path else "removable"
            usb_devices.append(
                f"{device.name} ({label}; {mount_text})"
            )

        if usb_devices:
            self.performance_usb_detail.setText(
                "USB/removable storage · "
                + "  |  ".join(usb_devices[:5])
            )
        else:
            self.performance_usb_detail.setText(
                "USB storage: no USB/removable block drives detected."
            )

    def build_hardware_page(self):
        page = QWidget()
        page.setObjectName("hardwarePage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # ----------------------------------------------------
        # NANOOS HARDWARE THEME
        # ----------------------------------------------------
        page.setStyleSheet("""
            QWidget#hardwarePage {
                background: transparent;
                color: #e6eef6;
            }

            QWidget#hardwarePage QLabel {
                background: transparent;
                color: #e6eef6;
                border: none;
            }

            QWidget#hardwarePage QFrame#hardwareInfo {
                background: #0b1118;
                border: 1px solid #223543;
                border-radius: 14px;
            }

            QWidget#hardwarePage QFrame#hardwareRow {
                background: #101b26;
                border: 1px solid #1a2936;
                border-radius: 14px;
            }

            QWidget#hardwarePage QPushButton {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 8px 16px;
                min-height: 22px;
                font-weight: 600;
                outline: none;
            }

            QWidget#hardwarePage QPushButton:hover {
                background: #132230;
                border-color: #31566a;
            }

            QWidget#hardwarePage QPushButton:pressed {
                background: #1a2936;
                border-color: #4e6276;
            }

            QWidget#hardwarePage QPushButton:focus {
                background: #101b26;
                border-color: #4e6276;
                outline: none;
            }

            QWidget#hardwarePage QPushButton:disabled {
                background: #0b1118;
                color: #4e6276;
                border-color: #1a2936;
            }

            QWidget#hardwarePage QComboBox {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 8px 12px;
                min-height: 22px;
                outline: none;
            }

            QWidget#hardwarePage QComboBox:hover {
                background: #132230;
                border-color: #31566a;
            }

            QWidget#hardwarePage QComboBox:focus,
            QWidget#hardwarePage QComboBox:on {
                background: #132230;
                border-color: #4e6276;
            }

            QWidget#hardwarePage QComboBox::drop-down {
                background: #101b26;
                border: none;
                border-left: 1px solid #223543;
                width: 30px;
                margin: 1px;
                border-top-right-radius: 9px;
                border-bottom-right-radius: 9px;
            }

            QWidget#hardwarePage QComboBox::drop-down:hover {
                background: #1a2936;
            }

            QWidget#hardwarePage QComboBox QAbstractItemView,
            QWidget#hardwarePage QListView,
            QWidget#hardwarePage QAbstractItemView {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 5px;
                outline: none;
                selection-background-color: #223543;
                selection-color: #ffffff;
            }

            QWidget#hardwarePage QComboBox QAbstractItemView::item,
            QWidget#hardwarePage QListView::item {
                background: transparent;
                color: #e6eef6;
                padding: 7px 10px;
                min-height: 30px;
                border-radius: 7px;
            }

            QWidget#hardwarePage QComboBox QAbstractItemView::item:hover,
            QWidget#hardwarePage QListView::item:hover {
                background: #132230;
                color: #ffffff;
            }

            QWidget#hardwarePage QComboBox QAbstractItemView::item:selected,
            QWidget#hardwarePage QListView::item:selected {
                background: #223543;
                color: #ffffff;
            }

            QWidget#hardwarePage QLineEdit,
            QWidget#hardwarePage QTextEdit,
            QWidget#hardwarePage QPlainTextEdit {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 8px 10px;
                selection-background-color: #223543;
                selection-color: #ffffff;
                outline: none;
            }

            QWidget#hardwarePage QLineEdit:focus,
            QWidget#hardwarePage QTextEdit:focus,
            QWidget#hardwarePage QPlainTextEdit:focus {
                border-color: #4e6276;
            }

            QWidget#hardwarePage QCheckBox,
            QWidget#hardwarePage QRadioButton {
                background: transparent;
                color: #e6eef6;
                spacing: 8px;
                outline: none;
            }

            QWidget#hardwarePage QSpinBox,
            QWidget#hardwarePage QDoubleSpinBox {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 7px 10px;
                outline: none;
            }

            QWidget#hardwarePage QSpinBox:focus,
            QWidget#hardwarePage QDoubleSpinBox:focus {
                border-color: #4e6276;
            }

            QWidget#hardwarePage QToolButton {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 9px;
                padding: 7px 12px;
            }

            QWidget#hardwarePage QToolButton:hover {
                background: #132230;
                border-color: #31566a;
            }

            QWidget#hardwarePage QMenu {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                padding: 5px;
            }

            QWidget#hardwarePage QMenu::item {
                background: transparent;
                color: #e6eef6;
                padding: 7px 12px;
                border-radius: 7px;
            }

            QWidget#hardwarePage QMenu::item:selected {
                background: #223543;
                color: #ffffff;
            }

            QWidget#hardwarePage QProgressBar {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 7px;
                text-align: center;
            }

            QWidget#hardwarePage QProgressBar::chunk {
                background: #31566a;
                border-radius: 6px;
            }

            QWidget#hardwarePage QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 3px 0;
                border: none;
            }

            QWidget#hardwarePage QScrollBar::handle:vertical {
                background: #223543;
                border-radius: 4px;
                min-height: 28px;
                border: none;
            }

            QWidget#hardwarePage QScrollBar::handle:vertical:hover {
                background: #4e6276;
            }

            QWidget#hardwarePage QScrollBar::add-line:vertical,
            QWidget#hardwarePage QScrollBar::sub-line:vertical,
            QWidget#hardwarePage QScrollBar::add-page:vertical,
            QWidget#hardwarePage QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
                height: 0px;
            }

            QWidget#hardwarePage QToolTip {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 8px;
                padding: 6px 9px;
            }
        """)

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------
        header = QVBoxLayout()
        header.setSpacing(2)

        title = QLabel("Hardware")
        title.setObjectName("mainTitle")
        header.addWidget(title)

        subtitle = QLabel(
            "Runtime CPU and platform performance controls"
        )
        subtitle.setObjectName("muted")
        header.addWidget(subtitle)

        layout.addLayout(header)

        # ----------------------------------------------------
        # Hardware detection
        # ----------------------------------------------------
        info = QFrame()
        info.setObjectName("hardwareInfo")

        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(18, 14, 18, 14)
        info_layout.setSpacing(4)

        cpu_name = "Unknown CPU"

        try:
            cpuinfo = Path("/proc/cpuinfo").read_text(
                encoding="utf-8",
                errors="ignore",
            )

            for line in cpuinfo.splitlines():
                if line.lower().startswith("model name"):
                    if ":" in line:
                        cpu_name = line.split(":", 1)[1].strip()
                    break
        except OSError:
            pass

        gpu_names = []

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )

            if result.returncode == 0:
                gpu_names.extend(
                    line.strip()
                    for line in result.stdout.splitlines()
                    if line.strip()
                )
        except (OSError, subprocess.SubprocessError):
            pass

        if not gpu_names:
            try:
                result = subprocess.run(
                    ["lspci", "-mm"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )

                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        upper = line.upper()
                        if "VGA" in upper or "3D CONTROLLER" in upper:
                            parts = line.split('"')
                            if len(parts) >= 6:
                                gpu_names.append(parts[5])
            except (OSError, subprocess.SubprocessError):
                pass

        gpu_text = " / ".join(gpu_names) if gpu_names else "GPU detection unavailable"

        info_layout.setContentsMargins(20, 16, 20, 16)
        info_layout.setSpacing(8)
        info_eyebrow = QLabel("SYSTEM")
        info_eyebrow.setObjectName("hwEyebrow")
        info_layout.addWidget(info_eyebrow)
        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(18)
        info_grid.setVerticalSpacing(6)
        for row_index, (key, value) in enumerate((
            ("Processor", cpu_name),
            ("Graphics", gpu_text),
        )):
            key_label = QLabel(key)
            key_label.setObjectName("hwKey")
            value_label = QLabel(value)
            value_label.setObjectName("hwValue")
            value_label.setWordWrap(True)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            info_grid.addWidget(key_label, row_index, 0)
            info_grid.addWidget(value_label, row_index, 1)
        info_grid.setColumnStretch(1, 1)
        info_layout.addLayout(info_grid)

        layout.addWidget(info)

        # ----------------------------------------------------
        # Live status tiles (highlighted when in a performance state)
        # ----------------------------------------------------
        tiles_row = QGridLayout()
        tiles_row.setHorizontalSpacing(12)
        tiles_row.setVerticalSpacing(12)
        status_tiles = {}
        for column, (key, label) in enumerate((
            ("boost", "CPU BOOST"),
            ("governor", "GOVERNOR"),
            ("epp", "POWER HINT"),
            ("platform", "PLATFORM"),
        )):
            tile = QFrame()
            tile.setObjectName("hwTile")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(16, 13, 16, 13)
            tile_layout.setSpacing(3)
            tile_label = QLabel(label)
            tile_label.setObjectName("hwEyebrow")
            tile_value = QLabel("—")
            tile_value.setObjectName("hwTileValue")
            tile_layout.addWidget(tile_label)
            tile_layout.addWidget(tile_value)
            tiles_row.addWidget(tile, 0, column)
            tiles_row.setColumnStretch(column, 1)
            status_tiles[key] = (tile, tile_value)
        layout.addLayout(tiles_row)

        controls_heading = QLabel("CONTROLS")
        controls_heading.setObjectName("hwSection")
        layout.addWidget(controls_heading)

        # ----------------------------------------------------
        # Runtime paths
        # ----------------------------------------------------
        policy = Path("/sys/devices/system/cpu/cpufreq/policy0")

        boost_control = find_cpu_boost_control()

        governor_path = policy / "scaling_governor"
        governor_available_path = policy / "scaling_available_governors"

        epp_path = policy / "energy_performance_preference"
        epp_available_path = policy / "energy_performance_available_preferences"

        platform_profile_path = Path(
            "/sys/firmware/acpi/platform_profile"
        )

        platform_choices_path = Path(
            "/sys/firmware/acpi/platform_profile_choices"
        )

        def read_text(path, fallback=""):
            try:
                if path.exists():
                    return path.read_text(
                        encoding="utf-8",
                        errors="ignore",
                    ).strip()
            except OSError:
                pass

            return fallback

        def runtime_write(path, value, label):
            if path is None or not path.exists():
                return False, f"{label} is not exposed by the kernel."

            try:
                path.write_text(str(value), encoding="utf-8")
                return True, ""

            except PermissionError:
                operation_map = {
                    "scaling_governor": "governor",
                    "energy_performance_preference": "epp",
                    "platform_profile": "platform",
                }

                operation = operation_map.get(path.name)

                if operation is None:
                    return False, (
                        f"No privileged NanoOS GameMode operation exists "
                        f"for {label}."
                    )

                return run_privileged_helper(
                    operation,
                    str(value),
                )

            except OSError as exc:
                return False, str(exc)

        def set_status(message, error=False):
            status_label.setText(message)
            status_label.setProperty("tone", "bad" if error else "good")
            status_label.style().unpolish(status_label)
            status_label.style().polish(status_label)

        # ----------------------------------------------------
        # Row helper
        # ----------------------------------------------------
        def make_row(title_text, description_text):
            row = QFrame()
            row.setObjectName("hardwareRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(18, 14, 18, 14)
            row_layout.setSpacing(14)

            text_box = QVBoxLayout()
            text_box.setSpacing(2)

            name = QLabel(title_text)
            name.setObjectName("hardwareRowTitle")
            text_box.addWidget(name)

            description = QLabel(description_text)
            description.setObjectName("muted")
            description.setWordWrap(True)
            text_box.addWidget(description)

            row_layout.addLayout(text_box, 1)

            chip = QLabel("")
            chip.setObjectName("hwChip")
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip.hide()
            row_layout.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
            row._nanoos_chip = chip

            return row, row_layout

        # ----------------------------------------------------
        # CPU Boost
        # ----------------------------------------------------
        boost_row, boost_layout = make_row(
            "CPU Boost",
            "Lets cores run above base clock. Off runs cooler and quieter.",
        )

        boost_button = QPushButton("Turn off")
        boost_button.setMinimumWidth(120)
        boost_button.setMinimumHeight(38)
        boost_button.setFocusPolicy(Qt.NoFocus)

        boost_layout.addWidget(boost_button)

        layout.addWidget(boost_row)

        # ----------------------------------------------------
        # Governor / NanoOS Gaming preset
        # ----------------------------------------------------
        governor_row, governor_layout = make_row(
            "CPU Governor",
            "How the kernel picks CPU frequency. Only governors your kernel offers are listed.",
        )

        governor_combo = QComboBox()
        governor_combo.setMinimumWidth(190)
        governor_combo.setMinimumHeight(38)
        governor_combo.setFocusPolicy(Qt.NoFocus)

        governors = read_text(
            governor_available_path,
            read_text(governor_path, ""),
        ).split()

        governor_items = []

        for item in governors:
            if item not in governor_items:
                governor_items.append(item)

        governor_combo.addItems(governor_items)

        governor_apply = QPushButton("Apply")
        governor_apply.setMinimumWidth(100)
        governor_apply.setMinimumHeight(38)
        governor_apply.setFocusPolicy(Qt.NoFocus)

        governor_layout.addWidget(governor_combo)
        governor_layout.addWidget(governor_apply)

        layout.addWidget(governor_row)

        # ----------------------------------------------------
        # EPP
        # ----------------------------------------------------
        epp_row, epp_layout = make_row(
            "Power Hint (EPP)",
            "Energy/performance preference sent to the CPU firmware (amd-pstate / intel_pstate).",
        )

        epp_combo = QComboBox()
        epp_combo.setMinimumWidth(170)
        epp_combo.setMinimumHeight(38)
        epp_combo.setFocusPolicy(Qt.NoFocus)

        epp_values = read_text(
            epp_available_path,
            read_text(epp_path, ""),
        ).split()

        epp_combo.addItems(
            list(dict.fromkeys(epp_values))
        )

        epp_apply = QPushButton("Apply")
        epp_apply.setMinimumWidth(100)
        epp_apply.setMinimumHeight(38)
        epp_apply.setFocusPolicy(Qt.NoFocus)

        epp_layout.addWidget(epp_combo)
        epp_layout.addWidget(epp_apply)

        layout.addWidget(epp_row)

        # ----------------------------------------------------
        # Platform Profile
        # ----------------------------------------------------
        platform_row, platform_layout = make_row(
            "Platform Profile",
            "Firmware fan and power profile. Mostly laptops and handhelds.",
        )

        platform_combo = QComboBox()
        platform_combo.setMinimumWidth(170)
        platform_combo.setMinimumHeight(38)
        platform_combo.setFocusPolicy(Qt.NoFocus)

        platform_values = read_text(
            platform_choices_path,
            read_text(platform_profile_path, ""),
        ).split()

        platform_combo.addItems(
            list(dict.fromkeys(platform_values))
        )

        platform_apply = QPushButton("Apply")
        platform_apply.setMinimumWidth(100)
        platform_apply.setMinimumHeight(38)
        platform_apply.setFocusPolicy(Qt.NoFocus)

        platform_layout.addWidget(platform_combo)
        platform_layout.addWidget(platform_apply)

        layout.addWidget(platform_row)

        # ----------------------------------------------------
        # NanoOS Performance Mode
        # ----------------------------------------------------
        performance_mode_row, performance_mode_layout = make_row(
            "NanoOS Performance Mode",
            "One preset for boost, governor, power hint, platform profile and GPU together.",
        )

        performance_mode_combo = QComboBox()
        performance_mode_combo.setMinimumWidth(190)
        performance_mode_combo.setMinimumHeight(38)
        performance_mode_combo.setFocusPolicy(Qt.NoFocus)
        performance_mode_combo.addItems([
            "Power Saving",
            "Balanced",
            "Performance",
            "Gaming",
        ])

        performance_mode_apply = QPushButton("Apply")
        performance_mode_apply.setMinimumWidth(100)
        performance_mode_apply.setMinimumHeight(38)
        performance_mode_apply.setFocusPolicy(Qt.NoFocus)

        performance_mode_layout.addWidget(performance_mode_combo)
        performance_mode_layout.addWidget(performance_mode_apply)

        layout.addWidget(performance_mode_row)

        # ----------------------------------------------------
        # Status + refresh
        # ----------------------------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        status_label = QLabel("Ready")
        status_label.setObjectName("hwBanner")
        status_label.setWordWrap(True)
        bottom.addWidget(status_label, 1)

        refresh_button = QPushButton("Refresh")
        refresh_button.setMinimumWidth(105)
        refresh_button.setMinimumHeight(36)
        refresh_button.setFocusPolicy(Qt.NoFocus)
        bottom.addWidget(refresh_button)

        layout.addLayout(bottom)

        layout.addStretch()

        # ----------------------------------------------------
        # Refresh current values
        # ----------------------------------------------------
        boost_applied = False

        PERFORMANCE_STATES = {
            "governor": {"performance"},
            "epp": {"performance"},
            "platform": {"performance"},
        }

        def set_chip(row, text, tone):
            chip = row._nanoos_chip
            chip.setText(text)
            chip.setProperty("tone", tone)
            chip.style().unpolish(chip)
            chip.style().polish(chip)
            chip.setVisible(bool(text))

        def set_tile(key, value, tone):
            tile, label = status_tiles[key]
            label.setText(value)
            tile.setProperty("tone", tone)
            tile.style().unpolish(tile)
            tile.style().polish(tile)

        def show_control(row, combo, button, supported):
            combo.setVisible(supported)
            button.setVisible(supported)
            if not supported:
                set_chip(row, "NOT SUPPORTED", "off")

        def refresh_hardware():
            boost = read_cpu_boost()

            # ---- CPU boost
            if boost is None:
                boost_button.setEnabled(False)
                boost_button.setText("Unavailable")
                set_chip(boost_row, "NOT SUPPORTED", "off")
                set_tile("boost", "Unavailable", "off")
            else:
                boost_button.setEnabled(True)
                boost_button.setChecked(boost)
                boost_button.setText("Turn off" if boost else "Turn on")
                set_chip(boost_row, "ON" if boost else "OFF",
                         "hot" if boost else "off")
                set_tile("boost", "On" if boost else "Off",
                         "hot" if boost else "idle")

            current_mode = self.state.get(
                "nanoos_performance_mode",
                "Balanced",
            )
            if performance_mode_combo.findText(current_mode) >= 0:
                performance_mode_combo.setCurrentText(current_mode)
            set_chip(performance_mode_row, current_mode.upper(),
                     "hot" if current_mode in ("Performance", "Gaming") else "idle")

            # ---- governor / EPP / platform: real values only
            for key, path, row, combo, button in (
                ("governor", governor_path, governor_row, governor_combo, governor_apply),
                ("epp", epp_path, epp_row, epp_combo, epp_apply),
                ("platform", platform_profile_path, platform_row, platform_combo, platform_apply),
            ):
                current = read_text(path, "")
                supported = bool(current) and combo.count() > 0
                show_control(row, combo, button, supported)
                if not supported:
                    set_tile(key, "Not supported", "off")
                    continue
                if combo.findText(current) >= 0:
                    combo.setCurrentText(current)
                hot = current in PERFORMANCE_STATES[key]
                set_chip(row, current.upper(), "hot" if hot else "idle")
                set_tile(key, current.replace("_", " ").title(),
                         "hot" if hot else "idle")
                # Only one choice means there is nothing to change.
                combo.setEnabled(combo.count() > 1)
                button.setEnabled(combo.count() > 1)

            if status_label.property("tone") not in ("good", "bad"):
                status_label.setText(
                    "Live values from the kernel. Changes apply immediately "
                    "and use your administrator session."
                )

        # ----------------------------------------------------
        # NanoOS Performance Mode helpers
        # ----------------------------------------------------
        def first_supported(values, preferred):
            for item in preferred:
                if item in values:
                    return item

            return values[0] if values else None

        def apply_nanoos_performance_mode():
            mode = performance_mode_combo.currentText()

            profiles = {
                "Power Saving": {
                    "boost": False,
                    "gpu": False,
                    "governor": [
                        "powersave",
                        "schedutil",
                        "conservative",
                        "ondemand",
                        "performance",
                    ],
                    "epp": [
                        "power",
                        "balance_power",
                        "powersave",
                        "balance_performance",
                        "performance",
                    ],
                    "platform": [
                        "powersave",
                        "quiet",
                        "cool",
                        "balanced",
                        "performance",
                    ],
                },
                "Balanced": {
                    "boost": False,
                    "gpu": False,
                    "governor": [
                        "schedutil",
                        "powersave",
                        "ondemand",
                        "conservative",
                        "performance",
                    ],
                    "epp": [
                        "balance_performance",
                        "balance_power",
                        "power",
                        "performance",
                    ],
                    "platform": [
                        "balanced",
                        "powersave",
                        "quiet",
                        "cool",
                        "performance",
                    ],
                },
                "Performance": {
                    "boost": True,
                    "gpu": True,
                    "governor": [
                        "performance",
                        "schedutil",
                    ],
                    "epp": [
                        "performance",
                        "balance_performance",
                        "balance_power",
                        "power",
                    ],
                    "platform": [
                        "performance",
                        "balanced",
                    ],
                },
                "Gaming": {
                    "boost": True,
                    "gpu": True,
                    "governor": [
                        "performance",
                        "schedutil",
                    ],
                    "epp": [
                        "performance",
                        "balance_performance",
                        "balance_power",
                        "power",
                    ],
                    "platform": [
                        "performance",
                        "balanced",
                    ],
                },
            }

            config = profiles[mode]
            failures = []
            applied = []

            # ---------------- CPU Boost ----------------
            ok, message = set_cpu_boost(config["boost"])

            if ok:
                applied.append(
                    "Boost ON" if config["boost"] else "Boost OFF"
                )
            else:
                if find_cpu_boost_control() is not None:
                    failures.append(message)

            # ---------------- Governor ----------------
            governor_value = first_supported(
                governors,
                config["governor"],
            )

            if governor_value is not None and governor_path.exists():
                ok, message = runtime_write(
                    governor_path,
                    governor_value,
                    "CPU governor",
                )

                if ok:
                    applied.append(
                        f"Governor {governor_value}"
                    )
                else:
                    failures.append(message)

            # ---------------- EPP ----------------
            epp_value = first_supported(
                epp_values,
                config["epp"],
            )

            if epp_value is not None and epp_path.exists():
                ok, message = runtime_write(
                    epp_path,
                    epp_value,
                    "CPU EPP",
                )

                if ok:
                    applied.append(
                        f"EPP {epp_value}"
                    )
                else:
                    failures.append(message)

            # ---------------- Platform ----------------
            platform_value = first_supported(
                platform_values,
                config["platform"],
            )

            if (
                platform_value is not None
                and platform_profile_path.exists()
            ):
                ok, message = runtime_write(
                    platform_profile_path,
                    platform_value,
                    "platform profile",
                )

                if ok:
                    applied.append(
                        f"Platform {platform_value}"
                    )
                else:
                    failures.append(message)

            # ---------------- NVIDIA readiness ----------------
            if shutil.which("nvidia-smi") is not None:
                ok, message = set_gpu_performance(
                    config["gpu"]
                )

                if ok:
                    applied.append(
                        "GPU Performance ON"
                        if config["gpu"]
                        else "GPU Performance OFF"
                    )
                else:
                    failures.append(message)

            self.state["nanoos_performance_mode"] = mode
            self.state["cpu_boost"] = config["boost"]
            self.state["gpu_performance"] = config["gpu"]

            save_state(self.state)
            self.write_gamemode_config()

            if failures:
                set_status(
                    f"{mode} applied with errors: "
                    + " | ".join(failures),
                    error=True,
                )
            else:
                set_status(
                    f"{mode} applied • "
                    + " • ".join(applied)
                )

            refresh_hardware()

        performance_mode_apply.clicked.connect(
            apply_nanoos_performance_mode
        )

        # ----------------------------------------------------
        # CPU boost action
        # ----------------------------------------------------
        def toggle_boost():
            nonlocal boost_applied

            desired = not bool(read_cpu_boost())

            # The next click represents a new operation.
            boost_applied = False
            boost_button.setText("Apply")

            ok, message = set_cpu_boost(desired)

            if ok:
                boost_applied = True

                set_status(
                    "CPU boost enabled."
                    if desired
                    else "CPU boost disabled."
                )

                refresh_hardware()
            else:
                boost_applied = False
                boost_button.setText("Apply")
                set_status(message, error=True)

        boost_button.clicked.connect(toggle_boost)

        # ----------------------------------------------------
        # Governor / Gaming action
        # ----------------------------------------------------
        def apply_governor():
            selected = governor_combo.currentText()

            # NanoOS Gaming is a coordinated runtime preset.

            ok, message = runtime_write(
                governor_path,
                selected,
                "CPU governor",
            )

            if ok:
                set_status(
                    f"CPU governor set to {selected}."
                )
                refresh_hardware()
            else:
                set_status(message, error=True)

        governor_apply.clicked.connect(apply_governor)

        # ----------------------------------------------------
        # EPP action
        # ----------------------------------------------------
        def apply_epp():
            selected = epp_combo.currentText()

            ok, message = runtime_write(
                epp_path,
                selected,
                "CPU EPP",
            )

            if ok:
                set_status(
                    f"Energy preference set to {selected}."
                )
                refresh_hardware()
            else:
                set_status(message, error=True)

        epp_apply.clicked.connect(apply_epp)

        # ----------------------------------------------------
        # Platform profile action
        # ----------------------------------------------------
        def apply_platform():
            selected = platform_combo.currentText()

            ok, message = runtime_write(
                platform_profile_path,
                selected,
                "platform profile",
            )

            if ok:
                set_status(
                    f"Platform profile set to {selected}."
                )
                refresh_hardware()
            else:
                set_status(message, error=True)

        platform_apply.clicked.connect(apply_platform)

        refresh_button.clicked.connect(refresh_hardware)

        refresh_hardware()


        # NANOOS_HARDWARE_GLACIER_V2
        page.setStyleSheet(page.styleSheet() + """
            QWidget#hardwarePage { background: transparent; color: #e6eef6; }
            QWidget#hardwarePage QFrame#hardwareInfo {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f2333, stop:0.6 #101b26, stop:1 #0d1720);
                border: 1px solid #2c4256;
                border-radius: 18px;
            }
            QWidget#hardwarePage QLabel#hwEyebrow {
                color: #66c7e8; font-size: 10px; font-weight: 800;
                letter-spacing: 1px;
            }
            QWidget#hardwarePage QLabel#hwSection {
                color: #7f93a7; font-size: 10px; font-weight: 800;
                padding: 6px 2px 0 2px;
            }
            QWidget#hardwarePage QLabel#hwKey { color: #7f93a7; font-size: 12px; }
            QWidget#hardwarePage QLabel#hwValue {
                color: #e6eef6; font-size: 13px; font-weight: 600;
            }
            QWidget#hardwarePage QFrame#hwTile {
                background: #101b26; border: 1px solid #223543;
                border-radius: 15px;
            }
            QWidget#hardwarePage QFrame#hwTile[tone="hot"] {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #12324a, stop:1 #10293a);
                border: 1px solid #66c7e8;
            }
            QWidget#hardwarePage QFrame#hwTile[tone="off"] {
                background: #0d151d; border: 1px dashed #223543;
            }
            QWidget#hardwarePage QLabel#hwTileValue {
                color: #e6eef6; font-size: 17px; font-weight: 700;
            }
            QWidget#hardwarePage QFrame#hwTile[tone="hot"] QLabel#hwTileValue { color: #9be3f7; }
            QWidget#hardwarePage QFrame#hwTile[tone="off"] QLabel#hwTileValue { color: #4e6276; }
            QWidget#hardwarePage QFrame#hardwareRow {
                background: #101b26; border: 1px solid #223543;
                border-radius: 15px;
            }
            QWidget#hardwarePage QFrame#hardwareRow:hover { border-color: #31566a; }
            QWidget#hardwarePage QLabel#hardwareRowTitle {
                color: #e6eef6; font-size: 14px; font-weight: 700;
            }
            QWidget#hardwarePage QLabel#hwChip {
                border-radius: 9px; padding: 4px 10px;
                font-size: 10px; font-weight: 800; min-width: 44px;
            }
            QWidget#hardwarePage QLabel#hwChip[tone="hot"] {
                color: #9be3f7; background: #10293a; border: 1px solid #2f8fb5;
            }
            QWidget#hardwarePage QLabel#hwChip[tone="idle"] {
                color: #b4c3d2; background: #16212d; border: 1px solid #2c4256;
            }
            QWidget#hardwarePage QLabel#hwChip[tone="off"] {
                color: #4e6276; background: #0d151d; border: 1px solid #223543;
            }
            QWidget#hardwarePage QLabel#hwBanner {
                color: #9be3f7; background: #10293a;
                border: 1px solid #214b5b; border-radius: 11px;
                padding: 10px 14px; font-size: 12px; font-weight: 600;
            }
            QWidget#hardwarePage QLabel#hwBanner[tone="good"] {
                color: #65d58f; background: #10251a; border-color: #28583a;
            }
            QWidget#hardwarePage QLabel#hwBanner[tone="bad"] {
                color: #ef6f7a; background: #2d1217; border-color: #7a2a33;
            }
            QWidget#hardwarePage QPushButton {
                color: #04121b; background: #66c7e8;
                border: 1px solid #9be3f7; border-radius: 11px;
                padding: 9px 18px; font-weight: 800; min-width: 84px;
            }
            QWidget#hardwarePage QPushButton:hover { background: #9be3f7; }
            QWidget#hardwarePage QPushButton:pressed { background: #2f8fb5; }
            QWidget#hardwarePage QPushButton:disabled {
                color: #4e6276; background: #101b26; border-color: #223543;
            }
        """)

        return page

    def build_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(18)
        layout.addLayout(self.page_header(
            "Settings",
            "Configure NanoOS GameMode preferences."
        ))

        card = self.card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(14)

        heading = QLabel("Performance preferences")
        heading.setObjectName("heroTitle")
        card_layout.addWidget(heading)

        card_layout.addWidget(QLabel("Performance profile"))
        self.settings_profile = QComboBox()
        self.settings_profile.addItems(["Balanced", "Performance", "Gaming"])
        self.settings_profile.setCurrentText(
            self.state.get("profile", "Gaming")
        )
        self.settings_profile.setMaxVisibleItems(3)

        profile_popup = self.settings_profile.view()
        profile_popup.setAutoFillBackground(True)
        popup_palette = profile_popup.palette()
        popup_palette.setColor(
            QPalette.ColorRole.Base, QColor("#101b26")
        )
        popup_palette.setColor(
            QPalette.ColorRole.Window, QColor("#101b26")
        )
        popup_palette.setColor(
            QPalette.ColorRole.Text, QColor("#e6eef6")
        )
        popup_palette.setColor(
            QPalette.ColorRole.Highlight, QColor("#1f4a61")
        )
        popup_palette.setColor(
            QPalette.ColorRole.HighlightedText, QColor("#ffffff")
        )
        profile_popup.setPalette(popup_palette)
        profile_popup.setStyleSheet("""
            QListView, QAbstractItemView {
                background-color: #101b26;
                color: #e6eef6;
                border: 1px solid #31566a;
                outline: none;
                padding: 5px;
                selection-background-color: #1f4a61;
                selection-color: #ffffff;
            }
            QListView::item, QAbstractItemView::item {
                background-color: #101b26;
                color: #e6eef6;
                min-height: 30px;
                padding: 8px 12px;
            }
            QListView::item:selected,
            QAbstractItemView::item:selected {
                background-color: #1f4a61;
                color: #ffffff;
            }
        """)

        card_layout.addWidget(self.settings_profile)

        self.settings_io = QCheckBox("Enable I/O priority optimization")
        self.settings_io.setChecked(
            bool(self.state.get("io_optimization", True))
        )
        card_layout.addWidget(self.settings_io)

        self.settings_scheduler = QCheckBox(
            "Enable game process priority adjustment"
        )
        self.settings_scheduler.setChecked(
            bool(self.state.get("scheduler_optimization", True))
        )
        card_layout.addWidget(self.settings_scheduler)

        self.settings_screensaver = QCheckBox(
            "Inhibit screensaver while gaming"
        )
        self.settings_screensaver.setChecked(
            bool(self.state.get("screensaver_inhibit", True))
        )
        card_layout.addWidget(self.settings_screensaver)

        actions = QHBoxLayout()
        self.settings_apply_button = QPushButton("APPLY SETTINGS")
        self.settings_apply_button.clicked.connect(
            self.apply_settings_preferences
        )
        actions.addWidget(self.settings_apply_button)

        self.settings_reset_button = QPushButton("RESET DEFAULTS")
        self.settings_reset_button.clicked.connect(
            self.reset_settings_preferences
        )
        actions.addWidget(self.settings_reset_button)
        card_layout.addLayout(actions)

        self.settings_feedback = QLabel("Settings loaded.")
        self.settings_feedback.setObjectName("muted")
        self.settings_feedback.setWordWrap(True)
        card_layout.addWidget(self.settings_feedback)

        backend = self.card()
        backend_layout = QVBoxLayout(backend)
        backend_layout.setContentsMargins(24, 24, 24, 24)
        backend_layout.setSpacing(14)

        self.backend_status = QLabel("Checking GameMode…")
        self.backend_status.setObjectName("heroTitle")
        backend_layout.addWidget(self.backend_status)

        paths = QLabel(
            f"GameMode config:\n{GAMEMODE_CONFIG}\n\n"
            f"NanoOS state:\n{STATE_FILE}"
        )
        paths.setObjectName("muted")
        paths.setWordWrap(True)
        backend_layout.addWidget(paths)

        self.test_button = QPushButton("RUN GAMEMODE SELF-TEST")
        self.test_button.setObjectName("secondaryButton")
        self.test_button.clicked.connect(self.run_test)
        backend_layout.addWidget(self.test_button)

        layout.addWidget(card)
        layout.addWidget(backend)
        layout.addStretch()

        # NANOOS_OVERRIDE_SETTINGS_SURFACE_V10
        page.setStyleSheet(page.styleSheet() + """
            QWidget { color: #e6eef6; }
            QFrame {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 15px;
            }
            QLabel {
                background: transparent;
                border: none;
                color: #e6eef6;
                padding: 3px 1px;
            }
            QCheckBox {
                color: #e6eef6;
                spacing: 10px;
                padding: 7px 2px;
            }
            QCheckBox::indicator {
                width: 19px;
                height: 19px;
                border-radius: 6px;
                border: 1px solid #4e6276;
                background: #0b1118;
            }
            QCheckBox::indicator:checked {
                background: #2f8fb5;
                border-color: #66c7e8;
            }
            QComboBox {
                color: #e6eef6;
                background: #0b1118;
                border: 1px solid #31566a;
                border-radius: 10px;
                padding: 9px 12px;
            }
            QPushButton {
                color: #e6eef6;
                background: #10293a;
                border: 1px solid #2f8fb5;
                border-radius: 11px;
                padding: 10px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #1f4a61;
                border-color: #66c7e8;
            }
        """)
        return page

    def apply_settings_preferences(self):
        profile = self.settings_profile.currentText()
        if profile not in PROFILE_DATA:
            self.settings_feedback.setText("Invalid profile.")
            return

        self.state["io_optimization"] = self.settings_io.isChecked()
        self.state["scheduler_optimization"] = (
            self.settings_scheduler.isChecked()
        )
        self.state["screensaver_inhibit"] = (
            self.settings_screensaver.isChecked()
        )

        try:
            self.select_profile(profile)
            self.state["io_optimization"] = self.settings_io.isChecked()
            self.state["scheduler_optimization"] = (
                self.settings_scheduler.isChecked()
            )
            self.state["screensaver_inhibit"] = (
                self.settings_screensaver.isChecked()
            )
            save_state(self.state)
            self.write_gamemode_config()
            self.sync_controls()
        except (OSError, KeyError, TypeError) as exc:
            self.settings_feedback.setText(f"Save failed: {exc}")
            return

        self.settings_feedback.setText(f"Applied {profile} preferences.")

    def reset_settings_preferences(self):
        self.settings_profile.setCurrentText(DEFAULT_STATE["profile"])
        self.settings_io.setChecked(DEFAULT_STATE["io_optimization"])
        self.settings_scheduler.setChecked(
            DEFAULT_STATE["scheduler_optimization"]
        )
        self.settings_screensaver.setChecked(
            DEFAULT_STATE["screensaver_inhibit"]
        )
        self.apply_settings_preferences()

    def sync_controls(self):
        self.cpu_toggle.setChecked(
            self.state.get("cpu_boost", True)
        )
        self.gpu_toggle.setChecked(
            self.state.get("gpu_performance", True)
        )
        self.io_toggle.setChecked(
            self.state.get("io_optimization", True)
        )
        self.scheduler_toggle.setChecked(
            self.state.get("scheduler_optimization", True)
        )
        self.screen_toggle.setChecked(
            self.state.get("screensaver_inhibit", True)
        )

        cpu_available = find_cpu_boost_control() is not None

        if not cpu_available:
            self.cpu_toggle.setEnabled(False)
            self.cpu_toggle.setText(
                "CPU Boost\n"
                "Kernel boost control unavailable\n"
                "○  UNAVAILABLE"
            )

        self.update_profile_ui()

    def optimization_changed(self, key, enabled):
        self.state[key] = enabled

        if key == "cpu_boost":
            success, error = set_cpu_boost(enabled)

            if not success:
                self.state[key] = not enabled
                self.cpu_toggle.setChecked(not enabled)

                self.show_error(
                    "CPU Boost",
                    error
                )
                return

        elif key == "gpu_performance":
            success, error = set_gpu_performance(enabled)

            if not success:
                self.state[key] = not enabled
                self.gpu_toggle.setChecked(not enabled)

                self.show_error(
                    "GPU Performance",
                    error
                )
                return

        save_state(self.state)
        self.write_gamemode_config()

        self.profile_summary.setText(
            "Changes saved. GameMode will use these optimization settings "
            "for the next active request."
        )

    def _write_profile_runtime_value(self, path, value, label):
        if not path.exists():
            return True, ""

        try:
            path.write_text(
                str(value),
                encoding="utf-8",
            )
            return True, ""

        except PermissionError:
            operation_map = {
                "scaling_governor": "governor",
                "energy_performance_preference": "epp",
                "platform_profile": "platform",
            }

            operation = operation_map.get(path.name)

            if operation is None:
                return False, (
                    f"No privileged NanoOS GameMode operation exists "
                    f"for {label}."
                )

            return run_privileged_helper(
                operation,
                str(value),
            )

        except OSError as exc:
            return False, str(exc)

    def apply_profile_runtime(self, name):
        profile = PROFILE_DATA[name]
        errors = []

        # ----------------------------------------------------
        # GPU performance readiness
        # ----------------------------------------------------
        desired_gpu = name != "Balanced"

        if gpu_performance_control() is not None:
            success, error = set_gpu_performance(desired_gpu)

            if not success:
                errors.append(error)
            else:
                self.state["gpu_performance"] = desired_gpu

        policy = Path(
            "/sys/devices/system/cpu/cpufreq/policy0"
        )

        # ----------------------------------------------------
        # CPU boost
        # ----------------------------------------------------
        desired_boost = name != "Balanced"

        success, error = set_cpu_boost(desired_boost)

        if not success:
            if find_cpu_boost_control() is not None:
                errors.append(error)
        else:
            self.state["cpu_boost"] = desired_boost

        # ----------------------------------------------------
        # CPU governor
        # ----------------------------------------------------
        governor_path = policy / "scaling_governor"
        available_governors_path = (
            policy / "scaling_available_governors"
        )

        if governor_path.exists():
            try:
                available = (
                    available_governors_path
                    .read_text(encoding="utf-8")
                    .strip()
                    .split()
                ) if available_governors_path.exists() else []

            except OSError:
                available = []

            desired_governor = profile["desiredgov"]

            if not available or desired_governor in available:
                success, error = self._write_profile_runtime_value(
                    governor_path,
                    desired_governor,
                    "CPU governor",
                )

                if not success:
                    errors.append(error)

        # ----------------------------------------------------
        # Energy Performance Preference
        # ----------------------------------------------------
        epp_path = policy / "energy_performance_preference"
        epp_choices_path = (
            policy / "energy_performance_available_preferences"
        )

        if epp_path.exists():
            try:
                available_epp = (
                    epp_choices_path
                    .read_text(encoding="utf-8")
                    .strip()
                    .split()
                ) if epp_choices_path.exists() else []

            except OSError:
                available_epp = []

            desired_epp = profile.get(
                "desired_epp",
                "performance",
            )

            # Some CPUs expose only one EPP value. In that case
            # leave it alone instead of pretending we changed it.
            if not available_epp or desired_epp in available_epp:
                success, error = self._write_profile_runtime_value(
                    epp_path,
                    desired_epp,
                    "CPU EPP",
                )

                if not success:
                    errors.append(error)

        # ----------------------------------------------------
        # Platform profile
        # ----------------------------------------------------
        platform_path = Path(
            "/sys/firmware/acpi/platform_profile"
        )

        platform_choices_path = Path(
            "/sys/firmware/acpi/platform_profile_choices"
        )

        if platform_path.exists():
            try:
                available_platforms = (
                    platform_choices_path
                    .read_text(encoding="utf-8")
                    .strip()
                    .split()
                ) if platform_choices_path.exists() else []

            except OSError:
                available_platforms = []

            desired_platform = profile.get(
                "desired_platform",
                profile["desiredprof"],
            )

            # Only apply a platform profile if the firmware/kernel
            # actually exposes that choice.
            if (
                not available_platforms
                or desired_platform in available_platforms
            ):
                success, error = self._write_profile_runtime_value(
                    platform_path,
                    desired_platform,
                    "platform profile",
                )

                if not success:
                    errors.append(error)

        return errors

    def select_profile(self, name):
        self.state["profile"] = name

        profile = PROFILE_DATA[name]

        self.state["gpu_performance"] = (
            profile["desiredprof"] == "performance"
        )

        self.state["io_optimization"] = (
            profile["ioprio"] == "0"
        )

        self.state["scheduler_optimization"] = (
            profile["renice"] != "0"
        )

        self.state["screensaver_inhibit"] = True

        if name == "Gaming":
            self.state["cpu_boost"] = True
        elif name == "Balanced":
            self.state["cpu_boost"] = False
        else:
            self.state["cpu_boost"] = True

        # Save the profile first so the GameMode daemon receives
        # the same preset the UI is showing.
        save_state(self.state)
        self.write_gamemode_config()

        # Apply the runtime CPU/platform controls too.
        # Hardware and Profiles therefore share one state.
        with PrivilegedBatch() as batch:
            runtime_errors = self.apply_profile_runtime(name)
        if not batch.ok:
            runtime_errors.append(batch.error)

        # Re-read actual CPU boost state when available.
        if find_cpu_boost_control() is not None:
            actual_boost = read_cpu_boost()

            if actual_boost is not None:
                self.state["cpu_boost"] = actual_boost

        save_state(self.state)
        self.write_gamemode_config()

        self.sync_controls()

        if runtime_errors:
            self.show_error(
                "Profile runtime settings",
                "\n".join(runtime_errors),
            )
        else:
            self._nanoos_smooth_status_text(
                self.header_status, "● PROFILE APPLIED"
            )

    def update_profile_ui(self):
        current = self.state["profile"]

        for card in self.profile_cards:
            card.setChecked(card.name == current)
            card.update_text()

        self.profile_name.setText("Ultra" if current == "Gaming" else current)

        descriptions = {
            "Balanced":
                "powersave CPU governor, lighter process optimization, "
                "and reduced I/O priority when supported.",
            "Performance":
                "performance CPU governor, moderate process priority, "
                "and high I/O priority.",
            "Gaming":
                "performance CPU governor, stronger process priority, "
                "high I/O priority, CPU boost, and performance controls.",
        }

        self.profile_details.setText(
            descriptions.get(current, "")
        )

        self.profile_summary.setText(
            f"Active profile: {current}"
        )

    def write_gamemode_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        if GAMEMODE_CONFIG.exists() and not GAMEMODE_BACKUP.exists():
            try:
                shutil.copy2(
                    GAMEMODE_CONFIG,
                    GAMEMODE_BACKUP
                )
            except OSError:
                pass

        profile = PROFILE_DATA[self.state["profile"]].copy()

        if self.state["gpu_performance"]:
            desiredprof = "performance"
        else:
            desiredprof = "balanced"

        if self.state["io_optimization"]:
            ioprio = "0"
        else:
            ioprio = "off"

        if self.state["scheduler_optimization"]:
            renice = profile["renice"]
        else:
            renice = "0"

        if self.state["screensaver_inhibit"]:
            inhibit = "1"
        else:
            inhibit = "0"

        # gamemode.ini only takes effect while GameMode is active, so it
        # must always carry the profile's governor. (It used to be written
        # as powersave unless this app's own toggle was on, which made
        # games launched with gamemoderun run on the powersave governor.)
        policy = Path("/sys/devices/system/cpu/cpufreq/policy0")
        available_path = policy / "scaling_available_governors"
        try:
            available_governors = (
                available_path.read_text(encoding="utf-8").split()
                if available_path.exists() else []
            )
        except OSError:
            available_governors = []

        desiredgov = profile["desiredgov"]
        if available_governors and desiredgov not in available_governors:
            desiredgov = (
                "performance" if "performance" in available_governors
                else available_governors[0]
            )

        # Platform profile (laptops / handhelds), only when exposed.
        platform_line = ""
        choices_path = Path("/sys/firmware/acpi/platform_profile_choices")
        try:
            platform_choices = (
                choices_path.read_text(encoding="utf-8").split()
                if choices_path.exists() else []
            )
        except OSError:
            platform_choices = []
        if desiredprof in platform_choices:
            platform_line = f"desiredprof={desiredprof}\n"

        content = f"""[general]
reaper_freq=5
desiredgov={desiredgov}
{platform_line}softrealtime={profile["softrealtime"]}
renice={renice}
ioprio={ioprio}
inhibit_screensaver={inhibit}
disable_splitlock=1
"""

        try:
            GAMEMODE_CONFIG.write_text(
                content,
                encoding="utf-8"
            )
        except OSError as exc:
            self.show_error(
                "GameMode configuration",
                str(exc)
            )

    def toggle_gamemode(self):
        if self.master_toggle.isChecked():
            self._nanoos_shutdown_pending = False
            self.enable_gamemode()
        else:
            self._nanoos_shutdown_pending = True
            self.disable_gamemode()

    def enable_gamemode(self):
        # NANOOS_OVERRIDE_GAMEMODE_REQUEST_LIFECYCLE_V3
        if shutil.which("gamemoded") is None:
            blocked = self.master_toggle.blockSignals(True)
            try:
                self.master_toggle.setChecked(False)
                self.master_toggle.setText("ENABLE")
            finally:
                self.master_toggle.blockSignals(blocked)
            self.show_error(
                "GameMode",
                "The GameMode daemon is not installed.\n\n"
                "Install the 'gamemode' package (NanoOS Welcome → Gaming "
                "Components, or NanoOS Control Center → Gaming), then try "
                "again.",
            )
            return

        self.state["gamemode"] = True
        save_state(self.state)
        self.write_gamemode_config()

        previous = self.request_process
        if previous is not None:
            if previous.state() != QProcess.ProcessState.NotRunning:
                # A request is already running; do not kill it and mistake
                # its intentional termination for a startup failure.
                QTimer.singleShot(100, self.refresh_status)
                return

            self.request_process = None
            for signal in (previous.errorOccurred, previous.finished):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    pass
            previous.deleteLater()

        executable = shutil.which("gamemoded") or "/usr/bin/gamemoded"
        process = QProcess(self)
        process.setProgram(executable)
        process.setArguments(["-r"])

        process.errorOccurred.connect(
            lambda error, request=process: self.game_mode_error(
                f"QProcess error {error}: {request.errorString()}",
                request,
            )
        )
        process.finished.connect(
            lambda *_: self.refresh_status()
        )

        self.request_process = process
        process.start()
        QTimer.singleShot(800, self.refresh_status)

    def disable_gamemode(self):
        self._nanoos_shutdown_pending = True
        self.state["gamemode"] = False
        save_state(self.state)

        process = self.request_process
        self.request_process = None

        if process is not None:
            # Disconnect request callbacks before the intentional shutdown.
            for signal in (process.errorOccurred, process.finished):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    pass

            if process.state() != QProcess.ProcessState.NotRunning:
                # Delete the QObject after its process exits; do not block UI.
                process.finished.connect(process.deleteLater)
                process.terminate()

                # Kill asynchronously only if the client refuses to exit.
                QTimer.singleShot(
                    1200,
                    lambda request=process:
                        self._nanoos_force_kill_request(request),
                )
            else:
                process.deleteLater()

        self.write_gamemode_config()
        QTimer.singleShot(500, self.refresh_status)
        QTimer.singleShot(1800, self._nanoos_finish_shutdown_guard)

    def _nanoos_finish_shutdown_guard(self):
        self._nanoos_shutdown_pending = False
        self.refresh_status()

    def _nanoos_force_kill_request(self, request):
        """Nonblocking fallback for an unresponsive GameMode request client."""
        try:
            if request.state() != QProcess.ProcessState.NotRunning:
                request.kill()
            else:
                request.deleteLater()
        except RuntimeError:
            # The request QObject may already have been deleted.
            pass

    def game_mode_error(self, detail="", request=None):
        # Ignore a delayed event belonging to a request that is no longer current.
        if request is not None and request is not self.request_process:
            return

        process = self.request_process
        self.request_process = None

        if process is not None:
            for signal in (process.errorOccurred, process.finished):
                try:
                    signal.disconnect()
                except (RuntimeError, TypeError):
                    pass

            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(800)
            process.deleteLater()

        self.state["gamemode"] = False
        save_state(self.state)

        blocked = self.master_toggle.blockSignals(True)
        try:
            self.master_toggle.setChecked(False)
            self.master_toggle.setText("ENABLE")
        finally:
            self.master_toggle.blockSignals(blocked)

        message = "The GameMode request client failed."
        if detail:
            message += f"\n\nDetails: {detail}"
        else:
            message += "\n\nThe request process reported an error."

        self.show_error("GameMode", message)

    def refresh_status(self):
        active, detail = gamemode_status()

        # During shutdown, don't let a stale backend result re-check the toggle.
        if getattr(self, "_nanoos_shutdown_pending", False):
            active = False

        if active:
            self._nanoos_smooth_status_text(
                self.header_status, "● ACTIVE"
            )
            if self.header_status.property("active") is not True:
                self.header_status.setProperty("active", True)
                self.header_status.style().unpolish(self.header_status)
                self.header_status.style().polish(self.header_status)

            if self.game_mode_big.text() != "GameMode Active":
                self.game_mode_big.setText("GameMode Active")
            active_detail = "NanoOS performance optimizations are active."
            if self.game_mode_detail.text() != active_detail:
                self.game_mode_detail.setText(active_detail)

            if not self.master_toggle.isChecked():
                self.master_toggle.setChecked(True)
            if self.master_toggle.text() != "DISABLE":
                self.master_toggle.setText("DISABLE")

        else:
            self._nanoos_smooth_status_text(
                self.header_status, "● READY"
            )
            if self.header_status.property("active") is not False:
                self.header_status.setProperty("active", False)
                self.header_status.style().unpolish(self.header_status)
                self.header_status.style().polish(self.header_status)

            if self.game_mode_big.text() != "GameMode Ready":
                self.game_mode_big.setText("GameMode Ready")
            ready_detail = "Waiting for a game request."
            if self.game_mode_detail.text() != ready_detail:
                self.game_mode_detail.setText(ready_detail)

            if self.master_toggle.isChecked():
                self.master_toggle.setChecked(False)
            if self.master_toggle.text() != "ENABLE":
                self.master_toggle.setText("ENABLE")

        if shutil.which("gamemoded") is None:
            backend_text = "GameMode backend: NOT INSTALLED"
        elif "active" in detail:        # "gamemode is active / inactive"
            backend_text = "GameMode backend: ONLINE"
        else:
            backend_text = "GameMode backend: CHECK FAILED"
        if self.backend_status.text() != backend_text:
            self.backend_status.setText(backend_text)

        cpu_state = read_cpu_boost()

        if cpu_state is not None:
            self.state["cpu_boost"] = cpu_state
            self.cpu_toggle.blockSignals(True)
            self.cpu_toggle.setChecked(cpu_state)
            self.cpu_toggle.blockSignals(False)

        if active:
            self.state["gamemode"] = True
        else:
            self.state["gamemode"] = False

    def run_test(self):
        """Run `gamemoded -t` in the background and show its report."""
        running = getattr(self, "_nanoos_test_process", None)
        if running is not None:
            return

        executable = shutil.which("gamemoded")
        if executable is None:
            self.show_error(
                "GameMode Self-Test",
                "gamemoded is not installed. Install the 'gamemode' package "
                "(NanoOS Welcome → Gaming Components).",
            )
            return

        process = QProcess(self)
        process.setProgram(executable)
        process.setArguments(["-t"])
        process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self._nanoos_test_process = process
        self.test_button.setEnabled(False)
        self.test_button.setText("RUNNING SELF-TEST…")

        def finished(*_):
            output = bytes(process.readAll()).decode(
                errors="replace"
            ).strip()
            self._nanoos_test_process = None
            self.test_button.setEnabled(True)
            self.test_button.setText("RUN GAMEMODE SELF-TEST")
            code = process.exitCode()
            process.deleteLater()
            if not output:
                output = f"gamemoded exited with code {code}"
            if code == 0:
                QMessageBox.information(
                    self, "GameMode Self-Test", output[-6000:]
                )
            else:
                self.show_error("GameMode Self-Test", output[-6000:])

        def failed(_error):
            if process.state() == QProcess.ProcessState.NotRunning:
                finished()

        process.finished.connect(finished)
        process.errorOccurred.connect(failed)
        # Safety net: the test normally takes a few seconds.
        QTimer.singleShot(
            60000,
            lambda: process.state() != QProcess.ProcessState.NotRunning
            and process.kill(),
        )
        process.start()

    def show_error(self, title, message):
        QMessageBox.critical(
            self,
            title,
            message
        )

    def apply_theme(self):
        self.setStyleSheet("""
            QWidget {
                color: #e6eef6;
                font-family: "Inter", "Noto Sans", sans-serif;
            }

           QMainWindow {
               background-color: #0b1118;
           }

           #appRoot {
               background-color: #0b1118;
           }

           QStackedWidget {
               background-color: #0b1118;
               border: none;
           }

           QStackedWidget > QWidget {
               background-color: #0b1118;
               border: none;
           }

           QScrollArea {
               background-color: #0b1118;
               border: none;
           }

           QScrollArea > QWidget {
               background-color: #0b1118;
               border: none;
           }

           QScrollArea > QWidget > QWidget {
               background-color: #0b1118;
               border: none;
           }

           QLabel {
               background: transparent;
               border: none;
           }

           QMenu {
               background: #101b26;
               border: 1px solid #1a2936;
               color: #e6eef6;
           }

           QMenu::item:selected {
               background: #132230;
               color: #ffffff;
           }

           QComboBox QAbstractItemView {
               background: #101b26;
               border: 1px solid #1a2936;
               color: #e6eef6;
               selection-background-color: #132230;
               selection-color: #ffffff;
           }

           QAbstractItemView {
               background: #101b26;
               color: #e6eef6;
               selection-background-color: #132230;
               selection-color: #ffffff;
           }

            QLabel {
                background: transparent;
                border: none;
            }

            #sidebar {
                background: #070b11;
                border-right: 1px solid #132230;
            }

            #brand {
                font-size: 24px;
                font-weight: 900;
                letter-spacing: 2px;
            }

            #brandSub {
                color: #7f93a7;
                font-size: 13px;
            }

            #mainTitle {
                font-size: 30px;
                font-weight: 850;
            }

            #pageTitle {
                font-size: 25px;
                font-weight: 800;
            }

            #heroTitle {
                font-size: 24px;
                font-weight: 800;
            }

            #eyebrow {
                color: #7f93a7;
                font-size: 11px;
                font-weight: 800;
                letter-spacing: 1.5px;
            }

            #sectionTitle {
                color: #7f93a7;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1.6px;
                padding-left: 2px;
            }

            #muted {
                color: #7f93a7;
                font-size: 13px;
            }

            #mutedSmall {
                color: #4e6276;
                font-size: 11px;
            }

            #statusPill {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 14px;
                padding: 8px 13px;
                color: #b4c3d2;
                font-weight: 800;
            }

            #statusPill[active="true"] {
                background: #10251a;
                border: 1px solid #28583a;
                color: #65d58f;
            }

            #card {
                background: #101b26;
                border: 1px solid #1a2936;
                border-radius: 20px;
            }

            #navButton {
                background: transparent;
                border: 0;
                border-radius: 12px;
                color: #7f93a7;
                text-align: left;
                padding: 13px 15px;
                font-size: 14px;
                font-weight: 650;
            }

            #navButton:hover {
                background: #101b26;
                color: #e6eef6;
            }

            #navButton:checked {
                background: #132230;
                color: #ffffff;
            }

            #masterToggle {
                background: #132230;
                border: 1px solid #223543;
                border-radius: 17px;
                color: #e6eef6;
                font-size: 15px;
                font-weight: 850;
            }

            #masterToggle:hover {
                background: #1a2936;
            }

            #masterToggle:checked {
                background: #163a27;
                border: 1px solid #2d8050;
                color: #77e5a1;
            }

            QPushButton[checkable="true"] {
                background: #101b26;
                border: 1px solid #223543;
                border-radius: 17px;
                color: #e6eef6;
                text-align: left;
                padding: 14px 17px;
                font-size: 14px;
                font-weight: 750;
            }

            QPushButton[checkable="true"]:hover {
                background: #132230;
                border-color: #223543;
            }

            QPushButton[checkable="true"]:checked {
                background: #13251b;
                border-color: #28613f;
            }

            QPushButton[checkable="true"]:disabled {
                color: #4e6276;
                background: #0b1118;
                border-color: #132230;
            }

            QPushButton[checkable="true"]:checked:hover {
                background: #173020;
            }

            QPushButton:focus {
                outline: none;
            }

            QListWidget:focus {
                outline: none;
            }

            #secondaryButton {
                background: #132230;
                border: 1px solid #223543;
                border-radius: 12px;
                padding: 12px 17px;
                font-weight: 750;
            }

            #secondaryButton:hover {
                background: #1a2936;
            }

            QListWidget#gameList {
                background: #0b1118;
                border: 1px solid #1a2936;
                border-radius: 14px;
                padding: 6px;
                outline: none;
            }

            QListWidget#gameList::item {
                padding: 15px;
                border-radius: 10px;
                color: #b4c3d2;
            }

            QListWidget#gameList::item:hover {
                background: #101b26;
            }

            QListWidget#gameList::item:selected {
                background: #1a2936;
                color: #ffffff;
            }
        """)
        # --------------------------------------------------------
        # NANOOS GLOBAL QT EXTERMINATION
        #
        # Final anti-Win95 pass:
        # Qt's host/platform styling is not allowed to leak into
        # the GameMode UI anymore.
        # --------------------------------------------------------
        QApplication.setStyle("Fusion")

        nanoos_global_style = """
            /* ---------- Core surfaces ---------- */

            QMainWindow,
            QDialog,
            QMessageBox,
            QWidget {
                color: #e6eef6;
                font-family: "Inter", "Noto Sans", sans-serif;
                selection-background-color: #223543;
                selection-color: #ffffff;
            }

            QMainWindow,
            QDialog,
            QMessageBox {
                background: #0b1118;
            }

            QFrame {
                color: #e6eef6;
            }

            QStackedWidget,
            QStackedWidget > QWidget,
            QScrollArea,
            QScrollArea > QWidget,
            QScrollArea > QWidget > QWidget,
            QAbstractScrollArea,
            QAbstractScrollArea > QWidget {
                background: transparent;
                border: none;
            }

            QLabel {
                background: transparent;
                border: none;
                color: #e6eef6;
            }

            /* ---------- Buttons ---------- */

            QPushButton,
            QToolButton {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 8px 15px;
                min-height: 22px;
                font-weight: 600;
                outline: none;
            }

            QPushButton:hover,
            QToolButton:hover {
                background: #132230;
                border-color: #31566a;
            }

            QPushButton:pressed,
            QToolButton:pressed {
                background: #1a2936;
                border-color: #4e6276;
            }

            QPushButton:checked,
            QToolButton:checked {
                background: #223543;
                border-color: #4e6276;
                color: #ffffff;
            }

            QPushButton:focus,
            QToolButton:focus {
                outline: none;
                border-color: #31566a;
            }

            QPushButton:disabled,
            QToolButton:disabled {
                background: #0b1118;
                color: #4e6276;
                border-color: #1a2936;
            }

            /* ---------- Combo boxes ---------- */

            QComboBox {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 8px 12px;
                min-height: 22px;
                outline: none;
            }

            QComboBox:hover {
                background: #132230;
                border-color: #31566a;
            }

            QComboBox:focus,
            QComboBox:on {
                background: #101b26;
                border-color: #31566a;
            }

            QComboBox::drop-down {
                background: #101b26;
                border: none;
                border-left: 1px solid #223543;
                width: 30px;
                margin: 1px;
                border-top-right-radius: 9px;
                border-bottom-right-radius: 9px;
            }

            QComboBox::drop-down:hover {
                background: #1a2936;
            }

            QComboBox:disabled {
                background: #0b1118;
                color: #4e6276;
                border-color: #1a2936;
            }

            /* ---------- Item views / popups ---------- */

            QAbstractItemView,
            QListView,
            QTreeView,
            QTableView {
                background: #0b1118;
                color: #e6eef6;
                alternate-background-color: #101b26;
                border: 1px solid #223543;
                border-radius: 10px;
                outline: none;
                selection-background-color: #223543;
                selection-color: #ffffff;
            }

            QAbstractItemView::item {
                background: transparent;
                color: #e6eef6;
                border-radius: 7px;
                padding: 7px 10px;
                min-height: 24px;
            }

            QAbstractItemView::item:hover {
                background: #132230;
                color: #ffffff;
            }

            QAbstractItemView::item:selected {
                background: #223543;
                color: #ffffff;
            }

            /* ---------- Text inputs ---------- */

            QLineEdit,
            QTextEdit,
            QPlainTextEdit {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 8px 10px;
                selection-background-color: #223543;
                selection-color: #ffffff;
                outline: none;
            }

            QLineEdit:hover,
            QTextEdit:hover,
            QPlainTextEdit:hover {
                border-color: #31566a;
            }

            QLineEdit:focus,
            QTextEdit:focus,
            QPlainTextEdit:focus {
                border-color: #31566a;
            }

            QLineEdit:disabled,
            QTextEdit:disabled,
            QPlainTextEdit:disabled {
                background: #0b1118;
                color: #4e6276;
            }

            /* ---------- Checkboxes / radio buttons ---------- */

            QCheckBox,
            QRadioButton {
                background: transparent;
                color: #e6eef6;
                spacing: 8px;
                outline: none;
            }

            QCheckBox:focus,
            QRadioButton:focus {
                outline: none;
            }

            /* ---------- Spin boxes ---------- */

            QSpinBox,
            QDoubleSpinBox {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 7px 10px;
                outline: none;
            }

            QSpinBox:focus,
            QDoubleSpinBox:focus {
                border-color: #31566a;
            }

            QSpinBox::up-button,
            QSpinBox::down-button,
            QDoubleSpinBox::up-button,
            QDoubleSpinBox::down-button {
                background: #101b26;
                border: none;
            }

            QSpinBox::up-button:hover,
            QSpinBox::down-button:hover,
            QDoubleSpinBox::up-button:hover,
            QDoubleSpinBox::down-button:hover {
                background: #1a2936;
            }

            /* ---------- Menus ---------- */

            QMenu {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 10px;
                padding: 5px;
            }

            QMenu::item {
                background: transparent;
                color: #e6eef6;
                border-radius: 7px;
                padding: 7px 12px;
            }

            QMenu::item:selected {
                background: #223543;
                color: #ffffff;
            }

            QMenu::separator {
                height: 1px;
                background: #223543;
                margin: 5px 8px;
            }

            /* ---------- Tabs ---------- */

            QTabWidget::pane {
                background: transparent;
                border: none;
            }

            QTabBar::tab {
                background: #101b26;
                color: #7f93a7;
                border: 1px solid #1a2936;
                border-radius: 9px;
                padding: 7px 13px;
                margin-right: 4px;
            }

            QTabBar::tab:hover {
                background: #132230;
                color: #e6eef6;
            }

            QTabBar::tab:selected {
                background: #223543;
                color: #ffffff;
                border-color: #31566a;
            }

            /* ---------- Group boxes ---------- */

            QGroupBox {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #1a2936;
                border-radius: 12px;
                margin-top: 10px;
                padding: 10px;
                font-weight: 600;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: #e6eef6;
                background: #0b1118;
            }

            /* ---------- Progress ---------- */

            QProgressBar {
                background: #101b26;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 7px;
                text-align: center;
            }

            QProgressBar::chunk {
                background: #31566a;
                border-radius: 6px;
            }

            /* ---------- Scrollbars ---------- */

            QScrollBar:vertical {
                background: transparent;
                width: 9px;
                margin: 2px 0;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #223543;
                border: none;
                border-radius: 4px;
                min-height: 28px;
            }

            QScrollBar::handle:vertical:hover {
                background: #4e6276;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
                border: none;
                height: 0px;
            }

            QScrollBar:horizontal {
                background: transparent;
                height: 9px;
                border: none;
            }

            QScrollBar::handle:horizontal {
                background: #223543;
                border: none;
                border-radius: 4px;
                min-width: 28px;
            }

            QScrollBar::handle:horizontal:hover {
                background: #4e6276;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: transparent;
                border: none;
                width: 0px;
            }

            /* ---------- Dialog controls ---------- */

            QMessageBox QLabel {
                background: transparent;
                color: #e6eef6;
            }

            QMessageBox QPushButton {
                min-width: 88px;
            }

            /* ---------- Tooltips ---------- */

            QToolTip {
                background: #0b1118;
                color: #e6eef6;
                border: 1px solid #223543;
                border-radius: 8px;
                padding: 6px 9px;
            }

            /* ---------- Status bar ---------- */

            QStatusBar {
                background: #0b1118;
                color: #7f93a7;
                border: none;
            }

            /* ---------- Splitters ---------- */

            QSplitter::handle {
                background: #1a2936;
            }

            QSplitter::handle:hover {
                background: #31566a;
            }
        """

        self.setStyleSheet(
            self.styleSheet() + "\n" + nanoos_global_style
        )

    def closeEvent(self, event):
        if self.request_process is not None:
            self.disable_gamemode()

        event.accept()


    def build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(222)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(13, 15, 13, 12)
        layout.setSpacing(5)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(11)
        mark = QLabel()
        mark.setFixedSize(42, 42)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark_file = Path("/usr/share/nanoos/branding/nanoos-mark-128.png")
        pixmap = QPixmap(str(mark_file)) if mark_file.is_file() else QPixmap()
        if not pixmap.isNull():
            ratio = self.devicePixelRatioF()
            pixmap = pixmap.scaled(
                int(42 * ratio), int(42 * ratio),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pixmap.setDevicePixelRatio(ratio)
            mark.setPixmap(pixmap)
        else:
            mark.setText("N")
            mark.setObjectName("brandMark")
        brand_row.addWidget(mark)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand = QLabel("NanoOS")
        brand.setObjectName("brand")
        brand_text.addWidget(brand)
        product = QLabel("GAMEMODE")
        product.setObjectName("brandSub")
        brand_text.addWidget(product)
        brand_row.addLayout(brand_text, 1)
        layout.addLayout(brand_row)

        layout.addSpacing(14)

        nav_items = [
            ("Overview", 0),
            ("Profiles", 1),
            ("Per-Game", 2),
            ("Hardware", 3),
            ("Settings", 4),
            ("Game Library", 5),
            ("Performance Lab", 6),
            ("Network Lab", 7),
            ("Audio Lab", 8),
            ("Latency Lab", 9),
        ]

        self._nanoos_override_nav_buttons = []
        for label, index in nav_items:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(label)
            button.clicked.connect(
                lambda _, i=index, b=button: self.navigate(i, b)
            )

            if index == 0:
                button.setChecked(True)

            layout.addWidget(button)
            self._nanoos_override_nav_buttons.append(button)

        layout.addStretch()

        footer_line = QFrame()
        footer_line.setFixedHeight(1)
        footer_line.setStyleSheet("background:#1d2c38;border:none;")
        layout.addWidget(footer_line)
        footer = QLabel("NANOOS GAMEMODE  ·  V2")
        footer.setObjectName("mutedSmall")
        layout.addWidget(footer)

        return sidebar

    def _nanoos_polish_controls(self):
        """Give every stock Qt control the NanoOS look.

        Page stylesheets kept overriding app-wide rules, leaving grey
        Windows-style dropdown arrows and plain checkboxes. A widget's own
        stylesheet has the highest priority, so the rules are set there.
        """
        chevron = nanoos_ui_icon("chevron-down.svg")
        chevron_off = nanoos_ui_icon("chevron-down-disabled.svg")
        check = nanoos_ui_icon("check.svg")

        combo_qss = f"""
            QComboBox {{
                color: #e6eef6; background: #0b151f;
                border: 1px solid #2c4256; border-radius: 10px;
                padding: 8px 34px 8px 12px; min-height: 20px;
                font-weight: 600;
            }}
            QComboBox:hover {{ border-color: #66c7e8; background: #0e1b27; }}
            QComboBox:on {{ border-color: #66c7e8; }}
            QComboBox:disabled {{ color: #4e6276; border-color: #1d2c38; background: #0b1118; }}
            QComboBox::drop-down {{
                subcontrol-origin: padding; subcontrol-position: center right;
                width: 30px; border: none; background: transparent;
            }}
            QComboBox::down-arrow {{ image: url({chevron}); width: 12px; height: 12px; }}
            QComboBox::down-arrow:disabled {{ image: url({chevron_off}); }}
        """
        popup_qss = """
            QListView, QAbstractItemView {
                color: #e6eef6; background: #101b26;
                border: 1px solid #31566a; border-radius: 10px;
                padding: 5px; outline: 0;
            }
            QAbstractItemView::item { min-height: 30px; padding: 4px 10px; border-radius: 7px; }
            QAbstractItemView::item:hover { background: #16212d; }
            QAbstractItemView::item:selected { background: #10293a; color: #9be3f7; }
        """
        for combo in self.findChildren(QComboBox):
            if isinstance(combo, NanoOSCompactTabSelector):
                continue  # custom painted
            combo.setStyleSheet(combo_qss)
            combo.view().setStyleSheet(popup_qss)
            combo.setCursor(Qt.CursorShape.PointingHandCursor)

        check_qss = f"""
            QCheckBox {{ color: #e6eef6; spacing: 10px; background: transparent; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px; border-radius: 6px;
                border: 1px solid #31566a; background: #0b151f;
            }}
            QCheckBox::indicator:hover {{ border-color: #66c7e8; }}
            QCheckBox::indicator:checked {{
                background: #66c7e8; border-color: #9be3f7; image: url({check});
            }}
            QCheckBox:disabled {{ color: #4e6276; }}
        """
        for box in self.findChildren(QCheckBox):
            box.setStyleSheet(check_qss)
            box.setCursor(Qt.CursorShape.PointingHandCursor)

        slider_qss = """
            QSlider::groove:horizontal { height: 6px; border-radius: 3px; background: #16212d; }
            QSlider::sub-page:horizontal {
                border-radius: 3px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2f8fb5, stop:1 #66c7e8);
            }
            QSlider::handle:horizontal {
                width: 16px; height: 16px; margin: -6px 0; border-radius: 8px;
                background: #e6eef6; border: 2px solid #66c7e8;
            }
            QSlider::handle:horizontal:hover { background: #ffffff; border-color: #9be3f7; }
            QSlider::groove:horizontal:disabled, QSlider::sub-page:horizontal:disabled { background: #101b26; }
        """
        for slider in self.findChildren(QSlider):
            slider.setStyleSheet(slider_qss)

        for edit in self.findChildren(QLineEdit):
            if edit.parent() is not None and isinstance(edit.parent(), QComboBox):
                continue
            edit.setStyleSheet("""
                QLineEdit {
                    color: #e6eef6; background: #0b151f;
                    border: 1px solid #2c4256; border-radius: 10px;
                    padding: 9px 12px; selection-background-color: #2f8fb5;
                }
                QLineEdit:hover { border-color: #31566a; }
                QLineEdit:focus { border-color: #66c7e8; background: #0e1b27; }
            """)

    def _nanoos_apply_shared_shell_style(self):
        """Final stylesheet layer: the shared NanoOS shell look.

        Appended after apply_theme() so these rules win. They mirror
        nanoos_ui.SHELL_QSS (Welcome / Control Center).
        """
        self.setStyleSheet(self.styleSheet() + """
            QWidget { font-family: "Inter", "Noto Sans", sans-serif; }
            QMainWindow, #nanoosWindow, #appRoot { background: #070b11; }
            QFrame#shell {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #101a25, stop:1 #0b131c);
                border: 1px solid #243543;
                border-radius: 26px;
            }
            QStackedWidget, QStackedWidget > QWidget,
            QScrollArea, QScrollArea > QWidget,
            QScrollArea > QWidget > QWidget {
                background: transparent;
                border: none;
            }
            QFrame#sidebar {
                background: #0a121b;
                border: 1px solid #1d2d3a;
                border-radius: 21px;
            }
            QLabel#brandMark {
                color: #04121b; background: #66c7e8; border-radius: 13px;
                font-size: 22px; font-weight: 900;
            }
            QLabel#brand {
                color: #e6eef6; font-size: 19px; font-weight: 800;
                letter-spacing: 0px;
            }
            QLabel#brandSub { color: #7f93a7; font-size: 11px; }
            QLabel#mutedSmall { color: #4e6276; font-size: 10px; }
            QLabel#sectionEyebrow {
                color: #66c7e8; font-size: 10px; font-weight: 800;
            }
            QLabel#pageTitle { color: #e6eef6; font-size: 29px; font-weight: 800; }
            QLabel#statusPill {
                color: #9be3f7; background: #10293a;
                border: 1px solid #214b5b; border-radius: 11px;
                padding: 9px 12px; font-size: 11px; font-weight: 700;
            }
            QLabel#statusPill[active="true"] {
                color: #65d58f; background: #10251a; border: 1px solid #28583a;
            }
            QPushButton#navButton {
                background: #101b25; color: #e6eef6;
                border: none; border-left: 2px solid transparent;
                border-radius: 13px; text-align: left;
                padding: 0px 13px; min-height: 44px; max-height: 44px;
                font-size: 13px; font-weight: 600;
            }
            QPushButton#navButton:hover { background: #192c3a; }
            QPushButton#navButton:checked {
                background: #112f3b; color: #e6eef6;
                border-left: 2px solid #66c7e8;
            }
            QFrame#card {
                background: #101b26; border: 1px solid #223543;
                border-radius: 17px;
            }
            QPushButton#masterToggle { min-width: 170px; min-height: 70px; }
            QScrollBar:vertical { background: transparent; width: 9px; margin: 3px 1px; }
            QScrollBar::handle:vertical { background: #2b4657; border-radius: 3px; min-height: 28px; }
            QScrollBar::handle:vertical:hover { background: #66c7e8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                height: 0; background: transparent;
            }
            QToolTip { color: #e6eef6; background: #142331; border: 1px solid #315063; padding: 6px; }
            QMessageBox { background: #0a121b; }
            QMessageBox QLabel { color: #e6eef6; font-size: 13px; }
            QMessageBox QPushButton {
                color: #04121b; background: #66c7e8; border: 1px solid #9be3f7;
                border-radius: 9px; padding: 7px 18px; font-weight: 800; min-width: 70px;
            }
            QMessageBox QPushButton:hover { background: #9be3f7; }
            QMenu {
                color: #e6eef6; background: #101b26; border: 1px solid #31566a;
                border-radius: 10px; padding: 5px;
            }
            QMenu::item { padding: 7px 22px 7px 12px; border-radius: 7px; }
            QMenu::item:selected { background: #10293a; color: #9be3f7; }
        """)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # Lets KDE/Wayland match the window to org.nanoos.GameMode.desktop (name + icon).
    app.setDesktopFileName("org.nanoos.GameMode")
    from PySide6.QtGui import QIcon
    app.setWindowIcon(QIcon.fromTheme("nanoos-gamemode"))

    # Use a consistent Qt style so native desktop focus/selection
    # painting does not create square highlight artifacts.
    app.setStyle("Fusion")

    window = NanoOSGameMode()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
