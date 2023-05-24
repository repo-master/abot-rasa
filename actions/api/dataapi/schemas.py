
from typing import Dict, Any, Optional

from httpx._types import (AuthTypes, CookieTypes, HeaderTypes, QueryParamTypes,
                          RequestContent, RequestData, RequestExtensions,
                          RequestFiles, TimeoutTypes, URLTypes)
from typing_extensions import TypedDict


DataLoaderOptions = Dict[str, Any]


class DataLoaderRequest(TypedDict):
    method: str
    url: URLTypes
    content: Optional[RequestContent]
    data: Optional[RequestData]
    files: Optional[RequestFiles]
    json: Optional[Any]
    params: Optional[QueryParamTypes]
    headers: Optional[HeaderTypes]
    cookies: Optional[CookieTypes]
    auth: Optional[AuthTypes]
    follow_redirects: Optional[bool]
    timeout: Optional[TimeoutTypes]
    extensions: Optional[RequestExtensions]


__all__ = [
    'DataLoaderRequest'
]
