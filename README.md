# LangGraph Agent Journey

A phase-by-phase build of an LLM agent using [LangGraph](https://github.com/langchain-ai/langgraph), starting from a single raw LLM call and growing into a multi-agent, orchestrated system that eventually plugs into an existing TypeScript/React RAG application.

Each phase is its own commit, so the git history doubles as a build log. If you're coming from JavaScript/Node/React (like I was), the [Coming from JS/Node](#coming-from-jsnode) section below maps the unfamiliar Python bits to things you already know.

## Why this repo exists

I wanted to learn LangGraph the way I actually learn best: build the smallest possible thing, get it working, then add exactly one new concept at a time. Each phase is deliberately minimal — the point isn't the calculator or the product catalog, it's understanding State, Nodes, Edges, and Conditional Edges well enough to build real agents on top of them.

## Roadmap

| Phase | Focus |
|---|---|
| 1 | Minimal Python + LLM application (a single `.invoke()` call) |
| 2 | Add a tool, manually inspect and run tool calls |
| 3 | Introduce LangGraph — State, Nodes, a fixed (hardcoded) Edge path |
| 4 | Add conditional routing — the agent decides tool vs. done |
| 5 | Make it goal-oriented — multi-step goals via a system prompt + loop |
| 6 | Add a second tool, dynamic tool dispatch by name |
| 7 | Add an evaluator node — critique the result, retry on failure |
| 8 | Final single-agent demo — polished output, recursion limits, error handling |
| 9+ | Multiple specialist agents, each with one responsibility |
| 10+ | Orchestrator/delegator agent — breaks down goals, delegates, collects results |
| 11+ | Programmatic agent creation from agent definitions (responsibilities, tools, scopes) |
| 12+ | Code-ownership proof of concept — frontend/backend/db/testing agents |
| 13+ | Define the communication boundary with the existing TS/React RAG app |
| 14+ | Integrate LangGraph agent with RAG as a callable tool |
| 15 | End-to-end testing, regression testing, full documentation |

### Build log (dates)

- **18 Aug** — Phases 1–4: Python fundamentals, State/Nodes/Edges/Conditional Edges
- **19 Aug** — Goal-oriented single agent (multi-step goals, tools, state)
- **20 Aug** — Evaluation and completion checks (retry/failure handling)
- **21 Aug** — Multiple specialist agents, each with a defined responsibility
- **22 Aug** — Testing, debugging, documentation, regression pass
- **23 Aug** — Buffer/catch-up day
- **24 Aug** — Orchestrator/delegator agent
- **25 Aug** — Programmatic agent creation from agent definitions
- **26 Aug** — Code-ownership proof of concept (frontend/backend/db/testing agents)
- **27 Aug** — Define communication boundary with existing TS/React RAG app
- **28 Aug** — Integrate LangGraph agent with RAG as a tool
- **29 Aug** — End-to-end + regression testing, final documentation

## Project structure

```
langgraph-agent-journey/
├── agent_journey.py   # all 8 phases live here, one function per phase
├── requirements.txt   # Python dependencies (like package.json)
├── .env.example        # template for required environment variables
├── .gitignore
└── README.md
```

Each phase is its own function (`phase1()` through `phase8()`) inside `agent_journey.py`, kept self-contained so any single phase can be read top-to-bottom without jumping around the file. Run one phase at a time from the command line:

```bash
python agent_journey.py 1   # runs phase1()
python agent_journey.py 5   # runs phase5()
python agent_journey.py 8   # runs phase8()
```

The git history still reflects the phase-by-phase build — each commit adds that phase's function to `agent_journey.py` without rewriting the ones before it.

## Getting started

```bash
# 1. Clone
git clone https://github.com/<your-username>/langgraph-agent-journey.git
cd langgraph-agent-journey

# 2. Create a virtual environment (isolated package folder, like node_modules)
python -m venv venv

# 3. Activate it — do this every time you open a new terminal
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 4. Install dependencies (like npm install)
pip install -r requirements.txt

# 5. Add your environment variables
cp .env.example .env
# then fill in OPENROUTER_API_KEY, OPENROUTER_BASE_URL, OPENROUTER_MODEL

# 6. Run any phase (like node index.js -- with an argument)
python agent_journey.py 1
```

## Coming from JS/Node

| Python | JS/Node equivalent |
|---|---|
| `venv/` folder | `node_modules/` |
| `requirements.txt` | `package.json` dependencies |
| `pip install -r requirements.txt` | `npm install` |
| `source venv/bin/activate` | *(no direct equivalent — see note below)* |
| `python phase1.py` | `node phase1.js` |
| `.env` | `.env` (same idea, same tool — `dotenv`) |

The one real difference: npm always resolves packages from `node_modules` automatically. Python doesn't — you have to explicitly "activate" a venv so `python`/`pip` know to use *this* project's packages instead of whatever's installed system-wide. Forgetting to activate is the #1 cause of `ModuleNotFoundError`.

## Relationship to `context-engine-chatbot`

This repo is the *learning ground* — every concept here (single agent → tools → conditional routing → goal-oriented loops → evaluation → multi-agent → orchestrator) is deliberately built with throwaway tools (a calculator, a fake product catalog) so the LangGraph mechanics stay front and center.

Once these patterns are solid, the actual integration work happens inside the existing [`context-engine-chatbot`](../context-engine-chatbot) repo — that's the TypeScript + React RAG chatbot already running Ollama (`nomic-embed-text`) for embeddings and Weaviate as the vector store. Rather than standing up a separate Python service, the plan is to bring Python/LangGraph into that codebase directly and wire retrieval (Weaviate) in as a LangGraph tool — the same shape as `get_product_price` in Phase 6, just swapping the fake catalog lookup for a real Weaviate query.

This repo does not call or depend on `context-engine-chatbot` — it's a standalone sandbox. The two repos only connect once the roadmap reaches Phases 13–14 (27–28 Aug), when patterns proven here get carried over.

## Tech stack

**This repo (LangGraph journey)**
- **LangGraph** — state graph orchestration for the agent
- **LangChain (langchain-openai)** — LLM client, tool binding
- **OpenRouter** — OpenAI-compatible API used as the LLM provider
- **Python** — 3.10+

**`context-engine-chatbot` (existing, separate repo — integration target)**
- **TypeScript + React** — application layer
- **Ollama (`nomic-embed-text`)** — embedding model
- **Weaviate** — vector database

## Status

🚧 In progress — actively building through the roadmap above. See commit history for phase-by-phase progress.