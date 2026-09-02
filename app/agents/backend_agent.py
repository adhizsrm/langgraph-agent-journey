from app.state.schemas import GraphState
from app.agents.llm import backend_llm
from app.prompts.backend import backend_prompt


def backend_agent_node(state: GraphState) -> GraphState:
    print("Running Backend Agent Node...")
    spec = state["orchestrator_spec"]
    spec_json = spec.model_dump_json(indent=2)
    prompt = backend_prompt.format(spec=spec_json)
    result = backend_llm.invoke(prompt)
    return {"backend_files": result}
