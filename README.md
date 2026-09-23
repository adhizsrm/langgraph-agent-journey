# LangGraph Agent Journey

A phase-by-phase journey from a minimal LLM application to a **LangGraph-based code enhancement agent** that can analyze an existing project, understand a natural-language enhancement request, modify the relevant files, validate the result, and repair failures.

The repository started as a hands-on exploration of LangGraph fundamentals — LLM calls, tools, state, nodes, conditional routing, evaluation, and multi-agent orchestration — and evolved into a practical **LLM-powered software enhancement workflow**.

The goal is not just to generate code with an LLM, but to build a workflow where:

> **The LLM proposes changes; deterministic systems decide whether those changes are safe and valid.**

---

## What this project does

Given an existing application and a request such as:

```text
Add a search bar that filters expenses by category.
```

the system:

1. Analyzes the project structure.
2. Discovers relevant files and entry points.
3. Retrieves bounded code context.
4. Chunks the selected code into manageable context.
5. Sends the relevant context and request to an Enhancement Agent.
6. Validates the LLM's structured response with Pydantic.
7. Safely applies the proposed patches.
8. Checks that the requested changes actually modified the project.
9. Creates an isolated temporary workspace.
10. Runs backend/frontend validation.
11. Runs build and smoke tests.
12. Invokes a Repair Agent when validation fails.
13. Retries repair up to a defined limit.
14. Promotes the enhanced project only when the workflow succeeds.

The system is designed to avoid situations where an LLM produces syntactically valid output but the requested feature is only partially implemented.

---

## Architecture

```text
User Request
     │
     ▼
Project Discovery
     │
     ├── Entry-point discovery
     ├── Keyword/relevance search
     ├── Import/dependency discovery
     └── HTML/CSS/reference discovery
     │
     ▼
Relevant Files
     │
     ▼
Chunker
     │
     ▼
Enhancement Agent
     │
     ▼
Structured LLM Output
     │
     ▼
Pydantic Validation
     │
     ├── Schema validation
     ├── Extra-field rejection
     ├── No-op detection
     └── Change/file consistency
     │
     ▼
Safe Patch Application
     │
     ├── Exact matching
     ├── Normalized matching
     ├── Ambiguous-match rejection
     └── Atomic patching
     │
     ▼
Safety Validation
     │
     ▼
Temporary Workspace
     │
     ▼
Project Validation
     │
     ├── Backend validation
     ├── Frontend build
     └── Smoke testing
     │
     ├───────────────┐
     │               │
   PASS            FAIL
     │               │
     ▼               ▼
 Promotion      Repair Agent
                     │
                     ▼
               Retry validation
                     │
                     ▼
                 PASS / FAIL
```

---

## Core design principle

The project deliberately separates **LLM reasoning** from **system authority**.

### LLM

The LLM is responsible for:

- understanding the user's request
- identifying the intended implementation
- proposing code changes
- producing structured patches
- diagnosing failures during repair

### Deterministic system

The application is responsible for:

- deciding which files are relevant
- validating the LLM output
- rejecting malformed structures
- rejecting no-op patches
- safely applying patches
- detecting incomplete modifications
- running builds and tests
- deciding whether the enhancement succeeded
- deciding whether repair is required

This prevents the workflow from treating:

```text
"the LLM generated something"
```

as equivalent to:

```text
"the requested enhancement was successfully implemented."
```

---

## Retrieval vs Chunking

One important architectural distinction is:

> **Retrieval decides which files matter. Chunking decides how their contents are packaged.**

The current chunking implementation is primarily deterministic rather than LLM-driven.

The workflow first identifies relevant files using deterministic discovery and dependency/relevance logic. The selected file contents are then divided into bounded chunks before being provided to the Enhancement Agent.

The chunker does not independently perform semantic ranking of every chunk.

In simplified form:

```text
Project
   ↓
Which files matter?
   ↓
Retrieval
   ↓
Relevant files
   ↓
How should their contents be packaged?
   ↓
Chunker
   ↓
LLM context
```

---

## Safe patching

LLM-generated code is treated as untrusted input.

The system does not blindly write the generated changes to the project.

### Atomic patching

Multiple patches are prepared in memory first.

For example:

