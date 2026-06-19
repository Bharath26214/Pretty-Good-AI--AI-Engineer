import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from voice_bot.storage.paths import TRANSCRIPTS_DIR, call_artifact_stem, ensure_storage_dirs


@dataclass
class TranscriptEntry:
    timestamp: str
    speaker: str
    text: str


@dataclass
class CallTranscript:
    scenario_id: str
    scenario_name: str
    call_id: str = "unknown"
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    entries: list[TranscriptEntry] = field(default_factory=list)

    def set_call_id(self, call_id: str) -> None:
        if call_id:
            self.call_id = call_id

    def add(self, speaker: str, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.entries.append(
            TranscriptEntry(
                timestamp=datetime.now(UTC).isoformat(),
                speaker=speaker,
                text=text,
            )
        )

    def save(self) -> Path:
        ensure_storage_dirs()
        stem = call_artifact_stem(self.scenario_id, self.call_id, self.started_at)
        txt_path = TRANSCRIPTS_DIR / f"{stem}.txt"
        json_path = TRANSCRIPTS_DIR / f"{stem}.json"

        lines = [
            f"Scenario: {self.scenario_id} - {self.scenario_name}",
            f"Call ID: {self.call_id}",
            f"Started: {self.started_at.isoformat()}",
            "",
        ]
        for entry in self.entries:
            lines.append(f"[{entry.timestamp}] {entry.speaker}: {entry.text}")

        txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        json_path.write_text(
            json.dumps(
                {
                    "scenario_id": self.scenario_id,
                    "scenario_name": self.scenario_name,
                    "call_id": self.call_id,
                    "started_at": self.started_at.isoformat(),
                    "entries": [
                        {
                            "timestamp": entry.timestamp,
                            "speaker": entry.speaker,
                            "text": entry.text,
                        }
                        for entry in self.entries
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        print(f"Transcript saved: {txt_path}")
        return txt_path
