"""
config.py
=========
Central configuration for the code optimization research experiment.
Change model names, API endpoints, sample counts, and paths here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ───────────────────────────────────────────────────────────────────
OPENAI_API_KEY            = os.getenv("OPENAI_API_KEY", "")
TOGETHER_API_KEY          = os.getenv("TOGETHER_API_KEY", "")
OPENROUTER_API_KEY        = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_HAIKU_API_KEY    = os.getenv("OPENROUTER_HAIKU_API_KEY", "")

# ── Model Definitions (OpenAI-compatible interface for both) ───────────────────
MODELS = {
    "gpt4o": {
        "name":        "gpt-4o",
        "api_key":     OPENAI_API_KEY,
        "base_url":    "https://api.openai.com/v1",
        "max_tokens":  2048,
        "temperature": 0.2,
    },
    "gpt4o_mini": {
        "name":        "gpt-4o-mini",
        "api_key":     OPENAI_API_KEY,
        "base_url":    "https://api.openai.com/v1",
        "max_tokens":  2048,
        "temperature": 0.0,
    },
    "qwen": {
        "name":        "Qwen/Qwen2.5-Coder-7B-Instruct",
        "api_key":     TOGETHER_API_KEY,
        "base_url":    "https://api.together.xyz/v1",
        "max_tokens":  2048,
        "temperature": 0.2,
    },
    "gpt5_4_mini": {
        "name":             "gpt-5.4-mini",
        "api_key":          OPENAI_API_KEY,
        "base_url":         "https://api.openai.com/v1",
        "max_tokens":       16384,
        "token_param":      "max_completion_tokens",
        "reasoning_effort": "medium",
    },
    "qwen3_6_27b": {
        "name":        "qwen/qwen3.6-27b",
        "api_key":     OPENROUTER_API_KEY,
        "base_url":    "https://openrouter.ai/api/v1",
        "max_tokens":  16384,
        "temperature": 0.2,
        # Pinned to Chutes — fastest + cheapest in the 2026-06-30 provider probe.
        "provider": {"only": ["Chutes"], "allow_fallbacks": False},
        # Qwen3.6 dropped the /think and /no_think soft switches (those were Qwen3
        # only). Per the model's HF card, the correct way to disable thinking is
        # via the vLLM chat template kwarg. Most OpenRouter providers (Chutes
        # included) are vLLM-based so this is honored at tokenization time.
        "chat_template_kwargs": {"enable_thinking": False},
    },
    "claude_haiku_4_5": {
        "name":        "anthropic/claude-haiku-4.5",
        "api_key":     OPENROUTER_HAIKU_API_KEY,
        "base_url":    "https://openrouter.ai/api/v1",
        "max_tokens":  16384,
        "temperature": 0.2,
        # Non-reasoning by default — extended thinking is a distinct opt-in flag
        # in Anthropic's API, so no kill-switch is needed here. Selected as the
        # 4th study arm after smoke-testing 4 candidates (haiku, llama-3.3-70b,
        # gemini-2.5-flash-lite, deepseek-chat); all 4 emitted 0 reasoning tokens
        # and code-shaped output, Haiku was fastest and most concise.
    },
}

# ── Experiment Settings ────────────────────────────────────────────────────────
LANGUAGES            = ["python", "java"]
SAMPLES_PER_LANGUAGE = 100
PROMPTING_TECHNIQUES = ["zero_shot", "few_shot", "chain_of_thought"]
RANDOM_SEED          = 42

# How many times to run each code sample when measuring dynamic metrics
DYNAMIC_METRIC_ITERATIONS = 5

# ── Dataset ────────────────────────────────────────────────────────────────────
# Local JSONL files — see dataset.py for file paths
DATASET_NAME = "codeparrot/codecomplex (local)"

# ── Paths ──────────────────────────────────────────────────────────────────────
RESULTS_DIR         = "results"
RAW_RESULTS_DIR     = "results/raw"
SUMMARY_RESULTS_DIR = "results/summary"
SAMPLES_DIR         = "data/samples"
PREPROCESSED_FILE   = "data/preprocessed_samples.json"
