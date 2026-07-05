from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

logger = logging.getLogger("wa-system.cooldown")

SendCallback = Callable[[str, str], Awaitable[None]]


class ReplyCooldown:
    """Debounce automatic replies independently for each recipient.

    When several messages arrive from the same recipient before the delay ends,
    the previous pending reply is cancelled and replaced by the latest one.
    This prevents simultaneous or chained replies to the same conversation.
    """

    def __init__(self, minimum_seconds: float = 16.0, maximum_seconds: float = 20.0):
        if minimum_seconds < 0 or maximum_seconds < minimum_seconds:
            raise ValueError("Invalid cooldown range")
        self.minimum_seconds = minimum_seconds
        self.maximum_seconds = maximum_seconds
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def schedule(
        self,
        recipient: str,
        message: str,
        send_callback: SendCallback,
    ) -> None:
        previous = self._tasks.get(recipient)
        if previous and not previous.done():
            previous.cancel()

        task = asyncio.create_task(
            self._wait_and_send(recipient, message, send_callback),
            name=f"wa-reply-{recipient[-4:]}",
        )
        self._tasks[recipient] = task
        task.add_done_callback(lambda finished: self._cleanup(recipient, finished))

    async def _wait_and_send(
        self,
        recipient: str,
        message: str,
        send_callback: SendCallback,
    ) -> None:
        delay = random.uniform(self.minimum_seconds, self.maximum_seconds)
        try:
            await asyncio.sleep(delay)
            lock = self._locks.setdefault(recipient, asyncio.Lock())
            async with lock:
                await send_callback(recipient, message)
        except asyncio.CancelledError:
            logger.info("Replaced pending reply for recipient ending %s", recipient[-4:])
            raise

    def _cleanup(self, recipient: str, task: asyncio.Task[None]) -> None:
        current = self._tasks.get(recipient)
        if current is task:
            self._tasks.pop(recipient, None)

        if task.cancelled():
            return
        error = task.exception()
        if error:
            logger.exception("Scheduled reply failed", exc_info=error)

    async def shutdown(self) -> None:
        tasks = [task for task in self._tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
