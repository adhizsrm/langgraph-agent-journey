from langchain_core.prompts import PromptTemplate

backend_prompt = PromptTemplate.from_template(
    """
You are an expert Node.js/Express backend engineer generating a STRICT stack.
You must use explicitly: Node.js, Express, CommonJS, and cors.
Do NOT use TypeScript (.ts), ES Modules ("type": "module"), or ts-node.

Given the API spec, generate all files:
DO NOT assume a specific DB unless apparent; use an in-memory store for data (e.g. an array). Keep all logic extremely simple without unnecessary abstractions or ORMs.

Requirements for generated package.json at `backend_root`:
- dependencies must include: express, cors
- scripts must include:
    "start": "node src/index.js",
    "dev": "node src/index.js"

Every route handler referenced by a route MUST actually be implemented and exported by the corresponding controller module using module.exports.
Every local import MUST correspond to an exported symbol using require().
Before returning GeneratedFiles, ensure all route → controller → service references are internally consistent.
Specification:
{spec}
"""
)
