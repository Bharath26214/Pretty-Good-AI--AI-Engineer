import httpx
from telnyx import Telnyx

from voice_bot.config import get_settings
from voice_bot.scenario import SCENARIO_ID

TELNYX_API_BASE = "https://api.telnyx.com/v2"


def make_call() -> str:
    """Place an outbound TeXML call using the TeXML application ID."""
    settings = get_settings()
    webhook_base = settings.webhook_base_url

    response = httpx.post(
        f"{TELNYX_API_BASE}/texml/calls/{settings.telnyx_app_id}",
        headers={
            "Authorization": f"Bearer {settings.telnyx_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "To": settings.target_phone_number,
            "From": settings.telnyx_phone_number,
            "Url": f"{webhook_base}/incoming-call",
            "Record": True,
            "RecordingChannels": "dual",
            "SendRecordingUrl": True,
            "RecordingStatusCallback": f"{webhook_base}/recording-complete",
            "RecordingStatusCallbackEvent": "completed",
            "StatusCallback": f"{webhook_base}/call-status",
            "StatusCallbackEvent": "initiated ringing answered completed",
        },
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
    print(f"  Scenario: {SCENARIO_ID}")
    print(f"  Status:   {status}")
    print(f"  To:       {data.get('to', settings.target_phone_number)}")
    print(f"  From:     {data.get('from', settings.telnyx_phone_number)}")
    print("  Note: Telnyx assigns a Call SID after the call connects — check Mission Control.")
    return status


def verify_client() -> Telnyx:
    """Return an authenticated Telnyx client for setup checks."""
    settings = get_settings()
    return Telnyx(api_key=settings.telnyx_api_key)
