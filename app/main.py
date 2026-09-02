import os
from app.utils.directory import get_actual_directory_listing
from app.graph.builder import build_graph


def main():
    app_graph = build_graph()
    print("--- Starting Production CRUD Code Generator (Modularized) ---")

    while True:
        try:
            goal = input(
                "\nEnter your goal for the new CRUD entity (or type 'exit' to quit): "
            ).strip()
            if not goal:
                continue
            if goal.lower() in ["exit", "quit"]:
                print("Exiting...")
                break

            base_dir = "demo_target_project"
            target_path = base_dir
            counter = 2
            while os.path.exists(target_path):
                target_path = f"{base_dir}_{counter}"
                counter += 1

            print(f"\n=> Target directory calculated as: {target_path}")

            initial_state = {
                "raw_goal": goal,
                "target_project_path": f"./{target_path}",
                "directory_listing": get_actual_directory_listing(target_path),
            }

            print(f"--- Generating CRUD generation for '{goal}' ---")
            result = app_graph.invoke(initial_state, {"recursion_limit": 50})

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
