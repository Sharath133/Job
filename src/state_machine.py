from __future__ import annotations

from src.models import JobExecutionContext, JobState


class StateMachine:
    """Encapsulates legal state transitions for job processing."""

    _allowed: dict[JobState, set[JobState]] = {
        JobState.INGESTED: {JobState.DEDUPED},
        JobState.DEDUPED: {JobState.SCORED},
        JobState.SCORED: {JobState.LEAD_SOURCED, JobState.FINALIZED},
        JobState.LEAD_SOURCED: {JobState.DRAFTED},
        JobState.DRAFTED: {JobState.EXECUTED},
        JobState.EXECUTED: {JobState.FINALIZED},
        JobState.FINALIZED: set(),
    }

    @staticmethod
    def transition(context: JobExecutionContext, next_state: JobState) -> None:
        if next_state not in StateMachine._allowed[context.state]:
            raise ValueError(f"Invalid transition from {context.state} to {next_state}")
        context.state = next_state
