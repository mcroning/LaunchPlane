"""Interactive launch-plane canvas for beam placement and manipulation."""

from __future__ import annotations

import math
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from launchplane.model import BeamDefinition, BeamStackDefinition, LaunchPlaneDefinition


class BeamItem(QGraphicsObject):
    """Movable graphics item representing one beam."""

    moved = Signal(int, float, float)
    selected = Signal(int)

    def __init__(
        self,
        index: int,
        beam: BeamDefinition,
        *,
        tilt_arrow_scale: float = 500.0,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self.index = int(index)
        self.beam = beam
        self.tilt_arrow_scale = float(tilt_arrow_scale)
        self._hovered = False

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        self._label = QGraphicsSimpleTextItem(self)
        self._label.setBrush(QBrush(QColor(235, 235, 235)))
        self._label.setFont(QFont("Sans Serif", 9))
        self._label.setPos(7.0, -18.0)
        self.refresh(beam)

    def refresh(self, beam: BeamDefinition) -> None:
        self.prepareGeometryChange()
        self.beam = beam
        self._label.setText(f"{self.index + 1}: {beam.name}")
        self.setPos(beam.y_um, -beam.x_um)
        self.update()

    def boundingRect(self) -> QRectF:
        waist_y = max(6.0, float(self.beam.waist_y_um))
        waist_x = max(6.0, float(self.beam.waist_x_um))
        arrow_dx = self.beam.tilt_y_rad_per_um * self.tilt_arrow_scale
        arrow_dy = -self.beam.tilt_x_rad_per_um * self.tilt_arrow_scale
        left = min(-waist_y - 4.0, arrow_dx - 6.0)
        right = max(waist_y + 4.0, arrow_dx + 6.0, 80.0)
        top = min(-waist_x - 22.0, arrow_dy - 6.0)
        bottom = max(waist_x + 4.0, arrow_dy + 6.0)
        return QRectF(left, top, right - left, bottom - top)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(
            QRectF(
                -self.beam.waist_y_um,
                -self.beam.waist_x_um,
                2.0 * self.beam.waist_y_um,
                2.0 * self.beam.waist_x_um,
            )
        )
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget

        color = QColor(90, 180, 255)
        if self.isSelected():
            color = QColor(255, 190, 70)
        elif self._hovered:
            color = QColor(130, 210, 255)
        if not self.beam.enabled:
            color = QColor(120, 120, 120)

        waist_rect = QRectF(
            -self.beam.waist_y_um,
            -self.beam.waist_x_um,
            2.0 * self.beam.waist_y_um,
            2.0 * self.beam.waist_x_um,
        )

        fill = QColor(color)
        fill.setAlpha(45 if self.beam.enabled else 20)
        painter.setPen(QPen(color, 1.6))
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(waist_rect)

        painter.setPen(QPen(color, 2.0))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(0.0, 0.0), 2.8, 2.8)

        painter.setPen(QPen(color, 1.0))
        painter.drawLine(QPointF(-4.0, 0.0), QPointF(4.0, 0.0))
        painter.drawLine(QPointF(0.0, -4.0), QPointF(0.0, 4.0))
        self._paint_tilt_arrow(painter)

        painter.setPen(QPen(QColor(175, 175, 175), 1.0))
        painter.drawText(QPointF(7.0, 16.0), self.beam.coherence_group)

    def _paint_tilt_arrow(self, painter: QPainter) -> None:
        dx = self.beam.tilt_y_rad_per_um * self.tilt_arrow_scale
        dy = -self.beam.tilt_x_rad_per_um * self.tilt_arrow_scale
        length = math.hypot(dx, dy)
        if length < 0.2:
            return

        end = QPointF(dx, dy)
        arrow_color = QColor(255, 110, 110)
        painter.setPen(QPen(arrow_color, 1.8))
        painter.drawLine(QPointF(0.0, 0.0), end)

        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        head = 4.0
        p1 = QPointF(dx - head * ux + 0.55 * head * px, dy - head * uy + 0.55 * head * py)
        p2 = QPointF(dx - head * ux - 0.55 * head * px, dy - head * uy - 0.55 * head * py)
        path = QPainterPath(end)
        path.lineTo(p1)
        path.lineTo(p2)
        path.closeSubpath()
        painter.setBrush(QBrush(arrow_color))
        painter.drawPath(path)

    def hoverEnterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.index)
        super().mousePressEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene() is not None:
            scene = self.scene()
            if isinstance(scene, LaunchPlaneScene):
                position = value
                y_um = min(max(float(position.x()), scene.y_min), scene.y_max)
                x_um = min(max(-float(position.y()), scene.x_min), scene.x_max)
                return QPointF(y_um, -x_um)

        if change == QGraphicsItem.ItemPositionHasChanged:
            position = self.pos()
            self.moved.emit(self.index, -float(position.y()), float(position.x()))

        if change == QGraphicsItem.ItemSelectedHasChanged and bool(value):
            self.selected.emit(self.index)

        return super().itemChange(change, value)


