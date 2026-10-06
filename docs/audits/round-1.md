# Round 1 — Architecture, task contract and runnable baseline

Date: 2026-10-05. Method: author self-review plus executable offline regression tests.
Not an external five-person audit and not a scientific benchmark.

## Findings and improvements

1. A multi-project wrapper could easily misrepresent a copied prompt as native execution.
   Added explicit execution-mode labels and `original_workflow_verified: false` provenance.
2. Free-form ideas would be difficult to compare. Added a strict common JSON contract,
   required hypothesis, mechanism, experiment and falsification fields, and evidence-ID checks.
3. Shared conversation history would undermine independent exploration. Generation packets
   contain no other candidates; each call runs in a separate temporary workspace. Review
   packets omit provenance and use opaque candidate IDs.
4. A demo could be mistaken for live model execution. Demo is an explicit provider and
   command; reports are prominently marked synthetic. Real runs have no silent demo fallback.

## Verification

Command: `python -m unittest discover -s tests -v`
Result: **18 tests passed**. Full captured output: `round-1-tests.txt`.

Includes real asyncio concurrency (peak bounded by 3), six distinct workspaces, blind
review payloads, six-candidate offline end-to-end reports, deterministic resume, quota
validation and invented evidence rejection.

Live Codex/model calls, native upstream systems, and GitHub publication were not executed.
