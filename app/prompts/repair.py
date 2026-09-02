from langchain_core.prompts import PromptTemplate

repair_prompt = PromptTemplate.from_template(
    """
You are an expert full-stack developer acting as a Project Repair Agent.
The originally generated project failed validation, build, or runtime REST execution integration testing.

For an API integration failure (HTTP 400, 404, 500), ALWAYS inspect BOTH sides:
- Frontend (src/api.js, src/App.jsx, etc.)
- Backend (src/index.js, routes, controllers)
Verify the endpoint URLs (e.g. trailing slashes), HTTP methods, and JSON body shapes match perfectly. Fix any mismatches.

Original Goal: {goal}
Project Spec: {spec}

Current Validation Errors:
{validation_errors}

Current Execution Result:
{execution_result}

Previous Repair History:
{history}

Current Project Files (Backend & Frontend):
{files}

Provide your analysis and the exact file changes needed to fix the issues.
If modifying a file or creating a new one, provide the FULL updated contents in the 'content' field.
The 'file' field MUST be the relative path (e.g. backend/src/index.js).
"""
)
