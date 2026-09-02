import os
from langchain_mistralai import ChatMistralAI
from app.config import MISTRAL_MODEL_NAME
from app.state.schemas import OrchestratorOutput, GeneratedFiles, RepairAnalysis

# Initialize Mistral LLM model
llm = ChatMistralAI(model=MISTRAL_MODEL_NAME, temperature=0.1)

# Setup LLM with structured output constraints
orch_llm = llm.with_structured_output(OrchestratorOutput)
backend_llm = llm.with_structured_output(GeneratedFiles)
frontend_llm = llm.with_structured_output(GeneratedFiles)
repair_llm = llm.with_structured_output(RepairAnalysis)
