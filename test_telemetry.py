import os
import json
from app.telemetry.metrics import TelemetryTracker


def test_run_creation():
    tracker = TelemetryTracker()
    tracker.start_run("test_run", "create", "test goal", "mock_prov", "mock_model")
    assert tracker.metrics is not None
    assert tracker.metrics["run_id"] == "test_run"
    assert tracker.metrics["files_retrieved"] == 0


def test_llm_metrics_recording():
    tracker = TelemetryTracker()
    tracker.start_run("test_run", "create", "test goal", "mock_prov", "mock_model")
    tracker.record_llm_call("test", "mock", "model", 1.5, 100, 200, 10, 20, 30, True)

    assert tracker.metrics["llm_calls"] == 1
    assert tracker.metrics["total_input_tokens"] == 10
    assert tracker.metrics["total_output_tokens"] == 20
    assert tracker.metrics["total_tokens"] == 30
    assert tracker.metrics["llm_events"][0]["latency_ms"] == 1500.0


def test_missing_token_metadata():
    tracker = TelemetryTracker()
    tracker.start_run("test_run", "create", "test goal", "mock_prov", "mock_model")
    tracker.record_llm_call(
        "test", "mock", "model", 1.5, 100, 200, None, None, None, True
    )

    assert tracker.metrics["llm_calls"] == 1
    assert tracker.metrics["total_input_tokens"] == 0
    assert tracker.metrics["total_output_tokens"] == 0
    assert tracker.metrics["total_tokens"] == 0
    assert tracker.metrics["llm_events"][0]["input_tokens"] is None
    assert tracker.metrics["llm_events"][0]["output_tokens"] is None


def test_serialization(tmp_path):
    # Temporarily monkeypatch the save location for test
    tracker = TelemetryTracker()
    tracker.start_run("test_run", "create", "test goal", "mock_prov", "mock_model")

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        tracker.save()
        assert os.path.exists("telemetry/run_test_run.json")
        with open("telemetry/run_test_run.json", "r") as f:
            data = json.load(f)
            assert data["mode"] == "create"
    finally:
        os.chdir(old_cwd)


def test_telemetry_failure_does_not_affect_workflow():
    tracker = TelemetryTracker()
    # If starting run fails (e.g. invalid type throwing exception ideally caught)
    tracker.metrics = "corrupted string instead of dict"

    # This shouldn't throw error
    try:
        tracker.record_llm_call(
            "test", "mock", "model", 1.5, 100, 200, 10, 20, 30, True
        )
        tracker.capture_workflow_state({"pending_patches": [1, 2]}, "success")
        tracker.save()
        assert True
    except Exception:
        assert (
            False
        ), "Telemetry tracker threw an exception instead of catching it quietly"
