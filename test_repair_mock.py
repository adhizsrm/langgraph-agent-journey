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


def run_mock_test():
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
    f_files = updated_state["frontend_files"].files

    print(f"\nFinal length of Frontend Files: {len(f_files)}")
    print(f"Path stored in list: {f_files[0].path}")
    print(f"Content stored in list: {f_files[0].content[:80]}...\n")

    if (
        len(f_files) == 1
        and f_files[0].path == "frontend/package.json"
        and "react" in f_files[0].content
    ):
        print(
            "✅ SUCCESS! The file was correctly updated in-place and the path was successfully normalized without duplicates!"
        )
    else:
        print("❌ FAILED! A duplicate was generated or content was ignored.")


if __name__ == "__main__":
    run_mock_test()
