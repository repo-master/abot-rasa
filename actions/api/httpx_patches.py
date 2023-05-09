

import json
from typing import Any, Dict, Tuple

from httpx import ByteStream

from ..common import JSONCustomEncoder


def _patched_encode_json(json_data: Any) -> Tuple[Dict[str, str], ByteStream]:
    body = json.dumps(json_data, cls=JSONCustomEncoder).encode("utf-8")
    content_length = str(len(body))
    content_type = "application/json"
    headers = {"Content-Length": content_length, "Content-Type": content_type}
    return headers, ByteStream(body)


def monkeypatch_httpx():
    from httpx import _content
    setattr(_content, 'encode_json', _patched_encode_json)
