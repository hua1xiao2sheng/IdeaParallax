# Round 2 — Security and process lifecycle

Date: 2026-10-05. Author self-review plus executable regression tests.

## Findings and fixes

1. **Confirmed hang:** a >4 MB child output could raise in the reader, leave its pipe
   undrained, and hang while waiting after kill. The initial stress test did not finish
   before the execution harness stopped it; see `round-2-before.txt`. Changed cleanup
   to kill while continuing to drain, shield communication during timeout, and bound
   exceptional platform cleanup. Added timeout and oversized-output regressions.
2. **Symlink validation order:** resolving the run path before checking it erased the
   symlink evidence. Added checks of existing path components before resolving/writing.
3. **Environment allowlist shape:** a string could be interpreted as individual characters.
   Validate it as a bounded list of environment-variable names before any invocation.
4. **Unbounded upstream capture:** git show was captured before checking size. Added
   git cat-file size inspection before loading the blob.
5. Tested remote HTTP/credential URL refusal, explicit external-command authorization,
   minimized child environment, stderr secret omission, and HTML escaping/CSP.

## Verification

`python -m unittest discover -s tests -v`

**34 tests passed**, captured in `round-2-tests.txt`. No live model account was used.
Unix subprocess behavior was exercised locally. Native Windows descendant cleanup remains
an explicitly documented limitation; working-directory separation is not a security sandbox.
