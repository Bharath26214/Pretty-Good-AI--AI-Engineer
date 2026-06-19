import asyncio
import json

from fastapi import WebSocket
from openai import AsyncOpenAI

from voice_bot.config import Settings
from voice_bot.scenario import SCENARIO_ID, SCENARIO_NAME, SYSTEM_PROMPT
from voice_bot.storage.transcripts import CallTranscript


def realtime_session_config(settings: Settings) -> dict:
    """OpenAI GA Realtime API session shape."""
    return {
        "type": "realtime",
        "instructions": SYSTEM_PROMPT,
        "audio": {
            "input": {
                "format": {"type": "audio/pcmu"},
                "turn_detection": {"type": "server_vad"},
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
) -> CallTranscript:
    """Bridge audio between Telnyx and OpenAI Realtime API."""
    transcript = CallTranscript(
        scenario_id=SCENARIO_ID,
        scenario_name=SCENARIO_NAME,
    )
    stop = asyncio.Event()
    print(f"Using scenario {SCENARIO_ID}: {SCENARIO_NAME}")

    async with openai_client.realtime.connect(model=settings.openai_model) as openai_ws:
        await openai_ws.session.update(session=realtime_session_config(settings))

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
                    break

        async def receive_from_openai():
            async for event in openai_ws:
                if stop.is_set():
                    break

                if event.type == "response.output_audio.delta" and event.delta:
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
                    print()

        telnyx_task = asyncio.create_task(receive_from_telnyx())
        openai_task = asyncio.create_task(receive_from_openai())

        try:
            await telnyx_task
        finally:
            stop.set()
            openai_task.cancel()
            try:
                await openai_task
            except asyncio.CancelledError:
                pass

    return transcript
