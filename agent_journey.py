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

@tool
def calculator(a: float, b: float, operation: str) -> float:
    """Performs basic arithmetic operations: add, subtract, multiply, divide."""
    if operation == "add": return a + b
    elif operation == "subtract": return a - b
    elif operation == "multiply": return a * b
    elif operation == "divide": return a / b
    return 0.0

@tool
def get_product_price(product_name: str) -> float:
    """Fetches the current price of a product from the database catalog."""
    catalog = {
        "laptop": 1200.0,
        "mouse": 25.0,
        "keyboard": 75.0,
        "monitor": 300.0
    }
    return catalog.get(product_name.lower().strip(), 0.0)

tools_list = [calculator, get_product_price]
llm_with_tools = llm.bind_tools(tools_list)
tools_map = {t.name: t for t in tools_list}

# We extend AgentState to hold our evaluation flag
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    is_valid_result: bool

def call_model(state: AgentState):
    print("--- [NODE] agent ---")
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def execute_tool(state: AgentState):
    print("--- [NODE] action (tool) ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    results = []
    for tool_call in last_message.tool_calls:
        print(f"Executing: {tool_call['name']}({tool_call['args']})")
        selected_tool = tools_map.get(tool_call["name"])
        if selected_tool:
            tool_msg = selected_tool.invoke(tool_call)
            results.append(tool_msg)
            
    return {"messages": results}

def evaluate_result(state: AgentState):
    print("--- [NODE] evaluator ---")
    messages = state["messages"]
    
    # Use the LLM as a critic to evaluate if the objective is completely solved
    eval_prompt = """Does the conversation history show that the initial goal was completely solved?
Answer exactly 'YES' if all parts of the goal are complete and the final answer is present.
Answer 'NO' if it is incomplete or incorrect."""

    # We send the messages plus our evaluation prompt
    evaluation = llm.invoke(messages + [HumanMessage(content=eval_prompt)])
    
    print(f">> [EVALUATOR] thought: {evaluation.content}")
    
    if "YES" in evaluation.content.upper():
        print(">> [EVALUATOR] Goal Achieved -> Approved!")
        return {"is_valid_result": True}
    else:
        print(">> [EVALUATOR] Goal NOT Achieved -> Rejecting and forcing retry.")
        return {
            "messages": [HumanMessage(content="Evaluator: The goal is not yet complete or the formatting is wrong. Please continue.")],
            "is_valid_result": False
        }

# --- Router Functions ---
def should_use_tool(state: AgentState) -> str:
    # Router 1: Does the agent want a tool or does it think it's done?
    last_message = state["messages"][-1]
    
    if hasattr(last_message, 'tool_calls') and len(last_message.tool_calls) > 0:
        return "action"
    
    # The agent thinks it's done, so send it to the evaluator!
    return "evaluator"

def check_eval(state: AgentState) -> str:
    # Router 2: Did the evaluator approve?
    if state.get("is_valid_result", False):
        return END
    else:
        # Go back to the agent to try again
        return "agent"

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", call_model)
    workflow.add_node("action", execute_tool)
    workflow.add_node("evaluator", evaluate_result)
    
    # 1. Start at the agent
    workflow.add_edge(START, "agent")
    
    # 2. Agent decides to Tool, or send to Evaluator
    workflow.add_conditional_edges("agent", should_use_tool, {"action": "action", "evaluator": "evaluator"})
    
    # 3. If action was taken, observe (go back to agent)
    workflow.add_edge("action", "agent")
    
    # 4. If evaluator was triggered, decide based on result
    workflow.add_conditional_edges("evaluator", check_eval, {"agent": "agent", END: END})
    
    return workflow.compile()

def main():
    print("Building Evaluator LangGraph...\n")
    app = build_graph()
    
    system_prompt = SystemMessage(content='''You are a goal-oriented AI agent.
When given a goal involving products, first look up their prices.
Then, calculate the total required.
''')

    user_goal = HumanMessage(content='''Goal: Calculate the total cost of:
- 1 Laptop
- 2 Mice (Mouse)
- 1 Keyboard''')

    initial_state = {
        "messages": [system_prompt, user_goal],
        "is_valid_result": False
    }
    
    print("Assigning Goal...")
    print("\nStarting execution loop...\n")
    
    final_state = app.invoke(initial_state)
    
    print("\n--- Final Approved Deliverable ---")
    print(final_state["messages"][-1].content)

if __name__ == "__main__":
    main()
