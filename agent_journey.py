import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END


# ============================================================
# ENVIRONMENT / LLM SETUP
# ============================================================

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL")
model = os.getenv("OPENROUTER_MODEL")

llm = ChatOpenAI(
    base_url=base_url,
    api_key=api_key,
    model=model,
    temperature=0.1,
)


# ============================================================
# SHARED STATE
# ============================================================

# All agents share the same basic state schema
# for simplicity in handoffs.

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ============================================================
# 1. SPECIALIST AGENT: RESEARCHER
# ============================================================

@tool
def product_lookup(product_name: str) -> float:
    """Fetches the current price of a product."""

    catalog = {
        "laptop": 1200.0,
        "mouse": 25.0,
        "keyboard": 75.0,
        "monitor": 300.0,
    }

    return catalog.get(
        product_name.lower().strip(),
        0.0
    )


# Bind the researcher tool to the LLM
research_llm = llm.bind_tools([product_lookup])


def res_node(state: AgentState):
    print(" --- [RESEARCH SPECIALIST] Thinking ---")

    sys = SystemMessage(
        content=(
            "You are a researcher. "
            "Get product prices. "
            "Do not do math."
        )
    )

    response = research_llm.invoke(
        [sys] + state["messages"]
    )

    return {
        "messages": [response]
    }


def res_action(state: AgentState):
    last = state["messages"][-1]

    results = []

    for tool_call in last.tool_calls:
        print(
            f" [Research Action]: {tool_call['name']}"
        )

        result = product_lookup.invoke(tool_call)

        results.append(result)

    return {
        "messages": results
    }


def res_router(state: AgentState) -> str:
    last_message = state["messages"][-1]

    if (
        hasattr(last_message, "tool_calls")
        and len(last_message.tool_calls) > 0
    ):
        return "action"

    return END


def build_researcher():
    graph = StateGraph(AgentState)

    graph.add_node("agent", res_node)
    graph.add_node("action", res_action)

    graph.add_edge(
        START,
        "agent"
    )

    graph.add_conditional_edges(
        "agent",
        res_router,
        {
            "action": "action",
            END: END,
        },
    )

    graph.add_edge(
        "action",
        "agent"
    )

    return graph.compile()


# ============================================================
# 2. SPECIALIST AGENT: CALCULATOR
# ============================================================

@tool
def calculator(
    a: float,
    b: float,
    operation: str
) -> float:
    """Performs basic arithmetic operations."""

    if operation == "add":
        return a + b

    elif operation == "multiply":
        return a * b

    return 0.0


# Bind calculator tool to LLM
calc_llm = llm.bind_tools([calculator])


def calc_node(state: AgentState):
    print(" --- [CALC SPECIALIST] Thinking ---")

    sys = SystemMessage(
        content=(
            "You are a calculator. "
            "Read prices from history and do math. "
            "Do not search for products."
        )
    )

    response = calc_llm.invoke(
        [sys] + state["messages"]
    )

    return {
        "messages": [response]
    }


def calc_action(state: AgentState):
    last = state["messages"][-1]

    results = []

    for tool_call in last.tool_calls:
        print(
            f" [Calculator Action]: {tool_call['name']}"
        )

        result = calculator.invoke(tool_call)

        results.append(result)

    return {
        "messages": results
    }


def calc_router(state: AgentState) -> str:
    last_message = state["messages"][-1]

    if (
        hasattr(last_message, "tool_calls")
        and len(last_message.tool_calls) > 0
    ):
        return "action"

    return END


def build_calculator():
    graph = StateGraph(AgentState)

    graph.add_node("agent", calc_node)
    graph.add_node("action", calc_action)

    graph.add_edge(
        START,
        "agent"
    )

    graph.add_conditional_edges(
        "agent",
        calc_router,
        {
            "action": "action",
            END: END,
        },
    )

    graph.add_edge(
        "action",
        "agent"
    )

    return graph.compile()


# ============================================================
# 3. ORCHESTRATOR
# ============================================================

def orchestrator_node(state: AgentState):
    print(
        "\n[ORCHESTRATOR] Reviewing entire state..."
    )

    sys = SystemMessage(
        content="""
You are the Supervisor of two autonomous specialist agents:

1. 'researcher' - securely finds product prices.
2. 'calculator' - accurately performs mathematics.

Analyze the conversation.

If you need prices, reply EXACTLY with:

ROUTE: researcher

If you have prices but need math, reply EXACTLY with:

ROUTE: calculator

If the goal is fully answered, reply EXACTLY with:

ROUTE: finish
"""
    )

    response = llm.invoke(
        [sys] + state["messages"]
    )

    return {
        "messages": [response]
    }


def orchestrator_router(state: AgentState) -> str:
    text = state["messages"][-1].content

    if "ROUTE: researcher" in text:
        print(
            ">> [ROUTER] Handing over completely "
            "to Research Specialist Sub-Graph"
        )

        return "researcher"

    elif "ROUTE: calculator" in text:
        print(
            ">> [ROUTER] Handing over completely "
            "to Calculator Specialist Sub-Graph"
        )

        return "calculator"

    print(
        ">> [ROUTER] Goal completely achieved."
    )

    return END


# ============================================================
# 4. BUILD HIERARCHICAL GRAPH
# ============================================================

def build_hierarchical_graph():

    # --------------------------------------------------------
    # Compile the specialist sub-graphs independently
    # --------------------------------------------------------

    research_app = build_researcher()
    calc_app = build_calculator()

    # --------------------------------------------------------
    # Create the main top-level graph
    # --------------------------------------------------------

    workflow = StateGraph(AgentState)

    # Add orchestrator
    workflow.add_node(
        "orchestrator",
        orchestrator_node
    )

    # Add compiled sub-graphs as nodes
    workflow.add_node(
        "researcher",
        research_app
    )

    workflow.add_node(
        "calculator",
        calc_app
    )

    # --------------------------------------------------------
    # Main graph routing
    # --------------------------------------------------------

    workflow.add_edge(
        START,
        "orchestrator"
    )

    workflow.add_conditional_edges(
        "orchestrator",
        orchestrator_router,
        {
            "researcher": "researcher",
            "calculator": "calculator",
            END: END,
        },
    )

    # After specialist finishes,
    # return control to orchestrator.

    workflow.add_edge(
        "researcher",
        "orchestrator"
    )

    workflow.add_edge(
        "calculator",
        "orchestrator"
    )

    return workflow.compile()


# ============================================================
# 5. EXECUTION
# ============================================================

def main():

    print(
        "Building Hierarchical Agent Graph "
        "(Orchestrator + Specialists)...\n"
    )

    app = build_hierarchical_graph()

    goal = HumanMessage(
        content=(
            "Find the total cost of "
            "1 Keyboard and 2 Mice (Mouse)."
        )
    )

    print(
        f"Goal: {goal.content}\n"
    )

    # Increase recursion_limit because
    # the workflow passes through multiple
    # graph hierarchies.

    final_state = app.invoke(
        {
            "messages": [goal]
        },
        {
            "recursion_limit": 25
        },
    )

    print("\n" + "=" * 60)
    print("🎉 FINAL HIERARCHICAL DELIVERABLE")

    print(
        final_state["messages"][-1].content
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()