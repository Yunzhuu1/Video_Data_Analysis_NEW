from copy import deepcopy

from app.graph.state import DataAgentState


class InMemoryCheckpointStore:
    """Demo checkpoint store for human approval waits.

    This is intentionally process-local. The platform docs call out SQLite/Postgres as the next
    production step; the first slice proves the resume contract without adding infrastructure.
    """

    def __init__(self) -> None:
        self._states: dict[str, DataAgentState] = {}

    def save(self, run_id: str, state: DataAgentState) -> None:
        self._states[run_id] = deepcopy(state)

    def get(self, run_id: str) -> DataAgentState | None:
        state = self._states.get(run_id)
        return deepcopy(state) if state is not None else None

    def delete(self, run_id: str) -> None:
        self._states.pop(run_id, None)


checkpoint_store = InMemoryCheckpointStore()
