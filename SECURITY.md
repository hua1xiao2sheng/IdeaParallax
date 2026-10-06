# Security and privacy boundaries

IdeaParallax is a local research orchestration tool, not a hostile-code sandbox.

## Network and credentials

API mode sends research prompts to the configured provider. Codex uses its own configured
service and saved authentication. Optional Crossref retrieval sends generated queries to
Crossref. Offline demo sends neither. Merely naming a paper URL does not fetch it.

Secrets are read from environment variables at request time. Config uses only an env-variable
name. Error bodies and subprocess stderr are not saved. Provider-reported usage is bounded.
The program does not read or copy your Codex auth.json or GitHub tokens.

## External code and skills

Commands use argument arrays, never interpolated shell strings. External programs require
`--allow-commands` and receive a minimized environment. Explicit env_allowlist can expose
additional variables: review it. A trusted program can still read files accessible to your
OS user. Process-group cleanup on Unix kills descendants; on Windows only the direct child
is guaranteed to be stopped. Use a VM/container for strong process and filesystem isolation.

Imported upstream text requires explicit paths, a full commit SHA, stored checksums and
`--trust-upstream`. Import is not a license grant or a security audit. Text-only import does
not execute dependencies and must never be reported as an original full workflow run.

Codex starts with read-only sandbox and no bypass flags. Its global configuration, MCP
servers, user rules and identity may still be shared across calls. Workspace separation
means independent contexts, not prevention of every cross-process access. Review your Codex
configuration before sending sensitive material or permitting write-capable remote tools.

## Storage and output

Runs include the original brief, evidence excerpts and model outputs. Keep them private;
.gitignore excludes runs and private configs. Publishing uses an explicit release-file
manifest rather than `git add .`. HTML escapes user/model text and embeds no remote assets.
Checkpoint checksums detect accidental or unsanctioned modification; they are not signed
attestations against a malicious local user who can rewrite the manifest too.

A crashed process can leave a .lock; verify the process is stopped before manually removing
it. Never remove an active lock to force a concurrent run. See docs/AUDIT.md for tested limits.

Report vulnerabilities privately to the repository owner after publication, not by posting
credentials, unpublished papers or exploit payloads containing personal data in public issues.
