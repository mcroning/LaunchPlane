# LaunchPlane

LaunchPlane is an experimental, pre-release optical beam-intent model and
PySide6 editor. The physical-intent milestone is an intentional breaking API
and serialization change. It edits external incident beams; it does **not**
yet construct physical material-interface launch fields.

## Physical intent

`launchplane.model.BeamDefinition` is an immutable, keyword-only, headless
model. Construction validates finite inputs. All lengths are micrometres,
angles are radians, and power is mW; the editor displays direction and roll
in degrees.

| Field | Meaning |
| --- | --- |
| `wavelength_um` | Vacuum wavelength, positive |
| `power_mW` | Nonnegative incident physical power through the external beam-normal plane, before the interface and laboratory screens |
| `n_ext` | Positive index immediately outside the material entrance, default 1 |
| `theta_ext_rad` | Signed external tilt from +z at fixed phi; `-pi/2 < theta < pi/2` |
| `phi_rad` | Azimuth from +x toward +y, normalized modulo `2*pi` |
| `w1_um`, `w2_um` | Positive external beam-normal 1/e field (1/e² intensity) radii |
| `psi_rad` | Independent profile roll, modulo `2*pi`; referenced to laboratory +x at normal incidence |
| `x_um`, `y_um` | Axis intersection with the entrance plane z=0; no implicit targeting |
| `phase_rad` | Phase at that axis/entrance intersection |
| `name`, `coherence_group`, `enabled` | Beam label, coherence membership and enabled state |
| `profile` | Only `collimated_gaussian` is supported in this physical-intent milestone |

Equal radii describe a circular incident beam. Roll does not change propagation
direction; phi is not roll. At theta=0, phi is retained as editor intent but has
no physical directional significance. Zero power is valid intent; it does not
establish a dark-relaxation solver contract. Names/order are not stable carrier
identifiers.

Read-only `external_direction`, `external_wavevector_rad_per_um` and
`transverse_wavevector_rad_per_um` derive direction and k from external intent:

```text
s = (sin(theta)*cos(phi), sin(theta)*sin(phi), cos(theta))
k_ext = 2*pi*n_ext/wavelength_um
(kx, ky, kz_ext) = k_ext*s
```

There is no editable kx/ky mode. Changing wavelength or n_ext leaves theta/phi
unchanged. Use `dataclasses.replace` to edit immutable definitions.

## Editor and arrows

The laboratory face uses x horizontal/right, y vertical/up; the Qt scene uses
`(x, -y)`. Click to place, drag a center to move, and select to edit the inspector.
The `Input face` caption and numeric beam labels keep the canvas concise.
Theta can be positive or negative without changing phi; the entered sign is
preserved in schema 4. Drag the center to position a beam without changing its
direction. Drag the physical-exit arrowhead for approximate direction editing;
numeric signed theta/phi remain the exact route. Roll stays independent.
Arrowheads win overlapping hit targets, including over another beam's center.
At zero tilt the coincident arrowhead remains interactive; drag it away to expose
the center. Both handles have device-sized hit targets under zoom and Fit.
Click a handle and use arrow keys for one-pixel nudges, Shift for ten pixels.
Spinbox focus retains ordinary spinbox arrow-key behavior.

A host installs `set_inverse_resolver(callback)`, where
`callback(beam, exit_x_um, exit_y_um)` returns `(theta_ext_rad, phi_rad)` or raises
`ValueError` with an availability reason. Product owns interface inversion and
signed-branch continuity; LaunchPlane contains no refraction fallback. Without
this callback direction editing is unavailable. Stack-change delivery and
synchronous preview redelivery preserve the active mouse grab; missing redelivery
invalidates previous geometry. Manual reciprocal crossing is possible by dragging
each arrowhead onto the other entrance; no persistent Target mode is created.

