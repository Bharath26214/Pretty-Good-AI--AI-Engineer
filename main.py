"""CLI entry point for the PGAI voice bot."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _cmd_call(args: argparse.Namespace) -> None:
    from voice_bot.bug_report import run_call_and_report
    from voice_bot.runtime import run_with_stack
    from voice_bot.scenario import normalize_scenario_id
    from voice_bot.telephony.calls import make_call

    sid = normalize_scenario_id(args.scenario)

    def action() -> None:
        if args.no_report:
            make_call(sid)
            return
        run_call_and_report(scenario_id=sid, timeout=args.timeout, force=args.force)

    run_with_stack(action, port=args.port)


def _cmd_cleanup(args: argparse.Namespace) -> None:
    from voice_bot.runtime import run_with_stack
    from voice_bot.telephony.calls import make_call

    def action() -> None:
        make_call(unnoted=True)
        if args.wait > 0:
            print(f"Waiting {int(args.wait)}s for call to finish...")
            time.sleep(args.wait)

    run_with_stack(action, port=args.port)


def _cmd_bug_report(args: argparse.Namespace) -> None:
    from voice_bot.bug_report import process_all, process_latest, process_transcript

    if args.all:
        process_all(force=args.force)
    elif args.transcript:
        process_transcript(args.transcript, force=args.force)
    else:
        process_latest(force=args.force)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="PGAI voice bot — all commands run from the CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    call = subparsers.add_parser(
        "call",
        help="Run a test scenario (starts server + ngrok automatically)",
    )
    call.add_argument(
        "scenario",
        nargs="?",
        default="01",
        metavar="N",
        help="Scenario number 1-12 (default: 1)",
    )
    call.add_argument(
        "--no-report",
        action="store_true",
        help="Skip bug report generation after the call",
    )
    call.add_argument(
        "--timeout",
        type=float,
        default=600,
        help="Seconds to wait for transcript (default: 600)",
    )
    call.add_argument(
        "--force",
        action="store_true",
        help="Regenerate bug report even if already reported",
    )
    call.add_argument("--port", type=int, default=8000, help="Local server port")
    call.set_defaults(func=_cmd_call)

    cleanup = subparsers.add_parser(
        "cleanup",
        help="Cancel all appointments — no recording, transcript, or bug report saved",
    )
    cleanup.add_argument(
        "--wait",
        type=float,
        default=180,
        help="Seconds to wait for call to finish (default: 180)",
    )
    cleanup.add_argument("--port", type=int, default=8000, help="Local server port")
    cleanup.set_defaults(func=_cmd_cleanup)

    bug_report = subparsers.add_parser(
        "bug-report",
        help="Generate bug reports from saved transcript JSON files",
    )
    bug_report.add_argument(
        "--transcript",
        type=Path,
        help="Path to a transcript JSON file (default: latest)",
    )
    bug_report.add_argument(
        "--all",
        action="store_true",
        help="Process every transcript JSON file",
    )
    bug_report.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if already reported",
    )
    bug_report.set_defaults(func=_cmd_bug_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
