"""CLI entry point for the PGAI voice bot."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "voice_bot.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def _cmd_call(args: argparse.Namespace) -> None:
    from voice_bot.scenario import normalize_scenario_id

    sid = normalize_scenario_id(args.scenario)

    if args.no_report:
        from voice_bot.telephony.calls import make_call

        make_call(sid)
        return

    from voice_bot.bug_report import run_call_and_report

    run_call_and_report(scenario_id=sid, timeout=args.timeout, force=args.force)


def _cmd_cleanup(args: argparse.Namespace) -> None:
    import time

    from voice_bot.telephony.calls import make_call

    make_call(unnoted=True)
    if args.wait > 0:
        print(f"Waiting {int(args.wait)}s for call to finish...")
        time.sleep(args.wait)


def _cmd_run_call(args: argparse.Namespace) -> None:
    from voice_bot.runtime import run_with_stack
    from voice_bot.scenario import normalize_scenario_id

    sid = normalize_scenario_id(args.scenario)

    def action() -> None:
        if args.no_report:
            from voice_bot.telephony.calls import make_call

            make_call(sid)
            return

        from voice_bot.bug_report import run_call_and_report

        run_call_and_report(scenario_id=sid, timeout=args.timeout, force=args.force)

    run_with_stack(action, port=args.port)


def _cmd_run_cleanup(args: argparse.Namespace) -> None:
    import time

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
    parser = argparse.ArgumentParser(description="PGAI voice bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the FastAPI webhook server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve.set_defaults(func=_cmd_serve)

    call = subparsers.add_parser(
        "call",
        help="Place a test call, wait for transcript, and generate bug report",
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
        help="Only place the call; do not wait for transcript or bug report",
    )
    call.add_argument(
        "--timeout",
        type=float,
        default=600,
        help="Seconds to wait for transcript after placing call (default: 600)",
    )
    call.add_argument(
        "--force",
        action="store_true",
        help="Regenerate bug report even if this transcript was already reported",
    )
    call.set_defaults(func=_cmd_call)

    cleanup = subparsers.add_parser(
        "cleanup",
        help="Unnoted call to cancel all appointments — saves nothing",
    )
    cleanup.add_argument(
        "--wait",
        type=float,
        default=180,
        help="Seconds to wait for the call to finish (default: 180, 0 = return immediately)",
    )
    cleanup.set_defaults(func=_cmd_cleanup)

    run = subparsers.add_parser(
        "run",
        help="One terminal: start server + ngrok, then call or cleanup",
    )
    run_sub = run.add_subparsers(dest="run_command", required=True)

    run_call = run_sub.add_parser("call", help="Run scenario call with auto server + ngrok")
    run_call.add_argument(
        "scenario",
        nargs="?",
        default="01",
        metavar="N",
        help="Scenario number 1-12 (default: 1)",
    )
    run_call.add_argument("--port", type=int, default=8000)
    run_call.add_argument("--no-report", action="store_true")
    run_call.add_argument("--timeout", type=float, default=600)
    run_call.add_argument("--force", action="store_true")
    run_call.set_defaults(func=_cmd_run_call)

    run_cleanup = run_sub.add_parser(
        "cleanup",
        help="Unnoted cancel-all call with auto server + ngrok",
    )
    run_cleanup.add_argument("--port", type=int, default=8000)
    run_cleanup.add_argument("--wait", type=float, default=180)
    run_cleanup.set_defaults(func=_cmd_run_cleanup)

    bug_report = subparsers.add_parser(
        "bug-report",
        help="Generate bug reports from transcript JSON using GPT-4o mini",
    )
    bug_report.add_argument(
        "--transcript",
        type=Path,
        help="Path to a transcript JSON file (default: latest in transcripts/)",
    )
    bug_report.add_argument(
        "--all",
        action="store_true",
        help="Process every transcript JSON file",
    )
    bug_report.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if this transcript was already reported",
    )
    bug_report.set_defaults(func=_cmd_bug_report)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
