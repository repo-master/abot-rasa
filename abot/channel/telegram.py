
import base64
import io
import urllib.parse
import logging
from asyncio import AbstractEventLoop, Task
from typing import Any, Awaitable, Callable, Coroutine, Dict

from aiogram import Bot, Dispatcher
from aiogram import types as aiogtypes
from aiogram.utils.exceptions import TelegramAPIError
from rasa.core.channels import InputChannel, OutputChannel, UserMessage
from sanic import Blueprint, Sanic

logger = logging.getLogger(__name__)


class TelegramOutput(OutputChannel):
    def __init__(self, dp: Dispatcher):
        self.dp = dp

    # Override
    async def send_response(self, recipient_id: str, message: Dict[str, Any]) -> None:
        if message.get("quick_replies"):
            await self.send_quick_replies(
                recipient_id,
                message.pop("text"),
                message.pop("quick_replies"),
                **message
            )
        elif message.get("image"):
            await self.send_image_url(recipient_id, message.pop("image"), caption=message.pop("text"), **message)
        else:
            await self.send_text_message(recipient_id, **message)

    def catch_exceptions(fn):
        async def wrapper(self, recipient_id: str, *args, **kwargs):
            try:
                return await fn(self, recipient_id, *args, **kwargs)
            except TelegramAPIError:
                self.dp.bot.send_message(recipient_id, "Woops! There was an issue encountered in the Telegram Bot.\nPlease report this issue.")
                logger.exception("TelegramAPIError exception in Telegram Bot:")
        return wrapper

    @catch_exceptions
    async def send_text_message(self, recipient_id: str, text: str, **kwargs) -> None:
        """Sends text message."""
        for message_part in text.strip().split("\n\n"):
            await self.dp.bot.send_message(recipient_id, message_part)

    @catch_exceptions
    async def send_image_url(self, recipient_id: str, image: str, caption: str = None, **kwargs) -> None:
        """Sends an image."""
        parsed_url = urllib.parse.urlparse(image)
        if parsed_url.scheme == 'data':
            img_buffer: bytes = b''
            mime_type, img_data = parsed_url.path.split(";", 1)
            encoding_type, img_encoded = img_data.split(',', 1)
            if encoding_type == 'base64':
                img_buffer = base64.b64decode(img_encoded)

            with io.BytesIO(img_buffer) as img_f:
                await self.dp.bot.send_photo(recipient_id, img_f, caption=caption)
        elif all([parsed_url.scheme, parsed_url.netloc]):
            # FIXME: Potential SSRF
            await self.dp.bot.send_photo(recipient_id, img_f, caption=caption)
        else:
            logger.warning("Invalid image uri received: %s...", image[:50])

class TelegramInput(InputChannel):
    @classmethod
    def name(cls):
        return "telegram_bot"

    @classmethod
    def from_credentials(cls, credentials):
        if not credentials:
            cls.raise_missing_credentials_exception()

        return cls(
            credentials.get("access_token")
        )

    def __init__(self, access_token, debug_mode: bool = True):
        self.access_token = access_token
        self.bot = Bot(self.access_token)
        self.dp = Dispatcher(self.bot)
        self._outchannel = TelegramOutput(self.dp)
        self._dispatcher_poll_tasks: Dict[str, Task] = {}

    def blueprint(
        self,
        on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        telegram_blueprint = Blueprint("telegram_blueprint", __name__)

        @self.dp.message_handler()
        async def handler(message: aiogtypes.Message):
            user_msg = UserMessage(
                text=message.text,
                output_channel=self._outchannel,
                sender_id=str(message.from_id),
                message_id=message.message_id,
                metadata={'content_type': message.content_type}
            )
            await message.answer_chat_action("typing")
            await on_new_message(user_msg)

        def start_listener(app: Sanic, loop: AbstractEventLoop) -> Coroutine[Any, Any, None]:
            task_name: str = telegram_blueprint.name
            self._dispatcher_poll_tasks[task_name] = loop.create_task(self.dp.start_polling())
            return

        def stop_listener(app: Sanic, loop: AbstractEventLoop) -> Coroutine[Any, Any, None]:
            async def _stop_listening_async():
                '''Async wrapper'''
                task_name: str = telegram_blueprint.name
                poll_task: Task = self._dispatcher_poll_tasks.get(task_name)
                self.dp.stop_polling()
                if poll_task:
                    # Wait for polling task to stop
                    await poll_task
            return _stop_listening_async()

        telegram_blueprint.before_server_start(start_listener)
        telegram_blueprint.before_server_stop(stop_listener)

        return telegram_blueprint

    def get_output_channel(self) -> OutputChannel:
        return self._outchannel
