import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL")
model = os.getenv("OPENROUTER_MODEL")

# Define a simple deterministic tool
@tool
def calculator(a: float, b: float, operation: str) -> float:
    """Performs basic arithmetic operations: add, subtract, multiply, divide."""
    if operation == "add":
        return a + b
    elif operation == "subtract":
        return a - b
    elif operation == "multiply":
        return a * b
    elif operation == "divide":
        if b == 0:
            return "Cannot divide by zero"
        return a / b
    else:
        return "Unknown operation"

def main():
    print("Initializing LLM with Tool...\n")
    llm = ChatOpenAI(base_url=base_url, api_key=api_key, model=model)
    
    # Bind the tool to the LLM so it knows it exists and how to use it
    llm_with_tools = llm.bind_tools([calculator])
    
    # 1. User Goal -> LLM
    # We use a HumanMessage to start the conversation history
    messages = [HumanMessage(content="What is 15 multiplied by 7?")]
    print(f"User Goal: {messages[0].content}\n")
    
    # 2. LLM decides what action is needed
    print("Thinking...")
    ai_msg = llm_with_tools.invoke(messages)
    messages.append(ai_msg)
    
    # 3. Check if the LLM decided to use a tool
    if ai_msg.tool_calls:
        for tool_call in ai_msg.tool_calls:
            print(f"Tool Requested: {tool_call['name']}")
            print(f"Tool Arguments: {tool_call['args']}")
            
            # 4. Use Tool and Observe Tool Result
            # Calling `.invoke()` with the tool_call dictionary automatically
            # returns a ToolMessage containing the result and tool_call_id
            tool_msg = calculator.invoke(tool_call)
            messages.append(tool_msg)
            
            print(f"Tool Result:    {tool_msg.content}\n")
            
        # 5. Tool Result -> LLM -> Final Response
        print("Sending Tool Result back to LLM to get final answer...")
        final_response = llm_with_tools.invoke(messages)
        print("\n--- Final Answer ---")
        print(final_response.content)
    else:
        print("\n--- Final Answer (No tool needed) ---")
        print(ai_msg.content)

if __name__ == "__main__":
    main()
