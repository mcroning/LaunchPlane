# LaunchPlane

LaunchPlane is a reusable GUI and data-model component for defining and
visualizing optical beam launch conditions. It provides an interactive
launch-plane editor together with beam definitions and JSON serialization.

## Launch-angle semantics

The normal editor specifies external launch angles in radians. These angles
are measured in the LaunchPlane launch medium immediately before the first
downstream optical or material interface. Air, with launch-medium refractive
index `1.0`, is the default for newly created angle-mode beams. They are not
internal crystal angles, and LaunchPlane does not calculate downstream
refraction.

Each beam's `wavelength_um` is its vacuum wavelength. LaunchPlane converts the
external projected-plane angles to the conserved transverse wavevector
components `qx` and `qy` in rad/µm. The stored compatibility fields
`tilt_x_rad_per_um` and `tilt_y_rad_per_um` contain those components; they are
phase slopes, not angles. They remain the canonical interchange quantities,
and LCProp receives them unchanged.

The advanced transverse-wavevector editor allows direct phase-slope input.
Legacy schema-version-1 records are loaded in that advanced mode with an
unknown launch medium, preserving their stored phase slopes exactly without
assuming that they originated in air.

## Project status

LaunchPlane is experimental, developmental, and pre-release software. Its API
and package structure may change, and the current interface is not yet a stable
public API. This repository is published to preserve provenance and make the
working implementation reproducible and inspectable; it is not currently a
PyPI release.

## Development installation

From a local checkout, install LaunchPlane in editable mode:

```bash
python -m pip install -e .
```

The current runtime dependency is PySide6, which is installed through the
package metadata.

## Current import

The currently supported import for the primary GUI component is:

```python
from launchplane.launchpane import LaunchPlaneWidget
```

No package-level re-export is currently provided.

## Naming

- Product and repository name: **LaunchPlane**
- Python distribution and import namespace: `launchplane`
- Primary GUI module: `launchplane.launchpane`
- Main widget: `LaunchPlaneWidget`

These names describe the present developmental implementation and are not an
API-stability commitment.

## Relationship to LCProp

LCProp currently uses this working LaunchPlane implementation during
development and fresh-clone validation. Publishing LaunchPlane provides an
inspectable, reproducible source for that development configuration. It does
not determine LCProp's future launch-plane architecture or make LaunchPlane a
permanent LCProp runtime dependency.

LCProp may later incorporate its own material-neutral launch pane while
maintaining compatibility with the independent LaunchPlane product.

## License

LaunchPlane is licensed under the BSD 3-Clause License. See [LICENSE](LICENSE).