```text
Patch 1 → success
Patch 2 → success
Patch 3 → failure
```

The system does **not** write Patch 1 and Patch 2 to the real file.

Instead:

```text
All patches succeed
      │
      ▼
Write final result
```

or:

```text
Any patch fails
      │
      ▼
Discard changes
      │
      ▼
Original file remains unchanged
```

This prevents partially applied LLM changes from corrupting the project.

### Patch safety checks

The patching layer includes checks for:

- missing patch targets
- ambiguous matches
- normalized whitespace matching
- no-op patches
- atomic application
- effective modification detection

---

## Structured LLM output

The Enhancement Agent uses structured output validated with Pydantic.

The LLM is expected to return a structure containing:

```text
EnhancementAnalysis
├── target_files
├── changes
│   ├── file
│   ├── action
│   └── patches
│       ├── target_content
│       └── replacement_content
└── implementation_checklist
```

Unexpected fields are rejected rather than silently ignored.

This is important because an LLM can produce structurally incorrect JSON that still looks superficially valid.

For example, a malformed response containing nested `changes` in the wrong location should fail validation rather than having the unexpected data silently discarded.

---

## No-op detection

A patch is invalid when:

```text
target_content == replacement_content
```

because it does not actually change the code.

This prevents the model from generating patches merely to describe existing behavior.

For example, if an existing generic handler already supports:

```typescript
setFilters(prev => ({ ...prev, [name]: value }));
```

the model should not create a patch replacing that code with the exact same code.

Instead, it should leave the existing implementation untouched.

---

## False-success prevention

One of the major problems discovered during real-world testing was **false success**.

An LLM could produce a malformed or incomplete structure, and because unexpected fields were previously ignored, part of the intended implementation could be silently discarded.

That could result in:

```text
LLM output
   ↓
Partial changes applied
   ↓
No obvious exception
   ↓
Workflow reports SUCCESS
```

The system was hardened so that:

```text
Malformed output
       ↓
Pydantic validation failure
       ↓
Retry / failure
```

and:

```text
Incomplete modification
       ↓
Safety validation
       ↓
Failure / repair
```

The overall principle is:

> **A workflow should fail safely rather than report success incorrectly.**

---

## Repair Agent

The Repair Agent is an exception path rather than the normal implementation path.

The intended workflow is:

```text
Enhancement
     ↓
Validation
     ↓
PASS ───────────────► Done
     │
     ▼
   FAIL
     │
     ▼
Repair Agent
     │
     ▼
Re-validation
```

The Repair Agent receives concrete validation information such as:

- compiler errors
- syntax errors
- build failures
- smoke-test failures
- patch/safety errors

The repair process prioritizes the actual error reported by the validation system rather than making speculative architectural changes.

Repair attempts are bounded so that the system does not enter an infinite repair loop.

---

## Validation layers

Different layers answer different questions.

### Pydantic validation

> Is the LLM's response structurally valid?

### Patch validation

> Can the requested changes be safely applied?

### Safety validation

> Did the expected project files actually change?

### Compiler/build validation

> Does the resulting project still compile/build?

### Smoke testing

> Can the resulting application actually start/respond as expected?

Therefore:

> **Patch success is not the same as enhancement success.**

A patch can be applied successfully while the resulting application still fails to build.

---

## LangGraph

LangGraph provides the workflow orchestration layer.

The project uses concepts including:

- State
- Nodes
- Edges
- Conditional routing
- Tool calling
- Agent nodes
- Evaluator/validator nodes
- Multi-agent orchestration
- Retry/repair flows
- State persistence/checkpointing

The graph allows the enhancement workflow to move from:

```text
Request
   ↓
Enhance
   ↓
Validate
```

to a controlled workflow such as:

```text
Request
   ↓
Discover
   ↓
Retrieve
   ↓
Enhance
   ↓
Validate
   ↓
     ┌── PASS ──► Promote
     │
   FAIL
     ↓
  Repair
     ↓
 Validate
     ↓
 PASS / FAIL
```

---

## Project structure

The repository has evolved beyond the original single-file phase demonstrations.

A simplified structure is:

