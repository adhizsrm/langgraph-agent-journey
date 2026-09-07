import os
from typing import List, Dict


def chunk_files(base_dir: str, file_paths: List[str]) -> List[Dict[str, str]]:
    chunks = []

    char_limit = (
        120000  # Guard bounds ensuring Prompts stay natively under ~30,000 tokens
    )
    current_chars = 0

    # Stratified ranking pushing core routing files natively to the API over extraneous utils
    def priority(fp):
        lower_fp = fp.lower()
        if "app" in lower_fp or "index" in lower_fp or "main" in lower_fp:
            return 0
        if "config" in lower_fp or "package.json" in lower_fp:
            return 1
        return 2

    sorted_paths = sorted(file_paths, key=priority)

    for fp in sorted_paths:
        full_path = os.path.join(base_dir, fp)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Block single-file bloat natively over extreme architectures
            if len(content) > 40000:
                content = (
                    content[:15000]
                    + "\n...[CONTENT OMITTED FOR TOKEN SCALE RESTRICTIONS]...\n"
                    + content[-15000:]
                )

            added_len = len(fp) + len(content)

            if current_chars + added_len > char_limit:
                chunks.append(
                    {
                        "file": fp,
                        "error": "[FILE CONTENTS OMITTED AVOIDING CONTEXT WINDOW LIMITS]",
                    }
                )
                continue

            chunks.append({"file": fp, "content": content})
            current_chars += added_len

        except Exception as e:
            chunks.append({"file": fp, "error": str(e)})

    return chunks
