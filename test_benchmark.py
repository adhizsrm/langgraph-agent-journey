import time
import json
import os
import shutil
from unittest.mock import patch
from app.graph.builder import build_graph
from app.state.schemas import FileContent, GeneratedFiles, OrchestratorOutput
from app.state.schemas import GraphState


class BenchmarkMetrics:
    def __init__(self):
        self.node_times = {}
        self.llm_calls = 0
        self.repair_attempts = 0
        self.validation_failures = 0
        self.files_discovered = 0
        self.context_sizes = []
        self.start_time = 0
        self.end_time = 0


metrics = BenchmarkMetrics()


def trace_node(node_func, node_name):
    def wrapped(state: GraphState):
        start = time.perf_counter()
        res = node_func(state)
        elapsed = time.perf_counter() - start
        if node_name not in metrics.node_times:
            metrics.node_times[node_name] = []
        metrics.node_times[node_name].append(elapsed)
        return res

    return wrapped


# Let's mock LLM heavily to track exactly context sizes
class MockLLM:
    def __init__(self, mode="orchestrator"):
        self.mode = mode

    def invoke(self, prompt):
        metrics.llm_calls += 1
        metrics.context_sizes.append(len(prompt))

        if self.mode == "orchestrator":
            from app.state.schemas import (
                OrchestratorOutput,
                EntitySpec,
                APIContract,
                FileLocations,
            )

            return OrchestratorOutput(
                entity_spec=EntitySpec(
                    entity_name="test", fields={}, validation_rules=[]
                ),
                crud_operations=["Create"],
                api_contract=APIContract(base_route="/ts", operations=[]),
                execution_order="backend_first",
                file_locations=FileLocations(),
            )
        elif self.mode == "backend":
            from app.state.schemas import GeneratedFiles, FileContent

            return GeneratedFiles(
                files=[FileContent(path="backend/package.json", content="{}")]
            )
        elif self.mode == "frontend":
            from app.state.schemas import GeneratedFiles, FileContent

            return GeneratedFiles(
                files=[FileContent(path="frontend/package.json", content="{}")]
            )
        elif self.mode == "repair":
            from app.state.schemas import RepairAnalysis, RepairAction

            return RepairAnalysis(
                analysis="test",
                changes=[
                    RepairAction(
                        file="backend/package.json", action="modify", content="{}"
                    )
                ],
            )
        elif self.mode == "enhancement":
            from app.state.schemas import EnhancementAnalysis, EnhancementAction

            return EnhancementAnalysis(
                analysis="test",
                changes=[
                    EnhancementAction(
                        file="backend/package.json", action="modify", content="{}"
                    )
                ],
            )


def run_benchmark(scenario_name, initial_state):
    print(f"\n========== RUNNING BENCHMARK: {scenario_name} ==========")
    global metrics
    metrics = BenchmarkMetrics()
    metrics.start_time = time.perf_counter()

    with patch(
        "app.agents.orchestrator.orchestrator_llm",
        MockLLM("orchestrator"),
    ), patch(
        "app.agents.backend_agent.backend_llm",
        MockLLM("backend"),
    ), patch(
        "app.agents.frontend_agent.frontend_llm",
        MockLLM("frontend"),
    ), patch(
        "app.agents.repair_agent.repair_llm",
        MockLLM("repair"),
    ), patch(
        "app.agents.repair_agent.enhancement_llm",
        MockLLM("enhancement"),
    ), patch(
        "app.agents.enhancement_agent.enhancement_llm",
        MockLLM("enhancement"),
    ), patch(
        "app.graph.nodes.execute_project",
        return_value={
            "success": False,
            "errors": ["Mocked backend startup failure to trigger repair loop!"],
        },
    ):

        # Avoid module reloading which corrupts Pydantic types crashing LangGraph
        from app.graph.builder import build_graph

        graph = build_graph()

        config = {"configurable": {"thread_id": "benchmark_123"}}

        # Run
        for step in graph.stream(initial_state, config=config):
            pass

        metrics.end_time = time.perf_counter()

    print(f"Total Workflow Time: {metrics.end_time - metrics.start_time:.3f}s")
    print(f"LLM Calls: {metrics.llm_calls}")
    if metrics.context_sizes:
        print(
            f"Avg Context Size: {sum(metrics.context_sizes)/len(metrics.context_sizes):.0f} chars"
        )

    print("\nNode Timings:")
    for node, times in metrics.node_times.items():
        print(f"  {node}: {sum(times):.3f}s (calls: {len(times)})")


def test_benchmark_pipeline_create():
    state_create = {
        "mode": "create",
        "raw_goal": "Create a dummy CRUD server",
        "target_project_path": "c:/Users/adhis/Desktop/langgraph-agent-journey/dummy_benchmark",
        "directory_listing": "",
    }
    run_benchmark("CREATE WORKFLOW", state_create)
    assert metrics.end_time > metrics.start_time
    assert metrics.llm_calls > 0
    assert (
        metrics.end_time - metrics.start_time < 5.0
    )  # Create shouldn't take more than 5s when mocked!


def test_benchmark_pipeline_enhance():
    state_enhance = {
        "mode": "enhance",
        "raw_goal": "Add caching",
        "target_project_path": "c:/Users/adhis/Desktop/langgraph-agent-journey/dummy_benchmark",
        "source_project_path": "c:/Users/adhis/Desktop/langgraph-agent-journey",  # Large project reference!
        "directory_listing": "",
    }
    run_benchmark("ENHANCE WORKFLOW (LARGE PROJECT)", state_enhance)
    assert metrics.end_time > metrics.start_time
    assert metrics.llm_calls > 0
    assert (
        metrics.end_time - metrics.start_time < 5.0
    )  # Even enhance shouldn't take > 5s thanks to workspace caching ignores!
