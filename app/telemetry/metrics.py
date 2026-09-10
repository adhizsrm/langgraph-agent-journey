import os
import json
import time
from typing import Optional, Dict, Any


class TelemetryTracker:
    def __init__(self):
        self.metrics = None
        self.enabled = True

    def start_run(self, run_id: str, mode: str, goal: str, provider: str, model: str):
        if not self.enabled:
            return
        try:
            self.metrics = {
                "run_id": run_id,
                "mode": mode,
                "goal": goal,
                "provider": provider,
                "model": model,
                "start_time": time.time(),
                "duration_ms": 0,
                "llm_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "files_retrieved": 0,
                "patches_attempted": 0,
                "patches_failed": 0,
                "validation_failures": 0,
                "repair_attempts": 0,
                "final_status": "in_progress",
                "llm_events": [],
            }
        except Exception:
            pass

    def record_llm_call(
        self,
        caller: str,
        provider: str,
        model: str,
        latency: float,
        input_chars: int,
        output_chars: int,
        input_tokens: Optional[int],
        output_tokens: Optional[int],
        total_tokens: Optional[int],
        parse_success: bool,
        parse_error: str = "",
    ):
        if not self.enabled or not self.metrics:
            return

        try:
            self.metrics["llm_calls"] += 1
            if input_tokens is not None:
                self.metrics["total_input_tokens"] += input_tokens
            if output_tokens is not None:
                self.metrics["total_output_tokens"] += output_tokens
            if total_tokens is not None:
                self.metrics["total_tokens"] += total_tokens

            self.metrics["llm_events"].append(
                {
                    "caller": caller,
                    "provider": provider,
                    "model": model,
                    "latency_ms": round(latency * 1000, 2),
                    "input_chars": input_chars,
                    "output_chars": output_chars,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "parse_success": parse_success,
                    "parse_error": parse_error,
                }
            )
        except Exception:
            pass

    def capture_workflow_state(self, final_state: Dict[str, Any], status: str):
        if not self.enabled or not self.metrics:
            return
        try:
            self.metrics["final_status"] = status
            self.metrics["duration_ms"] = round(
                (time.time() - self.metrics["start_time"]) * 1000, 2
            )

            files_to_read = final_state.get("enhancement_files_to_read", [])
            self.metrics["files_retrieved"] = (
                len(files_to_read)
                if isinstance(files_to_read, list)
                else (1 if files_to_read else 0)
            )

            patches = final_state.get("pending_patches", [])
            self.metrics["patches_attempted"] = (
                len(patches) if isinstance(patches, list) else 0
            )

            safety_errors = final_state.get("safety_errors", [])
            self.metrics["patches_failed"] = (
                len(safety_errors) if isinstance(safety_errors, list) else 0
            )

            validation = final_state.get("validation_errors", [])
            self.metrics["validation_failures"] = (
                len(validation) if isinstance(validation, list) else 0
            )

            self.metrics["repair_attempts"] = final_state.get("repair_attempts", 0)
        except Exception:
            pass

    def save(self):
        if not self.enabled or not self.metrics:
            return
        try:
            os.makedirs("telemetry", exist_ok=True)
            run_id = self.metrics.get("run_id", "unknown_run")
            filepath = os.path.join("telemetry", f"run_{run_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self.metrics, f, indent=2)
        except Exception:
            pass


telemetry_tracker = TelemetryTracker()
