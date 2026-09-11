import pytest
from pydantic import ValidationError
from app.state.schemas import RepairAnalysis


def test_valid_repair_analysis():
    """Verify that a valid RepairAnalysis payload is accepted payload."""
    valid_payload = {
        "analysis": "Found a missing start script.",
        "changes": [
            {
                "file": "backend/package.json",
                "action": "modify",
                "content": '{\n  "name": "backend",\n  "scripts": {"start": "node index.js"}\n}',
            }
        ],
    }

    # Validation should succeed without raising any exception
    RepairAnalysis.model_validate(valid_payload)


def test_malformed_changes_item_rejected():
    """Verify that the malformed production payload is rejected by pydantic."""
    invalid_payload = {
        "analysis": "The dependencies object needs fixing.",
        "changes": [
            'dependencies": {\n    "express": "^4.18.2",\n    "cors": "^2.8.5"\n  }}'
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        RepairAnalysis.model_validate(invalid_payload)

    # Verify the structure of the error matches expected bounds
    assert "Input should be a valid dictionary or instance of RepairAction" in str(
        exc_info.value
    )
