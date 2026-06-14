"""Resolves foreign-key dependencies and determines safe migration order."""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Set, Tuple

from sqlalchemy.engine import Engine

from core.schema_engine import SchemaEngine


class DependencyResolver:
    """Builds FK graphs, expands table sets, and produces migration order."""

    @staticmethod
    def get_dependencies(engine: Engine, table: str) -> Set[str]:
        """Return tables that must be migrated before ``table``."""
        deps: Set[str] = set()
        for fk in SchemaEngine.get_foreign_keys(engine, table):
            referred = fk.get("referred_table")
            if referred and referred != table:
                deps.add(referred)
        return deps

    @classmethod
    def build_graph(
        cls, engine: Engine, tables: List[str]
    ) -> Dict[str, Set[str]]:
        """Map each table to the set of tables it directly depends on."""
        table_set = set(tables)
        graph: Dict[str, Set[str]] = {t: set() for t in tables}

        for table in tables:
            for dep in cls.get_dependencies(engine, table):
                if dep in table_set:
                    graph[table].add(dep)
        return graph

    @classmethod
    def expand_with_dependencies(
        cls, engine: Engine, selected: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Include referenced parent tables not explicitly selected.

        Returns (expanded_table_list, auto_added_tables).
        """
        all_tables = set(SchemaEngine.get_tables(engine))
        expanded: Set[str] = set(selected)
        queue = deque(selected)
        auto_added: List[str] = []

        while queue:
            table = queue.popleft()
            for dep in cls.get_dependencies(engine, table):
                if dep not in all_tables:
                    continue
                if dep not in expanded:
                    expanded.add(dep)
                    auto_added.append(dep)
                    queue.append(dep)

        ordered = cls.sort_tables(engine, list(expanded))
        return ordered, auto_added

    @classmethod
    def sort_tables(cls, engine: Engine, tables: List[str]) -> List[str]:
        """
        Topologically sort tables so parents migrate before children.

        Tables in circular dependency groups keep a stable relative order.
        """
        if not tables:
            return []

        graph = cls.build_graph(engine, tables)
        in_degree = {t: len(graph[t]) for t in tables}
        queue = deque(sorted(t for t in tables if in_degree[t] == 0))
        sorted_tables: List[str] = []

        while queue:
            node = queue.popleft()
            sorted_tables.append(node)
            for child in tables:
                if node in graph.get(child, set()):
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        queue.append(child)

        if len(sorted_tables) < len(tables):
            remaining = [t for t in tables if t not in sorted_tables]
            sorted_tables.extend(sorted(remaining))

        return sorted_tables

    @classmethod
    def has_circular_dependencies(cls, engine: Engine, tables: List[str]) -> bool:
        """Return True if any FK cycle exists within the table set."""
        graph = cls.build_graph(engine, tables)
        in_degree = {t: len(graph[t]) for t in tables}
        queue = deque(t for t in tables if in_degree[t] == 0)
        visited = 0

        while queue:
            node = queue.popleft()
            visited += 1
            for child in tables:
                if node in graph.get(child, set()):
                    in_degree[child] -= 1
                    if in_degree[child] == 0:
                        queue.append(child)

        return visited < len(tables)

    @classmethod
    def validate_selection(
        cls, engine: Engine, selected: List[str]
    ) -> Dict[str, object]:
        """Summarize dependency info for the UI."""
        expanded, auto_added = cls.expand_with_dependencies(engine, selected)
        has_cycles = cls.has_circular_dependencies(engine, expanded)
        return {
            "selected": selected,
            "expanded": expanded,
            "auto_added": auto_added,
            "has_cycles": has_cycles,
            "order": expanded,
        }
