"""
models.py
=========
Thin wrapper around the OpenAI-compatible chat completions API.
Both GPT-4o (OpenAI) and Qwen (Together.ai) use the same client.

Supports both synchronous (standard) and batch API modes.
"""
import json
import time
from openai import OpenAI
from config import MODELS


API_TIMEOUT = 300  # seconds before giving up on a single request
API_MAX_RETRIES = 0  # fail fast — the SDK's default of 2 hides 5+ minute hangs


def _client(model_key: str) -> OpenAI:
    cfg = MODELS[model_key]
    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        timeout=API_TIMEOUT,
        max_retries=API_MAX_RETRIES,
    )


def _build_body(model_key: str, system_prompt: str, user_prompt: str, json_mode: bool = False) -> dict:
    """Build the chat completions request body for a given model."""
    cfg = MODELS[model_key]
    token_param = cfg.get("token_param", "max_tokens")
    suffix = cfg.get("prompt_suffix") or ""
    body = {
        "model":          cfg["name"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt + suffix},
        ],
        token_param: cfg["max_tokens"],
    }
    temperature = cfg.get("temperature")
    if temperature is not None:
        body["temperature"] = temperature
    if cfg.get("reasoning_effort"):
        body["reasoning_effort"] = cfg["reasoning_effort"]
    if cfg.get("reasoning") is not None:
        # OpenRouter-style reasoning block, e.g. {"enabled": False} or {"effort": "low"}
        body["extra_body"] = {**body.get("extra_body", {}), "reasoning": cfg["reasoning"]}
    if cfg.get("provider") is not None:
        # OpenRouter `provider` routing block, e.g. {"only": ["Chutes"]}
        body["extra_body"] = {**body.get("extra_body", {}), "provider": cfg["provider"]}
    if cfg.get("chat_template_kwargs") is not None:
        # vLLM-native template controls, e.g. {"enable_thinking": False} for Qwen3.6
        body["extra_body"] = {
            **body.get("extra_body", {}),
            "chat_template_kwargs": cfg["chat_template_kwargs"],
        }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    return body


# ── Standard (synchronous) API ─────────────────────────────────────────────────

def generate(model_key: str, system_prompt: str, user_prompt: str, json_mode: bool = False) -> dict:
    """
    Call the LLM synchronously and return a structured response.

    Returns
    -------
    {
        "content":                   str,
        "model":                     str,
        "prompt_tokens":             int,
        "completion_tokens":         int,
        "reasoning_tokens":          int,   # thought tokens (0 if model doesn't use them)
        "total_tokens":              int,
        "llm_response_time_seconds": float,
    }
    """
    client = _client(model_key)
    body   = _build_body(model_key, system_prompt, user_prompt, json_mode)

    t0 = time.perf_counter()
    response = client.chat.completions.create(**body)
    elapsed  = time.perf_counter() - t0

    details         = response.usage.completion_tokens_details
    reasoning_tokens = (getattr(details, "reasoning_tokens", None) or 0) if details else 0

    msg     = response.choices[0].message
    content = msg.content
    if not content:
        # Reasoning models sometimes return content=None when reasoning eats the
        # token budget. Fall back to the reasoning field so extract_code can try.
        content = getattr(msg, "reasoning", None) or ""

    return {
        "content":                   content.strip(),
        "content_was_empty":         not msg.content,
        "model":                     response.model,
        "prompt_tokens":             response.usage.prompt_tokens,
        "completion_tokens":         response.usage.completion_tokens,
        "reasoning_tokens":          reasoning_tokens,
        "total_tokens":              response.usage.total_tokens,
        "llm_response_time_seconds": round(elapsed, 3),
    }


# ── Batch API ──────────────────────────────────────────────────────────────────

def build_batch_request(
    custom_id: str,
    model_key: str,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
) -> dict:
    """Return a single batch JSONL request dict."""
    return {
        "custom_id": custom_id,
        "method":    "POST",
        "url":       "/v1/chat/completions",
        "body":      _build_body(model_key, system_prompt, user_prompt, json_mode),
    }


def submit_batch_job(model_key: str, requests: list[dict], description: str = "") -> str:
    """
    Upload a JSONL batch file and create the batch job.
    Returns the batch_id string.
    """
    client = _client(model_key)
    jsonl_bytes = "\n".join(json.dumps(r) for r in requests).encode()

    file_obj = client.files.create(
        file=("batch_requests.jsonl", jsonl_bytes, "application/jsonl"),
        purpose="batch",
    )
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": description} if description else {},
    )
    return batch.id


def poll_batch_job(model_key: str, batch_id: str):
    """Retrieve current batch status. Returns the batch object."""
    return _client(model_key).batches.retrieve(batch_id)


def download_batch_results(model_key: str, batch) -> list[dict]:
    """
    Download and parse completed batch output.
    Returns a list of response dicts (one per request, keyed by custom_id).
    """
    client  = _client(model_key)
    content = client.files.content(batch.output_file_id).content
    results = []
    for line in content.decode().strip().splitlines():
        if line.strip():
            results.append(json.loads(line))
    return results


def cancel_batch_job(model_key: str, batch_id: str):
    """Cancel a running batch job."""
    return _client(model_key).batches.cancel(batch_id)
