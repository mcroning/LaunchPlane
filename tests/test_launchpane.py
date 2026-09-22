import os
import math

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QGraphicsSceneMouseEvent

from launchplane.launchpane import LaunchPlaneWidget, example_beam_stack
from launchplane.model import (
    BeamDefinition,
    BeamStackDefinition,
)


def press_scene(scene, position: QPointF) -> None:
    event = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMousePress)
    event.setButton(Qt.LeftButton)
    event.setButtons(Qt.LeftButton)
    event.setScenePos(position)
    scene.mousePressEvent(event)


def test_launch_plane_widget_smoke() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())

    assert len(widget.beam_stack.beams) == 3
    assert widget.object_list.count() == 3

    widget.object_list.setCurrentRow(0)
    assert widget.scene.beam_items[0].isSelected()

    widget.scene.beam_items[0].setPos(12.0, -8.0)
    app.processEvents()
    assert widget.beam_stack.beams[0].x_um == 12.0
    assert widget.beam_stack.beams[0].y_um == 8.0

    widget.duplicate_selected()
    assert len(widget.beam_stack.beams) == 4

    widget.delete_selected()
    assert len(widget.beam_stack.beams) == 3

    widget.close()


def test_moving_beam_center_preserves_tilt() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    before = widget.beam_stack.beams[0]

    widget.scene.beam_items[0].setPos(14.0, -9.0)
    after = widget.beam_stack.beams[0]

    assert (after.x_um, after.y_um) == (14.0, 9.0)
    assert after.theta_ext_rad == before.theta_ext_rad
    assert after.phi_rad == before.phi_rad
    app.processEvents()
    widget.close()


def test_zoom_scale_is_clamped() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())

    zoom_in = QWheelEvent(
        QPointF(),
        QPointF(),
        QPoint(),
        QPoint(0, 100_000),
        Qt.NoButton,
        Qt.ControlModifier,
        Qt.NoScrollPhase,
        False,
    )
    widget.view.wheelEvent(zoom_in)
    assert widget.view.transform().m11() == widget.view.maximum_scale

    zoom_out = QWheelEvent(
        QPointF(),
        QPointF(),
        QPoint(),
        QPoint(0, -100_000),
        Qt.NoButton,
        Qt.ControlModifier,
        Qt.NoScrollPhase,
        False,
    )
    widget.view.wheelEvent(zoom_out)
    assert widget.view.transform().m11() == widget.view.minimum_scale

    pan_event = QWheelEvent(
        QPointF(),
        QPointF(),
        QPoint(0, 20),
        QPoint(),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.ScrollUpdate,
        False,
    )
    scale_before_pan = widget.view.transform().m11()
    widget.view.wheelEvent(pan_event)
    assert widget.view.transform().m11() == scale_before_pan
    app.processEvents()
    widget.close()


def test_add_beam_arms_then_places_at_scene_position() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    before = widget.beam_stack

    widget.add_beam()

    assert widget.beam_stack == before
    assert widget.scene.add_mode
    assert widget.add_button.text() == "Click launch plane…"
    assert widget.view.viewport().cursor().shape() == Qt.CrossCursor

    # Scene horizontal is +x; scene up is +y.
    press_scene(widget.scene, QPointF(17.0, -11.0))

    assert len(widget.beam_stack.beams) == len(before.beams) + 1
    beam = widget.beam_stack.beams[-1]
    assert beam.name == "Beam"
    assert (beam.x_um, beam.y_um) == (17.0, 11.0)
    assert beam.theta_ext_rad == 0
    assert beam.n_ext == 1.0
    assert widget.object_list.currentRow() == len(before.beams)
    assert widget.scene.beam_items[-1].isSelected()
    assert not widget.scene.add_mode
    assert widget.add_button.text() == "Add beam"
    app.processEvents()
    widget.close()


