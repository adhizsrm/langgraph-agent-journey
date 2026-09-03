import os
import shutil


def promote_workspace_to_target(workspace_path: str, target_path: str) -> dict:
    if os.path.exists(target_path):
        return {
            "error": f"Target path {target_path} already exists! Aborting promotion to avoid overwrite."
        }

    if not workspace_path or not os.path.exists(workspace_path):
        return {
            "error": f"Temporary workspace {workspace_path} not found! Cannot promote."
        }

    try:
        shutil.copytree(workspace_path, target_path)
    except Exception as e:
        return {"error": f"Failed to promote project: {str(e)}"}

    return {"written_files": [target_path], "workflow_status": "SUCCESS"}
