import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")

TOOL_REGISTRY = {}


def tool(name, description):
    """Decorator to register a function as a tool the agent can use."""
    def decorator(func):
        TOOL_REGISTRY[name] = {
            "function": func,
            "description": description,
        }
        return func
    return decorator


def _load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return []


def _save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


# ─── Personal Execution Tools ─────────────────────────────────────


@tool("get_time", "Returns the current date and time.")
def get_time():
    return datetime.now().strftime("%A, %B %d, %Y — %I:%M %p")


@tool("add_task", "Adds a task to your todo list. Input: task description.")
def add_task(description):
    tasks = _load_json(TASKS_FILE)
    task = {
        "id": len(tasks) + 1,
        "task": description,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
    }
    tasks.append(task)
    _save_json(TASKS_FILE, tasks)
    return f"Task #{task['id']} added: '{description}'"


@tool("list_tasks", "Lists all tasks. Input: 'all', 'pending', or 'done'.")
def list_tasks(filter_status="all"):
    tasks = _load_json(TASKS_FILE)
    if not tasks:
        return "No tasks found."

    if filter_status in ("pending", "done"):
        tasks = [t for t in tasks if t["status"] == filter_status]

    if not tasks:
        return f"No {filter_status} tasks."

    lines = []
    for t in tasks:
        marker = "x" if t["status"] == "done" else " "
        lines.append(f"  [{marker}] #{t['id']} — {t['task']}")
    return "\n".join(lines)


@tool("complete_task", "Marks a task as done. Input: task ID number.")
def complete_task(task_id):
    tasks = _load_json(TASKS_FILE)
    for t in tasks:
        if str(t["id"]) == str(task_id):
            t["status"] = "done"
            t["completed_at"] = datetime.now().isoformat()
            _save_json(TASKS_FILE, tasks)
            return f"Task #{task_id} marked as done: '{t['task']}'"
    return f"Task #{task_id} not found."


@tool("create_note", "Saves a note. Input: note content.")
def create_note(content):
    notes = _load_json(NOTES_FILE)
    note = {
        "id": len(notes) + 1,
        "content": content,
        "created_at": datetime.now().isoformat(),
    }
    notes.append(note)
    _save_json(NOTES_FILE, notes)
    return f"Note #{note['id']} saved."


@tool("read_notes", "Reads all saved notes. Input: not required.")
def read_notes(_=None):
    notes = _load_json(NOTES_FILE)
    if not notes:
        return "No notes found."

    lines = []
    for n in notes:
        lines.append(f"  Note #{n['id']} ({n['created_at'][:10]}): {n['content']}")
    return "\n".join(lines)


@tool("set_reminder", "Sets a reminder. Input: 'message | time' e.g. 'Call mom | 5:00 PM'.")
def set_reminder(raw_input):
    parts = raw_input.split("|")
    message = parts[0].strip()
    time_str = parts[1].strip() if len(parts) > 1 else "unspecified"

    reminders = _load_json(REMINDERS_FILE)
    reminder = {
        "id": len(reminders) + 1,
        "message": message,
        "remind_at": time_str,
        "created_at": datetime.now().isoformat(),
    }
    reminders.append(reminder)
    _save_json(REMINDERS_FILE, reminders)
    return f"Reminder #{reminder['id']} set: '{message}' at {time_str}"


@tool("list_reminders", "Lists all reminders. Input: not required.")
def list_reminders(_=None):
    reminders = _load_json(REMINDERS_FILE)
    if not reminders:
        return "No reminders set."

    lines = []
    for r in reminders:
        lines.append(f"  #{r['id']} — {r['message']} (at {r['remind_at']})")
    return "\n".join(lines)


@tool("send_email", "Sends an email (simulated). Input: 'to | subject | body'.")
def send_email(raw_input):
    parts = raw_input.split("|")
    if len(parts) < 3:
        return "Error: Format must be 'to | subject | body'."
    to = parts[0].strip()
    subject = parts[1].strip()
    body = parts[2].strip()
    return f"Email sent to {to}.\n  Subject: {subject}\n  Body: {body}"


@tool("ask_user", "Ask the user a question to gather info, clarify preferences, or confirm a plan. Input: your question.")
def ask_user(question):
    print(f"\n  Agent asks: {question}")
    answer = input("  Your answer: ").strip()
    return answer if answer else "User gave no response."


@tool("verify", "Review everything created so far (tasks, notes, reminders). Input: not required.")
def verify(_=None):
    sections = []

    tasks = _load_json(TASKS_FILE)
    if tasks:
        lines = []
        for t in tasks:
            marker = "x" if t["status"] == "done" else " "
            lines.append(f"  [{marker}] #{t['id']} — {t['task']}")
        sections.append("TASKS:\n" + "\n".join(lines))
    else:
        sections.append("TASKS: None")

    notes = _load_json(NOTES_FILE)
    if notes:
        lines = [f"  #{n['id']}: {n['content']}" for n in notes]
        sections.append("NOTES:\n" + "\n".join(lines))
    else:
        sections.append("NOTES: None")

    reminders = _load_json(REMINDERS_FILE)
    if reminders:
        lines = [f"  #{r['id']}: {r['message']} (at {r['remind_at']})" for r in reminders]
        sections.append("REMINDERS:\n" + "\n".join(lines))
    else:
        sections.append("REMINDERS: None")

    return "\n\n".join(sections)


@tool("done", "Call this when the goal is fully achieved. Input: final summary of what was done.")
def done(answer):
    return answer


# ─── Tool Execution ───────────────────────────────────────────────


def execute_tool(tool_name, tool_input):
    if tool_name not in TOOL_REGISTRY:
        return f"Error: Unknown tool '{tool_name}'. Available: {list(TOOL_REGISTRY.keys())}"

    func = TOOL_REGISTRY[tool_name]["function"]
    try:
        if tool_input:
            return func(tool_input)
        return func()
    except Exception as e:
        return f"Error executing '{tool_name}': {e}"


def get_tools_description():
    lines = []
    for name, info in TOOL_REGISTRY.items():
        lines.append(f"- {name}: {info['description']}")
    return "\n".join(lines)
