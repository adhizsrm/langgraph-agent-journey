import os
import sys
import shutil
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
from app.graph.builder import build_graph


def scaffold_demo():
    shutil.rmtree("./demo_target_project", ignore_errors=True)
    os.makedirs("./demo_target_project/frontend/src", exist_ok=True)

    with open("./demo_target_project/frontend/package.json", "w") as f:
        f.write(
            '{"name":"frontend","scripts":{"dev":"vite","build":"vite build"},"dependencies":{"react":"^18.2.0","react-dom":"^18.2.0"},"devDependencies":{"vite":"^5.0.0","@vitejs/plugin-react":"^4.0.0"}}'
        )

    with open("./demo_target_project/frontend/index.html", "w") as f:
        f.write('<script type="module" src="/src/main.jsx"></script>')

    with open("./demo_target_project/frontend/src/main.jsx", "w") as f:
        f.write(
            "import { createRoot } from 'react-dom/client';\nimport App from './App';\nimport './index.css';\ncreateRoot(document.getElementById('root')).render(<App />);"
        )

    with open("./demo_target_project/frontend/src/App.jsx", "w") as f:
        f.write(
            "export default function App() { return <div><h1>Notes App</h1></div>; }"
        )

    with open("./demo_target_project/frontend/src/index.css", "w") as f:
        f.write("body { background: white; color: black; }")


def main():
    scaffold_demo()

    app_graph = build_graph()
    initial_state = {
        "mode": "enhance",
        "raw_goal": "Add dark mode",
        "target_project_path": "./demo_target_project_enhanced",
        "source_project_path": "./demo_target_project",
        "directory_listing": "",
    }
    print("--- Invoking Enhance Mode ---")

    result = app_graph.invoke(initial_state, {"recursion_limit": 50})

    print("\n\n--- RESULTS ---")
    if "safety_errors" in result and result["safety_errors"]:
        print("Safety Errors:", result["safety_errors"])
    if "validation_errors" in result and result["validation_errors"]:
        print("Validation Errors:", result["validation_errors"])
    print("Workflow Status:", result.get("workflow_status"))


if __name__ == "__main__":
    main()
