"""Runnable PySide6 demonstration of the LaunchPlane canvas."""

from __future__ import annotations

import math
import sys
from dataclasses import replace

from PySide6.QtCore import QLocale, QSize, QEvent, QPointF, QTimer, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QPainterPath, QPen, QColor, QDoubleValidator, QValidator
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from launchplane.canvas import LaunchPlaneScene, LaunchPlaneView
from launchplane.model import (
    BeamDefinition,
    BeamStackDefinition,
    LaunchPlaneDefinition,
)


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

    return BeamStackDefinition(beams=(
        BeamDefinition(name="Probe", x_um=-15, y_um=-25, w1_um=4, w2_um=7,
                       theta_ext_rad=0.35, phi_rad=0, coherence_group="probe"),
        BeamDefinition(name="Control", x_um=4, y_um=2, w1_um=8, w2_um=5,
                       theta_ext_rad=0.6, phi_rad=math.pi, coherence_group="control"),
        BeamDefinition(name="Reference", x_um=18, y_um=28, w1_um=5, w2_um=10,
                       theta_ext_rad=0, coherence_group="probe"),
    ))


class IntentSpinBox(QDoubleSpinBox):
    """Keep invalid pending intent visible instead of Qt's previous-value fixup."""

    def _compact_text(self, value):
        locale = self.locale()
        if not self.isGroupSeparatorShown():
            locale.setNumberOptions(locale.numberOptions() | QLocale.OmitGroupSeparator)
        return locale.toString(value, 'g', 6)

    def _rest_text(self):
        return self.prefix() + self._compact_text(self.value()) + self.suffix()

    def _exponent_input(self, text):
        """Validate exponent input using locale syntax and fixed-point precision.

        Qt's fixed-point spinbox validator rejects some locale-valid exponent
        strings. Accept an exponent only if its numeric
        value fits the unchanged range and decimals; never widen precision.
        """
        token = text
        if self.prefix() and token.startswith(self.prefix()):
            token = token[len(self.prefix()):]
        if self.suffix() and token.endswith(self.suffix()):
            token = token[:-len(self.suffix())]
        token = token.strip()
        if self.locale().exponential().casefold() not in token.casefold():
            return None
        validator = QDoubleValidator(self.minimum(), self.maximum(), -1)
        validator.setLocale(self.locale())
        validator.setNotation(QDoubleValidator.ScientificNotation)
        state = validator.validate(token, len(token))[0]
        value, ok = self.locale().toDouble(token)
        if state == QValidator.Acceptable:
            if (ok and math.isfinite(value) and self.minimum() <= value <= self.maximum()
                    and round(value, self.decimals()) == value):
                return state, value
            return QValidator.Invalid, None
        return state, None

    def textFromValue(self, value):
        return (super().textFromValue(value) if self.hasFocus()
                else self._compact_text(value))

    def valueFromText(self, text):
        if not getattr(self, "_editing", False) and text == self._rest_text():
            return self.value()
        exponent = self._exponent_input(text)
        if exponent is not None:
            return exponent[1] if exponent[0] == QValidator.Acceptable else self.value()
        return super().valueFromText(text)

    def validate(self, text, pos):
        if not getattr(self, "_editing", False) and text == self._rest_text():
            return QValidator.State.Acceptable, text, pos
        exponent = self._exponent_input(text)
        if exponent is not None:
            return exponent[0], text, pos
        return super().validate(text, pos)

    def focusInEvent(self, event):
        self._editing = True
        # Never overwrite a retained pending/invalid draft when focus returns.
        if self.lineEdit().text() == self._rest_text():
            self.lineEdit().setText(self.prefix() +
                QDoubleSpinBox.textFromValue(self, self.value()) + self.suffix())
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._editing = False
        if self.hasAcceptableInput():
            self.lineEdit().setText(self._rest_text())

    def sizeHint(self):
        hint = super().sizeHint()
        fm = self.fontMetrics()
        compact = max(fm.horizontalAdvance(self._compact_text(v))
                      for v in (self.minimum(), self.maximum()))
        full = max(fm.horizontalAdvance(QDoubleSpinBox.textFromValue(self, v))
                   for v in (self.minimum(), self.maximum(), self.value()))
        return QSize(hint.width() + max(0, full - compact) + 12, hint.height())

    def minimumSizeHint(self):
        return self.sizeHint()

    def event(self, event) -> bool:
        # QAbstractSpinBox also fixes up text on Hide (e.g. switching to Results).
        if (event.type() in (QEvent.FocusOut, QEvent.FocusAboutToChange, QEvent.Hide)
                and not self.hasAcceptableInput()):
            return True
        return super().event(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not self.hasAcceptableInput():
            event.accept()
            return
        super().keyPressEvent(event)


class LaunchPlaneWidget(QWidget):
    """Reusable launch-plane canvas with basic beam collection controls."""

    supports_resolved_internal_rays = True
    beamStackChanged = Signal(object)

    def __init__(
        self,
        launch_plane: LaunchPlaneDefinition | None = None,
        beam_stack: BeamStackDefinition | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._resolved_items = []
        self._selected_index: int | None = None
        self._updating_inspector = False
        self._committing_pending_edits = False
        # Session-local ownership follows the immutable beam through replacements.
        # Keep a strong reference: object identity is not a persisted beam ID.
        self._editor_owner = None
        self._editor_drafts = {}
        self.scene = LaunchPlaneScene(launch_plane or LaunchPlaneDefinition(), self)
        self.view = LaunchPlaneView(self.scene, self)
        self.object_list = QListWidget(self)
        self.object_list.setMinimumWidth(170)

        self.add_button = QPushButton("Add beam", self)
        self.delete_button = QPushButton("Delete selected", self)
        self.duplicate_button = QPushButton("Duplicate selected", self)
        self.fit_button = QPushButton("Fit", self)
        self.full_aperture_button = QPushButton("Full Aperture", self)
        self.fit_button.setToolTip("Show all footprints, centers and resolved ray endpoints")
        self.full_aperture_button.setToolTip("Show the full input-face aperture")
        _increase_font_size(self.object_list, 2.0)
        for button in (
            self.add_button,
            self.delete_button,
            self.duplicate_button,
            self.fit_button,
        ):
            _increase_font_size(button, 1.5)

        side_panel = QWidget(self)
        side_panel.setMinimumWidth(430)
        side_panel.setMaximumWidth(480)
        side_layout = QVBoxLayout(side_panel)
        side_layout.setSpacing(5)
        objects_label = QLabel("Objects", side_panel)
        _increase_font_size(objects_label, 1.5)
        side_layout.addWidget(objects_label)
        self.object_list.setMinimumHeight(125)
        self.object_list.setMaximumHeight(145)
        side_layout.addWidget(self.object_list, 1)
        for buttons in ((self.add_button, self.delete_button),
                        (self.duplicate_button,),
                        (self.fit_button, self.full_aperture_button)):
            row = QHBoxLayout()
            for button in buttons:
                row.addWidget(button)
            side_layout.addLayout(row)

        self.inspector = self._create_inspector()
        self.inspector_scroll = QScrollArea(self)
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_scroll.setFrameShape(QScrollArea.NoFrame)
        self.inspector_scroll.setWidget(self.inspector)
        self.inspector_scroll.setMinimumHeight(160)
        side_layout.addWidget(self.inspector_scroll, 3)

        layout = QVBoxLayout(self)
        self.splitter = QSplitter(Qt.Horizontal, self)
        # Device-space annotations belong in a wrapping layout, not at
        # physical scene anchors whose separation changes with zoom.
        self.canvas_panel = QWidget(self)
        canvas_layout = QVBoxLayout(self.canvas_panel)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_title = QLabel(
            "Input face",
            self.canvas_panel,
        )
        self.canvas_bounds = QLabel(self.canvas_panel)
        for label in (self.canvas_title, self.canvas_bounds):
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            canvas_layout.addWidget(label)
        self._update_canvas_annotations()
        self.scene.sceneAboutToReset.connect(self._update_canvas_annotations)
        axes_layout = QGridLayout()
        self.x_axis_label = QLabel("x (µm)", self.canvas_panel)
        self.y_axis_label = QLabel("y (µm)", self.canvas_panel)
        self.x_axis_label.setAlignment(Qt.AlignCenter)
        self.y_axis_label.setAlignment(Qt.AlignCenter)
        axes_layout.addWidget(self.y_axis_label, 0, 0)
        axes_layout.addWidget(self.view, 0, 1)
        axes_layout.addWidget(self.x_axis_label, 1, 1)
        axes_layout.setColumnStretch(1, 1)
        axes_layout.setRowStretch(0, 1)
        canvas_layout.addLayout(axes_layout, 1)
        self.splitter.addWidget(self.canvas_panel)
        self.splitter.addWidget(side_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([900, 360])
        layout.addWidget(self.splitter, 1)
        # A bounded, wrapping region preserves qualifications without stealing
        # the canvas height when many beams are present. Overflow is scrollable.
        self.execution_status.setMinimumWidth(0)
        self.execution_status.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        self.status_scroll = QScrollArea(self)
        self.status_scroll.setWidgetResizable(True)
        self.status_scroll.setFrameShape(QScrollArea.NoFrame)
        self.status_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.status_scroll.setWidget(self.execution_status)
        line_height = self.execution_status.fontMetrics().lineSpacing()
        self.status_scroll.setMinimumHeight(3 * line_height)
        self.status_scroll.setMaximumHeight(6 * line_height)
        layout.addWidget(self.status_scroll)

        self.object_list.currentRowChanged.connect(self._select_scene_beam)
        self._inverse_resolver = None
        self._preview_current = False
        self.scene.exitRequested.connect(self._exit_requested)
        self.scene.sceneAboutToReset.connect(self.clear_resolved_preview)
        self.scene.beamSelected.connect(self._select_list_beam)
        self.scene.beamMoved.connect(self._beam_moved)
        self.scene.beamChanged.connect(self._beam_changed)
        self.scene.addBeamRequested.connect(self._place_beam)
        self.add_button.clicked.connect(self.add_beam)
        self.delete_button.clicked.connect(self.delete_selected)
        self.duplicate_button.clicked.connect(self.duplicate_selected)
        self.fit_button.clicked.connect(self.view.fit_all)
        self.full_aperture_button.clicked.connect(self._fit_aperture)

        self.cancel_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.cancel_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.cancel_shortcut.activated.connect(self.cancel_placement)

        self._beam_stack = BeamStackDefinition()
        self.set_beam_stack(beam_stack or BeamStackDefinition())

    def _create_inspector(self) -> QGroupBox:
        inspector = QGroupBox("Selected beam", self)
        form = QFormLayout(inspector)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

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
        self.x_spin = self._create_spin_box(-1.0e6, 1.0e6, 3, " µm")
        self.y_spin = self._create_spin_box(-1.0e6, 1.0e6, 3, " µm")
        self.w1_spin = self._create_spin_box(0.001, 1.0e6, 3, " µm")
        self.w2_spin = self._create_spin_box(0.001, 1.0e6, 3, " µm")
        self.theta_spin = self._create_spin_box(-89.999999, 89.999999, 6, " °")
        self.phi_spin = self._create_spin_box(0, 360, 6, " °")
        self.psi_spin = self._create_spin_box(0, 360, 6, " °")
        self.n_ext_spin = self._create_spin_box(0.000001, 100, 6, "")
        self.phase_spin = self._create_spin_box(-1.0e6, 1.0e6, 6, " rad")
        self.derived_k = QLabel(inspector)
        self.derived_k.setWordWrap(True)
        self.derived_k.setMinimumWidth(0)
        self.derived_k.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Minimum)
        self.execution_status = QLabel(
            "Intent editor only — physical launch resolver not yet implemented. "
            "No sampled fields, refraction, footprint or physical power execution.", inspector)
        self.execution_status.setWordWrap(True)
        self.power_spin.setToolTip("Incident power through the external beam-normal plane, before interface/screens.")
        self.w1_spin.setToolTip("External beam-normal 1/e field (1/e² intensity) radius.")
        self.w2_spin.setToolTip(self.w1_spin.toolTip())
        self.theta_spin.setToolTip("Signed external tilt from +z at fixed phi; grazing incidence is unsupported.")
        self.phi_spin.setToolTip("Azimuth from +x toward +y; direction is undefined at normal incidence.")
        self.psi_spin.setToolTip("Profile roll, independent of direction; referenced to +x at normal incidence.")
        self.phase_spin.setToolTip("Phase at the beam-axis/entrance intersection (x0, y0, z=0).")
        self.n_ext_spin.setToolTip("Index of the homogeneous medium immediately outside the material entrance.")
        for label, editor in (
            ("Name", self.name_edit), ("Enabled", self.enabled_checkbox),
            ("Incident power", self.power_spin), ("Vacuum wavelength", self.wavelength_spin),
            ("Entrance x0", self.x_spin), ("Entrance y0", self.y_spin),
            ("External normal radius w1", self.w1_spin), ("External normal radius w2", self.w2_spin),
            ("External theta", self.theta_spin), ("Azimuth phi", self.phi_spin),
            ("Profile roll psi", self.psi_spin), ("External index n_ext", self.n_ext_spin),
            ("Entrance phase", self.phase_spin), ("Laser", self.laser_combo),
        ):
            editor.setAccessibleName(label)
            form.addRow(label, editor)
        form.addRow(QLabel("Derived kx, ky (rad/µm)", inspector))
        form.addRow(self.derived_k)
        self._numeric_editors = {
            "power_mW": self.power_spin, "wavelength_um": self.wavelength_spin,
            "x_um": self.x_spin, "y_um": self.y_spin,
            "w1_um": self.w1_spin, "w2_um": self.w2_spin,
            "n_ext": self.n_ext_spin, "phase_rad": self.phase_spin,
        }
        self._angular_editors = {
            "theta_ext_rad": self.theta_spin, "phi_rad": self.phi_spin, "psi_rad": self.psi_spin,
        }
        self._inspector_editors = (
            self.name_edit, self.enabled_checkbox, self.laser_combo,
            *self._numeric_editors.values(), *self._angular_editors.values(),
        )
        self.name_edit.editingFinished.connect(self._name_edited)
        self.laser_combo.textActivated.connect(self._laser_edited)
        self.laser_combo.lineEdit().editingFinished.connect(self._laser_edited)
        self.enabled_checkbox.toggled.connect(self._enabled_changed)
        for field_name, editor in self._numeric_editors.items():
            editor.valueChanged.connect(
                lambda value, field=field_name: self._apply_selected_changes(**{field: value}))
        for field_name, editor in self._angular_editors.items():
            editor.valueChanged.connect(
                lambda value, field=field_name: self._apply_selected_changes(**{field: math.radians(value)}))
        _increase_font_size(inspector, 1.5)
        return inspector

    def _create_spin_box(
        self,
        minimum: float,
        maximum: float,
        decimals: int,
        suffix: str,
    ) -> QDoubleSpinBox:
        editor = IntentSpinBox(self)
        editor.setDecimals(decimals)
        editor.setRange(minimum, maximum)
        editor.setSuffix(suffix)
        editor.setKeyboardTracking(False)
        return editor

    def _capture_pending_edits(self) -> None:
        if self._updating_inspector or self._editor_owner is None:
            return
        drafts = {}
        for field, editor in {**self._numeric_editors, **self._angular_editors}.items():
            text = editor.lineEdit().text()
            if not editor.hasAcceptableInput() or editor.valueFromText(text) != editor.value():
                drafts[field] = text
        key = id(self._editor_owner)
        if drafts:
            self._editor_drafts[key] = (self._editor_owner, drafts)
        else:
            self._editor_drafts.pop(key, None)

    def _transfer_editor_owner(self, previous, replacement) -> None:
        self._capture_pending_edits()
        saved = self._editor_drafts.pop(id(previous), None)
        if saved is not None:
            self._editor_drafts[id(replacement)] = (replacement, saved[1])
        if self._editor_owner is previous:
            self._editor_owner = replacement

    def commit_pending_edits(self) -> None:
        """Validate every beam's drafts before applying canonical model updates.

        Invalid text survives selection and unrelated model refreshes. Qt owns
        parsing/ranges; the model owns scientific validation. No request escapes
        with a partially validated stack, including drafts on unselected beams.
        """
        if self._committing_pending_edits:
            return
        self._committing_pending_edits = True
        try:
            self._capture_pending_edits()
            editors = {**self._numeric_editors, **self._angular_editors}
            updates = []
            for index, beam in enumerate(self._beam_stack.beams):
                changes = {}
                drafts = self._editor_drafts.get(id(beam), (beam, {}))[1]
                for field, text in drafts.items():
                    editor = editors[field]
                    if editor.validate(text, 0)[0] != QValidator.Acceptable:
                        self.object_list.setCurrentRow(index)
                        self.inspector_scroll.ensureWidgetVisible(editor)
                        editor.setFocus()
                        raise ValueError(
                            f"Invalid pending beam edit: {editor.accessibleName()} "
                            f"({text!r}) in {beam.name}; correct the value before Run."
                        )
                    value = editor.valueFromText(text)
                    changes[field] = math.radians(value) if field in self._angular_editors else value
                if index == self._selected_index:
                    name = self._unique_name(self.name_edit.text(), exclude_index=index)
                    group = self.laser_combo.currentText().strip()
                    if not group:
                        raise ValueError("Invalid pending beam edit: Laser must not be empty.")
                    if name != beam.name:
                        changes['name'] = name
                    if group != beam.coherence_group:
                        changes['coherence_group'] = group
                updated = replace(beam, **changes)
                updated.validate()
                updates.append(updated)
            BeamStackDefinition(beams=tuple(updates)).validate()
            # Only after all drafts validate can widget/model synchronization
            # replace them. Ordinary field commits clear only their own draft.
            self._editor_drafts.clear()
            self._editor_owner = None
            self._apply_beam_updates(updates)
        finally:
            self._committing_pending_edits = False

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
        self._capture_pending_edits()
        retained = {id(beam) for beam in beam_stack.beams}
        if any(key not in retained for key in self._editor_drafts):
            raise ValueError("Unresolved beam edits must be corrected before replacing or deleting their beam.")
        self._beam_stack = beam_stack
        self.clear_resolved_preview()
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
        self.view.arrange_beam_labels()

    def _update_canvas_annotations(self) -> None:
        self.canvas_bounds.setText(
            f"x: {self.scene.x_min:g} … {self.scene.x_max:g} µm    "
            f"y: {self.scene.y_min:g} … {self.scene.y_max:g} µm"
        )

    def set_inverse_resolver(self, resolver) -> None:
        """Host callback (beam, exit_x, exit_y) -> (signed theta, phi), in radians.

        The host owns refraction and rejection of unreachable exits. LaunchPlane
        neither persists endpoints nor provides a fallback optical model.
        """
        self._inverse_resolver = resolver

    def _exit_requested(self, index: int, x: float, y: float) -> None:
        if self._inverse_resolver is None:
            self.execution_status.setText("Direction editing unavailable: host inverse resolver required.")
            return
        try:
            beam = self._beam_stack.beams[index]
            theta, phi = self._inverse_resolver(beam, x, y)
            updated = replace(beam, theta_ext_rad=theta, phi_rad=phi)
            updated.validate()
        except ValueError as exc:
            self.execution_status.setText(f"Direction unchanged: {exc}")
            return
        self._select_scene_beam(index)
        self._apply_selected_beam(updated)

    def _publish_stack(self) -> None:
        # Synchronous host redelivery is atomic for the focused/mouse-grabbed
        # handles. Hiding them between invalidation and redelivery loses Qt's
        # mouse grab. Without redelivery, invalidate the old geometry explicitly.
        self._preview_current = False
        self.beamStackChanged.emit(self._beam_stack)
        if not self._preview_current:
            self.clear_resolved_preview()

    def clear_resolved_preview(self, _stack=None, *, invalidate_rays=True) -> None:
        """Invalidate host geometry whenever the physical intent changes."""
        for item in self._resolved_items:
            if item.scene() is self.scene:
                self.scene.removeItem(item)
        self._resolved_items.clear()
        if invalidate_rays:
            self._preview_current = False
            for beam_item in self.scene.beam_items:
                beam_item.set_resolved_exit(None)
        self.execution_status.setText(
            "Internal ray unavailable. Material-aware preview requires a compatible host resolver."
        )

    def set_resolved_preview(self, contours, *, description: str, ray_endpoints=None) -> None:
        """Display host-supplied laboratory (x,y) contours in physical micrometres.

        This seam does not compute refraction or infer geometry from intent.
        Contours use x-right/y-up; the Qt sign conversion is presentation only.
        No derived value is persisted into the physical beam definition.
        """
        prepared = []
        for contour in contours:
            points = tuple((float(x), float(y)) for x, y in contour)
            if len(points) < 3 or not all(math.isfinite(v) for p in points for v in p):
                raise ValueError("resolved contours require at least three finite points")
            prepared.append(points)
        endpoints = None
        if ray_endpoints is not None:
            endpoints = tuple(None if point is None else tuple(map(float, point))
                              for point in ray_endpoints)
            if len(endpoints) != len(self.scene.beam_items) or any(
                point is not None and (len(point) != 2 or not all(map(math.isfinite, point)))
                for point in endpoints
            ):
                raise ValueError("resolved ray endpoints must match beam indices and be finite x,y pairs")
        self.clear_resolved_preview(invalidate_rays=False)
        self._preview_current = True
        pen = QPen(QColor("#62cddd"), 1.8)
        pen.setCosmetic(True)
        pen.setStyle(Qt.DashLine)
        for points in prepared:
            path = QPainterPath(QPointF(points[0][0], -points[0][1]))
            for x, y in points[1:]:
                path.lineTo(x, -y)
            path.closeSubpath()
            item = self.scene.addPath(path, pen)
            item.setAcceptedMouseButtons(Qt.NoButton)
            # Above the opaque aperture and axes (z=0), below beam handles
            # and internal rays/center markers (z=10).
            item.setZValue(1.0)
            self._resolved_items.append(item)
        if endpoints is None:
            for item in self.scene.beam_items:
                item.set_resolved_exit(None)
        else:
            for item, endpoint in zip(self.scene.beam_items, endpoints):
                item.set_resolved_exit(endpoint if item.beam.enabled else None)
        self.view.arrange_beam_labels()
        self.execution_status.setText(str(description) + (
            " Internal ray unavailable: host did not supply endpoints." if endpoints is None else ""))

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
            BeamDefinition(name=self._unique_name("Beam")),
            x_um=x_um,
            y_um=y_um,
        )
        beams = (*self._beam_stack.beams, beam)
        self.cancel_placement()
        self.set_beam_stack(BeamStackDefinition(beams=beams), len(beams) - 1)
        self._publish_stack()

    def delete_selected(self) -> None:
        self.cancel_placement()
        index = self._selected_index
        if index is None:
            return
        self._capture_pending_edits()
        if id(self._beam_stack.beams[index]) in self._editor_drafts:
            self.execution_status.setText("Correct pending beam edits before deleting this beam.")
            return
        beams = self._beam_stack.beams[:index] + self._beam_stack.beams[index + 1 :]
        selected = min(index, len(beams) - 1) if beams else None
        self.set_beam_stack(BeamStackDefinition(beams=beams), selected)
        self._publish_stack()

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
        self._publish_stack()

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
        previous = beams[index]
        beams[index] = replace(previous, x_um=x_um, y_um=y_um)
        self._transfer_editor_owner(previous, beams[index])
        self._beam_stack = BeamStackDefinition(beams=tuple(beams))
        self._sync_inspector()
        self._publish_stack()

    def _beam_changed(self, index: int, beam: BeamDefinition) -> None:
        beams = list(self._beam_stack.beams)
        self._transfer_editor_owner(beams[index], beam)
        beams[index] = beam
        self._beam_stack = BeamStackDefinition(beams=tuple(beams))
        self._sync_inspector()
        self._publish_stack()

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

    def _apply_selected_changes(self, **changes) -> None:
        index = self._selected_index
        if self._updating_inspector or index is None or not changes:
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
        beams = list(self._beam_stack.beams)
        beams[index] = beam
        self._apply_beam_updates(beams)

    def _apply_beam_updates(self, beams) -> None:
        """Publish a fully validated stack once, for normal or pending commits."""
        beam_stack = BeamStackDefinition(beams=tuple(beams))
        beam_stack.validate()
        changed = [i for i, (old, new) in enumerate(zip(self._beam_stack.beams, beams))
                   if old != new]
        if not changed:
            self._sync_inspector()
            return
        self.cancel_placement()
        for index in changed:
            self._transfer_editor_owner(self._beam_stack.beams[index], beams[index])
        self._beam_stack = beam_stack
        for index in changed:
            item = self.scene.beam_items[index]
            item.blockSignals(True)
            item.refresh(beams[index])
            item.blockSignals(False)
            self._update_object_list_item(index)
        self._sync_inspector()
        self._publish_stack()

    def _update_object_list_item(self, index: int) -> None:
        beam = self._beam_stack.beams[index]
        self.object_list.item(index).setText(
            f"{index + 1}. {beam.name}  [{beam.coherence_group}]"
        )

    def _sync_inspector(self) -> None:
        self._capture_pending_edits()
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
                self._editor_owner = beam
                self.name_edit.setText(beam.name)
                self.enabled_checkbox.setChecked(beam.enabled)
                self.laser_combo.setCurrentText(beam.coherence_group)
                for field_name, editor in self._numeric_editors.items():
                    editor.setValue(getattr(beam, field_name))
                for field_name, editor in self._angular_editors.items():
                    editor.setValue(math.degrees(getattr(beam, field_name)))
                for field, text in self._editor_drafts.get(id(beam), (beam, {}))[1].items():
                    editor = {**self._numeric_editors, **self._angular_editors}[field]
                    editor.lineEdit().setText(text)
                kx, ky = beam.transverse_wavevector_rad_per_um
                self.derived_k.setText(f"{kx:.8g}, {ky:.8g} (read-only)")
            else:
                self._editor_owner = None
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
