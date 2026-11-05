# Preview-state and layout remediation

Baseline: `d5e064c4a24475362345fc43f2d55191086f2a12`.
Isolated branch: `fix/preview-state-layout`.

## Boundary

Editor layout, pending-edit synchronization and their tests change. Product owns footprint resolution. No
resolver, physical-intent definition, ray endpoint, inverse callback, serialization, handle,
scene-ownership or preview-payload semantics change. No new persistence identity
is introduced. No package is installed and no native application is launched.
The companion Product baseline is `59eaf50d519d2ea0476c6ebbff5e00c2f35fa02a`.

## Presentation

[LaunchPlaneWidget](../../src/launchplane/launchpane.py) places `x (µm)` and
`y (µm)` designators adjacent to the view in a Qt grid layout, with `Input face`
as title. These do not move with physical scene zoom. The existing scene retains
x-right/y-up coordinates and only beam numbers, ticks and interactive geometry.

Status remains complete, wraps and scrolls vertically in a separate region.
Its height is bounded by font line spacing, preserving canvas space for large
beam lists without a screenshot-width branch. The inspector gains row spacing,
Qt form wrapping and a full-width derived-k row. Its scroll area may shrink
vertically while keeping every control reachable. Read-only wording remains.

No changes to ray/center priority, zero-tilt handles, hit targets, keyboard or
Shift nudging, signed intent, reciprocal edits, Fit or Full Aperture.

## Established native pending-editor cause and synchronization

The user reproduced typing theta=30 without Return/Tab while the committed preview
remained the theta=0 circle. Run consumed 30; Tab independently committed it and
updated the preview immediately. This establishes pending text versus committed
intent, not changed resolver geometry. The former unresolved diagnosis is
superseded. Human acceptance of this correction remains pending.

`commit_pending_edits()` validates numeric drafts on every beam with Qt's
validator, converts with its existing parser, and publishes one canonical update
through the shared `_apply_beam_updates` path. Product invokes this before LC/PR request
adaptation. Synchronous `beamStackChanged` delivery refreshes the host preview
before dispatch. Reentrant inspection sees the committed stack without repeating
the mutation. Unchanged rounded values preserve full-precision model state.
Names and laser labels are included; enabled remains an immediate checkbox, and
profile has no pending editable text. Normal valid Tab/Return/focus commits keep
their ordinary behavior; no per-keystroke physical preview is introduced.

`IntentSpinBox` keeps invalid text through focus transitions, Hide and Return so
request validation cannot silently use Qt's previous-value fallback. Hide matters
because Product switches to Results before request construction. Existing bounds
and scientific validation remain unchanged. Invalid batches do not partially
commit. Product's passive Input Screen preview reads only committed state.

[Pending-edit tests](../../tests/test_pending_editor_commit.py) cover atomic batch
updates, reentrancy, invalid text, Tab/Return and full-precision preservation.
The companion real PR-window test types 30, clicks the actual Run button and
observes the ellipse before forwarding to the real worker; its request, tilted
propagation and post-result preview agree. LC shares the same ownership boundary.

## Validation and self-review

[Layout tests](../../tests/test_preview_layout.py) cover compact through ordinary
window sizes, all status text retained, wrapping/scroll overflow, no overlapping
inspector rows, reachable read-only values, sufficient canvas space, unchanged
paths across selection/fit, axis labels and global handle stacking.

Existing no-vertical-scroll assertions in [editor tests](../../tests/test_launchpane.py)
are updated to check that scrolling actually exposes the derived values while
horizontal scrolling remains unnecessary. This implements the requested
scrolling option instead of squeezing the lower inspector rows.

Earlier layout-only evidence: focused preview/layout/ray-handle validation 17
passed; full suite 118 passed. Final pending-edit validation is recorded below.
Python 3.12, offscreen Qt, bytecode and pytest cache disabled. No native GUI or
GPU validation is claimed. Final syntax, documentation, whitespace and protection
checks are recorded in the companion Product report.

The new commit API requires coordinated companion Product delivery; persistence
schemas remain unchanged. All changes remain editor/presentation synchronization.
Human native checks must verify pending theta direct Run, Tab/Return, invalid-text
rejection, both footprints before/after PR, layout and mouse/keyboard interaction.

## First pending-editor validation (superseded)

- Focused editor/layout/ray/preview tests: **22 passed in 0.95s**.
- Complete affected LaunchPlane suite: **123 passed in 1.54s**.
- Companion Product focused: **24 passed in 6.16s**; affected:
  **207 passed in 42.47s**; complete: **1964 passed, 77 skipped in 540.21s**.
