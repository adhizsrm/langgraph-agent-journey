import os
import urllib.request
import urllib.parse
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END

load_dotenv()
llm_provider = os.getenv("LLM_PROVIDER", "openrouter").lower()

if llm_provider == "mistral":
    from langchain_mistralai import ChatMistralAI

    api_key = os.getenv("MISTRAL_API_KEY")
    model = os.getenv("MISTRAL_MODEL", "mistral-large-latest")
    llm = ChatMistralAI(api_key=api_key, model=model, temperature=0.1)
else:
    api_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASE_URL")
    model = os.getenv("OPENROUTER_MODEL")
    llm = ChatOpenAI(base_url=base_url, api_key=api_key, model=model, temperature=0.1)


def _format_messages_for_llm(messages):
    msgs = list(messages)
    if msgs and msgs[-1].type == "ai":
        msgs.append(HumanMessage(content="Please proceed with the next step."))
    return msgs


# All agents share the same basic state schema for simplicity in handoffs
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ==========================================
# 1. SPECIALIST AGENT: RESEARCHER
# ==========================================
@tool
def product_lookup(product_name: str) -> float:
    """Fetches the current price of a product."""
    catalog = {"laptop": 1200.0, "mouse": 25.0, "keyboard": 75.0, "monitor": 300.0}
    return catalog.get(product_name.lower().strip(), 0.0)


research_llm = llm.bind_tools([product_lookup])


def research_node(state: AgentState):
    print("   --- [RESEARCH SPECIALIST] Thinking ---")
    sys = SystemMessage(
        content="You are a researcher. Get product prices. Do not do math."
    )
    return {
        "messages": [
            research_llm.invoke(_format_messages_for_llm([sys] + state["messages"]))
        ]
    }


def research_action(state: AgentState):
    last = state["messages"][-1]
    results = []
    for tool_call in last.tool_calls:
        print(f"      [Research Action]: {tool_call['name']}")
        results.append(product_lookup.invoke(tool_call))
    return {"messages": results}


def research_router(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "action"
    return END


def build_researcher():
    g = StateGraph(AgentState)
    g.add_node("agent", research_node)
    g.add_node("action", research_action)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", research_router, {"action": "action", END: END})
    g.add_edge("action", "agent")
    return g.compile()


# ==========================================
# 2. SPECIALIST AGENT: CALCULATOR
# ==========================================
@tool
def calculator(a: float, b: float, operation: str) -> float:
    """Performs basic arithmetic operations."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    return 0.0


calc_llm = llm.bind_tools([calculator])


def calc_node(state: AgentState):
    print("   --- [CALC SPECIALIST] Thinking ---")
    sys = SystemMessage(
        content="You are a calculator. Read prices from history and do math. Do not search for products."
    )
    return {
        "messages": [
            calc_llm.invoke(_format_messages_for_llm([sys] + state["messages"]))
        ]
    }


def calc_action(state: AgentState):
    last = state["messages"][-1]
    results = []
    for tool_call in last.tool_calls:
        print(f"      [Calculator Action]: {tool_call['name']}")
        results.append(calculator.invoke(tool_call))
    return {"messages": results}


def calc_router(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and len(last_message.tool_calls) > 0:
        return "action"
    return END


def build_calculator():
    g = StateGraph(AgentState)
    g.add_node("agent", calc_node)
    g.add_node("action", calc_action)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", calc_router, {"action": "action", END: END})
    g.add_edge("action", "agent")
    return g.compile()


# ==========================================
# 4. THE ORCHESTRATOR
# ==========================================
def orchestrator_node(state: AgentState):
    print("\n[ORCHESTRATOR] Reviewing entire state...")
    sys = SystemMessage(
        content="""
        You are the Supervisor of three autonomous specialist agents:
        1. 'researcher' - securely finds product prices.
        2. 'calculator' - accurately performs mathematics.

        Analyze the conversation. 
        If you need prices, reply EXACTLY with: ROUTE: researcher
        If you need math, reply EXACTLY with: ROUTE: calculator
        If the objective given by the user is fully answered (all parts), provide a final comprehensive answer summarizing the results directly to the user."""
    )

    response = llm.invoke(_format_messages_for_llm([sys] + state["messages"]))
    return {"messages": [response]}


def orchestrator_router(state: AgentState) -> str:
    txt = state["messages"][-1].content
    if "ROUTE: researcher" in txt:
        print(">> [ROUTER] Handing over completely to Research Specialist Sub-Graph")
        return "researcher"
    elif "ROUTE: calculator" in txt:
        print(">> [ROUTER] Handing over completely to Calculator Specialist Sub-Graph")
        return "calculator"
    print(">> [ROUTER] Goal completely achieved.")
    return END


def build_hierarchical_graph():
    # 1. Compile the sub-graphs independently!
    research_app = build_researcher()
    calc_app = build_calculator()

    # 2. Build the main Top-Level graph
    workflow = StateGraph(AgentState)
    workflow.add_node("orchestrator", orchestrator_node)

    # 3. ADDING COMPILED GRAPHS AS NODES
    workflow.add_node("researcher", research_app)
    workflow.add_node("calculator", calc_app)

    # 4. Same hub-and-spoke logic
    workflow.add_edge(START, "orchestrator")
    workflow.add_conditional_edges(
        "orchestrator",
        orchestrator_router,
        {
            "researcher": "researcher",
            "calculator": "calculator",
            END: END,
        },
    )

    workflow.add_edge("researcher", "orchestrator")
    workflow.add_edge("calculator", "orchestrator")
    return workflow.compile()


# ==========================================
# 5. EXECUTION (INTERACTIVE REPL)
# ==========================================
def main():
    print("Building Scaled Hierarchical Agent Graph...\n")
    app = build_hierarchical_graph()

    print("Agent is ready! Type 'quit' to exit.")

    while True:
        try:
            print("\n" + "-" * 60)
            user_input = input("Enter your goal: ")

            if user_input.lower() in ["quit", "exit", "q"]:
                print("Exiting...")
                break

            if not user_input.strip():
                continue

            goal = HumanMessage(content=user_input)

            # Use a fresh state on each new user request! (No memory persistence between inputs)
            final_state = app.invoke({"messages": [goal]}, {"recursion_limit": 25})

            print("\n" + "=" * 60)
            print("--- FINAL HIERARCHICAL DELIVERABLE ---")
            print(final_state["messages"][-1].content)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n[ERROR] execution failed: {e}")


if __name__ == "__main__":
    main()
