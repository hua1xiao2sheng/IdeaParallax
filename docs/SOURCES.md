# Method provenance and implementation references

Checked against repository content and official documentation on 2026-10-05. No Star
counts are used in scheduling or evaluation. Source availability and model capabilities
may change; native imports must pin a full Git commit.

## Ideation methods

- Orchestra: https://github.com/Orchestra-Research/AI-Research-SKILLs/blob/main/21-research-ideation/brainstorming-research-ideas/SKILL.md
- ARIS: https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep/blob/main/skills/skills-codex/idea-creator/SKILL.md
- IdeaSpark: https://github.com/microsoft/ResearchStudio/blob/main/ResearchStudio-Idea/skills/idea_spark/SKILL.md
- K-Dense: https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/scientific-brainstorming/SKILL.md
- EvoSkills: https://github.com/EvoScientist/EvoSkills/blob/main/skills/research-ideation/SKILL.md
- AI-Scientist-v2: https://github.com/SakanaAI/AI-Scientist-v2/blob/main/README.md and its independent ideation script

The six built-in strategy files were written specifically for IdeaParallax. No upstream
code/skill is vendored under this repository's MIT license. Imported third-party files
retain their own authorship and applicable license; review those before redistribution.

## Codex execution

- Non-interactive mode: https://developers.openai.com/codex/noninteractive
- CLI flags: https://developers.openai.com/codex/cli/reference
- Skills: https://developers.openai.com/codex/skills

The consulted docs describe `codex exec`, `--ephemeral`, `--output-schema`,
`--output-last-message`, `--sandbox`, `--skip-git-repo-check`, JSONL usage and reuse of
saved local CLI authentication. Using those documented flags is not live compatibility
verification against every installed version. No unsupported `spawn_agent` API is invented.

## GitHub Actions

The action maintainers' README files were checked for their documented v7 usage:
https://github.com/actions/checkout and https://github.com/actions/setup-python.
The delivered CI workflow has not run remotely before this project is published.
