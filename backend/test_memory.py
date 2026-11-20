from backend.memory import (
    init_memory_table,
    extract_and_save_memories,
    get_all_memories
)

init_memory_table()

message = """
I am learning Python.
My long-term goal is to become an AI engineer.
I prefer practical examples while learning.
"""

count = extract_and_save_memories(message)

print("\nMemories saved:", count)

print("\nStored memories:")

for memory in get_all_memories():
    print(memory)