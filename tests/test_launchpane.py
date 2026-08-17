import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QWheelEvent
from PySide6.QtWidgets import QApplication, QGraphicsSceneMouseEvent

from launchplane.launchpane import LaunchPlaneWidget, example_beam_stack
from launchplane.model import BeamDefinition, BeamStackDefinition


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
    assert widget.beam_stack.beams[0].x_um == 8.0
    assert widget.beam_stack.beams[0].y_um == 12.0

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

    assert (after.x_um, after.y_um) == (9.0, 14.0)
    assert after.tilt_x_rad_per_um == before.tilt_x_rad_per_um
    assert after.tilt_y_rad_per_um == before.tilt_y_rad_per_um
    app.processEvents()
    widget.close()


def test_tilt_handle_mapping_preserves_beam_position() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    item = widget.scene.beam_items[1]
    before = widget.beam_stack.beams[1]
    widget.object_list.setCurrentRow(1)

    assert item._tilt_handle.isVisible()
    assert not widget.scene.beam_items[0]._tilt_handle.isVisible()

    # Scene right is model +y; scene up (negative screen y) is model +x.
    drag_event = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMouseMove)
    drag_event.setScenePos(item.scenePos() + QPointF(25.0, -10.0))
    item._tilt_handle.mouseMoveEvent(drag_event)
    after = widget.beam_stack.beams[1]

    assert (after.x_um, after.y_um) == (before.x_um, before.y_um)
    assert after.angle_x_rad == pytest.approx(
        10.0 / widget.scene.tilt_arrow_scale
    )
    assert after.angle_y_rad == pytest.approx(
        25.0 / widget.scene.tilt_arrow_scale
    )
    assert after.tilt_x_rad_per_um > after.angle_x_rad
    assert after.tilt_y_rad_per_um > after.angle_y_rad
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

    # Scene horizontal is model y; negative scene vertical is model +x.
    press_scene(widget.scene, QPointF(17.0, -11.0))

    assert len(widget.beam_stack.beams) == len(before.beams) + 1
    beam = widget.beam_stack.beams[-1]
    assert beam.name == "Beam"
    assert (beam.x_um, beam.y_um) == (11.0, 17.0)
    assert beam.launch_input_mode == "angle"
    assert beam.launch_medium_index == 1.0
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

    press_scene(widget.scene, QPointF(widget.scene.y_max + 1.0, 0.0))

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
    widget.waist_x_spin.setValue(9.5)
    widget.x_spin.setValue(7.0)
    widget.tilt_y_spin.setValue(0.031)

    beam = widget.beam_stack.beams[0]
    item = widget.scene.beam_items[0]
    assert beam.name == "Updated probe"
    assert beam.coherence_group == "new_group"
    assert beam.waist_x_um == 9.5
    assert beam.x_um == 7.0
    assert beam.tilt_y_rad_per_um == 0.031
    assert item.beam == beam
    assert item.pos() == QPointF(beam.y_um, -beam.x_um)
    assert "Updated probe" in widget.object_list.item(0).text()
    assert "new_group" in widget.object_list.item(0).text()
    app.processEvents()
    widget.close()


def test_canvas_edits_update_inspector_values() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    widget.object_list.setCurrentRow(1)
    item = widget.scene.beam_items[1]

    item.setPos(13.0, -6.0)
    assert widget.x_spin.value() == 6.0
    assert widget.y_spin.value() == 13.0

    drag_event = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMouseMove)
    drag_event.setScenePos(item.scenePos() + QPointF(-20.0, 15.0))
    item._tilt_handle.mouseMoveEvent(drag_event)
    assert widget.angle_x_spin.value() == -15.0 / widget.scene.tilt_arrow_scale
    assert widget.angle_y_spin.value() == -20.0 / widget.scene.tilt_arrow_scale
    app.processEvents()
    widget.close()


