#!/usr/bin/env python3
"""NanoOS shared application UI kit.

One window shell, one set of widgets and one stylesheet for every NanoOS
desktop app (Welcome, Control Center), so they look and behave the same:

  NanoShell      rounded shell, sidebar (brand, search, nav), page stack,
                 status bar, output panel and a pkexec process runner
  ActionCard     title + description + action button (optional usage bar)
  NanoButton     custom-painted nav / primary / secondary button
  SmoothScrollArea, FadingScrollBar   animated scrolling
"""

import shutil
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QElapsedTimer, QProcess, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QScrollBar,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)

BRANDING_DIR = Path("/usr/share/nanoos/branding")


class NanoButton(QWidget):
    clicked = Signal()

    def __init__(self, text, variant="nav"):
        super().__init__()

        self.text_value = text
        self.variant = variant
        self.hovered = False
        self.pressed = False
        self.active = False
        self.locked = False

        self.setFixedHeight(46)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

    def set_active(self, active):
        self.active = active
        self.update()

    def enterEvent(self, event):
        self.hovered = True
        self.update()

    def leaveEvent(self, event):
        self.hovered = False
        self.pressed = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.pressed = True
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_pressed = self.pressed
            self.pressed = False
            self.update()

            if was_pressed and self.rect().contains(
                event.position().toPoint()
            ):
                self.clicked.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)

        if not self.isEnabled():
            background = QColor("#111a23")
            foreground = QColor("#657583")
        elif self.variant == "primary":
            background = QColor("#9be3f7" if self.hovered else "#66c7e8")
            foreground = QColor("#04121b")
            if self.pressed:
                background = QColor("#2f8fb5")
        elif self.variant == "secondary":
            background = QColor("#253747" if self.hovered else "#1a2936")
            foreground = QColor("#e6eef6")
            if self.pressed:
                background = QColor("#13212c")
        else:
            background = QColor("#192c3a" if self.hovered else "#101b25")
            foreground = QColor("#e6eef6")
            if self.active:
                background = QColor("#153b4a" if self.hovered else "#112f3b")
            if self.pressed:
                background = QColor("#0c2631")

        path = QPainterPath()
        path.addRoundedRect(rect, 13, 13)
        painter.fillPath(path, background)

        if self.active and self.isEnabled():
            painter.setPen(QPen(QColor("#66c7e8"), 2))
            painter.drawLine(rect.left() + 1, rect.top() + 10, rect.left() + 1, rect.bottom() - 10)

        painter.setPen(foreground)
        painter.setFont(QFont("Inter", 10, QFont.Weight.DemiBold))
        if self.variant == "nav":
            text_rect = rect.adjusted(15, 0, -12, 0)
            flags = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        else:
            text_rect = rect.adjusted(8, 0, -8, 0)
            flags = Qt.AlignmentFlag.AlignCenter
        painter.drawText(text_rect, flags, self.text_value)
        painter.end()





