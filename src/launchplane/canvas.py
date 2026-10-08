"""Interactive launch-plane canvas for beam placement and manipulation."""

from __future__ import annotations

import math
from dataclasses import replace

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QPolygonF,
    QTransform,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from launchplane.model import (
    BeamDefinition,
    BeamStackDefinition,
    LaunchPlaneDefinition,
)


def _label_font(point_size: int, *, bold: bool = False) -> QFont:
    """Inherit Qt's application/platform font without requesting a family alias."""
    font = QFont()
    font.setPointSize(point_size)
    font.setWeight(QFont.Bold if bold else QFont.Normal)
    return font


class BeamItem(QGraphicsObject):
    """Movable graphics item representing one beam."""

    moved = Signal(int, float, float)
    changed = Signal(int, object)
    selected = Signal(int)

    def __init__(
        self,
        index: int,
        beam: BeamDefinition,
        *,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self.index = int(index)
        self.beam = beam
        self._resolved_tip: QPointF | None = None
        self._hovered = False
        self._refreshing = False

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        # Top-level handles share global z bands: every arrow beats every center.
        # They are scene-owned, not children of differently stacked beam items.
        self._ray_head = RayHandleItem(self, arrow=True)
        self._center_marker = RayHandleItem(self, arrow=False)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self._label = QGraphicsSimpleTextItem(self)
        self._label.setBrush(QBrush(QColor(235, 235, 235)))
        self._label.setFont(_label_font(12, bold=True))
        self._label.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self._label.setAcceptedMouseButtons(Qt.NoButton)
        self._label.setPos(6.0, -16.0)
        self.refresh(beam)

    def refresh(self, beam: BeamDefinition) -> None:
        self.prepareGeometryChange()
        self.beam = beam
        self._label.setText(str(self.index + 1))
        self._refreshing = True
        try:
            self.setPos(beam.x_um, -beam.y_um)
        finally:
            self._refreshing = False
        self._center_marker.setPos(self.pos())
        self.update()

    def set_resolved_exit(self, exit_xy: tuple[float, float] | None) -> None:
        """Host-owned physical endpoint; never infer a ray from external intent."""
        self.prepareGeometryChange()
        self._resolved_tip = (None if exit_xy is None else
                              QPointF(exit_xy[0] - self.beam.x_um,
                                      -(exit_xy[1] - self.beam.y_um)))
        tip = self.tilt_tip_offset()
        self._ray_head.setPos(self.pos() + tip)
        self._ray_head.setRotation(math.degrees(math.atan2(tip.y(), tip.x())))
        self._ray_head.setVisible(self.beam.enabled and self._resolved_tip is not None)
        self.setToolTip("Internal ray unavailable: requires a compatible host resolver."
                        if exit_xy is None else "Resolved internal entrance-to-exit ray")
        self.update()

    def tilt_tip_offset(self) -> QPointF:
        """Physical scene displacement in µm (Qt y down), not display pixels."""
        return QPointF() if self._resolved_tip is None else QPointF(self._resolved_tip)

    def boundingRect(self) -> QRectF:
        tip = self.tilt_tip_offset()
        return QRectF(QPointF(min(-7, tip.x()-7), min(-7, tip.y()-7)),
                      QPointF(max(7, tip.x()+7), max(7, tip.y()+7)))

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        # Shafts never intercept either handle.
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget
        # Host-resolved geometry only; no inferred direction glyph.
        self._paint_tilt_arrow(painter)

    def _paint_tilt_arrow(self, painter: QPainter) -> None:
        tip = self.tilt_tip_offset()
        dx = tip.x()
        dy = tip.y()
        length = math.hypot(dx, dy)
        if self._resolved_tip is None or not self.beam.enabled or length == 0:
            return

        end = QPointF(dx, dy)
        arrow_color = QColor(255, 110, 110) if self.beam.enabled else QColor(120, 120, 120)
        arrow_pen = QPen(arrow_color, 1.8)
        arrow_pen.setCosmetic(True)
        painter.setPen(arrow_pen)
        painter.drawLine(QPointF(0.0, 0.0), end)

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
        if (change == QGraphicsItem.ItemPositionChange
                and self.scene() is not None and not self._refreshing):
            scene = self.scene()
            if isinstance(scene, LaunchPlaneScene):
                position = value
                x_um = min(max(float(position.x()), scene.x_min), scene.x_max)
                y_um = min(max(-float(position.y()), scene.y_min), scene.y_max)
                return QPointF(x_um, -y_um)

        if change == QGraphicsItem.ItemPositionHasChanged:
            position = self.pos()
            x_um = float(position.x())
            y_um = -float(position.y())
            self.beam = replace(self.beam, x_um=x_um, y_um=y_um)
            self._center_marker.setPos(position)
            self._ray_head.setPos(position + self.tilt_tip_offset())
            if not self._refreshing:
                self.moved.emit(self.index, x_um, y_um)

        if change == QGraphicsItem.ItemSelectedHasChanged:
            selected = bool(value)
            self._center_marker.update()
            self._ray_head.update()
            if selected:
                self.selected.emit(self.index)

        return super().itemChange(change, value)


class RayHandleItem(QGraphicsItem):
    """Scene-owned device-sized handle; all physical updates go through its beam."""

    def __init__(self, beam_item: BeamItem, *, arrow: bool):
        super().__init__()
        self.beam_item = beam_item
        self.arrow = arrow
        self.setFlags(QGraphicsItem.ItemIgnoresTransformations | QGraphicsItem.ItemIsFocusable)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setZValue(30 if arrow else 20)
        self.setCursor(Qt.OpenHandCursor)
        self._press_offset = QPointF()
        if arrow:
            self.hide()
        self.setToolTip("Drag exit to set direction; arrows nudge, Shift ×10" if arrow else
                        "Drag entrance center; arrows nudge, Shift ×10")

    def boundingRect(self) -> QRectF:
        return QRectF(-18, -10, 28, 20) if self.arrow else QRectF(-8, -8, 16, 16)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if self.arrow:
            path.addRect(self.boundingRect())
        else:
            path.addEllipse(self.boundingRect())
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget
        beam = self.beam_item
        color = QColor(255, 190, 70) if beam.isSelected() else QColor(90, 180, 255)
        if not beam.beam.enabled:
            color = QColor(120, 120, 120)
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(QBrush(color))
        if self.arrow:
            # Tip stays exactly at the physical exit, even for a zero-length ray.
            painter.drawPolygon(QPolygonF([QPointF(), QPointF(-15, 7), QPointF(-11, 0), QPointF(-15, -7)]))
        else:
            painter.drawEllipse(QPointF(), 2.5, 2.5)
            painter.drawLine(QPointF(-5, 0), QPointF(5, 0))
            painter.drawLine(QPointF(0, -5), QPointF(0, 5))
        if self.hasFocus():
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(), 7, 7)

    def mousePressEvent(self, event) -> None:
        self.scene().set_selected_index(self.beam_item.index)
        self.setFocus(Qt.MouseFocusReason)
        self._press_offset = self.scenePos() - event.scenePos()
        self.setCursor(Qt.ClosedHandCursor)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        self._move_to(event.scenePos() + self._press_offset)
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.OpenHandCursor)
        event.accept()

    def _move_to(self, position: QPointF) -> None:
        if self.arrow:
            self.scene().exitRequested.emit(self.beam_item.index, position.x(), -position.y())
        else:
            self.beam_item.setPos(position)

    def keyPressEvent(self, event) -> None:
        directions = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0),
                      Qt.Key_Up: (0, -1), Qt.Key_Down: (0, 1)}
        if event.key() not in directions or not self.scene().views():
            super().keyPressEvent(event)
            return
        dx, dy = directions[event.key()]
        step = 10 if event.modifiers() & Qt.ShiftModifier else 1
        inverse, valid = self.scene().views()[0].viewportTransform().inverted()
        if valid:
            delta = inverse.map(QPointF(step*dx, step*dy)) - inverse.map(QPointF())
            self._move_to(self.scenePos() + delta)
        event.accept()


