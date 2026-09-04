import os
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from app.state.schemas import (
    OrchestratorOutput,
    GeneratedFiles,
    RepairAnalysis,
    EnhancementAnalysis,
)

load_dotenv()

# Initialize Mistral LLM model
llm = ChatMistralAI(
    model=os.environ.get("MISTRAL_MODEL", "mistral-large-latest"), temperature=0.1
)

from langchain_core.output_parsers import PydanticOutputParser


def create_structured_llm(pydantic_schema):
    parser = PydanticOutputParser(pydantic_object=pydantic_schema)

    class StructuredLLMWrapper:
        def invoke(self, prompt_str):
            if isinstance(prompt_str, str):
                final_prompt = prompt_str + "\n\n" + parser.get_format_instructions()
            else:
                final_prompt = prompt_str

            res = llm.invoke(final_prompt)
            return parser.parse(res.content)

    return StructuredLLMWrapper()


# Setup LLM with robust string-based structured output constraints
orchestrator_llm = create_structured_llm(OrchestratorOutput)
backend_llm = create_structured_llm(GeneratedFiles)
frontend_llm = create_structured_llm(GeneratedFiles)
repair_llm = create_structured_llm(RepairAnalysis)
enhancement_llm = create_structured_llm(EnhancementAnalysis)
