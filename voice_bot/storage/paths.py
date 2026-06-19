from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RECORDINGS_DIR = PROJECT_ROOT / "recordings"
TRANSCRIPTS_DIR = PROJECT_ROOT / "transcripts"


def ensure_storage_dirs() -> None:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def call_artifact_stem(scenario_id: str, call_id: str, started_at: datetime | None = None) -> str:
    timestamp = (started_at or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    safe_call_id = _sanitize(call_id)
    return f"{scenario_id}_{timestamp}_{safe_call_id}"


def _sanitize(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)[:64]
