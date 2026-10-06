# Local dashboard verification — 2026-10-06

This extends IdeaParallax only; no OpenClaw, DSH, or PaperForge dependency was added.
The default dashboard is a local, single-user Codex-subscription driver, not a public
service and not a native deployment of the six upstream research systems.

## Implemented

- `python -m idea_parallax web --open`: stdlib HTTP server, static Chinese UI, no build step.
- Browser input, strategy/model selection, concurrency, optional review and metadata search.
- Local `codex login status` classification; no reading/copying auth.json and no raw login
  output in browser responses. Real jobs require consent and confirmed ChatGPT login.
- Fixed OpenAI provider in subscription-only mode; API-key environment variables removed.
- Windows official npm shim resolution without shell interpolation; UTF-8 protocol retained.
- Independent generation contexts, stage-level progress, immutable candidate records,
  stop, remaining-budget resume, local history, source/text filters and report exports.
- Loopback-only binding, per-launch token, Host/Origin checks, CSP, export allowlist,
  bounded request size, no browser-supplied executable/provider/path fields.
- Windows cleanup requests termination of this invocation's process tree, not all Codex
  sessions. Completed service-side work and consumed quota cannot be rolled back.

## Checks actually performed locally

| Check | Result |
|---|---|
| Existing regression suite after reconstructing the current published source | 93 tests, OK |
| Existing + 30 dashboard/host/HTTP/lifecycle tests | 123 tests, OK; final run 9.392s |
| `python -m compileall -q idea_parallax scripts tests` | Passed |
| `node --check idea_parallax/data/web/app.js` | Passed |
| Offline demo through the HTTP API | Six synthetic candidates and two synthetic reviews |
| Shutdown/cancellation, progress, same-input resume and call cap | Offline regression tests passed |
| API credential environment removal and sanitized login classification | Mock-backed regressions passed |
| Missing token, wrong Host/Origin, unsupported provider/path | HTTP rejection tests passed |
| Wheel build/install outside source directory | Three web assets and web CLI present |

## Browser verification boundary

The installed Chromium blocks direct localhost navigation with an administrator policy.
We did not modify that policy. Instead the UI was rendered in an in-memory browser test
page and test requests were mapped by the harness onto the local HTTP server using Python.
This verified form submission, six rendered candidates, source/text filters, preserved
expanded details across refresh, report download, and no horizontal overflow at 390px.
No JavaScript page errors were recorded. Screenshots show synthetic data and no account.
Session-storage page reload in a normal, directly connected browser is not claimed as
verified by that harness; on-disk history restart is covered separately by unit tests.

## Unverified

No local authenticated Codex binary/account is available in this build environment.
Live sign-in, actual model availability, subscription quota, Windows sandbox enrollment,
real research-idea quality, and full original upstream execution were not tested here.
Unit test success is not evidence of scientific novelty or model-quality improvement.

Remote CI outcomes must be read from the workflow for the actual published commit.
The existing CI matrix covers Ubuntu/Windows and Python 3.11/3.13. This document does
not claim future jobs have passed before they execute. Windows retains the three
pre-existing platform-specific symlink skips.

## Repeat locally

```bash
python -m unittest discover -s tests -v
python -m compileall -q idea_parallax scripts tests
python -m idea_parallax web --open
```

In the dashboard choose the explicitly labeled offline demo first. Then on a machine
with a valid ChatGPT Codex login, select two strategies, one candidate each, concurrency
one or two, and no reviews for the first real smoke test. Do not upload credentials.
