"""CLI entry point for the PGAI voice bot."""

from __future__ import annotations

import argparse
import sys


def _cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "voice_bot.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


def _cmd_call(_: argparse.Namespace) -> None:
    from voice_bot.telephony.calls import make_call

    make_call()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="PGAI voice bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the FastAPI webhook server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve.set_defaults(func=_cmd_serve)

    call = subparsers.add_parser("call", help="Place an outbound test call")
    call.set_defaults(func=_cmd_call)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