def test_outside_click_does_not_place_and_escape_cancels() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    count = len(widget.beam_stack.beams)
    widget.add_beam()

    press_scene(widget.scene, QPointF(widget.scene.x_max + 1.0, 0.0))

    assert len(widget.beam_stack.beams) == count
    assert widget.scene.add_mode

    escape = QKeyEvent(QEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    widget.keyPressEvent(escape)
    assert not widget.scene.add_mode
    assert widget.add_button.text() == "Add beam"
    assert widget.view.viewport().cursor().shape() != Qt.CrossCursor
    app.processEvents()
    widget.close()


def test_inspector_edits_update_stack_canvas_and_object_list() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    widget.object_list.setCurrentRow(0)

    widget.name_edit.setText("Updated probe")
    widget.name_edit.editingFinished.emit()
    widget.laser_combo.setCurrentText("new_group")
    widget.laser_combo.lineEdit().editingFinished.emit()
    widget.w1_spin.setValue(9.5)
    widget.x_spin.setValue(7.0)
    widget.phi_spin.setValue(45)

    beam = widget.beam_stack.beams[0]
    item = widget.scene.beam_items[0]
    assert beam.name == "Updated probe"
    assert beam.coherence_group == "new_group"
    assert beam.w1_um == 9.5
    assert beam.x_um == 7.0
    assert beam.phi_rad == math.pi/4
    assert item.beam == beam
    assert item.pos() == QPointF(beam.x_um, -beam.y_um)
    assert "Updated probe" in widget.object_list.item(0).text()
    assert "new_group" in widget.object_list.item(0).text()
    app.processEvents()
    widget.close()


def test_inspector_resolves_duplicate_beam_names() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    widget.object_list.setCurrentRow(1)

    widget.name_edit.setText("Probe")
    widget.name_edit.editingFinished.emit()

    names = tuple(beam.name for beam in widget.beam_stack.beams)
    assert names[1] == "Probe 2"
    assert len(names) == len(set(names))
    assert widget.name_edit.text() == "Probe 2"
    app.processEvents()
    widget.close()


def test_laser_combo_assigns_existing_group_and_removes_unused_group() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    widget.object_list.setCurrentRow(1)

    assert tuple(widget.laser_combo.itemText(index) for index in range(widget.laser_combo.count())) == (
        "probe",
        "control",
    )
    widget.laser_combo.setCurrentText("probe")
    widget.laser_combo.lineEdit().editingFinished.emit()

    assert widget.beam_stack.beams[1].coherence_group == "probe"
    assert widget.beam_stack.coherence_groups == ("probe",)
    assert tuple(widget.laser_combo.itemText(index) for index in range(widget.laser_combo.count())) == (
        "probe",
    )
    assert "[probe]" in widget.object_list.item(1).text()
    app.processEvents()
    widget.close()


def test_laser_combo_creates_new_group_and_rejects_empty_name() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    widget.object_list.setCurrentRow(0)

    widget.laser_combo.setCurrentText("Ti:Sapphire")
    widget.laser_combo.lineEdit().editingFinished.emit()
    assert widget.beam_stack.beams[0].coherence_group == "Ti:Sapphire"
    assert "Ti:Sapphire" in widget.beam_stack.coherence_groups

    widget.laser_combo.setCurrentText("   ")
    widget.laser_combo.lineEdit().editingFinished.emit()
    assert widget.beam_stack.beams[0].coherence_group == "Ti:Sapphire"
    assert widget.laser_combo.currentText() == "Ti:Sapphire"
    app.processEvents()
    widget.close()


def test_primary_controls_fit_default_layout_without_scrolling() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    widget.resize(1280, 860)
    widget.object_list.setCurrentRow(0)
    widget.show()
    app.processEvents()

    assert widget.object_list.isVisibleTo(widget)
    assert widget.add_button.isVisibleTo(widget)
    assert widget.delete_button.isVisibleTo(widget)
    assert widget.duplicate_button.isVisibleTo(widget)
    assert widget.fit_button.isVisibleTo(widget)
    assert widget.laser_combo.isVisibleTo(widget)
    assert widget.phase_spin.isVisibleTo(widget)
    assert widget.inspector_scroll.verticalScrollBar().maximum() == 0
    widget.close()


def test_enabled_checkbox_updates_only_selected_beam() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())

    widget.object_list.setCurrentRow(0)
    assert widget.enabled_checkbox.isChecked()
    widget.enabled_checkbox.setChecked(False)

    assert widget.beam_stack.beams[0].enabled is False
    assert widget.beam_stack.beams[1].enabled is True
    assert widget.scene.beam_items[0].beam.enabled is False
    assert widget.scene.beam_items[1].beam.enabled is True

    widget.object_list.setCurrentRow(1)
    assert widget.enabled_checkbox.isChecked()
    assert widget.beam_stack.beams[0].enabled is False
    assert widget.beam_stack.beams[1].enabled is True

    widget.object_list.setCurrentRow(0)
    assert not widget.enabled_checkbox.isChecked()
    app.processEvents()
    widget.close()


