"""Runnable PySide6 demonstration of the LaunchPlane canvas."""

from __future__ import annotations

import sys
from dataclasses import replace

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from launchplane.canvas import LaunchPlaneScene, LaunchPlaneView
from launchplane.model import BeamDefinition, BeamStackDefinition, LaunchPlaneDefinition


def _increase_font_size(widget: QWidget, points: float) -> None:
    """Increase a widget's font while respecting the platform default."""

    font = widget.font()
    if font.pointSizeF() > 0:
        font.setPointSizeF(font.pointSizeF() + points)
    else:
        font.setPixelSize(font.pixelSize() + round(points * 1.4))
    widget.setFont(font)


def example_beam_stack() -> BeamStackDefinition:
    """Return the three beams shown when the demo starts."""

    return BeamStackDefinition(
        beams=(
            BeamDefinition.from_launch_angles(
                name="Probe",
                x_um=-15.0,
                y_um=-25.0,
                waist_x_um=4.0,
                waist_y_um=7.0,
                angle_x_rad=0.012,
                angle_y_rad=0.004,
                coherence_group="probe",
            ),
            BeamDefinition.from_launch_angles(
                name="Control",
                x_um=4.0,
                y_um=2.0,
                waist_x_um=8.0,
                waist_y_um=5.0,
                angle_x_rad=-0.006,
                angle_y_rad=0.018,
                coherence_group="control",
            ),
            BeamDefinition.from_launch_angles(
                name="Reference",
                x_um=18.0,
                y_um=28.0,
                waist_x_um=5.0,
                waist_y_um=10.0,
                angle_x_rad=0.005,
                angle_y_rad=-0.014,
                coherence_group="probe",
            ),
        )
    )