A compatible host supplies physical exit positions `(x0 + L*kx/kz_int,
y0 + L*ky/kz_int)` to `set_resolved_preview(..., ray_endpoints=...)`, one pair
(or `None`) per beam in stack order, including disabled beams. These internal
rays scale with physical scene coordinates, never with a bounded pixel length.
Disabled beams have no ray. Normal incidence retains its center and coincident
interactive arrowhead, with zero physical shaft length.
Without host endpoints the ray is explicitly unavailable.

`Fit` reveals all physical centers, footprints and exit points. `Full Aperture`
returns to the complete input-face extent. Neither changes launch geometry.

External beam-normal radii are not laboratory footprint radii. A compatible
host supplies laboratory contours and qualified text via `set_resolved_preview`.
Dashed contours scale in physical scene coordinates. LaunchPlane does
not compute material index, Snell refraction, flux normalization or capture.
Without a host, the editor states that material-aware preview requires a
compatible resolver. Intent changes invalidate the derived preview. Focused
launch and beam-normal screens remain deferred; laboratory masks are not
rotated by roll.

## Persistence and compatibility

[Serialization helpers](src/launchplane/serialization.py) write schema **4**,
containing all physical-intent fields and no authoritative derived wavevectors.
Round trips preserve intent, units and derived k. Missing or unexpected fields
are rejected. Schemas 1–3 are rejected with a recreate/re-export message; their
laboratory-waist and wavevector definitions are not silently reinterpreted.
There is no old/new semantics selector or automatic migration framework.

Frozen dataclass equality/hash represent the stored intent (including the
otherwise directionless phi at theta=0), not an assertion that two physical
fields are equivalent. Deterministic JSON fingerprints can be obtained by
hashing `json.dumps(beam_stack_to_dict(stack), sort_keys=True,
separators=(",", ":"))`. Persist the schema with that fingerprint.

## Standalone use

```python
from math import pi
from launchplane.model import BeamDefinition, BeamStackDefinition
from launchplane.serialization import beam_stack_to_dict, beam_stack_from_dict

stack = BeamStackDefinition(beams=(
    BeamDefinition(name="Probe", theta_ext_rad=pi/6, phi_rad=pi/2,
                   w1_um=4, w2_um=7, psi_rad=pi/4, n_ext=1.0),
))
assert beam_stack_from_dict(beam_stack_to_dict(stack)) == stack
```

The model and serialization do not import Qt. To open the standalone editor:

```python
from PySide6.QtWidgets import QApplication
from launchplane.launchpane import LaunchPlaneWidget

app = QApplication([])
widget = LaunchPlaneWidget(beam_stack=stack)
widget.show()
app.exec()
```

The demo is also available with `python -m launchplane.launchpane`.

## LCProp integration boundary

LCProp owns the canonical
[physical launch geometry and power contract](https://github.com/mcroning/LCProp/blob/c317f49d34a9e16247ae6c567a5dcc42c3f27f30/docs/architecture/beamplane_physical_launch_contract.md).
That reference identifies a local development commit; the public remote may
not yet contain it. The contract spans both packages but is not duplicated here.

This candidate supplies the display seam consumed by the isolated LCProp
Milestone 2 resolver. Neither repository is installed into authoritative
environments yet. Integrate and install the reviewed pair together with the
applications stopped. The schema-4 package must not be paired with an old
LCProp laboratory-waist/wavevector adapter.

LaunchPlane continues to own physical intent and presentation only. LCProp owns
sampled fields, refraction, power qualification and scientific execution.

## Development

Python 3.11+ and PySide6 are required. In a dedicated development environment:

```bash
python -m pip install -e .
python -m pip install pytest
QT_QPA_PLATFORM=offscreen python -m pytest
```

Package/import name remains `launchplane`; the GUI class remains
`launchplane.launchpane.LaunchPlaneWidget`. "BeamPlane" describes the physical
editor contract, not a package rename. No package-level re-exports are provided.

See the [milestone development record](docs/development/physical_intent_milestone_1.md)
for the candidate boundary, validation and deferred native checks.

LaunchPlane uses the BSD 3-Clause License. See [LICENSE](LICENSE).