class FadingScrollBar(QScrollBar):
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Vertical, parent)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.hovered = False
        self.dragging = False
        self.drag_offset = 0

        self.fade_value = 0.0
        self.fade_start = 0.0
        self.fade_target = 0.0
        self.fade_clock = QElapsedTimer()

        self.fade_timer = QTimer(self)
        self.fade_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.fade_timer.setInterval(4)
        self.fade_timer.timeout.connect(self.animate_fade)

        # Smooth sticky-arrow animation.
        self.arrow_position = 8.0
        self.arrow_start = 8.0
        self.arrow_target = 8.0
        self.arrow_clock = QElapsedTimer()

        self.arrow_timer = QTimer(self)
        self.arrow_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.arrow_timer.setInterval(4)
        self.arrow_timer.timeout.connect(self.animate_arrow)

        self.valueChanged.connect(self.update_arrow_target)
        self.rangeChanged.connect(
            lambda *_: self.update_arrow_target()
        )

        QTimer.singleShot(
            0,
            self.update_arrow_target,
        )

        self.setStyleSheet(
            "QScrollBar { background: transparent; border: none; }"
        )

    def sizeHint(self):
        size = super().sizeHint()
        size.setWidth(30)
        return size

    def enterEvent(self, event):
        self.hovered = True
        self.fade_to(1.0)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.dragging:
            self.hovered = False
            self.fade_to(0.0)

        self.update()
        super().leaveEvent(event)

    def fade_to(self, target):
        self.fade_start = self.fade_value
        self.fade_target = target
        self.fade_clock.restart()
        self.fade_timer.start()

    def animate_fade(self):
        progress = self.fade_clock.elapsed() / 180.0

        if progress >= 1.0:
            self.fade_value = self.fade_target
            self.fade_timer.stop()
            self.update()
            return

        eased = 1.0 - (1.0 - progress) ** 3

        self.fade_value = (
            self.fade_start
            + (self.fade_target - self.fade_start) * eased
        )

        self.update()

    def scrollbar_geometry(self):
        arrow_zone = 12
        gap = 4

        # Keep the pill below the REAL top arrow position.
        # This prevents the Dynamic Island pill from overlapping
        # the arrow when the first option is at the top of the page.
        arrow_y = int(self.top_arrow_position())

        top = max(
            arrow_zone + gap,
            arrow_y + 6,
        )

        bottom = self.height() - arrow_zone - gap

        track_height = max(
            1,
            bottom - top,
        )

        minimum = self.minimum()
        maximum = self.maximum()
        page = self.pageStep()

        if maximum <= minimum:
            thumb_height = track_height
            thumb_y = top
        else:
            total = (maximum - minimum) + page

            ratio = page / max(1, total)

            thumb_height = max(
                58,
                int(track_height * ratio),
            )

            thumb_height = min(
                thumb_height,
                track_height,
            )

            travel = max(
                0,
                track_height - thumb_height,
            )

            position = (
                self.value() - minimum
            ) / max(
                1,
                maximum - minimum,
            )

            thumb_y = top + int(
                travel * position
            )

        return (
            arrow_zone,
            top,
            bottom,
            track_height,
            thumb_y,
            thumb_height,
        )



    def top_arrow_target_position(self):
        ceiling = 8.0

        # Walk up the widget hierarchy until we find
        # the actual QScrollArea.
        scroll_area = self.parentWidget()

        while (
            scroll_area is not None
            and not isinstance(scroll_area, QScrollArea)
        ):
            scroll_area = scroll_area.parentWidget()

        if scroll_area is None:
            return ceiling

        content = scroll_area.widget()

        if content is None:
            return ceiling

        cards = [
            widget
            for widget in content.findChildren(QFrame)
            if widget.objectName() == "actionCard"
        ]

        if not cards:
            return ceiling

        # The card highest on screen is the first option.
        first_card = min(
            cards,
            key=lambda widget:
                widget.mapToGlobal(
                    widget.rect().topLeft()
                ).y()
        )

        first_global = first_card.mapToGlobal(
            first_card.rect().topLeft()
        )

        first_y = self.mapFromGlobal(
            first_global
        ).y()

        # Exact NanoOS rule:
        # top arrow = 13px above the first option.
        desired = first_y - 13.0

        # Never allow the arrow above the scrollbar ceiling.
        return max(
            ceiling,
            desired,
        )

    def update_arrow_target(self):
        target = self.top_arrow_target_position()

        if abs(target - self.arrow_target) < 0.01:
            return

        self.arrow_start = self.arrow_position
        self.arrow_target = target
        self.arrow_clock.restart()
        self.arrow_timer.start()

    def animate_arrow(self):
        elapsed = self.arrow_clock.elapsed()

        # Longer animation = softer transition.
        duration = 210.0

        progress = elapsed / duration

        if progress >= 1.0:
            self.arrow_position = self.arrow_target
            self.arrow_timer.stop()
            self.update()
            return

        # Smooth cubic ease-out.
        eased = 1.0 - (1.0 - progress) ** 3

        self.arrow_position = (
            self.arrow_start
            + (
                self.arrow_target
                - self.arrow_start
            ) * eased
        )

        self.update()

    def top_arrow_position(self):
        return self.arrow_position


    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        (
            arrow_zone,
            top,
            bottom,
            track_height,
            thumb_y,
            thumb_height,
        ) = self.scrollbar_geometry()

        # Dark -> NanoOS cyan fade.
        dark = QColor("#263744")
        blue = QColor("#66c7e8")

        r = int(
            dark.red()
            + (blue.red() - dark.red()) * self.fade_value
        )

        g = int(
            dark.green()
            + (blue.green() - dark.green()) * self.fade_value
        )

        b = int(
            dark.blue()
            + (blue.blue() - dark.blue()) * self.fade_value
        )

        # -------------------------------------------------
        # Dynamic Island-style pill.
        # -------------------------------------------------

        pill_width = 22
        pill_x = (self.width() - pill_width) // 2

        pill = QPainterPath()

        pill.addRoundedRect(
            pill_x,
            thumb_y,
            pill_width,
            thumb_height,
            pill_width / 2,
            pill_width / 2,
        )

        painter.fillPath(
            pill,
            QColor(r, g, b),
        )

        # -------------------------------------------------
        # Top + bottom chevrons.
        # -------------------------------------------------

        alpha = 235 if self.hovered or self.dragging else 150

        pen = QPen(
            QColor(120, 145, 160, alpha)
        )

        pen.setWidthF(2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

        painter.setPen(pen)

        center = self.width() / 2

        top_center = self.top_arrow_position()
        bottom_center = self.height() - arrow_zone / 2

        # Up chevron.
        painter.drawLine(
            int(center - 4),
            int(top_center + 1),
            int(center),
            int(top_center - 3),
        )

        painter.drawLine(
            int(center),
            int(top_center - 3),
            int(center + 4),
            int(top_center + 1),
        )

        # Down chevron.
        painter.drawLine(
            int(center - 4),
            int(bottom_center - 1),
            int(center),
            int(bottom_center + 3),
        )

        painter.drawLine(
            int(center),
            int(bottom_center + 3),
            int(center + 4),
            int(bottom_center - 1),
        )

        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        (
            arrow_zone,
            top,
            bottom,
            track_height,
            thumb_y,
            thumb_height,
        ) = self.scrollbar_geometry()

        y = int(event.position().y())

        # Top arrow.
        top_center = self.top_arrow_position()

        if abs(y - top_center) <= 10:
            self.setValue(
                self.value()
                - max(1, self.singleStep() * 3)
            )
            return

        # Bottom arrow.
        if y > self.height() - arrow_zone:
            self.setValue(
                self.value()
                + max(1, self.singleStep() * 3)
            )
            return

        # Thumb.
        if thumb_y <= y <= thumb_y + thumb_height:
            self.dragging = True
            self.drag_offset = y - thumb_y
            self.fade_to(1.0)
            self.update()
            return

        # Page click above/below thumb.
        if y < thumb_y:
            self.setValue(
                self.value() - self.pageStep()
            )
        elif y > thumb_y + thumb_height:
            self.setValue(
                self.value() + self.pageStep()
            )

    def mouseMoveEvent(self, event):
        if not self.dragging:
            return

        (
            arrow_zone,
            top,
            bottom,
            track_height,
            thumb_y,
            thumb_height,
        ) = self.scrollbar_geometry()

        travel = max(
            1,
            track_height - thumb_height,
        )

        position = (
            int(event.position().y())
            - self.drag_offset
            - top
        )

        position = max(
            0,
            min(travel, position),
        )

        ratio = position / travel

        new_value = (
            self.minimum()
            + int(
                ratio
                * (
                    self.maximum()
                    - self.minimum()
                )
            )
        )

        self.setValue(new_value)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.update()



class SmoothScrollArea(QScrollArea):
    def __init__(self):
        super().__init__()

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.scrollbar = FadingScrollBar(self)
        self.setVerticalScrollBar(self.scrollbar)

        self.animation = QTimer(self)
        self.animation.setTimerType(
            Qt.TimerType.PreciseTimer
        )
        self.animation.setInterval(4)

        self.clock = QElapsedTimer()

        self.scroll_start = 0
        self.scroll_target = 0
        self.scroll_duration = 75
        self.animation.timeout.connect(
            self.animate_scroll
        )

    def wheelEvent(self, event):
        # NANOOS_WELCOME_SCROLL_SPEED_V2
        pixel = event.pixelDelta().y()
        angle = event.angleDelta().y()

        # Trackpad stays controlled; mouse wheel gets a bigger boost.
        if pixel:
            delta = pixel
            multiplier = 2.0
        else:
            delta = angle
            multiplier = 4.6

        if delta == 0:
            event.ignore()
            return

        bar = self.verticalScrollBar()
        current = bar.value()

        # Accumulate new wheel inputs on the planned destination.
        # This prevents rapid wheel events from restarting a tiny scroll.
        if self.animation.isActive():
            base = self.scroll_target
        else:
            base = current

        self.scroll_start = current
        self.scroll_target = max(
            0,
            min(
                bar.maximum(),
                int(base - delta * multiplier),
            ),
        )

        if self.scroll_target == current:
            self.animation.stop()
            event.accept()
            return

        self.clock.restart()
        self.animation.start()
        event.accept()

    def animate_scroll(self):
        bar = self.verticalScrollBar()

        elapsed = self.clock.elapsed()
        progress = elapsed / self.scroll_duration

        if progress >= 1.0:
            bar.setValue(self.scroll_target)
            self.animation.stop()
            return

        eased = 1.0 - pow(1.0 - progress, 3)

        value = (
            self.scroll_start
            + (
                self.scroll_target
                - self.scroll_start
            ) * eased
        )

        bar.setValue(int(value))



class ActionCard(QFrame):
    """Title + description + action button. `fraction` adds a usage bar;
    `action_text=None` makes an information-only card; `enabled=False`
    shows a permanently disabled button (e.g. "Installed")."""

    def __init__(self, title, description, action_text=None, callback=None,
                 fraction=None, enabled=True):
        super().__init__()
        self.setObjectName("actionCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(86)
        self.title_text = str(title)
        self.description_text = str(description)
        self.search_blob = f"{self.title_text} {self.description_text}".casefold()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 16, 16)
        layout.setSpacing(18)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(6)

        title_label = QLabel(self.title_text)
        title_label.setObjectName("cardTitle")
        title_label.setWordWrap(True)
        title_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        desc_label = QLabel(self.description_text)
        desc_label.setObjectName("cardDescription")
        desc_label.setWordWrap(True)
        desc_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        body.addWidget(title_label)
        body.addWidget(desc_label)
        if fraction is not None:
            fraction = max(0.0, min(1.0, float(fraction)))
            bar = QProgressBar()
            bar.setObjectName(
                "usageBarBad" if fraction > 0.9 else
                "usageBarWarn" if fraction > 0.75 else "usageBar"
            )
            bar.setTextVisible(False)
            bar.setRange(0, 1000)
            bar.setValue(int(fraction * 1000))
            # A max width on the bar itself would cap (and centre) the whole
            # card body, so limit it with a stretch instead.
            bar_row = QHBoxLayout()
            bar_row.setContentsMargins(0, 0, 0, 0)
            bar_row.addWidget(bar, 3)
            bar_row.addStretch(2)
            body.addSpacing(2)
            body.addLayout(bar_row)
        layout.addLayout(body, 1)

        self.action_button = None
        if not action_text:
            return

        button = NanoButton(action_text, "primary")
        # Locked buttons stay disabled when the shell re-enables controls.
        button.locked = not enabled
        button.setEnabled(enabled)
        # NanoButton paints its own label, so size it to the text.
        text_width = QFontMetrics(QFont("Inter", 10, QFont.Weight.DemiBold)).horizontalAdvance(action_text)
        button.setFixedWidth(max(94, min(220, text_width + 34)))
        button.setFixedHeight(42)
        button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        button.setToolTip(action_text)
        if callback is not None:
            button.clicked.connect(callback)
        self.action_button = button
        layout.addWidget(button)


SHELL_QSS = """
    QWidget {
        background: transparent;
        color: #e6eef6;
        font-family: "Inter", "Noto Sans", sans-serif;
        font-size: 13px;
        selection-background-color: #2f8fb5;
        selection-color: #ffffff;
    }
    QWidget#nanoosWindow { background: #070b11; }
    QFrame#shell {
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 #101a25, stop:1 #0b131c);
        border: 1px solid #243543;
        border-radius: 26px;
    }
    QFrame#sidebar {
        background: #0a121b;
        border: 1px solid #1d2d3a;
        border-radius: 21px;
    }
    QLabel#brandMark {
        color: #04121b;
        background: #66c7e8;
        border: none;
        border-radius: 13px;
        font-size: 22px;
        font-weight: 900;
    }
    QLabel#brand { color: #e6eef6; font-size: 19px; font-weight: 800; }
    QLabel#brandSub { color: #7f93a7; font-size: 11px; }
    QLabel#pageTitle { color: #e6eef6; font-size: 29px; font-weight: 800; }
    QLabel#pageDescription { color: #b4c3d2; font-size: 14px; }
    QLabel#cardTitle { color: #e6eef6; font-size: 15px; font-weight: 700; }
    QLabel#cardDescription { color: #9aafbd; font-size: 12px; }
    QLabel#status {
        color: #9be3f7;
        background: #10293a;
        border: 1px solid #214b5b;
        border-radius: 11px;
        padding: 9px 12px;
        font-size: 11px;
        font-weight: 700;
    }
    QLabel#footer { color: #4e6276; font-size: 10px; }
    QLabel#sectionEyebrow { color: #66c7e8; font-size: 10px; font-weight: 800; }
    QLabel#groupLabel { color: #7f93a7; font-size: 10px; font-weight: 800; padding: 8px 2px 0 2px; }
    QFrame#actionCard {
        background: #101b26;
        border: 1px solid #223543;
        border-radius: 17px;
    }
    QFrame#actionCard:hover { background: #132230; border-color: #31566a; }
    QLineEdit#navSearch, QLineEdit#pageSearch {
        color: #e6eef6;
        background: #0b151f;
        border: 1px solid #263b4b;
        border-radius: 12px;
        padding: 10px 12px;
        min-height: 18px;
        selection-background-color: #2f8fb5;
    }
    QLineEdit#navSearch:focus, QLineEdit#pageSearch:focus {
        border: 1px solid #66c7e8;
        background: #0e1b27;
    }
    QScrollArea#navScroll { background: transparent; border: none; }
    QScrollArea#navScroll QWidget { background: transparent; }
    QScrollArea#navScroll QScrollBar:vertical { background: transparent; width: 7px; margin: 3px 0; }
    QScrollArea#navScroll QScrollBar::handle:vertical { background: #2b4657; border-radius: 3px; min-height: 24px; }
    QScrollArea#navScroll QScrollBar::handle:vertical:hover { background: #66c7e8; }
    QScrollArea#navScroll QScrollBar::add-line:vertical,
    QScrollArea#navScroll QScrollBar::sub-line:vertical { height: 0; }
    QPlainTextEdit#installLog {
        background: #08111a; color: #9be3f7;
        border: 1px solid #203441; border-radius: 14px;
        padding: 12px;
        font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
        font-size: 11px;
    }
    QProgressBar#installProgress {
        border: 1px solid #234253; border-radius: 4px;
        background: #0b1822; height: 7px; max-height: 7px;
    }
    QProgressBar#installProgress::chunk { background: #66c7e8; border-radius: 3px; }
    QProgressBar#usageBar, QProgressBar#usageBarWarn, QProgressBar#usageBarBad {
        border: none; border-radius: 3px; background: #0b1822;
        min-height: 6px; max-height: 6px;
    }
    QProgressBar#usageBar::chunk { background: #66c7e8; border-radius: 3px; }
    QProgressBar#usageBarWarn::chunk { background: #f2c66d; border-radius: 3px; }
    QProgressBar#usageBarBad::chunk { background: #ef6f7a; border-radius: 3px; }
    QPushButton#outputToggle {
        color: #b4c3d2; background: #142330;
        border: 1px solid #294251; border-radius: 10px;
        padding: 8px 12px; font-weight: 700;
    }
    QPushButton#outputToggle:hover { color: #ffffff; border-color: #66c7e8; background: #1a3040; }
    QLabel#emptyResults { color: #7f93a7; padding: 12px; }
    QDialog, QMessageBox { background: #0a121b; }
    QMessageBox QPushButton {
        color: #e6eef6; background: #142330; border: 1px solid #294251;
        border-radius: 9px; padding: 7px 16px; font-weight: 700;
    }
    QMessageBox QPushButton:hover { border-color: #66c7e8; }
    QToolTip { color: #e6eef6; background: #142331; border: 1px solid #315063; padding: 6px; }
"""


class NanoShell(QWidget):
    """The shared NanoOS application window.

    Subclasses set the class attributes, list their pages in MENU and
    build them in build_pages() with page_header()/add_page().
    """

    APP_NAME = "NanoOS"
    BRAND_SUB = "NANOOS"          # small caps line under the brand
    EYEBROW = "NANOOS"            # breadcrumb above each page title
    FOOTER = "NANOOS"
    MENU = []
    START_PAGE = None
    LOG_PLACEHOLDER = "Command output appears here when you open the output panel."

    def __init__(self):
        super().__init__()
        self.setObjectName("nanoosWindow")
        self.process = None
        self.current_task = None
        self.pages = {}
        self.nav_buttons = {}
        self.setWindowTitle(self.APP_NAME)
        self.setMinimumSize(780, 520)
        self.resize(1260, 820)
        self.setStyleSheet(SHELL_QSS)
        self.build_ui()
        self.build_pages()
        self.show_page(self.START_PAGE or (self.MENU[0] if self.MENU else ""))

    # ------------------------------------------------------------ hooks
    def build_pages(self):
        raise NotImplementedError

    def on_task_finished(self, title, success):
        """Called after a run_command() task ends."""

    # ------------------------------------------------------------ layout
    def build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("shell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(12, 12, 12, 12)
        shell_layout.setSpacing(12)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(222)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(13, 15, 13, 12)
        side.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(11)
        brand_mark = QLabel()
        brand_mark.setFixedSize(42, 42)
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark_file = BRANDING_DIR / "nanoos-mark-128.png"
        if mark_file.is_file():
            pixmap = QPixmap(str(mark_file))
            ratio = self.devicePixelRatioF()
            pixmap = pixmap.scaled(
                int(42 * ratio), int(42 * ratio),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pixmap.setDevicePixelRatio(ratio)
            brand_mark.setPixmap(pixmap)
        else:
            brand_mark.setText("N")
            brand_mark.setObjectName("brandMark")
        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand = QLabel("NanoOS")
        brand.setObjectName("brand")
        brand_sub = QLabel(self.BRAND_SUB)
        brand_sub.setObjectName("brandSub")
        brand_text.addWidget(brand)
        brand_text.addWidget(brand_sub)
        brand_row.addWidget(brand_mark)
        brand_row.addLayout(brand_text, 1)
        side.addLayout(brand_row)
        side.addSpacing(10)

        self.navigation_search = QLineEdit()
        self.navigation_search.setObjectName("navSearch")
        self.navigation_search.setPlaceholderText("Find a section…")
        self.navigation_search.setClearButtonEnabled(True)
        self.navigation_search.textChanged.connect(self.filter_navigation)
        side.addWidget(self.navigation_search)

        self.nav_scroll = QScrollArea()
        self.nav_scroll.setObjectName("navScroll")
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_content = QWidget()
        nav_layout = QVBoxLayout(nav_content)
        nav_layout.setContentsMargins(0, 5, 4, 5)
        nav_layout.setSpacing(5)
        for item in self.MENU:
            button = NanoButton(item)
            button.setToolTip(item)
            button.setAccessibleName(f"Open {item}")
            button.clicked.connect(lambda item=item: self.show_page(item))
            self.nav_buttons[item] = button
            nav_layout.addWidget(button)
        nav_layout.addStretch(1)
        self.nav_scroll.setWidget(nav_content)
        side.addWidget(self.nav_scroll, 1)

        footer_line = QFrame()
        footer_line.setFixedHeight(1)
        footer_line.setStyleSheet("background:#1d2c38;border:none;")
        side.addWidget(footer_line)
        self.footer_label = QLabel(self.FOOTER)
        self.footer_label.setObjectName("footer")
        side.addWidget(self.footer_label)
        shell_layout.addWidget(self.sidebar)

        content = QFrame()
        content.setObjectName("mainContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(10)
        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")
        content_layout.addWidget(self.stack, 1)

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.status = QLabel("Ready")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)
        status_row.addWidget(self.status, 1)
        self.output_toggle_button = QPushButton("Show Output")
        self.output_toggle_button.setObjectName("outputToggle")
        self.output_toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.output_toggle_button.clicked.connect(lambda: self.toggle_output())
        status_row.addWidget(self.output_toggle_button)
        content_layout.addLayout(status_row)

        self.progress = QProgressBar()
        self.progress.setObjectName("installProgress")
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        content_layout.addWidget(self.progress)

        self.log = QPlainTextEdit()
        self.log.setObjectName("installLog")
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(155)
        self.log.setMaximumBlockCount(3000)
        self.log.setPlaceholderText(self.LOG_PLACEHOLDER)
        self.log.hide()
        content_layout.addWidget(self.log)
        shell_layout.addWidget(content, 1)
        outer.addWidget(shell, 1)

    def resizeEvent(self, event):
        width = self.width()
        if hasattr(self, "sidebar"):
            target_width = 184 if width < 1000 else 222
            if self.sidebar.width() != target_width:
                self.sidebar.setFixedWidth(target_width)
        content = self.findChild(QFrame, "mainContent")
        if content is not None and content.layout() is not None:
            margin = 11 if width < 1000 else 16
            content.layout().setContentsMargins(margin, 10, margin, 10)
        super().resizeEvent(event)

    # ------------------------------------------------------------ pages
    def page_header(self, title, description, searchable=True):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 6)
        layout.setSpacing(10)

        eyebrow = QLabel(self.EYEBROW)
        eyebrow.setObjectName("sectionEyebrow")
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        title_label.setWordWrap(True)
        desc = QLabel(description)
        desc.setObjectName("pageDescription")
        desc.setWordWrap(True)
        desc.setMaximumWidth(920)

        layout.addWidget(eyebrow)
        layout.addWidget(title_label)
        layout.addWidget(desc)
        layout.addSpacing(2)

        if searchable:
            search = QLineEdit()
            search.setObjectName("pageSearch")
            search.setPlaceholderText(f"Search {title.lower()}…")
            search.setClearButtonEnabled(True)
            search.setMaximumWidth(640)
            page._nanoos_search_field = search
            layout.addWidget(search)
            empty_label = QLabel("No matching options. Try a different search.")
            empty_label.setObjectName("emptyResults")
            empty_label.setWordWrap(True)
            empty_label.hide()
            page._nanoos_empty_label = empty_label
            layout.addWidget(empty_label)
            layout.addSpacing(2)
        return page, layout

    @staticmethod
    def group_label(text):
        label = QLabel(text.upper())
        label.setObjectName("groupLabel")
        return label

    def add_page(self, name, page):
        """Add a page, or replace an existing page of the same name."""
        previous = self.pages.get(name)
        was_current = previous is not None and self.stack.currentWidget() is previous
        query = ""
        if previous is not None:
            old_search = getattr(previous.widget(), "_nanoos_search_field", None)
            if old_search is not None:
                query = old_search.text()

        scroll = SmoothScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidget(page)
        self.pages[name] = scroll
        if previous is not None:
            index = self.stack.indexOf(previous)
            self.stack.insertWidget(index, scroll)
            self.stack.removeWidget(previous)
            previous.deleteLater()
        else:
            self.stack.addWidget(scroll)
        if was_current:
            self.stack.setCurrentWidget(scroll)

        search = getattr(page, "_nanoos_search_field", None)
        if search is not None:
            search.textChanged.connect(lambda value, page=page: self.filter_page(page, value))
            if query:
                search.setText(query)
        self.filter_page(page, query)

    def show_page(self, name):
        target = self.pages.get(name)
        if target is None:
            return
        self.stack.setCurrentWidget(target)
        for item, button in self.nav_buttons.items():
            button.set_active(item == name)
        if not self.task_running():
            self.status.setText(f"{name}  ·  Ready")

    def current_page_name(self):
        current = self.stack.currentWidget()
        for name, widget in self.pages.items():
            if widget is current:
                return name
        return ""

    def filter_navigation(self, query):
        query = str(query).strip().casefold()
        for name, button in self.nav_buttons.items():
            button.setVisible(not query or query in name.casefold())

    def filter_page(self, page, query):
        query = str(query).strip().casefold()
        cards = page.findChildren(ActionCard)
        visible_count = 0
        for card in cards:
            matched = not query or query in getattr(card, "search_blob", "")
            card.setVisible(matched)
            visible_count += int(matched)
        empty_label = getattr(page, "_nanoos_empty_label", None)
        if empty_label is not None:
            empty_label.setVisible(bool(cards) and visible_count == 0)

    # ------------------------------------------------------------ output
    def toggle_output(self, force_visible=None):
        visible = self.log.isVisible()
        target_visible = (not visible) if force_visible is None else bool(force_visible)
        self.log.setVisible(target_visible)
        self.output_toggle_button.setText("Hide Output" if target_visible else "Show Output")

    def copy_value(self, label, value):
        QApplication.clipboard().setText(str(value))
        self.status.setText(f"Copied {label} to the clipboard.")

    # ------------------------------------------------------------ tasks
    def task_running(self):
        return bool(self.process and self.process.state() != QProcess.ProcessState.NotRunning)

    def set_action_controls_enabled(self, enabled):
        for button in self.findChildren(NanoButton):
            if button.variant == "primary" and not getattr(button, "locked", False):
                button.setEnabled(bool(enabled))
                button.update()

    def run_command(self, command, args, title, display_command, verb="Running"):
        """Run one command with live output in the panel. Returns False if busy."""
        if self.task_running():
            self.status.setText("Another operation is already running.")
            return False
        self.current_task = title
        self.log.clear()
        self.log.appendPlainText(f"$ {display_command}\n")
        self.status.setText(f"{verb} {title}… Authorize the operation if prompted.")
        self.toggle_output(True)
        self.progress.setRange(0, 0)
        self.progress.show()
        self.set_action_controls_enabled(False)

        process = QProcess(self)
        self.process = process
        process.setProgram(command)
        process.setArguments([str(arg) for arg in args])
        process.readyReadStandardOutput.connect(self._read_output)
        process.readyReadStandardError.connect(self._read_error)
        process.errorOccurred.connect(self._task_error)
        process.finished.connect(self._task_finished)
        process.start()
        return True

    def run_privileged(self, args, title, verb="Running"):
        """Run `args` as root through pkexec (polkit password prompt)."""
        pkexec = shutil.which("pkexec")
        if not pkexec:
            self.status.setText("Cancelled: pkexec was not found.")
            self.log.appendPlainText("[error] pkexec (polkit) is required for administrator actions.")
            self.toggle_output(True)
            return False
        display = "pkexec " + " ".join(str(arg) for arg in args)
        return self.run_command(pkexec, list(args), title, display, verb)

    def _read_output(self):
        if self.process is None:
            return
        data = self.process.readAllStandardOutput().data()
        if data:
            self.log.appendPlainText(data.decode(errors="replace").rstrip())

    def _read_error(self):
        if self.process is None:
            return
        data = self.process.readAllStandardError().data()
        if data:
            self.log.appendPlainText(data.decode(errors="replace").rstrip())

    def _task_error(self, error):
        process = self.process
        if process is None:
            return
        detail = process.errorString() or str(error)
        self.log.appendPlainText(f"\n[QProcess error] {detail}")
        if error == QProcess.ProcessError.FailedToStart:
            title = self.current_task or "Operation"
            self.status.setText(f"{title} could not be started: {detail}")
            self.process = None
            self.current_task = None
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.progress.hide()
            self.set_action_controls_enabled(True)
            self.toggle_output(True)

    def _task_finished(self, exit_code, exit_status):
        self._read_output()
        self._read_error()
        title = self.current_task or "Operation"
        success = exit_status == QProcess.ExitStatus.NormalExit and exit_code == 0
        if success:
            self.status.setText(f"{title} completed successfully.")
            self.log.appendPlainText("\n[NanoOS] Process completed with exit code 0.")
        elif exit_code in (126, 127):
            self.status.setText(f"{title} was not authorized; nothing was changed.")
            self.log.appendPlainText("\n[NanoOS] Administrator authorization was cancelled or unavailable.")
        else:
            self.status.setText(f"{title} failed · exit code {exit_code}.")
            self.log.appendPlainText(f"\n[NanoOS] Process ended with exit code {exit_code}.")
            output = self.log.toPlainText()
            if "failed retrieving file" in output or "404" in output:
                self.log.appendPlainText(
                    "[NanoOS] Package lists look out of date. Update NanoOS first "
                    "(Control Center → Updates), then try again."
                )
        self.process = None
        self.current_task = None
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        self.set_action_controls_enabled(True)
        self.toggle_output(True)
        self.on_task_finished(title, success)

    def closeEvent(self, event):
        # Closing would destroy the QProcess and kill a package transaction
        # halfway through, which can leave pacman's database locked.
        if self.task_running():
            answer = QMessageBox.warning(
                self,
                "Operation in progress",
                f"{self.current_task or 'An operation'} is still running. Closing now "
                "can leave the package database locked.\n\nWait for it to finish?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        super().closeEvent(event)
