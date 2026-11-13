"""
prompts.py
==========
ALL prompt templates live here. Edit this file to change what the LLM sees.
No other file needs to change when you modify a prompt.

Sections:
  SYSTEM_PROMPTS          — system-level instructions per language
  ZERO_SHOT               — direct optimization request
  FEW_SHOT_EXAMPLES       — hand-crafted before/after pairs used in few-shot
  CHAIN_OF_THOUGHT        — step-by-step reasoning prompt
  INPUT_GENERATION_PROMPT — ask LLM to produce test inputs for a code snippet

Public API:
  get_prompt(technique, language, code)  → formatted user prompt string
  get_input_generation_prompt(language, code) → formatted prompt string
"""

# ── System Prompts ─────────────────────────────────────────────────────────────
SYSTEM_PROMPTS = {
    "python": (
        "You are an expert Python software engineer specializing in algorithmic optimization.\n"
        "Your goal is to rewrite code so it is faster, uses less memory, and is easier to maintain.\n"
        "Focus on:\n"
        "  1. Reducing time complexity (e.g. O(n²) → O(n) using hash sets, sorting, two pointers).\n"
        "  2. Reducing space complexity where possible without harming readability.\n"
        "  3. Improving code clarity: meaningful names, removing dead code, flattening nesting.\n\n"
        "Output rules:\n"
        "  - Return ONLY the optimized Python code — no markdown fences, no explanations.\n"
        "  - Preserve all original function/method signatures exactly.\n"
        "  - The code must be syntactically valid Python 3."
    ),
    "java": (
        "You are an expert Java software engineer specializing in algorithmic optimization.\n"
        "Your goal is to rewrite code so it is faster, uses less memory, and is easier to maintain.\n"
        "Focus on:\n"
        "  1. Reducing time complexity (e.g. nested loops → HashMap/HashSet, sorting-based approaches).\n"
        "  2. Reducing space complexity where possible without harming readability.\n"
        "  3. Improving code clarity: StringBuilder over concatenation, enhanced for-loops, streams.\n\n"
        "Output rules:\n"
        "  - Return ONLY the optimized Java code — no markdown fences, no explanations.\n"
        "  - Preserve all original method signatures exactly.\n"
        "  - The code must be syntactically valid Java."
    ),
}

# ── Few-Shot Examples ──────────────────────────────────────────────────────────
# Each entry: {"description": str, "original": str, "optimized": str}
# Add or remove examples here to change the few-shot context.

FEW_SHOT_EXAMPLES = {
    "python": [
        {
            "description": "O(n²) duplicate search → O(n) with hash set",
            "original": """\
def find_duplicates(arr):
    duplicates = []
    for i in range(len(arr)):
        for j in range(i + 1, len(arr)):
            if arr[i] == arr[j] and arr[i] not in duplicates:
                duplicates.append(arr[i])
    return duplicates""",
            "optimized": """\
def find_duplicates(arr):
    seen, duplicates = set(), set()
    for item in arr:
        if item in seen:
            duplicates.add(item)
        else:
            seen.add(item)
    return list(duplicates)""",
        },
        {
            "description": "O(n log n) count occurrences in sorted array → O(log n) with bisect",
            "original": """\
def count_occurrences(sorted_arr, target):
    count = 0
    for elem in sorted_arr:
        if elem == target:
            count += 1
    return count""",
            "optimized": """\
import bisect

def count_occurrences(sorted_arr, target):
    left  = bisect.bisect_left(sorted_arr, target)
    right = bisect.bisect_right(sorted_arr, target)
    return right - left""",
        },
        {
            "description": "Fibonacci O(2^n) recursion → O(n) iterative",
            "original": """\
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)""",
            "optimized": """\
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b""",
        },
    ],
    "java": [
        {
            "description": "O(n²) duplicate detection → O(n) with HashSet",
            "original": """\
public static boolean hasDuplicate(int[] arr) {
    for (int i = 0; i < arr.length; i++) {
        for (int j = i + 1; j < arr.length; j++) {
            if (arr[i] == arr[j]) return true;
        }
    }
    return false;
}""",
            "optimized": """\
public static boolean hasDuplicate(int[] arr) {
    Set<Integer> seen = new HashSet<>();
    for (int num : arr) {
        if (!seen.add(num)) return true;
    }
    return false;
}""",
        },
        {
            "description": "String concatenation in loop → StringBuilder",
            "original": """\
public static String joinWords(String[] words) {
    String result = "";
    for (String word : words) {
        if (!result.isEmpty()) result += " ";
        result += word;
    }
    return result;
}""",
            "optimized": """\
public static String joinWords(String[] words) {
    if (words == null || words.length == 0) return "";
    StringBuilder sb = new StringBuilder(words[0]);
    for (int i = 1; i < words.length; i++) {
        sb.append(' ').append(words[i]);
    }
    return sb.toString();
}""",
        },
        {
            "description": "O(n²) array intersection → O(n) with HashMap",
            "original": """\
public static List<Integer> intersection(int[] a, int[] b) {
    List<Integer> result = new ArrayList<>();
    for (int x : a) {
        for (int y : b) {
            if (x == y && !result.contains(x)) {
                result.add(x);
            }
        }
    }
    return result;
}""",
            "optimized": """\
public static List<Integer> intersection(int[] a, int[] b) {
    Set<Integer> setA = new HashSet<>();
    for (int x : a) setA.add(x);
    Set<Integer> seen = new HashSet<>();
    List<Integer> result = new ArrayList<>();
    for (int y : b) {
        if (setA.contains(y) && seen.add(y)) result.add(y);
    }
    return result;
}""",
        },
    ],
}

