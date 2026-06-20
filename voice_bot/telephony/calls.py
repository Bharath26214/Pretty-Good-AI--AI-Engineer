import httpx
from telnyx import Telnyx

from voice_bot.config import get_settings
from voice_bot.scenario import load_scenario, load_unnoted_scenario, normalize_scenario_id

TELNYX_API_BASE = "https://api.telnyx.com/v2"


def make_call(scenario_id: str = "01", *, unnoted: bool = False) -> str:
    """Place an outbound TeXML call using the TeXML application ID."""
    settings = get_settings()
    webhook_base = settings.webhook_base_url

    if unnoted:
        scenario = load_unnoted_scenario()
        call_json = {
            "To": settings.target_phone_number,
            "From": settings.telnyx_phone_number,
            "Url": f"{webhook_base}/incoming-call?unnoted=1",
            "Record": False,
            "StatusCallback": f"{webhook_base}/call-status",
            "StatusCallbackEvent": "initiated ringing answered completed",
        }
    else:
        sid = normalize_scenario_id(scenario_id)
        scenario = load_scenario(sid)
        call_json = {
            "To": settings.target_phone_number,
            "From": settings.telnyx_phone_number,
            "Url": f"{webhook_base}/incoming-call?scenario={sid}",
            "Record": True,
            "RecordingChannels": "dual",
            "SendRecordingUrl": True,
            "RecordingStatusCallback": f"{webhook_base}/recording-complete?scenario={sid}",
            "RecordingStatusCallbackEvent": "completed",
            "StatusCallback": f"{webhook_base}/call-status",
            "StatusCallbackEvent": "initiated ringing answered completed",
        }

    response = httpx.post(
        f"{TELNYX_API_BASE}/texml/calls/{settings.telnyx_app_id}",
        headers={
            "Authorization": f"Bearer {settings.telnyx_api_key}",
            "Content-Type": "application/json",
        },
        json=call_json,
        timeout=30,
    )

    body = response.json()
    if response.is_error:
        errors = body.get("errors", [])
        error = errors[0] if errors else {}
        detail = error.get("detail") or response.text
        code = error.get("code", response.status_code)
        raise RuntimeError(f"Telnyx call failed ({code}): {detail}")

    data = body.get("data", {})
    status = data.get("status", "unknown")

    print("Call placed")
    print(f"  Mode:     {'unnoted cleanup (nothing saved)' if unnoted else 'test scenario'}")
    print(f"  Scenario: {scenario.id} — {scenario.name}")
    print(f"  Status:   {status}")
    print(f"  To:       {data.get('to', settings.target_phone_number)}")
    print(f"  From:     {data.get('from', settings.telnyx_phone_number)}")
    if unnoted:
        print("  Note: No recording, transcript, or bug report will be saved.")
    else:
        print("  Note: Telnyx assigns a Call SID after the call connects — check Mission Control.")
    return status


def verify_client() -> Telnyx:
    """Return an authenticated Telnyx client for setup checks."""
    settings = get_settings()
    return Telnyx(api_key=settings.telnyx_api_key)
