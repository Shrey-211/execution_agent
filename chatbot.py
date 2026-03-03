import os
from dotenv import load_dotenv
from openai import OpenAI
from utils.prompt import get_system_prompt
from utils.logging import save_log
from utils.memory import select_memory

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

LOG_FILE = "chat_log.json"
SYSTEM_PROMPT = get_system_prompt()


def chat():
    memory = select_memory(SYSTEM_PROMPT, client)

    print(f"\n=== Terminal Chatbot ===")
    print("Type 'quit' or 'exit' to end the conversation.\n")

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        memory.add_message("user", user_input)

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=memory.get_context(),
            )
            reply = response.choices[0].message.content
            memory.add_message("assistant", reply)
            save_log(LOG_FILE, memory.get_full_history())
            print(f"\nAssistant: {reply}\n")
        except Exception as e:
            print(f"\nError: {e}\n")
            memory.conversation.pop()


if __name__ == "__main__":
    chat()
