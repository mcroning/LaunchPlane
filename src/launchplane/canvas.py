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
        direction_arrow_length: float = 80.0,
        parent: QGraphicsItem | None = None,
    ):
        super().__init__(parent)
        self.index = int(index)
        self.beam = beam
        if not math.isfinite(direction_arrow_length) or direction_arrow_length <= 0:
            raise ValueError("direction_arrow_length must be finite and positive")
        self.direction_arrow_length = float(direction_arrow_length)
        self._hovered = False
        self._refreshing = False

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

        self._center_marker = CenterMarkerItem(self)
        self._label = QGraphicsSimpleTextItem(self)
        self._label.setBrush(QBrush(QColor(235, 235, 235)))
        self._label.setFont(QFont("Sans Serif", 12, QFont.Bold))
        self._label.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self._label.setAcceptedMouseButtons(Qt.NoButton)
        self._label.setPos(6.0, -16.0)
        self._tilt_handle = TiltHandleItem(self)
        self.refresh(beam)

    def refresh(self, beam: BeamDefinition) -> None:
        self.prepareGeometryChange()
        self.beam = beam
        self._label.setText(f"{self.index + 1}. {beam.name} · θext={math.degrees(beam.theta_ext_rad):.4g}°" + (" [disabled]" if not beam.enabled else ""))
        self._refreshing = True
        try:
            self.setPos(beam.x_um, -beam.y_um)
        finally:
            self._refreshing = False
        self._update_tilt_handle()
        self.update()

    def tilt_tip_offset(self) -> QPointF:
        """Bounded display-pixel arrow, never a physical trajectory."""
        length = self.direction_arrow_length * math.sin(self.beam.theta_ext_rad)
        return QPointF(length * math.cos(self.beam.phi_rad), -length * math.sin(self.beam.phi_rad))

    def set_tilt_tip(self, scene_position: QPointF) -> None:
        """Edit external direction using the same device mapping as painting."""
        views = self.scene().views() if self.scene() else []
        if not views:
            return
        transform = views[0].viewportTransform()
        inverse, valid = self.deviceTransform(transform).inverted()
        if not valid:
            return
        offset = inverse.map(transform.map(scene_position))
        radius = math.hypot(offset.x(), offset.y())
        # Drag saturation is a UI limit; model validation never clips inputs.
        theta = math.asin(min(radius / self.direction_arrow_length, math.sin(math.radians(89.999999))))
        phi = math.atan2(-offset.y(), offset.x()) if radius else self.beam.phi_rad
        self.refresh(replace(self.beam, theta_ext_rad=theta, phi_rad=phi))
        self.changed.emit(self.index, self.beam)

    def _update_tilt_handle(self) -> None:
        self._tilt_handle.setPos(self.tilt_tip_offset())
        self._tilt_handle.setToolTip("External direction: bounded sin(theta) display length; drag to edit theta/phi.")

    def boundingRect(self) -> QRectF:
        tip = self.tilt_tip_offset()
        return QRectF(QPointF(min(-7, tip.x()-7), min(-7, tip.y()-7)),
                      QPointF(max(7, tip.x()+7), max(7, tip.y()+7)))

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(QRectF(-7, -7, 14, 14))
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget
        # No fabricated footprint: centers and external directions only.
        self._paint_tilt_arrow(painter)

    def _paint_tilt_arrow(self, painter: QPainter) -> None:
        tip = self.tilt_tip_offset()
        dx = tip.x()
        dy = tip.y()
        length = math.hypot(dx, dy)
        if self.beam.theta_ext_rad == 0:
            return

        end = QPointF(dx, dy)
        arrow_color = QColor(255, 110, 110) if self.beam.enabled else QColor(120, 120, 120)
        arrow_pen = QPen(arrow_color, 1.8)
        arrow_pen.setCosmetic(True)
        painter.setPen(arrow_pen)
        painter.drawLine(QPointF(0.0, 0.0), end)

        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        head = min(2.2, length * 0.4)
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
            self.moved.emit(self.index, x_um, y_um)

        if change == QGraphicsItem.ItemSelectedHasChanged:
            selected = bool(value)
            self._tilt_handle.setVisible(selected)
            self._center_marker.update()
            if selected:
                self.selected.emit(self.index)

        return super().itemChange(change, value)


