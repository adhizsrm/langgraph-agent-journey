from dotenv import load_dotenv

load_dotenv()
from app.agents.llm import llm
from app.prompts.backend import backend_prompt
from app.state.schemas import GeneratedFiles
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
import json

spec = """{
  "entity_spec": {
    "entity_name": "Note",
    "fields": {
      "title": "string"
    }
  },
  "crud_operations": [
    "Create"
  ],
  "api_contract": {
    "base_route": "/api/notes",
    "operations": []
  },
  "execution_order": "backend_first",
  "file_locations": {
    "backend_root": "backend/",
    "frontend_root": "frontend/"
  }
}"""

parser = PydanticOutputParser(pydantic_object=GeneratedFiles)

# Append parser instructions
prompt = backend_prompt.format(spec=spec)
prompt_text = prompt + "\n\n" + parser.get_format_instructions()

try:
    res = llm.invoke(prompt_text)
    with open("diagnostic.txt", "w", encoding="utf-8") as f:
        f.write("RAW:\n" + res.content + "\n\n")
        parsed = parser.parse(res.content)
        f.write("PARSED SUCCESSFULLY!\n")
except Exception as e:
    with open("diagnostic.txt", "w", encoding="utf-8") as f:
        f.write(f"Error: {e}")
