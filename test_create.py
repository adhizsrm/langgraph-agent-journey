from dotenv import load_dotenv

load_dotenv()
from app.graph.builder import build_graph


def main():
    app_graph = build_graph()
    initial_state = {
        "mode": "create",
        "raw_goal": "A note-taking app",
        "target_project_path": "./demo_target_project",
        "directory_listing": "",
        "source_project_path": None,
    }
    print("--- Invoking Create Mode ---")
    result = app_graph.invoke(initial_state, {"recursion_limit": 50})
    print("Workflow Status:", result.get("workflow_status"))


if __name__ == "__main__":
    main()
