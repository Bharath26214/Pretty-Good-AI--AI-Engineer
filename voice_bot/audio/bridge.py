import asyncio
import json

from fastapi import WebSocket
from openai import AsyncOpenAI

from voice_bot.config import Settings
from voice_bot.scenario import ActiveScenario
from voice_bot.storage.transcripts import CallTranscript

# Wait for this much agent silence before treating their turn as finished.
AGENT_SILENCE_MS = 2000
# Extra pause after the agent stops before the patient speaks.
RESPONSE_BUFFER_SEC = 2.0


def realtime_session_config(settings: Settings, system_prompt: str) -> dict:
    """OpenAI GA Realtime API session shape."""
    return {
        "type": "realtime",
        "instructions": system_prompt,
        "audio": {
            "input": {
                "format": {"type": "audio/pcmu"},
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": AGENT_SILENCE_MS,
                    "create_response": False,
                    "interrupt_response": False,
                },
                "transcription": {"model": "gpt-4o-mini-transcribe"},
            },
            "output": {
                "format": {"type": "audio/pcmu"},
                "voice": settings.openai_voice,
            },
        },
    }


async def bridge_media_stream(
    websocket: WebSocket,
    openai_client: AsyncOpenAI,
    settings: Settings,
    scenario: ActiveScenario,
) -> CallTranscript:
    """Bridge audio between Telnyx and OpenAI Realtime API."""
    transcript = CallTranscript(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
    )
    stop = asyncio.Event()
    response_delay_task: asyncio.Task | None = None
    patient_responding = False
    print(f"Using scenario {scenario.id}: {scenario.name}")

    async with openai_client.realtime.connect(model=settings.openai_model) as openai_ws:
        await openai_ws.session.update(
            session=realtime_session_config(settings, scenario.system_prompt)
        )

        def cancel_scheduled_response() -> None:
            nonlocal response_delay_task
            if response_delay_task and not response_delay_task.done():
                response_delay_task.cancel()

        async def schedule_patient_response() -> None:
            nonlocal response_delay_task
            if patient_responding or stop.is_set():
                return

            cancel_scheduled_response()

            async def _speak_after_buffer() -> None:
                await asyncio.sleep(RESPONSE_BUFFER_SEC)
                if stop.is_set() or patient_responding:
                    return
                await openai_ws.response.create()

            response_delay_task = asyncio.create_task(_speak_after_buffer())

        async def receive_from_telnyx():
            async for message in websocket.iter_text():
                data = json.loads(message)
                event = data.get("event")

                if event == "start":
                    start = data.get("start", {})
                    call_id = (
                        start.get("call_control_id")
                        or start.get("call_session_id")
                        or data.get("stream_id")
                    )
                    transcript.set_call_id(str(call_id or "unknown"))
                    print(f"Stream started: {data.get('stream_id')}")
                    continue

                if event == "connected":
                    continue

                if event == "media":
                    track = data.get("media", {}).get("track")
                    if track and track != "inbound":
                        continue

                    await openai_ws.input_audio_buffer.append(
                        audio=data["media"]["payload"]
                    )
                elif event == "stop":
                    print("Telnyx stream stopped")
                    stop.set()
                    cancel_scheduled_response()
                    break

        async def receive_from_openai():
            nonlocal patient_responding

            async for event in openai_ws:
                if stop.is_set():
                    break

                if event.type == "input_audio_buffer.speech_started":
                    cancel_scheduled_response()
                elif event.type == "input_audio_buffer.speech_stopped":
                    await schedule_patient_response()
                elif event.type == "response.created":
                    patient_responding = True
                    cancel_scheduled_response()
                elif event.type == "response.output_audio.delta" and event.delta:
                    await websocket.send_json(
                        {
                            "event": "media",
                            "media": {"payload": event.delta},
                        }
                    )
                elif event.type == "response.output_audio_transcript.done":
                    transcript.add("Patient", event.transcript)
                    print(f"Patient: {event.transcript}")
                elif event.type == "conversation.item.input_audio_transcription.completed":
                    transcript.add("Agent", event.transcript)
                    print(f"Agent: {event.transcript}")
                elif event.type == "response.done":
                    patient_responding = False
                    print()

        telnyx_task = asyncio.create_task(receive_from_telnyx())
        openai_task = asyncio.create_task(receive_from_openai())

        try:
            await telnyx_task
        finally:
            stop.set()
            cancel_scheduled_response()
            openai_task.cancel()
            try:
                await openai_task
            except asyncio.CancelledError:
                pass

    return transcript
