
def estimate_tokens(text):
    """
    Roughly estimate tokens.
    A practical approximation is 1 token per 4 characters.
    """

    return max(1, len(text) // 4)


def trim_history_by_tokens(messages, max_tokens=3000):
    """
    Keep the newest conversation messages
    within the estimated token budget.
    """

    selected_messages = []
    total_tokens = 0

    for message in reversed(messages):

        message_tokens = estimate_tokens(
            message["content"]
        )

        if total_tokens + message_tokens > max_tokens:
            break

        selected_messages.append(message)
        total_tokens += message_tokens

    # Restore chronological order
    selected_messages.reverse()

    return selected_messages
