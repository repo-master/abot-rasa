
import logging
from typing import Any, Dict

import rasa
import rasa.utils.endpoints
from rasa.core.channels.channel import UserMessage, OutputChannel
from rasa.core.channels.rest import (CollectingOutputChannel,
                                     QueueOutputChannel, RestInput)

logger = logging.getLogger(__name__)


# Monkey patch

def monkey_patch():
    def patch_collecting_output_channel():
        async def _fixed_send_response(self, recipient_id: str, message: Dict[str, Any]) -> None:
            await self._persist_message(
                self._message(recipient_id, **message)
            )

        old__message = getattr(CollectingOutputChannel, "_message")
        @staticmethod
        def _fixed_message(
            recipient_id,
            text = None,
            image = None,
            buttons = None,
            attachment = None,
            custom = None,
            **kwargs
        ):
            # We ignore metadata sent, as that is not needed (in kwargs)
            return old__message(recipient_id, text, image, buttons, attachment, custom)
        setattr(CollectingOutputChannel, "send_response", _fixed_send_response)
        setattr(CollectingOutputChannel, "_message", _fixed_message)

    logger.info("Monkey-patching Rasa components...")
    patch_collecting_output_channel()

if not hasattr(rasa, "_is_fixed_abot"):
    monkey_patch()
    setattr(rasa, '_is_fixed_abot', True)

__all__ = [
    'monkey_patch'
]
