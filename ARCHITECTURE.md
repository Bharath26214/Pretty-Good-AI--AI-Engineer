# Architecture

The voice bot is a **Telnyx + OpenAI Realtime** pipeline wrapped in a small **FastAPI** server. A CLI command places an outbound TeXML call to the PGAI test line; when the call connects, Telnyx hits `/incoming-call`, which returns TeXML that opens a bidirectional WebSocket to `/media-stream`. That WebSocket bridges **PCMU audio** in both directions between the phone call and OpenAI’s Realtime API, while a scenario-specific system prompt makes the model behave as a scripted patient. When the call ends, Telnyx sends a recording URL to `/recording-complete` (saved as MP3), the bridge saves a dialogue transcript (agent vs. patient), and a separate **GPT-4o mini** step reads the transcript JSON plus scenario test criteria to append a structured bug report.

Key design choices: **Telnyx** was chosen since it had more flexibility and economical while consuming tokens. **OpenAI Realtime (GA)** with `audio/pcmu` end-to-end avoids transcoding and keeps latency low on a phone call. Didn't use the static API since transcribing and execution will add latency. **Turn-taking is manual** — server VAD detects when the clinic agent stops speaking, then the bot waits an extra two seconds before responding — so it does not talk over the recording disclaimer or interrupt mid-sentence and voices get overlapped. Scenarios are plain data in `scenarios.py` and selected via CLI (`call 5`), passed through webhook query params so the server does not depend on a hardcoded active scenario. Recordings are saved only once from the recording webhook (not call-status) to prevent duplicates. An **unnoted cleanup** mode disables recording and transcript saving for a one-off “cancel all appointments” call to execute more scenarios.

# Agent Pros

1. The Call assistant is equipped with excellent guardrails since it does not answer clinical and complex insurance questions regardless of how hardly its been prompted.
2. The Agent doesn't allow invalid birthday and check the date. It also doesn't allow booking on weekend or public holidays.
3. The Agent doesn't go off track and keeps the conversation formal and on-topic.

# Agent Cons

1. Agent when given false birthday doesn't move forward with the appointment but doesn't prompt the user about the invalid birthday which makes the user confused.
2. There is redundancy in the agent responses. Uttered 'Something's not right' multiple times when asked weekend appointments. Doesn't prompt the user about the date falls on weekend lacking clarity.