class LaunchPlaneWidget(QWidget):
    """Reusable launch-plane canvas with basic beam collection controls."""

    beamStackChanged = Signal(object)

    def __init__(
        self,
        launch_plane: LaunchPlaneDefinition | None = None,
        beam_stack: BeamStackDefinition | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._selected_index: int | None = None
        self._updating_inspector = False
        self.scene = LaunchPlaneScene(launch_plane or LaunchPlaneDefinition(), self)
        self.view = LaunchPlaneView(self.scene, self)
        self.object_list = QListWidget(self)
        self.object_list.setMinimumWidth(170)

        self.add_button = QPushButton("Add beam", self)
        self.delete_button = QPushButton("Delete selected", self)
        self.duplicate_button = QPushButton("Duplicate selected", self)
        self.fit_button = QPushButton("Fit aperture", self)
        _increase_font_size(self.object_list, 2.0)
        for button in (
            self.add_button,
            self.delete_button,
            self.duplicate_button,
            self.fit_button,
        ):
            _increase_font_size(button, 1.5)

        side_panel = QWidget(self)
        side_panel.setMinimumWidth(340)
        side_panel.setMaximumWidth(400)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setSpacing(5)
        objects_label = QLabel("Objects", side_panel)
        _increase_font_size(objects_label, 1.5)
        side_layout.addWidget(objects_label)
        self.object_list.setMinimumHeight(125)
        side_layout.addWidget(self.object_list, 1)
        side_layout.addWidget(self.add_button)
        side_layout.addWidget(self.delete_button)
        side_layout.addWidget(self.duplicate_button)
        side_layout.addWidget(self.fit_button)

        self.inspector = self._create_inspector()
        self.inspector_scroll = QScrollArea(self)
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QScrollArea.NoFrame)
        self.inspector_scroll.setWidget(self.inspector)
        self.inspector_scroll.setMinimumHeight(420)
        side_layout.addWidget(self.inspector_scroll, 3)

        layout = QHBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.addWidget(self.view)
        self.splitter.addWidget(side_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([900, 360])
        layout.addWidget(self.splitter)

        self.object_list.currentRowChanged.connect(self._select_scene_beam)
        self.scene.beamSelected.connect(self._select_list_beam)
        self.scene.beamMoved.connect(self._beam_moved)
        self.scene.beamChanged.connect(self._beam_changed)
        self.scene.addBeamRequested.connect(self._place_beam)
        self.add_button.clicked.connect(self.add_beam)
        self.delete_button.clicked.connect(self.delete_selected)
        self.duplicate_button.clicked.connect(self.duplicate_selected)
        self.fit_button.clicked.connect(self._fit_aperture)

        self.cancel_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.cancel_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.cancel_shortcut.activated.connect(self.cancel_placement)

        self._beam_stack = BeamStackDefinition()
        self.set_beam_stack(beam_stack or BeamStackDefinition())

    def _create_inspector(self) -> QGroupBox:
        inspector = QGroupBox("Selected beam", self)
        form = QFormLayout(inspector)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)

        self.name_edit = QLineEdit(inspector)
        self.enabled_checkbox = QCheckBox(inspector)
        self.enabled_check = self.enabled_checkbox
        self.laser_combo = QComboBox(inspector)
        self.laser_combo.setEditable(True)
        self.laser_combo.setInsertPolicy(QComboBox.NoInsert)
        self.laser_combo.setToolTip(
            "Beams with the same Laser name interfere coherently.\n"
            "Beams with different Laser names are mutually incoherent."
        )

        self.power_spin = self._create_spin_box(0.0, 1.0e9, 4, " mW")
        self.wavelength_spin = self._create_spin_box(1.0e-6, 1.0e6, 6, " µm")
        self.x_spin = self._create_spin_box(self.scene.x_min, self.scene.x_max, 3, " µm")
        self.y_spin = self._create_spin_box(self.scene.y_min, self.scene.y_max, 3, " µm")
        self.waist_x_spin = self._create_spin_box(0.001, 1.0e6, 3, " µm")
        self.waist_y_spin = self._create_spin_box(0.001, 1.0e6, 3, " µm")
        self.launch_input_mode_combo = QComboBox(inspector)
        self.launch_input_mode_combo.addItem("External angles", "angle")
        self.launch_input_mode_combo.addItem(
            "Transverse wavevector (advanced)",
            "transverse_wavevector",
        )
        self.launch_input_mode_combo.setToolTip(
            "External angles are measured in the launch medium before the first "
            "downstream interface. Switching modes does not change the beam."
        )
        angle_limit = 0.5 * 3.141592653589793 - 1.0e-6
        self.angle_x_spin = self._create_spin_box(
            -angle_limit, angle_limit, 8, " rad"
        )
        self.angle_y_spin = self._create_spin_box(
            -angle_limit, angle_limit, 8, " rad"
        )
        self.launch_medium_index_spin = self._create_spin_box(0.0, 100.0, 8, "")
        self.launch_medium_index_spin.setSpecialValueText("Unknown")
        self.launch_medium_index_spin.setToolTip(
            "Refractive index of the launch medium immediately before the first "
            "downstream interface. Air is normally 1.0."
        )
        self.tilt_x_spin = self._create_spin_box(-1.0e3, 1.0e3, 8, " rad/µm")
        self.tilt_y_spin = self._create_spin_box(-1.0e3, 1.0e3, 8, " rad/µm")
        self.tilt_x_spin.setToolTip(
            "Advanced conserved transverse wavevector / phase slope qx."
        )
        self.tilt_y_spin.setToolTip(
            "Advanced conserved transverse wavevector / phase slope qy."
        )
        self.phase_spin = self._create_spin_box(-1.0e6, 1.0e6, 6, " rad")

        form.addRow("Name", self.name_edit)
        form.addRow("Enabled", self.enabled_checkbox)
        form.addRow("Power", self.power_spin)
        form.addRow("Wavelength", self.wavelength_spin)
        form.addRow("x", self.x_spin)
        form.addRow("y", self.y_spin)
        form.addRow("Waist x", self.waist_x_spin)
        form.addRow("Waist y", self.waist_y_spin)
        form.addRow("Launch input", self.launch_input_mode_combo)
        form.addRow("Launch medium index", self.launch_medium_index_spin)
        self.angle_x_label = QLabel("Angle x", inspector)
        self.angle_y_label = QLabel("Angle y", inspector)
        self.phase_slope_x_label = QLabel("Phase slope x", inspector)
        self.phase_slope_y_label = QLabel("Phase slope y", inspector)
        form.addRow(self.angle_x_label, self.angle_x_spin)
        form.addRow(self.angle_y_label, self.angle_y_spin)
        form.addRow(self.phase_slope_x_label, self.tilt_x_spin)
        form.addRow(self.phase_slope_y_label, self.tilt_y_spin)
        form.addRow("Phase", self.phase_spin)
        form.addRow("Laser", self.laser_combo)

        self._numeric_editors = {
            "power_mW": self.power_spin,
            "x_um": self.x_spin,
            "y_um": self.y_spin,
            "waist_x_um": self.waist_x_spin,
            "waist_y_um": self.waist_y_spin,
            "phase_rad": self.phase_spin,
        }
        self._inspector_editors = (
            self.name_edit,
            self.enabled_checkbox,
            self.wavelength_spin,
            self.launch_input_mode_combo,
            self.launch_medium_index_spin,
            self.angle_x_spin,
            self.angle_y_spin,
            self.tilt_x_spin,
            self.tilt_y_spin,
            *self._numeric_editors.values(),
            self.laser_combo,
        )

        self.name_edit.editingFinished.connect(self._name_edited)
        self.laser_combo.textActivated.connect(self._laser_edited)
        self.laser_combo.lineEdit().editingFinished.connect(self._laser_edited)
        self.enabled_checkbox.toggled.connect(self._enabled_changed)
        self.wavelength_spin.valueChanged.connect(self._wavelength_edited)
        self.launch_input_mode_combo.currentIndexChanged.connect(
            self._launch_input_mode_edited
        )
        self.launch_medium_index_spin.valueChanged.connect(
            self._launch_medium_index_edited
        )
        self.angle_x_spin.valueChanged.connect(self._launch_angles_edited)
        self.angle_y_spin.valueChanged.connect(self._launch_angles_edited)
        self.tilt_x_spin.valueChanged.connect(self._phase_slopes_edited)
        self.tilt_y_spin.valueChanged.connect(self._phase_slopes_edited)
        for field_name, editor in self._numeric_editors.items():
            editor.valueChanged.connect(
                lambda value, field=field_name: self._apply_selected_changes(
                    **{field: value}
                )
            )
        _increase_font_size(inspector, 1.5)
        return inspector

    def _create_spin_box(
        self,
        minimum: float,
        maximum: float,
        decimals: int,
        suffix: str,
    ) -> QDoubleSpinBox:
        editor = QDoubleSpinBox(self)
        editor.setRange(minimum, maximum)
        editor.setDecimals(decimals)
        editor.setSuffix(suffix)
        editor.setKeyboardTracking(False)
        return editor

    @property
    def beam_stack(self) -> BeamStackDefinition:
        """The current immutable beam-stack definition."""

        return self._beam_stack

    def set_beam_stack(
        self,
        beam_stack: BeamStackDefinition,
        selected_index: int | None = None,
    ) -> None:
        beam_stack.validate()
        self._beam_stack = beam_stack
        self.scene.set_stack(beam_stack)

        self.object_list.blockSignals(True)
        self.object_list.clear()
        for index, beam in enumerate(beam_stack.beams, start=1):
            self.object_list.addItem(
                f"{index}. {beam.name}  [{beam.coherence_group}]"
            )
        if selected_index is not None and beam_stack.beams:
            selected_index = min(max(selected_index, 0), len(beam_stack.beams) - 1)
            self.object_list.setCurrentRow(selected_index)
        else:
            selected_index = None
        self._selected_index = selected_index
        self.object_list.blockSignals(False)
        self.scene.set_selected_index(selected_index)
        self._update_button_states()
        self._sync_inspector()

    def add_beam(self) -> None:
        if self.scene.add_mode:
            self.cancel_placement()
            return
        self.scene.arm_add_mode()
        self.add_button.setText("Click launch plane…")
        self.view.viewport().setCursor(Qt.CrossCursor)

    def cancel_placement(self) -> None:
        self.scene.cancel_add_mode()
        self.add_button.setText("Add beam")
        self.view.viewport().unsetCursor()

    def _place_beam(self, x_um: float, y_um: float) -> None:
        beam = replace(
            BeamDefinition.from_launch_angles(name=self._unique_name("Beam")),
            x_um=x_um,
            y_um=y_um,
        )
        beams = (*self._beam_stack.beams, beam)
        self.cancel_placement()
        self.set_beam_stack(BeamStackDefinition(beams=beams), len(beams) - 1)
        self.beamStackChanged.emit(self._beam_stack)

    def delete_selected(self) -> None:
        self.cancel_placement()
        index = self._selected_index
        if index is None:
            return
        beams = self._beam_stack.beams[:index] + self._beam_stack.beams[index + 1 :]
        selected = min(index, len(beams) - 1) if beams else None
        self.set_beam_stack(BeamStackDefinition(beams=beams), selected)
        self.beamStackChanged.emit(self._beam_stack)

    def duplicate_selected(self) -> None:
        self.cancel_placement()
        index = self._selected_index
        if index is None:
            return

        source = self._beam_stack.beams[index]
        duplicate = replace(
            source,
            name=self._unique_name(f"{source.name} copy"),
            x_um=min(max(source.x_um + 5.0, self.scene.x_min), self.scene.x_max),
            y_um=min(max(source.y_um + 5.0, self.scene.y_min), self.scene.y_max),
        )
        beams = list(self._beam_stack.beams)
        beams.insert(index + 1, duplicate)
        self.set_beam_stack(BeamStackDefinition(beams=tuple(beams)), index + 1)
        self.beamStackChanged.emit(self._beam_stack)

    def _unique_name(self, base: str, exclude_index: int | None = None) -> str:
        base = base.strip() or "Beam"
        names = {
            beam.name
            for index, beam in enumerate(self._beam_stack.beams)
            if index != exclude_index
        }
        if base not in names:
            return base
        suffix = 2
        while f"{base} {suffix}" in names:
            suffix += 1
        return f"{base} {suffix}"

    def _select_scene_beam(self, index: int) -> None:
        self._selected_index = index if 0 <= index < len(self._beam_stack.beams) else None
        self.scene.set_selected_index(self._selected_index)
        self._update_button_states()
        self._sync_inspector()

    def _select_list_beam(self, index: int) -> None:
        self.object_list.setCurrentRow(index)

    def _beam_moved(self, index: int, x_um: float, y_um: float) -> None:
        beams = list(self._beam_stack.beams)
        beams[index] = replace(beams[index], x_um=x_um, y_um=y_um)
        self._beam_stack = BeamStackDefinition(beams=tuple(beams))
        self._sync_inspector()
        self.beamStackChanged.emit(self._beam_stack)

    def _beam_changed(self, index: int, beam: BeamDefinition) -> None:
        beams = list(self._beam_stack.beams)
        beams[index] = beam
        self._beam_stack = BeamStackDefinition(beams=tuple(beams))
        self._sync_inspector()
        self.beamStackChanged.emit(self._beam_stack)

    def _name_edited(self) -> None:
        index = self._selected_index
        if index is None:
            return
        name = self._unique_name(self.name_edit.text(), exclude_index=index)
        self._apply_selected_changes(name=name)

    def _laser_edited(self, text: str | None = None) -> None:
        laser_name = (text if text is not None else self.laser_combo.currentText()).strip()
        if not laser_name:
            self._sync_inspector()
            return
        self._apply_selected_changes(coherence_group=laser_name)

    def _enabled_changed(self, enabled: bool) -> None:
        if self._updating_inspector or self._selected_index is None:
            return
        self._apply_selected_changes(enabled=enabled)

    def _wavelength_edited(self, wavelength_um: float) -> None:
        if self._updating_inspector or self._selected_index is None:
            return
        beam = self._beam_stack.beams[self._selected_index]
        self._apply_selected_beam(beam.with_wavelength_um(wavelength_um))

    def _launch_input_mode_edited(self, _index: int) -> None:
        if self._updating_inspector or self._selected_index is None:
            return
        mode = self.launch_input_mode_combo.currentData()
        beam = self._beam_stack.beams[self._selected_index]
        if mode == "angle" and beam.launch_medium_index is None:
            # This explicit user action establishes air as the launch medium;
            # schema-1 migration itself never does so.
            beam = replace(beam, launch_medium_index=1.0)
        beam = replace(beam, launch_input_mode=mode)
        try:
            beam.validate()
        except ValueError:
            # A phase slope may be non-propagating in the selected launch
            # medium. Keep its exact advanced-mode representation instead of
            # inventing or clipping an angle.
            self._sync_inspector()
            return
        self._apply_selected_beam(beam)

    def _launch_medium_index_edited(self, value: float) -> None:
        if self._updating_inspector or self._selected_index is None:
            return
        beam = self._beam_stack.beams[self._selected_index]
        index = None if value == 0.0 else value
        try:
            updated = beam.with_launch_medium_index(index)
        except ValueError:
            self._sync_inspector()
            return
        self._apply_selected_beam(updated)

    def _launch_angles_edited(self, _value: float) -> None:
        if self._updating_inspector or self._selected_index is None:
            return
        beam = self._beam_stack.beams[self._selected_index]
        self._apply_selected_beam(
            beam.with_launch_angles(
                angle_x_rad=self.angle_x_spin.value(),
                angle_y_rad=self.angle_y_spin.value(),
            )
        )

    def _phase_slopes_edited(self, _value: float) -> None:
        if self._updating_inspector or self._selected_index is None:
            return
        beam = replace(
            self._beam_stack.beams[self._selected_index],
            tilt_x_rad_per_um=self.tilt_x_spin.value(),
            tilt_y_rad_per_um=self.tilt_y_spin.value(),
            launch_input_mode="transverse_wavevector",
        )
        beam.validate()
        self._apply_selected_beam(beam)

    def _apply_selected_changes(self, **changes) -> None:
        index = self._selected_index
        if index is None or not changes:
            return

        if all(
            getattr(self._beam_stack.beams[index], field_name) == value
            for field_name, value in changes.items()
        ):
            self._sync_inspector()
            return

        beam = replace(self._beam_stack.beams[index], **changes)
        self._apply_selected_beam(beam)

    def _apply_selected_beam(self, beam: BeamDefinition) -> None:
        index = self._selected_index
        if index is None:
            return
        if beam == self._beam_stack.beams[index]:
            self._sync_inspector()
            return
        self.cancel_placement()
        beams = list(self._beam_stack.beams)
        beam.validate()
        beams[index] = beam
        beam_stack = BeamStackDefinition(beams=tuple(beams))
        beam_stack.validate()
        self._beam_stack = beam_stack

        item = self.scene.beam_items[index]
        item.blockSignals(True)
        item.refresh(beam)
        item.blockSignals(False)
        self._update_object_list_item(index)
        self._sync_inspector()
        self.beamStackChanged.emit(self._beam_stack)

    def _update_object_list_item(self, index: int) -> None:
        beam = self._beam_stack.beams[index]
        self.object_list.item(index).setText(
            f"{index + 1}. {beam.name}  [{beam.coherence_group}]"
        )

    def _sync_inspector(self) -> None:
        index = self._selected_index
        has_selection = index is not None and 0 <= index < len(self._beam_stack.beams)
        self.inspector.setEnabled(has_selection)
        self._updating_inspector = True
        try:
            for editor in self._inspector_editors:
                editor.blockSignals(True)
            self.laser_combo.clear()
            self.laser_combo.addItems(self._beam_stack.coherence_groups)
            if has_selection:
                beam = self._beam_stack.beams[index]
                self.name_edit.setText(beam.name)
                self.enabled_checkbox.setChecked(beam.enabled)
                self.laser_combo.setCurrentText(beam.coherence_group)
                for field_name, editor in self._numeric_editors.items():
                    editor.setValue(getattr(beam, field_name))
                self.wavelength_spin.setValue(beam.wavelength_um)
                mode_index = self.launch_input_mode_combo.findData(
                    beam.launch_input_mode
                )
                self.launch_input_mode_combo.setCurrentIndex(mode_index)
                self.launch_medium_index_spin.setValue(
                    0.0
                    if beam.launch_medium_index is None
                    else beam.launch_medium_index
                )
                self.tilt_x_spin.setValue(beam.tilt_x_rad_per_um)
                self.tilt_y_spin.setValue(beam.tilt_y_rad_per_um)
                try:
                    angle_x, angle_y = beam.launch_angles_rad
                except ValueError:
                    angle_x = angle_y = 0.0
                self.angle_x_spin.setValue(angle_x)
                self.angle_y_spin.setValue(angle_y)
                angle_mode = beam.launch_input_mode == "angle"
                for widget in (
                    self.angle_x_label,
                    self.angle_x_spin,
                    self.angle_y_label,
                    self.angle_y_spin,
                ):
                    widget.setVisible(angle_mode)
                for widget in (
                    self.phase_slope_x_label,
                    self.tilt_x_spin,
                    self.phase_slope_y_label,
                    self.tilt_y_spin,
                ):
                    widget.setVisible(not angle_mode)
        finally:
            for editor in self._inspector_editors:
                editor.blockSignals(False)
            self._updating_inspector = False

    def _fit_aperture(self) -> None:
        self.cancel_placement()
        self.view.fit_aperture()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Escape and self.scene.add_mode:
            self.cancel_placement()
            event.accept()
            return
        super().keyPressEvent(event)

    def _update_button_states(self) -> None:
        has_selection = self._selected_index is not None
        self.delete_button.setEnabled(has_selection)
        self.duplicate_button.setEnabled(has_selection)


def main() -> int:
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("LaunchPlane")
    demo = LaunchPlaneWidget(beam_stack=example_beam_stack())
    demo.object_list.setCurrentRow(0)
    window.setCentralWidget(demo)
    window.setMinimumSize(1100, 760)
    window.resize(1280, 860)
    window.show()
    QTimer.singleShot(0, demo.view.fit_aperture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["LaunchPlaneWidget", "example_beam_stack", "main"]
