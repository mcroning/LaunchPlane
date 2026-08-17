"""
Neutral data model for the LaunchPlane package.

These classes intentionally contain no Qt or LCProp dependencies.
They describe an optical launch configuration that can be adapted to
many simulation engines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Tuple
import math


LaunchInputMode = Literal["angle", "transverse_wavevector"]


def _finite(value: float, *, name: str) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def launch_angles_to_transverse_wavevector(
    *,
    angle_x_rad: float,
    angle_y_rad: float,
    wavelength_um: float,
    launch_medium_index: float,
) -> tuple[float, float]:
    """Convert external projected-plane angles to conserved ``(qx, qy)``.

    The angles are measured in the launch medium immediately before the first
    downstream interface. They obey ``tan(angle_x)=u_x/u_z`` and
    ``tan(angle_y)=u_y/u_z`` for a forward unit direction ``u``.
    """

    angle_x = _finite(angle_x_rad, name="angle_x_rad")
    angle_y = _finite(angle_y_rad, name="angle_y_rad")
    wavelength = _finite(wavelength_um, name="wavelength_um")
    index = _finite(launch_medium_index, name="launch_medium_index")
    if wavelength <= 0.0:
        raise ValueError("wavelength_um must be positive")
    if index <= 0.0:
        raise ValueError("launch_medium_index must be positive")
    limit = math.pi / 2.0
    if not -limit < angle_x < limit:
        raise ValueError("angle_x_rad must lie strictly within (-pi/2, pi/2)")
    if not -limit < angle_y < limit:
        raise ValueError("angle_y_rad must lie strictly within (-pi/2, pi/2)")

    tx = math.tan(angle_x)
    ty = math.tan(angle_y)
    direction_norm = math.sqrt(1.0 + tx * tx + ty * ty)
    k_launch = 2.0 * math.pi * index / wavelength
    return (
        k_launch * tx / direction_norm,
        k_launch * ty / direction_norm,
    )


def transverse_wavevector_to_launch_angles(
    *,
    transverse_wavevector_x_rad_per_um: float,
    transverse_wavevector_y_rad_per_um: float,
    wavelength_um: float,
    launch_medium_index: float,
) -> tuple[float, float]:
    """Convert conserved ``(qx, qy)`` to external projected-plane angles."""

    qx = _finite(
        transverse_wavevector_x_rad_per_um,
        name="transverse_wavevector_x_rad_per_um",
    )
    qy = _finite(
        transverse_wavevector_y_rad_per_um,
        name="transverse_wavevector_y_rad_per_um",
    )
    wavelength = _finite(wavelength_um, name="wavelength_um")
    index = _finite(launch_medium_index, name="launch_medium_index")
    if wavelength <= 0.0:
        raise ValueError("wavelength_um must be positive")
    if index <= 0.0:
        raise ValueError("launch_medium_index must be positive")
    k_launch = 2.0 * math.pi * index / wavelength
    q_transverse_squared = qx * qx + qy * qy
    if q_transverse_squared >= k_launch * k_launch:
        raise ValueError(
            "transverse wavevector is not a propagating direction in the "
            "specified launch medium"
        )
    qz = math.sqrt(k_launch * k_launch - q_transverse_squared)
    return math.atan2(qx, qz), math.atan2(qy, qz)


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

    launch_medium_index: float | None = None
    launch_input_mode: LaunchInputMode = "transverse_wavevector"

    phase_rad: float = 0.0

    coherence_group: str = "laser_A"

    enabled: bool = True

    @classmethod
    def from_launch_angles(
        cls,
        *,
        angle_x_rad: float = 0.0,
        angle_y_rad: float = 0.0,
        launch_medium_index: float = 1.0,
        **beam_fields,
    ) -> "BeamDefinition":
        """Construct a beam from external angles in its launch medium."""

        if "tilt_x_rad_per_um" in beam_fields or "tilt_y_rad_per_um" in beam_fields:
            raise TypeError("from_launch_angles does not accept phase-slope fields")
        if "launch_input_mode" in beam_fields:
            raise TypeError("from_launch_angles fixes launch_input_mode='angle'")
        if "launch_medium_index" in beam_fields:
            raise TypeError("launch_medium_index must be passed explicitly")
        wavelength = float(beam_fields.get("wavelength_um", 0.633))
        qx, qy = launch_angles_to_transverse_wavevector(
            angle_x_rad=angle_x_rad,
            angle_y_rad=angle_y_rad,
            wavelength_um=wavelength,
            launch_medium_index=launch_medium_index,
        )
        beam = cls(
            tilt_x_rad_per_um=qx,
            tilt_y_rad_per_um=qy,
            launch_medium_index=float(launch_medium_index),
            launch_input_mode="angle",
            **beam_fields,
        )
        beam.validate()
        return beam

    @property
    def transverse_wavevector_x_rad_per_um(self) -> float:
        """Conserved x wavevector component; alias for the legacy tilt field."""

        return self.tilt_x_rad_per_um

    @property
    def transverse_wavevector_y_rad_per_um(self) -> float:
        """Conserved y wavevector component; alias for the legacy tilt field."""

        return self.tilt_y_rad_per_um

    @property
    def launch_angles_rad(self) -> tuple[float, float]:
        """Return external ``(angle_x, angle_y)`` in the launch medium."""

        if self.launch_medium_index is None:
            raise ValueError("launch medium is unknown; launch angles are unavailable")
        return transverse_wavevector_to_launch_angles(
            transverse_wavevector_x_rad_per_um=self.tilt_x_rad_per_um,
            transverse_wavevector_y_rad_per_um=self.tilt_y_rad_per_um,
            wavelength_um=self.wavelength_um,
            launch_medium_index=self.launch_medium_index,
        )

    @property
    def angle_x_rad(self) -> float:
        return self.launch_angles_rad[0]

    @property
    def angle_y_rad(self) -> float:
        return self.launch_angles_rad[1]

    def with_launch_angles(
        self,
        *,
        angle_x_rad: float,
        angle_y_rad: float,
    ) -> "BeamDefinition":
        """Return an angle-mode copy with the requested external angles."""

        from dataclasses import replace

        if self.launch_medium_index is None:
            raise ValueError("launch_medium_index is required for angle input")
        qx, qy = launch_angles_to_transverse_wavevector(
            angle_x_rad=angle_x_rad,
            angle_y_rad=angle_y_rad,
            wavelength_um=self.wavelength_um,
            launch_medium_index=self.launch_medium_index,
        )
        return replace(
            self,
            tilt_x_rad_per_um=qx,
            tilt_y_rad_per_um=qy,
            launch_input_mode="angle",
        )

    def with_wavelength_um(self, wavelength_um: float) -> "BeamDefinition":
        """Change wavelength while respecting the selected input semantics."""

        from dataclasses import replace

        wavelength = _finite(wavelength_um, name="wavelength_um")
        if wavelength <= 0.0:
            raise ValueError("wavelength_um must be positive")
        if self.launch_input_mode == "angle":
            angle_x, angle_y = self.launch_angles_rad
            updated = replace(self, wavelength_um=wavelength)
            return updated.with_launch_angles(
                angle_x_rad=angle_x,
                angle_y_rad=angle_y,
            )
        return replace(self, wavelength_um=wavelength)

    def with_launch_medium_index(
        self,
        launch_medium_index: float | None,
    ) -> "BeamDefinition":
        """Change launch medium while respecting the selected input semantics."""

        from dataclasses import replace

        if launch_medium_index is None:
            if self.launch_input_mode == "angle":
                raise ValueError("angle mode requires a known launch_medium_index")
            return replace(self, launch_medium_index=None)
        index = _finite(launch_medium_index, name="launch_medium_index")
        if index <= 0.0:
            raise ValueError("launch_medium_index must be positive")
        if self.launch_input_mode == "angle":
            angle_x, angle_y = self.launch_angles_rad
            updated = replace(self, launch_medium_index=index)
            return updated.with_launch_angles(
                angle_x_rad=angle_x,
                angle_y_rad=angle_y,
            )
        return replace(self, launch_medium_index=index)

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

        for field_name in (
            "wavelength_um",
            "power_mW",
            "x_um",
            "y_um",
            "waist_x_um",
            "waist_y_um",
            "tilt_x_rad_per_um",
            "tilt_y_rad_per_um",
            "phase_rad",
        ):
            _finite(getattr(self, field_name), name=field_name)

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

        if self.launch_input_mode not in ("angle", "transverse_wavevector"):
            raise ValueError(
                "launch_input_mode must be 'angle' or 'transverse_wavevector'"
            )
        if self.launch_medium_index is not None:
            index = _finite(
                self.launch_medium_index,
                name="launch_medium_index",
            )
            if index <= 0.0:
                raise ValueError("launch_medium_index must be positive")
        if self.launch_input_mode == "angle":
            if self.launch_medium_index is None:
                raise ValueError("angle mode requires a known launch_medium_index")
            self.launch_angles_rad


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


__all__ = [
    "BeamDefinition",
    "BeamStackDefinition",
    "LaunchInputMode",
    "LaunchPlaneDefinition",
    "launch_angles_to_transverse_wavevector",
    "transverse_wavevector_to_launch_angles",
]