@pytest.mark.parametrize('phi,expected', [(0,(40,0)), (90,(0,-40)), (180,(-40,0)),
                                         (270,(0,40)), (45,(20*2**.5,-20*2**.5))])
def test_physical_arrows_and_device_length(phi,expected):
    app=QApplication.instance() or QApplication([])
    beam=BeamDefinition(theta_ext_rad=math.pi/6,phi_rad=math.radians(phi),x_um=7,y_um=-13)
    widget=LaunchPlaneWidget(beam_stack=BeamStackDefinition(beams=(beam,)))
    try:
        item=widget.scene.beam_items[0]
        assert item.pos()==QPointF(7,13)
        tip=item.tilt_tip_offset()
        assert (tip.x(),tip.y())==pytest.approx(expected)
        assert 'θext=30°' in item._label.text()
        for scale in (0.5,1,3,10):
            widget.view._set_scale(scale)
            device=item.deviceTransform(widget.view.viewportTransform())
            delta=device.map(tip)-device.map(QPointF())
            assert math.hypot(delta.x(),delta.y())==pytest.approx(40)
    finally:
        widget.close();widget.deleteLater();app.processEvents()


def test_drag_uses_same_device_geometry_at_different_zoom():
    app=QApplication.instance() or QApplication([])
    widget=LaunchPlaneWidget(beam_stack=example_beam_stack())
    try:
        widget.object_list.setCurrentRow(1)
        item=widget.scene.beam_items[1];before=item.beam
        for scale in (1,3,0.5):
            widget.view._set_scale(scale)
            scene_to_device=widget.view.viewportTransform()
            inverse,ok=scene_to_device.inverted();assert ok
            origin=scene_to_device.map(item.scenePos())
            event=QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMouseMove)
            event.setScenePos(inverse.map(origin+QPointF(0,-40)))
            item._tilt_handle.mouseMoveEvent(event)
            assert widget.beam_stack.beams[1].theta_ext_rad==pytest.approx(math.pi/6)
            assert widget.beam_stack.beams[1].phi_rad==pytest.approx(math.pi/2)
            assert widget.theta_spin.value()==pytest.approx(30)
            assert widget.phi_spin.value()==pytest.approx(90)
            assert (item.beam.x_um,item.beam.y_um)==(before.x_um,before.y_um)
        item.setPos(-9,-17)
        assert (widget.x_spin.value(),widget.y_spin.value())==(-9,17)
    finally:
        widget.close();widget.deleteLater();app.processEvents()


def test_normal_disabled_multi_beam_and_bounded_arrow():
    app=QApplication.instance() or QApplication([])
    beams=BeamStackDefinition(beams=(
        BeamDefinition(name='normal',phi_rad=1.3),
        BeamDefinition(name='high',theta_ext_rad=math.pi/2-1e-8,x_um=4,y_um=8,enabled=False),
        BeamDefinition(name='opposite',theta_ext_rad=math.pi/4,phi_rad=math.pi,x_um=-4,y_um=-8)))
    widget=LaunchPlaneWidget(beam_stack=beams)
    try:
        normal,high,opposite=widget.scene.beam_items
        assert normal.tilt_tip_offset()==QPointF()
        assert normal._center_marker.isVisible()
        assert math.hypot(high.tilt_tip_offset().x(),high.tilt_tip_offset().y())<=80
        assert '[disabled]' in high._label.text()
        assert opposite.tilt_tip_offset().x()<0
        assert high.pos()==QPointF(4,-8) and opposite.pos()==QPointF(-4,8)
        assert widget.scene.stack()==beams
        widget.view.fit_aperture()
        widget.show();app.processEvents()
        # Exercise offscreen painting, not only stored geometry.
        assert not widget.grab().isNull()
    finally:
        widget.close();widget.deleteLater();app.processEvents()


