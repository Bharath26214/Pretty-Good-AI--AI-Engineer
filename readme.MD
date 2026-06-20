# Pretty Good AI — Voice Bot

Automated patient voice bot for testing the PGAI clinic line. Everything is controlled from the CLI.

## Setup

```bash
poetry install
cp .env.example .env   # fill in API keys (see below)
```

| Variable | Required for |
|---|---|
| `OPENAI_API_KEY` | Patient voice + bug reports |
| `TELNYX_API_KEY` | Outbound calls |
| `TELNYX_PHONE_NUMBER` | Caller ID |
| `TELNYX_APP_ID` | TeXML application |
| `TARGET_PHONE_NUMBER` | PGAI test line (`+18054398008`) |
| `NGROK_AUTHTOKEN` | Public tunnel (also accepts `NGROK_AUTH_TOKEN`) |

Set your Telnyx TeXML app Voice URL to `{WEBHOOK_BASE_URL}/incoming-call`. When using the CLI below, the webhook URL is set automatically — you do not need to run ngrok separately.

## CLI

All commands start the server and ngrok tunnel automatically, then shut down when done.

### Run a test scenario

Places a call, saves recording + transcript, and generates a bug report.

```bash
poetry run python main.py call        # scenario 1
poetry run python main.py call 5      # scenario 5
poetry run python main.py call 12     # scenario 12
```

Options:

```bash
poetry run python main.py call 3 --no-report    # skip bug report
poetry run python main.py call 3 --force        # regenerate bug report
poetry run python main.py call 3 --timeout 900  # longer wait
```

### Cleanup (cancel all appointments)

Unnoted call — saves nothing (no recording, transcript, or bug report).

```bash
poetry run python main.py cleanup
poetry run python main.py cleanup --wait 300
```

### Bug reports only

Re-run reports from existing transcripts without placing a call.

```bash
poetry run python main.py bug-report              # latest transcript
poetry run python main.py bug-report --all        # all transcripts
poetry run python main.py bug-report --transcript transcripts/....json
```

## Scenarios

| # | What it tests |
|---|---|
| 1 | Happy-path scheduling |
| 2 | Invalid DOB validation |
| 3 | Pediatric / child appointment |
| 4 | Medication refill |
| 5 | Far-future date scheduling |
| 6 | Off-topic / AI disclosure |
| 7 | Insurance hallucination trap |
| 8 | De-escalation under pressure |
| 9 | Clinical advice scope creep |
| 10 | Gaslighting appointment time |
| 11 | Day/date calendar mismatch |
| 12 | Cancellation flow |

Definitions: `voice_bot/scenarios/scenarios.py`

## Outputs

```
recordings/    MP3 call recordings
transcripts/   .txt + .json dialogue logs
bug_reports/   scenario_XX.md (appended per call)
```

## Troubleshooting

**Port 8000 in use** — stop any old server process before running a command.

**Call placed but bot silent** — check `NGROK_AUTHTOKEN` in `.env`.

**Bot interrupts agent** — bridge waits 2s of agent silence + 2s buffer before speaking.

See [ARCHITECTURE.md](ARCHITECTURE.md) for system design.
