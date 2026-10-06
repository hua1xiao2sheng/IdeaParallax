# Three different integration levels

The project keeps execution identity separate from the source of an idea-generation strategy.

| Mode | What really runs | What it does NOT imply |
|---|---|---|
| `strategy_port` | One independently written project-inspired strategy per branch, through the chosen model | Full upstream system, original inner loops or evaluation results |
| `upstream_instructions_not_native_workflow` | Exact pinned text files, explicitly imported and passed as instructions | Execution of dependency scripts/tools or upstream quality gates |
| `native_project_via_codex_not_step_attested` | A fresh snapshot of a real local repository, with Codex instructed to follow its original ideation entry and dependencies | Proof that every upstream step succeeded; this needs native artifacts and a human audit |
| `external_command_not_attested` | Your explicit argv receives the JSON contract over stdin and returns JSON over stdout | That an arbitrary program is actually a named upstream project |

`original_workflow_verified` is deliberately false. Do not turn it true because a valid
JSON response was obtained. Six projects in the catalog are not six deployed, validated
scientific platforms.

## A. Use the six strategy ports

`configs/codex.json` dispatches six isolated prompts. `ideaspark` has a quota of one;
other ports have a quota of three. Empty outputs are allowed with reasons. No shared
candidate list is supplied until all generation branches have completed or failed.

## B. Import actual upstream instructions

Clone a selected public upstream yourself into a source directory; inspect its license
and files. Obtain a full commit SHA using `git -C <clone> rev-parse HEAD`. Then:

```bash
python -m idea_parallax import-upstream --repo /absolute/path/to/clone --commit FULL_40_CHARACTER_SHA --file path/to/SKILL.md --file path/to/references/needed.md --out configs/orchestra-bundle.local.json
```

The placeholder SHA must be replaced. Import only explicit UTF-8 .md/.txt files; no Python
or shell script executes during import. References must be listed when needed; missing
dependencies are not silently synthesized. Set the branch's `upstream_bundle` to this
file, then run with `--trust-upstream`. A relative bundle path is relative to the config
file, not the current directory. A bundle is checked on each run and included in the
input fingerprint. Refresh deliberately to a new file/version.

## C. Drive a real project in a fresh snapshot

Use a branch provider with `type: native-codex`, a local repository path, an immutable
commit, and the real entry file. The repository snapshot is exported with `git archive`
and extracted to a fresh temporary directory, not run in your original clone.

```json
{
  "id": "native-ideaspark",
  "strategy": "ideaspark",
  "max_ideas": 1,
  "provider": {
    "type": "native-codex",
    "repository_path": "/absolute/path/to/ResearchStudio",
    "commit": "REPLACE_WITH_FULL_40_CHARACTER_COMMIT_SHA",
    "entry": "ResearchStudio-Idea/skills/idea_spark/SKILL.md",
    "model": "",
    "timeout_seconds": 1800,
    "allow_network": false
  }
}
```

Put this in a config's `branches`. The default provider and reviewer should remain
ordinary `codex` or API providers. Run with `--allow-commands`. Review the upstream first;
this is code execution permission, not merely reading text. Codex uses workspace-write
rather than read-only for this explicit mode. Set `allow_network: true` only after deciding
to permit upstream shell-network access. No sandbox/approval bypass flags are used.

The original upstream's dependencies, model/search keys and supported platforms still
apply. Supply needed environment-variable names in `env_allowlist`; never their values.
This project deliberately does not install dependencies automatically. An upstream that
needs a GPU, an unavailable paper service, or unsupported host tools may return a blocker.
Choose a large enough outer timeout for the actual project; inner model calls are not
hard token- or dollar-capped by `max_calls`.

The strategy-port prompt is REMOVED for a native run; the named original entry drives
ideation. The host requests the common output contract only at the end. The result is
recorded as a native execution attempt, not step-by-step verified success. Native artifacts
inside the temporary workspace are not persisted beyond the normalized output in v0.1;
use an external command wrapper to retain/validate a project's native artifact tree when
that is required. Do not infer completed pilots, audits or novelty searches from its title.

## D. External JSON adapter

For a project with its own CLI/API, write a trusted adapter implementing:

```text
stdin:  {"task": "generate" or "review", "packet": {...}, "output_schema": {...}}
stdout: one JSON object matching output_schema
stderr: diagnostics (not saved by the orchestrator)
exit:   zero on completed response, nonzero on failure
```

Configure:

```json
{"type":"command","command":["/absolute/path/to/python","/absolute/path/to/adapter.py"],"timeout_seconds":600,"env_allowlist":["MY_PROVIDER_KEY"]}
```

No shell expansion/interpolation occurs. Paths must be absolute because each invocation
has a fresh temporary cwd. Return no candidates with a reason when there is no scientific
question; exit nonzero for infrastructure errors. Do not print progress to stdout.

## Integration matrix for the catalog

| Source | Default usable port | Pinned text path | Recommended original ideation entry |
|---|---|---|---|
| Orchestra | yes | catalog entry SKILL.md | same SKILL.md and its references |
| ARIS | yes | catalog entry SKILL.md | idea-creator / idea-discovery, without pilots unless separately authorized |
| ResearchStudio | yes | catalog entry SKILL.md | IdeaSpark navigator and referenced runbooks |
| K-Dense | yes | catalog entry SKILL.md | scientific-brainstorming plus references |
| EvoSkills | yes | catalog entry SKILL.md | research-ideation plus paper-navigator dependencies |
| AI-Scientist-v2 | yes | use README.md (Python code is not a text skill) | ai_scientist/perform_ideation_temp_free.py |

All real native integrations still need live acceptance testing with your host and accounts.
