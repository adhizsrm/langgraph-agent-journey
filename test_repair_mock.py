import json
from unittest.mock import patch
from pydantic import BaseModel


# Mock objects to mimic the Structured LLM output exactly
class MockAction(BaseModel):
    file: str
    action: str
    content: str


class MockResult(BaseModel):
    analysis: str
    changes: list[MockAction]


# Mock the repair_llm invoke method
def mock_invoke(*args, **kwargs):
    # This precisely mimics the LLaMa/Mistral behavior that originally broke the logic!
    # It outputs the path with a 'frontend/' prefix while the original state has 'package.json'
    return MockResult(
        analysis="Mocked repair to fix package.json paths without spending LLM tokens.",
        changes=[
            MockAction(
                file="frontend/package.json",
                action="modify",
                content=json.dumps(
                    {
                        "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
                        "devDependencies": {
                            "vite": "^5.0.0",
                            "@vitejs/plugin-react": "^4.0.0",
                        },
                        "scripts": {"dev": "vite"},
                    }
                ),
            )
        ],
    )


def test_run_mock_test():
    # Import locally to apply the patch before the module fully initializes LLM bindings
    from app.state.schemas import FileContent, GeneratedFiles

    # 1. State setup mimicking the Broken Phase
    initial_broken_package = json.dumps(
        {"dependencies": {}, "devDependencies": {}, "scripts": {}}
    )

    # Notice the path is 'package.json', missing the 'frontend/' prefix as it did originally!
    mock_state = {
        "mode": "create",
        "repair_attempts": 1,
        "backend_files": GeneratedFiles(files=[]),
        "frontend_files": GeneratedFiles(
            files=[FileContent(path="package.json", content=initial_broken_package)]
        ),
        "validation_errors": ["Frontend missing 'react' in dependencies"],
    }

    # 2. Patch the LLM and run the repair loop Node directly!
    with patch("app.agents.repair_agent.repair_llm.invoke", side_effect=mock_invoke):
        from app.agents.repair_agent import project_repair_node

        print("\n=== STARTING MOCK REPAIR LLM ===")
        updated_state = project_repair_node(mock_state)

    # 3. Assert the results cleanly
    patches = updated_state.get("pending_patches", [])

    print(f"\nFinal length of Pending Patches: {len(patches)}")
    if patches:
        print(f"Path stored in pending patch: {patches[0]['file']}")
        print(f"Content stored in pending patch: {patches[0]['content'][:80]}...\n")

    assert len(patches) == 1
    assert patches[0]["file"] == "frontend/package.json"
    assert "react" in patches[0]["content"]


if __name__ == "__main__":
    test_run_mock_test()
