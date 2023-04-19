
from decouple import config


BACKEND_ENDPOINT_BASE = config("BACKEND_ENDPOINT_BASE", default="http://localhost:8000")
