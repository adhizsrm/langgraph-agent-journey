import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL")
model = os.getenv("OPENROUTER_MODEL")

llm = ChatOpenAI(base_url=base_url, api_key=api_key, model=model, temperature=0.1)


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ==========================================
# DEFINING THE TOOLS
# ==========================================
@tool
def product_lookup(product_name: str) -> float:
    """Fetches the current price of a product."""
    catalog = {"laptop": 1200.0, "mouse": 25.0, "keyboard": 75.0}
    return catalog.get(product_name.lower().strip(), 0.0)


@tool
def calculator(a: float, b: float, operation: str) -> float:
    """Performs basic arithmetic operations."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    return 0.0


# 1. Bind tools exclusively for Agent A (Researcher)
research_tools = [product_lookup]
research_llm = llm.bind_tools(research_tools)
research_tools_map = {t.name: t for t in research_tools}

# 2. Bind tools exclusively for Agent B (Calculator)
calc_tools = [calculator]
calc_llm = llm.bind_tools(calc_tools)
calc_tools_map = {t.name: t for t in calc_tools}


# ==========================================
# AGENT A (RESEARCHER) NODES
# ==========================================
def research_node(state: AgentState):
    print("--- [AGENT A: RESEARCHER] Thinking ---")
    # Dynamically inject Agent A's personality so it doesn't get confused by Agent B later
    sys_msg = SystemMessage(
        content="You are a researcher. Use product_lookup to find prices. Once you have all prices, just list them and finish your thoughts."
    )
    response = research_llm.invoke([sys_msg] + state["messages"])
    return {"messages": [response]}


def research_action_node(state: AgentState):
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        print(f"   [RESEARCHER Action]: {tool_call['name']}({tool_call['args']})")
        tool = research_tools_map.get(tool_call["name"])
        if tool:
            results.append(tool.invoke(tool_call))
    return {"messages": results}


def research_router(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "research_action"

    # MAGIC: Instead of routing to END, Agent A routes to Agent B!
    print(
        ">> [HANDOFF] Researcher is done fetching data. Passing control to Calculator."
    )
    return "calc_node"


# ==========================================
# AGENT B (CALCULATOR) NODES
# ==========================================
def calc_node(state: AgentState):
    print("--- [AGENT B: CALCULATOR] Thinking ---")
    # Dynamically inject Agent B's personality
    sys_msg = SystemMessage(
        content="You are a calculator. Read the prices retrieved earlier in the conversation. Use the calculator tool to compute the exact total cost. Provide the final answer."
    )
    response = calc_llm.invoke([sys_msg] + state["messages"])
    return {"messages": [response]}


def calc_action_node(state: AgentState):
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        print(f"   [CALCULATOR Action]: {tool_call['name']}({tool_call['args']})")
        tool = calc_tools_map.get(tool_call["name"])
        if tool:
            results.append(tool.invoke(tool_call))
    return {"messages": results}


def calc_router(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "calc_action"

    print(">> [FINISHED] Calculator is done.")
    return END


# ==========================================
# UNIFIED PIPELINE BUILDER
# ==========================================
def build_pipeline():
    workflow = StateGraph(AgentState)

    workflow.add_node("research_node", research_node)
    workflow.add_node("research_action", research_action_node)

    workflow.add_node("calc_node", calc_node)
    workflow.add_node("calc_action", calc_action_node)

    # Sequence: START -> Agent A Loop -> Handoff -> Agent B Loop -> END

    # Agent A loop
    workflow.add_edge(START, "research_node")
    workflow.add_conditional_edges(
        "research_node",
        research_router,
        {"research_action": "research_action", "calc_node": "calc_node"},
    )
    workflow.add_edge("research_action", "research_node")

    # Agent B loop
    workflow.add_conditional_edges(
        "calc_node", calc_router, {"calc_action": "calc_action", END: END}
    )
    workflow.add_edge("calc_action", "calc_node")

    return workflow.compile()


def main():
    print("Building Agent A -> Agent B Pipeline...\n")
    app = build_pipeline()

    user_goal = HumanMessage(
        content="Goal: Calculate the total cost of 1 Laptop and 2 Keyboards."
    )
    print(f"Goal: {user_goal.content}\n")

    final_state = app.invoke({"messages": [user_goal]})

    print("\n--- FINAL DELIVERABLE ---")
    print(final_state["messages"][-1].content)


if __name__ == "__main__":
    main()
