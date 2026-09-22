# Physical external intent and editor — Milestone 1

Date: 2026-09-22. Status: Development + Local Validation complete;
independent pre-commit review pending. No commit or integration is authorized
by this record.

## Baselines and boundary

LaunchPlane baseline: `add5f6bdbfcceaea7a8f2fd132e4ebf70b6eb5a8`.
LCProp baseline and canonical contract owner:
`c317f49d34a9e16247ae6c567a5dcc42c3f27f30`.
The [public API documentation](../../README.md) links the exact canonical
physical-launch contract; that local Product commit may not yet be public.

This candidate changes only the standalone LaunchPlane model, serialization,
canvas, editor, tests and documentation. It is developed in an isolated
worktree. No LCProp candidate or adapter/transport edit is needed for this
bounded standalone boundary, so no Product worktree is created. Do not install
this breaking candidate into an existing LCProp runtime before coordinated
integration. Authoritative Product and LaunchPlane checkouts and private
Research remain unchanged during development.

## Architecture and schema decision

The keyword-only frozen `BeamDefinition` stores external polar theta, azimuth
phi, n_ext, beam-normal radii, independent roll, entrance center/phase, vacuum
wavelength, requested incident power and collection metadata. Construction
validates physical intent; replacement creates a newly validated object.
Direction and external k are deterministic derived properties, not persisted
wavevector inputs. No Qt import is required by the model or serializer.

Schema 4 persists every physical field. Schemas 1–3 are explicitly rejected
with a recreate/re-export message. Missing fields, extra fields and unsupported
focused/legacy/uniform profiles are rejected. The old mode selector, editable
wavevector API and focused geometry calculation are removed from this editor;
there is no compatibility bridge into old launch semantics. Unchanged package
naming is not a backward-compatibility claim.

The Qt adapter maps physical (x,y) to scene (x,-y) consistently for centers,
placement, dragging, clipping, ticks and labels. Arrows use display-pixel
length `80*sin(theta_ext)`, with device transforms used for editing; zoom
changes neither length nor meaning. Labels include beam name and numeric
external theta, disabled beams are gray and labelled, and normal incidence
has a center symbol without a directional arrow. Arrow drag saturation is a
UI bound below grazing; headless invalid angles are rejected rather than
clipped. Explicit centers supplied by API/inspector remain unchanged even
outside the displayed aperture; interactive center dragging is bounded to it.

No ellipse is drawn: no independent material-aware geometry or misleading
beam-normal-radius-as-face-footprint visualization is introduced. No host
preview interface is added prematurely. The future Product resolver can
consume the complete immutable physical intent without changing these fields;
resolved material context and footprint presentation remain later integration
work. No canonical architecture-contract change was required.

The editor visibly states that the physical launch resolver is not yet
implemented. No new intent reaches actual LC/PR sampled fields. Incident power
and entrance-reference phase are described as future physical intent, not a
claim that existing Product normalization/phase construction has changed.
Milestone 2 still owns the shared resolver; coordinated Product integration
and power-consumer migration must precede enabling execution.

## Validation

Python 3.12.13 with the established LCProp development environment's pytest
and PySide6, isolated `src` on PYTHONPATH, `PYTHONDONTWRITEBYTECODE=1`,
`QT_QPA_PLATFORM=offscreen`, and pytest's cache provider disabled. No package
installation or environment change occurred. Two inspected Python 3.12
environments lacked pytest; validation used the already provisioned environment.

- Focused model and serialization modules: **67 passed**.
- Affected Qt widget/canvas module: **26 passed**.
- Complete LaunchPlane `tests/`: **93 passed**, no failures or skips.
- Syntax compilation in memory, Markdown fences/local links, candidate
  whitespace scan and `git diff --check`: passed.
- LCProp tests: not run, because no LCProp file/runtime/persistence path changed.

Commands were `python -m pytest -p no:cacheprovider -q` followed by
`tests/test_angles.py tests/test_serialization.py`, `tests/test_launchpane.py`,
and `tests/`, respectively. These are development regressions, not scientific
commissioning evidence or a material-interface validation claim.

Tests cover independent analytic directions/k, quadrants/wrapping, grazing and
invalid inputs, radii/roll/center/phase, zero power, immutable identity,
headless imports, complete schema round trips and obsolete-schema rejection.
Geometry tests exercise opposite/arbitrary arrows, non-square physical axes,
actual scene mouse events, zoom-independent device length and drag inversion,
normal/disabled/multiple beams, offscreen paint, collection operations and
inspector-to-model-to-serialization round trips. Default-layout coverage is
retained, with additional widths 1000/1200/1280/1450.

Initial validation exposed inspector scrolling at the default size. The fix
uses layout stretch and a maximum vertical size policy for the persistent
status footer, plus grouped buttons and bounded object-list height. The
existing no-scroll assertion was retained. No fixed-width test special cases
were added. Self-review also caught positive spin-box minima being rounded
before decimals were set; order was corrected and covered by a regression.
Explicit out-of-aperture centers are covered against silent refresh movement.
No Qt crashes occurred. Standard offscreen-plugin/font diagnostics are not
native visual acceptance evidence.

## Deferred native checks and scientific non-change

After the separately approved lifecycle, inspect macOS font scaling, label
legibility/overlap for dense multi-beam layouts, trackpad zoom and handle
feel, normal/disabled symbols, responsive resize, and the persistent execution
status. Offscreen geometry tests establish coordinates and state, not native
subjective usability.

No sampled field construction, refraction resolver, flux normalization,
aperture capture, laboratory screen, focus, scalar propagator, LC/PR material
model, checkpoint, continuation, carrier diagnostics or reconstruction changed.
The existing Product reconstruction candidate is excluded and preserved.
Remote continuation remains **DEFERRED / NOT AUTHORIZED**. PR scattering
remains **SCIENTIFIC HOLD / UNESTABLISHED**. No Slurm/SSH/CUDA, native scientific
runs, remote queries, fanning or follow-on milestone was performed.