def test_normal_editor_uses_external_angles_and_air_default() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    widget.object_list.setCurrentRow(0)

    beam = widget.beam_stack.beams[0]
    assert beam.launch_input_mode == "angle"
    assert beam.launch_medium_index == 1.0
    assert widget.angle_x_label.text() == "Angle x"
    assert widget.angle_x_spin.suffix() == " rad"
    assert widget.launch_medium_index_spin.value() == 1.0
    assert not widget.angle_x_spin.isHidden()
    assert widget.tilt_x_spin.isHidden()
    assert "before the first downstream interface" in (
        widget.launch_medium_index_spin.toolTip()
    )
    widget.angle_y_spin.setValue(0.0)
    widget.angle_x_spin.setValue(0.1)
    assert widget.beam_stack.beams[0].tilt_x_rad_per_um == pytest.approx(
        0.9909508004,
        abs=5e-11,
    )
    app.processEvents()
    widget.close()


def test_switching_editor_mode_preserves_physical_wavevector() -> None:
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    widget.object_list.setCurrentRow(0)
    before = widget.beam_stack.beams[0]

    widget.launch_input_mode_combo.setCurrentIndex(
        widget.launch_input_mode_combo.findData("transverse_wavevector")
    )
    after = widget.beam_stack.beams[0]

    assert after.launch_input_mode == "transverse_wavevector"
    assert after.tilt_x_rad_per_um == before.tilt_x_rad_per_um
    assert after.tilt_y_rad_per_um == before.tilt_y_rad_per_um
    assert widget.phase_slope_x_label.text() == "Phase slope x"
    assert not widget.tilt_x_spin.isHidden()
    assert widget.angle_x_spin.isHidden()
    app.processEvents()
    widget.close()


def test_legacy_unknown_medium_remains_unknown_until_explicit_angle_mode() -> None:
    app = QApplication.instance() or QApplication([])
    legacy = BeamDefinition(
        name="legacy",
        tilt_x_rad_per_um=0.1,
        launch_medium_index=None,
        launch_input_mode="transverse_wavevector",
    )
    widget = LaunchPlaneWidget(
        beam_stack=BeamStackDefinition(beams=(legacy,))
    )
    widget.object_list.setCurrentRow(0)

    assert widget.launch_medium_index_spin.specialValueText() == "Unknown"
    assert widget.launch_medium_index_spin.value() == 0.0
    widget.launch_input_mode_combo.setCurrentIndex(
        widget.launch_input_mode_combo.findData("angle")
    )

    after = widget.beam_stack.beams[0]
    assert after.launch_input_mode == "angle"
    assert after.launch_medium_index == 1.0
    assert after.tilt_x_rad_per_um == legacy.tilt_x_rad_per_um
    app.processEvents()
    widget.close()


def test_nonpropagating_wavevector_cannot_be_relabelled_as_an_angle() -> None:
    app = QApplication.instance() or QApplication([])
    beam = BeamDefinition(
        name="evanescent-in-air",
        tilt_x_rad_per_um=20.0,
        launch_medium_index=1.0,
        launch_input_mode="transverse_wavevector",
    )
    widget = LaunchPlaneWidget(
        beam_stack=BeamStackDefinition(beams=(beam,))
    )
    widget.object_list.setCurrentRow(0)

    widget.launch_input_mode_combo.setCurrentIndex(
        widget.launch_input_mode_combo.findData("angle")
    )

    assert widget.beam_stack.beams[0] == beam
    assert widget.launch_input_mode_combo.currentData() == "transverse_wavevector"
    app.processEvents()
    widget.close()


def test_canvas_advanced_mode_preserves_phase_slope_signs() -> None:
    app = QApplication.instance() or QApplication([])
    beam = BeamDefinition(
        name="advanced",
        launch_medium_index=None,
        launch_input_mode="transverse_wavevector",
    )
    widget = LaunchPlaneWidget(
        beam_stack=BeamStackDefinition(beams=(beam,))
    )
    widget.object_list.setCurrentRow(0)
    item = widget.scene.beam_items[0]
    drag_event = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMouseMove)
    drag_event.setScenePos(item.scenePos() + QPointF(-25.0, 10.0))

    item._tilt_handle.mouseMoveEvent(drag_event)
    after = widget.beam_stack.beams[0]

    assert after.tilt_x_rad_per_um == -10.0 / widget.scene.tilt_arrow_scale
    assert after.tilt_y_rad_per_um == -25.0 / widget.scene.tilt_arrow_scale
    assert after.launch_medium_index is None
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
