import os
import time
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage

from typing import Annotated
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END

# ==========================================
# 1. SETUP
# ==========================================
load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL")
model = os.getenv("OPENROUTER_MODEL")

llm = ChatOpenAI(base_url=base_url, api_key=api_key, model=model, temperature=0.1)


# ==========================================
# 2. TOOLS
# ==========================================
@tool
def calculator(a: float, b: float, operation: str) -> float:
    """Performs basic arithmetic operations: add, subtract, multiply, divide."""
    if operation == "add": return a + b
    elif operation == "subtract": return a - b
    elif operation == "multiply": return a * b
    elif operation == "divide": return a / b
    return 0.0

@tool
def product_lookup(product_name: str) -> float:
    """Fetches the current price of a product from the database catalog."""
    catalog = {
        "laptop": 1200.0,
        "mouse": 25.0,
        "keyboard": 75.0,
        "monitor": 300.0,
        "desk": 450.0
    }
    return catalog.get(product_name.lower().strip(), 0.0)

tools_list = [calculator, product_lookup]
llm_with_tools = llm.bind_tools(tools_list)
tools_map = {t.name: t for t in tools_list}


# ==========================================
# 3. STATE
# ==========================================
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    is_valid_result: bool


# ==========================================
# 4. NODES
# ==========================================
def agent_node(state: AgentState):
    print("\n🧐 [AGENT] Looking at context & thinking about the next step...")
    time.sleep(1) # Added for readability when watching the console
    
    response = llm_with_tools.invoke(state["messages"])
    
    if hasattr(response, 'tool_calls') and len(response.tool_calls) > 0:
        print(f"🤖 [AGENT] Decided to perform {len(response.tool_calls)} action(s).")
    else:
        print("🤖 [AGENT] Believes the goal is complete. Formulating final answer...")
        
    return {"messages": [response]}


def action_node(state: AgentState):
    print("\n🛠️  [ACTION] Executing tools...")
    last_message = state["messages"][-1]
    
    results = []
    for tool_call in last_message.tool_calls:
        print(f"   -> Using tool: {tool_call['name']} | Args: {tool_call['args']}")
        
        selected_tool = tools_map.get(tool_call["name"])
        if selected_tool:
            result = selected_tool.invoke(tool_call)
            print(f"   <- Observation: {result.content}")
            results.append(result)
            
    return {"messages": results}


def evaluator_node(state: AgentState):
    print("\n🔎 [EVALUATOR] Critiquing the Agent's final answer...")
    
    eval_prompt = """Review the entire conversation history.
Does the Agent's final answer completely and accurately fulfill the original Goal?
Reply exactly with 'YES' or 'NO'."""
    
    evaluation = llm.invoke(state["messages"] + [HumanMessage(content=eval_prompt)])
    
    if "YES" in evaluation.content.upper():
        print("✅ [EVALUATOR] Goal successfully achieved. Approving completion!")
        return {"is_valid_result": True}
    else:
        print("❌ [EVALUATOR] Goal incomplete or incorrect. Sending back to Agent.")
        feedback = HumanMessage(content="Evaluator: The goal is not yet complete. Please review the missing requirements and continue.")
        return {"messages": [feedback], "is_valid_result": False}


# ==========================================
# 5. ROUTERS (CONDITIONAL LOGIC)
# ==========================================
def route_after_agent(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and len(last_message.tool_calls) > 0:
        return "action"
    return "evaluator"

def route_after_evaluator(state: AgentState) -> str:
    if state.get("is_valid_result", False):
        return END
    return "agent"


# ==========================================
# 6. GRAPH ASSEMBLY
# ==========================================
def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", agent_node)
    workflow.add_node("action", action_node)
    workflow.add_node("evaluator", evaluator_node)
    
    # Trace the logic:
    # 1. Always start at agent
    workflow.add_edge(START, "agent")
    
    # 2. After agent, route to action (tool) or evaluator
    workflow.add_conditional_edges("agent", route_after_agent, {"action": "action", "evaluator": "evaluator"})
    
    # 3. After action, immediately loop back to agent to observe
    workflow.add_edge("action", "agent")
    
    # 4. After evaluator, route to END if good, or agent if bad
    workflow.add_conditional_edges("evaluator", route_after_evaluator, {"agent": "agent", END: END})
    
    return workflow.compile()


# ==========================================
# 7. EXECUTION DEMO
# ==========================================
def main():
    print("="*60)
    print(" 🧠 LANGGRAPH AGENT SHOWCASE")
    print("="*60)
    app = build_graph()
    
    system_prompt = SystemMessage(content='''You are an intelligent goal-oriented assistant.
When analyzing products, accurately look up their prices. Use calculators for math.
Only provide a final answer when the objective is perfectly achieved. No assumptions.''')

    user_goal = HumanMessage(content='''Goal: Calculate the total cost for my new setup:
- 1 Laptop
- 1 Desk
- 1 Monitor''')

    print(f"\n🎯 {user_goal.content}")
    print("-" * 60)
    
    try:
        final_state = app.invoke(
            {"messages": [system_prompt, user_goal], "is_valid_result": False},
            {"recursion_limit": 15}
        )
        
        print("\n" + "="*60)
        print("🎉 SUCCESSFUL COMPLETION")
        print("="*60)
        print(final_state["messages"][-1].content)
        
    except Exception as e:
        print(f"\n[ERROR] Graph execution failed: {e}")

if __name__ == "__main__":
    main()
