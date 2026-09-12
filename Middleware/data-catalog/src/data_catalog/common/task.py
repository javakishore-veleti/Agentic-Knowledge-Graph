"""Task and workflow machinery. Concrete tasks live in `tasks/`, workflows in `wf/`.

A service does not implement a use case as one long method. It looks up a workflow -- an
ordered list of tasks -- and runs it against the Ctx. Each task performs one step, reads
what earlier tasks left on the Ctx, and leaves its own result there.

The point is not decomposition for its own sake: every step is named, timed and
individually skippable, so "which step was slow" and "how far did it get before failing"
are answerable from the Ctx alone.

Tasks and workflows are singletons and hold no request state. A task's `execute` receives
everything it needs on the Ctx and writes everything it produces back to the Ctx.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from .context import BaseCtx, TaskRecord
from .errors import ServiceError


class ITask(ABC):
    """One step of a use case. Stateless and shared; never store per-call data on self."""

    #: Appears in the task trail and logs. Defaults to the class name.
    name: str = ""

    def task_name(self) -> str:
        return self.name or type(self).__name__

    def should_run(self, ctx: BaseCtx) -> bool:
        """A conditional step declares its condition here rather than opening with an
        `if`, which would make the trail claim the task ran when it did nothing."""
        return True

    @abstractmethod
    def execute(self, ctx: BaseCtx) -> None:
        """Read from and write to the Ctx. Returns nothing: the Ctx is the channel."""


class IWorkflow(ABC):
    """An ordered set of tasks for one use case."""

    name: str = ""

    def wf_name(self) -> str:
        return self.name or type(self).__name__

    @abstractmethod
    def tasks(self) -> tuple[ITask, ...]:
        """The steps, in order. Returns a tuple because the sequence is wiring, not
        state: nothing may append to it at runtime."""

    def run(self, ctx: BaseCtx) -> BaseCtx:
        """Run every task in order, recording each on the Ctx.

        Stops at the first failure, leaving the trail intact up to the failing task --
        which is what makes the failure attributable.
        """
        for task in self.tasks():
            record = TaskRecord(name=task.task_name(), started_at=datetime.now(UTC))
            ctx.tasks.append(record)

            if not task.should_run(ctx):
                record.skipped = True
                record.finished_at = datetime.now(UTC)
                continue

            try:
                task.execute(ctx)
            except ServiceError:
                record.error = "service_error"
                record.finished_at = datetime.now(UTC)
                raise
            except Exception as exc:
                record.error = type(exc).__name__
                record.finished_at = datetime.now(UTC)
                raise ServiceError(
                    code="task_failed",
                    message=f"task {record.name} failed in workflow {self.wf_name()}",
                    trace_id=ctx.trace_id,
                ) from exc

            record.finished_at = datetime.now(UTC)
        return ctx

    def __repr__(self) -> str:
        return f"{self.wf_name()}({' -> '.join(t.task_name() for t in self.tasks())})"
