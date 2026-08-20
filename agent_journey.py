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

llm = ChatOpenAI(base_url=base_url, api_key=api_key, model=model)

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
    """Fetches the current price of a product from the database catalog. Use this to find prices before calculating."""
    catalog = {
        "laptop": 1200.0,
        "mouse": 25.0,
        "keyboard": 75.0,
        "monitor": 300.0
    }
    # Return the real price, or 0.0 if not found
    return catalog.get(product_name.lower().strip(), 0.0)

# We now bind MULTIPLE tools to the LLM
tools_list = [calculator, get_product_price]
llm_with_tools = llm.bind_tools(tools_list)

# A simple lookup dictionary for our node to use dynamically
tools_map = {t.name: t for t in tools_list}

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

def call_model(state: AgentState):
    print("--- [NODE] agent ---")
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def execute_tool(state: AgentState):
    print("--- [NODE] tool ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    results = []
    for tool_call in last_message.tool_calls:
        print(f"Executing: {tool_call['name']}({tool_call['args']})")
        
        # Dynamically find the tool based on the name the LLM requested
        selected_tool = tools_map.get(tool_call["name"])
        if selected_tool:
            tool_msg = selected_tool.invoke(tool_call)
            results.append(tool_msg)
            
    return {"messages": results}

def should_continue(state: AgentState) -> str:
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and len(last_message.tool_calls) > 0:
        print(">> [ROUTER] Agent requested tool(s) -> Routing to 'tool'")
        return "tool"
    
    print(">> [ROUTER] Goal Complete -> Routing to END")
    return END

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tool", execute_tool)
    
    workflow.add_edge(START, "agent")
    workflow.add_edge("tool", "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tool": "tool", END: END})
    
    return workflow.compile()

def main():
    print("Building Multi-Tool Agent LangGraph...\n")
    app = build_graph()
    
    system_prompt = SystemMessage(content='''You are a goal-oriented AI agent.
When given a goal involving products, first look up their prices.
Then, calculate the total required.
Only stop and provide a final answer when the entire goal has been fully achieved.
''')

    # The user provided the exact example from their prompt:
    user_goal = HumanMessage(content='''Goal: Calculate the total cost of:
- 1 Laptop
- 2 Mice (Mouse)
- 1 Keyboard''')

    initial_state = {
        "messages": [system_prompt, user_goal]
    }
    
    print("Assigning Goal:")
    print(user_goal.content)
    print("\nStarting execution loop...\n")
    
    final_state = app.invoke(initial_state)
    
    print("\n--- Final Deliverable ---")
    print(final_state["messages"][-1].content)

if __name__ == "__main__":
    main()
