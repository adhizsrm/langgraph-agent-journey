import os
import json
from unittest.mock import patch
from app.state.schemas import FileContent, GeneratedFiles
from app.validators.import_validator import validate_local_imports
from app.validators.topology_validator import validate_topology

print("\n=== STARTING BACKEND REGRESSION TESTS ===")

# ====== Test 1: Backend import validation ======
file1 = FileContent(path="backend/src/index.js", content="require('./routes/task')\n")
file2 = FileContent(path="backend/routes/task.js", content="module.exports = {};\n")

print("\n--- Test 1a: Invalid relative import (should report unresolved) ---")
errs_invalid = validate_local_imports([file1, file2], "Backend")
print(f"Errors: {errs_invalid}")
assert len(errs_invalid) == 1
assert "unresolved local import" in errs_invalid[0]

print("\n--- Test 1b: Valid relative import (should pass) ---")
file1_valid = FileContent(
    path="backend/src/index.js", content="require('../routes/task')\n"
)
errs_valid = validate_local_imports([file1_valid, file2], "Backend")
print(f"Errors: {errs_valid}")
assert len(errs_valid) == 0

# ====== Test 2: Duplicate topology file ======
print("\n--- Test 2: Duplicate topology file ---")
# To test topology, we must write the dummy files to a temp workspace since topology reads disk.
import tempfile
import shutil

temp_ws = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(temp_ws, "backend/src"))
    os.makedirs(os.path.join(temp_ws, "backend/routes"))
    os.makedirs(os.path.join(temp_ws, "backend/controllers"))
    os.makedirs(os.path.join(temp_ws, "backend/services"))

    with open(os.path.join(temp_ws, "backend/package.json"), "w") as f:
        f.write(json.dumps({"main": "src/index.js"}))
    with open(os.path.join(temp_ws, "backend/src/index.js"), "w") as f:
        f.write("require('../routes/task');")
    with open(os.path.join(temp_ws, "backend/routes/task.js"), "w") as f:
        f.write("require('../controllers/taskController');")
    with open(os.path.join(temp_ws, "backend/controllers/taskController.js"), "w") as f:
        f.write("require('../services/taskService');")
    with open(os.path.join(temp_ws, "backend/services/taskService.js"), "w") as f:
        f.write("module.exports = {};")

    # Duplicate file
    with open(os.path.join(temp_ws, "backend/controllers/task.js"), "w") as f:
        f.write("module.exports = {};")

    topo_errs = validate_topology(temp_ws)
    print(f"Topology Errors: {topo_errs}")
    assert len(topo_errs) == 1
    assert "backend/controllers/task.js" in topo_errs[0]
finally:
    shutil.rmtree(temp_ws)

# ====== Test 3: Repair delete ======
print("\n--- Test 3: Repair Delete ---")
from pydantic import BaseModel


class MockAction(BaseModel):
    file: str
    action: str
    content: str


class MockResult(BaseModel):
    analysis: str
    changes: list[MockAction]


def mock_repair_invoke(*args, **kwargs):
    return MockResult(
        analysis="Duplicate file spotted",
        changes=[
            MockAction(file="backend/controllers/task.js", action="delete", content="")
        ],
    )


with patch("app.agents.repair_agent.repair_llm.invoke", side_effect=mock_repair_invoke):
    from app.agents.repair_agent import project_repair_node

    mock_state = {
        "mode": "create",
        "repair_attempts": 1,
        "backend_files": GeneratedFiles(
            files=[
                FileContent(path="backend/src/index.js", content=""),
                FileContent(path="backend/controllers/task.js", content="DUPLICATE"),
            ]
        ),
        "frontend_files": GeneratedFiles(files=[]),
        "validation_errors": [
            "Topological Disconnect: backend/controllers/task.js is never imported"
        ],
    }
    updated_state = project_repair_node(mock_state)
    b_files = updated_state["backend_files"].files
    print(f"Files after repair delete: {[f.path for f in b_files]}")
    assert len(b_files) == 1
    assert b_files[0].path == "backend/src/index.js"

print("\n--- Test 4: Generated backend architecture (validates correctly) ---")
# Repeat Test 2 but without the duplicate, ensuring it completely passes
temp_ws_valid = tempfile.mkdtemp()
try:
    os.makedirs(os.path.join(temp_ws_valid, "backend/src"))
    os.makedirs(os.path.join(temp_ws_valid, "backend/routes"))
    os.makedirs(os.path.join(temp_ws_valid, "backend/controllers"))
    os.makedirs(os.path.join(temp_ws_valid, "backend/services"))

    with open(os.path.join(temp_ws_valid, "backend/package.json"), "w") as f:
        f.write(json.dumps({"main": "src/index.js"}))
    with open(os.path.join(temp_ws_valid, "backend/src/index.js"), "w") as f:
        f.write("require('../routes/task');")
    with open(os.path.join(temp_ws_valid, "backend/routes/task.js"), "w") as f:
        f.write("require('../controllers/taskController');")
    with open(
        os.path.join(temp_ws_valid, "backend/controllers/taskController.js"), "w"
    ) as f:
        f.write("require('../services/taskService');")
    with open(os.path.join(temp_ws_valid, "backend/services/taskService.js"), "w") as f:
        f.write("module.exports = {};")

    import_errs = validate_local_imports(
        [
            FileContent(
                path="backend/src/index.js", content="require('../routes/task');"
            ),
            FileContent(
                path="backend/routes/task.js",
                content="require('../controllers/taskController');",
            ),
            FileContent(
                path="backend/controllers/taskController.js",
                content="require('../services/taskService');",
            ),
            FileContent(path="backend/services/taskService.js", content=""),
        ],
        "Backend",
    )
    topo_errs = validate_topology(temp_ws_valid)
    print(f"Local Import Errors: {import_errs}")
    print(f"Topology Errors: {topo_errs}")
    assert len(import_errs) == 0
    assert len(topo_errs) == 0
finally:
    shutil.rmtree(temp_ws_valid)

print("\n[SUCCESS]: All tests passed!")
