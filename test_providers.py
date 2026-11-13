"""
test_providers.py
=================
Probe each OpenRouter provider for qwen/qwen3.6-27b with the same /no_think
prompt and report which one actually delivers low completion_tokens (= no
hidden reasoning). Total cost ~$0.05 across all providers.

Reads its API key from OPENROUTER_API_KEY (config.py).
"""
import time
from openai import OpenAI, APIStatusError
from config import MODELS
from prompts import get_prompt, SYSTEM_PROMPTS

cfg = MODELS["qwen3_6_27b"]

# Same moderately-hard sample as smoke_test_qwen so reasoning has motive to fire
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

system_prompt   = SYSTEM_PROMPTS["python"]
base_user       = get_prompt("zero_shot", "python", SAMPLE_PY)
prompt_no_think = base_user + "\n\n/no_think"

PROVIDERS_TO_TEST = [
    "Alibaba",
    "Chutes",
    "DeepInfra",
    "Io Net",
    "WandB",
    "Morph",
    "SiliconFlow",
]

# Probe pairs: (label, user_prompt, extra_body_extras)
# Qwen3.6 dropped /think and /no_think (Qwen3 only). Per HF card, the real
# switch is chat_template_kwargs.enable_thinking=False.
PROBES = [
    ("baseline (thinking on)",       base_user, {}),
    ("enable_thinking=False (vLLM)", base_user, {"chat_template_kwargs": {"enable_thinking": False}}),
]

client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=300, max_retries=0)

total_cost = 0.0
print(f"{'provider':14s} {'probe':28s} {'prompt':>6s} {'compl':>6s} {'reason':>7s} {'chars':>6s} {'time':>7s} {'cost':>9s}  notes")
print("-" * 132)

for provider in PROVIDERS_TO_TEST:
    for probe_label, user_prompt, extras in PROBES:
        t0 = time.perf_counter()
        try:
            extra_body = {
                "provider": {"only": [provider], "allow_fallbacks": False},
                **extras,
            }
            resp = client.chat.completions.create(
                model=cfg["name"],
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                max_tokens=cfg["max_tokens"],
                temperature=cfg["temperature"],
                extra_body=extra_body,
            )
        except APIStatusError as exc:
            print(f"{provider:14s} {probe_label:28s} {'-':>6s} {'-':>6s} {'-':>7s} {'-':>6s} {'-':>7s} {'-':>9s}  HTTP {exc.status_code}: {exc.response.text[:60]}")
            continue
        except Exception as exc:
            print(f"{provider:14s} {probe_label:28s} {'-':>6s} {'-':>6s} {'-':>7s} {'-':>6s} {'-':>7s} {'-':>9s}  ERR: {str(exc)[:60]}")
            continue
        elapsed = time.perf_counter() - t0

        usage = resp.usage
        details = usage.completion_tokens_details
        reasoning_tok = (getattr(details, "reasoning_tokens", None) or 0) if details else 0
        msg = resp.choices[0].message
        content = msg.content or ""
        # OpenRouter adds `cost` (USD) to usage; OpenAI SDK exposes it as an extra.
        cost = getattr(usage, "cost", None)
        if cost is None:
            # fall back to model_dump in case the field name is different
            dumped = usage.model_dump() if hasattr(usage, "model_dump") else {}
            cost = dumped.get("cost") or 0.0
        total_cost += float(cost or 0)
        cost_str = f"${cost:.5f}" if cost else "    -    "
        notes = "✓ NO REASONING" if usage.completion_tokens < 500 else "reasoning fires"
        print(f"{provider:14s} {probe_label:28s} {usage.prompt_tokens:6d} {usage.completion_tokens:6d} {reasoning_tok:7d} {len(content):6d} {elapsed:6.1f}s {cost_str:>9s}  {notes}")
    print()  # blank line between providers

print(f"Total cost across probes: ${total_cost:.5f}")
print(f"Projected for 900-call run on the best provider: see compl column × 900")

print()
print("Interpretation:")
print("  - chars ~50-300 means the model returned only the optimized code (good)")
print("  - completion < 500 means no hidden reasoning (we want this)")
print("  - completion in thousands + low chars = reasoning hidden in completion_tokens (bad)")
