from xml.sax.saxutils import escape


def incoming_call_texml(stream_url: str) -> str:
    """Build TeXML that connects the call to our bidirectional media WebSocket."""
    safe_url = escape(stream_url, {'"': "&quot;"})

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{safe_url}"
            bidirectionalMode="rtp"
            bidirectionalCodec="PCMU"
            codec="PCMU"
            track="both_tracks" />
  </Connect>
</Response>"""
