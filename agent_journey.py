import os
from dotenv import load_dotenv
from typing import Annotated
from typing_extensions import TypedDict

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

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
    # Loop over all requested tool calls
    for tool_call in last_message.tool_calls:
        print(f"Executing local tool: {tool_call['name']}({tool_call['args']})")
        if tool_call["name"] == "calculator":
            tool_msg = calculator.invoke(tool_call)
            results.append(tool_msg)
            
    return {"messages": results}

# 3. CONDITIONAL ROUTING: Here is the logic that decides what to do next
def should_continue(state: AgentState) -> str:
    """Evaluate the state and return the name of the next node to visit."""
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the LLM makes a tool call, route to the "tool" node
    if hasattr(last_message, 'tool_calls') and len(last_message.tool_calls) > 0:
        print(">> [ROUTER] Tool needed -> Routing to 'tool'")
        return "tool"
    
    # Otherwise, the LLM is done thinking and wrote a final answer
    print(">> [ROUTER] No tool needed -> Routing to END")
    return END

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("agent", call_model)
    workflow.add_node("tool", execute_tool)
    
    # Main flow
    workflow.add_edge(START, "agent")
    workflow.add_edge("tool", "agent")  # After tool runs, obviously return to agent
    
    # Conditional Flow
    # After "agent" runs, call 'should_continue' to decide where to go next
    workflow.add_conditional_edges(
        "agent",          # The node we are deciding FROM
        should_continue,  # The routing function
        # Mapping the string output of routing function to a destination node
        {
            "tool": "tool",
            END: END
        }
    )
    
    return workflow.compile()

def main():
    print("Building LangGraph application with conditional routing...\n")
    app = build_graph()
    
    print("Prompting agent...\n")
    initial_state = {
        "messages": [HumanMessage(content="Calculate 15 multiplied by 7 using the calculator tool")]
    }
    
    final_state = app.invoke(initial_state)
    
    print("\n--- Final Output ---")
    print(final_state["messages"][-1].content)

if __name__ == "__main__":
    main()
