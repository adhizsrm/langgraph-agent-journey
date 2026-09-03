import os
from typing import List, Dict


def chunk_files(base_dir: str, file_paths: List[str]) -> List[Dict[str, str]]:
    chunks = []
    for fp in file_paths:
        full_path = os.path.join(base_dir, fp)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Generic windowed chunker defaults mapped to passing whole clean files given current context limits
            chunks.append({"file": fp, "content": content})
        except Exception as e:
            chunks.append({"file": fp, "error": str(e)})

    return chunks
