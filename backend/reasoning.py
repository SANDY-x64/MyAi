
def analyze_question(question):

    question = question.strip().lower()

    if not question:
        question_type = "empty"

    # 1. Vague questions
    elif question in [
        "help",
        "help me",
        "do it",
        "do this",
        "what about this",
        "which one",
        "tell me"
    ]:
        question_type = "vague"

    # 2. Mathematical
    elif any(word in question for word in [
        "calculate", "solve", "equation", "formula"
    ]):
        question_type = "mathematical"

    # 3. Comparison
    elif any(word in question for word in [
        "compare", "comparison", "difference between",
        "differentiate", "versus", "vs"
    ]):
        question_type = "comparison"

    # 4. Definition
    elif any(word in question for word in [
        "define", "definition of", "meaning of"
    ]):
        question_type = "definition"

    # 5. Programming
    elif any(word in question for word in [
        "code", "program", "python", "java", "error", "debug"
    ]):
        question_type = "programming"

    # 6. Explanation
    elif any(word in question for word in [
        "explain", "describe", "what is", "how does"
    ]):
        question_type = "explanation"

    else:
        question_type = "general"

    instructions = {

        "mathematical": (
            "Identify the given values, choose the correct formula, "
            "solve carefully, and verify the result."
        ),

        "comparison": (
            "Compare the topics using clear points, "
            "similarities, differences, and examples."
        ),

        "definition": (
            "Give a clear definition, simple explanation and example."
        ),

        "programming": (
            "Understand the requirements, examine the logic, "
            "check syntax and edge cases."
        ),

        "explanation": (
            "Introduce the concept, explain it step by step, "
            "and provide a practical example."
        ),

        "vague": (
            "Check conversation history for context. "
            "If still unclear, ask one specific clarification question."
        ),

        "general": (
            "Understand the question and provide an accurate answer."
        ),

        "empty": "Ask the user to provide a question."
    }

    return {
        "type": question_type,
        "instruction": instructions[question_type]
    }


# --------------------------------
# RESPONSE FORMATTING
# --------------------------------

def get_response_format(question_type):

    formats = {

        "mathematical": """
Structure:
1. Given values
2. Required formula
3. Step-by-step calculation
4. Final answer
""",

        "programming": """
Structure:
1. Problem explanation
2. Algorithm or approach
3. Python/code solution
4. Expected output
5. Short explanation
""",

        "comparison": """
Structure:
1. Brief introduction
2. Comparison table
3. Important differences
4. Short conclusion
""",

        "definition": """
Structure:
1. Definition
2. Simple explanation
3. Practical example
4. Applications (if useful)
""",

        "explanation": """
Structure:
1. Introduction
2. Step-by-step explanation
3. Practical example
4. Applications (if useful)
""",

        "vague": """
Check conversation history.
If the meaning is unclear, ask one specific question.
Do not guess.
""",

        "general": """
Give a direct and accurate answer.
Use headings and examples when useful.
Avoid unnecessary details.
""",

        "empty": """
Ask the user to provide a question.
"""
    }

    return formats.get(
        question_type,
        formats["general"]
    )
# --------------------------------
# RESPONSE QUALITY INSTRUCTIONS
# --------------------------------

def get_quality_instructions():

    return """
RESPONSE QUALITY RULES:

1. Avoid repeating the same information.
2. Do not repeat the question unnecessarily.
3. Keep simple answers concise.
4. Explain complex topics clearly.
5. Avoid unnecessary headings.
6. Use examples only when they add value.
7. Maintain consistency with previous answers.
8. Do not invent facts or sources.
9. Answer the user's actual question.
10. If information is uncertain, say so clearly.
"""

def detect_multiple_tasks(question):

    question = question.lower()

    task_indicators = [
        " and ",
        "also",
        "then",
        "compare",
        "explain",
        "give me",
        "list"
    ]

    detected = []

    for indicator in task_indicators:

        if indicator in question:
            detected.append(indicator.strip())

    return {
    "is_multiple": len(detected) >= 2,
    "task_count": len(detected),
    "indicators": detected
}