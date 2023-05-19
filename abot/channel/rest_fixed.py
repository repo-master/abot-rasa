
from asyncio import Queue
from typing import Any, Awaitable, Callable, Dict, Optional

from rasa.core.channels.channel import UserMessage
from rasa.core.channels.rest import QueueOutputChannel, RestInput


class RestInputFixed(RestInput):
    # Override
    @staticmethod
    async def on_message_wrapper(
        on_new_message: Callable[[UserMessage], Awaitable[Any]],
        text: str,
        queue: Queue,
        sender_id: str,
        input_channel: str,
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        collector = QueueOutputChannelFixed(queue)

        message = UserMessage(
            text, collector, sender_id, input_channel=input_channel, metadata=metadata
        )
        await on_new_message(message)

        await queue.put("DONE")


class QueueOutputChannelFixed(QueueOutputChannel):
    # Override from `OutputChannel`
    async def send_response(self, recipient_id: str, message: Dict[str, Any]) -> None:
        await self._persist_message(self._message(recipient_id, **message))
