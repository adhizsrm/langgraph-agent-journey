import os
import sys
import sqlite3
import hashlib
from langgraph.checkpoint.sqlite import SqliteSaver

sys.stdout.reconfigure(encoding="utf-8")
from app.utils.directory import get_actual_directory_listing
from app.graph.builder import build_graph
from app.telemetry import telemetry_tracker
from app.agents.llm import provider, llm


def main():
    conn = sqlite3.connect("checkpoints.sqlite", check_same_thread=False)
    memory = SqliteSaver(conn)
    app_graph = build_graph(checkpointer=memory)
    print("--- Starting Production CRUD Code Generator (Modularized) ---")

    while True:
        try:
            print("\n" + "=" * 50)
            mode_choice = input(
                "[1] Create New Project\n[2] Enhance Existing Project\n[q] Quit\nSelect mode: "
            ).strip()

            if mode_choice.lower() in ["q", "quit", "exit"]:
                print("Exiting...")
                break

            if mode_choice not in ["1", "2"]:
                continue

            if mode_choice == "1":
                goal = input("\nEnter your goal for the new CRUD entity: ").strip()
                if not goal:
                    continue
                mode = "create"
                source_path = None
            else:
                goal = input(
                    "\nEnter your enhancement request (e.g. 'Add dark mode'): "
                ).strip()
                if not goal:
                    continue
                source_path = input(
                    "Enter path to existing project exactly to enhance: "
                ).strip()
                if not os.path.exists(source_path):
                    print("Source path does not exist.")
                    continue
                mode = "enhance"

            base_dir = (
                "demo_target_project"
                if mode == "create"
                else f"{os.path.basename(source_path.strip('/\\'))}_enhanced"
            )

            target_path = base_dir
            counter = 2
            while os.path.exists(target_path):
                target_path = f"{base_dir}_{counter}"
                counter += 1

            print(f"\n=> Target directory calculated as: {target_path}")

            thread_string = f"{mode}:{goal}:{source_path}".strip().lower()
            thread_id = hashlib.md5(thread_string.encode()).hexdigest()
            config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}

            checkpoint = memory.get_tuple(config)

            model_name = getattr(llm, "model", getattr(llm, "model_name", "unknown"))
            telemetry_tracker.start_run(
                run_id=thread_id,
                mode=mode,
                goal=goal,
                provider=provider,
                model=model_name,
            )

            if checkpoint:
                print(
                    f"--- Found suspended execution state. Resuming Workflow for '{goal}' ---"
                )
                result = app_graph.invoke(None, config)
            else:
                initial_state = {
                    "mode": mode,
                    "raw_goal": goal,
                    "target_project_path": f"./{target_path}",
                    "directory_listing": get_actual_directory_listing(target_path),
                    "source_project_path": source_path,
                }
                print(f"--- Generating Workflow for '{goal}' ---")
                result = app_graph.invoke(initial_state, config)

            status = "failed" if result.get("error") else "success"
            telemetry_tracker.capture_workflow_state(result, status)
            telemetry_tracker.save()

            if result.get("error"):
                print(f"--- FAILED ---")
                print(result["error"])
                if result.get("conflicts"):
                    print(f"Conflicts: {result['conflicts']}")
                print(
                    "Generated files preserved in memory for manual review, writing bypassed physically."
                )
            else:
                print("--- VALIDATION PASSED ---")
                print("--- SUCCESS File writing completed! ---")
                for f in result.get("written_files", []):
                    print(f" - {f}")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError occurred: {str(e)}")


if __name__ == "__main__":
    main()
