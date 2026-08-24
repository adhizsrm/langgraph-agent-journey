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

# ==========================================
# AGENT A: RESEARCH AGENT
# ==========================================
class ResearchState(TypedDict):
    messages: Annotated[list, add_messages]

@tool
def search_wiki(query: str) -> str:
    """Searches a mock wiki for information."""
    mock_db = {
        "python": "Python is a high-level programming language created in 1991.",
        "langgraph": "LangGraph is a library for building stateful, multi-actor applications with LLMs."
    }
    return mock_db.get(query.lower().strip(), "Information not found.")

research_tools = [search_wiki]
research_llm = llm.bind_tools(research_tools)
research_tools_map = {t.name: t for t in research_tools}

def research_agent_node(state: ResearchState):
    print("--- [AGENT A: RESEARCHER] Thinking ---")
    response = research_llm.invoke(state["messages"])
    return {"messages": [response]}

def research_action_node(state: ResearchState):
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        print(f"--- [AGENT A: RESEARCHER] Action: {tool_call['name']}({tool_call['args']}) ---")
        tool = research_tools_map.get(tool_call["name"])
        if tool:
            results.append(tool.invoke(tool_call))
    return {"messages": results}

def research_router(state: ResearchState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and len(last_message.tool_calls) > 0:
        return "action"
    return END

def build_research_agent():
    workflow = StateGraph(ResearchState)
    workflow.add_node("agent", research_agent_node)
    workflow.add_node("action", research_action_node)
    
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", research_router, {"action": "action", END: END})
    workflow.add_edge("action", "agent")
    
    return workflow.compile()


# ==========================================
# AGENT B: CALCULATION AGENT (STEP 4)
# ==========================================
class CalcState(TypedDict):
    # Notice this is completely independent from ResearchState!
    messages: Annotated[list, add_messages]

@tool
def calculator(a: float, b: float, operation: str) -> float:
    """Performs basic arithmetic operations: add, subtract, multiply, divide."""
    if operation == "add": return a + b
    elif operation == "subtract": return a - b
    elif operation == "multiply": return a * b
    elif operation == "divide": return a / b
    return 0.0

calc_tools = [calculator]
calc_llm = llm.bind_tools(calc_tools)
calc_tools_map = {t.name: t for t in calc_tools}

def calc_agent_node(state: CalcState):
    print("--- [AGENT B: CALCULATOR] Thinking ---")
    response = calc_llm.invoke(state["messages"])
    return {"messages": [response]}

def calc_action_node(state: CalcState):
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        print(f"--- [AGENT B: CALCULATOR] Action: {tool_call['name']}({tool_call['args']}) ---")
        tool = calc_tools_map.get(tool_call["name"])
        if tool:
            results.append(tool.invoke(tool_call))
    return {"messages": results}

def calc_router(state: CalcState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and len(last_message.tool_calls) > 0:
        return "action"
    return END

def build_calc_agent():
    workflow = StateGraph(CalcState)
    workflow.add_node("agent", calc_agent_node)
    workflow.add_node("action", calc_action_node)
    
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", calc_router, {"action": "action", END: END})
    workflow.add_edge("action", "agent")
    
    return workflow.compile()


# ==========================================
# TEST EXECUTION (STEP 5)
# ==========================================
def main():
    print("Compiling Agents...\n")
    research_agent = build_research_agent()
    calc_agent = build_calc_agent()
    
    print("="*50)
    print("RUNNING AGENT A (Independent Researcher)")
    print("="*50)
    sys_a = SystemMessage(content="You are a researcher. Use the search_wiki tool to find facts. Provide a concise summary.")
    goal_a = HumanMessage(content="What is LangGraph?")
    
    res_a = research_agent.invoke({"messages": [sys_a, goal_a]})
    print("\n[RESULT A]:", res_a["messages"][-1].content)
    
    print("\n" + "="*50)
    print("RUNNING AGENT B (Independent Calculator)")
    print("="*50)
    sys_b = SystemMessage(content="You are a strict calculator. Only use the calculator tool to answer.")
    goal_b = HumanMessage(content="What is 452 multiplied by 13?")
    
    res_b = calc_agent.invoke({"messages": [sys_b, goal_b]})
    print("\n[RESULT B]:", res_b["messages"][-1].content)

if __name__ == "__main__":
    main()
