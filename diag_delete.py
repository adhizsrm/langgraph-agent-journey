import json
from unittest.mock import patch
from app.agents.repair_agent import project_repair_node
from app.graph.safety_node import project_safety_node
from app.state.schemas import FileContent, GeneratedFiles
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

    with open("results.json", "w") as f:
        repaired_state = project_repair_node(mock_state)
        f.write(
            json.dumps({"pending_patches": repaired_state.get("pending_patches", [])})
            + "\n"
        )

        mock_state.update(repaired_state)
        safety_state = project_safety_node(mock_state)
        files = (
            [
                x.path
                for x in safety_state.get(
                    "backend_files", GeneratedFiles(files=[])
                ).files
            ]
            if safety_state.get("backend_files")
            else "N/A"
        )
        f.write(json.dumps({"files": files}) + "\n")
