"""Agent-facing bench catalog.

Importing this package loads the public task list only.
Scoring is a separate entry point and is not imported here.
"""

from bench.catalog import agent_tasks

__all__ = ["agent_tasks"]
