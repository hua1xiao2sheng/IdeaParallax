# IdeaParallax engineering rules

This is a new standalone project. Do not add dependencies on a previous user project,
OpenClaw, DSH or PaperForge. Work only inside this repository unless explicitly asked.

- Preserve independent generation strategies and first-round context isolation.
- Differentiate `strategy_port`, `upstream_instructions_not_native_workflow`, and
  `external_command_not_attested`. Never label a port as native upstream execution.
- Raw candidate variants and provenance are immutable. Clustering must not destroy them.
- Missing source evidence, unavailable data, provider failures, and unrun experiments
  stay explicit. No fabricated metadata, pilot results, model scores or novelty claims.
- Do not install/run third-party source code merely to inspect a strategy.
- No automatic experiments, publication or student assignment. Respect explicit opt-ins.
- Tests are offline and require no account. Never silently fall back to demo in real runs.
- Run `python -m unittest discover -s tests -v` and compileall after changes.
- Maintain docs/AUDIT.md and reproducible regression tests for consequential fixes.
- Do not commit runs/, .env, auth.json, credentials, unreviewed upstreams, or user papers.
