# Round 5 — Delivery, integration contracts and release safety

Date: 2026-10-05. Author self-review plus executed local regression tests.

## Pre-fix findings

The pre-fix run had **90 tests and 4 failures**, recorded in
`round-5-before.txt`. Duplicate JSON keys silently overwrote earlier values;
a native ideation provider was incorrectly inherited by the reviewer; negative
usage counters were accepted; failed requested retrieval still reported the run
as fully completed.

## Changes

- Reject duplicate keys throughout parsed model/configuration JSON.
- Default native-project runs to an ordinary Codex reviewer; explicitly reject a
  native ideation workflow configured as the reviewer.
- Retain only nonnegative, bounded integer usage counters (booleans are not counts).
- Record metadata lookup status separately; requested retrieval failure now
  downgrades the run to `partial`, never to a positive novelty claim.
- Added local HTTP protocol tests for API success, redirects, authentication
  errors, malformed responses and usage, plus subprocess and mocked Codex host
  integration tests. These do not call a paid model.
- Added release allowlisting/checksums and a new-repository publication script.
  Dry-run is the default, private is the default visibility, and existing
  repositories are never adopted, force-pushed or overwritten.
- Added a Windows/Ubuntu, Python 3.11/3.13 CI definition with read-only default
  permissions. Its remote jobs have **not** run in this delivery.
- Corrected the build-tool minimum to support the package's SPDX license metadata.

## Executed verification

`python -m unittest discover -s tests -v`: **91 tests passed**;
see `round-5-tests.txt`.

`python -m pip wheel . --no-deps --no-build-isolation --no-index`: final wheel built successfully;
see `round-5-wheel.txt`. An earlier isolated rebuild failed on DNS when downloading
setuptools (`round-5-build-network.txt`); the final build used the already installed
setuptools 82.0.1, which satisfies the declared minimum, with networking disabled.
Installed the wheel, without runtime dependencies, into
an independent directory; see `round-5-install.txt`.

From outside the source checkout, executed the installed package's `doctor`,
`demo`, and resumed `demo`; see `round-5-smoke.txt`. The six branch outputs and
both review stages completed on explicitly synthetic fixtures; resume retained
8 total outer call slots rather than replaying successful stages. Checked that
all six strategy resource files were present in the wheel.

Additional browser smoke inspection found a narrow-screen overflow from the
unbroken run fingerprint (445px page width at a 390px viewport). Fixed inherited
text wrapping, search-field shrink behavior and table layout. Headless Chromium
then passed desktop rendering, synthetic labeling, live filtering, restoring all
cards, and mobile layout with expanded details; no JavaScript exceptions.
See `round-5-browser-before.txt` and `round-5-browser.txt`. The browser disallowed
file-URL navigation, so the generated HTML bytes were rendered with `set_content`
without modifying browser policy.

## Unverified boundaries

No live Codex account or paid model was available in the runtime. The six real
upstream projects have **not** been evaluated end-to-end. Native export tests use
small local Git fixtures and a mocked Codex host contract. Crossref protocol and
failure behavior are tested; full-text literature verification is not implemented.
All local tests ran on Linux/Python 3.13.5, not Windows or every supported Python.
A synthetic demo demonstrates software behavior, not research originality.

GitHub publication is separately recorded in `github-publication.txt` and the
parent audit summary. Having a publish script is not evidence of a remote push.
