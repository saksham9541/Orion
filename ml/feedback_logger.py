"""
Logs controller overrides to feed back into future ML training.
"""

import json
import os
from datetime import datetime

class FeedbackLogger:
    def __init__(self, log_file: str = "data/feedback_log.jsonl"):
        self.log_file = log_file
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        
    def log_plan_status(self, plan_id: str, action: str, user: str, reason: str = ""):
        """Log when a plan is APPROVED, REJECTED, or MODIFIED."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "PLAN_STATUS",
            "plan_id": plan_id,
            "action": action,
            "user": user,
            "reason": reason
        }
        self._append(entry)
        
    def log_task_override(self, plan_id: str, task_id: str, user: str, original_status: str, new_status: str, reason: str = ""):
        """Log when a human overrides a task's scheduling status or priority."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "TASK_OVERRIDE",
            "plan_id": plan_id,
            "task_id": task_id,
            "user": user,
            "original_status": original_status,
            "new_status": new_status,
            "reason": reason
        }
        self._append(entry)
        
    def _append(self, entry: dict):
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to write feedback log: {e}")

    def get_feedback_summary(self) -> dict:
        """Parse log and return summary stats for the dashboard."""
        summary = {
            "total_approvals": 0,
            "total_rejections": 0,
            "total_overrides": 0
        }
        if not os.path.exists(self.log_file):
            return summary
            
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip(): continue
                    data = json.loads(line)
                    if data["type"] == "PLAN_STATUS":
                        if data["action"] == "APPROVED": summary["total_approvals"] += 1
                        elif data["action"] == "REJECTED": summary["total_rejections"] += 1
                    elif data["type"] == "TASK_OVERRIDE":
                        summary["total_overrides"] += 1
        except Exception:
            pass
        return summary
