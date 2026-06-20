from urllib.parse import parse_qs

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response
from openai import AsyncOpenAI

from voice_bot.audio.bridge import bridge_media_stream
from voice_bot.config import get_settings, webhook_host
from voice_bot.scenario import ActiveScenario, load_scenario, load_unnoted_scenario
from voice_bot.storage import ensure_storage_dirs
from voice_bot.storage.recordings import save_recording
from voice_bot.telephony.texml import incoming_call_texml

settings = get_settings()
ensure_storage_dirs()

app = FastAPI(title="PGAI Voice Bot")
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)


@app.get("/")
async def health_check():
    return {"status": "ok"}


@app.api_route("/incoming-call", methods=["GET", "POST"])
async def incoming_call(request: Request):
    """Return TeXML telling Telnyx to stream audio to our WebSocket."""
    scenario = _scenario_from_params(request.query_params)
    host = webhook_host()
    stream_url = f"wss://{host}/media-stream?{_scenario_query(scenario)}"

    print(f"Call connected — scenario {scenario.id}, streaming to {stream_url}")
    return Response(
        content=incoming_call_texml(stream_url),
        media_type="application/xml",
    )


@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    await websocket.accept()
    scenario = _scenario_from_params(websocket.query_params)
    print("WebSocket connected")

    transcript = None
    try:
        transcript = await bridge_media_stream(websocket, openai_client, settings, scenario)
    except Exception as exc:
        print(f"Media stream error: {exc}")
        raise
    finally:
        if transcript is not None and not scenario.unnoted:
            path = transcript.save()
            if not transcript.entries:
                print(f"Warning: transcript has no dialogue lines yet: {path}")
        elif scenario.unnoted:
            print("Unnoted call — transcript not saved")
        print("WebSocket closed")


@app.api_route("/call-status", methods=["GET", "POST"])
async def call_status(request: Request):
    payload = await _webhook_payload(request)
    call_id = (
        payload.get("CallSid")
        or payload.get("CallControlId")
        or payload.get("call_control_id")
    )
    status = payload.get("CallStatus") or payload.get("call_status") or payload.get("status")
    print(f"Call {call_id} status: {status}")
    return {"status": "ok"}


@app.api_route("/recording-complete", methods=["GET", "POST"])
async def recording_complete(request: Request):
    if request.query_params.get("unnoted") in ("1", "true", "yes"):
        print("Unnoted call — recording ignored")
        return {"status": "ok"}

    payload = await _webhook_payload(request)
    scenario = _scenario_from_params(request.query_params)
    if scenario.unnoted:
        print("Unnoted call — recording not saved")
        return {"status": "ok"}

    recording_url = payload.get("RecordingUrl") or payload.get("recording_url")
    recording_sid = payload.get("RecordingSid") or payload.get("recording_sid")
    call_id = (
        payload.get("CallSid")
        or payload.get("CallControlId")
        or payload.get("call_control_id")
        or recording_sid
        or "unknown"
    )

    print(f"Recording ready: {recording_url} (sid={recording_sid})")

    try:
        await save_recording(
            settings,
            recording_url=str(recording_url or ""),
            scenario_id=scenario.id,
            call_id=str(call_id),
            recording_sid=str(recording_sid) if recording_sid else None,
        )
    except Exception as exc:
        print(f"Failed to save recording: {exc}")

    return {"status": "ok"}


def _scenario_from_params(params) -> ActiveScenario:
    if params.get("unnoted") in ("1", "true", "yes"):
        return load_unnoted_scenario()
    return load_scenario(params.get("scenario", "01"))


def _scenario_query(scenario: ActiveScenario) -> str:
    if scenario.unnoted:
        return "unnoted=1"
    return f"scenario={scenario.id}"


async def _webhook_payload(request: Request) -> dict:
    """Telnyx TeXML callbacks arrive as query params (GET) or form/JSON (POST)."""
    if request.query_params:
        return dict(request.query_params)

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        if isinstance(body, dict) and "data" in body and isinstance(body["data"], dict):
            payload = body["data"].get("payload", body["data"])
            return payload if isinstance(payload, dict) else body
        return body if isinstance(body, dict) else {}

    if request.method == "POST":
        raw = await request.body()
        if raw:
            parsed = parse_qs(raw.decode("utf-8"))
            return {key: values[0] for key, values in parsed.items() if values}

    return {}
