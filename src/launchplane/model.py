"""
Neutral data model for the LaunchPlane package.

These classes intentionally contain no Qt or LCProp dependencies.
They describe an optical launch configuration that can be adapted to
many simulation engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple
import math


@dataclass(frozen=True)
class BeamDefinition:
    """
    One scalar optical beam.

    Coordinates use the LaunchPlane convention:

        x : LC thickness (vertical)
        y : transverse (horizontal)

    All lengths are in microns.
    """

    name: str = "Beam"

    wavelength_um: float = 0.633
    power_mW: float = 1.0

    x_um: float = 0.0
    y_um: float = 0.0

    waist_x_um: float = 3.0
    waist_y_um: float = 3.0

    tilt_x_rad_per_um: float = 0.0
    tilt_y_rad_per_um: float = 0.0

    phase_rad: float = 0.0

    coherence_group: str = "laser_A"

    enabled: bool = True

    @property
    def tilt_magnitude(self) -> float:
        return math.hypot(
            self.tilt_x_rad_per_um,
            self.tilt_y_rad_per_um,
        )

    @property
    def tilt_angle_rad(self) -> float:
        return math.atan2(
            self.tilt_x_rad_per_um,
            self.tilt_y_rad_per_um,
        )

    def validate(self) -> None:

        if self.wavelength_um <= 0:
            raise ValueError("wavelength_um must be positive")

        if self.power_mW < 0:
            raise ValueError("power_mW must be non-negative")

        if self.waist_x_um <= 0:
            raise ValueError("waist_x_um must be positive")

        if self.waist_y_um <= 0:
            raise ValueError("waist_y_um must be positive")

        if not self.coherence_group.strip():
            raise ValueError("coherence_group must be non-empty")


@dataclass(frozen=True)
class BeamStackDefinition:
    """
    Ordered collection of launch beams.

    The ordering is preserved because some propagation engines
    associate channels with beam order.
    """

    beams: Tuple[BeamDefinition, ...] = field(default_factory=tuple)

    def validate(self) -> None:

        names = set()

        for beam in self.beams:

            beam.validate()

            if beam.name in names:
                raise ValueError(
                    f"Duplicate beam name '{beam.name}'."
                )

            names.add(beam.name)

    @property
    def total_power_mW(self) -> float:

        return sum(
            beam.power_mW
            for beam in self.beams
            if beam.enabled
        )

    @property
    def coherence_groups(self):
        """Laser names in first-use order, derived from beam membership."""

        return tuple(dict.fromkeys(beam.coherence_group for beam in self.beams))


@dataclass(frozen=True)
class LaunchPlaneDefinition:
    """
    Physical launch aperture.

    This is intentionally separate from BeamStackDefinition so that
    the same beam stack may be launched into different experiments.
    """

    x_aperture_um: float = 75.0
    y_aperture_um: float = 100.0

    def validate(self) -> None:

        if self.x_aperture_um <= 0:
            raise ValueError(
                "x_aperture_um must be positive"
            )

        if self.y_aperture_um <= 0:
            raise ValueError(
                "y_aperture_um must be positive"
            )
