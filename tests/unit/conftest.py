import os

import pytest

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "{SERVICE_PREFIX}-dev-project")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
