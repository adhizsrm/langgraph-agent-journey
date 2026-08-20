import os
from pprint import pprint
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

from typing import Annotated
from typing_extensions import TypedDict

# LangGraph specific imports
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

llm_with_tools = llm.bind_tools([calculator])

# 1. STATE: define the minimum state required by LangGraph
class AgentState(TypedDict):
    # `add_messages` automatically appends new messages to the existing list
    messages: Annotated[list, add_messages]

# 2. NODES: discrete execution steps
def call_model(state: AgentState):
    print("--- [NODE] call_model ---")
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    
    # LangGraph will append this response to the state using `add_messages`
    return {"messages": [response]}

def execute_tool(state: AgentState):
    print("--- [NODE] execute_tool ---")
    messages = state["messages"]
    last_message = messages[-1]
    
    # For this phase, we hardcode knowing there's a tool call requested
    tool_call = last_message.tool_calls[0]
    print(f"Executing local tool: {tool_call['name']}...")
    
    # Actually run the python logic
    tool_result = calculator.invoke(tool_call)
    
    # Append the result to the state
    return {"messages": [tool_result]}

def build_graph():
    # Initialize the graph builder
    workflow = StateGraph(AgentState)
    
    # Register our nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tool", execute_tool)
    workflow.add_node("final_agent", call_model)
    
    # 3. EDGES: Hardcoding a fixed path for Phase 3 (START -> agent -> tool -> final -> END)
    workflow.add_edge(START, "agent")
    workflow.add_edge("agent", "tool")
    workflow.add_edge("tool", "final_agent")
    workflow.add_edge("final_agent", END)
    
    # Compile the graph
    app = workflow.compile()
    return app

def main():
    print("Building LangGraph application...")
    app = build_graph()
    
    print("Starting process with initial user goal...\n")
    initial_state = {
        "messages": [HumanMessage(content="What is 15 multiplied by 7?")]
    }
    
    # Invoke the graph
    final_state = app.invoke(initial_state)
    
    print("\n--- Final Messages in State ---")
    for msg in final_state["messages"]:
        msg_type = msg.__class__.__name__
        if msg_type == "HumanMessage":
            print(f"USER:   {msg.content}")
        elif msg_type == "AIMessage":
            print(f"AI:     {msg.content if msg.content else '[Requested Tool]'}")
        elif msg_type == "ToolMessage":
            print(f"TOOL:   {msg.content}")

if __name__ == "__main__":
    main()