class CenterMarkerItem(QGraphicsItem):
    """Constant-screen-size marker at a beam center."""

    def __init__(self, parent: BeamItem):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setZValue(2)

    def boundingRect(self) -> QRectF:
        return QRectF(-6.0, -6.0, 12.0, 12.0)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget
        beam_item = self.parentItem()
        color = QColor(255, 190, 70) if beam_item.isSelected() else QColor(90, 180, 255)
        if not beam_item.beam.enabled:
            color = QColor(120, 120, 120)
        pen = QPen(color, 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(), 2.5, 2.5)
        painter.drawLine(QPointF(-5.0, 0.0), QPointF(5.0, 0.0))
        painter.drawLine(QPointF(0.0, -5.0), QPointF(0.0, 5.0))


class TiltHandleItem(QGraphicsObject):
    """Constant-screen-size draggable handle for a beam's tilt tip."""

    def __init__(self, parent: BeamItem):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.setCursor(Qt.CrossCursor)
        self.setZValue(3)
        self.setVisible(False)

    def boundingRect(self) -> QRectF:
        return QRectF(-5.0, -5.0, 10.0, 10.0)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget
        pen = QPen(QColor(255, 235, 235), 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(220, 55, 55)))
        painter.drawEllipse(self.boundingRect())

    def mousePressEvent(self, event) -> None:
        beam_item = self.parentItem()
        beam_item.setSelected(True)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        beam_item = self.parentItem()
        beam_item.set_tilt_tip(event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        event.accept()


class LaunchPlaneScene(QGraphicsScene):
    """Graphics scene containing the aperture and beam items."""

    sceneAboutToReset = Signal()
    addBeamRequested = Signal(float, float)
    beamMoved = Signal(int, float, float)
    beamChanged = Signal(int, object)
    beamSelected = Signal(int)

    def __init__(
        self,
        definition: LaunchPlaneDefinition | None = None,
        parent=None,
        *,
        direction_arrow_length: float = 80.0,
    ):
        super().__init__(parent)
        self.definition = definition or LaunchPlaneDefinition()
        self.definition.validate()
        if not math.isfinite(direction_arrow_length) or direction_arrow_length <= 0:
            raise ValueError("direction_arrow_length must be positive")
        self.direction_arrow_length = float(direction_arrow_length)
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
                direction_arrow_length=self.direction_arrow_length,
            )
            item.moved.connect(self.beamMoved)
            item.changed.connect(self.beamChanged)
            item.selected.connect(self.beamSelected)
            self.addItem(item)
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

        title = self.addSimpleText("Entrance centers · x right / y up · arrows: external direction")
        title.setBrush(QBrush(QColor(238, 239, 241)))
        title.setFont(QFont("Sans Serif", 14, QFont.Bold))
        title.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        title.setPos(self.x_min, -self.y_max - 0.55 * y_margin)

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
            QFont("Sans Serif", point_size, QFont.Bold if bold else QFont.Normal)
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

        horizontal_title = self._add_axis_text(
            "Laboratory x (µm)",
            QPointF(0.0, self.y_max + 0.58 * y_margin),
            point_size=15,
            bold=True,
        )
        horizontal_title.setTransform(
            QTransform.fromTranslate(
                -0.5 * horizontal_title.boundingRect().width(),
                0.0,
            )
        )

        vertical_title = self._add_axis_text(
            "Laboratory y (µm)",
            QPointF(
                self.x_min - 0.72 * x_margin,
                0.16 * self.definition.y_aperture_um,
            ),
            point_size=15,
            bold=True,
            rotation=-90.0,
        )

        bounds = self.addSimpleText(
            f"x: {self.x_min:g} … {self.x_max:g} µm    "
            f"y: {self.y_min:g} … {self.y_max:g} µm"
        )
        bounds.setBrush(QBrush(QColor(185, 190, 197)))
        bounds.setFont(QFont("Sans Serif", 11, QFont.Bold))
        bounds.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        bounds.setPos(self.x_max, -self.y_max - 0.55 * y_margin)
        bounds.setTransform(
            QTransform.fromTranslate(-bounds.boundingRect().width(), 0.0)
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

    minimum_scale = 0.5
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

    def fit_aperture(self) -> None:
        scene = self.scene()
        if scene is not None:
            self.fitInView(scene.sceneRect(), Qt.KeepAspectRatio)
            self._clamp_current_scale()

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
