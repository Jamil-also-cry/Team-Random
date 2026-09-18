import json
import re
import httpx
from typing import List, Dict, Any, Optional
from config.config import settings
from models.schemas import BatteryData, DirectiveInterpretationItem, DirectiveAdjustment, DirectiveType
from .prompt import SYSTEM_DIRECTIVE_PROMPT, USER_DIRECTIVE_PROMPT_TEMPLATE
from optimizer.validator import validate_and_guardrail_directive


async def call_external_llm(system_prompt: str, user_prompt: str) -> str:
    """Invokes the configured external LLM provider securely and asynchronously."""
    provider = settings.LLM_PROVIDER.lower()
    api_key = settings.LLM_API_KEY
    timeout = settings.TIMEOUT_SECONDS

    if not api_key:
        raise RuntimeError("No LLM API key configured in LLM_API_KEY environment variable.")

    async with httpx.AsyncClient(timeout=timeout) as client:
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.LLM_MODEL}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": f"{system_prompt}\n\n{user_prompt}"}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.0,
                    "responseMimeType": "application/json"
                }
            }
            res = await client.post(url, json=payload)
            res.raise_for_status()
            data = res.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

        elif provider in ["openai", "groq", "generic"]:
            base_url = settings.LLM_BASE_URL
            if not base_url:
                base_url = "https://api.groq.com/openai/v1" if provider == "groq" else "https://api.openai.com/v1"
            
            url = f"{base_url.rstrip('/')}/chat/completions"
            payload = {
                "model": settings.LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"} if provider == "openai" else None
            }
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            res = await client.post(url, json=payload, headers=headers)
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"]

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")


def _clean_json_text(raw_text: str) -> str:
    """Strips markdown backticks if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def interpret_operator_notes(
    notes: List[str],
    battery: BatteryData
) -> List[DirectiveInterpretationItem]:
    """
    Genuine LLM interpreter: prompts generative model, extracts structured adjustments,
    and applies deterministic guardrail verification before downstream optimization.
    """
    notes_formatted = "\n".join([f"[{i}] \"{note}\"" for i, note in enumerate(notes)])
    user_prompt = USER_DIRECTIVE_PROMPT_TEMPLATE.format(
        capacity_kwh=battery.capacity_kwh,
        initial_energy_kwh=battery.initial_energy_kwh,
        minimum_energy_kwh=battery.minimum_energy_kwh,
        notes_text=notes_formatted
    )

    try:
        raw_llm_response = await call_external_llm(SYSTEM_DIRECTIVE_PROMPT, user_prompt)
        cleaned_json = _clean_json_text(raw_llm_response)
        parsed_data = json.loads(cleaned_json)
        
        # Handle dict wrapping (e.g., {"directives": [...]})
        if isinstance(parsed_data, dict):
            for key in ["directives", "result", "items", "data"]:
                if key in parsed_data and isinstance(parsed_data[key], list):
                    parsed_data = parsed_data[key]
                    break

        if not isinstance(parsed_data, list):
            raise ValueError("LLM returned non-list top-level structure.")

    except Exception as exc:
        # Controlled fallback: If the external LLM is momentarily unreachable or returns invalid syntax,
        # return safe no_op for each note to prevent 500 crashes while preserving API contract.
        fallback_list = []
        for i, _ in enumerate(notes):
            fallback_list.append(
                DirectiveInterpretationItem(
                    note_index=i,
                    applies=False,
                    directive_type=DirectiveType.NO_OP,
                    structured_adjustment=None,
                    explanation="Interpreted safely as no_op due to external model response fallback."
                )
            )
        return fallback_list

    # Deterministic Guardrail Validation Phase
    validated_directives: List[DirectiveInterpretationItem] = []
    
    # Map by note_index to guarantee order and absence of duplicates
    parsed_by_index: Dict[int, Any] = {}
    for item in parsed_data:
        if isinstance(item, dict) and "note_index" in item:
            parsed_by_index[int(item["note_index"])] = item

    for i in range(len(notes)):
        raw_item = parsed_by_index.get(i)
        if not raw_item:
            # Safe default if LLM missed an index
            validated_directives.append(
                DirectiveInterpretationItem(
                    note_index=i,
                    applies=False,
                    directive_type=DirectiveType.NO_OP,
                    structured_adjustment=None,
                    explanation="No directive specified for this note."
                )
            )
            continue

        guarded_item = validate_and_guardrail_directive(raw_item, i, battery)
        validated_directives.append(guarded_item)

    return validated_directives