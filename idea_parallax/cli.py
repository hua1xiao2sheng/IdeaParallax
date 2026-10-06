from __future__ import annotations
import argparse
import asyncio
from importlib.resources import files
import json
from pathlib import Path
import shutil
import sys
from .catalog import catalog
from .engine import Engine
from .io_utils import ValidationError, load_json, write_json
from .upstreams import import_bundle

DEFAULT_CONFIG = {"provider": {"type": "codex"}, "concurrency": 3, "max_calls": 20, "retries": 1, "review": True,
    "branches": [{"id": key, "strategy": key, "max_ideas": 1 if key == "ideaspark" else 3} for key in catalog()]}

def parser():
    p = argparse.ArgumentParser(prog="idea-parallax", description="Standalone parallel research ideation. No old-project dependencies.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("catalog", help="List six independent strategy ports and upstream entry paths")
    sub.add_parser("doctor", help="Check local runtime availability without reading credentials")
    init = sub.add_parser("init", help="Create a new task/config directory without overwriting")
    init.add_argument("directory", type=Path)
    for name in ("run", "demo"):
        run = sub.add_parser(name, help="Run real providers" if name == "run" else "Run explicitly synthetic offline fixtures")
        run.add_argument("--brief", type=Path)
        run.add_argument("--config", type=Path)
        run.add_argument("--out", type=Path, required=True)
        run.add_argument("--resume", action="store_true")
        run.add_argument("--allow-commands", action="store_true", help="Opt into trusted configured external programs")
        run.add_argument("--trust-upstream", action="store_true", help="Opt into reviewed imported instruction files")
        run.add_argument("--retrieval", choices=("none", "crossref"), default="none", help="Crossref sends research queries to an external service")
    web = sub.add_parser("web", help="Local dashboard with Codex subscription login and live progress")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--data-dir", type=Path, default=Path("runs/webui"))
    web.add_argument("--open", action="store_true", help="Open the dashboard in your browser")
    web.add_argument("--codex-binary", default="codex", help="Local Codex executable, never a shell command")
    imp = sub.add_parser("import-upstream", help="Import explicit text files from a local clone at a full commit SHA")
    imp.add_argument("--repo", type=Path, required=True)
    imp.add_argument("--commit", required=True)
    imp.add_argument("--file", action="append", required=True)
    imp.add_argument("--out", type=Path, required=True)
    return p

def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "web":
            from .web import serve
            if not 0 <= args.port <= 65535:
                raise ValidationError("Port must be between 0 and 65535")
            serve(args.data_dir, args.port, args.open, args.codex_binary)
            return 0
        if args.command == "catalog":
            print(json.dumps(catalog(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "doctor":
            print(json.dumps({"python": sys.version.split()[0], "codex": bool(shutil.which("codex")), "git": bool(shutil.which("git")),
                "gh": bool(shutil.which("gh")), "api_credentials": "not inspected", "demo": "available",
                "note": "Executable presence does not verify login, model access, network, or sandbox setup."}, indent=2))
            return 0
        if args.command == "init":
            args.directory.mkdir(parents=True, exist_ok=False)
            write_json(args.directory / "config.json", DEFAULT_CONFIG)
            write_json(args.directory / "brief.json", {"topic": "填写研究内容", "language": "zh-CN", "constraints": [], "context": "", "seed_papers": []})
            print(f"Created {args.directory}. Edit brief.json, then run with --brief and --config.")
            return 0
        if args.command == "import-upstream":
            result = import_bundle(args.repo, args.commit, args.file, args.out)
            print(f"Imported instructions at {result['commit']}; NOT a native workflow execution")
            return 0
        config = load_json(args.config) if args.config else json.loads(json.dumps(DEFAULT_CONFIG))
        if not isinstance(config, dict):
            raise ValidationError("Configuration must be a JSON object")
        brief = load_json(args.brief) if args.brief else {"topic": "演示：在固定预算下检索缺失证据", "language": "zh-CN"}
        if args.command == "run" and args.brief is None:
            raise ValidationError("Real runs require --brief; use demo for fixtures")
        if args.command == "demo":
            # Explicit demo also overrides per-branch providers and disables all network.
            config["provider"] = {"type": "demo"}
            config["reviewer"] = {"type": "demo"}
            for branch in config["branches"]:
                branch.pop("provider", None)
                branch.pop("upstream_bundle", None)
            args.retrieval = "none"
        if args.config:
            for branch in config["branches"]:
                if branch.get("upstream_bundle"):
                    bundle = Path(branch["upstream_bundle"])
                    if not bundle.is_absolute():
                        branch["upstream_bundle"] = str((args.config.resolve().parent / bundle).resolve())
        report = asyncio.run(Engine(brief, config, args.out, allow_commands=args.allow_commands,
                                   trust_upstream=args.trust_upstream, retrieval=args.retrieval).run(resume=args.resume))
        print(json.dumps({"status": report["status"], "candidates": len(report["candidates"]), "synthetic_demo": report["synthetic_demo"],
                          "report": str(args.out.resolve() / "report.html")}, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "completed" else 2
    except (ValidationError, OSError, ValueError) as exc:
        print(f"Error: {type(exc).__name__}: {str(exc) if isinstance(exc, ValidationError) else 'Check input paths and JSON files'}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Interrupted; completed checkpoints are retained. Use --resume with unchanged inputs.", file=sys.stderr)
        return 130
