import os
import json
import pytest
from unittest.mock import patch, MagicMock
from app.execution.executor import execute_project
from app.state.schemas import OrchestratorOutput, EntitySpec, APIContract


@pytest.fixture
def base_orchestrator_spec():
    return OrchestratorOutput(
        entity_spec=EntitySpec(entity_name="Test", fields={}),
        crud_operations=[],
        api_contract=APIContract(base_route="/test", operations=[]),
        execution_order="backend_first",
        file_locations={"backend_root": "backend/", "frontend_root": "frontend/"},
    )


@patch("app.execution.executor.run_cmd")
@patch("app.execution.executor.run_server_smoke_test")
def test_executor_skips_build_when_no_build_script(
    mock_smoke, mock_run_cmd, tmp_path, base_orchestrator_spec
):
    # Setup workspace
    workspace = tmp_path / "workspace"
    backend_dir = workspace / "backend"
    backend_dir.mkdir(parents=True)

    # Create package.json with no build script
    pkg_json = {"scripts": {"start": "node index.js"}}
    (backend_dir / "package.json").write_text(json.dumps(pkg_json))

    # Mock return values for success
    mock_run_cmd.return_value = {"success": True, "stdout": "", "stderr": ""}
    mock_smoke.return_value = {"success": True, "stdout": "", "stderr": ""}

    # Run execute
    result = execute_project(str(workspace), base_orchestrator_spec)

    # Verify build was NOT called
    build_calls = [c for c in mock_run_cmd.call_args_list if c[0][0] == "npm run build"]
    assert len(build_calls) == 0
    assert result["success"] is True


@patch("app.execution.executor.run_cmd")
@patch("app.execution.executor.run_server_smoke_test")
def test_executor_runs_build_when_build_script_exists(
    mock_smoke, mock_run_cmd, tmp_path, base_orchestrator_spec
):
    # Setup workspace
    workspace = tmp_path / "workspace"
    backend_dir = workspace / "backend"
    backend_dir.mkdir(parents=True)

    # Create package.json with a build script
    pkg_json = {"scripts": {"start": "node index.js", "build": "tsc"}}
    (backend_dir / "package.json").write_text(json.dumps(pkg_json))

    # Mock return values for success
    mock_run_cmd.return_value = {"success": True, "stdout": "", "stderr": ""}
    mock_smoke.return_value = {"success": True, "stdout": "", "stderr": ""}

    # Run execute
    result = execute_project(str(workspace), base_orchestrator_spec)

    # Verify build WAS called
    build_calls = [c for c in mock_run_cmd.call_args_list if c[0][0] == "npm run build"]
    assert len(build_calls) == 1
    assert "-backend" in build_calls[0][0][1] or build_calls[0][0][1].endswith(
        "backend"
    )
    assert result["success"] is True
