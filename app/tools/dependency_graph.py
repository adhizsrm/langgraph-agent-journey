from collections import defaultdict
from typing import List, Set
import os


class DependencyGraph:
    def __init__(self):
        self.forward = defaultdict(set)
        self.reverse = defaultdict(set)
        self.nodes = set()

    def add_edge(self, source: str, target: str):
        self.forward[source].add(target)
        self.reverse[target].add(source)
        self.nodes.add(source)
        self.nodes.add(target)

    def get_forward_dependencies(self, seeds: Set[str], max_depth: int = 2) -> Set[str]:
        return self._traverse(seeds, self.forward, max_depth)

    def get_reverse_dependencies(self, seeds: Set[str], max_depth: int = 2) -> Set[str]:
        return self._traverse(seeds, self.reverse, max_depth)

    def _traverse(self, seeds: Set[str], graph: dict, max_depth: int) -> Set[str]:
        visited = set(seeds)
        current_level = set(seeds)

        for _ in range(max_depth):
            next_level = set()
            for node in current_level:
                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
            current_level = next_level

        return visited


def build_repository_dependency_graph(
    file_paths: List[str], base_dir: str, file_contents: dict
) -> DependencyGraph:
    """Builds a deterministic in-memory representation of local structural dependencies natively."""
    from app.tools.ast_parser import extract_local_imports

    graph = DependencyGraph()
    for rel_path in file_paths:
        graph.nodes.add(rel_path)
        content = file_contents.get(rel_path, "")
        if content:
            valid_imports = extract_local_imports(
                os.path.join(base_dir, rel_path),
                content,
                base_dir,
                file_map=file_contents,
            )
            for imp in valid_imports:
                graph.add_edge(rel_path, imp)

    return graph
