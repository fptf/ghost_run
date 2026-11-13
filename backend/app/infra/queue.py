"""Постановка фоновых задач. В тестах подменяется синхронной реализацией."""

import uuid
from typing import Protocol


class TaskQueue(Protocol):
    def process_track(self, track_id: uuid.UUID) -> None: ...

    def recompute_visibility(self, user_id: uuid.UUID) -> None: ...


class CeleryQueue:
    def process_track(self, track_id: uuid.UUID) -> None:
        from app.infra.tasks import process_track_task

        process_track_task.delay(str(track_id))

    def recompute_visibility(self, user_id: uuid.UUID) -> None:
        from app.infra.tasks import recompute_visibility_task

        recompute_visibility_task.delay(str(user_id))


def get_queue() -> TaskQueue:
    return CeleryQueue()