def test_external_inspector_intent_roundtrip_without_execution_bridge():
    from launchplane.serialization import beam_stack_to_dict,beam_stack_from_dict
    app=QApplication.instance() or QApplication([])
    widget=LaunchPlaneWidget(beam_stack=example_beam_stack())
    try:
        widget.object_list.setCurrentRow(0)
        widget.theta_spin.setValue(42)
        widget.phi_spin.setValue(230)
        widget.psi_spin.setValue(65)
        widget.n_ext_spin.setValue(1.4)
        widget.w1_spin.setValue(6)
        widget.w2_spin.setValue(11)
        widget.phase_spin.setValue(1.2)
        widget.power_spin.setValue(0)
        beam=widget.beam_stack.beams[0]
        assert (beam.theta_ext_rad,beam.phi_rad,beam.psi_rad)==pytest.approx(tuple(map(math.radians,(42,230,65))))
        assert (beam.n_ext,beam.w1_um,beam.w2_um,beam.phase_rad,beam.power_mW)==(1.4,6,11,1.2,0)
        direction=beam.external_direction
        widget.psi_spin.setValue(100)
        assert widget.beam_stack.beams[0].external_direction==direction
        data=beam_stack_to_dict(widget.beam_stack)
        widget.set_beam_stack(beam_stack_from_dict(data),0)
        assert beam_stack_to_dict(widget.beam_stack)==data
        assert 'read-only' in widget.derived_k.text()
        assert 'requires a compatible host resolver' in widget.execution_status.text()
        assert not hasattr(widget,'tilt_x_spin')
        assert not hasattr(widget,'launch_input_mode_combo')
        assert not hasattr(widget,'profile_combo')
    finally:
        widget.close();widget.deleteLater();app.processEvents()


def test_nonsquare_aperture_placement_and_clamping():
    from launchplane.model import LaunchPlaneDefinition
    from PySide6.QtWidgets import QGraphicsRectItem
    app=QApplication.instance() or QApplication([])
    widget=LaunchPlaneWidget(launch_plane=LaunchPlaneDefinition(80,140))
    try:
        rectangles=[i.rect() for i in widget.scene.items() if isinstance(i,QGraphicsRectItem)]
        assert any(r.x()==-40 and r.y()==-70 and r.width()==80 and r.height()==140 for r in rectangles)
        widget.add_beam();press_scene(widget.scene,QPointF(35,-65))
        assert (widget.beam_stack.beams[0].x_um,widget.beam_stack.beams[0].y_um)==(35,65)
        item=widget.scene.beam_items[0];item.setPos(60,90)
        assert (widget.beam_stack.beams[0].x_um,widget.beam_stack.beams[0].y_um)==(40,-70)
        labels=[i.text() for i in widget.scene.items() if hasattr(i,'text')]
        assert 'Laboratory x (µm)' in labels and 'Laboratory y (µm)' in labels
    finally:
        widget.close();widget.deleteLater();app.processEvents()


def test_positive_inputs_and_grazing_limit_are_enforced_by_widgets():
    app=QApplication.instance() or QApplication([])
    widget=LaunchPlaneWidget(beam_stack=example_beam_stack())
    try:
        widget.object_list.setCurrentRow(0)
        for editor in (widget.n_ext_spin,widget.wavelength_spin,widget.w1_spin,widget.w2_spin):
            assert editor.minimum()>0
            editor.setValue(0)
            assert editor.value()>0
        widget.theta_spin.setValue(90)
        assert widget.beam_stack.beams[0].theta_ext_rad<math.pi/2
    finally:
        widget.close();widget.deleteLater();app.processEvents()


@pytest.mark.parametrize('width',[1000,1200,1280,1450])
def test_layout_remains_responsive(width):
    app=QApplication.instance() or QApplication([])
    widget=LaunchPlaneWidget(beam_stack=example_beam_stack())
    try:
        widget.resize(width,860);widget.object_list.setCurrentRow(0)
        widget.show();app.processEvents()
        assert widget.size().width()==width
        assert widget.view.width()>300
        assert widget.inspector_scroll.horizontalScrollBar().maximum()==0
        assert widget.inspector_scroll.verticalScrollBar().maximum()==0
        assert widget.execution_status.isVisibleTo(widget)
    finally:
        widget.close();widget.deleteLater();app.processEvents()


def test_refresh_does_not_move_explicit_outside_aperture_center():
    app = QApplication.instance() or QApplication([])
    beam = BeamDefinition(x_um=200, y_um=-300)
    widget = LaunchPlaneWidget(beam_stack=BeamStackDefinition(beams=(beam,)))
    try:
        widget.object_list.setCurrentRow(0)
        assert widget.x_spin.value() == 200
        assert widget.y_spin.value() == -300
        widget.power_spin.setValue(2)
        after = widget.beam_stack.beams[0]
        assert (after.x_um, after.y_um) == (200, -300)
        assert widget.scene.stack() == widget.beam_stack
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()