class LaunchPlaneScene(QGraphicsScene):
    """Graphics scene containing the aperture and beam items."""

    sceneAboutToReset = Signal()
    addBeamRequested = Signal(float, float)
    beamMoved = Signal(int, float, float)
    beamChanged = Signal(int, object)
    beamSelected = Signal(int)
    exitRequested = Signal(int, float, float)

    def __init__(
        self,
        definition: LaunchPlaneDefinition | None = None,
        parent=None,
    ):
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
            item = BeamItem(
                index,
                beam,
            )
            item.moved.connect(self.beamMoved)
            item.changed.connect(self.beamChanged)
            item.selected.connect(self.beamSelected)
            self.addItem(item)
            self.addItem(item._center_marker)
            self.addItem(item._ray_head)
            self.beam_items.append(item)

    def stack(self) -> BeamStackDefinition:
        beams: list[BeamDefinition] = []
        for item in self.beam_items:
            position = item.pos()
            beams.append(replace(item.beam, x_um=float(position.x()), y_um=-float(position.y())))
        return BeamStackDefinition(beams=tuple(beams))

    def set_selected_index(self, index: int | None) -> None:
        for item_index, item in enumerate(self.beam_items):
            item.setSelected(item_index == index)

    def arm_add_mode(self) -> None:
        self.add_mode = True

    def cancel_add_mode(self) -> None:
        self.add_mode = False

    def _draw_static_scene(self) -> None:
        self.sceneAboutToReset.emit()
        self.clear()
        self.beam_items = []

        y_margin = max(18.0, 0.20 * self.definition.y_aperture_um)
        x_margin = max(18.0, 0.18 * self.definition.x_aperture_um)

        self.setSceneRect(
            QRectF(
                self.x_min - x_margin,
                -self.y_max - y_margin,
                self.definition.x_aperture_um + 2.0 * x_margin,
                self.definition.y_aperture_um + 2.0 * y_margin,
            )
        )

        aperture_rect = QRectF(
            self.x_min,
            -self.y_max,
            self.definition.x_aperture_um,
            self.definition.y_aperture_um,
        )
        aperture_pen = QPen(QColor(225, 228, 232), 2.0)
        aperture_pen.setCosmetic(True)
        aperture_gradient = QRadialGradient(
            QPointF(0.0, 0.0),
            0.75 * max(
                self.definition.y_aperture_um,
                self.definition.x_aperture_um,
            ),
        )
        aperture_gradient.setColorAt(0.0, QColor(43, 49, 57))
        aperture_gradient.setColorAt(1.0, QColor(32, 36, 42))
        self.addRect(aperture_rect, aperture_pen, QBrush(aperture_gradient))

        axis_pen = QPen(QColor(112, 118, 126), 1.2, Qt.DashLine)
        axis_pen.setCosmetic(True)
        self.addLine(self.x_min, 0.0, self.x_max, 0.0, axis_pen)
        self.addLine(0.0, -self.y_max, 0.0, -self.y_min, axis_pen)

        self._draw_scientific_axes(y_margin, x_margin)

    @staticmethod
    def _nice_tick_step(span: float, target_intervals: int = 5) -> float:
        """Return a readable 1/2/2.5/5 × 10ⁿ tick interval."""

        rough_step = span / target_intervals
        magnitude = 10.0 ** math.floor(math.log10(rough_step))
        normalized = rough_step / magnitude
        for candidate in (1.0, 2.0, 2.5, 5.0, 10.0):
            if normalized <= candidate:
                return candidate * magnitude
        return 10.0 * magnitude

    @staticmethod
    def _tick_values(minimum: float, maximum: float, step: float) -> list[float]:
        first = math.ceil(minimum / step - 1.0e-10) * step
        count = max(0, math.floor((maximum - first) / step + 1.0e-10) + 1)
        return [first + index * step for index in range(count)]

    def _add_axis_text(
        self,
        text: str,
        position: QPointF,
        *,
        point_size: int,
        bold: bool = False,
        rotation: float = 0.0,
    ) -> QGraphicsSimpleTextItem:
        item = self.addSimpleText(text)
        item.setBrush(QBrush(QColor(210, 213, 218)))
        item.setFont(
            _label_font(point_size, bold=bold)
        )
        item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        item.setPos(position)
        item.setRotation(rotation)
        return item

    def _draw_scientific_axes(self, y_margin: float, x_margin: float) -> None:
        """Draw cosmetic ticks and physical-coordinate annotations."""

        tick_pen = QPen(QColor(195, 199, 204), 1.2)
        tick_pen.setCosmetic(True)
        tick_length = 2.0

        x_step = self._nice_tick_step(self.definition.x_aperture_um)
        for x_value in self._tick_values(self.x_min, self.x_max, x_step):
            self.addLine(
                x_value,
                self.y_max,
                x_value,
                self.y_max + tick_length,
                tick_pen,
            )
            self.addLine(
                x_value,
                -self.y_max,
                x_value,
                -self.y_max - tick_length,
                tick_pen,
            )
            label = f"{0.0 if abs(x_value) < x_step * 1.0e-9 else x_value:g}"
            text_item = self._add_axis_text(
                label,
                QPointF(x_value, self.y_max + 0.18 * y_margin),
                point_size=12,
                bold=True,
            )
            text_item.setTransform(
                QTransform.fromTranslate(-0.5 * text_item.boundingRect().width(), 0.0)
            )

        y_step = self._nice_tick_step(self.definition.y_aperture_um)
        for y_value in self._tick_values(self.y_min, self.y_max, y_step):
            scene_y = -y_value
            self.addLine(
                self.x_min - tick_length,
                scene_y,
                self.x_min,
                scene_y,
                tick_pen,
            )
            self.addLine(
                self.x_max,
                scene_y,
                self.x_max + tick_length,
                scene_y,
                tick_pen,
            )
            label = f"{0.0 if abs(y_value) < y_step * 1.0e-9 else y_value:g}"
            text_item = self._add_axis_text(
                label,
                QPointF(self.x_min - 0.16 * x_margin, scene_y),
                point_size=12,
                bold=True,
            )
            text_item.setTransform(
                QTransform.fromTranslate(
                    -text_item.boundingRect().width(),
                    -0.5 * text_item.boundingRect().height(),
                )
            )
            right_text_item = self._add_axis_text(
                label,
                QPointF(self.x_max + 0.16 * x_margin, scene_y),
                point_size=12,
                bold=True,
            )
            right_text_item.setTransform(
                QTransform.fromTranslate(
                    0.0,
                    -0.5 * right_text_item.boundingRect().height(),
                )
            )

    def mousePressEvent(self, event) -> None:
        if self.add_mode and event.button() == Qt.LeftButton:
            position = event.scenePos()
            inside = (
                self.x_min <= position.x() <= self.x_max
                and -self.y_max <= position.y() <= -self.y_min
            )
            if inside:
                self.addBeamRequested.emit(float(position.x()), -float(position.y()))
                self.add_mode = False
                event.accept()
                return
        super().mousePressEvent(event)


