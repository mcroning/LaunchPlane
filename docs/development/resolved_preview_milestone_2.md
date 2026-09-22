# Milestone 2 — host-resolved physical preview

Development baseline: Milestone 1 commit
`c577b5b0053b078b083b08561d8f27ecb932c4cc`.

The widget accepts host-supplied laboratory contour points and explanatory text
through `set_resolved_preview`. It does not resolve indices, Snell refraction,
waists, power, or fields. Schema 4 and Milestone 1 physical intent remain unchanged.
Contour coordinates are micrometres, x-right/y-up; Qt y inversion occurs only at
display. Dashed contours scale with scene geometry while existing external arrows
retain their device-space geometry. Derived previews are never serialized.

Intent/scene replacement invalidates the supplied preview. A scene reset signal
lets the widget remove its contours before Qt destroys their underlying objects.
This fixes a defect found by Product aperture-change and experiment-loading tests.
Invalid contour input is rejected before replacing a valid preview.

Validation: the complete LaunchPlane suite passed with 95 tests after the scene
lifetime correction. Product validation passed with 1889 tests and 77 skips;
focused and affected results are recorded in LCProp's Milestone 2 development
record. Syntax, Markdown/local-link, whitespace and diff checks passed. Native interaction and coordinated installation
remain later acceptance steps. Neither authoritative repository nor its installed
package is changed by this isolated development candidate.

Integration requires the reviewed physical-intent Product consumer and this
LaunchPlane candidate together, with applications stopped until both compatible
packages are installed. Do not install this breaking schema into an environment
still running the old LCProp launch adapter.
