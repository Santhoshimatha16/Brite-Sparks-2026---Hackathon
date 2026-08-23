import json
import os
from datetime import datetime

class ExecutionTrace:
    def __init__(self, filepath="execution_trace.json"):
        self.filepath = filepath
        self.trace_log = []

    def log(self, event: str, details: dict = None):
        """Logs an event with a timestamp."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
        }
        if details:
            entry["details"] = details
        
        self.trace_log.append(entry)
        self._save()

    def _save(self):
        """Saves the trace log to the JSON file."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.trace_log, f, indent=2)