class LaunchPlaneView(QGraphicsView):
    """View with scroll panning, modified-scroll zoom, and drag panning."""

    minimum_scale = 1.0e-8
    maximum_scale = 50.0

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
        self.setBackgroundBrush(scene.backgroundBrush())
        self._panning = False
        self._pan_start = None

    def fit_all(self) -> None:
        """Reveal the full physical geometry without shortening any ray."""
        scene = self.scene()
        if scene is not None:
            rect = scene.sceneRect().united(scene.itemsBoundingRect())
            self.setSceneRect(rect)
            self.fitInView(rect.adjusted(-10, -10, 10, 10), Qt.KeepAspectRatio)
            self.arrange_beam_labels()

    def arrange_beam_labels(self) -> None:
        """Separate number labels in device space, including coincident beams."""
        scene = self.scene()
        if not isinstance(scene, LaunchPlaneScene):
            return
        occupied = []
        scale = max(abs(self.transform().m11()), 1e-12)
        for item in scene.beam_items:
            label = item._label
            for row in range(len(scene.beam_items) + 1):
                label.setPos(8 / scale, (-18 - row * (label.boundingRect().height() + 5)) / scale)
                rect = label.deviceTransform(self.viewportTransform()).mapRect(label.boundingRect())
                if not any(rect.adjusted(-2,-2,2,2).intersects(other) for other in occupied):
                    break
            occupied.append(rect)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.arrange_beam_labels()

    def fit_aperture(self) -> None:
        scene = self.scene()
        if scene is not None:
            self.setSceneRect(scene.sceneRect())
            self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
            self._clamp_current_scale()
            self.arrange_beam_labels()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            delta = event.pixelDelta().y() or event.angleDelta().y()
            if delta:
                factor = 1.0015**delta
                self._set_scale(self.transform().m11() * factor)
            event.accept()
            return

        delta = event.pixelDelta()
        if delta.isNull():
            delta = event.angleDelta()
        self.horizontalScrollBar().setValue(
            self.horizontalScrollBar().value() - delta.x()
        )
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value() - delta.y()
        )
        event.accept()

    def _set_scale(self, requested_scale: float) -> None:
        current_scale = self.transform().m11()
        target_scale = min(max(requested_scale, self.minimum_scale), self.maximum_scale)
        if current_scale > 0:
            factor = target_scale / current_scale
            self.scale(factor, factor)
            self.arrange_beam_labels()

    def _clamp_current_scale(self) -> None:
        self._set_scale(self.transform().m11())

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
