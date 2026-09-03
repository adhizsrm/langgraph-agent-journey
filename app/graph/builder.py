from langgraph.graph import StateGraph, START, END
from app.state.schemas import GraphState

from app.agents.orchestrator import orchestrator_node
from app.agents.backend_agent import backend_agent_node
from app.agents.frontend_agent import frontend_agent_node
from app.agents.repair_agent import project_repair_node
from app.agents.enhancement_agent import enhancement_agent_node
from app.graph.safety_node import project_safety_node

from app.graph.nodes import (
    validate_generated_project_node,
    create_temp_workspace_node,
    project_executor_node,
    promote_project_node,
    cleanup_failed_project_node,
    grep_node,
    chunker_node,
)
from app.graph.routing import (
    route_execution_order,
    route_backend_agent,
    route_frontend_agent,
    route_validation,
    route_executor,
    route_initial_mode,
    route_safety,
)


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    # Core Generation Agents
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("backend_agent", backend_agent_node)
    graph.add_node("frontend_agent", frontend_agent_node)

    # Enhancement Mode Agents/Tools
    graph.add_node("grep_node", grep_node)
    graph.add_node("chunker_node", chunker_node)
    graph.add_node("enhancement_agent", enhancement_agent_node)
    graph.add_node("project_safety_node", project_safety_node)

    # Execution/Validation Nodes
    graph.add_node("validate_generated_project", validate_generated_project_node)
    graph.add_node("create_temp_workspace", create_temp_workspace_node)
    graph.add_node("project_executor", project_executor_node)
    graph.add_node("project_repair", project_repair_node)
    graph.add_node("promote_project", promote_project_node)
    graph.add_node("cleanup_failed_project", cleanup_failed_project_node)

    # ROUTING
    graph.add_conditional_edges(START, route_initial_mode)

    # Generation Path
    graph.add_conditional_edges("orchestrator", route_execution_order)
    graph.add_conditional_edges("backend_agent", route_backend_agent)
    graph.add_conditional_edges("frontend_agent", route_frontend_agent)

    # Enhancement Path
    graph.add_edge("grep_node", "chunker_node")
    graph.add_edge("chunker_node", "enhancement_agent")
    graph.add_edge("enhancement_agent", "project_safety_node")
    graph.add_conditional_edges("project_safety_node", route_safety)

    # Shared Execution Path
    graph.add_conditional_edges("validate_generated_project", route_validation)
    graph.add_edge("create_temp_workspace", "project_executor")
    graph.add_conditional_edges("project_executor", route_executor)
    graph.add_edge("project_repair", "validate_generated_project")

    # Endings
    graph.add_edge("cleanup_failed_project", END)

    return graph.compile()
