# GitHub publication verification

Date: 2026-10-06. Repository: [hua1xiao2sheng/IdeaParallax](https://github.com/hua1xiao2sheng/IdeaParallax).

## What was actually published

The user created this new **public** repository, then authorized uploading the standalone
project. No previous project was edited, adopted, or force-pushed. Repository visibility
was left as selected by the user.

The first complete source commit is
[`ceff9e3cf7a75cd62c631603527067ecba136d13`](https://github.com/hua1xiao2sheng/IdeaParallax/commit/ceff9e3cf7a75cd62c631603527067ecba136d13).
Its tree is `2e32b29e8a671478135c7d444ea0c7fac01136d6`, matching the original
**67-file IdeaParallax-v0.1.0.zip** exactly, including paths, file modes and bytes.
All 66 file hashes listed by the original release manifest were also checked locally;
`release-files.json` itself is the 67th file. No credential signatures were found by
the pre-upload scan. This is not a claim of an exhaustive security audit.

Publication used GitHub Git Data APIs, followed by a non-force update of `main` with an
expected-head check. The remote branch and commit tree were then read back and verified.
The older ZIP and its separate Git bundle remain historical delivery artifacts; the
remote publication commits are not the same five local audit-history commits.

## Tests and post-publication correction

Before uploading, the extracted original source passed:

```text
python -m unittest discover -s tests -v
Ran 91 tests in 4.994s
OK
```

The [first GitHub Actions run](https://github.com/hua1xiao2sheng/IdeaParallax/actions/runs/37406343733)
passed on Ubuntu/Python 3.11 and 3.13. Its Windows/Python 3.13 job exposed **three encoding
errors**: two tests read UTF-8 research reports using the Windows locale, and the external
Python adapter emitted a locale-dependent stream. These were real remote CI findings,
not simulated failures.

The follow-up commit explicitly reads UTF-8 in the affected tests and sets `PYTHONUTF8=1`
and `PYTHONIOENCODING=utf-8` for adapter subprocesses. Two regressions check that parent
locale settings cannot override the UTF-8 wire protocol. The corrected local run passed:

```text
python -m unittest discover -s tests -v
Ran 93 tests in 4.885s
OK
```

The workflow still tests Ubuntu and Windows with Python 3.11 and 3.13. See the
[current Actions results](https://github.com/hua1xiao2sheng/IdeaParallax/actions/workflows/ci.yml)
for the corrected commit's remote outcome; no future run result is asserted in advance.
Windows skips three explicitly platform-dependent symlink tests; Ubuntu executes them.

## Reading the older audit documents

`docs/audits/round-*.md` and their logs preserve the five original engineering review
rounds. Statements that GitHub had not been published or remote CI had not run describe
that earlier delivery stage. `docs/audits/github-publication.txt` preserves the earlier
failed local CLI preflight, not the current repository state.

The earlier blanket description of the connector as read-only was inaccurate: creation
of a repository was unavailable, but writes to this user-created repository succeeded.
The current README and audit summary point here to avoid confusing that history with
publication status. The release manifest is regenerated for the follow-up files.

## Boundaries that remain

No live paid-model or authenticated Codex scientific run was performed during publication.
Six default branches are strategy ports, not six fully deployed upstream systems.
Offline tests and CI validate engineering behavior, not research originality, global
novelty, completed experiments, or publication quality.