```text
langgraph-agent-journey/
│
├── app/
│   ├── agents/
│   │   ├── enhancement_agent.py
│   │   └── repair_agent.py
│   │
│   ├── graph/
│   │   ├── routing.py
│   │   └── safety_node.py
│   │
│   ├── prompts/
│   │   ├── enhancement.py
│   │   └── repair.py
│   │
│   ├── state/
│   │   └── schemas.py
│   │
│   └── utils/
│
├── tests/
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

The repository also contains supporting diagnostic, validation, and experimentation scripts used during development.

---

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/adhizsrm/langgraph-agent-journey.git
cd langgraph-agent-journey
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate it

Windows:

```powershell
venv\Scripts\activate
```

Mac/Linux:

```bash
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment variables

```bash
copy .env.example .env
```

On Mac/Linux:

```bash
cp .env.example .env
```

Configure the required LLM provider settings in `.env`.

### 6. Run the application

```bash
python -m app.main
```

The CLI can then be used to run the enhancement workflow against a target project.

---

## Development and testing

The project includes regression tests covering important parts of the enhancement workflow.

Examples include:

```bash
python test_enhancement_parsing.py
python test_grep_discovery.py
python test_smoke_test_readiness.py
```

The test suite is particularly important for preventing regressions in:

- structured LLM parsing
- retrieval/discovery
- patch safety
- validation
- smoke-test readiness

Real-world end-to-end testing is also used because passing unit tests alone does not guarantee that an LLM-generated enhancement will behave correctly in a real project.

---

## Evolution of the project

The repository originally followed a phase-by-phase learning path:

| Phase | Focus |
|---|---|
| 1 | Minimal Python + LLM application |
| 2 | Tool calling |
| 3 | LangGraph State and Nodes |
| 4 | Conditional routing |
| 5 | Goal-oriented multi-step execution |
| 6 | Multiple tools and dynamic dispatch |
| 7 | Evaluation and retry |
| 8 | Single-agent lifecycle |
| 9+ | Multiple specialist agents |
| 10+ | Orchestrator/delegator architecture |
| 11+ | Programmatic agent creation |
| 12+ | Code ownership across frontend/backend/database/testing |
| 13+ | Communication boundary with an existing application |
| 14+ | LangGraph integration with application workflows |
| 15+ | End-to-end testing and reliability |
| Current | LLM-powered code enhancement and repair workflow |

The early phases remain important because they explain how the current architecture evolved.

---

## Relationship to `context-engine-chatbot`

`context-engine-chatbot` was the original application that motivated the move from basic LangGraph experiments toward a more practical agent architecture.

It is a separate TypeScript/React project containing a RAG pipeline using technologies such as:

- TypeScript
- React
- Ollama
- Weaviate
- semantic retrieval
- hybrid retrieval
- reranking

This repository became the learning and experimentation ground for the Python/LangGraph side of the system.

The two repositories are conceptually related, but this repository is independently executable.

---

## Tech stack

### Core

- **Python**
- **LangGraph**
- **LangChain**
- **Pydantic**

### LLM

- **OpenRouter**
- OpenAI-compatible LLM APIs
- Mistral / Ministral models used during development

### Target applications

The enhancement workflow is designed to work with real application codebases, including projects using technologies such as:

- React
- TypeScript
- JavaScript
- Vite
- Node.js
- Express

### Validation

- Project-specific validation
- TypeScript/JavaScript build validation
- Smoke testing
- Deterministic safety checks

---

## Current status

🚧 **Actively developing**

The core enhancement workflow is operational and has been tested against real application codebases.

Current focus areas include:

- improving enhancement reliability
- hardening patch application
- reducing unnecessary Repair Agent calls
- improving deterministic validation
- real-world volume testing
- improving model reliability for complex cross-file enhancements
- deployment and API integration

Some complex semantic UI enhancements can still be sensitive to the capabilities of the selected LLM. The architecture therefore treats model output as a proposal and relies on deterministic validation to prevent unsafe or falsely successful results.

---

## Key takeaway

The project has evolved from:

```text
"How do I use LangGraph?"
```

into:

```text
"How do I build a reliable software-engineering workflow around an LLM?"
```

The central idea is:

> **LLM = proposal.  
> LangGraph = orchestration.  
> Deterministic systems = authority.**
