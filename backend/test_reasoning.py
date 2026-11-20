
from backend.reasoning import analyze_question

questions = [
    "Calculate 25 multiplied by 4",
    "Write a Python program to add two numbers",
    "Explain machine learning",
    "Tell me about artificial intelligence",
    "Compare Python and Java",
    "What is the difference between AI and ML?",
    "Define artificial intelligence",
    "What is the meaning of machine learning?",
    "Help me",
    "What about this?",
    "Calculate 25 multiplied by 4"
    ]

for question in questions:

    result = analyze_question(question)

    print("\nQuestion:", question)
    print("Detected type:", result["type"])
    print("Instruction:", result["instruction"])
