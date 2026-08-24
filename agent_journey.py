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
    catalog = {"laptop": 1200.0, "mouse": 25.0, "keyboard": 75.0, "monitor": 300.0}
    return catalog.get(product_name.lower().strip(), 0.0)


@tool
def calculator(a: float, b: float, operation: str) -> float:
    """Performs basic arithmetic operations."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    return 0.0


research_tools_map = {product_lookup.name: product_lookup}
calc_tools_map = {calculator.name: calculator}

research_llm = llm.bind_tools([product_lookup])
calc_llm = llm.bind_tools([calculator])


# ==========================================
# SUPERVISOR / ORCHESTRATOR NODE
# ==========================================
def orchestrator_node(state: AgentState):
    print("\n--- [ORCHESTRATOR] Reviewing Progress ---")

    # We force the Supervisor to reply with a strict routing command.
    # (In production, you'd use Pydantic/function-calling to enforce structure).
    sys_msg = SystemMessage(
        content="""
    You are the Supervisor. You manage two workers:
    - 'researcher': looks up product prices.
    - 'calculator': performs mathematics.

    Analyze the conversation. 
    If you need prices, reply EXACTLY with: ROUTE: researcher
    If you have prices but need math, reply EXACTLY with: ROUTE: calculator
    If the goal is fully answered, reply EXACTLY with: ROUTE: finish
    """
    )

    response = llm.invoke([sys_msg] + state["messages"])
    return {"messages": [response]}


def orchestrator_router(state: AgentState) -> str:
    # Router looks at what the Supervisor decided
    last_message_content = state["messages"][-1].content

    if "ROUTE: researcher" in last_message_content:
        print(">> [ROUTER] Delegating to Researcher")
        return "researcher"
    elif "ROUTE: calculator" in last_message_content:
        print(">> [ROUTER] Delegating to Calculator")
        return "calculator"
    else:
        print(">> [ROUTER] Goal completely achieved.")
        return END


# ==========================================
# SIMPLE WORKER NODES
# ==========================================
def worker_research(state: AgentState):
    print("--- [WORKER: RESEARCHER] Invoked ---")

    sys_msg = SystemMessage(
        content="You are a researcher. Get the required product prices using your tool."
    )
    response = research_llm.invoke([sys_msg] + state["messages"])

    results = [response]
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in response.tool_calls:
            print(
                f"   -> [Researcher Action]: {tool_call['name']}({tool_call['args']})"
            )
            tool = research_tools_map.get(tool_call["name"])
            results.append(tool.invoke(tool_call))

    return {"messages": results}

def worker_calculator(state: AgentState):
    print("--- [WORKER: CALCULATOR] Invoked ---")

    sys_msg = SystemMessage(content="You are a calculator. Do math using your tool.")
    response = calc_llm.invoke([sys_msg] + state["messages"])

    results = [response]
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tool_call in last_message.tool_calls:
            print(
                f"   -> [Calculator Action]: {tool_call['name']}({tool_call['args']})"
            )
            tool = calc_tools_map.get(tool_call["name"])
            results.append(tool.invoke(tool_call))

    return {"messages": results}

# ==========================================
# GRAPH ASSEMBLY
# ==========================================
def build_orchestrator():
    workflow = StateGraph(AgentState)

    # Add our hubs and spokes
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("researcher", worker_research)
    workflow.add_node("calculator", worker_calculator)

    # Entry point is always Supervisor
    workflow.add_edge(START, "orchestrator")

    # Supervisor delegates outwards
    workflow.add_conditional_edges(
        "orchestrator",
        orchestrator_router,
        {"researcher": "researcher", "calculator": "calculator", END: END},
    )

    # Workers always route backwards to Supervisor when done
    workflow.add_edge("researcher", "orchestrator")
    workflow.add_edge("calculator", "orchestrator")

    return workflow.compile()


def main():
    print("Building Hub-and-Spoke Orchestrator...\n")
    app = build_orchestrator()

    user_goal = HumanMessage(
        content="Goal: Find the total cost of 1 Keyboard and 2 Monitors."
    )

    print(f"{user_goal.content}")
    print("=" * 60)

    final_state = app.invoke({"messages": [user_goal]}, {"recursion_limit": 15})

    print("\n" + "=" * 60)
    print("🎉 FINAL DELIVERABLE")
    print(final_state["messages"][-1].content)


if __name__ == "__main__":
    main()
