"""
MyAI Advanced Reasoning and Question Analysis Engine
Provides intelligent classification, task decomposition, format guidance, and quality evaluation.
"""

import re


PROGRAMMING_KEYWORDS = [
    "code", "program", "script", "function", "class", "algorithm",
    "debug", "error", "traceback", "exception", "compile", "syntax",
    "refactor", "optimize", "api", "backend", "frontend", "database",
    "sql", "query", "regex", "json", "git"
]

LANGUAGE_PATTERNS = {
    "python": [r"\bpython\b", r"\bpy\b", r"\bpip\b", r"\bdef\b", r"\bimport\b", r"\bdict\b"],
    "javascript": [r"\bjavascript\b", r"\bjs\b", r"\bnode\b", r"\btypescript\b", r"\bts\b", r"\bconst\b", r"\blet\b"],
    "c": [r"\bc\s+code\b", r"\bc\s+program\b", r"\bpointer\b", r"\bmalloc\b", r"\b#include\s*<stdio\.h>"],
    "cpp": [r"\bc\+\+\b", r"\bcpp\b", r"\bstd::", r"\bvector\b", r"\btemplate\b"],
    "java": [r"\bjava\b", r"\bpublic\s+class\b", r"\bjvm\b", r"\bspring\b", r"\bmaven\b"],
    "rust": [r"\brust\b", r"\bcargo\b", r"\bfn\s+main\b"],
    "go": [r"\bgolang\b", r"\bgo\s+code\b", r"\bfunc\b"],
    "sql": [r"\bsql\b", r"\bselect\s+.+from\b", r"\bjoin\b", r"\binsert\s+into\b", r"\bcreate\s+table\b"]
}

AGENT_INTENT_PATTERNS = {
    "search": [r"\bsearch\s+(the\s+)?web\b", r"\blatest\s+news\b", r"\blook\s*up\b", r"\bcurrent\s+weather\b", r"\btoday's\b"],
    "file_write": [r"\bsave\s+to\s+file\b", r"\bwrite\s+a\s+file\b", r"\bcreate\s+a\s+file\b", r"\bexport\s+to\b"],
    "file_read": [r"\bread\s+(the\s+)?file\b", r"\bopen\s+(the\s+)?file\b", r"\binspect\s+file\b"],
    "code_run": [r"\brun\s+(the\s+)?code\b", r"\bexecute\s+(the\s+)?script\b", r"\btest\s+this\s+code\b"]
}


def detect_languages(text: str) -> list[str]:
    """Detect mentioned or implied programming languages."""
    lower_text = text.lower()
    matched = []
    for lang, patterns in LANGUAGE_PATTERNS.items():
        if any(re.search(pat, lower_text) for pat in patterns):
            matched.append(lang)
    return matched


def detect_agent_intent(question: str) -> dict:
    """Detect if the user is asking the assistant to take an external action / tool step."""
    lower_q = question.lower()
    intents = []
    for intent, patterns in AGENT_INTENT_PATTERNS.items():
        if any(re.search(pat, lower_q) for pat in patterns):
            intents.append(intent)
    return {
        "requires_tool": len(intents) > 0,
        "intents": intents
    }


def analyze_question(question: str) -> dict:
    """
    Intelligently analyzes the user's question, classifying its primary domain,
    complexity, detected languages, and delivering tailored instructions.
    Full backward compatibility with legacy types.
    """
    cleaned = question.strip().lower()

    if not cleaned:
        question_type = "empty"
    elif cleaned in [
        "help", "help me", "do it", "do this", "what about this",
        "which one", "tell me", "start"
    ]:
        question_type = "vague"
    elif any(word in cleaned for word in ["calculate", "solve", "equation", "formula", "derivative", "integral", "matrix"]):
        question_type = "mathematical"
    elif any(phrase in cleaned for phrase in ["compare", "comparison", "difference between", "differentiate", "versus", "vs", "pros and cons"]):
        question_type = "comparison"
    elif any(phrase in cleaned for phrase in ["define", "definition of", "meaning of", "what does", "stand for"]):
        question_type = "definition"
    elif any(word in cleaned for word in PROGRAMMING_KEYWORDS) or any(detect_languages(cleaned)):
        question_type = "programming"
    elif any(phrase in cleaned for phrase in ["explain", "describe", "what is", "how does", "why does", "walk me through"]):
        question_type = "explanation"
    elif any(phrase in cleaned for phrase in ["summarize", "summary", "tl;dr", "key takeaways"]):
        question_type = "summarization"
    else:
        question_type = "general"

    instructions = {
        "mathematical": (
            "Identify the given values and unknown variables, choose the correct formula, "
            "show calculation steps with clear mathematical notation, and double-check numerical accuracy."
        ),
        "comparison": (
            "Compare the subjects methodically. Use a comparison table where appropriate, "
            "cover key dimensions (architecture, performance, use cases), and summarize trade-offs."
        ),
        "definition": (
            "Provide a precise, unambiguous definition followed by intuitive explanation, "
            "practical examples, and common misconceptions."
        ),
        "programming": (
            "Analyze specifications, choose the most idiomatic approach, provide clean, "
            "runnable code with error handling, and explain design decisions and complexity."
        ),
        "explanation": (
            "Introduce the concept clearly, unpack the underlying mechanism step by step, "
            "use a relatable analogy, and provide real-world applications."
        ),
        "summarization": (
            "Condense the information to core insights, organized with concise bullet points, "
            "highlighting key outcomes and actionable takeaways."
        ),
        "vague": (
            "Check conversation history for context. If the request remains ambiguous, "
            "politely ask one clarifying question offering likely interpretations."
        ),
        "general": (
            "Understand the question thoroughly and deliver a direct, accurate, well-structured answer."
        ),
        "empty": "Prompt the user to ask a question or state a task."
    }

    detected_langs = detect_languages(cleaned)
    agent_intent = detect_agent_intent(cleaned)
    multiple_tasks = detect_multiple_tasks(question)

    return {
        "type": question_type,
        "instruction": instructions.get(question_type, instructions["general"]),
        "detected_languages": detected_langs,
        "is_code": question_type == "programming" or bool(detected_langs),
        "agent_intent": agent_intent,
        "is_multiple_task": multiple_tasks["is_multiple"]
    }


