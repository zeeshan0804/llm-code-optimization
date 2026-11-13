"""
input_generator.py
==================
Uses the LLM to generate diverse test inputs for a given code snippet.
Inputs are saved to disk alongside the code so they can be used on the
target machine to measure latency and memory (dynamic metrics).
"""
import json
from models import generate
from prompts import get_input_generation_prompt
from utils import extract_json_from_response

_INPUT_GEN_SYSTEM = (
    "You are a software testing expert. "
    "Your task is to produce test inputs for a given code snippet. "
    "Respond with valid JSON only — no markdown, no explanation, no code comments. "
    "Every value inside 'args' must be a plain string literal. "
    "Never use Python expressions, function calls, list comprehensions, or any code — "
    "only literal strings such as \"5\" or \"1 2 3 4 5\"."
)


def generate_inputs(model_key: str, language: str, code: str) -> list[dict]:
    """
    Ask the LLM to produce 5 test inputs for *code*.

    Returns a list of dicts:
        [{"input_description": "...", "args": [...]}, ...]

    Falls back to an empty list with an error entry if the LLM output cannot
    be parsed as JSON.
    """
    prompt   = get_input_generation_prompt(language, code)
    response = generate(model_key, _INPUT_GEN_SYSTEM, prompt)
    raw      = response["content"]

    try:
        json_str = extract_json_from_response(raw)
        inputs   = json.loads(json_str)
        if not isinstance(inputs, list):
            raise ValueError("Expected a JSON array")
        # Truncate any individual arg string that is excessively long (>500 chars)
        # to prevent stress-test inputs with thousands of numbers from blowing up JSON output.
        for item in inputs:
            if isinstance(item.get("args"), list):
                item["args"] = [
                    a[:500] if isinstance(a, str) and len(a) > 500 else a
                    for a in item["args"]
                ]
        return inputs
    except Exception as exc:
        return [
            {
                "input_description": f"[parse error: {exc}]",
                "args":              [],
                "_raw_llm_output":   raw,
            }
        ]
