import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")
base_url = os.getenv("OPENROUTER_BASE_URL")
model = os.getenv("OPENROUTER_MODEL")

def main():
    print("Initializing LLM...\n")
    
    # We use ChatOpenAI because OpenRouter provides an OpenAI-compatible API
    llm = ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model, # You can switch this to another model later if desired
    )
    
    prompt = "Hello! Please reply with a short greeting."
    print(f"Sending prompt to LLM: '{prompt}'\n")
    
    # Make the LLM call
    response = llm.invoke(prompt)
    
    print("--- LLM Response ---")
    print(response.content)

if __name__ == "__main__":
    main()
