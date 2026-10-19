import os

import pytest

requires_gcp = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "true",
    reason="Set RUN_INTEGRATION_TESTS=true to run integration tests",
)
