from langchain_core.prompts import PromptTemplate

orchestrator_prompt = PromptTemplate.from_template(
    """
You are an expert orchestrator for a multi-agent CRUD generator.
Given a raw user goal and the target directory structure, output a structured JSON plan.
Default to backend_first unless explicitly requested otherwise. Provide appropriate mappings in file_locations.
Ensure your file_locations explicitly defines a 'backend_root' (e.g. 'backend/') and 'frontend_root' (e.g. 'frontend/') where package.json and config files should reside.

CRITICAL JSON FORMATTING INSTRUCTIONS:
You MUST return ONLY valid, raw JSON. 
DO NOT wrap the JSON in Markdown code fences (e.g., ```json ... ```).
DO NOT use a top-level "plan" wrapper object or any extra fields.
Your output MUST contain EXACTLY these five top-level fields:
1. "entity_spec": Object with "entity_name" (string), "fields" (object mapping name to type), and "validation_rules" (array of strings).
2. "crud_operations": Array of exactly expected operations (e.g., ["Create", "Read", "Update", "Delete"]).
3. "api_contract": Object with "base_route" (string) and "operations" (array of objects containing method, path, request/response shape).
4. "execution_order": String, either "backend_first" or "frontend_first".
5. "file_locations": Object with "backend_root" (string) and "frontend_root" (string).

Goal: {goal}
Directory Structure (Existing):
{directory_listing}
"""
)
