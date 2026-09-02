import os
from app.state.schemas import GraphState, GeneratedFiles, OrchestratorOutput
from app.validators.project_validator import validate_project
from app.workspace.manager import create_temp_workspace, cleanup_workspace
from app.execution.executor import execute_project
from app.workspace.promotion import promote_workspace_to_target


def validate_generated_project_node(state: GraphState) -> GraphState:
    print("Running Pre-Write Validator Node...")
    backend_files = state.get("backend_files")
    b_files = backend_files.files if backend_files else []

    frontend_files = state.get("frontend_files")
    f_files = frontend_files.files if frontend_files else []

    return validate_project(b_files, f_files)


def create_temp_workspace_node(state: GraphState) -> GraphState:
    print("Running Create Temp Workspace Node...")
    backend_files = state.get("backend_files", GeneratedFiles(files=[])).files
    frontend_files = state.get("frontend_files", GeneratedFiles(files=[])).files

    workspace_path, written_files, error = create_temp_workspace(
        backend_files, frontend_files
    )

    if error:
        return {"error": error}
    return {"workspace_path": workspace_path, "written_files": written_files}


def project_executor_node(state: GraphState) -> GraphState:
    print("Running Project Executor Node...")
    workspace_path = state.get("workspace_path")
    if not workspace_path:
        return {"error": "Missing workspace path"}

    result = execute_project(workspace_path, state.get("orchestrator_spec"))

    return {"execution_result": result}


def promote_project_node(state: GraphState) -> GraphState:
    print("Running Promote Project Node...")
    target_path = state["target_project_path"]
    workspace_path = state.get("workspace_path")

    return promote_workspace_to_target(workspace_path, target_path)


def cleanup_failed_project_node(state: GraphState) -> GraphState:
    print("Running Cleanup Node (Max Repairs Reached)...")
    workspace_path = state.get("workspace_path")
    cleanup_workspace(workspace_path)
    return {
        "error": "FINAL FAILURE: Max 3 repair attempts reached.",
        "workflow_status": "FAILED",
    }
