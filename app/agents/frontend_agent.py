from app.state.schemas import GraphState
from app.agents.llm import frontend_llm
from app.prompts.frontend import frontend_prompt


def frontend_agent_node(state: GraphState) -> GraphState:
    print("Running Frontend Agent Node...")
    spec = state["orchestrator_spec"]
    spec_json = spec.model_dump_json(indent=2)
    prompt = frontend_prompt.format(spec=spec_json)
    result = frontend_llm.invoke(prompt)
    return {"frontend_files": result}
