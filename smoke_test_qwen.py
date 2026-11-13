"""
smoke_test_qwen.py
==================
Three calls back-to-back to compare how much reasoning each approach cuts:

  A. Baseline                — current config, reasoning runs freely
  B. /no_think suffix        — Qwen3's native chat-template token; should = 0 reasoning
  C. reasoning.max_tokens=512 — OpenRouter cap; may or may not be honored

Picks a moderately hard sample so reasoning has reason to fire.
"""
import json
import traceback
from openai import OpenAI, APIStatusError
from config import MODELS
from prompts import get_prompt, SYSTEM_PROMPTS

MODEL_KEY = "qwen3_6_27b"
cfg = MODELS[MODEL_KEY]

# A non-trivial sample so reasoning is actually motivated
SAMPLE_PY = """n = int(input())
arr = list(map(int, input().split()))
count = 0
for i in range(n):
    for j in range(i+1, n):
        for k in range(j+1, n):
            if arr[i] + arr[j] + arr[k] == 0:
                count += 1
print(count)
"""

system_prompt = SYSTEM_PROMPTS["python"]
base_user_prompt = get_prompt("zero_shot", "python", SAMPLE_PY)

client = OpenAI(
    api_key=cfg["api_key"],
    base_url=cfg["base_url"],
    timeout=300,
    max_retries=0,
)

def call(label: str, user_prompt: str, extra_body: dict | None = None):
    print(f"\n=== {label} ===")
    try:
        resp = client.chat.completions.create(
            model=cfg["name"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=cfg["max_tokens"],
            temperature=cfg["temperature"],
            extra_body=extra_body or {},
        )
    except APIStatusError as exc:
        print(f"  !! HTTP {exc.status_code}: {exc.response.text[:300]}")
        return
    except Exception:
        print("  !! Error:")
        traceback.print_exc()
        return

    usage = resp.usage
    details = usage.completion_tokens_details
    reasoning_tok = (getattr(details, "reasoning_tokens", None) or 0) if details else 0
    msg = resp.choices[0].message
    content = msg.content or ""
    provider = getattr(resp, "provider", "?")
    print(f"  provider:           {provider}")
    print(f"  prompt_tokens:      {usage.prompt_tokens}")
    print(f"  completion_tokens:  {usage.completion_tokens}")
    print(f"  reasoning_tokens:   {reasoning_tok}")
    print(f"  visible chars:      {len(content)}")
    print(f"  finish_reason:      {resp.choices[0].finish_reason}")
    print(f"  --- first 200 chars of content ---")
    print(f"  {content[:200]!r}")


print(f"Model: {cfg['name']}  base_url: {cfg['base_url']}")
call("A. BASELINE (no overrides)", base_user_prompt)
call("B. /no_think suffix",        base_user_prompt + "\n\n/no_think")
call("C. reasoning.max_tokens=512", base_user_prompt,
     extra_body={"reasoning": {"max_tokens": 512}})