def get_response_format(question_type: str) -> str:
    """Returns recommended response structure based on question type."""
    formats = {
        "mathematical": """
Structure:
1. Problem Summary & Given Values
2. Formula / Method
3. Step-by-Step Calculation
4. Final Verified Result
""",
        "programming": """
Structure:
1. Problem Analysis & Approach
2. Production-Ready Code (with type hints & comments)
3. Explanation of Key Components
4. Edge Cases & Complexity (Time/Space)
""",
        "comparison": """
Structure:
1. Overview of Both Subjects
2. Comparison Table (Key Criteria)
3. Deep-Dive Differences & Similarities
4. Recommendation / Decision Guide
""",
        "definition": """
Structure:
1. Concise Definition
2. In-Depth Explanation & Analogy
3. Practical Real-World Example
4. Related Concepts
""",
        "explanation": """
Structure:
1. Core Concept Overview
2. Step-by-Step Mechanism / Breakdown
3. Practical Example or Analogy
4. Key Takeaways
""",
        "summarization": """
Structure:
1. Executive Summary
2. Core Highlights (Bullet Points)
3. Actionable Takeaways
""",
        "vague": """
Check recent conversation history. If intent cannot be established, ask one specific question to clarify.
""",
        "general": """
Direct, accurate answer. Use clear markdown headers and lists for readability. Avoid unnecessary fluff.
""",
        "empty": """
Ask the user what they would like help with today.
"""
    }
    return formats.get(question_type, formats["general"]).strip()


def get_quality_instructions() -> str:
    """Return strict output quality guidelines."""
    return """
RESPONSE QUALITY & INTEGRITY RULES:
1. Answer the specific question directly before expanding into background details.
2. Avoid unnecessary conversational filler, self-narration, or repetitive apologies.
3. Keep code blocks fully runnable without placeholders unless explicitly requested.
4. If facts are uncertain or unverified, state the uncertainty explicitly.
5. Align strictly with stored user preferences and long-term memory.
6. Use markdown formatting: bolding for key terms, code fences for code, tables for comparisons.
"""


def detect_multiple_tasks(question: str) -> dict:
    """Detect if a user input contains multiple independent instructions or questions."""
    q_lower = question.lower()
    split_indicators = [
        " and also ", " additionally ", " then ", " furthermore ",
        " as well as ", " first ", " second ", " finally "
    ]
    detected = [ind.strip() for ind in split_indicators if ind in q_lower]

    # Also detect multiple question marks or numbered lists
    question_mark_count = question.count("?")
    has_numbered_list = bool(re.search(r"\b1[\.\)]\s+.+\b2[\.\)]\s+", question))

    is_multiple = len(detected) >= 1 or question_mark_count > 1 or has_numbered_list

    return {
        "is_multiple": is_multiple,
        "task_count": max(len(detected) + 1, question_mark_count, 2 if has_numbered_list else 1),
        "indicators": detected
    }


def evaluate_response_quality(query: str, response: str) -> dict:
    """
    Lightweight heuristic evaluator to verify response quality and flag issues
    such as emptiness, repetition, or unformatted code.
    """
    issues = []
    resp_clean = response.strip()

    if not resp_clean:
        return {"passed": False, "score": 0.0, "issues": ["Response is empty"]}

    if len(resp_clean) < 10 and len(query.split()) > 4:
        issues.append("Response may be incomplete or excessively short")

    # Check for unformatted code blocks if code is detected
    if any(k in query.lower() for k in ["python", "function", "write code"]) and "```" not in response:
        issues.append("Code response lacks markdown code fencing")

    # Check for hallucinated system prefixes
    if response.startswith("Assistant:") or response.startswith("AI:"):
        issues.append("Response contains unwanted role prefix")

    score = max(0.0, 1.0 - (len(issues) * 0.3))
    return {
        "passed": len(issues) == 0,
        "score": round(score, 2),
        "issues": issues
    }
