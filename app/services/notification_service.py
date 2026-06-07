import asyncio
from collections.abc import AsyncIterator


class NotificationHub:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[str]] = {}

    def get_queue(self, user_id: str) -> asyncio.Queue[str]:
        if user_id not in self._queues:
            self._queues[user_id] = asyncio.Queue()
        return self._queues[user_id]

    async def publish(self, user_id: str, message: str) -> None:
        queue = self.get_queue(user_id)
        await queue.put(message)

    async def stream(self, user_id: str) -> AsyncIterator[str]:
        queue = self.get_queue(user_id)
        while True:
            message = await queue.get()
            yield message


notification_hub = NotificationHub()