# ── Zero-Shot Templates ────────────────────────────────────────────────────────
# {code} is replaced with the actual source code at runtime.

_ZERO_SHOT = {
    "python": (
        "Optimize the following Python code to improve its time complexity, space complexity, "
        "and overall maintainability. Return only the optimized code.\n\n"
        "Code:\n{code}"
    ),
    "java": (
        "Optimize the following Java code to improve its time complexity, space complexity, "
        "and overall maintainability. Return only the optimized code.\n\n"
        "Code:\n{code}"
    ),
}

# ── Chain-of-Thought Templates ─────────────────────────────────────────────────
_CHAIN_OF_THOUGHT = {
    "python": (
        "Optimize the following Python code using step-by-step reasoning.\n\n"
        "Step 1 — Complexity analysis: State the current time and space complexity.\n"
        "Step 2 — Bottleneck identification: Pinpoint the slowest or most memory-hungry parts "
        "(nested loops, repeated lookups, string concatenation, etc.).\n"
        "Step 3 — Optimization plan: Decide which data structures or algorithms to apply "
        "(hash maps, sorting, two pointers, memoization, generators, etc.).\n"
        "Step 4 — Optimized code: Write the improved version.\n\n"
        "End your response with the final optimized code and nothing else after it.\n\n"
        "Code:\n{code}"
    ),
    "java": (
        "Optimize the following Java code using step-by-step reasoning.\n\n"
        "Step 1 — Complexity analysis: State the current time and space complexity.\n"
        "Step 2 — Bottleneck identification: Pinpoint the slowest or most memory-hungry parts "
        "(nested loops, repeated lookups, string concatenation, inefficient collections, etc.).\n"
        "Step 3 — Optimization plan: Decide which data structures or algorithms to apply "
        "(HashMap, HashSet, StringBuilder, sorting, streams, etc.).\n"
        "Step 4 — Optimized code: Write the improved version.\n\n"
        "End your response with the final optimized code and nothing else after it.\n\n"
        "Code:\n{code}"
    ),
}

# ── Input Generation Template ──────────────────────────────────────────────────
_INPUT_GENERATION = {
    "python": (
        "The following Python code reads input via input() or sys.stdin (competitive programming style).\n"
        "Generate exactly 5 stdin test inputs that together cover:\n"
        "  - An edge case (minimum values, boundary conditions)\n"
        "  - A small typical input\n"
        "  - A medium typical input\n"
        "  - A large stress-test input (large numbers or many lines)\n"
        "  - A worst-case scenario specific to this algorithm\n\n"
        "Return a JSON array with exactly 5 objects. Each object must have:\n"
        '  "input_description": short human-readable label (string)\n'
        '  "args": list of strings, where each string is one line of stdin input\n\n'
        'Example: if the program reads two lines, args would be ["5 3", "1 2 3 4 5"]\n\n'
        "IMPORTANT: Keep each string in 'args' SHORT — at most 50 space-separated values per line.\n"
        "For large-n stress tests, use n=1000 (not 100000) and write only 20-50 representative values.\n"
        "Never generate thousands of literal numbers — use a small but representative sample.\n\n"
        "Return valid JSON only — no markdown, no explanation.\n\n"
        "Code:\n{code}"
    ),
    "java": (
        "The following Java code reads input via Scanner or BufferedReader (competitive programming style).\n"
        "Generate exactly 5 stdin test inputs that together cover:\n"
        "  - An edge case (minimum values, boundary conditions)\n"
        "  - A small typical input\n"
        "  - A medium typical input\n"
        "  - A large stress-test input (large numbers or many lines)\n"
        "  - A worst-case scenario specific to this algorithm\n\n"
        "Return a JSON array with exactly 5 objects. Each object must have:\n"
        '  "input_description": short human-readable label (string)\n'
        '  "args": list of strings, where each string is one line of stdin input\n\n'
        'Example: if the program reads two lines, args would be ["5 3", "1 2 3 4 5"]\n\n'
        "IMPORTANT: Keep each string in 'args' SHORT — at most 50 space-separated values per line.\n"
        "For large-n stress tests, use n=1000 (not 100000) and write only 20-50 representative values.\n"
        "Never generate thousands of literal numbers — use a small but representative sample.\n\n"
        "Return valid JSON only — no markdown, no explanation.\n\n"
        "Code:\n{code}"
    ),
}


# ── Public helpers ─────────────────────────────────────────────────────────────

def _build_few_shot_prompt(language: str, code: str) -> str:
    examples = FEW_SHOT_EXAMPLES[language]
    parts = [
        f"Here are {len(examples)} examples of {language} code optimization:\n"
    ]
    for i, ex in enumerate(examples, 1):
        parts.append(f"--- Example {i}: {ex['description']} ---")
        parts.append(f"ORIGINAL:\n{ex['original']}")
        parts.append(f"OPTIMIZED:\n{ex['optimized']}\n")
    parts.append(
        f"Now apply the same optimization principles to the following {language} code. "
        "Return only the optimized code.\n\n"
        f"Code:\n{code}"
    )
    return "\n".join(parts)


def get_prompt(technique: str, language: str, code: str) -> str:
    """Return the formatted user prompt for a given technique and language."""
    if technique == "zero_shot":
        return _ZERO_SHOT[language].format(code=code)
    if technique == "few_shot":
        return _build_few_shot_prompt(language, code)
    if technique == "chain_of_thought":
        return _CHAIN_OF_THOUGHT[language].format(code=code)
    raise ValueError(f"Unknown prompting technique: {technique!r}")


def get_input_generation_prompt(language: str, code: str) -> str:
    """Return the formatted prompt for generating test inputs."""
    return _INPUT_GENERATION[language].format(code=code)
