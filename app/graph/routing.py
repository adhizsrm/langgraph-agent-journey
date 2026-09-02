from app.state.schemas import GraphState


def route_execution_order(state: GraphState) -> str:
    order = state["orchestrator_spec"].execution_order
    if order == "backend_first":
        return "backend_agent"
    else:
        return "frontend_agent"


def route_backend_agent(state: GraphState) -> str:
    if state["orchestrator_spec"].execution_order == "frontend_first":
        return "validate_generated_project"
    return "frontend_agent"


def route_frontend_agent(state: GraphState) -> str:
    if state["orchestrator_spec"].execution_order == "backend_first":
        return "validate_generated_project"
    return "backend_agent"


def route_validation(state: GraphState) -> str:
    if state.get("validation_errors"):
        if state.get("repair_attempts", 0) >= 3:
            print("Max repair attempts reached (Validation Phase). Aborting.")
            return "cleanup_failed_project"
        return "project_repair"
    return "create_temp_workspace"


def route_executor(state: GraphState) -> str:
    exec_res = state.get("execution_result", {})
    if exec_res.get("success"):
        return "promote_project"
    else:
        if state.get("repair_attempts", 0) >= 3:
            print("Max repair attempts reached (Execution Phase). Aborting.")
            return "cleanup_failed_project"
        return "project_repair"
