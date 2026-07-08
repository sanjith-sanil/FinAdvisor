import asyncio
import json
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification


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

    async def publish_and_persist(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str,
        db: AsyncSession,
    ) -> None:
        """Publish a notification to the SSE stream AND persist it to the DB."""
        import uuid

        # Persist to DB
        notif = Notification(
            user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
            title=title,
            message=message,
            notification_type=notification_type,
        )
        db.add(notif)
        await db.commit()
        await db.refresh(notif)

        # Also push to real-time stream
        event_data = json.dumps({
            "id": str(notif.id),
            "title": title,
            "meta": message,
            "timestamp": notif.created_at.isoformat() if notif.created_at else None,
            "type": notification_type,
            "unread": True,
        })
        await self.publish(user_id if isinstance(user_id, str) else str(user_id), event_data)

    async def stream(self, user_id: str) -> AsyncIterator[str]:
        queue = self.get_queue(user_id)
        while True:
            message = await queue.get()
            yield message


notification_hub = NotificationHub()
