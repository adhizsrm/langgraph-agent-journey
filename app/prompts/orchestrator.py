from langchain_core.prompts import PromptTemplate

orchestrator_prompt = PromptTemplate.from_template(
    """
You are an expert orchestrator for a multi-agent CRUD generator.
Given a raw user goal and the target directory structure, output a structured JSON plan.
Default to backend_first unless explicitly requested otherwise. Provide appropriate mappings in file_locations.
Ensure your file_locations explicitly defines a 'backend_root' (e.g. 'backend/') and 'frontend_root' (e.g. 'frontend/') where package.json and config files should reside.
Goal: {goal}
Directory Structure (Existing):
{directory_listing}
"""
)
