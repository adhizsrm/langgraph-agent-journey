import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv()


class TestSchema(BaseModel):
    files: list[str] = Field(description="Paths")
    code: str = Field(description="Source code")


llm = ChatOpenAI(
    model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
    api_key=os.environ.get("OPENROUTER_API_KEY"),
    base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
    temperature=0.1,
)


def test_with_structured_output():
    print("Starting native with_structured_output test...")
    try:
        s_llm = llm.with_structured_output(TestSchema)
        res = s_llm.invoke(
            "Output a valid JSON containing 1 file called 'App.jsx' and code containing exactly this string: import React from 'react'; \\n console.log(\\'hello\\');"
        )
        print("SUCCESS: ", res)
    except Exception as e:
        print(f"FAILED with exception: {e}")
