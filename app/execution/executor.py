import os
import posixpath
from typing import Dict, Any

from app.execution.process_runner import run_cmd
from app.execution.smoke_test import run_server_smoke_test
from app.state.schemas import OrchestratorOutput, EntitySpec, APIContract


def execute_project(
    workspace_path: str, orchestrator_spec: OrchestratorOutput
) -> Dict[str, Any]:
    result = {
        "success": False,
        "frontend": None,
        "backend": None,
        "smoke_tests": [],
        "errors": [],
    }

    if not orchestrator_spec:
        orchestrator_spec = OrchestratorOutput(
            entity_spec=EntitySpec(entity_name="", fields={}),
            crud_operations=[],
            api_contract=APIContract(base_route="", operations=[]),
            execution_order="backend_first",
            file_locations={},
        )

    backend_root = orchestrator_spec.file_locations.get(
        "backend_root", "backend/"
    ).strip("/")
    frontend_root = orchestrator_spec.file_locations.get(
        "frontend_root", "frontend/"
    ).strip("/")

    backend_cwd = posixpath.join(workspace_path, backend_root)
    frontend_cwd = posixpath.join(workspace_path, frontend_root)

    # Execute Backend
    if os.path.exists(backend_cwd):
        print("  -> Installing Backend Dependencies...")
        install_res = run_cmd("npm install", backend_cwd, timeout=30)
        if not install_res["success"]:
            result["errors"].append(
                "Backend npm install failed: " + install_res["stderr"]
            )
            result["backend"] = install_res
            return result

        print("  -> Building Backend...")
        build_res = run_cmd("npm run build", backend_cwd, timeout=30)
        if not build_res["success"]:
            result["errors"].append(
                "Backend npm run build failed: " + build_res["stderr"]
            )
            result["backend"] = build_res
            return result

        print("  -> Smoke Testing Backend Startup and CRUD Integration...")
        start_res = run_server_smoke_test(
            ["npm", "start"],
            backend_cwd,
            api_contract=orchestrator_spec.api_contract,
            timeout=10,
        )

        if not start_res["success"]:
            err_msg = start_res.get("error", "Backend failed to start")
            result["errors"].append(f"{err_msg}: {start_res['stderr']}")
            result["backend"] = start_res
            return result

        result["backend"] = start_res

    # Execute Frontend
    if os.path.exists(frontend_cwd):
        print("  -> Installing Frontend Dependencies...")
        install_res = run_cmd("npm install", frontend_cwd, timeout=60)
        if not install_res["success"]:
            result["errors"].append(
                "Frontend npm install failed: " + install_res["stderr"]
            )
            result["frontend"] = install_res
            return result

        print("  -> Building Frontend...")
        build_res = run_cmd("npm run build", frontend_cwd, timeout=30)
        if not build_res["success"]:
            result["errors"].append(
                "Frontend npm run build failed: " + build_res["stderr"]
            )
            result["frontend"] = build_res
            return result

        result["frontend"] = build_res

    result["success"] = True
    return result
