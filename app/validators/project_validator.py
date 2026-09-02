from typing import List, Dict, Any
from app.state.schemas import FileContent
from app.validators.package_validator import (
    validate_backend_package,
    validate_frontend_package,
)
from app.validators.import_validator import validate_local_imports
from app.validators.export_validator import validate_cross_file_symbols


def validate_project(
    b_files: List[FileContent], f_files: List[FileContent]
) -> Dict[str, Any]:
    errors = []

    # -- 1. Backend Validation --
    errors.extend(validate_backend_package(b_files))

    # -- 2. Frontend Validation --
    errors.extend(validate_frontend_package(f_files))

    # -- 3. Generic Local-Import Validation --
    errors.extend(validate_local_imports(b_files, "Backend"))
    errors.extend(validate_local_imports(f_files, "Frontend"))
    errors.extend(validate_cross_file_symbols(b_files, "Backend"))
    errors.extend(validate_cross_file_symbols(f_files, "Frontend"))

    if errors:
        return {
            "validation_errors": errors,
            "error": "VALIDATION FAILED\n" + "\n - ".join(errors),
        }

    return {"validation_errors": []}
