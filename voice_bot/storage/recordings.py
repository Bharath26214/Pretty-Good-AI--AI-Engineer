import asyncio
from pathlib import Path
from urllib.parse import urlparse

import httpx

from voice_bot.config import Settings
from voice_bot.storage.paths import RECORDINGS_DIR, call_artifact_stem, ensure_storage_dirs

TELNYX_API_BASE = "https://api.telnyx.com/v2"


def _safe_call_id(call_id: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in call_id)[:64]


def recording_exists_for_call(call_id: str) -> Path | None:
    safe_call_id = _safe_call_id(call_id)
    matches = sorted(RECORDINGS_DIR.glob(f"*_{safe_call_id}*.mp3"))
    return matches[0] if matches else None


def _recording_extension(recording_url: str, content_type: str | None) -> str:
    path = urlparse(recording_url).path.lower()
    if path.endswith(".mp3"):
        return ".mp3"
    if path.endswith(".wav"):
        return ".wav"
    if content_type:
        if "mpeg" in content_type or "mp3" in content_type:
            return ".mp3"
        if "wav" in content_type:
            return ".wav"
    return ".mp3"


def _uses_presigned_url(recording_url: str) -> bool:
    """Telnyx recording URLs are pre-signed S3 links and must not get extra auth headers."""
    lowered = recording_url.lower()
    return "amazonaws.com" in lowered or "x-amz-signature" in lowered


async def _download_recording(
    settings: Settings,
    recording_url: str,
    output_path: Path,
) -> Path:
    headers = {}
    if not _uses_presigned_url(recording_url):
        headers["Authorization"] = f"Bearer {settings.telnyx_api_key}"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            recording_url,
            headers=headers,
            follow_redirects=True,
        )
        response.raise_for_status()

    extension = _recording_extension(recording_url, response.headers.get("content-type"))
    if output_path.suffix != extension:
        output_path = output_path.with_suffix(extension)

    output_path.write_bytes(response.content)
    print(f"Recording saved: {output_path}")
    return output_path


async def save_recording(
    settings: Settings,
    *,
    recording_url: str,
    scenario_id: str,
    call_id: str,
    recording_sid: str | None = None,
    started_at=None,
) -> Path | None:
    if not recording_url:
        print("Recording webhook missing URL — skipping download")
        return None

    lookup_id = call_id or recording_sid or "unknown"
    existing = recording_exists_for_call(lookup_id)
    if existing:
        print(f"Recording already saved: {existing}")
        return existing

    ensure_storage_dirs()
    stem = call_artifact_stem(
        scenario_id,
        call_id or recording_sid or "unknown",
        started_at,
    )
    return await _download_recording(settings, recording_url, RECORDINGS_DIR / f"{stem}.mp3")


async def fetch_call_recordings(
    settings: Settings,
    *,
    account_sid: str,
    call_sid: str,
    scenario_id: str,
    retries: int = 4,
    delay_seconds: float = 5.0,
) -> list[Path]:
    """Fetch recordings from Telnyx when the recording webhook is delayed."""
    ensure_storage_dirs()
    url = f"{TELNYX_API_BASE}/texml/Accounts/{account_sid}/Calls/{call_sid}/Recordings.json"

    for attempt in range(1, retries + 1):
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {settings.telnyx_api_key}"},
            )
            response.raise_for_status()
            body = response.json()

        recordings = body.get("recordings") or []
        if recordings:
            saved: list[Path] = []
            for index, recording in enumerate(recordings, start=1):
                media_url = recording.get("media_url") or recording.get("MediaUrl")
                if not media_url:
                    continue

                stem = call_artifact_stem(scenario_id, call_sid)
                suffix = f"_{index}" if len(recordings) > 1 else ""
                output_path = RECORDINGS_DIR / f"{stem}{suffix}.mp3"
                saved.append(await _download_recording(settings, media_url, output_path))
            return saved

        if attempt < retries:
            print(
                f"No recordings found yet for call {call_sid} "
                f"(retry {attempt}/{retries - 1} in {delay_seconds:.0f}s)"
            )
            await asyncio.sleep(delay_seconds)

    print(f"No recordings found for call {call_sid} after {retries} attempts")
    return []
