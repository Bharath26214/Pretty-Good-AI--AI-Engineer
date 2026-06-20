from dataclasses import dataclass

from voice_bot.scenarios.scenarios import SCENARIOS

DEFAULT_DOB = "August 22, 1990"
DEFAULT_NAME = "Marcus Thompson"
_DOB_KEYWORDS = ("dob", "date of birth", "birthday", "born on", "born")


@dataclass(frozen=True)
class ActiveScenario:
    id: str
    key: str
    name: str
    system_prompt: str
    unnoted: bool = False


UNNOTED_SCENARIO_ID = "00"


def is_unnoted(value: int | str) -> bool:
    text = str(value).strip().lower()
    return text in ("00", "unnoted", "cleanup")


def normalize_scenario_id(value: int | str) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError(f"Invalid scenario number: {value!r}")
    number = int(text)
    if number < 1 or number > len(SCENARIOS):
        raise ValueError(f"Scenario must be between 1 and {len(SCENARIOS)}, got {number}")
    return f"{number:02d}"


def get_scenario_dict(value: int | str) -> dict:
    sid = normalize_scenario_id(value)
    for scenario in SCENARIOS:
        if scenario["id"].startswith(f"{sid}_"):
            return scenario
    raise ValueError(f"No scenario found for id {sid}")


def _scenario_display_name(scenario: dict) -> str:
    suffix = scenario["id"].split("_", 1)[-1]
    return suffix.replace("_", " ").title()


def _dob_instruction(persona: str) -> str:
    lower = persona.lower()
    default_normalized = DEFAULT_DOB.lower().replace(",", "")
    persona_normalized = lower.replace(",", "")

    if any(keyword in lower for keyword in _DOB_KEYWORDS):
        if default_normalized not in persona_normalized:
            return (
                "If asked for your date of birth, use the date of birth described "
                "in your character below."
            )
    return f"If asked for your date of birth, say {DEFAULT_DOB}."


def build_system_prompt(scenario: dict) -> str:
    return (
        "You are a patient calling a medical clinic in the United States to schedule an appointment. "
        "Speak only in English. Use a natural, conversational tone like a real phone caller. "
        "Keep each response short (1-3 sentences). Stay in character as the patient at all times. "
        "At the start of the call, stay completely silent while the receptionist plays any recording "
        "notice, language options, or greeting — do not speak until they clearly finish and pause. "
        "Wait for the receptionist to finish speaking completely before you respond — do not interrupt or talk over them. "
        "Listen to the receptionist, answer their questions directly, and work toward booking an appointment. "
        "If asked for your phone number, give +18608509755. "
        f"Your name is {DEFAULT_NAME}. "
        f"{_dob_instruction(scenario['persona'])} "
        "Do not speak Spanish or any language other than English.\n\n"
        f"Your character: {scenario['persona']}\n\n"
        f"Your goal: {scenario['goal']}"
    )


def build_unnoted_system_prompt() -> str:
    return (
        "You are a patient calling a medical clinic in the United States. "
        "Speak only in English. Use a natural, conversational tone like a real phone caller. "
        "Keep each response short (1-3 sentences). "
        "At the start of the call, stay completely silent while the receptionist plays any recording "
        "notice, language options, or greeting — do not speak until they clearly finish and pause. "
        "Wait for the receptionist to finish speaking completely before you respond. "
        "If asked for your phone number, give +18608509755. "
        f"Your name is {DEFAULT_NAME}. "
        f"If asked for your date of birth, say {DEFAULT_DOB}. "
        "Do not speak Spanish or any language other than English.\n\n"
        "Your goal: Cancel ALL upcoming appointments on your account. "
        "Ask the receptionist to cancel every appointment you have. "
        "If they list one or more appointments, confirm each cancellation. "
        "If they say there are none on file, thank them and end the call. "
        "Once all cancellations are confirmed, thank them briefly and end the call."
    )


def load_unnoted_scenario() -> ActiveScenario:
    return ActiveScenario(
        id=UNNOTED_SCENARIO_ID,
        key="unnoted_cancel_all",
        name="Cancel all (unnoted)",
        system_prompt=build_unnoted_system_prompt(),
        unnoted=True,
    )


def load_scenario(value: int | str = "01") -> ActiveScenario:
    if is_unnoted(value):
        return load_unnoted_scenario()
    scenario = get_scenario_dict(value)
    sid = normalize_scenario_id(value)
    return ActiveScenario(
        id=sid,
        key=scenario["id"],
        name=_scenario_display_name(scenario),
        system_prompt=build_system_prompt(scenario),
    )


_default = load_scenario("01")
SCENARIO_ID = _default.id
SCENARIO_NAME = _default.name
SYSTEM_PROMPT = _default.system_prompt
