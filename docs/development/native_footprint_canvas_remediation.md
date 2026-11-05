# Native footprint and canvas annotation remediation

Baseline: `1d2a0cece656fdd87113faf0fefbf7dd678793da`.
Companion Product baseline: `16315734ad3223cdf5c0729a2d513a3314b6d7fa`.
Status: Development + Local Validation and self-review passed; awaiting
strictly read-only pre-commit review. Native acceptance remains pending.

## Findings and bounded correction

The host supplied the correct laboratory contour in micrometres. The dashed
path was created at z=-0.5, behind the opaque aperture rectangle at z=0.
The contour now occupies z=1, above the background/axes and below beam items
at z=10. A brighter cosmetic dashed pen retains device-space stroke width;
path coordinates continue to scale physically. No ellipse or refraction
calculation is introduced into LaunchPlane.

The scene title and aperture-range text shared the same top row. Their
`ItemIgnoresTransformations` text widths were fixed in pixels while their
physical anchor separation scaled with the view. The two annotations now use
separate wrapping labels in a vertical layout above the graphics view. The
bounds label updates on scene replacement. Axis ticks and physical x/y titles
remain in the scene. No fixed acceptance widths or screenshot coordinates are
used in production.

Product also needs to redeliver its resolved preview after its aperture setter
rebuilds the scene. That companion change is confined to its Beam panel.

## Validation

Python 3.12, offscreen Qt, bytecode disabled, isolated source trees only:

- Focused resolved-preview module: 5 passed.
- Affected resolved-preview, editor and angle modules: 67 passed.
- Complete LaunchPlane suite: 98 passed.
- Product host/integration/affected GUI set: 112 passed.
- Complete Product suite: 1905 passed, 77 skipped in 532.90 s.

Layout checks exercise widths 850, 1100 and 1450, intermediate resizes, zoom,
wrapping height and scene replacement. The Product companion exercises the
real PR window, host resolver and preview delivery against independent circle,
oblique ellipse, arbitrary azimuth, roll and coordinate oracles. Its development
record contains complete Product-suite evidence and preliminary failure details.

## Boundaries and human verification

Physical intent, schemas, external arrows, normal-incidence behavior and
scientific computations are unchanged. Applications and installed packages
are not updated during this isolated task. Automated results do not establish
native acceptance.

After separately approved integration and installation, check a 20 µm normal
circle, a 45-degree x-oriented ellipse with radii 28.284271 and 20 µm, azimuth
90-degree rotation, and readable annotations at compact and ordinary sizes.
Footprint and external arrow must coexist through zoom, edits and resize.
Do not proceed automatically into other native acceptance work.
