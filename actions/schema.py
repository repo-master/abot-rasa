
from typing import TypedDict


class StatementContext(TypedDict):
    intent_used: str
    action_performed: str
    extra_data: str  # JSON-serialized string
