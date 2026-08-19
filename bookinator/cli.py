from __future__ import annotations

import argparse
from pathlib import Path

from . import pipeline
from .config import Config


def cmd_new(args: argparse.Namespace, config: Config) -> None:
    mp3_path = Path(args.mp3)
    paths = pipeline.create_project(config, args.project, mp3_path, mp3_path.name)
    print(f"Created project '{args.project}' -> {paths.base}")


def cmd_stage(stage: str):
    def handler(args: argparse.Namespace, config: Config) -> None:
        message = pipeline.run_stage(config, args.project, stage)
        print(message)

    return handler


def cmd_all(args: argparse.Namespace, config: Config) -> None:
    mp3_path = Path(args.mp3)
    pipeline.create_project(config, args.project, mp3_path, mp3_path.name)
    for message in pipeline.run_all(config, args.project):
        print(message)


def cmd_status(args: argparse.Namespace, config: Config) -> None:
    paths = pipeline.ProjectPaths.for_project(config, args.project)
    status = pipeline.stage_status(paths)
    for stage in pipeline.STAGES:
        mark = "done" if status[stage] else "not started"
        print(f"{pipeline.STAGE_LABELS[stage]:<40} {mark}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="bookinator", description="Podcast -> fantasy novel pipeline")
    parser.add_argument("--config", type=Path, default=None, help="Path to config.toml")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_project_arg(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("project", help="Project name (folder under projects/)")

    p_new = sub.add_parser("new", help="Create a project from a source mp3 (does not run any stage)")
    add_project_arg(p_new)
    p_new.add_argument("mp3", help="Path to the source mp3 file")
    p_new.set_defaults(func=cmd_new)

    for stage in pipeline.STAGES:
        p_stage = sub.add_parser(stage, help=pipeline.STAGE_LABELS[stage])
        add_project_arg(p_stage)
        p_stage.set_defaults(func=cmd_stage(stage))

    p_all = sub.add_parser("all", help="Create a project and run the full pipeline")
    add_project_arg(p_all)
    p_all.add_argument("mp3", help="Path to the source mp3 file")
    p_all.set_defaults(func=cmd_all)

    p_status = sub.add_parser("status", help="Show which stages have completed for a project")
    add_project_arg(p_status)
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    config = Config.load(args.config)
    args.func(args, config)


if __name__ == "__main__":
    main()
