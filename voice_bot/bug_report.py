import json
import time
from datetime import UTC, datetime
from pathlib import Path

from openai import OpenAI

from voice_bot.config import get_settings
from voice_bot.scenarios.scenarios import SCENARIOS
from voice_bot.storage.paths import PROJECT_ROOT, TRANSCRIPTS_DIR

BUG_REPORTS_DIR = PROJECT_ROOT / "bug_reports"
BUG_REPORT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are a QA engineer reviewing voice agent test calls for a medical clinic.
Write a concise, professional bug report from the transcript and test criteria.
Quote the agent only as evidence. Keep the full report under 250 words.
If the agent behaved correctly, verdict is Pass.

Use exactly this structure:

# Bug Report
**Scenario:** [id — name]
**Call ID:** [call_id]
**Date:** [started_at]
**Verdict:** Pass | Fail | Partial
**Severity:** None | Low | Medium | High | Critical

## Summary
One or two sentences.

## Issues
Number each issue, or write "None identified."

## Expected Behavior
Brief — what the agent should do per the test focus.

## Actual Behavior
Brief — what the agent did.

## Recommendation
One actionable fix, or "No action needed."
"""


def ensure_bug_reports_dir() -> None:
    BUG_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def find_scenario(scenario_id: str) -> dict | None:
    sid = scenario_id.strip()
    for scenario in SCENARIOS:
        if scenario["id"].startswith(sid) or scenario["id"].split("_")[0] == sid:
            return scenario
    return None


def compact_transcript(transcript: dict) -> str:
    lines: list[str] = []
    for entry in transcript.get("entries", []):
        text = entry.get("text", "").strip()
        if text:
            lines.append(f"{entry.get('speaker', '?')}: {text}")
    return "\n".join(lines)


def _build_user_prompt(transcript: dict, scenario: dict | None) -> str:
    scenario_id = transcript.get("scenario_id", "unknown")
    scenario_name = transcript.get("scenario_name", "unknown")

    parts = [
        f"Scenario ID: {scenario_id}",
        f"Scenario name: {scenario_name}",
        f"Call ID: {transcript.get('call_id', 'unknown')}",
        f"Started: {transcript.get('started_at', 'unknown')}",
    ]

    if scenario:
        parts.extend(
            [
                f"Test focus: {scenario.get('edge') or scenario.get('notes', '')}",
                f"Patient goal: {scenario.get('goal', '')}",
            ]
        )

    parts.append("\nTranscript:\n" + compact_transcript(transcript))
    return "\n".join(parts)


def generate_bug_report(transcript_path: Path) -> str:
    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    scenario = find_scenario(str(transcript.get("scenario_id", "")))

    client = OpenAI(api_key=get_settings().openai_api_key)
    response = client.chat.completions.create(
        model=BUG_REPORT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(transcript, scenario)},
        ],
        temperature=0.2,
        max_tokens=600,
    )

    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned an empty bug report")
    return content.strip()


def _scenario_report_path(scenario_id: str) -> Path:
    sid = scenario_id.zfill(2) if scenario_id.isdigit() else scenario_id
    return BUG_REPORTS_DIR / f"scenario_{sid}.md"


def _already_reported(report_path: Path, transcript_name: str) -> bool:
    return report_path.exists() and transcript_name in report_path.read_text(encoding="utf-8")


def append_bug_report(
    scenario_id: str,
    report: str,
    *,
    transcript_path: Path,
    force: bool = False,
) -> Path:
    ensure_bug_reports_dir()
    out_path = _scenario_report_path(scenario_id)

    if not force and _already_reported(out_path, transcript_path.name):
        print(f"Skipping {transcript_path.name} — already in {out_path.name}")
        return out_path

    if not out_path.exists():
        sid = scenario_id.zfill(2) if scenario_id.isdigit() else scenario_id
        out_path.write_text(f"# Scenario {sid} Bug Reports\n", encoding="utf-8")

    block = (
        f"\n\n---\n\n"
        f"_Generated {datetime.now(UTC).isoformat()} from `{transcript_path.name}`_\n\n"
        f"{report}\n"
    )
    with out_path.open("a", encoding="utf-8") as handle:
        handle.write(block)

    print(f"Bug report appended: {out_path}")
    return out_path


def process_transcript(transcript_path: Path, *, force: bool = False) -> Path:
    transcript_path = transcript_path.resolve()
    if not transcript_path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    transcript = json.loads(transcript_path.read_text(encoding="utf-8"))
    scenario_id = str(transcript.get("scenario_id", "unknown"))
    out_path = _scenario_report_path(scenario_id)

    if not force and _already_reported(out_path, transcript_path.name):
        print(f"Skipping {transcript_path.name} — already in {out_path.name}")
        return out_path

    report = generate_bug_report(transcript_path)
    return append_bug_report(
        scenario_id,
        report,
        transcript_path=transcript_path,
        force=force,
    )


def list_transcripts() -> list[Path]:
    if not TRANSCRIPTS_DIR.exists():
        return []
    return sorted(TRANSCRIPTS_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime)


def process_latest(*, force: bool = False) -> Path:
    transcripts = list_transcripts()
    if not transcripts:
        raise FileNotFoundError(f"No transcript JSON files in {TRANSCRIPTS_DIR}")
    return process_transcript(transcripts[-1], force=force)


def process_all(*, force: bool = False) -> list[Path]:
    transcripts = list_transcripts()
    if not transcripts:
        raise FileNotFoundError(f"No transcript JSON files in {TRANSCRIPTS_DIR}")

    saved: list[Path] = []
    for transcript_path in transcripts:
        saved.append(process_transcript(transcript_path, force=force))
    return saved


def wait_for_new_transcript(
    *,
    known_files: set[str],
    scenario_id: str,
    timeout: float = 600,
    poll_interval: float = 3,
) -> Path:
    """Wait until the server saves a new transcript JSON for this scenario."""
    deadline = time.monotonic() + timeout
    prefix = f"{scenario_id}_"

    print(f"Waiting for call to finish and transcript to save (timeout {int(timeout)}s)...")

    while time.monotonic() < deadline:
        for path in sorted(TRANSCRIPTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
            if path.name in known_files:
                continue
            if not path.name.startswith(prefix):
                continue
            # Brief pause so the server finishes writing the file.
            time.sleep(0.5)
            return path.resolve()

        time.sleep(poll_interval)

    raise TimeoutError(
        f"No new transcript for scenario {scenario_id} within {int(timeout)}s. "
        "Is the server running with ngrok?"
    )


def run_call_and_report(
    *,
    scenario_id: str = "01",
    timeout: float = 600,
    force: bool = False,
) -> Path:
    """Place a call, wait for the transcript, then generate a bug report."""
    from voice_bot.scenario import load_scenario, normalize_scenario_id
    from voice_bot.telephony.calls import make_call

    sid = normalize_scenario_id(scenario_id)
    scenario = load_scenario(sid)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    known = {path.name for path in TRANSCRIPTS_DIR.glob("*.json")}

    make_call(sid)
    transcript_path = wait_for_new_transcript(
        known_files=known,
        scenario_id=scenario.id,
        timeout=timeout,
    )
    print(f"Transcript ready: {transcript_path.name}")
    return process_transcript(transcript_path, force=force)
