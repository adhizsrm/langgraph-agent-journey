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

# Setup LLM with structured output constraints
orchestrator_llm = llm.with_structured_output(OrchestratorOutput)
backend_llm = llm.with_structured_output(GeneratedFiles)
frontend_llm = llm.with_structured_output(GeneratedFiles)
repair_llm = llm.with_structured_output(RepairAnalysis)
enhancement_llm = llm.with_structured_output(EnhancementAnalysis)
