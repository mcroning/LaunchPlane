# Native acceptance: signed intent and physical ray presentation

Candidate; human native acceptance remains pending.

Baseline: `7b10bc1963c5b83dcf2eab866216f02746e1ea40`. Development is isolated;
no installed package, authoritative working file, or milestone history changes.
Product's companion baseline is `dc3cc668d756762917e8070e421a36a3bb3143b5`.

## Bounded implementation

- Signed theta: -pi/2 < theta < pi/2, preserved by schema-4 round-trip and editor.
- Host-supplied physical exit endpoints replace fixed-pixel external glyphs.
  No material physics is inferred by LaunchPlane. Missing endpoints are explicit.
- The earlier center-only design is superseded by the authorized interactive
  remediation below. A physical-exit handle now delegates inversion to Product;
  the old external screen-angle mapping is not restored.
- Caption `Input face`, numeric beam labels only, device-space collision spacing.
- `Fit` reveals all geometry; `Full Aperture` returns to the complete face.
  Historical LaunchPlane only had `Fit aperture`. The two-control precedent is
  Product's image view, not a lost LaunchPlane companion.
- Dashed host footprints and stacking order are retained. All physical ray
  lengths remain unchanged by Fit, resizing, or zoom.
- `supports_resolved_internal_rays` identifies the coordinated preview API.
  Existing field schemas remain unchanged; obsolete definitions still reject.

Product owns the new aperture-size controls and binds them to its canonical
Grid. This repository does not define a second scientific aperture.

## Validation

Final validation evidence is recorded below after local checks. Tests cover
signed quadrants/equivalence/round-trip, physical scene scaling, explicit
unavailability, invalid-preview atomicity, disabled/normal/coincident beams,
Fit/full-aperture, responsive annotations, and retained footprint behavior.
No native GUI, remote system or GPU is used for validation; Qt is offscreen.

## Native checks still required

Use the coordinated candidate only after separate review, commit, integration
and installation approvals. Check positive/negative theta at fixed phi; ray
motion and crystal-exit endpoint; opposing beams; aperture controls; Fit and
Full Aperture; number-only labels; Input face caption; footprints; resizing and
zoom. Automated tests do not complete this human gate.

## Earlier candidate local results

Python 3.12.13, isolated LaunchPlane source on PYTHONPATH, bytecode disabled,
Qt offscreen, pytest cache disabled:

- Focused native-design/resolved-preview checks: 13 passed (before the additional
  explicit crossing-ray case, which passed in the final full suite).
- Affected angle/editor/native-design/preview checks: 74 passed before that added
  crossing case; all are included in the final full suite.
- Complete final suite: **106 passed**, no failures or skips (0.94 seconds).
- Syntax compilation, Markdown/local links, candidate whitespace and
  `git diff --check`: passed.

An initial coincident-label test found that a fixed 20-pixel row was smaller
than the active font height. Row spacing now uses measured label height.
Self-review also made arrowheads fixed-size cosmetic children at the physical
exit, preserving their visibility without changing ray lengths. Independent
zoom tests verify both endpoint and head size. No Qt lifetime workaround or
scientific change was introduced.

## Interactive-handle remediation

The prior read-only review found that a device-sized center marker was backed by
a scene-sized parent hit target. Both center and arrowhead now use real,
scene-owned device-sized interactive items. Global z bands put every arrowhead
above every center, including other beams. Shafts/footprints never intercept
handle selection. Zero tilt retains a coincident interactive arrowhead without
inventing ray length. The arrowhead is enlarged, with its tip at the physical exit.
Selected beams and the focused handle are highlighted.

Dragging preserves the initial cursor offset. A center move keeps direction;
an exit move calls the host's `set_inverse_resolver` callback. LaunchPlane does
not compute refraction. Missing callbacks or rejected exits show an explicit
reason and leave direction unchanged. Product owns the signed-theta branch rule.
Synchronous stack/preview redelivery preserves the mouse grab and keyboard focus;
missing redelivery clears stale geometry. Scene resets still discard old items.

Arrows nudge the focused handle by one device pixel, Shift by ten, through the
current inverse view transform. Spinbox focus keeps ordinary keyboard behavior.
Objects-list selection is retained but not required between canvas manipulations.
Manual reciprocal crossing is supported; no persistent target mode is added.

New tests send actual mouse events to the viewport, including repeated move
updates, and assert the Qt grabber. They cover zoom, Fit/long rays, zero overlap,
exposed centers, cross-beam priority, footprints, keyboard/Shift/device mapping,
focus transfer and missing host behavior. Product's companion tests exercise the
real inverse and independently propagate reciprocal beams. No test-owned item
replacement, event-handler bypass or production ownership workaround is used.

Focused: **21 passed**. Affected: **114 passed**. Complete-suite and final static
checks are recorded below after completion. Earlier preliminary fixture failures
were corrected by allowing Qt layout to settle before input, using a sufficient
explicit aperture and unique beam names; no production workaround was needed.

User guidance and the coordinated architecture amendment describe the final
interaction. Human native checks remain pending: zero-tilt grab, exposed center,
reciprocal drag, keyboard/Shift and numeric updates, focus, propagation agreement,
Fit/Full Aperture and resize. No authoritative or installed package is changed.

Current LaunchPlane validation commands (same isolated environment):

```text
python -m pytest -p no:cacheprovider tests/test_ray_handles.py tests/test_native_design.py tests/test_resolved_preview.py -q
python -m pytest -p no:cacheprovider tests/test_ray_handles.py tests/test_native_design.py tests/test_resolved_preview.py tests/test_angles.py tests/test_launchpane.py tests/test_serialization.py -q
python -m pytest -p no:cacheprovider tests/ -q
```

Development self-review covers actual Qt routing, global handle priority,
zero/disabled/unavailable states, physical versus device geometry, mouse-grab
lifetime, inverse API ownership, focus transfer and schema compatibility.
The host owns all optical inversions and forward scientific behavior. Coordinated
review, integration and installation remain necessary; native acceptance is pending.

## Completed interactive validation

Complete suite: **114 passed, no failures or skips (1.22s)**. No implementation changes occurred during
these final full-suite runs. Syntax compilation, Markdown/local-reference checks,
candidate whitespace and `git diff --check` pass. Fresh protection verification
confirms authoritative repositories, reconstruction, historical files and the
installed new-user environment unchanged. Both indexes remain empty.

This completes Development + Local Validation, not human native acceptance or
independent pre-commit review. Nothing is staged or committed.
