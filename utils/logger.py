import json
import os
from datetime import datetime, timezone

LOG_FILE = "data/logs.json"

def log_action(action, user, moderator, reason=None):
    os.makedirs("data", exist_ok=True)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "user": str(user),
        "moderator": str(moderator),
        "reason": reason
    }

    # Safely read existing logs
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            # File exists but is empty or invalid
            data = []
    else:
        data = []

    data.append(log_entry)

    with open(LOG_FILE, "w") as f:
        json.dump(data, f, indent=4)

    return log_entry