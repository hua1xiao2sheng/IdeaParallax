# Round 3 — Reliability, concurrency and recovery

Date: 2026-10-05. Author self-review plus regression tests.

## Confirmed failures before the fixes

The 48-test pre-fix run had **4 failures**, retained in `round-3-before.txt`:

- negative saved call counters were accepted on resume;
- cancellation left the state labelled running;
- a competing process could populate a new directory between initial checking and lock acquisition;
- the two independent review stages were unnecessarily serial.

## Changes

Validate saved state and counters; record interrupted state while still holding the run
lock; recheck directory contents under that lock; dispatch both reviewers concurrently
through the same global semaphore. Successful checkpoints remain reusable only when
packet and input fingerprints match.

## Verification

`python -m unittest discover -s tests -v`

**48 tests passed**, `round-3-tests.txt`. Additional tests cover partial/all branch failure,
strict outer-call budgets, bounded retries, recovery of only failed generation, re-review
after the candidate set changes, corrupted checkpoint refusal, lock release and no-review mode.
