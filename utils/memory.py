from abc import ABC, abstractmethod

import tiktoken


class BaseMemory(ABC):
    def __init__(self, system_prompt):
        self.system_prompt = {"role": "system", "content": system_prompt}
        self.conversation = []

    def add_message(self, role, content):
        self.conversation.append({"role": role, "content": content})

    def get_full_history(self):
        return [self.system_prompt] + self.conversation

    @abstractmethod
    def get_context(self):
        """Return the messages to send to the API."""
        pass


class SlidingWindowMemory(BaseMemory):
    """Keeps only the last N messages (user + assistant pairs)."""

    def __init__(self, system_prompt, max_messages=20):
        super().__init__(system_prompt)
        self.max_messages = max_messages

    def get_context(self):
        recent = self.conversation[-self.max_messages:]
        return [self.system_prompt] + recent


class TokenBasedMemory(BaseMemory):
    """Trims oldest messages to stay within a token budget."""

    def __init__(self, system_prompt, max_tokens=4000, model="gpt-4o-mini"):
        super().__init__(system_prompt)
        self.max_tokens = max_tokens
        self.encoder = tiktoken.encoding_for_model(model)

    def _count_tokens(self, message):
        return len(self.encoder.encode(message["content"])) + 4  # role overhead

    def get_context(self):
        budget = self.max_tokens - self._count_tokens(self.system_prompt)
        trimmed = []

        for msg in reversed(self.conversation):
            cost = self._count_tokens(msg)
            if budget - cost < 0:
                break
            trimmed.insert(0, msg)
            budget -= cost

        return [self.system_prompt] + trimmed


class SummaryMemory(BaseMemory):
    """Summarizes older messages once the conversation exceeds a threshold."""

    def __init__(self, system_prompt, client, threshold=10, keep_recent=6):
        super().__init__(system_prompt)
        self.client = client
        self.threshold = threshold
        self.keep_recent = keep_recent
        self.summary = None

    def _summarize(self, messages):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Summarize the following conversation in 2-3 concise sentences. "
                        "Capture key facts, user preferences, and any decisions made."
                    ),
                },
                *messages,
            ],
        )
        return response.choices[0].message.content

    def get_context(self):
        if len(self.conversation) > self.threshold:
            old = self.conversation[:-self.keep_recent]
            self.summary = self._summarize(old)
            self.conversation = self.conversation[-self.keep_recent:]

        context = [self.system_prompt]
        if self.summary:
            context.append({
                "role": "system",
                "content": f"Summary of earlier conversation:\n{self.summary}",
            })
        context.extend(self.conversation)
        return context


MEMORY_TYPES = {
    "1": ("Sliding Window", SlidingWindowMemory),
    "2": ("Token-Based", TokenBasedMemory),
    "3": ("Summary-Based", SummaryMemory),
}


def select_memory(system_prompt, client):
    print("\n--- Select Memory Type ---")
    for key, (name, _) in MEMORY_TYPES.items():
        print(f"  {key}. {name}")

    choice = input("\nEnter choice (1/2/3): ").strip()

    if choice == "1":
        return SlidingWindowMemory(system_prompt, max_messages=20)
    elif choice == "2":
        return TokenBasedMemory(system_prompt, max_tokens=4000)
    elif choice == "3":
        return SummaryMemory(system_prompt, client, threshold=10, keep_recent=6)
    else:
        print("Invalid choice, defaulting to Sliding Window.")
        return SlidingWindowMemory(system_prompt, max_messages=20)
