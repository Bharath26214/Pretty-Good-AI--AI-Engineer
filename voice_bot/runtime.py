"""Start server + ngrok tunnel for one-terminal workflows."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from collections.abc import Callable
from typing import Any

import httpx
import ngrok
from dotenv import load_dotenv

DEFAULT_PORT = 8000
HEALTH_PATH = "/"


def _wait_for_server(port: int, timeout: float = 30) -> None:
    url = f"http://127.0.0.1:{port}{HEALTH_PATH}"
    deadline = time.monotonic() + timeout
    last_error = ""

    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=1)
            if response.status_code == 200:
                return
            last_error = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        time.sleep(0.5)

    raise RuntimeError(f"Server did not start on port {port}: {last_error}")


def _configure_ngrok() -> None:
    load_dotenv()
    token = (
        os.getenv("NGROK_AUTHTOKEN", "").strip()
        or os.getenv("NGROK_AUTH_TOKEN", "").strip()
    )
    if not token:
        raise RuntimeError(
            "NGROK_AUTHTOKEN is not set in .env — get one at https://dashboard.ngrok.com/get-started/your-authtoken"
        )
    ngrok.set_auth_token(token)


def _close_listener(listener: ngrok.Listener) -> None:
    try:
        asyncio.run(listener.close())
    except Exception:
        pass


def run_with_stack(action: Callable[[], Any], *, port: int = DEFAULT_PORT) -> Any:
    """Start uvicorn + ngrok, run action, then shut everything down."""
    _configure_ngrok()
    listener = None
    server: subprocess.Popen | None = None

    try:
        listener = ngrok.forward(port)
        public_url = listener.url().rstrip("/")
        print(f"Ngrok tunnel: {public_url}")

        env = os.environ.copy()
        env["WEBHOOK_BASE_URL"] = public_url

        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "voice_bot.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=env,
        )
        os.environ["WEBHOOK_BASE_URL"] = public_url

        print(f"Server starting on http://127.0.0.1:{port} ...")
        _wait_for_server(port)
        print("Server ready")

        return action()
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
        if listener is not None:
            _close_listener(listener)
        try:
            ngrok.disconnect()
        except Exception:
            pass
        print("Stopped server and ngrok")