- Syntax, Markdown/local references, whitespace and `git diff --check` pass.

Preliminary testing exposed Qt's Hide-triggered invalid-text correction after
focus-only interception; the final event handling and real Product Run tests
cover that additional boundary. A suffix assertion uses `cleanText` to check
numeric text independently of Qt's displayed unit. No production physics change
was needed. Final logs/commands remain external `pending-editor-*` artifacts.

Development self-review confirms exact editor/layout scope, unchanged model and
serialization, retained interaction tests, empty indexes, and preserved
authoritative repositories and installed environment. Local validation passes;
independent pre-commit review and later human native acceptance remain required.

## Read-only review P2 correction: preserve cross-field drafts

The first correction still let general inspector refresh overwrite unresolved
text when another field committed. The theta-minus/Tab/phi-commit failure was
reproduced through real Qt editing. This follow-up keeps explicit session-local
numeric drafts, distinct from committed immutable intent. Valid pending text and
Qt-invalid/intermediate text are captured before synchronization; clean controls
refresh normally and draft text is restored verbatim afterward.

Ownership is tied to the actual beam object, with a retained reference and explicit
transfer when normal field, center or ray updates replace that immutable object.
There is no persisted identity or schema change. Selection retains per-beam drafts;
returning to a beam restores its own text. Same-stack scene rebuild, Fit/Full
Aperture, host preview redelivery and resize do not discard drafts. Duplication
copies committed intent only. Deletion or wholesale replacement cannot silently
remove pending edits; these operations reject until the edits are corrected.
No new global discard/cancel interaction is introduced.

Run's commit API checks every beam's drafts. Invalid input selects its owner and
focuses/scrolls the offending field, then raises the existing validation error.
Product blocks dispatch; unresolved text remains available for correction.
Other valid fields may commit normally, without asserting that the unresolved
field was corrected. When every draft validates, the common stack-update helper
assigns the complete validated model before one publication, including multi-beam
batches. Reentrant host inspection never sees a partially applied batch.

The new regressions cover four real-editor cross-field pairs in Product,
selection plus actual host aperture rebuild and Run, multiple invalid fields and
beams, explicit correction (including re-entering the original value), ownership
transfer through model replacement, and atomic valid multi-beam publication.
The earlier layout, direct-Run worker, Tab/Return and interaction tests are retained.
No physics, resolver, schema or unrelated production file changed.

## Final P2 remediation validation and self-review

- product-focused: **30 passed in 7.94s**.
- product-affected: **213 passed in 44.29s**.
- product-full: **1970 passed, 77 skipped in 544.05s**.
- lp-focused: **10 passed in 0.47s**.
- lp-affected: **53 passed in 1.03s**.
- lp-full: **128 passed in 1.28s**.

Syntax compilation in memory, Markdown/local-link checks, whitespace and
`git diff --check` pass. The external command record remains
`pending-editor-validation-commands.txt`; final logs are `invalid-drafts-*.log`.
An initial full Product run was deliberately interrupted to include the added
center/aperture-range regression, then restarted in full. It is not counted as
completed evidence. The final complete run above includes the entire candidate.

Preliminary test corrections were limited to using actual unacceptable text in
positive-minimum controls (Select All/Backspace; minus alone is rejected by Qt),
and allowing a normal valid neighboring commit when validation transfers focus.
The contract blocks unresolved requests, not independent valid model edits.
Direct batch validation without focus transfer still checks no partial mutation.
The added host center/range-refresh check passes without another source change.

Self-review: the P2 production correction is confined to LaunchPlane's editor.
The existing Product BeamPanel source, prior lifecycle test, LaunchPlane layout
and inspector tests remain unchanged from the earlier candidate. The combined
candidate still has exactly four Product and five LaunchPlane files. Session
editor ownership does not introduce scientific state, persistent IDs or schema
changes. All physical mappings, algorithms, power/capture, screens, material and
continuation behavior remain unchanged. Coordinated delivery is still required.

Fresh protection verification matches authoritative Product/LaunchPlane/Research,
the reconstruction candidate, all 4,348 historical Product paths and all 19,733
installed-environment files. Historical Product fingerprint remains
`929fe98e9a4162687e4ce21b140f85d11c5233f3e4f5897f10ed3de3b011bc68`.
Both isolated indexes are empty. No commit, integration, installation, native
application launch, remote/GPU access or follow-on work occurred.

Development + Local Validation closes the P2 failure: unresolved edits survive
unrelated commits/refreshes, Run rejects them across beam selections, and explicit
correction permits canonical synchronization. Independent read-only review is
next. Human native acceptance remains pending.
