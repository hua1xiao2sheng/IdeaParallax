# Round 4 — Scientific integrity and upstream boundaries

Date: 2026-10-05. Author self-review plus local regression tests.

## Pre-fix findings

The pre-fix 67-test run recorded **4 failures** (`round-4-before.txt`): different controlled
baselines were grouped as exact duplicates; empty search strings passed; zero candidates
needed no explanation; review normalization mutated the original model-return object.

## Changes

- Exact grouping now compares the scientific object AND the full minimal experiment;
  all original variants are still retained. Similarity remains an advisory lexical signal.
- Require useful search queries and a reason for an empty candidate set.
- Preserve the original review object and record evidence-driven novelty downgrades as
  explicit enforcement records, not silent editorial changes.
- Added a separately gated native-Codex path: export a pinned local repository to a new
  temporary directory without modifying its original checkout, drive its real entrypoint
  using Codex, and retain `not_step_attested` provenance. This is distinct from a strategy
  port and from text-only upstream import. No automatic dependency installation.
- Native exports reject links and unsafe archive members and bound total extracted size.

## Verification

`python -m unittest discover -s tests -v`

**69 tests passed**, full output `round-4-tests.txt`. Tests cover no fabricated evidence,
no global-novelty status, complete reviewer coverage, original candidate preservation,
commit-pinned text import, changed-bundle refusal, native export correctness and symlink
rejection. The native export uses a small local Git fixture, not a claim that all real
upstream research pipelines have been deployed or completed with paid model access.
