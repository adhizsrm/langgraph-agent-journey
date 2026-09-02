from langgraph.graph import StateGraph, START, END
from app.state.schemas import GraphState

from app.agents.orchestrator import orchestrator_node
from app.agents.backend_agent import backend_agent_node
from app.agents.frontend_agent import frontend_agent_node
from app.agents.repair_agent import project_repair_node

from app.graph.nodes import (
    validate_generated_project_node,
    create_temp_workspace_node,
    project_executor_node,
    promote_project_node,
    cleanup_failed_project_node,
)
from app.graph.routing import (
    route_execution_order,
    route_backend_agent,
    route_frontend_agent,
    route_validation,
    route_executor,
)


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("backend_agent", backend_agent_node)
    graph.add_node("frontend_agent", frontend_agent_node)
    graph.add_node("validate_generated_project", validate_generated_project_node)

    # Phase 18 New Nodes
    graph.add_node("create_temp_workspace", create_temp_workspace_node)
    graph.add_node("project_executor", project_executor_node)
    graph.add_node("project_repair", project_repair_node)
    graph.add_node("promote_project", promote_project_node)
    graph.add_node("cleanup_failed_project", cleanup_failed_project_node)

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges("orchestrator", route_execution_order)
    graph.add_conditional_edges("backend_agent", route_backend_agent)
    graph.add_conditional_edges("frontend_agent", route_frontend_agent)
    graph.add_conditional_edges("validate_generated_project", route_validation)
    graph.add_edge("create_temp_workspace", "project_executor")
    graph.add_conditional_edges("project_executor", route_executor)
    graph.add_edge("project_repair", "validate_generated_project")
    graph.add_edge("promote_project", END)
    graph.add_edge("cleanup_failed_project", END)

    return graph.compile()
