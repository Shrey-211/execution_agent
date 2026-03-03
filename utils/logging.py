import json
import os
from datetime import datetime


def save_log(log_file, conversation):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "messages": conversation,
    }

    logs = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            logs = json.load(f)

    logs.append(log_entry)

    with open(log_file, "w") as f:
        json.dump(logs, f, indent=2)