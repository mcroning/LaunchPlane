"""External-angle and transverse-wavevector model tests."""

from dataclasses import replace
import math

import pytest

from launchplane.model import (
    BeamDefinition,
    launch_angles_to_transverse_wavevector,
    transverse_wavevector_to_launch_angles,
)


def test_direct_constructor_preserves_legacy_wavevector_semantics():
    beam = BeamDefinition(
        wavelength_um=0.633,
        tilt_x_rad_per_um=0.1,
        tilt_y_rad_per_um=-0.2,
    )

    assert beam.launch_input_mode == "transverse_wavevector"
    assert beam.launch_medium_index is None
    beam.validate()

    changed = beam.with_wavelength_um(0.532)
    assert changed.tilt_x_rad_per_um == beam.tilt_x_rad_per_um
    assert changed.tilt_y_rad_per_um == beam.tilt_y_rad_per_um


def test_direct_constructor_accepts_large_legacy_wavevector():
    beam = BeamDefinition(tilt_x_rad_per_um=20.0)

    beam.validate()
    assert beam.launch_input_mode == "transverse_wavevector"
    assert beam.launch_medium_index is None


def test_zero_external_angle_has_zero_transverse_wavevector():
    beam = BeamDefinition.from_launch_angles(angle_x_rad=0.0, angle_y_rad=0.0)

    assert beam.tilt_x_rad_per_um == 0.0
    assert beam.tilt_y_rad_per_um == 0.0
    assert beam.launch_angles_rad == (0.0, 0.0)


def test_required_air_launch_case():
    beam = BeamDefinition.from_launch_angles(
        wavelength_um=0.633,
        angle_x_rad=0.1,
        angle_y_rad=0.0,
        launch_medium_index=1.0,
    )

    assert beam.tilt_x_rad_per_um == pytest.approx(0.9909508004, abs=5e-11)
    assert beam.tilt_y_rad_per_um == 0.0


def test_angle_conversion_is_odd():
    positive = BeamDefinition.from_launch_angles(
        angle_x_rad=0.17,
        angle_y_rad=-0.08,
    )
    negative = BeamDefinition.from_launch_angles(
        angle_x_rad=-0.17,
        angle_y_rad=0.08,
    )

    assert negative.tilt_x_rad_per_um == pytest.approx(
        -positive.tilt_x_rad_per_um
    )
    assert negative.tilt_y_rad_per_um == pytest.approx(
        -positive.tilt_y_rad_per_um
    )


def test_two_axis_angles_form_one_normalized_direction():
    angle_x = 0.3
    angle_y = -0.2
    wavelength = 0.7
    index = 1.4
    qx, qy = launch_angles_to_transverse_wavevector(
        angle_x_rad=angle_x,
        angle_y_rad=angle_y,
        wavelength_um=wavelength,
        launch_medium_index=index,
    )
    tx = math.tan(angle_x)
    ty = math.tan(angle_y)
    norm = math.sqrt(1.0 + tx * tx + ty * ty)
    k_launch = 2.0 * math.pi * index / wavelength

    assert qx == pytest.approx(k_launch * tx / norm)
    assert qy == pytest.approx(k_launch * ty / norm)
    assert math.hypot(qx, qy) < k_launch
    assert qx != pytest.approx(k_launch * math.sin(angle_x))


@pytest.mark.parametrize(
    ("angle_x", "angle_y"),
    [(0.0, 0.0), (0.31, 0.0), (0.0, -0.27), (0.22, -0.19)],
)
def test_angle_wavevector_round_trip(angle_x, angle_y):
    qx, qy = launch_angles_to_transverse_wavevector(
        angle_x_rad=angle_x,
        angle_y_rad=angle_y,
        wavelength_um=0.532,
        launch_medium_index=1.33,
    )

    recovered = transverse_wavevector_to_launch_angles(
        transverse_wavevector_x_rad_per_um=qx,
        transverse_wavevector_y_rad_per_um=qy,
        wavelength_um=0.532,
        launch_medium_index=1.33,
    )

    assert recovered == pytest.approx((angle_x, angle_y), abs=2e-16)


def test_wavevector_scales_with_inverse_wavelength_and_launch_index():
    reference = BeamDefinition.from_launch_angles(
        wavelength_um=0.8,
        launch_medium_index=1.0,
        angle_x_rad=0.12,
    )
    shorter = BeamDefinition.from_launch_angles(
        wavelength_um=0.4,
        launch_medium_index=1.0,
        angle_x_rad=0.12,
    )
    denser = BeamDefinition.from_launch_angles(
        wavelength_um=0.8,
        launch_medium_index=1.5,
        angle_x_rad=0.12,
    )

    assert shorter.tilt_x_rad_per_um == pytest.approx(
        2.0 * reference.tilt_x_rad_per_um
    )
    assert denser.tilt_x_rad_per_um == pytest.approx(
        1.5 * reference.tilt_x_rad_per_um
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"angle_x_rad": math.nan},
        {"angle_y_rad": math.inf},
        {"angle_x_rad": math.pi / 2.0},
        {"angle_y_rad": -math.pi / 2.0},
        {"wavelength_um": 0.0},
        {"launch_medium_index": 0.0},
    ],
)
def test_invalid_angle_inputs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        BeamDefinition.from_launch_angles(**kwargs)


def test_nonpropagating_inverse_is_rejected_but_wavevector_mode_can_store_it():
    beam = BeamDefinition(
        tilt_x_rad_per_um=20.0,
        launch_medium_index=1.0,
        launch_input_mode="transverse_wavevector",
    )
    beam.validate()

    with pytest.raises(ValueError, match="not a propagating direction"):
        _ = beam.launch_angles_rad


def test_angle_mode_wavelength_and_index_edits_preserve_angles():
    beam = BeamDefinition.from_launch_angles(
        wavelength_um=0.633,
        launch_medium_index=1.0,
        angle_x_rad=0.1,
        angle_y_rad=-0.05,
    )
    q_before = (beam.tilt_x_rad_per_um, beam.tilt_y_rad_per_um)

    wavelength_changed = beam.with_wavelength_um(0.532)
    index_changed = beam.with_launch_medium_index(1.5)

    assert wavelength_changed.launch_angles_rad == pytest.approx(
        beam.launch_angles_rad
    )
    assert index_changed.launch_angles_rad == pytest.approx(beam.launch_angles_rad)
    assert wavelength_changed.tilt_x_rad_per_um != q_before[0]
    assert index_changed.tilt_y_rad_per_um != q_before[1]


def test_wavevector_mode_wavelength_and_index_edits_preserve_wavevector():
    beam = BeamDefinition(
        tilt_x_rad_per_um=0.7,
        tilt_y_rad_per_um=-0.4,
        launch_medium_index=1.0,
        launch_input_mode="transverse_wavevector",
    )
    q_before = (beam.tilt_x_rad_per_um, beam.tilt_y_rad_per_um)

    wavelength_changed = beam.with_wavelength_um(0.532)
    index_changed = beam.with_launch_medium_index(1.5)

    assert (
        wavelength_changed.tilt_x_rad_per_um,
        wavelength_changed.tilt_y_rad_per_um,
    ) == q_before
    assert (
        index_changed.tilt_x_rad_per_um,
        index_changed.tilt_y_rad_per_um,
    ) == q_before


def test_angle_mode_requires_known_launch_medium():
    beam = replace(
        BeamDefinition(),
        launch_medium_index=None,
        launch_input_mode="angle",
    )

    with pytest.raises(ValueError, match="known launch_medium_index"):
        beam.validate()
