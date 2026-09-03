from app.state.schemas import GraphState
from app.agents.llm import orchestrator_llm
from app.prompts.orchestrator import orchestrator_prompt


def orchestrator_node(state: GraphState) -> GraphState:
    print("Running Orchestrator Node...")
    prompt = orchestrator_prompt.format(
        goal=state["raw_goal"], directory_listing=state["directory_listing"]
    )
    result = orchestrator_llm.invoke(prompt)
    return {"orchestrator_spec": result}
