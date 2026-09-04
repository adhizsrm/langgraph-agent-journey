from dotenv import load_dotenv

load_dotenv()

import os
import json
from app.graph.builder import build_graph
from app.utils.directory import get_actual_directory_listing


def main():
    app_graph = build_graph()

    source_path = "c:/Users/adhis/Desktop/langgraph-agent-journey/demo_target_project"
    if not os.path.exists(source_path):
        print(f"FAILED: Source project '{source_path}' does not exist.")
        return

    # Simulate enhancement mode payload
    initial_state = {
        "mode": "enhance",
        "raw_goal": "Add dark mode",
        "target_project_path": "./demo_target_project_enhanced",
        "directory_listing": get_actual_directory_listing("demo_target_project"),
        "source_project_path": source_path,
    }

    try:
        print("--- Invoking Enhancement Mode Test ---")
        result = app_graph.invoke(initial_state, {"recursion_limit": 50})

        if result.get("error"):
            print("TEST FAILED WITH ERROR:")
            print(result["error"])
        else:
            print("TEST PASSED!")
            print("Written files:")
            for f in result.get("written_files", []):
                print(f" - {f}")
            print(f"Workflow Status: {result.get('workflow_status')}")
    except Exception as e:
        print(f"CRITICAL TEST FATAL: {str(e)}")


if __name__ == "__main__":
    main()
