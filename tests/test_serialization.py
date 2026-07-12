"""Tests for LaunchPlane JSON serialization."""

import json

import pytest

from launchplane.model import BeamDefinition, BeamStackDefinition
from launchplane.serialization import (
    SCHEMA_VERSION,
    beam_stack_from_dict,
    beam_stack_to_dict,
    load_beam_stack_json,
    save_beam_stack_json,
)


def make_stack() -> BeamStackDefinition:
    return BeamStackDefinition(
        beams=(
            BeamDefinition(
                name="Signal",
                wavelength_um=0.633,
                power_mW=0.6,
                x_um=-4.0,
                y_um=-12.0,
                waist_x_um=3.0,
                waist_y_um=5.0,
                tilt_y_rad_per_um=0.018,
                phase_rad=0.25,
                coherence_group="laser_A",
            ),
            BeamDefinition(
                name="Probe",
                wavelength_um=0.532,
                power_mW=0.1,
                x_um=8.0,
                y_um=16.0,
                waist_x_um=2.5,
                waist_y_um=2.5,
                tilt_x_rad_per_um=-0.014,
                coherence_group="laser_B",
                enabled=False,
            ),
        )
    )


def test_beam_stack_dict_round_trip():
    stack = make_stack()

    payload = beam_stack_to_dict(stack)
    restored = beam_stack_from_dict(payload)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert restored == stack


def test_beam_stack_json_file_round_trip(tmp_path):
    stack = make_stack()
    path = tmp_path / "nested" / "beam_stack.json"

    returned_path = save_beam_stack_json(stack, path)
    restored = load_beam_stack_json(path)

    assert returned_path == path
    assert restored == stack

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert len(payload["beams"]) == 2


def test_rejects_unsupported_schema_version():
    payload = beam_stack_to_dict(make_stack())
    payload["schema_version"] = SCHEMA_VERSION + 1

    with pytest.raises(ValueError, match="Unsupported schema_version"):
        beam_stack_from_dict(payload)


def test_rejects_invalid_beam_entry():
    payload = {
        "schema_version": SCHEMA_VERSION,
        "beams": [
            {
                "name": "Invalid",
                "wavelength_um": 0.0,
                "power_mW": 1.0,
                "x_um": 0.0,
                "y_um": 0.0,
                "waist_x_um": 3.0,
                "waist_y_um": 3.0,
                "tilt_x_rad_per_um": 0.0,
                "tilt_y_rad_per_um": 0.0,
                "phase_rad": 0.0,
                "coherence_group": "laser_A",
                "enabled": True,
            }
        ],
    }

    with pytest.raises(ValueError, match="wavelength_um must be positive"):
        beam_stack_from_dict(payload)


def test_rejects_duplicate_beam_names():
    beam = BeamDefinition(name="Same")
    stack = BeamStackDefinition(beams=(beam, beam))

    with pytest.raises(ValueError, match="Duplicate beam name"):
        beam_stack_to_dict(stack)
