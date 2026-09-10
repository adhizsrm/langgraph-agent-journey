from app.agents.frontend_agent import frontend_prompt
from app.agents.llm import frontend_llm

mock_spec = """
{
  "entity_name": "Note",
  "fields": { "title": "string", "content": "string" },
  "validation_rules": []
}
"""

prompt = frontend_prompt.format(goal="create a simple notes app", spec=mock_spec)


def test_frontend_llm_inference():
    print("Starting Frontend LLM inference...")
    try:
        result = frontend_llm.invoke(prompt)
        print("SUCCESS, parsed output:", len(result.files), "files")
    except Exception as e:
        print(f"FAILED with exception: {e}")
