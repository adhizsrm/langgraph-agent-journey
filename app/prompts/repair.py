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

Provide your analysis and the exact file changes needed to fix the issues. Do not merely describe the problem in the analysis; produce the actual repair action.
After proposing repairs, verify the resulting file graph mentally before returning.

The 'file' field MUST be the relative path (e.g. backend/src/index.js).

CRITICAL INSTRUCTION:
The existing-file manifest is authoritative for determining whether a path already exists.
You must respect the following schema rules exactly:
- `CREATE`: Use ONLY when the target file DOES NOT already exist. Do not propose CREATE for a path listed in the existing-file manifest.
- `MODIFY`: Use ONLY when the target file ALREADY EXISTS in the manifest and needs changes.
- `DELETE`: Use ONLY when an existing file should be removed.

If modifying a file or creating a new one, provide the FULL updated contents in the 'content' field.
When topology reports a duplicate/orphan file, you MUST either wire it into the application if it is genuinely required, or delete it using the 'delete' action if it is unnecessary.
All modified imports must point to files that actually exist.
"""
)
