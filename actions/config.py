
from decouple import config

BACKEND_ENDPOINT_BASE = config("BACKEND_ENDPOINT_BASE", default="http://localhost:8000")
DUCKLING_HTTP_URL = config("RASA_DUCKLING_HTTP_URL", default="http://localhost:8001")