class LaunchPlaneScene(QGraphicsScene):
    """Graphics scene containing the aperture and beam items."""

    addBeamRequested = Signal(float, float)
    beamMoved = Signal(int, float, float)
    beamSelected = Signal(int)

    def __init__(self, definition: LaunchPlaneDefinition | None = None, parent=None):
        super().__init__(parent)
        self.definition = definition or LaunchPlaneDefinition()
        self.definition.validate()
        self.add_mode = False
        self.beam_items: list[BeamItem] = []
        self.setBackgroundBrush(QBrush(QColor(28, 31, 36)))
        self._draw_static_scene()

    @property
    def x_min(self) -> float:
        return -0.5 * self.definition.x_aperture_um

    @property
    def x_max(self) -> float:
        return 0.5 * self.definition.x_aperture_um

    @property
    def y_min(self) -> float:
        return -0.5 * self.definition.y_aperture_um

    @property
    def y_max(self) -> float:
        return 0.5 * self.definition.y_aperture_um

    def set_definition(self, definition: LaunchPlaneDefinition) -> None:
        definition.validate()
        self.definition = definition
        stack = BeamStackDefinition(beams=tuple(item.beam for item in self.beam_items))
        self.set_stack(stack)

    def set_stack(self, stack: BeamStackDefinition) -> None:
        stack.validate()
        self._draw_static_scene()
        for index, beam in enumerate(stack.beams):
            item = BeamItem(index, beam)
            item.moved.connect(self.beamMoved)
            item.selected.connect(self.beamSelected)
            self.addItem(item)
            self.beam_items.append(item)

    def stack(self) -> BeamStackDefinition:
        beams: list[BeamDefinition] = []
        for item in self.beam_items:
            position = item.pos()
            beams.append(replace(item.beam, x_um=-float(position.y()), y_um=float(position.x())))
        return BeamStackDefinition(beams=tuple(beams))

    def set_selected_index(self, index: int | None) -> None:
        for item_index, item in enumerate(self.beam_items):
            item.setSelected(item_index == index)

    def arm_add_mode(self) -> None:
        self.add_mode = True

    def cancel_add_mode(self) -> None:
        self.add_mode = False

    def _draw_static_scene(self) -> None:
        self.clear()
        self.beam_items = []

        x_margin = 0.10 * self.definition.x_aperture_um
        y_margin = 0.10 * self.definition.y_aperture_um

        self.setSceneRect(
            QRectF(
                self.y_min - y_margin,
                -self.x_max - x_margin,
                self.definition.y_aperture_um + 2.0 * y_margin,
                self.definition.x_aperture_um + 2.0 * x_margin,
            )
        )

        aperture_rect = QRectF(
            self.y_min,
            -self.x_max,
            self.definition.y_aperture_um,
            self.definition.x_aperture_um,
        )
        self.addRect(aperture_rect, QPen(QColor(210, 215, 220), 1.6), QBrush(QColor(38, 42, 48)))

        axis_pen = QPen(QColor(105, 110, 118), 1.0, Qt.DashLine)
        self.addLine(self.y_min, 0.0, self.y_max, 0.0, axis_pen)
        self.addLine(0.0, -self.x_max, 0.0, -self.x_min, axis_pen)

        title = self.addSimpleText("Launch Plane  (z = 0, viewing along +z)")
        title.setBrush(QBrush(QColor(225, 225, 225)))
        title.setFont(QFont("Sans Serif", 10, QFont.Bold))
        title.setPos(self.y_min, -self.x_max - 0.75 * x_margin)

        x_label = self.addSimpleText("Cell thickness  x  ↑")
        x_label.setBrush(QBrush(QColor(205, 205, 205)))
        x_label.setRotation(-90.0)
        x_label.setPos(self.y_min - 0.75 * y_margin, 10.0)

        y_label = self.addSimpleText("Transverse  y  →")
        y_label.setBrush(QBrush(QColor(205, 205, 205)))
        y_label.setPos(-24.0, self.x_max + 0.35 * x_margin)

        bounds = self.addSimpleText(
            f"x: {self.x_min:g} … {self.x_max:g} µm    "
            f"y: {self.y_min:g} … {self.y_max:g} µm"
        )
        bounds.setBrush(QBrush(QColor(150, 155, 162)))
        bounds.setPos(self.y_min, self.x_max + 0.62 * x_margin)

    def mousePressEvent(self, event) -> None:
        if self.add_mode and event.button() == Qt.LeftButton:
            position = event.scenePos()
            inside = (
                self.y_min <= position.x() <= self.y_max
                and -self.x_max <= position.y() <= -self.x_min
            )
            if inside:
                self.addBeamRequested.emit(-float(position.y()), float(position.x()))
                self.add_mode = False
                event.accept()
                return
        super().mousePressEvent(event)


class LaunchPlaneView(QGraphicsView):
    """View with antialiasing, wheel zoom, and middle-button panning."""

    def __init__(self, scene: LaunchPlaneScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._panning = False
        self._pan_start = None

    def fit_aperture(self) -> None:
        scene = self.scene()
        if scene is not None:
            self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self.hasFocus():
            self.fit_aperture()

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self._pan_start = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


__all__ = ["BeamItem", "LaunchPlaneScene", "LaunchPlaneView"]
